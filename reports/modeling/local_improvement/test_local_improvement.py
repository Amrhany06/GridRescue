"""Regression checks for decision rules and past-only history."""
import unittest

import numpy as np

from thresholds import metrics, pareto, select_thresholds, threshold_curve


class ThresholdTests(unittest.TestCase):
    def test_tied_scores_move_together_and_half_is_strict(self):
        y = np.array([1, 0, 1, 0])
        scores = np.array([0.8, 0.5, 0.5, 0.2])
        points = threshold_curve(y, scores)
        self.assertEqual(points.predicted.tolist(), [0, 1, 3, 4])
        self.assertEqual(metrics(y, scores, 0.5)['tp'], 1)
        self.assertEqual(metrics(y, scores, points.threshold.iloc[2])['fp'], 1)

    def test_constraints_use_best_accuracy_among_eligible_points(self):
        y = np.array([1, 0, 0, 1, 0])
        scores = np.array([0.9, 0.8, 0.7, 0.6, 0.5])
        curve = threshold_curve(y, scores)
        candidates = select_thresholds(curve)
        self.assertEqual(metrics(y, scores, candidates['accuracy_recall_50'])['recall'], 0.5)
        self.assertEqual(metrics(y, scores, candidates['accuracy_recall_60'])['recall'], 1.0)
        self.assertEqual(metrics(y, scores, candidates['f2'])['f2'], 5 / 6)

    def test_single_class_group_preserves_counts_and_undefined_rank(self):
        result = metrics([0, 0], [0.7, 0.1], 0.5)
        self.assertEqual(result['false_alarms_per_1000'], 500)
        self.assertIsNone(result['average_precision'])
        self.assertIsNone(result['balanced_accuracy'])

    def test_pareto_retains_only_strict_recall_accuracy_tradeoffs(self):
        curve = threshold_curve([1, 0, 0, 1, 0], [0.9, 0.8, 0.7, 0.6, 0.5])
        frontier = pareto(curve)
        self.assertEqual(frontier.recall.tolist(), [0.5, 1.0])
        self.assertEqual(frontier.accuracy.tolist(), [0.8, 0.6])


if __name__ == '__main__':
    unittest.main()
