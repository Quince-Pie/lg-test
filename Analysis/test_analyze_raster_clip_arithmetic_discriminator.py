#!/usr/bin/env python3
"""Unit tests for fixed-post-clip arithmetic analysis helpers."""

from fractions import Fraction
import unittest

import numpy as np

import analyze_raster_clip_arithmetic_discriminator as analysis
import validate_raster_clip_arithmetic_discriminator as capture


class RasterClipArithmeticAnalysisTests(unittest.TestCase):
    def test_zero_distance_preserves_source_delta(self) -> None:
        for bits in capture.DELTA_BITS:
            exact = analysis.exact_generated_delta(
                bits,
                post_clip_span_fixed=81_920,
                distance_fixed=0,
            )
            self.assertEqual(
                analysis.boundary_analysis.fraction_float32_bits(exact),
                bits,
            )

    def test_directed_quantizers_bound_source(self) -> None:
        value = Fraction(12_345_679, 16_777_216)
        for precision in range(24, 31):
            down = analysis.boundary_analysis.quantize_down(value, precision)
            nearest = analysis.quantize_nearest_even(value, precision)
            up = analysis.quantize_up(value, precision)
            self.assertLessEqual(down, value)
            self.assertLessEqual(down, nearest)
            self.assertLessEqual(nearest, up)
            self.assertGreaterEqual(up, value)

    def test_synthetic_pull_record_accepts_exact_slope(self) -> None:
        records = np.zeros(
            (capture.SAMPLE_COUNT, capture.RECORD_WORD_COUNT),
            dtype=np.uint32,
        )
        witness_index = 0
        center_word = 8 + 16 * (witness_index // 4)
        pull_zero_word = center_word + 4
        pull_fifteen_word = center_word + 8
        slope_bits = 0x3A92_4924
        slope = analysis.float32_value(slope_bits)
        constant = analysis.float32_value(0x3D80_0000)
        for sample_index, base_position in enumerate((0.0, 15.0, 31.0)):
            records[sample_index, pull_zero_word] = analysis.float32_bits(
                base_position * slope + constant
            )
            records[sample_index, pull_fifteen_word] = analysis.float32_bits(
                (base_position + 0.9375) * slope + constant
            )
        self.assertTrue(
            analysis.accepts_slope(
                records,
                witness_index=witness_index,
                slope_bits=slope_bits,
            )
        )
        self.assertFalse(
            analysis.accepts_slope(
                records,
                witness_index=witness_index,
                slope_bits=slope_bits + 8,
            )
        )


if __name__ == "__main__":
    unittest.main()
