#!/usr/bin/env python3
"""Tests for path-isolation producer-mesh response analysis."""

import unittest

import analyze_dynamic_allocation_path_isolation as analysis


class PathIsolationAnalysisTests(unittest.TestCase):
    def test_response_runs_preserve_sampled_transition_brackets(self) -> None:
        runs = analysis.response_runs(
            [
                (-4, (0, 0, 0, 0)),
                (-1, (0, 0, 0, 0)),
                (1, (1, 0, 0, 0)),
                (4, (1, 0, 0, 0)),
                (8, (1, 0, 1, 0)),
            ]
        )
        self.assertEqual(
            runs,
            [
                {
                    "minimumValue": -4,
                    "maximumValue": -1,
                    "response": [0, 0, 0, 0],
                },
                {
                    "minimumValue": 1,
                    "maximumValue": 4,
                    "response": [1, 0, 0, 0],
                },
                {
                    "minimumValue": 8,
                    "maximumValue": 8,
                    "response": [1, 0, 1, 0],
                },
            ],
        )
        self.assertEqual(
            analysis.transition_brackets(runs),
            [
                {
                    "lowerObservedValue": -1,
                    "upperObservedValue": 1,
                    "lowerResponse": [0, 0, 0, 0],
                    "upperResponse": [1, 0, 0, 0],
                },
                {
                    "lowerObservedValue": 4,
                    "upperObservedValue": 8,
                    "lowerResponse": [1, 0, 0, 0],
                    "upperResponse": [1, 0, 1, 0],
                },
            ],
        )

    def test_duplicate_dense_values_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "not unique"):
            analysis.response_runs([(1, (0, 0, 0, 0)), (1, (1, 0, 0, 0))])

    def test_classification_is_not_an_unseen_transfer(self) -> None:
        self.assertIn("post-opening", analysis.CLASSIFICATION)
        self.assertIn("not-an-unseen", analysis.CLASSIFICATION)


if __name__ == "__main__":
    unittest.main()
