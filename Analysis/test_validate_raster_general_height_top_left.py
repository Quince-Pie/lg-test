#!/usr/bin/env python3
"""Tests for the preregistered top-left primitive-equality gate."""

import unittest
from collections import Counter

import validate_raster_general_height_top_left as top_left


class GeneralHeightTopLeftTests(unittest.TestCase):
    def test_preregistration_sample_hash_and_control_masks_are_frozen(
        self,
    ) -> None:
        top_left.load_preregistration()
        self.assertEqual(
            top_left.uint32_sha256(top_left.SAMPLE_XS),
            top_left.SAMPLE_XS_SHA256,
        )
        masks = top_left.load_bottom_right_masks()
        self.assertEqual(
            Counter(mask.bit_count() for (mask,) in top_left.MASK.iter_unpack(masks)),
            {
                1: 47_028,
                2: 87_910,
                3: 53_644,
                4: 77_776,
                5: 46_314,
                6: 50_065,
                7: 56_457,
                8: 38_651,
                9: 818,
                10: 88,
                11: 1,
            },
        )

    def test_every_sample_is_safely_inside_top_left_triangle(self) -> None:
        for width in top_left.factorized.geometry_widths():
            for geometry in top_left.GEOMETRY_CASES:
                positions = [
                    top_left.sample_position(width, geometry, sample_index)
                    for sample_index in range(top_left.SAMPLE_POSITION_COUNT)
                ]
                self.assertEqual(
                    [position["tile"] for position in positions],
                    list(top_left.SAMPLE_TILES),
                )
                self.assertEqual(
                    [position["tileLocalX"] for position in positions],
                    list(top_left.SAMPLE_TILE_LOCAL_XS),
                )
                self.assertGreater(
                    min(int(position["signedInteriorArea"]) for position in positions),
                    top_left.MINIMUM_SIGNED_INTERIOR_AREA,
                )

    def test_ideal_control_uniquely_recovers_every_direct_slope(self) -> None:
        multiplicity: Counter[int] = Counter()
        widths = top_left.factorized.geometry_widths()
        shifts = top_left.factorized.delta_exponent_shift_bits()
        witnesses = top_left.arithmetic.witness_delta_bits()
        for width_index, width in enumerate(widths):
            for delta_bits in witnesses:
                scaled_value = top_left.arithmetic.float32_value(
                    delta_bits - shifts[width_index]
                )
                direct_bits = top_left.arithmetic.float32_bits(scaled_value / width)
                slope = top_left.arithmetic.float32_value(direct_bits)
                records = []
                for position in top_left.SAMPLE_TILE_LOCAL_XS:
                    first = top_left.arithmetic.float32_bits(float(position) * slope)
                    second = top_left.arithmetic.float32_bits(
                        (float(position) + 0.9375) * slope
                    )
                    records.append((first, second, first, direct_bits))
                accepted = top_left.accepted_slopes(direct_bits, records)
                multiplicity[len(accepted)] += 1
                self.assertEqual(accepted, (direct_bits,))
        self.assertEqual(multiplicity, {1: 114_688})

    def test_raw_layout_size_is_frozen(self) -> None:
        self.assertEqual(top_left.RECORD.size, 16)
        self.assertEqual(top_left.COEFFICIENT_COUNT, 458_752)
        self.assertEqual(top_left.RAW_BYTES, 14_680_064)
        self.assertEqual(
            top_left.BOTTOM_RIGHT_MASK_RAW_BYTES,
            1_835_008,
        )


if __name__ == "__main__":
    unittest.main()
