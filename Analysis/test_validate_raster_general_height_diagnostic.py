#!/usr/bin/env python3
"""Tests for the power-of-two-viewport general-height diagnostic gate."""

import unittest

import validate_raster_general_height_diagnostic as diagnostic


class GeneralHeightDiagnosticTests(unittest.TestCase):
    def test_preregistration_and_control_hashes_are_frozen(self) -> None:
        diagnostic.load_preregistration()
        self.assertEqual(
            diagnostic.computed_control_metadata(),
            {
                "pairCount": 484,
                "coefficientCount": 6_776,
                "pairsSha256": diagnostic.CONTROL_PAIRS_SHA256,
                "selectedReciprocalsSha256": (diagnostic.CONTROL_RECIPROCALS_SHA256),
                "predictedCoefficientsSha256": (diagnostic.CONTROL_COEFFICIENTS_SHA256),
            },
        )

    def test_control_table_has_stable_boundaries(self) -> None:
        pair_words, reciprocals, coefficients = diagnostic.control_tables()
        self.assertEqual(
            pair_words[:8],
            [8192, 47, 8192, 61, 8192, 79, 8192, 113],
        )
        self.assertEqual(
            pair_words[-8:],
            [16256, 79, 16256, 113, 16320, 47, 16320, 61],
        )
        self.assertEqual(
            reciprocals[:4],
            [22845571, 17602325, 27183337, 19004280],
        )
        self.assertEqual(
            coefficients[:4],
            [0x37BBD80B, 0x37BBD80A, 0x37BBD80B, 0x37BBD80B],
        )

    def test_every_sample_is_interior_and_same_tile(self) -> None:
        for width in diagnostic.factorized.geometry_widths():
            for geometry in diagnostic.failed_general.GEOMETRY_CASES:
                positions = [
                    diagnostic.sample_position(width, geometry, side)
                    for side in range(diagnostic.SAMPLE_SIDE_COUNT)
                ]
                self.assertEqual(positions[0]["tile"], positions[1]["tile"])
                self.assertEqual(positions[0]["tileLocalX"], 31)
                self.assertEqual(positions[1]["tileLocalX"], 1)

    def test_raw_layout_size_is_frozen(self) -> None:
        self.assertEqual(diagnostic.RECORD.size, 16)
        self.assertEqual(diagnostic.RAW_BYTES, 14_680_064)


if __name__ == "__main__":
    unittest.main()
