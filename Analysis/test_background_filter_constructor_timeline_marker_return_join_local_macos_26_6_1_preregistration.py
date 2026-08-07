#!/usr/bin/env python3
"""Integrity checks for the immediate constructor-return preregistration."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
REPOSITORY = ANALYSIS.parent
PREREGISTRATION_PATH = (
    ANALYSIS
    / "background_filter_constructor_timeline_marker_return_join_local_macos_26_6_1_preregistration.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ConstructorReturnPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_runtime_outcome_is_unknown_before_dispatch(self) -> None:
        self.assertIsNone(self.value["runtimeOutcomeFrozenBeforeDispatch"])

    def test_every_frozen_file_hash_matches(self) -> None:
        for record in self.value["frozenImplementation"]["files"]:
            path = REPOSITORY / record["path"]
            self.assertTrue(path.is_file(), record["path"])
            self.assertEqual(sha256(path), record["sha256"], record["path"])

    def test_selection_is_value_blind_and_includes_immediate_return(self) -> None:
        selection = self.value["selectionPolicy"]
        self.assertFalse(selection["capturedValuesMaySelectCalls"])
        self.assertTrue(selection["selectionFrozenBeforeDispatch"])
        self.assertIn("immediate return", selection["chainSelection"])

    def test_five_stop_predictions_are_frozen(self) -> None:
        predictions = self.value["prospectivePredictions"]
        self.assertTrue(predictions["everyChainHasExactFiveEventSequence"])
        self.assertTrue(
            predictions[
                "everyInitializedConstructorReturnByteMatchesProviderObjectBitwise"
            ]
        )
        self.assertIsNone(predictions["publicParameters49FieldMatchCountPredicted"])
        self.assertFalse(predictions["paddingByteEqualityAcceptanceGated"])

    def test_late_snapshot_predecessor_remains_failed(self) -> None:
        predecessor = self.value["rejectedDirectJoinPredecessor"]
        self.assertEqual(predecessor["validationExitStatus"], 2)
        self.assertTrue(predecessor["frozenGateRemainsFailed"])
        self.assertTrue(predecessor["constructorOutputWasObservedAfterTemporaryLifetime"])

    def test_authority_remains_narrow(self) -> None:
        authority = self.value["productAuthority"]
        self.assertTrue(authority["liveConstructorReturnJoinMayPassProspectively"])
        for key in (
            "generalPublicParameters49FieldConstructionLawEstablishedOnPass",
            "upstreamCropAllocationPolicyEstablishedOnPass",
            "physicalRetinaColorPixelCompositorTransferEstablishedOnPass",
            "independentWalleZeroByteFrameParityEstablishedOnPass",
            "liquidGlassParityEstablishedOnPass",
            "productionShaderAuthorizedOnPass",
        ):
            self.assertFalse(authority[key])


if __name__ == "__main__":
    unittest.main()
