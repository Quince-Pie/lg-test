#!/usr/bin/env python3
"""Integrity checks for the frozen negative field-matrix validator."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
SOURCE = (
    ANALYSIS / "validate_case22_provider_field_matrix_local_macos_26_6_1_retry2.py"
).read_text(encoding="utf-8")
RESULT = json.loads(
    (
        ANALYSIS
        / "case22_provider_field_matrix_local_macos_26_6_1_retry2_result.json"
    ).read_text(encoding="utf-8")
)


class Case22ProviderFieldMatrixRetry2ValidatorSourceTests(unittest.TestCase):
    def test_validator_requires_exact_artifact_hashes(self) -> None:
        for digest in (
            "f457e74a8e179166c13690c45cc73920f50f5a8d1e68aea0dffe617341b043f9",
            "f38bd2c049aeb917de1ef2d2430dee333a78ab745421d4e42f970779b377bdf8",
        ):
            self.assertIn(digest, SOURCE)

    def test_validator_requires_every_marker_but_zero_calls(self) -> None:
        self.assertIn('trace.get("finalIntervalCount") == 23', SOURCE)
        self.assertIn('trace.get("finalEventCount") == 46', SOURCE)
        self.assertIn('trace.get("finalCallCount") == 0', SOURCE)
        self.assertIn('trace.get("finalFailureCount") == 0', SOURCE)

    def test_result_does_not_promote_the_failed_capture(self) -> None:
        self.assertFalse(RESULT["captureContractPassed"])
        self.assertFalse(RESULT["fieldMappingAuthority"])
        self.assertFalse(RESULT["productParityAuthority"])
        self.assertEqual(RESULT["trace"]["providerCallCount"], 0)

    def test_result_is_canonical_json(self) -> None:
        path = (
            ANALYSIS
            / "case22_provider_field_matrix_local_macos_26_6_1_retry2_result.json"
        )
        decoded = json.loads(path.read_text(encoding="utf-8"))
        canonical = json.dumps(decoded, indent=2, sort_keys=True) + "\n"
        self.assertEqual(path.read_text(encoding="utf-8"), canonical)
        self.assertEqual(len(hashlib.sha256(path.read_bytes()).hexdigest()), 64)


if __name__ == "__main__":
    unittest.main()
