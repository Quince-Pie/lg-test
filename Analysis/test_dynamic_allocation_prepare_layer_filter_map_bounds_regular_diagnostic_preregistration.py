#!/usr/bin/env python3
"""Integrity tests for the prospective regular FilterOp diagnostic."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_filter_map_bounds_regular_diagnostic_preregistration.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerFilterMapBoundsRegularDiagnosticPreregistrationTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_registration_is_prospective_and_output_blind(self) -> None:
        registration = self.registration
        self.assertEqual(
            registration[
                "prepareLayerFilterMapBoundsRegularDiagnosticPreregistrationSchemaVersion"
            ],
            1,
        )
        self.assertIn("prospective", registration["classification"])
        self.assertIn("output-blind", registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])

    def test_prior_failure_is_preserved_without_overclaim(self) -> None:
        prior = self.registration["priorEvidence"]
        self.assertEqual(prior["profileTransferRunID"], 31074006001)
        self.assertEqual(prior["profileTransferWorkflowConclusion"], "failure")
        self.assertEqual(prior["regularProfileOldReplayExactRectangleCount"], 0)
        self.assertEqual(prior["regularProfileOldReplayRectangleCount"], 128)
        self.assertEqual(
            prior["centeredRecursiveSourceCandidateExactRectangleCount"], 0
        )
        self.assertTrue(prior["mereSourceBoundSubstitutionFalsified"])
        self.assertFalse(prior["completeProfileMatrixPassed"])
        self.assertFalse(prior["liquidGlassParityEstablished"])

    def test_selector_and_identity_are_frozen(self) -> None:
        diagnostic = self.registration["frozenDiagnostic"]
        self.assertEqual(
            (
                diagnostic["material"],
                diagnostic["appearance"],
                diagnostic["direction"],
                diagnostic["geometry"],
            ),
            ("regular", "light", "materialize", "circle-800-center"),
        )
        self.assertEqual(diagnostic["selectedSampleIndex"], 2)
        self.assertEqual(diagnostic["selectedMarkerInterval"], 2)
        self.assertEqual(diagnostic["selectedQualifiedHelperOrdinal"], 14)
        self.assertEqual(diagnostic["dynamicDispatchOffset"], 0x2864)
        self.assertEqual(diagnostic["dynamicDispatchOrdinal"], 4)
        self.assertEqual(diagnostic["producerStoreIndexDelta"], 2)
        self.assertEqual(diagnostic["producerRoleDelta"], 0xFB0)
        self.assertEqual(diagnostic["producerDepthDelta"], 2)
        self.assertFalse(diagnostic["captureAdapterReadsCropOrOutputForSelection"])
        self.assertFalse(diagnostic["validatorChangesFilterInstructionValidation"])

    def test_acceptance_requires_bitwise_structural_correlation(self) -> None:
        acceptance = self.registration["acceptance"]
        self.assertTrue(acceptance["zeroCaptureFailuresRequired"])
        self.assertTrue(acceptance["completeFilterInstructionTraceRequired"])
        self.assertTrue(acceptance["allOpenedScopeCodeHashesMustMatch"])
        self.assertTrue(
            acceptance["filterReturnMustMatchStructuralProducerBitForBit"]
        )
        self.assertEqual(
            acceptance["changedProducerQwordOffsetsMustEqual"], [0, 8, 16, 24]
        )
        self.assertFalse(acceptance["regularMaterialArithmeticMayBeClaimed"])
        self.assertFalse(acceptance["completeProfileTransferMayBeClaimed"])
        self.assertFalse(acceptance["liquidGlassParityMayBeClaimed"])

    def test_product_authority_stays_closed(self) -> None:
        authority = self.registration["productAuthority"]
        self.assertFalse(
            authority["completeFilterOpCropProfileTransferMayBeClaimed"]
        )
        self.assertFalse(authority["opticalMaterialAppearanceTransferMayBeClaimed"])
        self.assertFalse(authority["retina2xAndColorTransferMayBeClaimed"])
        self.assertFalse(authority["independentWalleParityMayBeClaimed"])
        self.assertFalse(authority["productionShaderMayChange"])
        self.assertFalse(authority["liquidGlassParityMayBeClaimed"])

    def test_frozen_implementation_hashes_match(self) -> None:
        for record in self.registration["frozenImplementation"]["files"]:
            self.assertEqual(sha256(REPOSITORY_ROOT / record["path"]), record["sha256"])
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
