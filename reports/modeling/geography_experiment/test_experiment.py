"""Focused regression tests for the isolated geographic comparison."""
import unittest

import numpy as np
import pandas as pd

from run_experiment import FEATURE_COLUMNS, add_state, make_variant


class GeographyExperimentTests(unittest.TestCase):
    def setUp(self):
        self.train = pd.DataFrame({name: [0.0, 1.0, 2.0, 3.0] for name in FEATURE_COLUMNS})
        self.train['state'] = ['California', 'California', 'Florida', 'Florida']
        self.train['fips_code'] = ['06037', '06037', '12086', '12086']
        self.future = self.train.iloc[[0]].assign(state='Texas', fips_code='48201')

    def test_each_variant_maps_unseen_geography_to_an_all_zero_block(self):
        for category in ('state', 'fips_code'):
            with self.subTest(category=category):
                model = make_variant(category).fit(self.train, [0, 0, 1, 1])
                transformer = model.named_steps['prepare']
                encoder = transformer.named_transformers_['geography']
                expected = ['California', 'Florida'] if category == 'state' else ['06037', '12086']
                self.assertEqual(encoder.categories_[0].tolist(), expected)
                np.testing.assert_array_equal(transformer.transform(self.future)[0, -2:], [0, 0])
                self.assertTrue(np.isfinite(model.predict_proba(self.future)).all())

    def test_baseline_keeps_exact_numeric_inputs_and_classifier_settings(self):
        model = make_variant(None).fit(self.train, [0, 0, 1, 1])
        self.assertEqual(model.named_steps['prepare'].transform(self.future).shape, (1, 13))
        settings = model.named_steps['classifier'].get_params()
        self.assertEqual([settings[k] for k in ('n_estimators', 'max_depth', 'min_samples_leaf', 'random_state')],
                         [100, 12, 10, 17])

    def test_metadata_mapping_keeps_order_and_rejects_conflicting_state(self):
        rows = pd.DataFrame({'fips_code': ['12086', '06037', '12086']})
        metadata = pd.DataFrame({'fips_code': ['06037', '12086', '12086'],
                                 'state': ['California', 'Florida', 'Florida']})
        result = add_state(rows, metadata)
        self.assertEqual(result.state.tolist(), ['Florida', 'California', 'Florida'])
        self.assertEqual(result.fips_code.tolist(), ['12086', '06037', '12086'])
        metadata.loc[2, 'state'] = 'Texas'
        with self.assertRaisesRegex(ValueError, 'one state'):
            add_state(rows, metadata)

    def test_metadata_rejects_unpadded_numeric_county(self):
        invalid = pd.DataFrame({'fips_code': [6037], 'state': ['California']})
        with self.assertRaisesRegex(ValueError, 'five-character'):
            add_state(self.train, invalid)
