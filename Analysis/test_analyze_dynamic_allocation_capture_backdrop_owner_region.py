#!/usr/bin/env python3
"""Tests for the prospectively passing dual-owner capture audit."""

import json
import unittest
from pathlib import Path

import analyze_dynamic_allocation_capture_backdrop_owner_region as analyzer


ANALYSIS_ROOT = Path(__file__).resolve().parent
RESULT = json.loads(
    (
        ANALYSIS_ROOT / "dynamic_allocation_capture_backdrop_owner_region_result.json"
    ).read_text(encoding="utf-8")
)


class CaptureBackdropOwnerRegionTests(unittest.TestCase):
    def test_result_preserves_the_prospective_pass(self) -> None:
        self.assertEqual(RESULT["runID"], analyzer.EXPECTED_RUN_ID)
        self.assertEqual(RESULT["headSHA"], analyzer.EXPECTED_HEAD_SHA)
        self.assertEqual(RESULT["workflowConclusion"], "success")
        self.assertTrue(RESULT["prospectiveGatePassed"])
        self.assertTrue(RESULT["conclusion"]["frozenOwnerRegionGatePassed"])

    def test_all_live_replay_gates_are_exact(self) -> None:
        aggregate = RESULT["aggregate"]
        self.assertEqual(aggregate["recordCount"], 114)
        self.assertEqual(aggregate["completeLiveOperandCaptureCount"], 114)
        self.assertEqual(
            aggregate["primaryPositionReplay"],
            {
                "componentCount": 912,
                "mismatchedComponents": 0,
                "allowNumericTolerance": False,
            },
        )
        self.assertEqual(
            aggregate["primarySourceReplay"],
            {
                "componentCount": 912,
                "mismatchedComponents": 0,
                "allowNumericTolerance": False,
            },
        )
        self.assertEqual(aggregate["selectedRegionConsumedRectangleExactCount"], 114)
        self.assertEqual(aggregate["callbackAttemptCount"], 0)

    def test_both_pointer_regions_are_fully_decoded(self) -> None:
        aggregate = RESULT["aggregate"]
        self.assertEqual(aggregate["owner248HandleClassCounts"], {"packed": 114})
        self.assertEqual(
            aggregate["owner270HandleClassCounts"], {"packed": 112, "pointer": 2}
        )
        self.assertEqual(aggregate["owner270PointerPrefixByteCount"], 4096)
        mismatches = aggregate["ownerRegionMismatches"]
        self.assertEqual(
            [item["recordIndex"] for item in mismatches],
            list(analyzer.EXPECTED_MISMATCH_RECORDS),
        )
        pointer_rectangles = {
            item["recordIndex"]: tuple(
                tuple(rectangle) for rectangle in item["owner270Rectangles"]
            )
            for item in mismatches
            if item["owner270Class"] == "pointer"
        }
        self.assertEqual(pointer_rectangles, analyzer.EXPECTED_POINTER_RECTANGLES)

    def test_owner_window_is_fully_accounted_for(self) -> None:
        owner = RESULT["openedOwnerWindow"]
        self.assertEqual(owner["generationCounters"]["exactCount"], 114)
        self.assertEqual(owner["publicBounds"]["exactCount"], 114)
        self.assertEqual(owner["remaining"]["exactCount"], 114)
        self.assertTrue(owner["allOtherBytesZero"])
        self.assertEqual(owner["generationNormalizedDistinctWindowCount"], 9)
        self.assertTrue(RESULT["aggregate"]["sameStateNormalizedOwnerWindowsExact"])

    def test_next_unknown_is_not_promoted(self) -> None:
        instructions = RESULT["openedInstructions"]
        conclusion = RESULT["conclusion"]
        self.assertEqual(instructions["recordVector"]["recordStrideBytes"], 0xD0)
        self.assertEqual(
            instructions["regionSelector"]["candidateOwnerOffsets"],
            [0x248, 0x270],
        )
        self.assertFalse(conclusion["publicLayerStateCropRuleRecovered"])
        self.assertTrue(conclusion["requiresBoundedOwnerRecordVectorCapture"])
        self.assertTrue(conclusion["requiresUnseenGeometryTransfer"])
        self.assertFalse(conclusion["productionShaderAuthorized"])


if __name__ == "__main__":
    unittest.main()
