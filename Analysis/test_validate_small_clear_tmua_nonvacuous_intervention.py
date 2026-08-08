#!/usr/bin/env python3
"""Tests for the nonvacuous small-clear Tmua validator."""

import json
from pathlib import Path
import tempfile
import unittest

import validate_small_clear_tmua_nonvacuous_intervention as subject


class SmallClearTmuaNonvacuousValidatorTests(unittest.TestCase):
    def test_pattern_payload_matches_frozen_word_formula(self) -> None:
        self.assertEqual(
            subject.pattern_payload(2, 2, 0x13579BDF),
            bytes.fromhex("df9b57ff e4040aff c0454eff fbda13ff"),
        )

    def test_raw_payload_reads_bgra8_and_rgba16f(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = ((80, 4), (81, 4), (115, 8))
            for pixel_format, byte_count in cases:
                with self.subTest(pixel_format=pixel_format):
                    filename = f"{pixel_format}.raw"
                    payload = bytes(range(byte_count))
                    (root / filename).write_bytes(payload)
                    snapshot = {
                        "width": 1,
                        "height": 1,
                        "pixelFormat": pixel_format,
                        "rawCapture": True,
                        "rawBytes": byte_count,
                        "rawFile": filename,
                    }
                    self.assertEqual(
                        subject.raw_payload(root, snapshot, "fixture"),
                        payload,
                    )

    def test_raw_payload_rejects_path_escape(self) -> None:
        snapshot = {
            "width": 1,
            "height": 1,
            "pixelFormat": 80,
            "rawCapture": True,
            "rawBytes": 4,
            "rawFile": "../outside.raw",
        }
        with self.assertRaisesRegex(ValueError, "escapes root"):
            subject.raw_payload(Path("fixture"), snapshot, "fixture")

    def test_comparison_metrics_are_exact_and_byte_addressed(self) -> None:
        left = bytes.fromhex("00010203 10111213")
        right = bytes.fromhex("00010203 11111013")
        self.assertEqual(
            subject.comparison_metrics(left, right),
            {
                "byteCount": 8,
                "mismatchedByteCount": 2,
                "mismatchedPixelCount": 1,
                "maximumChannelDelta": 2,
                "firstMismatchedByte": 4,
                "absoluteChannelDelta": 3,
                "squaredChannelDelta": 5,
            },
        )
        exact = subject.comparison_metrics(left, left)
        self.assertEqual(exact["mismatchedByteCount"], 0)
        self.assertEqual(exact["firstMismatchedByte"], -1)

    def test_reported_comparison_cannot_hide_a_mismatch(self) -> None:
        measured = subject.comparison_metrics(bytes(4), b"\x01\0\0\0")
        reported = {
            "compared": True,
            "exactByteMatch": True,
            "byteCount": 4,
            "mismatchedByteCount": 1,
            "mismatchedPixelCount": 1,
            "maximumChannelDelta": 1,
            "firstMismatchedByte": 0,
        }
        with self.assertRaisesRegex(ValueError, "exact flag"):
            subject.validate_reported_comparison(
                reported,
                measured,
                "fixture",
            )

    def test_candidate_domain_and_source_hash_are_frozen(self) -> None:
        self.assertEqual(subject.SAMPLES, tuple(range(3, 10)))
        self.assertEqual(subject.STAGES, ("Tghn", "Irsd"))
        self.assertEqual(subject.TARGET_BYTES, 4_194_304)
        self.assertEqual(
            subject.TMUA_SOURCE_SHA256,
            "7db629a886e5cd6982b3e23b2170681194cf9956d97de086754e68598b705c3e",
        )
        self.assertNotEqual(subject.sha256_bytes(bytes(131_072)), "")

    def test_source_hash_validation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preregistration.json"
            path.write_text(json.dumps({}), encoding="utf-8")
            relative = path.relative_to(path.anchor)
            preregistration = {"sourceSHA256": {str(relative): "0" * 64}}
            with self.assertRaisesRegex(ValueError, "pinned source"):
                subject.validate_sources(preregistration)


if __name__ == "__main__":
    unittest.main()
