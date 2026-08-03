#!/usr/bin/env python3
"""Tests for the prospectively passing upstream-object capture audit."""

import json
import unittest
from pathlib import Path

import analyze_dynamic_allocation_capture_backdrop_upstream_writer as analyzer


ANALYSIS_ROOT = Path(__file__).resolve().parent
RESULT = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_capture_backdrop_upstream_writer_result.json"
    ).read_text(encoding="utf-8")
)


class CaptureBackdropUpstreamWriterTests(unittest.TestCase):
    def test_result_preserves_the_prospective_pass(self) -> None:
        self.assertEqual(RESULT["runID"], analyzer.EXPECTED_RUN_ID)
        self.assertEqual(RESULT["headSHA"], analyzer.EXPECTED_HEAD_SHA)
        self.assertEqual(RESULT["workflowConclusion"], "success")
        self.assertTrue(RESULT["prospectiveGatePassed"])
        self.assertTrue(RESULT["conclusion"]["frozenUpstreamObjectGatePassed"])

    def test_all_prior_live_replay_gates_remain_exact(self) -> None:
        aggregate = RESULT["aggregate"]
        self.assertEqual(aggregate["recordCount"], 114)
        self.assertEqual(aggregate["completeLiveOperandCaptureCount"], 114)
        self.assertEqual(aggregate["completeReadMask"], "0x3fffffff")
        self.assertEqual(aggregate["primaryPositionReplay"]["mismatchedComponents"], 0)
        self.assertEqual(aggregate["primarySourceReplay"]["mismatchedComponents"], 0)
        self.assertEqual(aggregate["selectedRegionConsumedRectangleExactCount"], 114)

    def test_selected_rectangle_is_exact_at_five_private_locations(self) -> None:
        identity = RESULT["openedPrivateRectangleIdentity"]
        self.assertEqual(identity["exactCrossObjectCount"], 114)
        self.assertEqual(identity["distinctSelectedRectangleCount"], 9)
        self.assertEqual(identity["distinctLayerStateInputBoundsCount"], 83)
        self.assertEqual(identity["inputBoundsWithMultipleObservedOutputsCount"], 0)
        self.assertEqual(
            [(item["object"], item["offset"]) for item in identity["encodingMap"]],
            [
                ("CA::Render::BackdropState", 0x50),
                ("layer state", 0xB0),
                ("CA::Render::BackdropGroup", 0xE0),
                ("single owner record", 0x70),
                ("CA::Render::BackdropGroup", 0x248),
            ],
        )
        self.assertFalse(identity["publicConstructionRuleRecovered"])

    def test_opened_helper_is_edge_replication_not_region_construction(self) -> None:
        opened = RESULT["openedTargetCode"]
        helper = opened["desiredSourceEdgeReplication"]
        self.assertEqual(len(opened["directCalls"]), 7)
        self.assertEqual(helper["functionBodyEndOffset"], 0x2D4)
        self.assertFalse(helper["constructsOwnerRegion"])
        self.assertEqual(helper["nestedAuxiliaryReadOffset"], 0x60)
        self.assertEqual(helper["capturedNestedAuxiliaryByteCount"], 0x60)
        self.assertFalse(helper["nestedReadCoveredByCapture"])
        self.assertEqual(
            opened["lateRegionSelection"]["candidateOwnerOffsets"],
            [0x248, 0x270],
        )
        self.assertFalse(opened["lateRegionSelection"]["constructsSelectedRegion"])

    def test_missing_writer_is_not_promoted_to_a_shader_change(self) -> None:
        conclusion = RESULT["conclusion"]
        self.assertTrue(conclusion["privateSelectedRectangleMappedAcrossFiveLocations"])
        self.assertTrue(conclusion["lateCaptureBackdropPathConsumesPrebuiltRegion"])
        self.assertFalse(conclusion["layerStateA0ToB0ConstructionRuleRecovered"])
        self.assertTrue(conclusion["requiresEarlierWriterTrace"])
        self.assertTrue(conclusion["requiresUnseenGeometryTransfer"])
        self.assertFalse(conclusion["productionShaderAuthorized"])


if __name__ == "__main__":
    unittest.main()
