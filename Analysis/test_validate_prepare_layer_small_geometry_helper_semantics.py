#!/usr/bin/env python3
"""Unit checks for the helper-semantics validator contract."""

from __future__ import annotations

import unittest

import validate_prepare_layer_small_geometry_helper_semantics as validator


class SmallGeometryHelperSemanticsValidatorTests(unittest.TestCase):
    def test_all_structural_constant_offsets_are_frozen(self) -> None:
        self.assertEqual(
            [offset for _, offset in validator.CONSTANT_SPECS],
            [
                0x394910,
                0x394928,
                0x394930,
                0x394938,
                0x394940,
                0x394918,
                0x394920,
                0x3944F8,
            ],
        )

    def test_delegated_symbol_is_bounded_without_a_code_candidate(self) -> None:
        self.assertEqual(validator.GET_BACKDROP_BOUNDS_RELATIVE, 364696)
        self.assertEqual(validator.GET_BACKDROP_BOUNDS_MAXIMUM_BYTE_COUNT, 65536)
        self.assertIn("get_backdrop_bounds", validator.GET_BACKDROP_BOUNDS_FUNCTION)

    def test_payload_is_bit_exact_and_fail_closed(self) -> None:
        self.assertEqual(validator.payload("00010203", 4, "word"), b"\0\1\2\3")
        with self.assertRaises(ValueError):
            validator.payload("0001", 4, "word")
        with self.assertRaises(ValueError):
            validator.payload("not-hex", 4, "word")


if __name__ == "__main__":
    unittest.main()
