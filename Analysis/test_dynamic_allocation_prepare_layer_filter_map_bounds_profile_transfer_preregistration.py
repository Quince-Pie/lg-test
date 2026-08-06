#!/usr/bin/env python3
"""Integrity tests for the exact FilterOp profile-transfer matrix."""

from __future__ import annotations

import hashlib
import json
import unittest
from itertools import product
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_filter_map_bounds_profile_transfer_preregistration.json"
)
BLIND_RESULT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_filter_map_bounds_blind_replay_result.json"
)
EXPECTED_PROFILES = {
    (material, appearance, direction)
    for material, appearance, direction in product(
        ("clear", "regular"),
        ("light", "dark"),
        ("materialize", "dematerialize"),
    )
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerFilterMapBoundsProfileTransferPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))
        cls.blind_result = json.loads(BLIND_RESULT_PATH.read_text(encoding="utf-8"))

    def test_registration_is_prospective_and_output_blind(self) -> None:
        registration = self.registration
        self.assertEqual(
            registration[
                "prepareLayerFilterMapBoundsProfileTransferPreregistrationSchemaVersion"
            ],
            1,
        )
        self.assertIn("prospective", registration["classification"])
        self.assertIn("target-output-blind", registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])
        self.assertFalse(registration["priorEvidence"]["profileMatrixPassed"])
        self.assertFalse(registration["priorEvidence"]["liquidGlassParityEstablished"])

    def test_matrix_contains_the_complete_cartesian_profile_domain(self) -> None:
        matrix = self.registration["profileMatrix"]
        observed = {
            (job["material"], job["appearance"], job["direction"])
            for job in matrix["jobs"]
        }
        self.assertEqual(observed, EXPECTED_PROFILES)
        self.assertEqual(len(matrix["jobs"]), 8)
        self.assertEqual(matrix["geometry"], "circle-800-center")
        self.assertEqual(matrix["normalSamplesPerJob"], 32)
        self.assertEqual(matrix["targetComponentCount"], 1024)
        self.assertTrue(matrix["targetProducerRectanglesUnopenedAtFreeze"])

    def test_direction_adapter_removes_only_the_preexisting_guard(self) -> None:
        amendment = self.registration["directionHarnessAmendment"]
        self.assertEqual(
            amendment["sourceSHA256"],
            "c4398a9ae82d8bddd22038c228989dc6398e9ba790e7c5451a555e9ecd265518",
        )
        self.assertEqual(
            amendment["transformedSHA256"],
            "247ad3094bec2c82244d02c5cff6815805c56bdafb59a57c6b24109009480ede",
        )
        self.assertEqual(amendment["removedGuardCount"], 1)
        self.assertEqual(amendment["changedPrivateBreakpointCount"], 0)
        self.assertEqual(amendment["changedMemoryReadCount"], 0)
        self.assertEqual(amendment["changedCropSelectorCount"], 0)
        self.assertFalse(amendment["scientificCandidateChanged"])

    def test_candidate_and_acceptance_remain_bitwise(self) -> None:
        candidate = self.registration["frozenCandidate"]
        acceptance = self.registration["acceptance"]
        self.assertEqual(candidate["sourceBoundsSampleIndex"], 32)
        self.assertEqual(candidate["sourceBoundsTransformIndices"], [12, 13])
        self.assertEqual(candidate["sourceBoundsNominalIndices"], [2, 3])
        self.assertTrue(candidate["binary64FMARequired"])
        self.assertFalse(candidate["toleranceUsed"])
        self.assertFalse(candidate["exceptionFitUsed"])
        self.assertEqual(acceptance["jobCount"], 8)
        self.assertEqual(acceptance["exactRectangleCountPerJob"], 32)
        self.assertEqual(acceptance["exactComponentCountPerJob"], 128)
        self.assertEqual(acceptance["maximumULPDistanceAllowed"], 0)
        self.assertEqual(acceptance["maximumAbsoluteErrorAllowed"], 0.0)
        self.assertTrue(acceptance["allEightJobsMustPass"])

    def test_prior_blind_result_is_authenticated(self) -> None:
        prior = self.registration["priorEvidence"]
        conclusion = self.blind_result["conclusion"]
        self.assertEqual(sha256(BLIND_RESULT_PATH), prior["blindResultSHA256"])
        self.assertTrue(conclusion["unchangedBlindRepeatPassed"])
        self.assertTrue(
            conclusion["clearLightMaterializeOneXGeometryCropTransferPassed"]
        )
        self.assertFalse(conclusion["materialAppearanceDirectionTransferPassed"])

    def test_product_authority_stays_closed_beyond_filterop_crop_transfer(self) -> None:
        authority = self.registration["productAuthority"]
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
