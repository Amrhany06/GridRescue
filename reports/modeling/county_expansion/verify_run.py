"""Check the experiment's saved scores and reload each expanded forest without fitting."""
import argparse
import ast
import math

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, average_precision_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)

from train_cohort import FEATURE_COLUMNS, KEY, METRICS, ROOT, VARIANTS, load_split
from prepare_cohort import directories, read_json, write_new
from gridrescue.experiment import probability
from gridrescue.storage import sha256


def verify_metrics(predictions, metric_rows, expected_roles):
    """Recalculate each stored metric and confusion matrix from persisted probabilities."""
    roles = predictions.fips_code.map(expected_roles.role)
    original = predictions.fips_code.map(expected_roles.original)
    for row in metric_rows.itertuples():
        if row.group == 'original':
            block = predictions[original]
        elif row.group == 'other_seen':
            block = predictions[roles.eq('seen') & ~original]
        elif row.group.startswith('county_'):
            block = predictions[predictions.fips_code.eq(row.group.removeprefix('county_'))]
        elif row.group != 'all':
            block = predictions[roles.eq(row.group)]
        else:
            block = predictions
        target, scores = block.candidate_y, block[row.variant]
        classes = scores.gt(.5)
        assert row.rows == len(block) and row.positive == target.sum()
        assert confusion_matrix(target, classes, labels=[0, 1]).tolist() == ast.literal_eval(row.confusion_matrix)
        metrics = dict(accuracy=accuracy_score(target, classes), precision=precision_score(target, classes, zero_division=0),
                       recall=recall_score(target, classes, zero_division=0), f1=f1_score(target, classes), prevalence=target.mean())
        if target.nunique() == 2:
            metrics.update(average_precision=average_precision_score(target, scores), roc_auc=roc_auc_score(target, scores))
        for key, measured in metrics.items():
            assert math.isclose(getattr(row, key), measured, rel_tol=0, abs_tol=1e-14), (row.period, row.variant, row.group, key)


def main(run_id):
    reports, artifacts = directories(run_id)
    output = reports / 'model_results'
    manifest = read_json(reports / 'cohort.json')
    metadata = pd.DataFrame(manifest['county_selection'])
    expected_roles = metadata.set_index('fips_code')
    execution = read_json(output / 'execution.json')
    settings = read_json(output / 'configuration.json')
    assert execution['status'] == 'VERIFIED' and not execution['holdout_accessed']
    assert settings['cohort_sha256'] == sha256(reports / 'cohort.json')
    assert settings['audit_sha256'] == sha256(reports / 'data_audit.json')
    for path, expected in settings['protected_hashes'].items():
        assert sha256(ROOT / path) == expected, path
    for path in ('reports/modeling/final_evaluation_journal.json', 'reports/modeling/final_evaluation.json', 'data/final_test'):
        assert not (ROOT / path).exists()

    metrics = pd.read_csv(output / 'metrics.csv', dtype={'period': str}, float_precision='round_trip')
    assert not metrics.duplicated(['period', 'variant', 'group']).any()
    reference = metrics.loc[metrics.variant.eq('numeric')].set_index(['period', 'group'])
    keys = pd.MultiIndex.from_frame(metrics[['period', 'group']])
    for metric in METRICS:
        baseline = reference.loc[keys, metric].to_numpy()
        absolute = metrics[metric].to_numpy() - baseline
        relative = absolute / np.where(baseline == 0, np.nan, baseline)
        np.testing.assert_allclose(metrics[f'delta_{metric}'], absolute, rtol=0, atol=1e-14)
        np.testing.assert_allclose(metrics[f'relative_{metric}'], relative, rtol=1e-12, atol=1e-14)
    for period, rows in metrics.groupby('period'):
        predictions = pd.read_parquet(output / f'predictions_{period}.parquet')
        assert not predictions.duplicated(['fips_code', 'timestamp']).any()
        assert predictions.timestamp.dt.year.eq(int(period[:4])).all()
        if period != '2021':
            assert set(predictions.fips_code) == set(settings['seen_training_counties'])
            for fit in execution['fits']:
                if fit['period'] == period:
                    bound = pd.Timestamp(fit['validation_start'])
                    assert pd.Timestamp(fit['last_train_utc']) + pd.Timedelta(hours=3) < bound
        verify_metrics(predictions, rows, expected_roles)

    validation = load_split(artifacts, metadata, 'validation')
    final_scores = pd.read_parquet(output / 'predictions_2021.parquet')
    assert validation[KEY].equals(final_scores[KEY])
    selection = read_json(output / 'cv_selection.json')
    by_cv_ap = metrics[metrics.period.ne('2021') & metrics.group.eq('all')].groupby('variant').average_precision.mean()
    assert selection['selected_for_development_comparison'] == by_cv_ap.idxmax()
    for fit in execution['fits']:
        if fit['period'] != '2021':
            continue
        variant = fit['variant']
        path = artifacts / 'models' / f'{variant}.joblib'
        assert sha256(path) == fit['model_sha256']
        model = joblib.load(path)
        assert model.named_steps['classifier'].get_params() == settings['forest']
        if categories := VARIANTS[variant]:
            fitted_categories = model.named_steps['prepare'].named_transformers_['geography'].categories_
            seen = metadata[metadata.role.eq('seen')]
            for name, values in zip(categories, fitted_categories):
                assert set(values) == set(seen[name]), (variant, name)
        columns = [*FEATURE_COLUMNS, *VARIANTS[variant]]
        indices = np.linspace(0, len(validation) - 1, 100, dtype=int)
        np.testing.assert_allclose(probability(model, validation[columns].iloc[indices]),
                                   final_scores[variant].iloc[indices], rtol=0, atol=1e-14)
    write_new(output / 'independent_verification.json', {'status': 'VERIFIED', 'metric_rows_recomputed': len(metrics),
              'pipelines_reloaded_in_fresh_process': 4, 'saved_score_rows_per_pipeline': 100,
              'protected_canonical_hashes_match': True, 'holdout_accessed': False})
    print(f'Verified {len(metrics)} metric rows and four persisted pipelines from saved scores.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_id')
    main(parser.parse_args().run_id)
