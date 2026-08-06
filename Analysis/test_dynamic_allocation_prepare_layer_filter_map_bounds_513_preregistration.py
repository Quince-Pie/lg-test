#!/usr/bin/env python3
"""Integrity checks for the 513-point FilterOp diagnostic transfer."""

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_filter_map_bounds_513_preregistration.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerFilterMapBounds513PreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_transfer_is_diagnostic_not_a_blind_repeat(self) -> None:
        registration = self.registration
        self.assertEqual(
            registration[
                "prepareLayerFilterMapBounds513PreregistrationSchemaVersion"
            ],
            1,
        )
        self.assertIn("retrospective diagnostic", registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])
        target = registration["diagnosticTarget"]
        self.assertEqual(target["geometry"], "circle-513-center")
        self.assertTrue(target["geometryChoiceUsedPriorObservedResiduals"])
        self.assertFalse(target["cropOrOutputValuesUsedForInRunSelection"])

    def test_successful_1025_capture_is_the_antecedent(self) -> None:
        antecedent = self.registration["antecedent"]
        self.assertEqual(antecedent["runID"], 31070080768)
        self.assertEqual(antecedent["conclusion"], "success")
        self.assertTrue(antecedent["filterReturnMatchesProducerBitForBit"])
        self.assertFalse(antecedent["exactCrossCorpusReplayEstablished"])
        self.assertFalse(antecedent["liquidGlassParityEstablished"])

    def test_filter_identity_and_capture_are_unchanged(self) -> None:
        target = self.registration["diagnosticTarget"]
        self.assertEqual(target["targetDispatchOrdinal"], 4)
        self.assertEqual(target["filterRelativeToPrepareLayer"], -61056)
        self.assertEqual(target["filterSymbolByteCount"], 788)
        capture = self.registration["captureInvariants"]
        self.assertFalse(capture["captureImplementationChangedFromSuccessful1025Run"])
        self.assertFalse(capture["validatorImplementationChangedFromSuccessful1025Run"])
        self.assertTrue(capture["selectionRemainsStructuralAndOutputBlindWithinRun"])

    def test_diagnostic_cannot_claim_parity(self) -> None:
        acceptance = self.registration["acceptance"]
        self.assertTrue(acceptance["diagnosticMayAuthorizeArithmeticDecoderRefinement"])
        for key in (
            "unchangedBlindRepeatMayBeClaimed",
            "allCropHoldoutsMayBeClaimed",
            "materialAppearanceDirectionTransferMayBeClaimed",
            "retina2xAndColorTransferMayBeClaimed",
            "independentWalleZeroByteParityMayBeClaimed",
            "productionShaderMayChange",
            "liquidGlassParityMayBeClaimed",
        ):
            self.assertFalse(acceptance[key], key)

    def test_frozen_file_hashes_match(self) -> None:
        for record in self.registration["frozenImplementation"]["files"]:
            self.assertEqual(sha256(REPOSITORY_ROOT / record["path"]), record["sha256"])
        shader = self.registration["frozenImplementation"]["productionShader"]
        self.assertFalse(shader["changed"])
        local_shader = REPOSITORY_ROOT.parent / "shaders" / "frag.glsl"
        if local_shader.is_file():
            self.assertEqual(sha256(local_shader), shader["sha256"])


if __name__ == "__main__":
    unittest.main()
