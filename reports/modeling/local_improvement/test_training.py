"""Check fold-local preprocessing and how unseen geography is represented."""
import unittest
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from train_local import ADDED, FEATURE_COLUMNS, aligned, fold_resume_identity, model_for, tune_one


class TrainingTests(unittest.TestCase):
    def test_fold_resume_identity_binds_predictors_depth_and_membership(self):
        rows = pd.DataFrame({name: [3., 8.] for name in FEATURE_COLUMNS + ADDED})
        rows = rows.assign(fips_code='06037', timestamp=pd.date_range('2020-01-01', periods=2, tz='UTC'),
                           state='California', candidate_y=[0, 1])
        folds = [{'name': '2020', 'train': [0], 'validation': [1]}]
        variant = 'xgb_history_state'
        original = fold_resume_identity(variant, 4, rows, folds)
        self.assertNotEqual(original, fold_resume_identity(variant, 4, rows.assign(lag_15m=[3., 9.]), folds))
        self.assertNotEqual(original, fold_resume_identity(variant, 6, rows, folds))
        self.assertNotEqual(original, fold_resume_identity(variant, 4, rows, [
            {'name': '2020', 'train': [1], 'validation': [0]}]))

    def test_legacy_fold_without_bound_inputs_is_not_resumed(self):
        rows = pd.DataFrame({name: [3., 8.] for name in FEATURE_COLUMNS + ADDED})
        rows = rows.assign(fips_code='06037', timestamp=pd.date_range('2020-01-01', periods=2, tz='UTC'),
                           state='California', candidate_y=[0, 1])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / 'oof_xgb_history_state_depth4_2020.parquet').write_bytes(b'legacy')
            (path / 'fit_xgb_history_state_depth4_2020.json').write_text('{}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'checkpoint provenance'):
                tune_one('xgb_history_state', rows, [{'name': '2020', 'train': [0], 'validation': [1]}], path)

    def test_augmented_geography_and_numeric_statistics_fit_on_training(self):
        model = model_for('rf_history_both', None)
        prepare = model.named_steps['prepare']
        rows = pd.DataFrame({name: [3.0, 8.0, np.nan] for name in FEATURE_COLUMNS + ADDED})
        rows['state'] = ['California', 'California', 'Florida']
        rows['fips_code'] = ['06037', '06037', '12086']
        prepare.fit(rows.iloc[:2])
        numeric = prepare.named_transformers_['numeric']
        self.assertEqual(numeric.named_steps['imputer'].statistics_[0], 5.5)
        result = prepare.transform(rows)
        self.assertTrue(np.isfinite(result).all())
        np.testing.assert_array_equal(result[-1, -2:], [0, 0])
        self.assertEqual(prepare.named_transformers_['geography'].categories_[1].tolist(), ['06037'])

    def test_alignment_rejects_label_change(self):
        frame = pd.DataFrame({'fips_code': ['06037'], 'timestamp': ['2020-03-01'], 'candidate_y': [1]})
        with self.assertRaises(AssertionError):
            aligned(frame, frame.assign(candidate_y=0))

    def test_cpu_histogram_xgboost_accepts_unseen_state(self):
        rows = pd.DataFrame({name: np.arange(100, dtype=float) for name in FEATURE_COLUMNS})
        rows['state'] = ['California'] * 100
        model = model_for('xgb_original_state', 4)
        model.fit(rows, np.arange(len(rows)) % 2)
        classifier = model.named_steps['classifier']
        self.assertEqual(classifier.get_params()['tree_method'], 'hist')
        self.assertEqual(classifier.get_params()['device'], 'cpu')
        predicted = model.predict_proba(rows.iloc[:2].assign(state='New York'))
        np.testing.assert_allclose(predicted.sum(axis=1), [1, 1], atol=1e-6)
