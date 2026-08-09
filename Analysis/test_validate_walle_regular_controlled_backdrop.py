#!/usr/bin/env python3
"""Unit discriminators for the regular controlled-backdrop validator."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import validate_walle_regular_controlled_backdrop as validator


class ControlledBackdropValidatorTests(unittest.TestCase):
    def test_controlled_input_is_frozen(self) -> None:
        payload = validator.controlled_input()
        self.assertEqual(len(payload), validator.CONTROLLED_BYTES)
        self.assertEqual(
            validator.sha256_bytes(payload),
            validator.CONTROLLED_SHA256,
        )
        self.assertEqual(payload[:8], bytes.fromhex("0d5a00ff325103ff"))
        self.assertTrue(all(payload[index] == 0xFF for index in range(3, 4096, 4)))

    def test_unique_pixel_counter_uses_complete_bgra_words(self) -> None:
        payload = bytes.fromhex("010203ff010203ff010204ff")
        self.assertEqual(validator.unique_bgra8_pixels(payload), 2)
        with self.assertRaisesRegex(ValueError, "multiple of four"):
            validator.unique_bgra8_pixels(payload[:-1])

    def test_raw_path_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "escapes"):
                validator.raw_path(
                    root,
                    {"rawCapture": True, "rawFile": "../answer.raw"},
                    "synthetic",
                )

    def test_producer_fragment_accepts_both_frozen_branches(self) -> None:
        for fragment in validator.PRODUCER_FRAGMENTS:
            records = [
                {
                    "kind": "pipeline",
                    "encoder": "encoder",
                    "pipeline": {
                        "creationDescriptor": {
                            "fragmentFunction": fragment,
                        }
                    },
                }
            ]
            self.assertEqual(
                validator.producer_fragment(records, "encoder"),
                fragment,
            )

    def test_probe_intercepts_downsample_at_binding_and_replay(self) -> None:
        source = (
            Path(__file__).parents[1] / "Sources" / "GlassIntrospect" / "main.swift"
        ).read_text(encoding="utf-8")
        self.assertEqual(source.count('fragment == "downsample_4_frag_lph"'), 2)


if __name__ == "__main__":
    unittest.main()
