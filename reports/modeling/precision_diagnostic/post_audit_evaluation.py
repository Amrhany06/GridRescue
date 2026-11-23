"""Compare archived GridRescue scores on the fixed pilot without fitting a model."""
import argparse
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'cloud_expansion'))
from diagnostic import (ABLATION, ARCHIVE, CHAMPION, FOLDS, KEY, ROOT, checked_arrays,
                        load_json, masks, metrics, ranking, sha256, threshold_curve, validate_period,
                        write_json)
from cloud_data import cohort_roles, fingerprint
from cloud_train import flag_workload, recall_cutoffs
from thresholds import select_thresholds

CLOUD = HERE.parent / 'cloud_expansion'
TARGETS = (40, 50, 60)
MATCHED = (.55, .60)
ABLATION_SHA256 = {
    'ablation_2021.parquet': 'dbd67d6a6d879311e040af5929e1ded02eb355e712c1b3ada5764fff7e363f5f',
    'ablation_oof_2018_H2.parquet': '08cecc0f05837cb6676b445e832c332a2695587cf6c133b1f51a392168fd63ca',
    'ablation_oof_2019.parquet': 'a53723ddfdcc516597d7a3c5f1df7f05a1ede3de5c9c39717acc36442ac66098',
    'ablation_oof_2020.parquet': '93b5696cbf0eda517c5af321b48b8b8a8b0a76e08ec9e5bb48cfd5abf0096ec8',
}


def checked_cohort(frame, period, expected):
    if not isinstance(frame.timestamp.dtype, pd.DatetimeTZDtype) or str(frame.timestamp.dt.tz) != 'UTC':
        raise ValueError('Archived score timestamps must explicitly be UTC')
    validate_period(frame.timestamp, period)
    actual = fingerprint(frame)
    if actual != expected:
        raise ValueError(f'{period} row identities or labels differ from the frozen cohort')
    return actual


def frozen_policy(folds, pins, *, incumbent=False):
    if set(folds) != set(FOLDS) or set(pins) != set(FOLDS):
        raise ValueError('Policy requires the three frozen training-period OOF cohorts')
    identities = {period: checked_cohort(folds[period], period, pins[period]) for period in FOLDS}
    pooled = pd.concat([folds[period] for period in FOLDS], ignore_index=True)
    y, score = checked_arrays(pooled.candidate_y, pooled.score)
    cutoffs = recall_cutoffs(y, score, TARGETS)
    if incumbent:
        cutoffs['incumbent'] = select_thresholds(threshold_curve(y, score))['accuracy_recall_60']
    return {'comparison': 'float64 score > cutoff', 'folds': identities, 'oof': fingerprint(pooled),
            'cutoffs': cutoffs, 'actual_oof_recall': {name: policy_metrics(y, score, value)['recall']
                                                     for name, value in cutoffs.items()}}


def ranking_metrics(y, score):
    y, score = checked_arrays(y, score)
    result = ranking(y, score)
    if y.all():
        result['average_precision'] = 1.
    matched = dict.fromkeys(f'{target:.2f}' for target in MATCHED)
    if y.any() and not y.all():
        curve = threshold_curve(y, score)
        for target in MATCHED:
            point = curve.loc[curve.recall.ge(target)].iloc[0]
            matched[f'{target:.2f}'] = {'recall': float(point.recall), 'precision': float(point.precision)}
    elif y.all():
        # With one class, selecting whole score ties can still overshoot a recall coordinate.
        for target in MATCHED:
            crossing = np.sort(score)[-int(np.ceil(len(y) * target))]
            matched[f'{target:.2f}'] = {'recall': float(np.mean(score >= crossing)), 'precision': 1.}
    return {**result, 'rows': len(y), 'positives': int(y.sum()), 'prevalence': float(y.mean()),
            'matched_recall': matched}


def policy_metrics(y, score, cutoff):
    result = metrics(y, score, cutoff, rank={})
    result['fp_rows_per_1000'] = float(result.pop('false_alarms_per_1000'))
    return result


def workload(frame, flags):
    flags = np.asarray(flags, dtype=bool)
    result = flag_workload(frame, flags)
    positive = flag_workload(frame.assign(candidate_y=flags), frame.candidate_y.eq(1))
    county_days = len(frame.assign(day=frame.timestamp.dt.floor('D'))[['fips_code', 'day']].drop_duplicates())
    return {**result, 'eligible_county_days': county_days, 'eligible_row_hours': len(frame) / 4,
            'flag_runs_per_eligible_county_day': result['flag_runs'] / county_days,
            'all_negative_runs_per_eligible_county_day': result['runs_all_rows_negative'] / county_days,
            'positive_label_runs': positive['flag_runs'],
            'positive_runs_with_flag': positive['flag_runs'] - positive['runs_all_rows_negative']}


def paired_blocks(frame, left, right, left_cutoff, right_cutoff, *, days, replicates, seed):
    """Resample shared nonoverlapping UTC blocks, with all counties drawn together."""
    if days not in (7, 14) or replicates < 2:
        raise ValueError('Use 7- or 14-day blocks and at least two replicates')
    start = pd.Timestamp('2020-12-28', tz='UTC')  # Monday spanning the start of development.
    _, blocks = np.unique((frame.timestamp - start).dt.days // days, return_inverse=True)
    count = int(blocks.max()) + 1
    if count < 2:
        raise ValueError('At least two observed time blocks are required')
    y, left = checked_arrays(frame.candidate_y, left)
    _, right = checked_arrays(y, right)
    if not y.any():
        raise ValueError('Paired recall and AP require observed positives')

    def prepare(score, cutoff):
        order = np.argsort(-score, kind='stable')
        sorted_score = score[order]
        ends = np.flatnonzero(np.r_[sorted_score[1:] != sorted_score[:-1], True])
        chosen = score > cutoff
        return (ends, y[order], blocks[order],
                np.bincount(blocks[chosen & (y == 1)], minlength=count),
                np.bincount(blocks[chosen & (y == 0)], minlength=count))

    def measure(model, multiplicity, total):
        ends, labels, ids, tp, fp = model
        weights = multiplicity[ids]
        positives = np.cumsum(weights * labels)[ends]
        selected = np.cumsum(weights)[ends]
        precision = positives / np.maximum(selected, 1)
        recall = positives / positives[-1]
        return [np.sum(np.diff(recall, prepend=0) * precision),
                *(precision[np.searchsorted(recall, target)] for target in MATCHED),
                (tp @ multiplicity) / positives[-1], 1000 * (fp @ multiplicity) / total]

    models = (prepare(left, left_cutoff), prepare(right, right_cutoff))
    rng = np.random.default_rng(seed)
    all_rows = np.bincount(blocks)
    positive_rows = np.bincount(blocks, weights=y)
    deltas = []
    for draw in rng.multinomial(count, np.full(count, 1 / count), size=replicates):
        if positive_rows @ draw:
            total = all_rows @ draw
            deltas.append(np.subtract(*(measure(model, draw, total) for model in models)))
    names = ['average_precision', 'precision_at_55_recall', 'precision_at_60_recall', 'actual_recall',
             'fp_rows_per_1000']
    intervals = np.percentile(deltas, [2.5, 97.5], axis=0).T.tolist() if deltas else [None] * len(names)
    return {'days': days, 'blocks': count, 'block_origin_utc': start.isoformat(), 'seed': seed,
            'requested_replicates': replicates, 'usable_replicates': len(deltas),
            'intervals': dict(zip(names, intervals, strict=True))}


def run(output, replicates):
    if output.exists():
        raise FileExistsError('Choose a new replay output path')
    evidence_path = HERE / 'results/run_evidence.json'
    previous = load_json(evidence_path)['input_sha256']
    inputs = {}

    def checked_input(path, expected=None):
        relative = path.relative_to(ROOT).as_posix()
        identity = sha256(path)
        if expected is not None and identity != expected:
            raise ValueError(f'Archived input digest mismatch: {relative}')
        inputs[relative] = identity
        return path

    def archived(path, columns=None):
        pin = previous[path.relative_to(ROOT).as_posix()]
        return pd.read_parquet(checked_input(path, pin), columns=columns)

    reference = load_json(checked_input(CLOUD / 'reference_manifest.json'))
    spec = load_json(checked_input(CLOUD / 'experiment_manifest.json'))
    source = load_json(checked_input(CLOUD / 'source_manifest.json'))
    checked_input(evidence_path)
    selections = {}
    for name in ('selection.json', 'config.json', 'full_fits.json'):
        path = ARCHIVE / name
        selections[name] = load_json(checked_input(path, previous[path.relative_to(ROOT).as_posix()]))
    depth = selections['selection.json']['selection'][CHAMPION]['depth']
    rules = load_json(checked_input(HERE / 'results/frozen_thresholds.json'))['models']
    first = archived(ARCHIVE / 'predictions_2021.parquet', [*KEY, CHAMPION])
    path = HERE / 'results/ablation_2021.parquet'
    second = pd.read_parquet(checked_input(path, ABLATION_SHA256[path.name]))
    for frame in (first, second):
        checked_cohort(frame, '2021', reference['validation']['overall'])
    frame = first.merge(second.rename(columns={'score': ABLATION}), on=KEY, validate='one_to_one')
    pins = {period: reference['folds'][period]['validation'] for period in FOLDS}
    policies = {}
    for model in (CHAMPION, ABLATION):
        folds = {}
        for period in FOLDS:
            if model == CHAMPION:
                folds[period] = archived(ARCHIVE / f'oof_{CHAMPION}_depth{depth}_{period}.parquet')
            else:
                path = HERE / 'results' / f'ablation_oof_{period}.parquet'
                folds[period] = pd.read_parquet(checked_input(path, ABLATION_SHA256[path.name]))
        policies[model] = frozen_policy(folds, pins, incumbent=model == CHAMPION)
        if policies[model]['cutoffs'] != rules[model]:
            raise ValueError(f'Replayed OOF policies differ from the archive for {model}')

    roles, _, _ = cohort_roles(reference)
    if set(frame.fips_code) != set(roles):
        raise ValueError('Development predictions do not cover the frozen geography')
    cohort = pd.DataFrame(reference['counties'])
    groups = masks(frame, cohort)
    state = frame.fips_code.map(cohort.set_index('fips_code').state)
    groups.update({f'state_{name}': state.eq(name).to_numpy() for name in sorted(state.unique())})
    groups['seen_state'] = groups['seen'] | groups['unseen_county']
    ranks, decisions, workloads = {}, {}, {}
    for model in policies:
        ranks[model], decisions[model], workloads[model] = {}, {}, {}
        for group, mask in groups.items():
            sample = frame.loc[mask]
            y, score = checked_arrays(sample.candidate_y, sample[model])
            ranks[model][group] = ranking_metrics(y, score)
            decisions[model][group] = {name: policy_metrics(y, score, cutoff)
                                       for name, cutoff in policies[model]['cutoffs'].items()}
            if group in ('all', 'seen_state', 'seen', 'unseen_county', 'unseen_state'):
                workloads[model][group] = {name: workload(sample, score > cutoff)
                                           for name, cutoff in policies[model]['cutoffs'].items()}
        macro = {}
        for level in ('state', 'county'):
            values = [item['average_precision'] for name, item in ranks[model].items()
                      if name.startswith(level + '_') and item['average_precision'] is not None]
            macro[level] = float(np.mean(values)) if values else None
        ranks[model]['macro_ap'] = macro

    champion = decisions[CHAMPION]['all']['incumbent']
    benchmark = spec['benchmark']
    if tuple(champion[key] for key in ('tp', 'fp', 'tn', 'fn')) != (66810, 129696, 334481, 51545):
        raise ValueError('Archived champion confusion counts did not reproduce')
    np.testing.assert_allclose(
        [ranks[CHAMPION]['all']['average_precision'], *(champion[key] for key in
          ('precision', 'recall', 'accuracy', 'fp_rows_per_1000'))],
        [benchmark[key] for key in ('average_precision', 'precision', 'recall', 'accuracy',
                                    'false_positive_rows_per_1000')], atol=1e-9, rtol=0)

    paired = [paired_blocks(frame, frame[CHAMPION], frame[ABLATION], rules[CHAMPION]['target_60'],
                            rules[ABLATION]['target_60'], days=days, replicates=replicates, seed=17)
              for days in (7, 14)]
    for module in (Path(__file__), HERE / 'diagnostic.py', CLOUD / 'cloud_data.py',
                   CLOUD / 'cloud_train.py', ARCHIVE.parent / 'thresholds.py'):
        checked_input(module)
    summary = {'protocol': 'GridRescue post-audit archive replay v1',
               'scope': '2021 repeatedly consulted development; the same eligible rows for both models',
               'source': source, 'source_verification': 'Pinned archive lineage; raw files not reread',
               'inputs_sha256': inputs, 'environment': {'python': platform.python_version(),
                   'pandas': pd.__version__, 'numpy': np.__version__, 'scikit_learn': sklearn.__version__},
               'cohort': reference['validation'], 'training_cohort': reference['train']['overall'],
               'coverage_from_independent_audit': {
                   'evidence': 'reports/modeling/independent_audit/DATA_INTEGRITY_AUDIT.md',
                   'clean_positive_current_2021_anchors': 642891, 'complete_eligible': 582532,
                   'incomplete': 60359, 'incomplete_with_observed_crossing': 5277,
                   'incomplete_with_no_observed_future_slot': 1543},
               'counties': reference['counties'], 'policy': policies, 'ranking': ranks, 'decisions': decisions,
               'workload': workloads,
               'workload_definition': 'Consecutive flags within a county at exact 15-minute spacing. '
                   'Rates use county-days and quarter-hours with eligible rows. Overlap is observational.',
               'paired_difference': {'contrast': 'champion minus no-hour ablation',
                                     'policy': 'each model uses its frozen 60% OOF recall crossing', 'blocks': paired}}
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, summary)
    print(f'{output}: {len(frame):,} rows, {len(groups)} slices; champion archive metrics reproduced')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--replicates', type=int, default=2000)
    run(**vars(parser.parse_args()))
