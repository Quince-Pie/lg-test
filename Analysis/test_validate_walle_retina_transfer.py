#!/usr/bin/env python3
"""Tests for the Walle-shaped physical Retina transfer validator."""

import json
import tempfile
import unittest
from pathlib import Path

from validate_walle_retina_transfer import (
    EXPECTED_CASES,
    FRAME_BYTES,
    HEIGHT,
    PIXELS,
    WIDTH,
    capture_file,
    mismatch_metrics,
    require_exact,
    validate_reported_comparison,
)


REPOSITORY = Path(__file__).resolve().parents[1]


class WalleRetinaTransferValidatorTests(unittest.TestCase):
    def test_frozen_frame_geometry_and_case_matrix(self) -> None:
        self.assertEqual((WIDTH, HEIGHT), (2048, 2048))
        self.assertEqual(PIXELS, 4_194_304)
        self.assertEqual(FRAME_BYTES, 16_777_216)
        self.assertEqual(
            EXPECTED_CASES,
            (
                ("clear-light", "clear", "light"),
                ("clear-dark", "clear", "dark"),
                ("regular-light", "regular", "light"),
                ("regular-dark", "regular", "dark"),
            ),
        )

    def test_mismatch_metrics_are_byte_pixel_and_hash_exact(self) -> None:
        reference = bytes((1, 2, 3, 4, 5, 6, 7, 8))
        candidate = bytes((1, 9, 3, 4, 4, 6, 10, 8))
        metrics = mismatch_metrics(reference, candidate)
        self.assertEqual(metrics["byteCount"], 8)
        self.assertEqual(metrics["pixelCount"], 2)
        self.assertEqual(metrics["mismatchedByteCount"], 3)
        self.assertEqual(metrics["mismatchedPixelCount"], 2)
        self.assertEqual(metrics["maximumChannelDelta"], 7)
        self.assertEqual(metrics["firstMismatchedByte"], 1)
        self.assertFalse(metrics["exactByteMatch"])
        self.assertNotEqual(
            metrics["referenceSHA256"], metrics["candidateSHA256"]
        )

    def test_exact_metrics_have_zero_tolerance(self) -> None:
        payload = bytes(range(16))
        metrics = mismatch_metrics(payload, payload)
        self.assertEqual(metrics["mismatchedByteCount"], 0)
        self.assertEqual(metrics["mismatchedPixelCount"], 0)
        self.assertEqual(metrics["maximumChannelDelta"], 0)
        self.assertEqual(metrics["firstMismatchedByte"], -1)
        self.assertTrue(metrics["exactByteMatch"])
        require_exact(metrics, "test")

    def test_one_code_value_cannot_pass_exact_gate(self) -> None:
        metrics = mismatch_metrics(bytes(4), bytes((0, 0, 1, 0)))
        with self.assertRaisesRegex(ValueError, "1 unequal bytes"):
            require_exact(metrics, "test")

    def test_reported_metrics_cannot_hide_a_difference(self) -> None:
        independent = mismatch_metrics(bytes(4), bytes((1, 0, 0, 0)))
        reported = {"compared": True, **independent}
        validate_reported_comparison(reported, independent, label="test")
        reported["mismatchedByteCount"] = 0
        with self.assertRaisesRegex(ValueError, "mismatchedByteCount differs"):
            validate_reported_comparison(reported, independent, label="test")

    def test_capture_path_cannot_escape_case_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root.parent / "retina-validator-outside"
            outside.write_bytes(b"evidence")
            try:
                with self.assertRaisesRegex(ValueError, "escapes capture root"):
                    capture_file(root, f"../{outside.name}", "test")
            finally:
                outside.unlink(missing_ok=True)

    def test_preregistration_retains_all_or_nothing_product_boundary(self) -> None:
        preregistration = json.loads(
            (
                REPOSITORY
                / "Analysis/walle_retina_transfer_preregistration.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(preregistration["acceptance"]["tolerance"], 0)
        self.assertEqual(
            preregistration["acceptance"]["totalComparedBytes"],
            268_435_456,
        )
        self.assertFalse(
            preregistration["scientificScope"]["independentWalleFrame"]
        )
        self.assertFalse(
            preregistration["scientificScope"]["appleConstructionReopened"]
        )
        self.assertIn(
            "does not itself claim production parity",
            preregistration["promotionRule"],
        )

    def test_swift_probe_retains_physical_transfer_controls(self) -> None:
        source = (REPOSITORY / "Sources/GlassIntrospect/main.swift").read_text(
            encoding="utf-8"
        )
        required = (
            "LG_WALLE_RETINA_TRANSFER_TRACE",
            "finishWalleRetinaTransfer",
            "transitionRetinaCARendererFrame",
            "transitionRGBA8Comparison",
            '"retina-native-0"',
            '"retina-native-1"',
            '"retina-transfer-stimulus-0"',
            '"retina-transfer-stimulus-1"',
            '"retina-flat-0"',
            '"retina-flat-1"',
            '"capturedApplePixelsUsedOnlyAsTransferStimulus": true',
            '"appleConstructionReopened": false',
            '"independentWalleFrameClaimed": false',
            '"outputTolerance": 0',
            "flatLayer.contentsScale = 2",
            "flatLayer.contentsGravity = .resize",
            "flatLayer.minificationFilter = .nearest",
            "flatLayer.magnificationFilter = .nearest",
        )
        for text in required:
            with self.subTest(text=text):
                self.assertIn(text, source)


if __name__ == "__main__":
    unittest.main()
