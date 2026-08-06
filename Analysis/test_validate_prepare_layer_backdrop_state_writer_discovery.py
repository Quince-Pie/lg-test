#!/usr/bin/env python3
"""Unit checks for live BackdropLayer-state validation."""

from __future__ import annotations

import math
import struct
import unittest

import validate_prepare_layer_backdrop_state_writer_discovery as validator


def object_payload(byte_count: int) -> bytearray:
    return bytearray(byte_count)


class BackdropStateWriterDiscoveryValidatorTests(unittest.TestCase):
    def test_live_backdrop_base_and_margin_replay_exactly(self) -> None:
        backdrop = object_payload(validator.BACKDROP_OBJECT_BYTE_COUNT)
        layer = object_payload(validator.LAYER_OBJECT_BYTE_COUNT)
        struct.pack_into("<f", backdrop, validator.BACKDROP_MARGIN_OFFSET, 83.0)
        struct.pack_into(
            "<4d", backdrop, validator.BACKDROP_ORIGIN_OFFSET, 0.0, 0.0, 127.0, 127.0
        )
        source, raw, values, margin = validator.replay_get_backdrop_bounds(
            bytes(backdrop), bytes(layer)
        )
        self.assertEqual(source, "backdrop")
        self.assertEqual(margin, 83.0)
        self.assertEqual(values, (-83.0, -83.0, 293.0, 293.0))
        self.assertEqual(raw, struct.pack("<4d", *values))

    def test_nonpositive_backdrop_size_selects_layer_base(self) -> None:
        backdrop = object_payload(validator.BACKDROP_OBJECT_BYTE_COUNT)
        layer = object_payload(validator.LAYER_OBJECT_BYTE_COUNT)
        struct.pack_into("<f", backdrop, validator.BACKDROP_MARGIN_OFFSET, 2.0)
        struct.pack_into(
            "<4d", backdrop, validator.BACKDROP_ORIGIN_OFFSET, 9.0, 9.0, 0.0, 8.0
        )
        struct.pack_into("<2d", layer, validator.LAYER_ORIGIN_OFFSET, 3.0, 4.0)
        struct.pack_into("<2d", layer, validator.LAYER_SIZE_OFFSET, 10.0, 20.0)
        source, _raw, values, _margin = validator.replay_get_backdrop_bounds(
            bytes(backdrop), bytes(layer)
        )
        self.assertEqual(source, "layer")
        self.assertEqual(values, (1.0, 2.0, 14.0, 24.0))

    def test_invalid_expanded_size_zeros_both_size_lanes(self) -> None:
        backdrop = object_payload(validator.BACKDROP_OBJECT_BYTE_COUNT)
        layer = object_payload(validator.LAYER_OBJECT_BYTE_COUNT)
        struct.pack_into("<f", backdrop, validator.BACKDROP_MARGIN_OFFSET, -4.0)
        struct.pack_into(
            "<4d", backdrop, validator.BACKDROP_ORIGIN_OFFSET, 1.0, 2.0, 3.0, 7.0
        )
        _source, _raw, values, _margin = validator.replay_get_backdrop_bounds(
            bytes(backdrop), bytes(layer)
        )
        self.assertEqual(values, (5.0, 6.0, 0.0, 0.0))

    def test_arm_fcsel_nan_behavior_is_explicit(self) -> None:
        nan = math.nan
        self.assertEqual(validator.arm_minimum(nan, 7.0), 7.0)
        self.assertEqual(validator.arm_maximum(nan, 7.0), 7.0)
        self.assertTrue(math.isnan(validator.arm_minimum(7.0, nan)))
        self.assertTrue(math.isnan(validator.arm_maximum(7.0, nan)))

    def test_capture_bounds_are_frozen(self) -> None:
        self.assertEqual(validator.BACKDROP_OBJECT_BYTE_COUNT, 0x90)
        self.assertEqual(validator.LAYER_OBJECT_BYTE_COUNT, 0x140)
        self.assertEqual(validator.RECT_BYTE_COUNT, 0x20)
        self.assertEqual(validator.BACKDROP_MARGIN_OFFSET, 0x24)
        self.assertEqual(validator.BACKDROP_ORIGIN_OFFSET, 0x60)
        self.assertEqual(validator.BACKDROP_SIZE_OFFSET, 0x70)
        self.assertEqual(validator.LAYER_ORIGIN_OFFSET, 0x48)
        self.assertEqual(validator.LAYER_SIZE_OFFSET, 0x58)


if __name__ == "__main__":
    unittest.main()
