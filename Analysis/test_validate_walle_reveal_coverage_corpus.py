#!/usr/bin/env python3

from __future__ import annotations

import math
import struct
import tempfile
import unittest
from pathlib import Path

from validate_walle_reveal_coverage_corpus import (
    ValidationError,
    expected_radius,
    parse_source_samples,
)


def append_block(payload: bytearray, x: int, y: int, width: int, height: int) -> None:
    payload.extend(struct.pack("<iiII", x, y, width, height))
    payload.extend(bytes((x & 255, y & 255, 17, 255)) * width * height)


class RevealCoverageCorpusTests(unittest.TestCase):
    def test_sample_parser_accepts_frozen_layout(self) -> None:
        payload = bytearray(b"LGRSMP01")
        payload.extend(
            struct.pack(
                "<IIIIQQQI",
                1,
                512,
                512,
                2048,
                struct.unpack("<Q", struct.pack("<d", 128.0))[0],
                struct.unpack("<Q", struct.pack("<d", 192.0))[0],
                struct.unpack("<Q", struct.pack("<d", 64.5))[0],
                65,
            )
        )
        append_block(payload, 0, 0, 384, 384)
        for index in range(64):
            append_block(payload, index, index, 16, 16)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "samples.raw"
            path.write_bytes(payload)
            parsed = parse_source_samples(path)
        self.assertEqual(parsed.width, 512)
        self.assertEqual(parsed.height, 512)
        self.assertEqual(parsed.center_x, 128.0)
        self.assertEqual(parsed.center_y, 192.0)
        self.assertEqual(parsed.radius, 64.5)
        self.assertEqual(len(parsed.blocks), 65)

    def test_sample_parser_rejects_trailing_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "samples.raw"
            path.write_bytes(b"LGRSMP01" + bytes(64))
            with self.assertRaises(ValidationError):
                parse_source_samples(path)

    def test_effective_radius_is_half_pixel_quantized(self) -> None:
        radius = expected_radius(1, 17, 1024, 1024, 2, 0.25, 0.30)
        unsnapped = math.hypot(1536.0, 1433.6) * 1.03 / 16
        self.assertEqual(radius, math.floor(2 * unsnapped) / 2)
        self.assertEqual(radius, 135.0)


if __name__ == "__main__":
    unittest.main()
