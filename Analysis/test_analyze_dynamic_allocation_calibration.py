#!/usr/bin/env python3
"""Tests for the dense dynamic-allocation calibration audit."""

import unittest

import analyze_dynamic_allocation_calibration as calibration


class PhaseTests(unittest.TestCase):
    def test_phase_candidates_diverge_between_frozen_thresholds(self) -> None:
        remaining = 0.4087800979614258
        self.assertEqual(calibration.phase_halo(remaining, calibration.RATIO_PHASE), 2)
        self.assertEqual(
            calibration.phase_halo(remaining, calibration.PADDING_PHASE), 1
        )

    def test_rounded_padding_preserves_the_half_tie(self) -> None:
        remaining = 7.0 / 16.0
        self.assertEqual(
            calibration.phase_halo(remaining, calibration.PADDING_PHASE), 1
        )
        self.assertEqual(
            calibration.phase_halo(remaining + 0.0001, calibration.PADDING_PHASE),
            2,
        )

    def test_clipped_lower_boundary_has_negative_origin_quantum(self) -> None:
        self.assertEqual(
            calibration.phase_origin(
                crop=0,
                clipped_lower=0.0,
                remaining=0.75,
                candidate=calibration.PADDING_PHASE,
            ),
            -4,
        )


class PrimaryMeshTests(unittest.TestCase):
    geometry = {"windowWidth": 1024, "windowHeight": 1024}

    def test_sixteen_vertex_primary_candidate(self) -> None:
        bounds = {"x": [400.25, 1024.0], "y": [0.0, 623.75]}
        self.assertEqual(
            calibration.primary_position_candidate(
                self.geometry,
                bounds,
                scale=0.75,
                vertex_count=16,
            ),
            [298, 0, 768, 470],
        )

    def test_thirty_six_vertex_primary_candidate(self) -> None:
        bounds = {"x": [0.0, 1024.0], "y": [0.0, 1024.0]}
        self.assertEqual(
            calibration.primary_position_candidate(
                self.geometry,
                bounds,
                scale=0.625,
                vertex_count=36,
            ),
            [0, 0, 640, 640],
        )


if __name__ == "__main__":
    unittest.main()
