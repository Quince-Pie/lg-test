#!/usr/bin/env python3
"""Integrity checks for the small-geometry helper-code preregistration."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_small_geometry_helper_code_preregistration.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class SmallGeometryHelperCodePreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_antecedent_exact_decode_is_preserved_without_transfer(self) -> None:
        antecedent = self.registration["antecedent"]
        self.assertEqual(antecedent["runID"], 31084256909)
        self.assertTrue(antecedent["selectedSDFReplayExact"])
        self.assertTrue(antecedent["selectedFilterReplayExact"])
        self.assertTrue(antecedent["formerVerticalResidualExplainedExactly"])
        self.assertFalse(antecedent["generalHelperSemanticsDecoded"])
        self.assertFalse(antecedent["regularUnseenGeometryTransferPassed"])

    def test_code_and_semantics_are_unknown_before_capture(self) -> None:
        for target in self.registration["targets"]:
            self.assertIsNone(target["expectedCodeSHA256"])
            self.assertIsNone(target["semanticOutputAcceptedBeforeCapture"])
        self.assertIsNone(self.registration["runtimeOutcomeFrozenBeforeDispatch"])
        contract = self.registration["captureContract"]
        self.assertTrue(contract["staticMemoryReadsOnly"])
        self.assertEqual(contract["breakpointsAdded"], 0)
        self.assertEqual(contract["instructionStepsAdded"], 0)
        self.assertFalse(contract["codeHashAcceptedBeforeCapture"])
        self.assertFalse(contract["rectangleOrProducerCandidateAcceptedBeforeCapture"])

    def test_inherited_structural_selector_is_unchanged(self) -> None:
        profile = self.registration["frozenProfile"]
        self.assertEqual(profile["geometry"], "circle-127-center")
        self.assertEqual(profile["selectedSampleIndex"], 2)
        self.assertEqual(profile["selectedMarkerInterval"], 2)
        self.assertEqual(profile["selectedQualifiedHelperOrdinal"], 14)
        self.assertEqual(profile["filterDispatchOrdinal"], 4)
        self.assertEqual(profile["sdfDispatchOrdinal"], 2)
        self.assertFalse(profile["selectorChangedFromRun31084256909"])
        self.assertFalse(profile["cropOrOutputValuesUsedForSelection"])

    def test_product_authority_remains_closed(self) -> None:
        acceptance = self.registration["acceptance"]
        authority = self.registration["productAuthority"]
        self.assertTrue(acceptance["helperCodeOpeningMayBeClaimed"])
        self.assertFalse(acceptance["helperGeneralSemanticsMayBeClaimed"])
        self.assertFalse(acceptance["regularGeometryTransferMayBeClaimed"])
        self.assertFalse(acceptance["productionShaderMayChange"])
        self.assertFalse(authority["completeRegularCropLawMayBeClaimed"])
        self.assertFalse(authority["liquidGlassParityMayBeClaimed"])

    def test_frozen_implementation_hashes_match(self) -> None:
        for record in self.registration["frozenImplementation"]["files"]:
            self.assertEqual(
                sha256(REPOSITORY_ROOT / record["path"]), record["sha256"]
            )
        shader = self.registration["frozenImplementation"]["productionShader"]
        self.assertEqual(
            shader["sha256"],
            "6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d",
        )
        local_shader = REPOSITORY_ROOT.parent / "shaders" / "frag.glsl"
        if local_shader.is_file():
            self.assertEqual(sha256(local_shader), shader["sha256"])


if __name__ == "__main__":
    unittest.main()
