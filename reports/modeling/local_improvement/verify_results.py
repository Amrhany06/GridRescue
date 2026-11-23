"""Independently check run evidence and reload saved candidates in a fresh process."""
import json
import platform
import shutil
import sys

import joblib
import numpy as np
import pandas as pd
import psutil
import sklearn

from train_local import BASELINE, PRIMARY, SPEC, aligned, probability, read_split, sha256
from thresholds import (ARTIFACTS, BASE_DATA, BASE_REPORT, FOLDS, HERE, ROOT, metadata,
                        metrics, prior_scores, select_thresholds, threshold_curve, write_json)


def load_json(path):
    """Read measured records from the completed run."""
    return json.loads(path.read_text(encoding='utf-8'))


def run():
    """Verify row identity, metrics, persistence and protected artifacts independently."""
    sys.path.insert(0, str(ARTIFACTS / 'deps_local'))
    import xgboost

    output = HERE / 'model_results'
    config = load_json(output / 'selection.json')
    fits = load_json(output / 'full_fits.json')
    original = load_json(BASE_REPORT / 'model_results' / 'configuration.json')
    for name, expected in original['protected_hashes'].items():
        if sha256(ROOT / name) != expected:
            raise ValueError(f'Protected notebook or model changed: {name}')
    for variant in ('numeric', 'state', 'fips', 'both'):
        original_variant = load_json(BASE_REPORT / 'model_results' / f'evidence_2021_{variant}.json')
        if sha256(BASE_DATA / 'models' / f'{variant}.joblib') != original_variant['fit']['model_sha256']:
            raise ValueError(f'Expansion model changed: {variant}')

    # Confirm every candidate, including the unselected depth, used identical OOF anchors.
    for row in config['fold_search']:
        name, depth, period = row['name'], row['depth'], row['period']
        suffix = f'{name}_depth{depth}' if depth is not None else name
        scores = pd.read_parquet(output / f'oof_{suffix}_{period}.parquet')
        aligned(scores, prior_scores(period))
        measured = metrics(scores.candidate_y, scores.score, 0.5)
        np.testing.assert_allclose(measured['average_precision'], row['average_precision'], rtol=0, atol=1e-12)
    expected_winner = max(PRIMARY, key=lambda name: config['selection'][name]['mean_ap'])
    assert expected_winner == config['champion']
    assert all(len(config['selection'][name]['fold_ap']) == len(FOLDS) for name in (*BASELINE, *SPEC))
    winner = config['selection'][expected_winner]
    if expected_winner in BASELINE:
        columns = [prior_scores(period).rename(columns={BASELINE[expected_winner]: 'score'}) for period in FOLDS]
    else:
        depth = winner['depth']
        suffix = f'{expected_winner}_depth{depth}' if depth is not None else expected_winner
        columns = [pd.read_parquet(output / f'oof_{suffix}_{period}.parquet') for period in FOLDS]
    pooled = pd.concat(columns, ignore_index=True)
    assert select_thresholds(threshold_curve(pooled.candidate_y, pooled.score)) == winner['rules']

    cohort = metadata()
    archived = prior_scores('2021')
    stored = pd.read_parquet(output / 'predictions_2021.parquet')
    aligned(stored, archived)
    validation = read_split(ARTIFACTS / 'history', 'validation', cohort)
    aligned(validation, stored)
    fixed = pd.read_csv(output / 'metrics_2021.csv').query("period == 2021 and group == 'all'")
    assert len(fixed) == sum(len(entry['rules']) for entry in config['selection'].values())
    for row in fixed.itertuples():
        expected_cutoff = config['selection'][row.variant]['rules'][row.rule]
        actual = metrics(stored.candidate_y, stored[row.variant], expected_cutoff)
        for count in ('tn', 'fp', 'fn', 'tp'):
            assert actual[count] == getattr(row, count)
        for metric in ('average_precision', 'accuracy', 'recall', 'precision', 'f1', 'f2', 'balanced_accuracy',
                       'false_alarms_per_1000', 'roc_auc'):
            np.testing.assert_allclose(actual[metric], getattr(row, metric), rtol=0, atol=1e-10)

    fixture = validation.iloc[::997]
    complexity = {}
    for name in SPEC:
        path = ARTIFACTS / 'models' / f'{name}.joblib'
        if sha256(path) != fits[name]['sha256']:
            raise ValueError(f'Saved pipeline hash differs: {name}')
        model = joblib.load(path)
        np.testing.assert_array_equal(probability(model, fixture), stored[name].iloc[::997].to_numpy())
        estimator = model.named_steps['classifier']
        if name.startswith('rf_'):
            nodes = sum(tree.tree_.node_count for tree in estimator.estimators_)
            leaves = sum(tree.tree_.n_leaves for tree in estimator.estimators_)
        else:
            def size(tree):
                children = tree.get('children', [])
                counts = [size(child) for child in children]
                return (1 + sum(count[0] for count in counts), sum(count[1] for count in counts) if children else 1)
            sizes = [size(json.loads(tree)) for tree in estimator.get_booster().get_dump(dump_format='json')]
            nodes, leaves = (sum(count[i] for count in sizes) for i in (0, 1))
        complexity[name] = dict(nodes=int(nodes), leaves=int(leaves), trees=estimator.n_estimators,
                                depth_limit=estimator.max_depth, file_bytes=path.stat().st_size)
    write_json(output / 'verification.json', dict(
        status='PASS', observations_2021=len(stored), reloaded_rows_per_model=len(fixture),
        checked_oof_candidate_folds=len(config['fold_search']), verified_metric_rows=len(fixed),
        protected_official_artifacts=len(original['protected_hashes']), protected_prior_forests=4,
        python=platform.python_version(), scikit_learn=sklearn.__version__, xgboost=xgboost.__version__,
        available_ram_after=psutil.virtual_memory().available, disk_free_after=shutil.disk_usage(ROOT).free,
        complexity=complexity))
    print(f'Verified {len(stored):,} identical evaluation keys, {len(fixed)} metric rows and {len(fixture)} reload rows per model.')


if __name__ == '__main__':
    run()
