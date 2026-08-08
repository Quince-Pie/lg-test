#!/usr/bin/env python3
"""Tests for the corrected nonvacuous Tmua/Tghn validator."""

import json
from pathlib import Path
import tempfile
import unittest

import validate_small_clear_tmua_nonvacuous_v2 as subject


class SmallClearTmuaNonvacuousV2ValidatorTests(unittest.TestCase):
    def test_pattern_payload_matches_frozen_word_formula(self) -> None:
        self.assertEqual(
            subject.pattern_payload(2, 2, 0x13579BDF),
            bytes.fromhex("df9b57ff e4040aff c0454eff fbda13ff"),
        )

    def test_zero_source_hashes_are_literal(self) -> None:
        for byte_count, expected in subject.TMUA_ZERO_SHA256.items():
            with self.subTest(byte_count=byte_count):
                self.assertEqual(subject.sha256_bytes(bytes(byte_count)), expected)

    def test_raw_payload_reads_exact_formats(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for pixel_format, bytes_per_pixel in ((80, 4), (115, 8)):
                with self.subTest(pixel_format=pixel_format):
                    filename = f"{pixel_format}.raw"
                    payload = bytes(range(bytes_per_pixel))
                    (root / filename).write_bytes(payload)
                    snapshot = {
                        "width": 1,
                        "height": 1,
                        "pixelFormat": pixel_format,
                        "rawCapture": True,
                        "rawBytes": bytes_per_pixel,
                        "rawFile": filename,
                    }
                    self.assertEqual(
                        subject.raw_payload(
                            root,
                            snapshot,
                            "fixture",
                            expected_format=pixel_format,
                            expected_dimensions=(1, 1),
                        ),
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
            subject.raw_payload(
                Path("fixture"),
                snapshot,
                "fixture",
                expected_format=80,
            )

    def test_comparison_metrics_are_byte_and_pixel_exact(self) -> None:
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

    def test_reported_comparison_cannot_hide_a_difference(self) -> None:
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
            subject.validate_reported_comparison(reported, measured, "fixture")

    def test_background_selection_fails_closed(self) -> None:
        trace = {
            "executed": False,
            "eligible": False,
            "selected": False,
            "reason": "no differing exact-halfway decision in state",
        }
        subject.validate_background_selection_trace(
            trace,
            sample=2,
            should_select=False,
            has_differing_axis=False,
        )
        trace["eligible"] = True
        trace["reason"] = "earlier eligible Tghn state selected"
        subject.validate_background_selection_trace(
            trace,
            sample=15,
            should_select=False,
            has_differing_axis=True,
        )

    def test_candidate_grid_and_pipelines_are_frozen(self) -> None:
        self.assertEqual(subject.SAMPLES, tuple(range(2, 32)))
        self.assertEqual(subject.TARGET_BYTES, 4_194_304)
        self.assertEqual(
            subject.TGHN_PIPELINE,
            "com.apple.coreanimation.PBGRABsovXm_TghnA2Xhf_Isrc_Isrc",
        )
        self.assertEqual(
            subject.FINAL_PIPELINE, "com.apple.coreanimation.PBGRAXm_A2Xghfc"
        )

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
