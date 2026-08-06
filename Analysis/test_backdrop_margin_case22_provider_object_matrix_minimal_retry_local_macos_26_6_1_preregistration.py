#!/usr/bin/env python3
"""Integrity checks for the callsite-gated minimal matrix retry."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
REPOSITORY = ANALYSIS.parent
PATH = (
    ANALYSIS
    / "backdrop_margin_case22_provider_object_matrix_minimal_retry_local_macos_26_6_1_preregistration.json"
)


class MinimalCase22ProviderObjectMatrixRetryPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PATH.read_text(encoding="utf-8"))

    def test_broad_attempt_is_preserved_without_authority(self) -> None:
        failed = self.value["stoppedBroadDomainAttempt"]
        self.assertTrue(failed["investigatorTerminated"])
        self.assertEqual(failed["providerCallCount"], 432)
        self.assertEqual(failed["providerGroupLinkedCallCount"], 432)
        self.assertFalse(failed["selectionDomainMatchedFrozenGroupDiagnostic"])
        self.assertFalse(failed["matrixAuthority"])
        self.assertFalse(failed["productAuthority"])

    def test_retry_only_restores_the_exact_frozen_caller(self) -> None:
        retry = self.value["retryOverlay"]
        self.assertTrue(retry["baseMinimalCaptureImportedUnchanged"])
        self.assertTrue(retry["selectionDomainNarrowedToOriginalCaller"])
        self.assertFalse(retry["capturedValueUsedForArmingOrSelection"])
        for key, value in retry.items():
            if key.endswith("Changed"):
                self.assertFalse(value, key)
        self.assertEqual(retry["callerGroupCallOffset"], 5760)
        self.assertEqual(retry["callerReturnOffset"], 5764)
        self.assertEqual(retry["perSelectedCallMaximumStopCount"], 6)

    def test_contract_is_complete_output_blind_and_zero_tolerance(self) -> None:
        contract = self.value["captureContract"]
        self.assertEqual(contract["requireTimelineSampleCount"], 33)
        self.assertEqual(contract["requireTimelineSamplesLength"], 33)
        self.assertEqual(contract["requireTimelineFailedSamples"], 0)
        for key, value in contract.items():
            if key.startswith("captured") and key.endswith("UsedForRuntimeSelection"):
                self.assertFalse(value, key)
        self.assertTrue(contract["zeroTolerance"])

    def test_every_frozen_hash_matches(self) -> None:
        for item in self.value["frozenImplementation"]["files"]:
            self.assertEqual(
                hashlib.sha256((REPOSITORY / item["path"]).read_bytes()).hexdigest(),
                item["sha256"],
                item["path"],
            )

    def test_outcome_is_unknown_and_authority_stays_narrow(self) -> None:
        self.assertIsNone(self.value["runtimeOutcomeFrozenBeforeDispatch"])
        self.assertTrue(
            all(value is None for value in self.value["unknownBeforeDispatch"].values())
        )
        authority = self.value["authorityOnPass"]
        allowed = {
            "exactAllLiveCase22ProviderObjectsForThisOpenedProfile",
            "exactObjectOffsetAndReturnCovarianceForThisOpenedProfile",
        }
        for key, value in authority.items():
            self.assertIs(value, key in allowed, key)


if __name__ == "__main__":
    unittest.main()
