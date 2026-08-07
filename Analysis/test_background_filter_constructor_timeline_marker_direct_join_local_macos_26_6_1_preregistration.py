#!/usr/bin/env python3
"""Integrity checks for the live direct-join preregistration."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
REPOSITORY = ANALYSIS.parent
PREREGISTRATION_PATH = (
    ANALYSIS
    / "background_filter_constructor_timeline_marker_direct_join_local_macos_26_6_1_preregistration.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DirectJoinPreregistrationTests(unittest.TestCase):
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

    def test_selection_is_structural_and_value_blind(self) -> None:
        selection = self.value["selectionPolicy"]
        self.assertFalse(selection["capturedValuesMaySelectCalls"])
        self.assertTrue(selection["selectionFrozenBeforeDispatch"])
        self.assertEqual(
            selection["sampleSelection"],
            "last structurally completed chain in each preceding marker interval",
        )

    def test_predictions_are_exact_but_mapping_outcome_is_open(self) -> None:
        predictions = self.value["prospectivePredictions"]
        self.assertTrue(predictions["all32MarkerBatchesAreNonempty"])
        self.assertTrue(
            predictions["everyBuilderOutputMatchesConstructorParametersBitwise"]
        )
        self.assertTrue(
            predictions[
                "everyInitializedConstructorOutputByteMatchesProviderObjectBitwise"
            ]
        )
        self.assertIsNone(predictions["publicParameters49FieldMatchCountPredicted"])
        self.assertIsNone(predictions["constructorAndProviderAddressEqualityPredicted"])
        self.assertFalse(predictions["paddingByteEqualityAcceptanceGated"])

    def test_rejected_census_is_preserved(self) -> None:
        predecessor = self.value["rejectedCensusPredecessor"]
        self.assertEqual(predecessor["validationExitStatus"], 2)
        self.assertTrue(predecessor["frozenGateRemainsFailed"])
        self.assertTrue(predecessor["retrospectiveExactOneToOneTopologyEstablished"])

    def test_product_authority_remains_narrow(self) -> None:
        authority = self.value["productAuthority"]
        self.assertTrue(authority["liveDirectJoinMayPassProspectively"])
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
