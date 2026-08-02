#!/usr/bin/env python3
"""Tests for the producer-mesh center intervention audit."""

import unittest

import analyze_dynamic_allocation_mesh_calibration as mesh


class CausalDiagnosticsTests(unittest.TestCase):
    def test_integer_residuals_reject_fractional_phase_only(self) -> None:
        metrics = {
            name: {
                "mismatchedComponents": mismatch_count,
                "residuals": [{"edge": edge}],
            }
            for name, mismatch_count, edge in (
                ("circle-640-center", 1, "xLower"),
                ("circle-640-integer", 2, "xUpper"),
                ("circle-640-phase-0500-even", 3, "xLower"),
                ("circle-640-phase-0500-signed", 4, "yLower"),
            )
        }
        remaining = {
            index: {
                name: index / 32.0 + offset
                for offset, name in enumerate(mesh.EXPECTED_GEOMETRIES)
            }
            for index in range(1, 32)
        }
        result = mesh.causal_diagnostics(metrics, remaining)
        self.assertTrue(result["fractionalPhaseOnlyHypothesisRejected"])
        self.assertTrue(result["fractionalPhaseInsufficientAcrossTranslations"])
        self.assertFalse(result["exactKCenterAttributionPossible"])

    def test_equal_realized_k_removes_timing_confound(self) -> None:
        metrics = {
            name: {"mismatchedComponents": 0, "residuals": []}
            for name in mesh.EXPECTED_GEOMETRIES
        }
        remaining = {
            index: {name: index / 32.0 for name in mesh.EXPECTED_GEOMETRIES}
            for index in range(1, 32)
        }
        result = mesh.causal_diagnostics(metrics, remaining)
        self.assertEqual(result["nonEndpointExactRemainingMatchedSampleCount"], 31)
        self.assertTrue(result["exactKCenterAttributionPossible"])


if __name__ == "__main__":
    unittest.main()
