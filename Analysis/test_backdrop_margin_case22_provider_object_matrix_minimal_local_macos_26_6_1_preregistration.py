#!/usr/bin/env python3
"""Integrity checks for the minimal provider-object matrix freeze."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
REPOSITORY = ANALYSIS.parent
PATH = (
    ANALYSIS
    / "backdrop_margin_case22_provider_object_matrix_minimal_local_macos_26_6_1_preregistration.json"
)


class MinimalCase22ProviderObjectMatrixPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PATH.read_text(encoding="utf-8"))

    def test_heavy_capture_is_preserved_without_authority(self) -> None:
        failed = self.value["failedHeavyCapture"]
        self.assertEqual(failed["providerCallCount"], 90)
        self.assertEqual(failed["providerGroupLinkedCallCount"], 90)
        self.assertEqual(failed["traceFailureCount"], 0)
        self.assertFalse(failed["completeTimelinePassed"])
        self.assertFalse(failed["matrixAuthority"])
        self.assertFalse(failed["productAuthority"])

    def test_minimal_capture_only_removes_observation_overhead(self) -> None:
        minimal = self.value["minimalCapture"]
        self.assertEqual(minimal["activeBreakpointCountPerSelectedCall"], 4)
        self.assertFalse(minimal["inheritedWriterBreakpointsInstalled"])
        self.assertFalse(minimal["inheritedGroupEntryOrBranchBreakpointsInstalled"])
        for key, value in minimal.items():
            if key.endswith("Changed"):
                self.assertFalse(value, key)

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
