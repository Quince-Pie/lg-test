#!/usr/bin/env python3
"""Discriminator tests for the natural background-scissor constructor."""

from __future__ import annotations

import unittest

import analyze_walle_dynamic_background_scissor as analysis


class DynamicBackgroundScissorTests(unittest.TestCase):
    REMAINING_AND_SCISSORS = (
        (0.96738719940185547, (112, 96, 816, 816)),
        (0.87432956695556641, (134, 74, 816, 816)),
        (0.74893379211425781, (164, 59, 801, 801)),
        (0.62362098693847656, (194, 86, 744, 744)),
        (0.49930095672607422, (224, 113, 687, 687)),
        (0.37336158752441406, (254, 140, 630, 630)),
        (0.24988365173339844, (284, 167, 573, 573)),
        (0.12501621246337891, (314, 193, 517, 517)),
    )

    def test_calibration_scissors_are_exact(self) -> None:
        for remaining, expected in self.REMAINING_AND_SCISSORS:
            with self.subTest(remaining=remaining):
                result = analysis.predict_scissor_state(
                    analysis.EXPECTED_GEOMETRY, remaining
                )
                self.assertEqual(tuple(result["metalTopLeftScissor"]), expected)

    def test_no_roi_intersection_is_rejected(self) -> None:
        result = analysis.predict_scissor_state(
            analysis.EXPECTED_GEOMETRY, self.REMAINING_AND_SCISSORS[6][0]
        )
        self.assertNotEqual(
            tuple(result["filterDOD"]), self.REMAINING_AND_SCISSORS[6][1]
        )

    def test_prepare_layer_2_8_factor_is_rejected_for_ogl_roi(self) -> None:
        result = analysis.predict_scissor_state(
            analysis.EXPECTED_GEOMETRY,
            self.REMAINING_AND_SCISSORS[2][0],
            roi_radius_factor=2.8,
        )
        self.assertNotEqual(
            tuple(result["metalTopLeftScissor"]),
            self.REMAINING_AND_SCISSORS[2][1],
        )

    def test_changed_sdf_radius_crosses_an_integral_boundary(self) -> None:
        result = analysis.predict_scissor_state(
            analysis.EXPECTED_GEOMETRY,
            self.REMAINING_AND_SCISSORS[7][0],
            sdf_radius=41.0,
        )
        self.assertNotEqual(
            tuple(result["sdf"]["integerBounds"]), (222, 222, 580, 580)
        )

    def test_geometry_guard_rejects_a_matrix_fit_domain_change(self) -> None:
        geometry = {**analysis.EXPECTED_GEOMETRY, "width": 481, "height": 481}
        with self.assertRaisesRegex(ValueError, "geometry differs"):
            analysis.predict_scissor_state(geometry, 0.5)


if __name__ == "__main__":
    unittest.main()
