#!/usr/bin/env python3
"""Tests for live-carrier normalization of the opened primary-mesh scan."""

import math
import unittest

import analyze_dynamic_allocation_primary_mesh_normalized_response as analyzer


class PrimaryMeshNormalizedResponseTests(unittest.TestCase):
    def test_response_runs_report_only_observed_boundaries(self) -> None:
        lower = (0.0, 0.0, 0.0, -1.0)
        upper = (1.0, 0.0, 0.0, -1.0)
        runs = analyzer.response_runs([(85, upper), (83, lower), (84, lower)])
        self.assertEqual(
            analyzer.transition_brackets(runs),
            [
                {
                    "lowerObservedValue": 84,
                    "upperObservedValue": 85,
                    "lowerResponse": list(lower),
                    "upperResponse": list(upper),
                }
            ],
        )

    def test_classification_denies_unseen_transfer(self) -> None:
        self.assertIn("not-an-unseen-geometry-transfer", analyzer.CLASSIFICATION)

    def test_pixel_center_retains_one_ulp_staging_residual(self) -> None:
        value = 251.0 + math.ulp(251.0)
        self.assertEqual(analyzer.pixel_center(value), (251, math.ulp(251.0), 1.0))

    def test_pixel_center_rejects_larger_residual(self) -> None:
        with self.assertRaisesRegex(ValueError, "permitted binary64-ULP distance"):
            analyzer.pixel_center(251.0 + 2.0 * math.ulp(251.0))


if __name__ == "__main__":
    unittest.main()
