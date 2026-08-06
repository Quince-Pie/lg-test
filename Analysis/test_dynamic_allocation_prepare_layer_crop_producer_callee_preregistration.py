#!/usr/bin/env python3
"""Integrity tests for the post-mask crop-producer callee preregistration."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_crop_producer_callee_preregistration.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerCropProducerCalleePreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_gate_is_prospective_and_has_no_runtime_outcome(self) -> None:
        registration = self.registration
        self.assertEqual(
            registration["prepareLayerCropProducerCalleePreregistrationSchemaVersion"],
            1,
        )
        self.assertIn("prospective output-blind", registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])

    def test_antecedent_helper_ownership_failure_is_immutable(self) -> None:
        antecedent = self.registration["antecedents"]["selectedHelperResult"]
        path = REPOSITORY_ROOT / antecedent["path"]
        self.assertEqual(antecedent["runID"], 31065907932)
        self.assertEqual(antecedent["qualifiedHelperOrdinal"], 14)
        self.assertTrue(antecedent["structuralRoleMappingPassed"])
        self.assertFalse(antecedent["prepareLayerMaskFirstRectangleOwner"])
        self.assertEqual(sha256(path), antecedent["sha256"])

    def test_static_target_is_fixed_without_callee_identity_or_output(self) -> None:
        target = self.registration["fixedStructuralTarget"]
        self.assertEqual(target["callerContinuationStartOffset"], 0xD94)
        self.assertEqual(target["calleeCallOffset"], 0xF5C)
        self.assertEqual(target["calleeReturnOffset"], 0xF60)
        self.assertEqual(target["calleeEntryRelativeToPrepareLayer"], -1_206_100)
        self.assertEqual(target["calleeCallRawLittleEndianHex"], "5462fb97")
        self.assertFalse(target["calleeIdentityKnownBeforeDispatch"])
        self.assertFalse(target["calleeCodeSHA256KnownBeforeDispatch"])
        self.assertFalse(target["calleeReturnBytesKnownBeforeDispatch"])
        self.assertFalse(target["selectionMayChangeAfterDispatch"])

    def test_capture_is_bounded_complete_and_output_blind(self) -> None:
        capture = self.registration["captureInvariants"]
        self.assertFalse(capture["newBreakpointAdded"])
        self.assertFalse(capture["hardwareWatchpointUsed"])
        self.assertFalse(capture["cropOrOutputValuesUsedForSelection"])
        self.assertTrue(
            capture["completeScalarAndSIMDRegistersBeforeAndAfterEachInstruction"]
        )
        self.assertTrue(capture["completeResolvedCalleeSymbolCodeRequired"])
        self.assertTrue(capture["everyOtherCalleeMustBeAnExplicitStepOutBoundary"])
        self.assertGreater(capture["maximumCalleeInstructionCount"], 0)

    def test_first_run_can_open_ownership_but_no_semantic_or_product_claim(
        self,
    ) -> None:
        acceptance = self.registration["acceptance"]
        self.assertTrue(
            acceptance["firstRunMayEstablishCalleeIdentityAndOwnershipOnly"]
        )
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
        self.assertFalse(shader["changed"])
        local_shader = REPOSITORY_ROOT.parent / "shaders" / "frag.glsl"
        if local_shader.is_file():
            self.assertEqual(sha256(local_shader), shader["sha256"])
        flake = self.registration["frozenImplementation"]["developmentFlake"]
        local_flake = REPOSITORY_ROOT.parent / "flake.nix"
        self.assertFalse(flake["nixStorePathUsed"])
        if local_flake.is_file():
            self.assertEqual(sha256(local_flake), flake["sha256"])


if __name__ == "__main__":
    unittest.main()
