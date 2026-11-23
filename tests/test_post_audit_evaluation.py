import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPORTS = Path(__file__).resolve().parents[1] / 'reports/modeling'
sys.path[:0] = [str(REPORTS / folder) for folder in ('cloud_expansion', 'precision_diagnostic')]
from cloud_data import fingerprint
from post_audit_evaluation import (checked_cohort, frozen_policy, paired_blocks,
                                   policy_metrics, ranking_metrics, workload)


def rows(labels=(1, 0, 1, 0), scores=(.9, .8, .8, .1), start='2020-01-01'):
    return pd.DataFrame({'fips_code': '06037', 'candidate_y': labels, 'score': scores,
                         'timestamp': pd.date_range(start, periods=len(labels), freq='15min', tz='UTC')})


class EvaluationTests(unittest.TestCase):
    def test_fixed_cohort_rejects_duplicate_shifted_or_relabeled_rows(self):
        frame = rows()
        pin = fingerprint(frame)
        checked_cohort(frame.iloc[::-1], '2020', pin)
        for changed in (pd.concat([frame, frame.iloc[:1]]),
                        frame.assign(candidate_y=1 - frame.candidate_y),
                        frame.assign(timestamp=frame.timestamp + pd.Timedelta(hours=1)),
                        frame.assign(timestamp=frame.timestamp.dt.tz_localize(None))):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                checked_cohort(changed, '2020', pin)

    def test_oof_policy_rejects_development_and_purges_boundary(self):
        earlier = rows(start='2018-07-01')
        middle = rows(start='2019-01-01')
        last = rows()
        folds = {'2018_H2': earlier, '2019': middle, '2020': last}
        pins = {key: fingerprint(value) for key, value in folds.items()}
        policy = frozen_policy(folds, pins)
        self.assertEqual(policy['oof']['rows'], 12)
        self.assertEqual(policy['cutoffs']['target_60'], np.nextafter(.8, -np.inf))
        with self.assertRaises(ValueError):
            frozen_policy({**folds, '2021': rows(start='2021-01-01')}, pins)
        boundary = rows(start='2020-12-31 21:00')
        with self.assertRaises(ValueError):
            frozen_policy({**folds, '2020': boundary}, {**pins, '2020': fingerprint(boundary)})

    def test_ranking_and_frozen_decisions_use_score_ties_and_correct_denominator(self):
        frame = rows()
        ranks = ranking_metrics(frame.candidate_y, frame.score)
        self.assertAlmostEqual(ranks['average_precision'], 5 / 6)
        self.assertEqual(ranks['matched_recall']['0.55'], {'recall': 1., 'precision': 2 / 3})
        self.assertAlmostEqual(ranking_metrics(frame.candidate_y, [.5] * 4)['average_precision'], .5)
        self.assertIsNone(ranking_metrics([0, 0], [.2, .3])['matched_recall']['0.55'])
        fixed = policy_metrics(frame.candidate_y, frame.score, .8)
        self.assertEqual((fixed['recall'], fixed['fp_rows_per_1000']), (.5, 0))
        fixed = policy_metrics(frame.candidate_y, frame.score, np.nextafter(.8, -np.inf))
        self.assertEqual((fixed['recall'], fixed['fp_rows_per_1000']), (1., 250))
        float32 = np.array([.8, .8], dtype='float32')
        self.assertEqual(policy_metrics([1, 0], float32, np.nextafter(float(float32[0]), -np.inf))['tp'], 1)

    def test_flag_runs_split_on_negative_decisions_gaps_and_county(self):
        frame = rows(labels=[1, 1, 0, 1, 0, 1], scores=[1, 0, 1, 1, 1, 1])
        frame.loc[3:, 'timestamp'] += pd.Timedelta(minutes=15)
        frame.loc[5, 'fips_code'] = '06073'
        result = workload(frame.iloc[::-1], frame.score.iloc[::-1] > .5)
        self.assertEqual((result['flag_runs'], result['runs_all_rows_negative']), (4, 1))
        self.assertEqual((result['eligible_county_days'], result['eligible_row_hours']), (2, 1.5))
        self.assertEqual((result['positive_label_runs'], result['positive_runs_with_flag']), (3, 3))

    def test_bootstrap_reuses_the_same_calendar_draw_for_both_models(self):
        frame = pd.concat([rows(start='2021-01-01'), rows(start='2021-01-18')], ignore_index=True)
        ordered = frame.score.to_numpy()
        same = paired_blocks(frame, ordered, ordered, .8, .8, days=7, replicates=12, seed=17)
        self.assertEqual(same['blocks'], 2)
        self.assertTrue(all(item == [0., 0.] for item in same['intervals'].values()))
        different = paired_blocks(frame, ordered, 1 - ordered, .8, .8, days=7, replicates=12, seed=17)
        self.assertGreater(different['intervals']['average_precision'][0], 0)


if __name__ == '__main__':
    unittest.main()
