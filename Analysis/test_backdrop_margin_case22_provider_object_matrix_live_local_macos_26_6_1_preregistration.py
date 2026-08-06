#!/usr/bin/env python3
"""Integrity checks for the live provider-matrix transfer."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
REPOSITORY = ANALYSIS.parent
PATH = (
    ANALYSIS
    / "backdrop_margin_case22_provider_object_matrix_live_local_macos_26_6_1_preregistration.json"
)


class LiveCase22ProviderObjectMatrixPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PATH.read_text(encoding="utf-8"))

    def test_parent_transport_passed_but_nonzero_contract_failed(self) -> None:
        parent = self.value["failedDynamicUniformParent"]
        self.assertTrue(parent["transportAndObjectCapturePassed"])
        self.assertFalse(parent["captureContractPassed"])
        self.assertEqual(parent["providerCallCount"], 1232)
        self.assertEqual(parent["zeroGaussianInputCount"], 1232)
        self.assertEqual(parent["zeroGaussianGateCount"], 1232)
        self.assertEqual(parent["providerReturnWords"], ["0000000000000000"])
        self.assertEqual(parent["controlledReplayUnequalByteCount"], 0)

    def test_only_dynamic_uniform_capture_changes(self) -> None:
        delta = self.value["transferDelta"]
        self.assertEqual(
            delta["LG_TRANSITION_UNIFORMS"], {"from": "1", "to": "0"}
        )
        self.assertEqual(
            set(key for key, value in delta.items() if isinstance(value, dict)),
            {"LG_TRANSITION_UNIFORMS"},
        )
        for key, value in delta.items():
            if key.endswith("Changed"):
                self.assertFalse(value, key)
        self.assertFalse(delta["capturedObjectReturnMarginCropImageOrPixelUsedForSelection"])

    def test_historical_nonzero_trace_has_no_transfer_authority(self) -> None:
        motivation = self.value["retrospectiveNonzeroMotivation"]
        self.assertEqual(
            motivation["selectedProviderReturnRawLittleEndianHex"],
            "0000006002a22a40",
        )
        self.assertTrue(motivation["selectedGaussianInputPositive"])
        self.assertTrue(motivation["selectedGaussianGatePositive"])
        self.assertFalse(motivation["dynamicUniformEnvironmentRecorded"])
        self.assertFalse(motivation["applicationTimelinePassed"])
        self.assertFalse(motivation["prospectiveTransferAuthority"])

    def test_live_contract_requires_nonzero_branch_and_complete_timeline(self) -> None:
        profile = self.value["profile"]
        self.assertFalse(profile["dynamicUniforms"])
        self.assertFalse(profile["allocationOnly"])
        self.assertFalse(profile["denseAllocation"])
        contract = self.value["captureContract"]
        self.assertTrue(contract["requireDynamicBackgroundUniformsAbsent"])
        self.assertTrue(contract["requireAtLeastTwoDistinctProviderReturnWords"])
        self.assertTrue(contract["requireAtLeastOneFinitePositiveProviderReturn"])
        self.assertTrue(contract["requireAtLeastOnePositiveGaussianInputAndGateObject"])
        self.assertEqual(contract["requireTimelineSampleCount"], 33)
        self.assertEqual(contract["maximumCallCount"], 4096)

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
            "exactAllLiveCase22ProviderObjectsForThisOpenedLiveProfile",
            "exactObjectOffsetAndReturnCovarianceForThisOpenedLiveProfile",
            "observedProviderBranchReplayMayBeDecoded",
        }
        for key, value in authority.items():
            self.assertIs(value, key in allowed, key)


if __name__ == "__main__":
    unittest.main()
