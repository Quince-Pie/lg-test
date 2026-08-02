#!/usr/bin/env python3
"""Tests for the failed owner-record-vector capture audit."""

import json
import unittest
from pathlib import Path

import analyze_dynamic_allocation_capture_backdrop_owner_record_failed_run as analyzer


ANALYSIS_ROOT = Path(__file__).resolve().parent
RESULT = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_capture_backdrop_owner_record_failed_run_result.json"
    ).read_text(encoding="utf-8")
)


class CaptureBackdropOwnerRecordFailedRunTests(unittest.TestCase):
    def test_result_preserves_the_prospective_failure(self) -> None:
        self.assertEqual(RESULT["runID"], analyzer.EXPECTED_RUN_ID)
        self.assertEqual(RESULT["headSHA"], analyzer.EXPECTED_HEAD_SHA)
        self.assertEqual(RESULT["workflowConclusion"], "failure")
        self.assertEqual(RESULT["frozenGateError"], analyzer.EXPECTED_GATE_ERROR)
        self.assertFalse(RESULT["prospectiveGatePassed"])
        self.assertFalse(RESULT["conclusion"]["frozenOwnerRecordGatePassed"])

    def test_only_the_record_vector_read_is_missing(self) -> None:
        aggregate = RESULT["aggregate"]
        self.assertEqual(aggregate["recordCount"], 114)
        self.assertEqual(aggregate["completeLiveOperandCaptureCount"], 0)
        self.assertEqual(aggregate["partialOperandCaptureCount"], 114)
        self.assertEqual(aggregate["callbackAttemptCount"], 342)
        self.assertEqual(
            aggregate["partialReadMaskCounts"],
            {analyzer.EXPECTED_PARTIAL_READ_MASK: 114},
        )
        self.assertEqual(aggregate["ownerObjectPrefixExactCount"], 114)
        self.assertEqual(aggregate["sourceStateWindowExactCount"], 114)
        self.assertEqual(aggregate["retainedOwnerRecordVectorCount"], 0)

    def test_all_states_falsify_the_capacity_assumption(self) -> None:
        aggregate = RESULT["aggregate"]
        opened = RESULT["openedFacts"]
        self.assertEqual(aggregate["beginEndSpanByteCounts"], {"208": 114})
        self.assertEqual(aggregate["ownerWord60EqualsBeginCount"], 114)
        self.assertEqual(
            opened["instructionProvenOwnerRecordOffsets"],
            [analyzer.OWNER_RECORD_BEGIN_OFFSET, analyzer.OWNER_RECORD_END_OFFSET],
        )
        self.assertEqual(
            opened["falsifiedCapacityOffset"],
            analyzer.FALSIFIED_CAPACITY_OFFSET,
        )
        self.assertTrue(opened["observedOwnerWord60EqualsBeginEveryState"])
        self.assertEqual(opened["observedRecordCountEveryState"], 1)

    def test_previous_owner_region_gate_still_replays_exactly(self) -> None:
        replay = RESULT["aggregate"]["downgradedOwnerRegionGate"]
        self.assertEqual(replay["primaryPositionComponentCount"], 912)
        self.assertEqual(replay["primaryPositionMismatchedComponents"], 0)
        self.assertEqual(replay["primarySourceComponentCount"], 912)
        self.assertEqual(replay["primarySourceMismatchedComponents"], 0)
        self.assertEqual(replay["selectedRegionConsumedRectangleExactCount"], 114)
        self.assertEqual(replay["selectedEqualsOwner248Count"], 114)
        self.assertEqual(replay["selectedEqualsOwner270Count"], 111)
        self.assertEqual(replay["primarySourceQ"]["mismatchedComponents"], 0)
        self.assertEqual(replay["allocationInvariants"]["mismatchedComponents"], 0)
        self.assertFalse(replay["allowNumericTolerance"])

    def test_failure_does_not_promote_missing_evidence(self) -> None:
        conclusion = RESULT["conclusion"]
        self.assertTrue(conclusion["failureIsolatedToUnprovenCapacityGuard"])
        self.assertTrue(conclusion["previousOwnerRegionGateReplaysExactly"])
        self.assertFalse(conclusion["ownerRecordVectorCaptured"])
        self.assertTrue(conclusion["requiresInstructionProvenBeginEndRetry"])
        self.assertFalse(conclusion["publicLayerStateCropRuleRecovered"])
        self.assertTrue(conclusion["requiresUnseenGeometryTransfer"])
        self.assertFalse(conclusion["productionShaderAuthorized"])


if __name__ == "__main__":
    unittest.main()
