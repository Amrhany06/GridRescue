"""Check a fresh replay and independently validate selected metric values."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, average_precision_score, balanced_accuracy_score,
                             confusion_matrix, fbeta_score, precision_score, recall_score)

from diagnostic import (ABLATION, ARCHIVE, CHAMPION, FOLDS, MODELS, PRIMARY, TARGETS, check_alignment,
                        load_json, metadata, prior_scores, sha256, snapshot, write_json)


def verify_metrics(frame, table, rules, verify_selection):
    y = frame.candidate_y.to_numpy()
    for model in MODELS:
        score = frame[model].to_numpy(dtype='float64')
        ap = average_precision_score(y, score)
        for rule, cutoff in rules[model].items():
            predicted = score > cutoff
            tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
            row = table.loc[(model, rule)]
            np.testing.assert_array_equal([tn, fp, fn, tp], row[['tn', 'fp', 'fn', 'tp']])
            expected = [ap, accuracy_score(y, predicted), precision_score(y, predicted, zero_division=0), recall_score(y, predicted),
                        fbeta_score(y, predicted, beta=1), fbeta_score(y, predicted, beta=2),
                        balanced_accuracy_score(y, predicted), fp / (fp + tn), 1000 * fp / len(y)]
            columns = ['average_precision', 'accuracy', 'precision', 'recall', 'f1', 'f2', 'balanced_accuracy',
                       'false_positive_rate', 'false_alarms_per_1000']
            np.testing.assert_allclose(expected, row[columns].to_numpy(dtype=float), rtol=0, atol=1e-12)
            np.testing.assert_allclose(cutoff, row.threshold, rtol=0, atol=1e-16)
            if verify_selection and rule != 'incumbent':
                minimum = int(rule.split('_')[1]) / 100
                stricter = np.count_nonzero((score > np.nextafter(cutoff, np.inf)) & (y == 1))
                if not stricter / y.sum() < minimum <= tp / y.sum():
                    raise ValueError(f'Cutoff is not the highest one satisfying {rule} for {model}')


def verify_geography(final, table, rules):
    """Recreate every geographic group from county metadata and raw decisions."""
    cohort = metadata().set_index('fips_code')
    role = final.fips_code.map(cohort.role)
    is_original = final.fips_code.isin(cohort.index[cohort.original])
    groups = {'seen': role.eq('seen'), 'original': is_original, 'other_seen': role.eq('seen') & ~is_original,
              'unseen_state': role.eq('unseen_state'), 'unseen_county': role.eq('unseen_county')}
    groups.update({f'county_{code}': final.fips_code.eq(code) for code in cohort.index})
    nonoverall = table.loc[table.group.ne('all')]
    if set(groups) != set(nonoverall.group):
        raise ValueError('Unexpected geographic group coverage')
    for group, included in groups.items():
        frame = final.loc[included]
        expected = table.loc[table.group.eq(group)].set_index(['model', 'rule'])
        np.testing.assert_array_equal(len(frame), expected.rows.to_numpy())
        np.testing.assert_allclose(expected.prevalence, frame.candidate_y.mean(), rtol=0, atol=1e-12)
        verify_metrics(frame, expected, rules, False)
    return len(nonoverall)


def verify_hours(final, table, rules):
    """Reconcile each 2021 hourly count and rate against aligned scores and UTC timestamps."""
    expected = table.loc[table.period.eq('2021')]
    cohort = metadata().set_index('fips_code')
    fips = final.fips_code.astype(str)
    location = fips.map(cohort.state)
    fields = ['rows', 'positive', 'tp', 'fp', 'negative', 'prevalence', 'false_positive_rate', 'mean_score']
    checked = 0
    for (model, rule, level), stored in expected.groupby(['model', 'rule', 'level']):
        keys = {'all': [], 'state': ['state'], 'county': ['state', 'fips_code']}[level] + ['hour_utc']
        score = final[model].astype('float64')
        predicted = score.gt(rules[model][rule])
        positive = final.candidate_y.eq(1)
        rows = pd.DataFrame({'state': location, 'fips_code': fips,
                             'hour_utc': final.timestamp.dt.hour, 'positive': positive,
                             'tp': predicted & positive, 'fp': predicted & ~positive, 'score': score})
        cross = rows.groupby(keys, observed=True).agg(rows=('score', 'size'), positive=('positive', 'sum'),
                                                      tp=('tp', 'sum'), fp=('fp', 'sum'), mean_score=('score', 'mean'))
        cross['negative'] = cross.rows - cross.positive
        cross['prevalence'] = cross.positive / cross.rows
        cross['false_positive_rate'] = cross.fp / cross.negative
        stored = stored.set_index(keys).sort_index()
        pd.testing.assert_index_equal(cross.index, stored.index, exact=False)
        np.testing.assert_allclose(cross[fields], stored[fields], rtol=0, atol=1e-12)
        checked += len(stored)
    if checked != 3 * 24 * (1 + cohort.state.nunique() + len(cohort)):
        raise ValueError('Unexpected 2021 hourly table coverage')
    return checked


def run(original, replay, evidence):
    base = load_json(original / 'run_evidence.json')
    repeated = load_json(replay / 'run_evidence.json')
    if (base['status'] != 'PASS' or repeated['status'] != 'PASS'
            or base['fit_mode'] not in ('train', 'checkpoint') or repeated['fit_mode'] != 'reuse'):
        raise ValueError('Verification requires a complete diagnostic and a completed no-fit replay')
    for key in ('input_sha256', 'reloaded_rows', 'ablation_sha256', 'folds'):
        if base[key] != repeated[key]:
            raise ValueError(f'Run evidence differs for {key}')
    if len(base['fits']) != (4 if base['fit_mode'] == 'train' else 0) or repeated['fits']:
        raise ValueError('Unexpected fit count')
    names = {p.name for p in original.iterdir()} - {'run_evidence.json'}
    if names != ({p.name for p in replay.iterdir()} - {'run_evidence.json'}):
        raise ValueError('Replay changed the set of outputs')
    for name in names:
        if sha256(original / name) != sha256(replay / name):
            raise ValueError(f'Replay changed output {name}')

    selection = load_json(ARCHIVE / 'selection.json')['selection']
    current_inputs, protected_count = snapshot(metadata(), selection)
    if current_inputs != base['input_sha256'] or protected_count != base['protected_artifact_count']:
        raise ValueError('An archived or protected artifact changed after the diagnostic')
    rules = load_json(original / 'frozen_thresholds.json')['models']
    if rules[CHAMPION]['incumbent'] != selection[CHAMPION]['rules']['accuracy_recall_60']:
        raise ValueError('Incumbent cutoff differs from the archived selection')
    parts = []
    for period in FOLDS:
        base_scores = prior_scores(period)
        scores = base_scores[['candidate_y']].assign(rf_original_state=base_scores.state)
        for model in PRIMARY[1:]:
            depth = selection[model]['depth']
            stem = f'{model}_depth{depth}' if depth is not None else model
            saved = pd.read_parquet(ARCHIVE / f'oof_{stem}_{period}.parquet')
            check_alignment(base_scores, saved)
            scores[model] = saved.score.to_numpy()
        no_hour = pd.read_parquet(original / f'ablation_oof_{period}.parquet')
        check_alignment(base_scores, no_hour)
        parts.append(scores.assign(**{ABLATION: no_hour.score.to_numpy()}))
    pooled = pd.concat(parts, ignore_index=True)
    final = pd.read_parquet(ARCHIVE / 'predictions_2021.parquet')
    no_hour = pd.read_parquet(original / 'ablation_2021.parquet')
    check_alignment(final, no_hour)
    final = final.assign(**{ABLATION: no_hour.score.to_numpy()})
    for file, period, frame, verify_selection in (('oof', 'pooled_oof', pooled, True),
                                                  ('development', '2021', final, False)):
        table = pd.read_csv(original / f'{file}_metrics.csv', dtype={'period': str}, float_precision='round_trip')
        all_rows = table.query('period == @period and group == "all"').set_index(['model', 'rule'])
        verify_metrics(frame, all_rows, rules, verify_selection)
    geography = verify_geography(final, table, rules)
    hourly = verify_hours(final, pd.read_csv(original / 'hourly_metrics.csv', dtype={'fips_code': str, 'period': str}), rules)
    write_json(evidence, dict(status='PASS', replay_files_identical=len(names), independent_metric_rows=2 * (
        len(MODELS) * len(TARGETS) + 1), independent_oof_target_checks=len(MODELS) * len(TARGETS),
        independent_geographic_metric_rows=geography, independent_2021_hourly_rows=hourly,
        no_fit_replay=True, reloaded_rows_per_model=base['reloaded_rows'], protected_artifact_count=protected_count,
        input_digest_checks=len(current_inputs)))
    print(f'Verified {len(names)} identical replay files, 32 overall and {geography} geographic metric rows, '
          f'{hourly} hourly rows, and 15 OOF cutoff decisions.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original', type=Path)
    parser.add_argument('replay', type=Path)
    parser.add_argument('evidence', type=Path)
    run(**vars(parser.parse_args()))
