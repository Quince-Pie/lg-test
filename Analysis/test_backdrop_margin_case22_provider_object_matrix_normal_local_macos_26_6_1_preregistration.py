#!/usr/bin/env python3
"""Integrity checks for the normal-transition provider-matrix transfer."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
REPOSITORY = ANALYSIS.parent
PATH = (
    ANALYSIS
    / "backdrop_margin_case22_provider_object_matrix_normal_local_macos_26_6_1_preregistration.json"
)


class NormalCase22ProviderObjectMatrixPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PATH.read_text(encoding="utf-8"))

    def test_parent_is_the_exact_passing_allocation_matrix(self) -> None:
        parent = self.value["passingAllocationParent"]
        self.assertTrue(parent["captureContractPassed"])
        self.assertEqual(parent["providerCallCount"], 1228)
        self.assertEqual(parent["providerGroupLinkedCallCount"], 1228)
        self.assertEqual(parent["timelineSampleCount"], 33)
        self.assertEqual(parent["timelineFailedSamples"], 0)
        self.assertEqual(parent["providerReturnWords"], ["0000000000000000"])

    def test_only_allocation_diagnostic_flags_change(self) -> None:
        delta = self.value["transferDelta"]
        self.assertEqual(
            set(key for key, value in delta.items() if isinstance(value, dict)),
            {
                "LG_TRANSITION_ALLOCATION_ONLY",
                "LG_TRANSITION_ALLOCATION_DENSE",
            },
        )
        self.assertEqual(delta["LG_TRANSITION_ALLOCATION_ONLY"], {"from": "1", "to": "0"})
        self.assertEqual(delta["LG_TRANSITION_ALLOCATION_DENSE"], {"from": "1", "to": "0"})
        for key, value in delta.items():
            if key.endswith("Changed"):
                self.assertFalse(value, key)
        self.assertFalse(delta["capturedObjectReturnMarginCropImageOrPixelUsedForSelection"])

    def test_normal_profile_requires_nonzero_return_coverage(self) -> None:
        profile = self.value["profile"]
        self.assertFalse(profile["allocationOnly"])
        self.assertFalse(profile["denseAllocation"])
        contract = self.value["captureContract"]
        self.assertTrue(contract["requireAtLeastTwoDistinctProviderReturnWords"])
        self.assertTrue(contract["requireAtLeastOneFinitePositiveProviderReturn"])
        self.assertEqual(contract["maximumCallCount"], 4096)
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
            "exactAllLiveCase22ProviderObjectsForThisOpenedNormalProfile",
            "exactObjectOffsetAndReturnCovarianceForThisOpenedNormalProfile",
            "observedProviderBranchReplayMayBeDecoded",
        }
        for key, value in authority.items():
            self.assertIs(value, key in allowed, key)


if __name__ == "__main__":
    unittest.main()
