#!/usr/bin/env python3
"""Integrity checks for the failed normal-flags provider-matrix transfer."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
SOURCE = (
    ANALYSIS
    / "validate_backdrop_margin_case22_provider_object_matrix_normal_local_macos_26_6_1.py"
).read_text(encoding="utf-8")
RESULT_PATH = (
    ANALYSIS
    / "backdrop_margin_case22_provider_object_matrix_normal_local_macos_26_6_1_result.json"
)
RESULT = json.loads(RESULT_PATH.read_text(encoding="utf-8"))


class NormalCase22ProviderObjectMatrixValidatorSourceTests(unittest.TestCase):
    def test_validator_requires_exact_trace_and_timeline_hashes(self) -> None:
        self.assertIn(
            "32f82fab6a209831347bd2673a6c83fb304cdc72fb04045f37ed23c1ea0be614",
            SOURCE,
        )
        self.assertIn(
            "e6fa2d9a2f9916f077f2af1b02d9e24a26a90bc60d72a84e0bb27fda5ef65345",
            SOURCE,
        )

    def test_validator_requires_zero_early_gate_words(self) -> None:
        self.assertIn('"gaussianInput": (136, "f")', SOURCE)
        self.assertIn('"gaussianGate": (144, "d")', SOURCE)
        self.assertIn('value == 0.0', SOURCE)
        self.assertIn(
            'trace_result["providerReturnWords"] == ["0000000000000000"]',
            SOURCE,
        )

    def test_validator_retains_the_exact_controlled_replay_pass(self) -> None:
        self.assertIn('dynamic.get("evidenceMode") == "controlled-replay-v1"', SOURCE)
        self.assertIn('replay.get("exactByteMatch") is True', SOURCE)
        self.assertIn('replay.get("mismatchedByteCount") == 0', SOURCE)

    def test_result_fails_only_the_nonzero_branch_requirements(self) -> None:
        self.assertTrue(RESULT["transportAndObjectCapturePassed"])
        self.assertFalse(RESULT["captureContractPassed"])
        self.assertEqual(RESULT["trace"]["callCount"], 1232)
        self.assertEqual(RESULT["trace"]["failureCount"], 0)
        self.assertEqual(RESULT["trace"]["distinctProviderReturnCount"], 1)
        self.assertEqual(
            RESULT["trace"]["providerReturnWords"], ["0000000000000000"]
        )
        self.assertEqual(
            set(RESULT["failedRequirements"]),
            {
                "requireAtLeastTwoDistinctProviderReturnWords",
                "requireAtLeastOneFinitePositiveProviderReturn",
            },
        )
        self.assertFalse(RESULT["liquidGlassParityEstablished"])

    def test_result_is_canonical_json(self) -> None:
        decoded = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            RESULT_PATH.read_text(encoding="utf-8"),
            json.dumps(decoded, indent=2, sort_keys=True) + "\n",
        )


if __name__ == "__main__":
    unittest.main()
