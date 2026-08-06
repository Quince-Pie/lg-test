#!/usr/bin/env python3
"""Integrity tests for the prospective unseen crop-policy holdout."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_crop_policy_holdout_preregistration.json"
)
CALIBRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_crop_union_operand_matrix_analysis.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerCropPolicyHoldoutPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_registration_is_prospective_and_chained_to_failed_opened_run(self):
        registration = self.registration
        antecedent = registration["openedCalibrationEvidence"]
        self.assertEqual(
            registration["prepareLayerCropPolicyHoldoutPreregistrationSchemaVersion"],
            1,
        )
        self.assertIn("prospective", registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])
        self.assertEqual(antecedent["runID"], 31057364064)
        self.assertEqual(antecedent["workflowConclusion"], "failure")
        self.assertFalse(antecedent["prospectiveGatePassed"])
        self.assertEqual(
            antecedent["falsifiedProspectiveAssumption"],
            "exactly one destination-matched union exists in each marker interval",
        )
        self.assertEqual(sha256(CALIBRATION_PATH), antecedent["analysisSHA256"])
        self.assertEqual(antecedent["recordCount"], 256)
        self.assertEqual(antecedent["exactPublicCropRecordCount"], 256)

    def test_candidate_and_operation_order_are_frozen(self):
        candidate = self.registration["frozenCandidate"]
        self.assertEqual(candidate["publicLayerPath"], [1, 0, 1])
        self.assertEqual(
            candidate["glassDODExpansion"],
            "e = 2.8 * max(2 * inputBlurRadius, inputBleedBlurRadius)",
        )
        self.assertEqual(candidate["support"], "s = 9 + e")
        self.assertEqual(candidate["publicROIEdges"]["lowerX"], "Px + Bx - s")
        self.assertEqual(
            candidate["publicROIEdges"]["lowerY"],
            "H - Py - (By + Bh) - 17",
        )
        self.assertEqual(candidate["publicROIEdges"]["farX"], "Px + (Bx + Bw) + s")
        self.assertEqual(candidate["publicROIEdges"]["farY"], "H - Py - By + s")
        self.assertFalse(candidate["toleranceUsed"])
        self.assertFalse(candidate["exceptionFitUsed"])

    def test_holdout_geometries_are_disjoint_from_derivation_matrix(self):
        matrix = self.registration["holdoutMatrix"]
        calibration = set(matrix["excludedCalibrationGeometries"])
        holdouts = {record["geometry"] for record in matrix["jobs"]}
        self.assertEqual(len(matrix["jobs"]), 8)
        self.assertEqual(len(holdouts), 8)
        self.assertTrue(calibration.isdisjoint(holdouts))
        self.assertIn("circle-065-center", holdouts)
        self.assertIn("circle-2048-center", holdouts)
        self.assertIn("circle-256-crop-d", holdouts)
        self.assertIn("circle-096-padx-453", holdouts)

    def test_frozen_implementation_hashes_match(self):
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

    def test_acceptance_is_exact_and_keeps_product_authority_sealed(self):
        acceptance = self.registration["acceptance"]
        self.assertEqual(acceptance["jobCount"], 8)
        self.assertEqual(acceptance["normalMarkerCountPerJob"], 32)
        self.assertTrue(acceptance["twoDestinationMatchesPerMarkerRequired"])
        self.assertTrue(acceptance["lastDestinationMatchRequired"])
        self.assertTrue(acceptance["onePointerMatchedStorePerMarkerRequired"])
        self.assertTrue(acceptance["allPreIntegerF64WordsMustMatchBitForBit"])
        self.assertTrue(acceptance["allIntegerCropWordsMustMatchExactly"])
        self.assertTrue(acceptance["allFinalAggregateWordsMustMatchBitForBit"])
        self.assertFalse(acceptance["materialAppearanceDirectionTransferMayBeClaimed"])
        self.assertFalse(acceptance["retina2xTransferMayBeClaimed"])
        self.assertFalse(acceptance["productionShaderMayChange"])
        self.assertFalse(acceptance["liquidGlassParityMayBeClaimed"])


if __name__ == "__main__":
    unittest.main()
