#!/usr/bin/env python3
"""Tests for the failed capture_backdrop code-capture audit."""

import hashlib
import json
import unittest
from pathlib import Path

import analyze_dynamic_allocation_capture_backdrop_code_failed_run as analyzer


ANALYSIS_ROOT = Path(__file__).resolve().parent
RESULT_PATH = (
    ANALYSIS_ROOT / "dynamic_allocation_capture_backdrop_code_failed_run_result.json"
)
RESULT_SHA256 = "5d75ceb21031d22402e1d44446d01d0badba6dc9b54b3f48e35be0b2d866aa7e"


class CaptureBackdropCodeFailedRunAnalyzerTests(unittest.TestCase):
    def test_mesh_difference_fields_are_sorted_and_exact(self) -> None:
        self.assertEqual(
            analyzer.mesh_difference_fields(
                {"same": 1, "changed": 2},
                {"same": 1, "changed": 3, "added": 4},
            ),
            ["added", "changed"],
        )

    def test_pipeline_fragment_rejects_incomplete_metadata(self) -> None:
        self.assertIsNone(analyzer.pipeline_fragment({}))
        self.assertEqual(
            analyzer.pipeline_fragment(
                {"pipeline": {"creationDescriptor": {"fragmentFunction": "A"}}}
            ),
            "A",
        )

    def test_classification_denies_accepted_code_recovery(self) -> None:
        self.assertIn("not-an-accepted-code-recovery", analyzer.CLASSIFICATION)

    def test_canonical_failed_result_is_immutable(self) -> None:
        self.assertEqual(
            hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest(), RESULT_SHA256
        )
        result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
        self.assertFalse(result["conclusion"]["frozenCodeCaptureGatePassed"])
        self.assertFalse(result["conclusion"]["captureBackdropBytesRecovered"])
        self.assertTrue(result["conclusion"]["requiresLiveStackQualifiedRetry"])


if __name__ == "__main__":
    unittest.main()
