#!/usr/bin/env python3
"""Tests for the retrospective callback-retry crop-policy opening."""

from __future__ import annotations

import hashlib
import json
import struct
import unittest
from pathlib import Path

import analyze_prepare_layer_crop_policy_holdout_callback_retry as analyzer


ANALYSIS_ROOT = Path(__file__).resolve().parent
RESULT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_crop_policy_holdout_callback_retry_result.json"
)
RESULT = json.loads(RESULT_PATH.read_text(encoding="utf-8"))


class PrepareLayerCropPolicyHoldoutCallbackRetryAnalysisTests(unittest.TestCase):
    def test_original_red_gate_is_preserved(self) -> None:
        self.assertEqual(
            RESULT[
                "prepareLayerCropPolicyHoldoutCallbackRetryAnalysisSchemaVersion"
            ],
            1,
        )
        self.assertEqual(RESULT["run"]["id"], 31059860458)
        self.assertEqual(
            RESULT["run"]["headSHA"],
            "6ff54c6bd01e6dea04002ca8c11fd1c0f7e4852c",
        )
        self.assertEqual(RESULT["run"]["conclusion"], "failure")
        self.assertFalse(RESULT["prospectiveGatePassed"])
        failures = RESULT["originalProspectiveFailures"]
        self.assertEqual(len(failures), 8)
        self.assertEqual(
            failures["holdout-2048-center"],
            "qualified normal-render recursion topology differs",
        )
        for label, failure in failures.items():
            if label != "holdout-2048-center":
                self.assertEqual(failure, "public crop producer replay differs")

    def test_opened_topology_is_explicit_and_narrow(self) -> None:
        self.assertEqual(RESULT["geometryCount"], 8)
        self.assertEqual(RESULT["recordCount"], 256)
        opened = [
            geometry
            for geometry in RESULT["geometryResults"]
            if geometry["openedTopologyVariant"]
        ]
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0]["label"], "holdout-2048-center")
        self.assertEqual(opened[0]["observedPrepareRecursionDepths"], [3] * 32)
        for geometry in RESULT["geometryResults"]:
            if geometry["label"] != "holdout-2048-center":
                self.assertEqual(
                    geometry["observedPrepareRecursionDepths"], [3] + [4] * 31
                )

    def test_true_producer_selection_is_structural(self) -> None:
        selection = RESULT["openedProducerSelection"]
        self.assertFalse(selection["selectionUsesCropValues"])
        self.assertTrue(selection["allStructuralSelectionsPassed"])
        for record in RESULT["records"]:
            self.assertEqual(
                record["structuralProducerStoreIndex"] + 2,
                record["pointerCorrelatedMirrorStoreIndex"],
            )
            self.assertEqual(
                record["producerRoleBase"] + 0xFB0, record["mirrorRoleBase"]
            )
            self.assertEqual(
                record["producerPrepareRecursionDepth"],
                record["mirrorPrepareRecursionDepth"] + 2,
            )

    def test_integer_boundary_is_exact_for_all_opened_records(self) -> None:
        boundary = RESULT["downstreamBoundary"]
        self.assertEqual(boundary["pointerCorrelatedIntegerMirrorCount"], 256)
        self.assertEqual(
            boundary["producerIntegerizationAndViewportIntersectionExactCount"],
            256,
        )
        self.assertEqual(boundary["mismatchedIntegerCropCount"], 0)
        self.assertEqual(boundary["calibrationAndHoldoutIntegerCropCount"], 512)
        self.assertEqual(
            boundary["calibrationAndHoldoutMismatchedIntegerCropCount"], 0
        )

    def test_float_models_are_reported_without_tolerance(self) -> None:
        models = RESULT["floatingProducerModels"]
        collapsed = models["originalCollapsedCanvasCandidate"]
        self.assertEqual(collapsed["exactRectangleCount"], 139)
        self.assertEqual(collapsed["mismatchedRectangleCount"], 117)
        self.assertEqual(
            collapsed["exactComponentCountsXYWH"], [256, 229, 151, 198]
        )
        self.assertFalse(collapsed["toleranceUsed"])

        local = models["retrospectiveLocalCoordinateCandidate"]
        self.assertEqual(local["exactRectangleCount"], 211)
        self.assertEqual(local["mismatchedRectangleCount"], 45)
        self.assertEqual(local["exactComponentCountsXYWH"], [256, 211, 245, 211])
        self.assertFalse(local["toleranceUsed"])

    def test_role_layout_exposes_the_lost_operation_order(self) -> None:
        counts = RESULT["producerRoleIntermediateExactCounts"]
        self.assertEqual(counts["recordCount"], 256)
        self.assertEqual(counts["matrixTranslationMatchesPublicBoundsBitwise"], 256)
        self.assertEqual(counts["dynamicLocalMatchesPublicBoundsBitwise"], 256)
        self.assertEqual(counts["shadowOffsetIsEightBitwise"], 256)
        self.assertEqual(counts["recursiveChildIsNominalPlusShadowBitwise"], 256)
        self.assertEqual(
            counts["transformedDynamicMatchesCollapsedPublicTransformBitwise"],
            251,
        )
        self.assertEqual(counts["carrierTranslationMatchesPublicBitwise"], 255)
        self.assertEqual(counts["nominalShapeMatchesPublicGeometryBitwise"], 224)

    def test_local_candidate_operation_order_anchor(self) -> None:
        candidate = analyzer.local_coordinate_candidate(
            (510.99810791015625, 510.99810791015625),
            (
                -37.29649066925049,
                -37.29649066925049,
                77.59298133850098,
                77.59298133850098,
            ),
            (0.0, -0.0, 65.0, 73.0),
            1024.0,
            0.03130912780761719,
            0.0,
        )
        self.assertEqual(
            struct.pack("<4d", *candidate).hex(),
            "00000040f8ef7f4000000053497b7c40000000a864bc484000000068f3a54c40",
        )

    def test_result_has_frozen_unmodified_shader_authority(self) -> None:
        conclusion = RESULT["conclusion"]
        self.assertEqual(
            conclusion["productionShaderExpectedSHA256"],
            "6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d",
        )
        self.assertFalse(conclusion["exactBinary64ProducerArithmeticRecovered"])
        self.assertFalse(conclusion["productionShaderAuthorized"])
        self.assertFalse(conclusion["liquidGlassParityEstablished"])

        walle_shader = ANALYSIS_ROOT.parent.parent / "shaders" / "frag.glsl"
        if walle_shader.is_file():
            self.assertEqual(
                hashlib.sha256(walle_shader.read_bytes()).hexdigest(),
                conclusion["productionShaderExpectedSHA256"],
            )


if __name__ == "__main__":
    unittest.main()
