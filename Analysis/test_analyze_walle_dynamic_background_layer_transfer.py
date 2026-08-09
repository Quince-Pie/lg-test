#!/usr/bin/env python3
"""Tests for the natural background half-source and BGRA8 transfer model."""

from __future__ import annotations

import unittest

import numpy as np

import analyze_walle_dynamic_background_layer_transfer as analysis


class WalleDynamicBackgroundLayerTransferTests(unittest.TestCase):
    def test_measured_shadow_edge_rounds_through_binary16(self) -> None:
        destination = np.zeros((1, 1, 4), dtype=np.uint8)
        source = np.array(
            [[[[0.0, 0.0, 0.0, 0.005863189697265625]]]],
            dtype=np.float16,
        ).reshape(1, 1, 4)
        output = analysis.half_blend_layer(destination, source.view(np.uint16))
        self.assertEqual(output[0, 0].tolist(), [0, 0, 0, 1])

    def test_main_store_is_reloaded_before_shadow(self) -> None:
        destination = np.zeros((1, 1, 4), dtype=np.uint8)
        source = np.array([0.0, 0.0, 0.0, 0.1], dtype=np.float16).reshape(1, 1, 4)
        first = analysis.half_blend_layer(destination, source.view(np.uint16))
        second = analysis.half_blend_layer(first, source.view(np.uint16))
        self.assertEqual(first[0, 0, 3], 25)
        self.assertEqual(second[0, 0, 3], 48)

    def test_byte_gate_has_zero_tolerance(self) -> None:
        reference = np.zeros((1, 1, 4), dtype=np.uint8)
        candidate = reference.copy()
        candidate[0, 0, 3] = 1
        metrics = analysis.byte_metrics(reference, candidate)
        self.assertFalse(metrics["exact"])
        self.assertEqual(metrics["unequalBytes"], 1)
        self.assertEqual(metrics["unequalPixels"], 1)
        self.assertEqual(metrics["maximumChannelDelta"], 1)

    def test_half_gate_compares_bit_patterns_not_numeric_values(self) -> None:
        positive_zero = np.zeros((1, 1, 4), dtype=np.uint16)
        negative_zero = positive_zero.copy()
        negative_zero[0, 0, 0] = 0x8000
        metrics = analysis.half_word_metrics(positive_zero, negative_zero)
        self.assertFalse(metrics["exact"])
        self.assertEqual(metrics["unequalWords"], 1)
        self.assertEqual(metrics["unequalPixels"], 1)


if __name__ == "__main__":
    unittest.main()
