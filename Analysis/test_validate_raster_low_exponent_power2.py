#!/usr/bin/env python3
"""Tests for the low-determinant-exponent transfer gate."""

import unittest

import validate_raster_low_exponent_power2 as low_exponent


class RasterLowExponentPower2Tests(unittest.TestCase):
    def test_preregistration_and_predictions_are_frozen(self) -> None:
        low_exponent.load_preregistration()
        self.assertEqual(
            len(low_exponent.load_top_left_slope_offsets()),
            low_exponent.TOP_LEFT_SLOPE_OFFSET_COUNT,
        )
        coefficients = low_exponent.predicted_coefficients()
        self.assertEqual(
            low_exponent.uint32_sha256(coefficients),
            low_exponent.ONE_GEOMETRY_COEFFICIENT_SHA256,
        )
        self.assertEqual(
            low_exponent.repeated_prediction_metadata(),
            {
                "coefficientCount": 458_752,
                "sha256": low_exponent.FOUR_GEOMETRY_COEFFICIENT_SHA256,
                "directDivisionOffsetDistribution": {
                    "-1": 27_680,
                    "0": 392_552,
                    "1": 38_520,
                },
            },
        )

    def test_every_determinant_normalizes_exactly_to_its_width(self) -> None:
        for width in low_exponent.factorized.geometry_widths():
            for geometry in low_exponent.GEOMETRY_CASES:
                height = int(geometry["height"])
                self.assertEqual(height.bit_count(), 1)
                shift = height.bit_length() - 1
                area = width * height
                self.assertEqual(area, width << shift)
                self.assertEqual(area >> shift, width)
                positions = [
                    low_exponent.sample_position(
                        width,
                        geometry,
                        sample_index,
                    )
                    for sample_index in range(low_exponent.SAMPLE_POSITION_COUNT)
                ]
                self.assertEqual(
                    [position["tileLocalX"] for position in positions],
                    list(low_exponent.SAMPLE_TILE_LOCAL_XS),
                )

    def test_raw_layout_size_is_frozen(self) -> None:
        self.assertEqual(low_exponent.RECORD.size, 16)
        self.assertEqual(low_exponent.COEFFICIENT_COUNT, 458_752)
        self.assertEqual(low_exponent.RAW_BYTES, 14_680_064)


if __name__ == "__main__":
    unittest.main()
