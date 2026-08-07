#!/usr/bin/env python3
"""Tests for exact selected-region origin/allocation arithmetic."""

import json
from pathlib import Path
import struct
import unittest

import validate_variable_blur_selected_region_origin as validator


CALIBRATION_RESULT = Path(__file__).with_name(
    "variable_blur_selected_region_origin_circle499_calibration_result.json"
)


def bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


class VariableBlurSelectedRegionOriginTests(unittest.TestCase):
    def test_opened_sample_replays_exactly(self) -> None:
        mip = validator.predict_mip_policy(
            radius1=2.5623297691345215,
            source_extent=[676, 677],
        )
        self.assertEqual(mip["levelCount"], 4)
        self.assertEqual(mip["alignmentScale"], 16)
        self.assertEqual(
            validator.predict_integer_bounds(
                bounds=[322, 0, 676, 677],
                radius1=2.5623297691345215,
                alignment_scale=16,
            ),
            [304, -16, 704, 704],
        )

    def test_floor_ceil_is_not_nearest_rounding(self) -> None:
        predicted = validator.predict_integer_bounds(
            bounds=[292, 0, 659, 660],
            radius1=6.986487865447998,
            alignment_scale=32,
        )
        self.assertEqual(predicted, [256, -32, 736, 736])
        self.assertNotEqual(predicted, [288, -32, 672, 704])

    def test_desired_extent_and_allocation_are_separate(self) -> None:
        self.assertEqual(validator.align_up(736), 768)
        self.assertEqual(validator.align_up(704), 704)

    def test_public_radius_is_binary32_exact(self) -> None:
        predicted = validator.predict_radius1(
            blur_radius=0.13135147094726562,
            bleed_blur_radius=5.254058837890625,
            backdrop_scale=0.9753715991973877,
        )
        self.assertEqual(bits(predicted), bits(2.5623297691345215))

    def test_alignment_phase_is_mip_derived(self) -> None:
        cases = (
            (4.789196014404297, [668, 669], 16),
            (6.986487865447998, [659, 660], 32),
            (11.133310317993164, [639, 640], 64),
            (20.412410736083984, [572, 573], 128),
            (20.0, [212, 212], 64),
        )
        for radius, extent, expected in cases:
            with self.subTest(radius=radius, extent=extent):
                self.assertEqual(
                    validator.predict_mip_policy(
                        radius1=radius,
                        source_extent=extent,
                    )["alignmentScale"],
                    expected,
                )


class VariableBlurCalibrationResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(CALIBRATION_RESULT.read_text(encoding="utf-8"))

    def test_calibration_is_exact_without_claiming_transfer(self) -> None:
        self.assertEqual(self.result["status"], "passed")
        self.assertEqual(self.result["authority"], "calibration")
        self.assertEqual(self.result["sampleCount"], 32)
        for field in (
            "originMismatchedComponents",
            "desiredExtentMismatchedComponents",
            "allocationExtentMismatchedComponents",
            "radiusBinary32Mismatches",
        ):
            self.assertEqual(self.result[field], 0)
        self.assertFalse(self.result["selectedRegionOriginTransferPassed"])
        self.assertFalse(self.result["liquidGlassParityEstablished"])

    def test_calibration_separates_desired_and_allocated_extent(self) -> None:
        states = self.result["states"]
        self.assertEqual(
            {state["alignmentScale"] for state in states},
            {16, 32, 64, 128},
        )
        exposed = [
            state for state in states if state["helperDesiredExtent"] == [736, 736]
        ]
        self.assertEqual(len(exposed), 2)
        self.assertTrue(
            all(state["allocatedExtent"] == [768, 768] for state in exposed)
        )


if __name__ == "__main__":
    unittest.main()
