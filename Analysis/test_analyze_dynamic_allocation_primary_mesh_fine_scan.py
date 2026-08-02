#!/usr/bin/env python3
"""Tests for the preregistered primary-mesh fine-scan analyzer."""

import unittest

import analyze_dynamic_allocation_primary_mesh_fine_scan as analyzer


class PrimaryMeshFineScanAnalyzerTests(unittest.TestCase):
    def test_response_runs_preserve_only_observed_integer_boundaries(self) -> None:
        zero = (0.0, 0.0, 0.0, 0.0)
        changed = (1.0, 0.0, 0.0, 0.0)
        runs = analyzer.response_runs([(82, changed), (80, zero), (81, zero)])
        self.assertEqual(
            runs,
            [
                {"minimumValue": 80, "maximumValue": 81, "response": list(zero)},
                {
                    "minimumValue": 82,
                    "maximumValue": 82,
                    "response": list(changed),
                },
            ],
        )
        self.assertEqual(
            analyzer.transition_brackets(runs),
            [
                {
                    "lowerObservedValue": 81,
                    "upperObservedValue": 82,
                    "lowerResponse": list(zero),
                    "upperResponse": list(changed),
                }
            ],
        )

    def test_prior_response_anchors_cover_both_source_states(self) -> None:
        self.assertEqual(len(analyzer.PRIOR_RESPONSE_ANCHORS), 8)
        self.assertEqual(
            {sample for sample, _ in analyzer.PRIOR_RESPONSE_ANCHORS}, {25, 31}
        )

    def test_classification_denies_geometry_transfer(self) -> None:
        self.assertIn("not-an-unseen-geometry-transfer", analyzer.CLASSIFICATION)


if __name__ == "__main__":
    unittest.main()
