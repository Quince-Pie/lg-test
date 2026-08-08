#!/usr/bin/env python3
"""Tests for the frozen small-clear Tmua intervention validator."""

import json
from pathlib import Path
import tempfile
import unittest

import validate_small_clear_tmua_composition_intervention as subject


class SmallClearTmuaCompositionValidatorTests(unittest.TestCase):
    def test_raw_rgba16f_payload_reads_every_byte(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = bytes(range(32))
            (root / "source.raw").write_bytes(payload)
            snapshot = {
                "width": 2,
                "height": 2,
                "pixelFormat": 115,
                "rawCapture": True,
                "rawBytes": len(payload),
                "rawFile": "source.raw",
            }
            self.assertEqual(
                subject.raw_payload(root, snapshot, "source"),
                payload,
            )
            (root / "source.raw").write_bytes(payload[:-1])
            with self.assertRaisesRegex(ValueError, "disk bytes"):
                subject.raw_payload(root, snapshot, "source")

    def test_raw_payload_rejects_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            snapshot = {
                "width": 1,
                "height": 1,
                "pixelFormat": 115,
                "rawCapture": True,
                "rawBytes": 8,
                "rawFile": "../source.raw",
            }
            with self.assertRaisesRegex(ValueError, "escapes root"):
                subject.raw_payload(Path(directory), snapshot, "source")

    def test_exact_comparison_has_literal_zero_tolerance(self) -> None:
        exact = {
            "compared": True,
            "exactByteMatch": True,
            "byteCount": 16,
            "mismatchedByteCount": 0,
            "mismatchedPixelCount": 0,
            "matchingPixelFraction": 1.0,
            "meanAbsoluteChannelDelta": 0.0,
            "rootMeanSquareChannelDelta": 0.0,
            "maximumChannelDelta": 0,
            "firstMismatchedByte": -1,
        }
        subject.validate_exact_comparison(exact, 16, "synthetic")
        exact["maximumChannelDelta"] = 1
        with self.assertRaisesRegex(ValueError, "maximumChannelDelta"):
            subject.validate_exact_comparison(exact, 16, "synthetic")

    def test_candidate_order_is_frozen(self) -> None:
        self.assertEqual(
            subject.INTERVENTIONS,
            (
                "zero-for-Tghn-only",
                "zero-for-Irsd-only",
                "zero-for-Tghn-and-Irsd",
            ),
        )
        self.assertEqual(subject.SAMPLES, tuple(range(2, 32)))

    def test_source_hash_validation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preregistration.json"
            path.write_text(json.dumps({}), encoding="utf-8")
            relative = path.relative_to(path.anchor)
            preregistration = {"sourceSHA256": {str(relative): "0" * 64}}
            with self.assertRaisesRegex(ValueError, "pinned source"):
                subject.validate_sources(preregistration)

    def test_zero_texture_branch_is_distinct_from_tolerance(self) -> None:
        zero = bytes(128)
        nonzero = zero[:-1] + b"\x01"
        self.assertFalse(any(zero))
        self.assertTrue(any(nonzero))
        self.assertNotEqual(subject.sha256_bytes(zero), subject.sha256_bytes(nonzero))


if __name__ == "__main__":
    unittest.main()
