#!/usr/bin/env python3
"""Tests for the deepest-SDF threshold post-opening analyzer."""

import unittest

import analyze_dynamic_allocation_surviving_path_threshold as analyzer


class SurvivingPathThresholdAnalyzerTests(unittest.TestCase):
    def test_response_runs_preserve_unsampled_brackets(self) -> None:
        runs = analyzer.response_runs(
            [
                (-4, (0.0, 0.0, 0.0, 0.0)),
                (-1, (0.0, 0.0, 0.0, 0.0)),
                (1, (1.0, 0.0, 0.0, 0.0)),
                (4, (1.0, 0.0, 0.0, 0.0)),
            ]
        )
        self.assertEqual(
            analyzer.transition_brackets(runs),
            [
                {
                    "lowerObservedValue": -1,
                    "upperObservedValue": 1,
                    "lowerResponse": [0.0, 0.0, 0.0, 0.0],
                    "upperResponse": [1.0, 0.0, 0.0, 0.0],
                }
            ],
        )

    def test_duplicate_dense_values_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "not unique"):
            analyzer.response_runs(
                [(1, (0.0, 0.0, 0.0, 0.0)), (1, (1.0, 0.0, 0.0, 0.0))]
            )

    def test_classification_denies_unseen_transfer(self) -> None:
        self.assertIn("not-an-unseen", analyzer.CLASSIFICATION)


if __name__ == "__main__":
    unittest.main()
