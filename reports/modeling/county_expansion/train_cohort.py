"""Run four fixed forest variants on the frozen, isolated expansion cohort."""
import argparse
from contextlib import contextmanager
import threading
import time

import joblib
import numpy as np
import pandas as pd
import psutil
from sklearn.preprocessing import OneHotEncoder

from prepare_cohort import ROOT, STATE_ORDER, directories, read_json, write_new
from gridrescue.experiment import fit, load_development, probability
from gridrescue.modeling import (FEATURE_COLUMNS, chronological_folds, classification_metrics,
                                 make_model, validate_development)
from gridrescue.storage import sha256

VARIANTS = {'numeric': [], 'state': ['state'], 'fips': ['fips_code'], 'both': ['state', 'fips_code']}
PARAMETERS = {'n_estimators': 100, 'max_depth': 12, 'min_samples_leaf': 10}
METRICS = ['average_precision', 'accuracy', 'precision', 'recall', 'f1', 'roc_auc']
KEY = ['fips_code', 'timestamp', 'candidate_y']


def make_variant(variant):
    """Reuse the canonical numeric pipeline and optionally append independent category blocks."""
    model = make_model('Random Forest', PARAMETERS)
    if categories := VARIANTS[variant]:
        prep = model.named_steps['prepare']
        prep.set_params(transformers=[*prep.transformers,
                                      ('geography', OneHotEncoder(handle_unknown='ignore', sparse_output=False), categories)])
    return model


@contextmanager
def memory_measurement():
    """Sample the parent Python working set and system headroom during each fit."""
    stop = threading.Event()
    process = psutil.Process()
    trace = {'start_rss': process.memory_info().rss, 'peak_rss': 0,
             'min_available_ram': psutil.virtual_memory().available}

    def sample():
        while not stop.is_set():
            trace['peak_rss'] = max(trace['peak_rss'], process.memory_info().rss)
            trace['min_available_ram'] = min(trace['min_available_ram'], psutil.virtual_memory().available)
            stop.wait(0.25)

    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    try:
        yield trace
    finally:
        stop.set()
        thread.join()


def measure_resources(audit, seen):
    """Estimate dense-frame and fit workspace before collecting any modeling rows."""
    counts = [row for state in audit['state_audits'] for row in state['by_county_year_split']]
    train = sum(row['eligible'] for row in counts if row['split'] == 'train' and row['fips_code'] in seen)
    validation = sum(row['eligible'] for row in counts if row['split'] == 'validation')
    available = psutil.virtual_memory().available
    fixed = validation * 320 + 512 * 2**20
    estimated = fixed + 1000 * train
    allowable = max(0, (int(available * 0.65) - fixed) // 1000)
    # Keep 2021 untouched. Under genuine memory pressure, shorten only the training transfer.
    if not allowable:
        raise MemoryError('Available RAM is below the estimated workspace for full 2021 evaluation')
    return {'available_ram': available, 'full_estimated_workspace': estimated, 'train_before_sampling': train,
            'validation_rows': validation, 'training_fraction': min(1.0, allowable / train),
            'estimated_bytes_per_training_row': 1000, 'fixed_workspace_bytes': fixed}


def balanced_sample(frame, fraction):
    """Take a deterministic fraction within every county and UTC month, without using y."""
    if fraction >= 1.0:
        return frame
    keyed = frame.assign(sample_order=pd.util.hash_pandas_object(frame[['fips_code', 'timestamp']], index=False),
                         period=frame.timestamp.dt.strftime('%Y-%m'))
    keyed = keyed.sort_values(['sample_order', 'timestamp', 'fips_code'])
    groups = keyed.groupby(['fips_code', 'period'], sort=False)
    limit = np.floor(groups.timestamp.transform('size') * fraction).clip(lower=1)
    return keyed.loc[groups.cumcount() < limit].drop(columns=['sample_order', 'period'])


def load_split(artifacts, metadata, split, fraction=1.0):
    """Transfer narrow, eligible state partitions with Parquet row filtering."""
    parts = []
    for state, group in metadata.groupby('state'):
        path = artifacts / 'labels' / f's{STATE_ORDER[state]}' / f'split={split}'
        files = sorted(path.glob('part-*.parquet'))
        if not files:
            raise FileNotFoundError(path)
        state_frame = pd.read_parquet(files, columns=[*KEY, 'state', *FEATURE_COLUMNS, 'future_slots'],
                                      filters=[('fips_code', 'in', group.fips_code.tolist()), ('candidate_y', 'in', [0, 1])])
        state_frame['timestamp'] = pd.to_datetime(state_frame.timestamp, utc=True).astype('datetime64[ns, UTC]')
        state_frame = balanced_sample(state_frame, fraction)
        parts.append(state_frame)

    frame = pd.concat(parts, ignore_index=True).sort_values(['timestamp', 'fips_code']).reset_index(drop=True)
    validate_development(frame)
    if (frame.duplicated(['fips_code', 'timestamp']).any() or not frame.fips_code.str.fullmatch(r'[0-9]{5}').all()
            or not frame.future_slots.eq(12).all() or not frame.customers_out_t.gt(0).all()
            or set(frame.fips_code) != set(metadata.fips_code)):
        raise ValueError(f'Inconsistent {split} transfer')
    bound = pd.Timestamp('2021-01-01' if split == 'train' else '2022-01-01', tz='UTC')
    expected_year = frame.timestamp.dt.year.between(2018, 2020) if split == 'train' else frame.timestamp.dt.year.eq(2021)
    if not expected_year.all() or not (frame.timestamp + pd.Timedelta(hours=3) < bound).all():
        raise ValueError(f'Temporal boundary violation in {split}')
    expected_state = metadata.set_index('fips_code').state
    if not frame.state.eq(frame.fips_code.map(expected_state)).all():
        raise ValueError(f'State metadata differs in {split}')
    frame.drop(columns='future_slots', inplace=True)
    frame['candidate_y'] = frame.candidate_y.astype(int)
    for feature in FEATURE_COLUMNS:
        frame[feature] = frame[feature].astype(float)
    if np.isinf(frame[FEATURE_COLUMNS].to_numpy()).any():
        raise ValueError('Infinite numeric predictor')
    return frame


def observations(frame):
    """Normalize key dtypes before asserting exact compatibility with the historical rows."""
    return frame[KEY].assign(timestamp=pd.to_datetime(frame.timestamp, utc=True).astype('datetime64[ns, UTC]'),
                             candidate_y=frame.candidate_y.astype(int)).reset_index(drop=True)


def reference_predictions(validation, original_codes, training=None):
    """Verify original county rows and load both existing three-county benchmarks read-only."""
    reports = ROOT / 'reports/modeling'
    baseline = read_json(reports / 'random_forest_cv_selected.json')
    baseline_path = ROOT / baseline['predictions']
    if sha256(baseline_path) != baseline['predictions_sha256']:
        raise ValueError('Historical baseline predictions were modified')
    original = validation[validation.fips_code.isin(original_codes)]
    raw = pd.read_parquet(baseline_path)
    geographic = pd.read_parquet(reports / 'geography_experiment/run_20261121T170253377051Z/predictions_2021.parquet')
    if not (observations(original).equals(observations(raw)) and observations(original).equals(observations(geographic))):
        raise ValueError('Expanded original validation observations or labels differ from the historical benchmark')
    prior_cohort = load_development(ROOT)
    np.testing.assert_allclose(original[FEATURE_COLUMNS].to_numpy(),
                               prior_cohort[prior_cohort.split.eq('validation')][FEATURE_COLUMNS].to_numpy(),
                               rtol=1e-12, atol=1e-8, equal_nan=True)
    if training is not None:
        same = training[training.fips_code.isin(original_codes)]
        earlier = prior_cohort[prior_cohort.split.eq('train')]
        if not observations(same).equals(observations(earlier)):
            raise ValueError('Original training observations differ in a full-cohort comparison')
        np.testing.assert_allclose(same[FEATURE_COLUMNS].to_numpy(), earlier[FEATURE_COLUMNS].to_numpy(),
                                   rtol=1e-12, atol=1e-8, equal_nan=True)
    return original, {'three_county_numeric': raw.probability.to_numpy(),
                      'three_county_state': geographic.state_score.to_numpy(),
                      'three_county_fips': geographic.fips_score.to_numpy()}


def fit_forest(variant, train):
    """Fit one fresh pipeline and retain timings, complexity and resources."""
    columns = [*FEATURE_COLUMNS, *VARIANTS[variant]]
    model = make_variant(variant)
    with memory_measurement() as memory:
        seconds, warnings = fit(model, train[columns], train.candidate_y)
    forest = model.named_steps['classifier']
    tree_stats = {'trees': len(forest.estimators_), 'max_depth': max(t.tree_.max_depth for t in forest.estimators_),
                  'mean_depth': float(np.mean([t.tree_.max_depth for t in forest.estimators_])),
                  'total_nodes': sum(t.tree_.node_count for t in forest.estimators_),
                  'total_leaves': sum(t.get_n_leaves() for t in forest.estimators_),
                  'encoded_feature_count': forest.n_features_in_, 'candidate_features_per_split': forest.estimators_[0].max_features_}
    return model, {'train_rows': len(train), 'training_seconds': seconds, 'warnings': warnings, 'memory': memory,
                   'complexity': tree_stats, 'train_metrics': classification_metrics(train.candidate_y, probability(model, train[columns]))}


def score_groups(period, variant, model, evaluation, groups):
    """Score once and reuse aligned probabilities for cohort and county comparisons."""
    categories = VARIANTS[variant]
    scores = probability(model, evaluation[[*FEATURE_COLUMNS, *categories]])
    unknown = {}
    if categories:
        learned = model.named_steps['prepare'].named_transformers_['geography'].categories_
        unknown = {name: ~evaluation[name].isin(values).to_numpy() for name, values in zip(categories, learned)}
    results = []
    for group, mask in groups.items():
        result = classification_metrics(evaluation.candidate_y.to_numpy()[mask], scores[mask])
        results.append({'period': period, 'variant': variant, 'group': group, **result,
                        'unknown_states': int(unknown['state'][mask].sum()) if 'state' in unknown else None,
                        'unknown_fips': int(unknown['fips_code'][mask].sum()) if 'fips_code' in unknown else None})
    return scores, results


def masks(frame, metadata):
    """Construct spatial summaries without changing a row, label, or prediction."""
    roles = frame.fips_code.map(metadata.set_index('fips_code').role)
    original = frame.fips_code.isin(metadata[metadata.original].fips_code)
    groups = {'all': np.ones(len(frame), dtype=bool), 'original': original.to_numpy(),
              'seen': roles.eq('seen').to_numpy(), 'other_seen': (roles.eq('seen') & ~original).to_numpy(),
              'unseen_county': roles.eq('unseen_county').to_numpy(), 'unseen_state': roles.eq('unseen_state').to_numpy()}
    groups.update({f'county_{code}': frame.fips_code.eq(code).to_numpy() for code in sorted(frame.fips_code.unique())})
    return {name: mask for name, mask in groups.items() if mask.any()}


def metric_table(records):
    """Calculate absolute and relative differences within each identical evaluation population."""
    frame = pd.DataFrame(records)
    baseline = frame[frame.variant == 'numeric'].set_index(['period', 'group'])
    loc = pd.MultiIndex.from_frame(frame[['period', 'group']])
    for metric in METRICS:
        reference = baseline.loc[loc, metric].to_numpy()
        frame[f'delta_{metric}'] = frame[metric] - reference
        frame[f'relative_{metric}'] = frame[f'delta_{metric}'] / np.where(reference == 0, np.nan, reference)
    return frame


def run(reports, artifacts):
    """Keep spatial holdouts out of preprocessing, training and CV selection."""
    models = artifacts / 'models'
    models.mkdir()
    output = reports / 'model_results'
    output.mkdir()
    cohort = read_json(reports / 'cohort.json')
    audit = read_json(reports / 'data_audit.json')
    if audit['status'] != 'VERIFIED' or audit['inputs'] != cohort['inputs']:
        raise ValueError('Frozen coverage and data audit differ')
    metadata = pd.DataFrame(cohort['county_selection'])
    seen = metadata[metadata.role.eq('seen')]
    plan = measure_resources(audit, set(seen.fips_code))
    write_new(output / 'resource_plan.json', plan)
    print('Resource plan:', plan, flush=True)
    train = load_split(artifacts, seen, 'train', plan['training_fraction'])
    if plan['training_fraction'] == 1 and len(train) != plan['train_before_sampling']:
        raise ValueError('Training transfer is missing audited eligible rows')
    frozen = read_json(ROOT / 'reports/modeling/random_forest_cv_selected.json')
    if make_variant('numeric').named_steps['classifier'].get_params() != frozen['classifier_parameters']:
        raise ValueError('Forest settings differ from the existing approved configuration')
    files_to_protect = [*sorted((ROOT / 'notebooks').glob('*.ipynb')), ROOT / frozen['artifact'],
                        ROOT / frozen['predictions'], ROOT / 'artifacts/modeling/frozen_development_pipeline.joblib',
                        ROOT / 'reports/modeling/frozen_selection.json', ROOT / 'reports/modeling/frozen_pipeline.json']
    before = {path.relative_to(ROOT).as_posix(): sha256(path) for path in files_to_protect}
    write_new(output / 'configuration.json', {'variants': VARIANTS, 'features': FEATURE_COLUMNS,
              'forest': frozen['classifier_parameters'], 'threshold': 0.5, 'tie_class': 0,
              'temporal_purge_hours': 3, 'primary_metric': 'average_precision', 'seen_training_counties': sorted(seen.fips_code),
              'cohort_sha256': sha256(reports / 'cohort.json'), 'audit_sha256': sha256(reports / 'data_audit.json'),
              'protected_hashes': before, 'train_frame_bytes': int(train.memory_usage(deep=True).sum())})

    folds = chronological_folds(train)
    records, fits = [], []
    for fold in folds:
        name = fold['name']
        earlier, evaluation = train.iloc[fold['train']], train.iloc[fold['validation']]
        scores = evaluation[KEY].copy()
        period_records = []
        for variant in VARIANTS:
            print(f'{name} {variant}: {len(earlier):,} training rows', flush=True)
            model, info = fit_forest(variant, earlier)
            predicted, metrics = score_groups(name, variant, model, evaluation, masks(evaluation, seen))
            scores[variant] = predicted
            period_records.extend(metrics)
            detail = {'period': name, 'variant': variant, 'validation_start': fold['validation_start'],
                      'validation_end_exclusive': fold['validation_end'], 'last_train_utc': earlier.timestamp.max().isoformat(), **info}
            fits.append(detail)
            del model
        scores.to_parquet(output / f'predictions_{name}.parquet', index=False)
        records.extend(period_records)
        write_new(output / f'evidence_{name}.json', {'metrics': period_records, 'fits': [f for f in fits if f['period'] == name]})

    cv_table = metric_table(records)
    cv_means = cv_table[cv_table.group.eq('all')].groupby('variant').average_precision.mean().to_dict()
    winner = max(VARIANTS, key=cv_means.__getitem__)
    write_new(output / 'cv_selection.json', {'selected_for_development_comparison': winner, 'cv_mean_ap': cv_means,
              'spatial_holdouts_and_2021_used_for_selection': False, 'replaces_frozen_model': False})
    validation = load_split(artifacts, metadata, 'validation')
    if len(validation) != plan['validation_rows']:
        raise ValueError('2021 transfer is missing audited eligible rows')
    complete_training = plan['training_fraction'] == 1.0
    original, prior = reference_predictions(validation, metadata[metadata.original].fips_code,
                                            train if complete_training else None)
    references = {name: classification_metrics(original.candidate_y, scores) for name, scores in prior.items()}
    write_new(output / 'historical_comparison.json', {'all_original_rows_identical': True,
              'original_features_match': True, 'original_training_rows_identical': True if complete_training else None,
              'n_rows': len(original), 'benchmarks': references})
    groups = masks(validation, metadata)
    scores = validation[[*KEY, 'state']].copy()
    scores['role'] = scores.fips_code.map(metadata.set_index('fips_code').role)
    for variant in VARIANTS:
        print(f'2021 {variant}: {len(train):,} training rows, {len(validation):,} evaluation rows', flush=True)
        model, info = fit_forest(variant, train)
        scores[variant], metrics = score_groups('2021', variant, model, validation, groups)
        path = models / f'{variant}.joblib'
        joblib.dump(model, path, compress=3)
        check = joblib.load(path)
        features = [*FEATURE_COLUMNS, *VARIANTS[variant]]
        sample = validation[features].iloc[::max(1, len(validation) // 100)].iloc[:100]
        np.testing.assert_allclose(probability(model, sample), probability(check, sample), rtol=0, atol=1e-14)
        detail = {'period': '2021', 'variant': variant, **info, 'last_train_utc': train.timestamp.max().isoformat(),
                  'model_bytes': path.stat().st_size, 'model_sha256': sha256(path), 'reload_fixture_rows': len(sample)}
        fits.append(detail)
        records.extend(metrics)
        write_new(output / f'evidence_2021_{variant}.json', {'metrics': metrics, 'fit': detail})
        del model, check
    scores.to_parquet(output / 'predictions_2021.parquet', index=False)
    table = metric_table(records)
    table.to_csv(output / 'metrics.csv', index=False)
    cv_table.groupby(['variant', 'group'])[[*METRICS, *[f'delta_{name}' for name in METRICS]]].agg(['mean', 'std']).to_csv(output / 'cv_summary.csv')
    if before != {path.relative_to(ROOT).as_posix(): sha256(path) for path in files_to_protect}:
        raise ValueError('Canonical artifacts changed during the expansion')
    write_new(output / 'execution.json', {'status': 'VERIFIED', 'fits': fits, 'production_artifacts_unchanged': True,
              'actual_train_rows': len(train), 'validation_rows': len(validation),
              'validation_frame_bytes': int(validation.memory_usage(deep=True).sum()), 'holdout_accessed': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_id')
    args = parser.parse_args()
    started = time.perf_counter()
    run(*directories(args.run_id))
    print(f'Model workflow finished in {time.perf_counter() - started:.1f}s', flush=True)
