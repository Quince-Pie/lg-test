#!/usr/bin/env python3
"""Integrity checks for the prospective FilterOp map-bounds gate."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_filter_map_bounds_preregistration.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerFilterMapBoundsPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_gate_is_prospective_and_has_no_runtime_outcome(self) -> None:
        registration = self.registration
        self.assertEqual(
            registration["prepareLayerFilterMapBoundsPreregistrationSchemaVersion"],
            1,
        )
        self.assertIn("prospective output-blind", registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])

    def test_opened_retry_falsification_and_owner_are_immutable(self) -> None:
        antecedent = self.registration["antecedents"]["callbackRetryResult"]
        self.assertEqual(antecedent["runID"], 31068498526)
        self.assertTrue(antecedent["callbackTransportRepaired"])
        self.assertTrue(antecedent["staticPlusF5CCalleeHypothesisFalsified"])
        self.assertTrue(antecedent["filterMapBoundsFloatingProducerOwner"])
        self.assertFalse(antecedent["exactInternalArithmeticDecoded"])
        self.assertEqual(
            sha256(REPOSITORY_ROOT / antecedent["path"]), antecedent["sha256"]
        )

    def test_target_is_the_fourth_exact_dynamic_dispatch(self) -> None:
        target = self.registration["fixedStructuralTarget"]
        self.assertEqual(target["callerContinuationStartOffset"], 0xD94)
        self.assertEqual(target["dynamicCallOffset"], 0x2864)
        self.assertEqual(target["dynamicReturnOffset"], 0x2868)
        self.assertEqual(target["dynamicCallRawLittleEndianHex"], "10093fd7")
        self.assertEqual(target["targetDispatchOrdinal"], 4)
        self.assertEqual(target["filterRelativeToPrepareLayer"], -61056)
        self.assertEqual(target["filterSymbolByteCount"], 788)
        self.assertEqual(
            target["filterCodeSHA256"],
            "e8766dcefdadc0074f7bb4e2bf62955072891858009dca6c72a7eef1c96789d0",
        )
        scopes = target["openedArithmeticScopes"]
        self.assertEqual(len(scopes), 7)
        self.assertEqual(
            {scope["name"] for scope in scopes},
            {
                "rectApplyTransform",
                "rectUnapplyTransform",
                "glassBackgroundDOD",
                "filterApplyDOD",
                "filterApply",
                "filterMapBounds",
                "unionBounds",
            },
        )
        by_name = {scope["name"]: scope for scope in scopes}
        self.assertEqual(by_name["unionBounds"]["relativeToPrepareLayer"], -2720)
        self.assertEqual(
            by_name["glassBackgroundDOD"]["relativeToPrepareLayer"], -90584
        )
        self.assertFalse(target["cropOrOutputValuesUsedForSelection"])

    def test_capture_is_complete_bounded_and_output_blind(self) -> None:
        capture = self.registration["captureInvariants"]
        self.assertFalse(capture["newBreakpointAdded"])
        self.assertFalse(capture["hardwareWatchpointUsed"])
        self.assertFalse(capture["cropOrOutputValuesUsedForSelection"])
        self.assertTrue(
            capture["completeScalarAndSIMDRegistersBeforeAndAfterEachInstruction"]
        )
        self.assertTrue(capture["completeFilterSymbolCodeRequired"])
        self.assertTrue(capture["allPreviouslyHashedArithmeticScopesOpened"])
        self.assertTrue(capture["everyOtherCalleeMustBeAnExplicitStepOutBoundary"])

    def test_first_pass_cannot_claim_semantics_or_product_parity(self) -> None:
        acceptance = self.registration["acceptance"]
        self.assertTrue(acceptance["filterReturnMustMatchProducerBitForBit"])
        for key in (
            "exactFilterSemanticsMayBeClaimed",
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
        self.assertFalse(flake["nixStorePathUsed"])
        local_flake = REPOSITORY_ROOT.parent / "flake.nix"
        if local_flake.is_file():
            self.assertEqual(sha256(local_flake), flake["sha256"])


if __name__ == "__main__":
    unittest.main()
