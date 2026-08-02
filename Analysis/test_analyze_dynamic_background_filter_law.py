#!/usr/bin/env python3
"""Tests for recovered dynamic glass-background input laws."""

import unittest

import analyze_dynamic_background_filter_law as law


class ArithmeticTests(unittest.TestCase):
    def test_float32_mix_matches_captured_headroom_staging(self) -> None:
        self.assertEqual(
            law.float32_mix(1.2, 9_999.0, 0.7838306427001953),
            7_837.78173828125,
        )

    def test_blur_weight_uses_nested_float32_mix(self) -> None:
        prediction = law.predicted_numeric_fields(
            {"width": 640, "height": 640},
            0.7838306427001953,
        )
        self.assertEqual(prediction["inputBlurOpacity1"], 0.34108325839042664)
        self.assertEqual(prediction["inputBlurOpacity3"], 0.6821665167808533)

    def test_geometry_fields_share_effective_diameter(self) -> None:
        prediction = law.predicted_numeric_fields(
            {"width": 640, "height": 640},
            0.7838306427001953,
        )
        self.assertEqual(
            law.float32(prediction["inputBlurDistance0"]),
            law.float32(-252.18132699417765),
        )
        self.assertEqual(
            law.float32(prediction["inputOuterRefractionHeight"]),
            law.float32(63.04533174854441),
        )


if __name__ == "__main__":
    unittest.main()
