#!/usr/bin/env python3
"""Integrity checks for the small-geometry Filter/SDF diagnostic."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_filter_sdf_small_geometry_preregistration.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerFilterSDFSmallGeometryPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_failure_is_preserved_without_a_transfer_claim(self) -> None:
        registration = self.registration
        self.assertEqual(
            registration[
                "prepareLayerFilterSDFSmallGeometryPreregistrationSchemaVersion"
            ],
            1,
        )
        failure = registration["openedFailureEvidence"]
        self.assertEqual(failure["runID"], 31082481844)
        self.assertEqual(
            failure["observedRecursiveChildF64"], [0.0, 0.0, 293.0, 293.0]
        )
        self.assertTrue(failure["constant280GeometryRuleFalsified"])
        self.assertFalse(failure["regularUnseenGeometryTransferPassed"])

    def test_selector_is_structural_and_unchanged(self) -> None:
        profile = self.registration["diagnosticProfile"]
        self.assertEqual(profile["geometry"], "circle-127-center")
        self.assertEqual(profile["selectedSampleIndex"], 2)
        self.assertEqual(profile["selectedMarkerInterval"], 2)
        self.assertEqual(profile["selectedQualifiedHelperOrdinal"], 14)
        self.assertEqual(profile["filterDispatchOrdinal"], 4)
        self.assertEqual(profile["sdfDispatchOrdinal"], 2)
        self.assertFalse(profile["selectorChangedFromAcceptedCircle800Diagnostics"])
        self.assertFalse(profile["cropOrOutputValuesUsedForSelection"])

    def test_diagnostic_does_not_freeze_an_output_candidate(self) -> None:
        questions = self.registration["frozenQuestions"]
        self.assertTrue(
            questions["extractExactFilterSourceDODFromLiveInstructionState"]
        )
        self.assertTrue(
            questions["distinguishSourceDODFromShadowUnionAndRecursiveChildClip"]
        )
        self.assertFalse(questions["acceptAnyNumericSourceDODBeforeCapture"])
        self.assertFalse(questions["acceptAnyNumericSDFRadiusBeforeCapture"])
        self.assertFalse(questions["acceptAnyCropOrProducerTolerance"])
        self.assertIsNone(self.registration["runtimeOutcomeFrozenBeforeDispatch"])

    def test_product_authority_remains_closed(self) -> None:
        acceptance = self.registration["acceptance"]
        authority = self.registration["productAuthority"]
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
