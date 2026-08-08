#!/usr/bin/env python3
"""Tests for the exact small-clear Tkfh fragment constructor."""

from __future__ import annotations

import math
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

import analyze_small_clear_final_payload as payload


REPOSITORY = Path(__file__).resolve().parents[1]
DISCRIMINATING_EXTENT = 53.870121574401765


class SmallClearFinalPayloadTests(unittest.TestCase):
    @staticmethod
    def _prefix(extent: float = DISCRIMINATING_EXTENT) -> bytes:
        axes = ({}, {}, 0.0, 0.0, extent, extent)
        with patch.object(payload.geometry, "layer_axes", return_value=axes):
            return payload.predicted_fragment_prefix({})

    def test_exact_float_header(self) -> None:
        prefix = self._prefix()
        radius = payload.geometry.small_axis_terms(DISCRIMINATING_EXTENT)[2]
        half = payload.geometry.small_axis_terms(DISCRIMINATING_EXTENT)[0]
        self.assertEqual(len(prefix), payload.FRAGMENT_PREFIX_BYTES)
        self.assertEqual(
            struct.unpack_from("<12f", prefix),
            (radius, radius, 4.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 1.0, half, 0.0),
        )

    def test_expansion_order_is_discriminated(self) -> None:
        half, _, exact_radius, _ = payload.geometry.small_axis_terms(
            DISCRIMINATING_EXTENT
        )
        rounded_half_radius = payload.model.float32(
            payload.model.float32(half + 9.0) - 9.0
        )
        self.assertNotEqual(
            payload.model.float32_bits(exact_radius),
            payload.model.float32_bits(rounded_half_radius),
        )

    def test_middle_region_is_exact_zero(self) -> None:
        prefix = self._prefix()
        self.assertEqual(prefix[0x30:0xD0], bytes(160))

    def test_fixed_half_tail_preserves_subnormal_and_sign_bits(self) -> None:
        prefix = self._prefix()
        observed = struct.unpack_from(
            f"<{len(payload.FIXED_HALF_WORDS)}H",
            prefix,
            0xD0,
        )
        self.assertEqual(observed, payload.FIXED_HALF_WORDS)
        self.assertEqual(observed[1], 0x8001)
        self.assertFalse(
            math.isnan(struct.unpack("<e", struct.pack("<H", observed[1]))[0])
        )

    def test_hash_pinned_corpus_is_exact(self) -> None:
        result = payload.analyze(REPOSITORY)
        fragment = result["fragmentPrefix"]
        self.assertEqual(fragment["comparedBytes"], 30_504)
        self.assertEqual(fragment["mismatchedBytes"], 0)
        self.assertEqual(
            fragment["observedSHA256"],
            "b5104c5c048679cd6a39d108d4239234af24bad229478b08852608b4083f012e",
        )


if __name__ == "__main__":
    unittest.main()
