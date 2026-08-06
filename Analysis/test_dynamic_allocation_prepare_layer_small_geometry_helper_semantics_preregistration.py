#!/usr/bin/env python3
"""Integrity checks for the helper-semantics preregistration."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_small_geometry_helper_semantics_preregistration.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class SmallGeometryHelperSemanticsPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_capture_is_prospective_and_output_blind(self) -> None:
        registration = self.registration
        self.assertEqual(
            registration[
                "prepareLayerSmallGeometryHelperSemanticsPreregistrationSchemaVersion"
            ],
            1,
        )
        for token in ("prospective", "output-blind", "unknown"):
            self.assertIn(token, registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])

    def test_accepted_code_is_the_only_target_antecedent(self) -> None:
        antecedent = self.registration["antecedent"]
        self.assertEqual(antecedent["runID"], 31087074253)
        self.assertTrue(antecedent["helperCodeOpeningPassed"])
        self.assertTrue(antecedent["gaussianSymbolicControlFlowDecoded"])
        self.assertTrue(antecedent["backdropWrapperSemanticsDecoded"])
        self.assertFalse(antecedent["gaussianGeneralNumericLawDecoded"])
        self.assertFalse(antecedent["backdropAllocationGeneralLawDecoded"])
        self.assertEqual(
            sha256(REPOSITORY_ROOT / antecedent["analysis"]),
            antecedent["analysisSHA256"],
        )

    def test_no_gaussian_value_is_accepted(self) -> None:
        target = self.registration["gaussianTarget"]
        self.assertFalse(target["valuesAcceptedBeforeCapture"])
        self.assertIsNone(target["globalModeFlag"]["expectedValue"])
        self.assertEqual(len(target["binary64DataWords"]), 8)
        for word in target["binary64DataWords"]:
            self.assertIsNone(word["expectedValue"])

    def test_delegated_code_is_bounded_but_unknown(self) -> None:
        target = self.registration["delegatedBackdropTarget"]
        self.assertEqual(target["relativeToPrepareLayer"], 364696)
        self.assertEqual(target["maximumSymbolByteCountInclusive"], 65536)
        self.assertIsNone(target["symbolByteCount"])
        self.assertIsNone(target["expectedCodeSHA256"])
        self.assertIsNone(target["semanticOutputAcceptedBeforeCapture"])

    def test_capture_adds_no_dynamic_or_value_selected_mechanism(self) -> None:
        contract = self.registration["captureContract"]
        self.assertTrue(contract["staticMemoryReadsOnly"])
        self.assertEqual(contract["breakpointsAdded"], 0)
        self.assertEqual(contract["instructionStepsAdded"], 0)
        for field in (
            "constantValueAcceptedBeforeCapture",
            "globalModeFlagAcceptedBeforeCapture",
            "delegatedCodeHashAcceptedBeforeCapture",
            "delegatedSymbolSizeAcceptedBeforeCapture",
            "cropOrOutputValueUsedForSelection",
            "inheritedFilterAndSDFCaptureChanged",
            "validatorSemanticChecksChanged",
        ):
            self.assertFalse(contract[field], field)

    def test_product_authority_remains_closed(self) -> None:
        acceptance = self.registration["acceptance"]
        authority = self.registration["productAuthority"]
        self.assertTrue(acceptance["gaussianDataOpeningMayBeClaimed"])
        self.assertTrue(acceptance["delegatedBackdropCodeOpeningMayBeClaimed"])
        self.assertFalse(acceptance["gaussianGeneralSemanticsMayBeClaimed"])
        self.assertFalse(acceptance["regularGeometryTransferMayBeClaimed"])
        self.assertFalse(authority["productionShaderMayChange"])
        self.assertFalse(authority["liquidGlassParityMayBeClaimed"])

    def test_frozen_implementation_hashes_match(self) -> None:
        for record in self.registration["frozenImplementation"]["files"]:
            self.assertEqual(sha256(REPOSITORY_ROOT / record["path"]), record["sha256"])
        shader = self.registration["frozenImplementation"]["productionShader"]
        local_shader = REPOSITORY_ROOT.parent / "shaders" / "frag.glsl"
        self.assertFalse(shader["changed"])
        if local_shader.is_file():
            self.assertEqual(sha256(local_shader), shader["sha256"])


if __name__ == "__main__":
    unittest.main()
