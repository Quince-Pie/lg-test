#!/usr/bin/env python3
"""Integrity checks for the failed live-profile provider transfer."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
SOURCE = (
    ANALYSIS
    / "validate_backdrop_margin_case22_provider_object_matrix_live_local_macos_26_6_1.py"
).read_text(encoding="utf-8")
RESULT_PATH = (
    ANALYSIS
    / "backdrop_margin_case22_provider_object_matrix_live_local_macos_26_6_1_result.json"
)
RESULT = json.loads(RESULT_PATH.read_text(encoding="utf-8"))


class LiveProviderObjectMatrixValidatorSourceTests(unittest.TestCase):
    def test_freezes_exact_trace_and_timeline_hashes(self) -> None:
        self.assertIn(
            "8539c9bb226831970b242a95530378bbad86cc3287bdaf1a6f541a91dcfa15fa",
            SOURCE,
        )
        self.assertIn(
            "4df34cd327097767a802b52316e5b60b1dd5eef02731bbfab56c83b53c96c3cc",
            SOURCE,
        )

    def test_seals_zero_branch_without_promoting_domain(self) -> None:
        self.assertIn('trace_result["callCount"] == 1222', SOURCE)
        self.assertIn('"requireCompleteProcessLifetimeSelection"', SOURCE)
        self.assertIn(
            '"requireEveryCase22IterationUntilSelectedCallerReturn"', SOURCE
        )
        self.assertIn('"completeProcessDomainEstablished": False', SOURCE)
        self.assertIn('"liquidGlassParityEstablished": False', SOURCE)

    def test_requires_disabled_dynamic_uniform_capture(self) -> None:
        self.assertIn('"LG_TRANSITION_UNIFORMS": "0"', SOURCE)
        self.assertIn('dynamic.get("requested") is False', SOURCE)
        self.assertIn('dynamic.get("evidenceMode") == "disabled"', SOURCE)

    def test_result_seals_only_observed_call_integrity(self) -> None:
        self.assertTrue(RESULT["observedCallChainIntegrityPassed"])
        self.assertFalse(RESULT["captureContractPassed"])
        self.assertFalse(RESULT["completeProcessDomainEstablished"])
        self.assertEqual(RESULT["trace"]["observedCallCount"], 1222)
        self.assertEqual(
            RESULT["trace"]["observedProviderReturnWords"],
            ["0000000000000000"],
        )
        self.assertFalse(RESULT["liquidGlassParityEstablished"])

    def test_result_is_canonical_json(self) -> None:
        self.assertEqual(
            RESULT_PATH.read_text(encoding="utf-8"),
            json.dumps(RESULT, indent=2, sort_keys=True) + "\n",
        )


if __name__ == "__main__":
    unittest.main()
