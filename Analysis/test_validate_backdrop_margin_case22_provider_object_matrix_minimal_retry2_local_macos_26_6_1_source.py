#!/usr/bin/env python3
"""Integrity checks for the complete allocation-profile matrix validator."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
SOURCE = (
    ANALYSIS
    / "validate_backdrop_margin_case22_provider_object_matrix_minimal_retry2_local_macos_26_6_1.py"
).read_text(encoding="utf-8")
RESULT_PATH = (
    ANALYSIS
    / "backdrop_margin_case22_provider_object_matrix_minimal_retry2_local_macos_26_6_1_result.json"
)
RESULT = json.loads(RESULT_PATH.read_text(encoding="utf-8"))


class MinimalCase22ProviderObjectMatrixRetry2ValidatorSourceTests(
    unittest.TestCase
):
    def test_validator_requires_the_exact_primary_artifacts(self) -> None:
        for digest in (
            "0e83312d2535ad6601b6bcae178e939e13a9ebae95d15efcc166ffde013e6d72",
            "1dd73cfa4e696c43a0612c107e9a5edcb78c72b14ba80e67a53e4e99b06d931f",
            "87801d05b664f5f5d9c3fba7e4b26deea02c7ca71e6245c528972b6ed1274b8e",
        ):
            self.assertIn(digest, SOURCE)

    def test_validator_requires_every_exact_control_flow_join(self) -> None:
        for needle in (
            'caller_code[5760:5764].hex() == "5526e997"',
            'provider_address == wrapper_address + 16',
            'wrapper_payload == entry_payload == return_payload',
            'raw_v0[:16] == raw_f64 and raw_v0 == group_v0',
            'trace.get("finalActiveSelectedCallerCount") == 0',
            'trace.get("finalFailureCount") == 0',
        ):
            self.assertIn(needle, SOURCE)

    def test_validator_requires_the_complete_retina_timeline(self) -> None:
        self.assertIn('timeline.get("sampleCount") == 33', SOURCE)
        self.assertIn('timeline.get("failedSamples") == 0', SOURCE)
        self.assertIn('timeline.get("windowBackingScaleFactor") == 2', SOURCE)
        self.assertIn('observed_names == expected_names', SOURCE)

    def test_result_passes_only_the_narrow_matrix_contract(self) -> None:
        self.assertTrue(RESULT["captureContractPassed"])
        self.assertTrue(
            RESULT["exactAllLiveProviderObjectsForOpenedAllocationProfile"]
        )
        self.assertEqual(RESULT["trace"]["callCount"], 1228)
        self.assertEqual(RESULT["trace"]["failureCount"], 0)
        self.assertEqual(RESULT["application"]["canonicalImageCount"], 33)
        self.assertFalse(RESULT["publicInputMappingAuthority"])
        self.assertFalse(RESULT["independentWalleZeroByteFrameParity"])
        self.assertFalse(RESULT["liquidGlassParityEstablished"])

    def test_endpoint_candidates_remain_non_authoritative(self) -> None:
        candidates = RESULT["retrospectiveEndpointCandidateSemantics"]
        self.assertEqual(len(candidates), 4)
        for candidate in candidates:
            self.assertTrue(candidate["wordEqual"])
            self.assertFalse(candidate["authenticatedTemporalJoin"])
            self.assertFalse(candidate["publicInputMappingAuthority"])

    def test_result_is_canonical_json(self) -> None:
        decoded = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
        canonical = json.dumps(decoded, indent=2, sort_keys=True) + "\n"
        self.assertEqual(RESULT_PATH.read_text(encoding="utf-8"), canonical)
        self.assertEqual(len(hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest()), 64)


if __name__ == "__main__":
    unittest.main()
