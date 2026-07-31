#!/usr/bin/env python3
"""Tests for the schema-23 quotient arithmetic validator."""

import unittest

import validate_raster_quotient_arithmetic as arithmetic


class QuotientArithmeticValidatorTests(unittest.TestCase):
    def test_layout_is_fixed(self) -> None:
        self.assertEqual(len(arithmetic.DISCOVERY_WIDTHS), 80)
        self.assertEqual(len(arithmetic.HOLDOUT_WIDTHS), 16)
        self.assertEqual(arithmetic.RECORD.size, 48)
        self.assertEqual(arithmetic.expected_file_bytes(), 125_829_120)

    def test_float32_control_bits_are_exact(self) -> None:
        self.assertEqual(arithmetic.float32_bits(0.5), 0x3F000000)
        self.assertEqual(
            arithmetic.float32_bits(65_535 * 2.0**-16),
            0x3F7FFF00,
        )

    def test_record_accepts_constant_reciprocals(self) -> None:
        record = (
            0x3BA3D70A,
            0x3BA3D70A,
            0x3BA3D70A,
            0x3BA3D70A,
            0x3BA3D70A,
            0x3BA3D70A,
            0x3BA3D70A,
            0x3BA3D70A,
            0x3C23D70A,
            0x3C23D70A,
            0x3C23D70A,
            0x3F000000,
        )
        reciprocals = arithmetic.validate_record(
            record,
            expected_delta_bits=0x3F000000,
            reciprocal_bits=None,
        )
        self.assertEqual(
            arithmetic.validate_record(
                record,
                expected_delta_bits=0x3F000000,
                reciprocal_bits=reciprocals,
            ),
            reciprocals,
        )

    def test_record_rejects_changed_reciprocal(self) -> None:
        record = (0x3F000000,) * 12
        with self.assertRaisesRegex(ValueError, "reciprocal changed"):
            arithmetic.validate_record(
                record,
                expected_delta_bits=0x3F000000,
                reciprocal_bits=(
                    0x3F000001,
                    0x3F000000,
                    0x3F000000,
                ),
            )

    def test_record_rejects_wrong_delta(self) -> None:
        record = (0x3F000000,) * 12
        with self.assertRaisesRegex(ValueError, "delta ordering"):
            arithmetic.validate_record(
                record,
                expected_delta_bits=0x3F000001,
                reciprocal_bits=None,
            )

    def test_record_rejects_nonfinite_value(self) -> None:
        record = (0x3F000000,) * 11 + (0x7F800000,)
        with self.assertRaisesRegex(ValueError, "finite and positive"):
            arithmetic.validate_record(
                record,
                expected_delta_bits=0x7F800000,
                reciprocal_bits=None,
            )


if __name__ == "__main__":
    unittest.main()
