#!/usr/bin/env python3
"""Integrity checks for the active-Retina provider-transfer preregistration."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
REPOSITORY = ANALYSIS.parent
PREREGISTRATION_PATH = (
    ANALYSIS
    / "backdrop_margin_case22_provider_timeline_marker_retina_transfer_local_macos_26_6_1_preregistration.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RetinaTimelineMarkerPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_runtime_outcome_is_sealed(self) -> None:
        self.assertIsNone(self.value["runtimeOutcomeFrozenBeforeDispatch"])

    def test_every_frozen_file_hash_matches(self) -> None:
        for record in self.value["frozenImplementation"]["files"]:
            path = REPOSITORY / record["path"]
            self.assertTrue(path.is_file(), record["path"])
            self.assertEqual(sha256(path), record["sha256"], record["path"])

    def test_failed_predecessor_remains_failed(self) -> None:
        predecessor = self.value["rejectedPredecessor"]
        self.assertEqual(predecessor["validationExitStatus"], 2)
        self.assertTrue(predecessor["frozenGateRemainsFailed"])

    def test_selection_is_value_blind_and_structural(self) -> None:
        policy = self.value["selectionPolicy"]
        self.assertFalse(policy["capturedObjectOrOutputMaySelectCall"])
        self.assertTrue(policy["selectionFrozenBeforeDispatch"])
        self.assertEqual(policy["sampleIndices"], list(range(1, 33)))
        self.assertEqual(
            policy["selectedProviderCall"],
            "last structurally completed call in the preceding marker interval",
        )

    def test_all_18_fields_and_all_32_returns_are_frozen(self) -> None:
        predictions = self.value["prospectivePredictions"]
        self.assertTrue(predictions["all32SelectedCallsMatchAll18LoadedFieldsBitwise"])
        self.assertTrue(predictions["all32SelectedReturnsMatchExactPublicLaw"])
        self.assertEqual(len(self.value["loadedFieldPredictions"]), 18)
        self.assertTrue(self.value["captureContract"]["zeroTolerance"])

    def test_product_authority_remains_narrow(self) -> None:
        authority = self.value["productAuthority"]
        self.assertTrue(
            authority[
                "sameProfilePublicProviderConstructionMayPassProspectively"
            ]
        )
        for key in (
            "freshMaterialAppearanceGeometryProfileTransferEstablishedOnPass",
            "upstreamCropAllocationPolicyEstablishedOnPass",
            "physicalRetinaColorPixelCompositorTransferEstablishedOnPass",
            "independentWalleZeroByteFrameParityEstablishedOnPass",
            "liquidGlassParityEstablishedOnPass",
            "productionShaderAuthorizedOnPass",
        ):
            self.assertFalse(authority[key])


if __name__ == "__main__":
    unittest.main()
