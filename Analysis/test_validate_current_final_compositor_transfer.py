#!/usr/bin/env python3
"""Tests for the current Iscd/Irsd compositor transfer validator."""

import hashlib
import unittest
from pathlib import Path

from validate_current_final_compositor_transfer import (
    BGRA_BYTES,
    FORCED_COVERAGE_EDITS,
    HEIGHT,
    WIDTH,
    expected_seed,
    mismatch_metrics,
    validate_intervention,
    validate_reported_comparison,
)


REPOSITORY = Path(__file__).resolve().parents[1]


class CurrentFinalCompositorTransferValidatorTests(unittest.TestCase):
    def test_seed_is_exact_premultiplied_bgra8(self) -> None:
        seed = expected_seed()
        self.assertEqual(len(seed), BGRA_BYTES)
        self.assertEqual(
            hashlib.sha256(seed).hexdigest(),
            "33fdf3748e85aa9ee5f1840480f620611ef757bddbb714b77de08c559c15d737",
        )
        for offset in range(0, len(seed), 4):
            alpha = seed[offset + 3]
            self.assertGreaterEqual(alpha, 64)
            self.assertLessEqual(alpha, 255)
            self.assertLessEqual(seed[offset], alpha)
            self.assertLessEqual(seed[offset + 1], alpha)
            self.assertLessEqual(seed[offset + 2], alpha)

    def test_mismatch_metrics_are_byte_and_pixel_exact(self) -> None:
        reference = bytes((1, 2, 3, 4, 5, 6, 7, 8))
        candidate = bytes((1, 9, 3, 4, 4, 6, 10, 8))
        self.assertEqual(
            mismatch_metrics(reference, candidate),
            {
                "byteCount": 8,
                "mismatchedByteCount": 3,
                "mismatchedPixelCount": 2,
                "maximumChannelDelta": 7,
                "firstMismatchedByte": 1,
                "exactByteMatch": False,
            },
        )
        self.assertEqual(
            mismatch_metrics(reference, reference)["mismatchedByteCount"],
            0,
        )

    def test_forced_coverage_intervention_is_frozen(self) -> None:
        intervention = {
            "name": "positive-normal-x",
            "edits": [
                {"field": field, "recordOffset": offset, "hex": encoded}
                for field, offset, encoded in FORCED_COVERAGE_EDITS
            ],
        }
        validate_intervention(intervention, label="test")
        intervention["edits"][4]["hex"] = "0100"
        with self.assertRaisesRegex(ValueError, "edits differ"):
            validate_intervention(intervention, label="test")

    def test_reported_comparison_cannot_hide_one_byte(self) -> None:
        independent = mismatch_metrics(bytes(4), bytes((1, 0, 0, 0)))
        reported = {"compared": True, **independent}
        validate_reported_comparison(
            reported,
            independent,
            label="test comparison",
        )
        reported["mismatchedByteCount"] = 0
        with self.assertRaisesRegex(ValueError, "mismatchedByteCount differs"):
            validate_reported_comparison(
                reported,
                independent,
                label="test comparison",
            )

    def test_swift_source_retains_independent_exact_gate(self) -> None:
        source = (
            REPOSITORY / "Sources/GlassIntrospect/main.swift"
        ).read_text(encoding="utf-8")
        required = (
            "LG_TRANSITION_CURRENT_COMPOSITOR_TRANSFER_TRACE",
            "current_compositor_fragment",
            "candidateOptions.fastMathEnabled = false",
            '"vibrantArithmeticMode": 9',
            '"sourceConstructionMode": 1',
            '"destinationDivisionMode": 0',
            '"positiveControlsPassed": positiveControlsPassed',
            '"candidatesExact": candidatesExact',
        )
        for text in required:
            with self.subTest(text=text):
                self.assertIn(text, source)
        self.assertEqual(WIDTH, 1024)
        self.assertEqual(HEIGHT, 1024)


if __name__ == "__main__":
    unittest.main()
