#!/usr/bin/env python3
"""Integrity tests for the exact FilterOp target-output-blind matrix."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_filter_map_bounds_blind_replay_preregistration.json"
)
RETROSPECTIVE_RESULT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_filter_map_bounds_exact_replay_result.json"
)
EXPECTED_GEOMETRIES = [
    "circle-127-center",
    "circle-128-center",
    "circle-255-center",
    "circle-257-center",
    "circle-511-center",
    "circle-512-center",
    "circle-1023-center",
    "circle-1024-center",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerFilterMapBoundsBlindReplayPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))
        cls.retrospective = json.loads(
            RETROSPECTIVE_RESULT_PATH.read_text(encoding="utf-8")
        )

    def test_registration_is_prospective_and_target_output_blind(self) -> None:
        registration = self.registration
        self.assertEqual(
            registration[
                "prepareLayerFilterMapBoundsBlindReplayPreregistrationSchemaVersion"
            ],
            1,
        )
        self.assertIn("prospective", registration["classification"])
        self.assertIn("target-output-blind", registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])
        self.assertFalse(registration["priorEvidence"]["unchangedBlindRepeatPassed"])
        self.assertFalse(registration["priorEvidence"]["liquidGlassParityEstablished"])

    def test_matrix_is_unseen_by_the_retrospective_filter_replay(self) -> None:
        matrix = self.registration["blindMatrix"]
        geometries = [job["geometry"] for job in matrix["jobs"]]
        self.assertEqual(geometries, EXPECTED_GEOMETRIES)
        self.assertEqual(len(set(geometries)), 8)
        self.assertEqual(matrix["normalSamplesPerJob"], 32)
        self.assertEqual(matrix["targetComponentCount"], 1024)
        retained = set(matrix["retrospectiveFilterReplayGeometries"])
        self.assertTrue(retained.isdisjoint(geometries))
        self.assertTrue(matrix["targetProducerRectanglesUnopenedAtFreeze"])

    def test_candidate_and_acceptance_are_bitwise_not_tolerant(self) -> None:
        candidate = self.registration["frozenCandidate"]
        acceptance = self.registration["acceptance"]
        self.assertEqual(candidate["sourceBoundsSampleIndex"], 32)
        self.assertEqual(candidate["sourceBoundsTransformIndices"], [12, 13])
        self.assertEqual(candidate["sourceBoundsNominalIndices"], [2, 3])
        self.assertFalse(candidate["cropOrProducerValuesUsedForSourceBounds"])
        self.assertFalse(candidate["cropOrProducerValuesUsedForSelection"])
        self.assertTrue(candidate["binary64FMARequired"])
        self.assertFalse(candidate["toleranceUsed"])
        self.assertFalse(candidate["exceptionFitUsed"])
        self.assertEqual(acceptance["jobCount"], 8)
        self.assertEqual(acceptance["exactRectangleCountPerJob"], 32)
        self.assertEqual(acceptance["exactComponentCountPerJob"], 128)
        self.assertEqual(acceptance["maximumULPDistanceAllowed"], 0)
        self.assertEqual(acceptance["maximumAbsoluteErrorAllowed"], 0.0)
        self.assertTrue(acceptance["allEightJobsMustPass"])

    def test_product_authority_remains_sealed(self) -> None:
        authority = self.registration["productAuthority"]
        self.assertFalse(authority["materialAppearanceDirectionTransferMayBeClaimed"])
        self.assertFalse(authority["retina2xAndColorTransferMayBeClaimed"])
        self.assertFalse(authority["independentWalleParityMayBeClaimed"])
        self.assertFalse(authority["productionShaderMayChange"])
        self.assertFalse(authority["liquidGlassParityMayBeClaimed"])

    def test_retrospective_antecedent_is_exact_but_not_blind(self) -> None:
        conclusion = self.retrospective["conclusion"]
        prior = self.registration["priorEvidence"]
        self.assertTrue(conclusion["archivedHoldoutFloatingReplayExact"])
        self.assertEqual(conclusion["archivedHoldoutFloatingRectangleCount"], 256)
        self.assertEqual(conclusion["archivedHoldoutFloatingComponentCount"], 1024)
        self.assertFalse(conclusion["unchangedBlindRepeatPassed"])
        self.assertEqual(sha256(RETROSPECTIVE_RESULT_PATH), prior["resultSHA256"])

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
