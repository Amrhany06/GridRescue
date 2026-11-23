import unittest

import joblib
import numpy as np
import pandas as pd

from diagnostic import (CHAMPION, check_alignment, check_reloaded_scores, hourly_summary, make_ablation,
                        operating_point, select_targets, validate_period)
from train_local import model_for, threshold_curve


class DiagnosticTests(unittest.TestCase):
    def test_strict_cutoff_keeps_score_ties_together(self):
        labels = [1, 0, 1, 0, 1, 0, 1]
        scores = [.9, .8, .8, .8, .6, .5, .2]
        points = select_targets(threshold_curve(labels, scores))
        self.assertEqual(points[40], np.nextafter(.8, -np.inf))
        self.assertEqual(points[50], points[40])
        result = operating_point(labels, scores, points[60])
        self.assertEqual((result['tp'], result['fp']), (3, 2))
        self.assertEqual(result['recall'], .75)

    def test_false_positive_rate_uses_actual_negatives(self):
        result = operating_point([1, 1, 0, 0, 0], [.2, .7, .6, .4, .3], .5)
        self.assertAlmostEqual(result['false_positive_rate'], 1 / 3)
        self.assertEqual(result['false_alarms_per_1000'], 200)

    def test_only_original_forest_allows_parallel_roundoff(self):
        score = np.array([.42])
        near = np.nextafter(score, np.inf)
        check_reloaded_scores('rf_original_state', near, score)
        with self.assertRaises(AssertionError):
            check_reloaded_scores(CHAMPION, near, score)
        with self.assertRaises(AssertionError):
            check_reloaded_scores('rf_original_state', score + .0001, score)

    def test_alignment_rejects_changed_labels_reordering_and_duplicates(self):
        frame = pd.DataFrame(dict(fips_code=['06001', '06003'],
                                  timestamp=pd.to_datetime(['2021-01-01', '2021-02-01'], utc=True),
                                  candidate_y=[0, 1]))
        check_alignment(frame, frame.assign(fips_code=frame.fips_code.astype('category')))
        for bad in (frame.assign(candidate_y=[1, 0]), frame.iloc[::-1], frame.iloc[[0, 0]],
                    frame.assign(candidate_y=[.5, 1])):
            with self.subTest(bad=bad), self.assertRaises((AssertionError, ValueError)):
                check_alignment(frame, bad)

    def test_period_guard_enforces_horizon_purge_and_allowed_period(self):
        timestamp = pd.Series(pd.to_datetime(['2020-12-31T20:45Z'], utc=True))
        validate_period(timestamp, '2020')
        with self.assertRaises(ValueError):
            validate_period(pd.Series(pd.to_datetime(['2020-12-31T21:00Z'], utc=True)), '2020')
        with self.assertRaises(ValueError):
            validate_period(timestamp, '2022')

    def test_ablation_keeps_exact_baseline_pipeline_except_hour(self):
        before, after = model_for(CHAMPION, 6), make_ablation(6)
        step_a, step_b = (model.named_steps for model in (before, after))
        self.assertEqual(step_a['classifier'].get_xgb_params(), step_b['classifier'].get_xgb_params())
        numeric_a, state_a = step_a['prepare'].transformers
        numeric_b, state_b = step_b['prepare'].transformers
        self.assertEqual(numeric_b[2], [col for col in numeric_a[2] if col != 'hour_utc'])
        self.assertIn('hour_utc', numeric_a[2])
        self.assertEqual(joblib.hash(numeric_a[1]), joblib.hash(numeric_b[1]))
        self.assertEqual(state_a[1].get_params(), state_b[1].get_params())
        self.assertEqual(state_a[2], state_b[2])

    def test_hourly_summary_exposes_prevalence_and_score_burden(self):
        frame = pd.DataFrame(dict(hour_utc=[3, 3, 4], candidate_y=[1, 0, 1],
                                  coverage_3h=[1., .5, 1.]))
        result = hourly_summary(frame, np.array([.8, .6, .5]), .5).set_index('hour_utc')
        self.assertEqual(result.loc[3, 'prevalence'], .5)
        self.assertAlmostEqual(result.loc[3, 'mean_score'], .7)
        self.assertEqual(result.loc[3, 'false_positive_rate'], 1.)
        self.assertEqual(result.loc[3, 'mean_coverage_3h'], .75)
        self.assertEqual(result.loc[4, 'recall'], 0.)
        self.assertTrue(np.isnan(result.loc[4, 'false_positive_rate']))


if __name__ == '__main__':
    unittest.main()
