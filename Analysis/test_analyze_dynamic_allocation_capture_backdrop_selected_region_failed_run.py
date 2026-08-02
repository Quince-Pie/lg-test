#!/usr/bin/env python3
"""Tests for the failed selected-region capture audit."""

import json
import unittest
from pathlib import Path

import analyze_dynamic_allocation_capture_backdrop_selected_region_failed_run as analyzer


ANALYSIS_ROOT = Path(__file__).resolve().parent
RESULT = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_capture_backdrop_selected_region_failed_run_result.json"
    ).read_text(encoding="utf-8")
)


class CaptureBackdropSelectedRegionFailedRunTests(unittest.TestCase):
    def test_result_preserves_the_prospective_failure(self) -> None:
        self.assertEqual(RESULT["runID"], analyzer.EXPECTED_RUN_ID)
        self.assertEqual(RESULT["headSHA"], analyzer.EXPECTED_HEAD_SHA)
        self.assertEqual(RESULT["workflowConclusion"], "failure")
        self.assertEqual(RESULT["frozenGateError"], analyzer.EXPECTED_GATE_ERROR)
        self.assertFalse(RESULT["prospectiveGatePassed"])
        self.assertFalse(RESULT["conclusion"]["frozenSelectedRegionGatePassed"])

    def test_retained_live_operands_are_zero_tolerance_and_bit_exact(self) -> None:
        aggregate = RESULT["aggregate"]
        replay = aggregate["retainedOperandReplay"]
        self.assertEqual(aggregate["recordCount"], 114)
        self.assertEqual(aggregate["completeLiveOperandCaptureCount"], 113)
        self.assertEqual(aggregate["missingLiveOperandCaptureCount"], 1)
        self.assertEqual(replay["primaryPositionComponentCount"], 113 * 8)
        self.assertEqual(replay["primaryPositionMismatchedComponents"], 0)
        self.assertEqual(replay["primarySourceComponentCount"], 113 * 8)
        self.assertEqual(replay["primarySourceMismatchedComponents"], 0)
        self.assertEqual(replay["selectedRegionConsumedRectangleExactCount"], 113)
        self.assertFalse(replay["allowNumericTolerance"])

    def test_baseline_integrity_survives_all_114_states(self) -> None:
        aggregate = RESULT["aggregate"]
        self.assertEqual(
            aggregate["baselinePrimarySourceQ"],
            {"componentCount": 912, "exact": True, "mismatchedComponents": 0},
        )
        self.assertEqual(
            aggregate["baselineAllocationInvariants"],
            {"componentCount": 1596, "exact": True, "mismatchedComponents": 0},
        )
        self.assertTrue(
            aggregate["inputClampSideGate"]["recoveredTransferCandidateExact"]
        )

    def test_owner_slots_expose_a_new_pointer_backed_boundary(self) -> None:
        aggregate = RESULT["aggregate"]
        replay = aggregate["retainedOperandReplay"]
        self.assertEqual(replay["selectedEqualsOwner248Count"], 113)
        self.assertEqual(replay["selectedEqualsOwner270Count"], 110)
        self.assertEqual(
            [item["recordIndex"] for item in aggregate["ownerRegionMismatches"]],
            list(analyzer.EXPECTED_OWNER_MISMATCH_RECORDS),
        )
        self.assertEqual(aggregate["owner270PointerMismatchCount"], 2)
        self.assertTrue(
            RESULT["openedFacts"]["owner270RequiresIndependentPrefixCapture"]
        )

    def test_same_state_repeat_is_diagnostic_only(self) -> None:
        missing = RESULT["missingCapture"]
        conclusion = RESULT["conclusion"]
        self.assertEqual(missing["recordIndex"], analyzer.EXPECTED_MISSING_RECORD_INDEX)
        self.assertEqual(
            missing["sameStateRepeatRecordIndex"], analyzer.EXPECTED_REPEAT_RECORD_INDEX
        )
        self.assertTrue(missing["allNonRenderStateFieldsExact"])
        self.assertTrue(missing["drawConsumedPrimaryGeometryExact"])
        self.assertFalse(missing["bufferReuseCauseProven"])
        self.assertFalse(conclusion["missingCapturePromotedFromRepeat"])
        self.assertFalse(conclusion["publicLayerStateCropRuleRecovered"])
        self.assertTrue(conclusion["requiresUnseenGeometryTransfer"])
        self.assertFalse(conclusion["productionShaderAuthorized"])


if __name__ == "__main__":
    unittest.main()
