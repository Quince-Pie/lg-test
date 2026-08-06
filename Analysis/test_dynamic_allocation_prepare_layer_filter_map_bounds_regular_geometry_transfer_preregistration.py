#!/usr/bin/env python3
"""Integrity tests for the regular geometry/profile Cartesian preregistration."""

from __future__ import annotations

import hashlib
import json
import unittest
from itertools import product
from pathlib import Path

import validate_prepare_layer_filter_map_bounds_regular_geometry_transfer as regular


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_filter_map_bounds_regular_geometry_transfer_preregistration.json"
)
PROFILE_RESULT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_filter_map_bounds_profile_transfer_retry_result.json"
)
CLEAR_GEOMETRY_RESULT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_filter_map_bounds_blind_replay_result.json"
)
EXPECTED_CASES = set(
    product(
        regular.EXPECTED_GEOMETRY_WIDTHS,
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


class PrepareLayerFilterMapBoundsRegularGeometryTransferPreregistrationTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_registration_is_prospective_and_target_output_blind(self) -> None:
        registration = self.registration
        self.assertEqual(
            registration[
                "prepareLayerFilterMapBoundsRegularGeometryTransferPreregistrationSchemaVersion"
            ],
            1,
        )
        self.assertIn("prospective", registration["classification"])
        self.assertIn("target-output-blind", registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])
        self.assertFalse(
            registration["frozenCandidate"][
                "geometryOrProducerOutputUsedToFitSourceRule"
            ]
        )

    def test_antecedent_profile_and_clear_geometry_results_are_authenticated(
        self,
    ) -> None:
        evidence = self.registration["priorEvidence"]
        self.assertEqual(
            sha256(PROFILE_RESULT_PATH), evidence["profileTransferResultSHA256"]
        )
        self.assertEqual(
            sha256(CLEAR_GEOMETRY_RESULT_PATH),
            evidence["clearGeometryBlindReplayResultSHA256"],
        )
        self.assertTrue(evidence["fixedGeometryProfileTransferPassed"])
        self.assertTrue(evidence["clearUnseenGeometryTransferPassed"])
        self.assertFalse(evidence["regularUnseenGeometryTransferPassed"])

    def test_complete_regular_geometry_profile_cartesian_product_is_frozen(
        self,
    ) -> None:
        matrix = self.registration["cartesianMatrix"]
        observed = {
            (case["geometry"], case["appearance"], case["direction"])
            for case in matrix["cases"]
        }
        self.assertEqual(observed, EXPECTED_CASES)
        self.assertEqual(matrix["geometryCount"], 8)
        self.assertEqual(matrix["profilePerGeometryCount"], 4)
        self.assertEqual(matrix["jobCount"], 32)
        self.assertEqual(matrix["targetRectangleCount"], 1024)
        self.assertEqual(matrix["targetComponentCount"], 4096)
        self.assertEqual(matrix["targetSDFStateRecordCount"], 1024)
        self.assertEqual(matrix["targetEndpointBranchRecordCount"], 32)
        self.assertTrue(matrix["allRegularProducerTargetsUnopenedAtFreeze"])

    def test_source_dod_and_zero_tolerance_acceptance_are_exact(self) -> None:
        candidate = self.registration["frozenCandidate"]
        self.assertEqual(candidate["sourceExpansionPerEdgeF64"], 280.0)
        self.assertEqual(
            candidate["sourceBoundsRule"],
            "[-280, -280, geometryWidth + 560, geometryWidth + 560]",
        )
        self.assertEqual(
            candidate["recursiveChildRule"],
            "[0, 0, geometryWidth + 560, geometryWidth + 560]",
        )
        self.assertEqual(
            candidate["sdfParametersHex"],
            "04db2942000000000000000000000000",
        )
        self.assertTrue(candidate["binary64FMARequired"])
        self.assertFalse(candidate["toleranceUsed"])
        self.assertFalse(candidate["exceptionFitUsed"])

        acceptance = self.registration["acceptance"]
        self.assertEqual(acceptance["maximumULPDistanceAllowed"], 0)
        self.assertEqual(acceptance["maximumAbsoluteErrorAllowed"], 0.0)
        self.assertTrue(acceptance["all32JobsAndAggregateMustPass"])

    def test_product_authority_remains_closed_beyond_crop_geometry(self) -> None:
        authority = self.registration["productAuthority"]
        self.assertTrue(
            authority[
                "regularGeometryProfileCartesianTransferMayBeClaimedOnExactAggregatePass"
            ]
        )
        for sealed in (
            "currentShaderCapturedInputOpticalTransferMayBeClaimed",
            "independentPrivateInputGenerationMayBeClaimed",
            "opticalMaterialAppearanceDirectionTransferMayBeClaimed",
            "retina2xAndColorTransferMayBeClaimed",
            "independentWalleParityMayBeClaimed",
            "productionShaderMayChange",
            "liquidGlassParityMayBeClaimed",
        ):
            self.assertFalse(authority[sealed])

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

        flake = self.registration["frozenImplementation"]["developmentFlake"]
        self.assertFalse(flake["nixStorePathUsed"])
        local_flake = REPOSITORY_ROOT.parent / "flake.nix"
        if local_flake.is_file():
            self.assertEqual(sha256(local_flake), flake["sha256"])


if __name__ == "__main__":
    unittest.main()
