#!/usr/bin/env python3
"""Unit tests for post-capture clip-boundary analysis helpers."""

from fractions import Fraction
import unittest

import analyze_raster_clip_boundary_tomography as analysis


class RasterClipBoundaryAnalysisTests(unittest.TestCase):
    def test_float32_fraction_round_trip(self) -> None:
        for bits in (0x3E89_145A, 0x3F00_0000, 0x3F80_0000):
            self.assertEqual(
                analysis.fraction_float32_bits(analysis.float32_fraction(bits)),
                bits,
            )

    def test_nearest_even_integer_rounding(self) -> None:
        self.assertEqual(analysis.round_integer_nearest_even(5, 2), 2)
        self.assertEqual(analysis.round_integer_nearest_even(7, 2), 4)
        self.assertEqual(analysis.round_integer_nearest_even(8, 3), 3)

    def test_down_quantizer_never_exceeds_input(self) -> None:
        for precision in (24, 25, 27, 32):
            value = Fraction(12_345_679, 16_777_216)
            quantized = analysis.quantize_down(value, precision)
            self.assertLessEqual(quantized, value)
            self.assertGreater(quantized, 0)


if __name__ == "__main__":
    unittest.main()
