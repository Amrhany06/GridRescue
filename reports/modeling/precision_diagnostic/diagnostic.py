"""Local, development-only comparison using the archived GridRescue cohort."""
import argparse
import json
import platform
import shutil
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import psutil
import sklearn

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'local_improvement'))
from train_local import (ARTIFACTS, BASE_DATA, BASE_REPORT, FOLDS, KEY, PRIMARY, ROOT,
                         XGB_SETTINGS, aligned, chronological_folds, fit, masks,
                         memory_measurement, metadata, metrics, model_for, prior_scores,
                         probability, read_split, sha256, threshold_curve, write_json)
from thresholds import checked_arrays, ranking

ARCHIVE = HERE.parent / 'local_improvement' / 'model_results'
HISTORY = ARTIFACTS / 'history'
# A no-fit replay must also be able to unpickle the archived CPU-only estimator.
sys.path.insert(0, str(ARTIFACTS / 'deps_local'))
CHAMPION = 'xgb_history_state'
ABLATION = 'xgb_history_without_hour_state'
TARGETS = (40, 50, 60)
MODELS = (*PRIMARY, ABLATION)
COLORS = dict(zip(MODELS, ('#718096', '#ab7357', '#329282', '#214fa6', '#a43a8a'), strict=True))
NAMES = dict(zip(MODELS, ('RF original', 'RF longer', 'XGB original', 'XGB longer', 'XGB without hour'), strict=True))
PERIODS = {'2018_H2': ('2018-07-01', '2019-01-01'), '2019': ('2019-01-01', '2020-01-01'),
           '2020': ('2020-01-01', '2021-01-01'), '2021': ('2021-01-01', '2022-01-01')}


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def validate_period(timestamp, period):
    """Check the allowlisted period and strict three-hour label horizon purge."""
    if period not in PERIODS:
        raise ValueError(f'Unknown development period: {period}')
    start, end = (pd.Timestamp(value, tz='UTC') for value in PERIODS[period])
    if timestamp.empty or not (timestamp.ge(start) & timestamp.lt(end - pd.DateOffset(hours=3))).all():
        raise ValueError(f'Timestamps outside purged period {period}')


def check_alignment(left, right):
    """Reject invalid keys or labels before the archived exact ordered comparison."""
    for frame in (left, right):
        if (frame[KEY].isna().any().any() or not frame.candidate_y.isin([0, 1]).all()
                or not frame.fips_code.astype(str).str.fullmatch(r'[0-9]{5}').all()):
            raise ValueError('Invalid observation key or label')
    aligned(left, right)


def select_targets(curve):
    """Take the first qualifying score block, which flags the fewest rows."""
    return {target: float(curve.loc[curve.recall.ge(target / 100), 'threshold'].iloc[0])
            for target in TARGETS}


def operating_point(y, score, threshold, rank=None):
    result = metrics(y, score, threshold, rank)
    negatives = result['tn'] + result['fp']
    return {**result, 'false_positive_rate': result['fp'] / negatives if negatives else None}


def check_reloaded_scores(variant, actual, expected):
    if variant == 'rf_original_state':
        # The archived two-thread forest can add its trees in different orders.
        np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-14)
    else:
        np.testing.assert_array_equal(actual, expected)


def make_ablation(depth):
    """Reuse the upstream factory and change only the numeric column selector."""
    model = model_for(CHAMPION, depth)
    prep = model.named_steps['prepare']
    (name, pipeline, columns), state_block = prep.transformers
    if columns.count('hour_utc') != 1:
        raise ValueError('Expected a single hour_utc input in the archived configuration')
    prep.set_params(transformers=[(name, pipeline, [col for col in columns if col != 'hour_utc']), state_block])
    return model


def hourly_summary(frame, score, threshold, group_columns=()):
    """Summarize eligible rows at each UTC hour, optionally by geography."""
    y, score = checked_arrays(frame.candidate_y, score)
    positive = y == 1
    chosen = score > threshold
    columns = [*group_columns, 'hour_utc']
    work = frame[columns + ['coverage_3h']].assign(score=score, positive=positive,
        tp=chosen & positive, fp=chosen & ~positive, negative_score=np.where(positive, np.nan, score),
        positive_score=np.where(positive, score, np.nan))
    result = work.groupby(columns, observed=True, sort=True).agg(
        rows=('score', 'size'), positive=('positive', 'sum'), mean_score=('score', 'mean'),
        mean_positive_score=('positive_score', 'mean'), mean_negative_score=('negative_score', 'mean'),
        mean_coverage_3h=('coverage_3h', 'mean'), tp=('tp', 'sum'), fp=('fp', 'sum')).reset_index()
    result['negative'] = result.rows - result.positive
    result['prevalence'] = result.positive / result.rows
    result['predicted_positive_rate'] = (result.tp + result.fp) / result.rows
    result['recall'] = result.tp / result.positive
    result['precision'] = result.tp / (result.tp + result.fp)
    result['false_positive_rate'] = result.fp / result.negative
    result['false_alarms_per_1000'] = 1000 * result.fp / result.rows
    totals = result.groupby(list(group_columns), observed=True).rows.transform('sum') if group_columns else result.rows.sum()
    result['share_of_eligible_rows'] = result.rows / totals
    return result


def snapshot(cohort, selection):
    """Check protected files against archived digests and fingerprint bounded inputs."""
    earlier = BASE_REPORT / 'model_results'
    config = load_json(earlier / 'configuration.json')
    expected = {ROOT / path: digest for path, digest in config['protected_hashes'].items()}
    archived = load_json(ARCHIVE / 'full_fits.json')
    for variant in ('numeric', 'state', 'fips', 'both'):
        expected[BASE_DATA / 'models' / f'{variant}.joblib'] = load_json(
            earlier / f'evidence_2021_{variant}.json')['fit']['model_sha256']
    for variant, evidence in archived.items():
        if 'sha256' in evidence:
            expected[ARTIFACTS / 'models' / f'{variant}.joblib'] = evidence['sha256']
    inputs = [ARCHIVE / name for name in ('selection.json', 'config.json', 'full_fits.json', 'permutation_ap.json',
                                           'predictions_2021.parquet')]
    inputs += [earlier / f'predictions_{period}.parquet' for period in PERIODS]
    inputs += [HISTORY / 'audit.json', BASE_REPORT / 'cohort.json']
    for period in FOLDS:
        for variant in PRIMARY[1:]:
            depth = selection[variant]['depth']
            stem = f'{variant}_depth{depth}' if depth is not None else variant
            inputs.append(ARCHIVE / f'oof_{stem}_{period}.parquet')
    for code in sorted(cohort.fips_code.str[:2].unique()):
        for split in ('train', 'validation'):
            inputs.extend(sorted((HISTORY / f's{code}' / f'split={split}').glob('part-*.parquet')))
    actual = {path: sha256(path) for path in dict.fromkeys([*expected, *inputs])}
    for path, digest in expected.items():
        if actual[path] != digest:
            raise ValueError(f'Protected artifact digest mismatch: {path}')
    return {path.relative_to(ROOT).as_posix(): digest for path, digest in actual.items()}, len(expected)


def fit_one(depth, train):
    model = make_ablation(depth)
    start = time.perf_counter()
    with memory_measurement() as memory:
        _, warnings = fit(model, train, train.candidate_y)
    return model, dict(seconds=time.perf_counter() - start, fit_rows=len(train), warnings=warnings,
                       width=len(model.named_steps['prepare'].get_feature_names_out()), **memory)


def prepare_oof(train, folds, selection, output, reuse, fit_log):
    """Align the four archived OOF score sets and fit only the ablation."""
    collected = []
    for fold in folds:
        period = fold['name']
        validation = train.iloc[fold['validation']]
        original = prior_scores(period)
        validate_period(original.timestamp, period)
        check_alignment(validation, original)
        frame = original[KEY].assign(period=period, rf_original_state=original.state)
        for variant in PRIMARY[1:]:
            depth = selection[variant]['depth']
            stem = f'{variant}_depth{depth}' if depth is not None else variant
            saved = pd.read_parquet(ARCHIVE / f'oof_{stem}_{period}.parquet')
            check_alignment(frame, saved)
            frame[variant] = saved.score.to_numpy()
        path = output / f'ablation_oof_{period}.parquet'
        if reuse is None:
            model, fit_log[period] = fit_one(selection[CHAMPION]['depth'], train.iloc[fold['train']])
            new = validation[KEY].assign(score=probability(model, validation))
        else:
            new = pd.read_parquet(reuse / path.name)
        check_alignment(frame, new)
        new.to_parquet(path, index=False)
        frame[ABLATION] = new.score.to_numpy()
        collected.append(frame)
        print(f'{period}: aligned {len(frame):,} OOF rows across five variants.', flush=True)
    result = pd.concat(collected, ignore_index=True)
    if result.duplicated(KEY[:2]).any():
        raise ValueError('OOF folds overlap')
    return result


def freeze_thresholds(oof, incumbent, output):
    frozen = {'source': list(FOLDS), 'oof_rows': len(oof), 'comparison': 'score > threshold',
              'selection': 'Highest cutoff meeting each pooled OOF recall target. Tied scores move together.',
              'models': {}}
    for model in MODELS:
        choices = select_targets(threshold_curve(oof.candidate_y, oof[model]))
        frozen['models'][model] = {f'target_{target}': threshold for target, threshold in choices.items()}
    frozen['models'][CHAMPION]['incumbent'] = incumbent
    path = output / 'frozen_thresholds.json'
    write_json(path, frozen)
    return load_json(path)['models']


def matched_curve_points(curve, group, model):
    """Compare ranking descriptively at fixed recall coordinates, with no cutoff output."""
    targets = []
    for target in TARGETS:
        row = curve.loc[curve.recall.ge(target / 100)].iloc[0]
        targets.append(dict(group=group, model=model, recall_coordinate=target / 100,
                            recall=row.recall, precision=row.precision))
    return targets


def comparison(frame, rules, period, groups, matched=None):
    records = []
    for group, group_mask in groups.items():
        sample = frame.loc[group_mask]
        y = sample.candidate_y.to_numpy()
        for model in MODELS:
            score = sample[model].to_numpy()
            rank = ranking(y, score)
            if matched is not None and (group == 'all' or model in (CHAMPION, ABLATION)):
                matched.extend(matched_curve_points(threshold_curve(y, score), group, model))
            for rule, threshold in rules[model].items():
                point = operating_point(y, score, threshold, rank)
                records.append(dict(period=period, model=model, group=group, rule=rule, **point,
                                    ap_above_prevalence=(point['average_precision'] - point['prevalence']
                                                         if point['average_precision'] is not None else None)))
    return pd.DataFrame(records)


def hour_evidence(oof, train, final_scores, validation, rules, cohort, output):
    columns = ['hour_utc', 'reporting_coverage_180m']
    train_features = train.set_index(KEY[:2])[columns].reindex(oof.set_index(KEY[:2]).index).reset_index(drop=True)
    location = cohort.set_index('fips_code').state
    hourly = []
    for period, scored, features in [(period, part, train_features.loc[part.index])
                                      for period, part in oof.groupby('period', sort=False)] + [
                                          ('2021', final_scores, validation[columns])]:
        frame = scored[KEY].reset_index(drop=True).assign(
            hour_utc=features.hour_utc.to_numpy(), coverage_3h=features.reporting_coverage_180m.to_numpy())
        if (not np.array_equal(frame.hour_utc, frame.timestamp.dt.hour.to_numpy())
                or not frame.coverage_3h.between(0, 1).all()):
            raise ValueError('Hour or coverage does not match the bounded feature table')
        frame['hour_utc'] = frame.hour_utc.astype(int)
        frame['state'] = frame.fips_code.map(location)
        for model, rule in ((CHAMPION, 'incumbent'), (CHAMPION, 'target_60'), (ABLATION, 'target_60')):
            for level, labels in (('all', ()), ('state', ('state',)), ('county', ('state', 'fips_code'))):
                table = hourly_summary(frame, scored[model].to_numpy(), rules[model][rule], labels)
                hourly.append(table.assign(level=level, model=model, rule=rule, period=period))
    pd.concat(hourly, ignore_index=True).to_csv(output / 'hourly_metrics.csv', index=False)


def conditional_permutation(model, validation, full_scores):
    """Break the link between hour and each row while retaining county-month hour mixes."""
    sample = validation.sample(n=20_000, random_state=17).reset_index()
    positions = sample.groupby([sample.fips_code, sample.timestamp.dt.strftime('%Y-%m')],
                               observed=True, sort=True).indices.values()
    hour = sample.hour_utc.to_numpy(copy=True)
    ap = ranking(sample.candidate_y.to_numpy(), full_scores[sample['index'].to_numpy()])['average_precision']
    rows = []
    for seed in (17, 31, 47):
        shuffled = hour.copy()
        rng = np.random.default_rng(seed)
        for index in positions:
            shuffled[index] = rng.permutation(hour[index])
        score = probability(model, sample.assign(hour_utc=shuffled))
        shuffled_ap = ranking(sample.candidate_y.to_numpy(), score)['average_precision']
        rows.append(dict(seed=seed, sample_rows=len(sample), original_ap=ap, shuffled_ap=shuffled_ap,
                         ap_drop=ap - shuffled_ap, changed_fraction=float(np.mean(hour != shuffled))))
    return rows


def final_predictions(train, validation, depth, output, reuse, fit_log):
    saved = pd.read_parquet(ARCHIVE / 'predictions_2021.parquet')
    earlier = prior_scores('2021')
    validate_period(saved.timestamp, '2021')
    check_alignment(validation, saved)
    check_alignment(earlier, saved)
    np.testing.assert_array_equal(saved.rf_original_state, earlier.state)
    model_path = output / 'ablation.joblib'
    if reuse is None:
        model, fit_log['final'] = fit_one(depth, train)
        scores = probability(model, validation)
        with model_path.open('xb') as stream:
            joblib.dump(model, stream, compress=3)
    else:
        shutil.copyfile(reuse / model_path.name, model_path)
        cached = pd.read_parquet(reuse / 'ablation_2021.parquet')
        check_alignment(saved, cached)
        scores = cached.score.to_numpy()
    reload = joblib.load(model_path)
    check_reloaded_scores(ABLATION, probability(reload, validation), scores)
    final = saved[[*KEY, *PRIMARY]].assign(**{ABLATION: scores})
    validation[KEY].assign(score=scores).to_parquet(output / 'ablation_2021.parquet', index=False)
    reloaded = {}
    for variant in PRIMARY:
        path = BASE_DATA / 'models/state.joblib' if variant == 'rf_original_state' else ARTIFACTS / 'models' / f'{variant}.joblib'
        model = joblib.load(path)
        check_reloaded_scores(variant, probability(model, validation.iloc[::997]), final[variant].iloc[::997])
        reloaded[variant] = len(validation.iloc[::997])
        if variant == CHAMPION:
            settings = {key: model.named_steps['classifier'].get_xgb_params()[key]
                        for key in reload.named_steps['classifier'].get_xgb_params()}
            if settings != reload.named_steps['classifier'].get_xgb_params():
                raise ValueError('Ablation classifier settings differ from the archived champion')
            conditional = conditional_permutation(model, validation, final[variant].to_numpy())
        del model
    reloaded[ABLATION] = len(validation)
    pd.DataFrame(conditional).to_csv(output / 'hour_conditional_permutation.csv', index=False)
    return final, reloaded


def curve_files(frame, output, period):
    for model in MODELS:
        curve = threshold_curve(frame.candidate_y, frame[model])
        # Zero-recall empty endpoint follows the conventional plotting convention.
        curve.loc[0, 'precision'] = 1.0
        curve[['recall', 'precision']].to_parquet(output / f'pr_{period}_{model}.parquet', index=False)


def resources():
    return {'available_ram': psutil.virtual_memory().available, 'disk_free': shutil.disk_usage(ROOT).free}


def run(output, reuse, run_memory):
    start = resources()
    if start['available_ram'] < 2.25 * 2**30 or start['disk_free'] < 2 * 2**30:
        raise MemoryError(f'Insufficient local resources: {start}')
    output.mkdir()
    prior = load_json(ARCHIVE / 'selection.json')
    selection = prior['selection']
    config = load_json(ARCHIVE / 'config.json')
    if prior['champion'] != CHAMPION or config['xgb_settings'] != XGB_SETTINGS:
        raise ValueError('Archived champion or XGBoost configuration differs')
    cohort = metadata()
    train = read_split(HISTORY, 'train', cohort)
    folds = chronological_folds(train)
    fold_contract = [{**fold, 'train': len(fold['train']), 'validation': len(fold['validation'])} for fold in folds]
    if fold_contract != config['folds'] or len(train) != config['train_rows']:
        raise ValueError('Archived training cohort or fold contract differs')
    fits = {}
    oof = prepare_oof(train, folds, selection, output, reuse, fits)
    incumbent = selection[CHAMPION]['rules']['accuracy_recall_60']
    rules = freeze_thresholds(oof, incumbent, output)
    if reuse is not None and rules != load_json(reuse / 'frozen_thresholds.json')['models']:
        raise ValueError('Replay selected different cutoffs')
    print('OOF thresholds frozen. Loading 2021 development data.', flush=True)
    # Fingerprinting archived 2021 evidence is also postponed until the lock is on disk.
    before, protected_count = snapshot(cohort, selection)
    validation = read_split(HISTORY, 'validation', cohort)
    final, reloaded = final_predictions(train, validation, selection[CHAMPION]['depth'], output, reuse, fits)
    print(f'2021: aligned {len(final):,} development rows and checked saved-model reloads.', flush=True)
    pooled = [('pooled_oof', oof), *oof.groupby('period', sort=False)]
    fold_results = pd.concat([comparison(part, rules, period, {'all': np.ones(len(part), dtype=bool)})
                              for period, part in pooled], ignore_index=True)
    dev_results = comparison(final, rules, '2021', masks(final, cohort), matched := [])
    counties = cohort[['fips_code', 'county', 'state', 'role']].assign(group=lambda data: 'county_' + data.fips_code)
    dev_results = dev_results.merge(counties, on='group', how='left', validate='many_to_one')
    fold_results.to_csv(output / 'oof_metrics.csv', index=False)
    dev_results.to_csv(output / 'development_metrics.csv', index=False)
    pd.DataFrame(matched).to_csv(output / 'development_matched_recall.csv', index=False)
    curve_files(oof, output, 'oof')
    curve_files(final, output, 'development')
    hour_evidence(oof, train, final, validation, rules, cohort, output)
    archive_importance = load_json(ARCHIVE / 'permutation_ap.json')[CHAMPION]
    write_json(output / 'archived_hour_permutation.json', next(row for row in archive_importance if row['feature'] == 'hour_utc'))
    after, _ = snapshot(cohort, selection)
    if before != after:
        raise ValueError('An archived input changed during the diagnostic')
    from plots import make_plots
    make_plots(output)
    from xgboost import __version__ as xgb_version
    fit_mode = 'train' if reuse is None else ('reuse' if (reuse / 'run_evidence.json').exists() else 'checkpoint')
    write_json(output / 'run_evidence.json', dict(
        status='PASS', fit_mode=fit_mode, fits=fits, folds=fold_contract,
        train_rows=len(train), oof_rows=len(oof), development_rows=len(final), development_positive=int(final.candidate_y.sum()),
        reloaded_rows=reloaded, protected_artifact_count=protected_count, input_sha256=before,
        ablation_sha256=sha256(output / 'ablation.joblib'), xgb_depth=selection[CHAMPION]['depth'], xgb_settings=XGB_SETTINGS,
        python=platform.python_version(), packages={'xgboost': xgb_version, 'scikit_learn': sklearn.__version__,
                                                   'pandas': pd.__version__, 'numpy': np.__version__},
        resources_at_start=start, resources_at_end=resources(), resource_monitor=dict(run_memory)))
    print(f'Wrote diagnostic results and plots to {output}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New diagnostics directory')
    parser.add_argument('--reuse-ablation', type=Path, help='Previous run with all ablation scores and model, no refitting')
    args = parser.parse_args()
    with memory_measurement() as run_memory:
        run(args.output, args.reuse_ablation, run_memory)
