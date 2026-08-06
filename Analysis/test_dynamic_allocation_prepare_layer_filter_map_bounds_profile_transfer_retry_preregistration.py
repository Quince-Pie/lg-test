#!/usr/bin/env python3
"""Integrity tests for the exact FilterOp profile-transfer retry."""

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
    / "dynamic_allocation_prepare_layer_filter_map_bounds_profile_transfer_retry_preregistration.json"
)
REANALYSIS_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_filter_map_bounds_profile_transfer_reanalysis_result.json"
)
EXPECTED_PROFILES = set(
    product(
        ("clear", "regular"),
        ("light", "dark"),
        ("materialize", "dematerialize"),
    )
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerFilterMapBoundsProfileTransferRetryPreregistrationTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))
        cls.reanalysis = json.loads(REANALYSIS_PATH.read_text(encoding="utf-8"))

    def test_registration_is_prospective_and_output_blind(self) -> None:
        registration = self.registration
        self.assertEqual(
            registration[
                "prepareLayerFilterMapBoundsProfileTransferRetryPreregistrationSchemaVersion"
            ],
            1,
        )
        self.assertIn("prospective", registration["classification"])
        self.assertIn("target-output-blind", registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])
        prior = registration["priorEvidence"]
        self.assertTrue(prior["targetOutputsOpenedBeforeCandidateFreeze"])
        self.assertFalse(prior["prospectiveUnchangedRepeatPassed"])
        self.assertFalse(prior["filterOpCropProfileTransferPassed"])

    def test_retrospective_evidence_is_authenticated_without_promoting_it(self) -> None:
        prior = self.registration["priorEvidence"]
        conclusion = self.reanalysis["conclusion"]
        self.assertEqual(sha256(REANALYSIS_PATH), prior["reanalysisResultSHA256"])
        self.assertTrue(conclusion["archivedCompleteProfileMatrixReplaysBitForBit"])
        self.assertFalse(conclusion["prospectiveUnchangedRepeatPassed"])
        self.assertFalse(conclusion["filterOpCropProfileTransferPassed"])

    def test_complete_cartesian_matrix_and_aggregate_are_frozen(self) -> None:
        matrix = self.registration["profileMatrix"]
        observed = {
            (job["material"], job["appearance"], job["direction"])
            for job in matrix["jobs"]
        }
        self.assertEqual(observed, EXPECTED_PROFILES)
        self.assertEqual(matrix["jobCount"], 8)
        self.assertEqual(matrix["normalSamplesPerJob"], 32)
        self.assertEqual(matrix["targetRectangleCount"], 256)
        self.assertEqual(matrix["targetComponentCount"], 1024)
        self.assertEqual(matrix["targetSDFStateRecordCount"], 256)
        self.assertEqual(matrix["targetEndpointYOffsetAppliedRecordCount"], 4)
        self.assertTrue(matrix["targetProducerRectanglesUnopenedAtFreeze"])

        acceptance = self.registration["acceptance"]
        self.assertTrue(acceptance["aggregateJobRequired"])
        self.assertTrue(acceptance["allEightJobsAndAggregateMustPass"])
        self.assertEqual(acceptance["maximumULPDistanceAllowed"], 0)
        self.assertEqual(acceptance["maximumAbsoluteErrorAllowed"], 0.0)

    def test_structural_selectors_and_exact_arithmetic_are_frozen(self) -> None:
        candidate = self.registration["frozenCandidate"]
        self.assertEqual(
            candidate["producerSelector"]["storeIndexDeltaFromPointerCorrelatedMirror"],
            -2,
        )
        self.assertFalse(
            candidate["producerSelector"]["cropOrProducerValuesUsedForSelection"]
        )
        self.assertEqual(
            candidate["sdfStateSelector"]["storeIndexDeltaFromPointerCorrelatedMirror"],
            -1,
        )
        self.assertEqual(candidate["sdfStateSelector"]["parametersRoleOffset"], 0x7F0)
        self.assertFalse(
            candidate["sdfStateSelector"]["cropOrProducerValuesUsedForSelection"]
        )
        self.assertEqual(
            candidate["clear"]["sdfParametersHex"],
            "00001041000000000000000000000000",
        )
        self.assertEqual(
            candidate["regular"]["sdfParametersHex"],
            "04db2942000000000000000000000000",
        )
        self.assertEqual(
            candidate["regular"]["sourceBoundsF64"],
            [-280.0, -280.0, 1360.0, 1360.0],
        )
        self.assertTrue(candidate["binary64FMARequired"])
        self.assertFalse(candidate["toleranceUsed"])
        self.assertFalse(candidate["exceptionFitUsed"])

    def test_product_authority_stays_closed_beyond_crop_transfer(self) -> None:
        authority = self.registration["productAuthority"]
        self.assertTrue(
            authority["filterOpCropProfileTransferMayBeClaimedOnExactAggregatePass"]
        )
        self.assertFalse(authority["regularUnseenGeometryTransferMayBeClaimed"])
        self.assertFalse(authority["independentPrivateInputGenerationMayBeClaimed"])
        self.assertFalse(
            authority["opticalMaterialAppearanceDirectionTransferMayBeClaimed"]
        )
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
