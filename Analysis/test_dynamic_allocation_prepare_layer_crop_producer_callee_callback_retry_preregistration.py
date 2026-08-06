#!/usr/bin/env python3
"""Integrity tests for the producer-callee callback retry preregistration."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_crop_producer_callee_callback_retry_preregistration.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerCropProducerCalleeCallbackRetryPreregistrationTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_retry_is_prospective_without_runtime_outcome(self) -> None:
        registration = self.registration
        self.assertEqual(
            registration[
                "prepareLayerCropProducerCalleeCallbackRetryPreregistrationSchemaVersion"
            ],
            1,
        )
        self.assertIn("callback-name transport retry", registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])

    def test_opened_run_has_no_scientific_outcome(self) -> None:
        failure = self.registration["openedFailedRun"]
        self.assertEqual(failure["runID"], 31068004888)
        self.assertEqual(failure["stopFunctionOffset"], 0)
        self.assertEqual(failure["qualifiedCropRecordCount"], 0)
        self.assertEqual(failure["qualifiedHelperEntryCount"], 0)
        self.assertFalse(failure["manualTraceStarted"])
        self.assertFalse(failure["selectorReached"])
        self.assertFalse(failure["ownershipOutcomeAvailable"])

    def test_amendment_changes_callback_transport_only(self) -> None:
        amendment = self.registration["transportOnlyAmendment"]
        self.assertFalse(amendment["scientificAmendment"])
        for key in (
            "sameBreakpointAddresses",
            "sameMemoryReads",
            "sameStructuralSelector",
            "sameCallerAndCalleeOffsets",
            "sameInstructionStepping",
            "sameCheckpointIntervals",
            "sameValidator",
            "sameAcceptance",
            "sameProductionShader",
        ):
            self.assertTrue(amendment[key], key)
        self.assertEqual(amendment["newBreakpointCount"], 0)
        self.assertEqual(amendment["newMemoryReadCount"], 0)
        self.assertEqual(amendment["newInstructionStepCount"], 0)
        self.assertEqual(amendment["newValueBasedSelectorCount"], 0)

    def test_scientific_gate_and_claim_boundary_are_unchanged(self) -> None:
        gate = self.registration["unchangedScientificGate"]
        acceptance = self.registration["acceptance"]
        self.assertEqual(gate["markerInterval"], 2)
        self.assertEqual(gate["qualifiedHelperOrdinal"], 14)
        self.assertEqual(gate["calleeCallOffset"], 0xF5C)
        self.assertEqual(gate["calleeEntryRelativeToPrepareLayer"], -1_206_100)
        self.assertFalse(gate["cropOrOutputValuesUsedForSelection"])
        self.assertTrue(
            acceptance["returnedFirstRectangleMustMatchIndependentProducerBitForBit"]
        )
        for key in (
            "exactCalleeSemanticsMayBeClaimed",
            "unchangedRepeatMayBeClaimed",
            "allCropHoldoutsMayBeClaimed",
            "materialAppearanceDirectionTransferMayBeClaimed",
            "retina2xAndColorTransferMayBeClaimed",
            "endToEndWalleParityMayBeClaimed",
            "productionShaderMayChange",
            "liquidGlassParityMayBeClaimed",
        ):
            self.assertFalse(acceptance[key], key)

    def test_frozen_implementation_hashes_match(self) -> None:
        for record in self.registration["frozenImplementation"]["files"]:
            self.assertEqual(sha256(REPOSITORY_ROOT / record["path"]), record["sha256"])
        shader = self.registration["frozenImplementation"]["productionShader"]
        flake = self.registration["frozenImplementation"]["developmentFlake"]
        self.assertFalse(shader["changed"])
        self.assertFalse(flake["nixStorePathUsed"])
        local_shader = REPOSITORY_ROOT.parent / "shaders" / "frag.glsl"
        local_flake = REPOSITORY_ROOT.parent / "flake.nix"
        if local_shader.is_file():
            self.assertEqual(sha256(local_shader), shader["sha256"])
        if local_flake.is_file():
            self.assertEqual(sha256(local_flake), flake["sha256"])


if __name__ == "__main__":
    unittest.main()
