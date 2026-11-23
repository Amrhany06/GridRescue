"""Compare fixed Random Forests with a bounded CPU XGBoost search."""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import shutil
import sys
import time

import joblib
import numpy as np
import pandas as pd
import psutil
from sklearn.compose import ColumnTransformer

from history import ADDED
from thresholds import (ARTIFACTS, BASE_DATA, BASE_REPORT, FOLDS, HERE, KEY, PRIOR, ROOT,
                        metadata, metrics, prior_scores, score_groups, select_thresholds,
                        threshold_curve, write_json)

sys.path.insert(0, str(PRIOR))
from train_cohort import make_variant, masks, memory_measurement, observations
from gridrescue.experiment import fit, probability
from gridrescue.modeling import FEATURE_COLUMNS, chronological_folds
from gridrescue.storage import sha256

BASELINE = {'rf_original_state': 'state', 'rf_original_both': 'both'}
PRIMARY = ('rf_original_state', 'rf_history_state', 'xgb_original_state', 'xgb_history_state')
SPEC = {'rf_history_state': ('rf', 'state', True), 'rf_history_both': ('rf', 'both', True),
        'xgb_original_state': ('xgb', 'state', False), 'xgb_history_state': ('xgb', 'state', True)}
XGB_SETTINGS = dict(tree_method='hist', device='cpu', n_jobs=2, random_state=17, n_estimators=120,
                    learning_rate=0.1, max_bin=128, min_child_weight=10, subsample=0.85,
                    reg_lambda=1.0, objective='binary:logistic', eval_metric='logloss')


def model_for(name, depth):
    """Start with the same numeric and geographic preprocessing for both classifiers."""
    algorithm, geography, history = SPEC[name]
    model = make_variant(geography)
    if history:
        prepare = model.named_steps['prepare']
        (_, numeric, _), geography_block = prepare.transformers
        model.set_params(prepare=ColumnTransformer(
            [('numeric', numeric, FEATURE_COLUMNS + ADDED), geography_block], remainder='drop'))
    if algorithm == 'xgb':
        sys.path.insert(0, str(ARTIFACTS / 'deps_local'))
        from xgboost import XGBClassifier
        model.set_params(classifier=XGBClassifier(**XGB_SETTINGS, max_depth=depth))
    return model


def read_split(path, split, cohort):
    """Read bounded state partitions and keep predictor statistics out of loading."""
    parts = []
    for bucket, counties in cohort.groupby(cohort.fips_code.str[:2]):
        state_part = path / f's{bucket}' / f'split={split}'
        files = sorted(state_part.glob('part-*.parquet'))
        if not files:
            if split == 'train' and not counties.role.eq('seen').any():
                continue
            raise FileNotFoundError(state_part)
        frame = pd.read_parquet(files, columns=[*KEY, 'state', 'future_slots', *FEATURE_COLUMNS, *ADDED])
        frame['timestamp'] = pd.to_datetime(frame.timestamp, utc=True).astype('datetime64[ns, UTC]')
        frame['candidate_y'] = frame.candidate_y.astype('int8')
        if not frame.future_slots.eq(12).all() or not frame.customers_out_t.gt(0).all():
            raise ValueError('Input contains ineligible anchors')
        frame.drop(columns='future_slots', inplace=True)
        # Scikit-learn imputes nulls. Integer flags stay compact until prepare.transform().
        for name in FEATURE_COLUMNS:
            frame[name] = frame[name].astype(float)
        if np.isinf(frame[FEATURE_COLUMNS + ADDED].to_numpy()).any():
            raise ValueError('Infinite predictor')
        parts.append(frame)
    combined = pd.concat(parts, ignore_index=True)
    # Pandas sorts categoricals by category order. Match the archived lexical FIPS order.
    combined['fips_code'] = pd.Categorical(combined.fips_code, categories=sorted(cohort.fips_code))
    combined['state'] = pd.Categorical(combined.state, categories=sorted(cohort.state.unique()))
    combined.sort_values(['timestamp', 'fips_code'], inplace=True, ignore_index=True)
    expected_cohort = cohort if split == 'validation' else cohort[cohort.role.eq('seen')]
    last = pd.Timestamp('2021-01-01' if split == 'train' else '2022-01-01', tz='UTC')
    if (set(combined.fips_code) != set(expected_cohort.fips_code)
            or not combined.fips_code.str.fullmatch('[0-9]{5}').all()
            or not combined.state.astype(str).eq(combined.fips_code.map(cohort.set_index('fips_code').state).astype(str)).all()
            or not combined.timestamp.dt.year.between(2021 if split == 'validation' else 2018, last.year - 1).all()
            or not (combined.timestamp + pd.Timedelta(hours=3)).lt(last).all()
            or combined.duplicated(KEY[:2]).any()):
        raise ValueError(f'Geographic/time contract failed for {split}')
    return combined


def aligned(left, right):
    """Check keys, order and labels exactly, normalizing Arrow or category dtypes."""
    for frame in (left, right):
        if frame.duplicated(KEY[:2]).any():
            raise ValueError('Duplicate observation in alignment')
    a, b = (observations(frame.assign(fips_code=frame.fips_code.astype(str))) for frame in (left, right))
    pd.testing.assert_frame_equal(a, b)


def fit_timed(name, depth, train):
    """Fit fold-local preprocessing and classifier and capture runtime and peak RSS."""
    model = model_for(name, depth)
    start = time.perf_counter()
    with memory_measurement() as memory:
        fit(model, train, train.candidate_y)
    # Forest trees add their scores in parallel by default. Serial scoring keeps
    # the sum order, and therefore strict probability cutoffs, reproducible.
    if name.startswith('rf_'):
        model.set_params(classifier__n_jobs=1)
    classifier = model.named_steps['classifier']
    return model, dict(seconds=time.perf_counter() - start, **memory,
                       transformed_width=len(model.named_steps['prepare'].get_feature_names_out()),
                       trees=classifier.n_estimators)


def fold_resume_identity(name, depth, train, folds):
    """Bind cached fold scores to ordered input values, fit settings and implementation."""
    algorithm, _, history = SPEC[name]
    columns = [*KEY, *FEATURE_COLUMNS, *(ADDED if history else []), 'state']
    inputs = train[columns]
    row_hashes = pd.util.hash_pandas_object(inputs, index=False).to_numpy(dtype='<u8')
    packages = ('numpy', 'pandas', 'scikit-learn', 'scipy', 'joblib', 'pyarrow')
    versions = {package: version(package) for package in packages}
    model = model_for(name, depth)
    if algorithm == 'xgb':
        # The Windows pilot can use a project-local CPU wheel.
        import xgboost
        versions['xgboost'] = xgboost.__version__
    settings = model.named_steps['classifier'].get_params()
    recipe = {'variant': name, 'depth': depth, 'settings': settings,
              'python': platform.python_version(), 'platform': platform.platform(), 'packages': versions,
              'content': hashlib.sha256(row_hashes).hexdigest(),
              'schema': [(column, str(inputs[column].dtype)) for column in columns],
              'folds': {fold['name']: {part: hashlib.sha256(np.asarray(fold[part], dtype='<i8')).hexdigest()
                                      for part in ('train', 'validation')} for fold in folds},
              'code': {path.name: sha256(path) for path in (
                  Path(__file__), HERE / 'history.py', HERE / 'thresholds.py', PRIOR / 'train_cohort.py',
                  ROOT / 'src/gridrescue/modeling.py', ROOT / 'src/gridrescue/experiment.py')}}
    return hashlib.sha256(json.dumps(recipe, sort_keys=True).encode()).hexdigest()


def tune_one(name, train, folds, output):
    """Save each candidate's chronological scores, choosing using mean fold AP only."""
    candidates = [None] if name.startswith('rf_') else [4, 6]
    evidence = []
    for depth in candidates:
        identity = fold_resume_identity(name, depth, train, folds)
        suffix = f'{name}_depth{depth}' if depth is not None else name
        for fold in folds:
            label = fold['name']
            artifact = output / f'oof_{suffix}_{label}.parquet'
            details_path = output / f'fit_{suffix}_{label}.json'
            if artifact.exists() and details_path.exists():
                saved = json.loads(details_path.read_text(encoding='utf-8'))
                if saved.get('resume_identity') != identity or saved.get('oof_sha256') != sha256(artifact):
                    raise ValueError(f'Fold checkpoint provenance mismatch for {suffix}/{label}. Use a new run directory.')
                evidence.append(saved)
                continue
            if artifact.exists() or details_path.exists():
                raise FileExistsError(f'Incomplete experiment fold {suffix}/{label}')
            fit_rows = train.iloc[fold['train']]
            evaluation = train.iloc[fold['validation']]
            model, details = fit_timed(name, depth, fit_rows)
            scores = probability(model, evaluation)
            keys = evaluation[KEY].assign(score=scores)
            keys.to_parquet(artifact, index=False)
            row = dict(name=name, depth=depth, period=label, fit_rows=len(fit_rows),
                       evaluation_rows=len(evaluation), resume_identity=identity, oof_sha256=sha256(artifact),
                       **details, **metrics(evaluation.candidate_y, scores, 0.5))
            write_json(details_path, row)
            evidence.append(row)
            print(f'{suffix} {label}: AP {row["average_precision"]:.6f}, {details["seconds"]:.1f}s', flush=True)
    return evidence


def choose(candidates):
    """Return the candidate with greatest mean fold AP, preferring shallower ties."""
    return max(candidates, key=lambda rows: np.mean([row['average_precision'] for row in rows]))


def oof_selection(train, folds, specs, output):
    """Freeze model ranking and operating thresholds before loading 2021 scores."""
    initial = [prior_scores(period) for period in FOLDS]
    for fold, former in zip(folds, initial, strict=True):
        aligned(train.iloc[fold['validation']], former)
    selection = {}
    comparisons = []
    for name in (*BASELINE, *specs):
        if name in BASELINE:
            chosen = [dict(name=name, depth=None, period=label, **metrics(frame.candidate_y, frame[BASELINE[name]], 0.5))
                      for label, frame in zip(FOLDS, initial, strict=True)]
            predictions = [frame[KEY].assign(score=frame[BASELINE[name]]) for frame in initial]
        else:
            evidence = tune_one(name, train, folds, output)
            comparisons.extend(evidence)
            depths = list(dict.fromkeys(row['depth'] for row in evidence))
            chosen = choose([[row for row in evidence if row['depth'] == depth] for depth in depths])
            depth = chosen[0]['depth']
            suffix = f'{name}_depth{depth}' if depth is not None else name
            predictions = [pd.read_parquet(output / f'oof_{suffix}_{fold}.parquet') for fold in FOLDS]
            for frame, earlier in zip(predictions, initial, strict=True):
                aligned(frame, earlier)
        pooled = pd.concat(predictions, ignore_index=True)
        curve = threshold_curve(pooled.candidate_y, pooled.score)
        aps = [row['average_precision'] for row in chosen]
        selection[name] = dict(depth=chosen[0]['depth'], fold_ap=aps, mean_ap=float(np.mean(aps)),
                               sd_ap=float(np.std(aps, ddof=1)), rules=select_thresholds(curve))
    winner = max((name for name in PRIMARY if name in selection), key=lambda name: selection[name]['mean_ap'])
    result = dict(champion=winner, selection=selection, primary_metric='mean chronological fold AP',
                  operating_rule='Highest accuracy at or above 60% recall on pooled chronological OOF',
                  high_recall_rule='F2 on pooled chronological OOF', fold_search=comparisons)
    write_json(output / 'selection.json', result)
    return result


def permute_hour(model, validation, seeds=(17, 31, 47)):
    """Measure AP drops after shuffling one column at a time on the same diagnostic sample."""
    sample = validation.sample(n=min(20_000, len(validation)), random_state=17).copy()
    rank = metrics(sample.candidate_y, probability(model, sample), 0.5)['average_precision']
    numerics = model.named_steps['prepare'].transformers_[0][2]
    evidence = []
    for column in numerics:
        original = sample[column].copy()
        drops = []
        for seed in seeds:
            sample[column] = np.random.default_rng(seed).permutation(original)
            shuffled = metrics(sample.candidate_y, probability(model, sample), 0.5)['average_precision']
            drops.append(rank - shuffled)
        sample[column] = original
        evidence.append(dict(feature=column, mean_ap_drop=float(np.mean(drops)), drops=drops,
                             sample_rows=len(sample), unshuffled_ap=rank))
    return sorted(evidence, key=lambda row: -row['mean_ap_drop'])


def score_final(train, validation, cohort, config, output, model_dir):
    """Refit selected settings on the 12 seen counties and apply OOF thresholds unchanged."""
    archived = prior_scores('2021')
    aligned(validation, archived)
    evaluation = validation[KEY].copy()
    records = []
    full_fit = {}
    hour = {}
    roles = masks(validation, cohort)
    for name, evidence in config['selection'].items():
        if name in BASELINE:
            base = BASELINE[name]
            evaluation[name] = archived[base].to_numpy()
            pipeline = joblib.load(BASE_DATA / 'models' / f'{base}.joblib') if name == 'rf_original_state' else None
            prev = json.loads((BASE_REPORT / 'model_results' / f'evidence_2021_{base}.json').read_text(encoding='utf-8'))
            full_fit[name] = {'source': 'archived', 'original': prev}
        else:
            pipeline, fit_details = fit_timed(name, evidence['depth'], train)
            print(f'{name} final fit: {fit_details["seconds"]:.1f}s', flush=True)
            evaluation[name] = probability(pipeline, validation)
            destination = model_dir / f'{name}.joblib'
            with destination.open('xb') as stream:
                joblib.dump(pipeline, stream, compress=3)
            reload = joblib.load(destination)
            test = validation.iloc[::997]
            np.testing.assert_array_equal(probability(pipeline, test), probability(reload, test))
            del reload
            full_fit[name] = dict(**fit_details, sha256=sha256(destination), reload_rows=len(test),
                                  train=metrics(train.candidate_y, probability(pipeline, train), 0.5))
        records.extend(score_groups(evaluation, name, evidence['rules'], roles, '2021'))
        if pipeline is not None and name in {config['champion'], 'rf_original_state'}:
            hour[name] = permute_hour(pipeline, validation)
    evaluation.to_parquet(output / 'predictions_2021.parquet', index=False)
    pd.DataFrame(records).to_csv(output / 'metrics_2021.csv', index=False, mode='x')
    write_json(output / 'full_fits.json', full_fit)
    write_json(output / 'permutation_ap.json', hour)


def run(history, output, model_dir, rf_only=False):
    """Check resource headroom and run each phase with fixed cohorts and a bounded search."""
    memory = psutil.virtual_memory().available
    disk = shutil.disk_usage(ROOT).free
    if memory < 2.25 * 2**30 or disk < 2 * 2**30:
        raise MemoryError(f'Modeling needs 2.25 GiB available RAM and 2 GiB free disk; found {memory}, {disk} bytes')
    if not (history / 'audit.json').is_file():
        raise FileNotFoundError('History has no reconciled evidence')
    output.mkdir(exist_ok=True)
    model_dir.mkdir(exist_ok=True)
    if (output / 'selection.json').exists():
        raise FileExistsError('Choose a new output directory for an independent run')
    cohort = metadata()
    train = read_split(history, 'train', cohort)
    folds = chronological_folds(train)
    resources = dict(available_ram_at_start=memory, free_disk_at_start=disk, python=platform.python_version(),
                     train_rows=len(train), train_frame_bytes=int(train.memory_usage(deep=True).sum()),
                     xgb_settings=XGB_SETTINGS, validation_disclosure='Previously consulted 2021 and spatial development scores',
                     folds=[{key: value if key not in ('train', 'validation') else len(value)
                             for key, value in fold.items()} for fold in folds])
    if not (output / 'config.json').exists():
        write_json(output / 'config.json', resources)
    specs = [name for name in SPEC if not rf_only or name.startswith('rf_')]
    config = oof_selection(train, folds, specs, output)
    validation = read_split(history, 'validation', cohort)
    score_final(train, validation, cohort, config, output, model_dir)
    print(f'Development selection: {config["champion"]}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--history', type=type(ROOT), default=ARTIFACTS / 'history')
    parser.add_argument('--output', type=type(ROOT), default=HERE / 'model_results')
    parser.add_argument('--models', dest='model_dir', type=type(ROOT), default=ARTIFACTS / 'models')
    parser.add_argument('--rf-only', action='store_true')
    run(**vars(parser.parse_args()))
