#!/usr/bin/env python3
"""Tests for the failed capture_backdrop operand-run audit."""

import json
import unittest
from pathlib import Path

import analyze_dynamic_allocation_capture_backdrop_operand_failed_run as analyzer
import validate_dynamic_allocation_surviving_path_threshold as surviving


ANALYSIS_ROOT = Path(__file__).resolve().parent
RESULT = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_capture_backdrop_operand_failed_run_result.json"
    ).read_text(encoding="utf-8")
)


class CaptureBackdropOperandFailedRunTests(unittest.TestCase):
    def test_result_retains_the_failed_prospective_status(self) -> None:
        self.assertEqual(RESULT["runID"], analyzer.EXPECTED_RUN_ID)
        self.assertEqual(RESULT["headSHA"], analyzer.EXPECTED_HEAD_SHA)
        self.assertEqual(RESULT["workflowConclusion"], "failure")
        self.assertFalse(RESULT["prospectiveGatePassed"])
        self.assertFalse(RESULT["conclusion"]["frozenOperandGatePassed"])

    def test_corrected_replay_is_zero_tolerance_and_bit_exact(self) -> None:
        replay = RESULT["aggregate"]["captureBackdropOperandReplay"]
        self.assertEqual(replay["captureCount"], 114)
        self.assertEqual(replay["primaryPositionComponentCount"], 114 * 8)
        self.assertEqual(replay["primaryPositionMismatchedComponents"], 0)
        self.assertEqual(replay["primarySourceComponentCount"], 114 * 8)
        self.assertEqual(replay["primarySourceMismatchedComponents"], 0)
        self.assertEqual(replay["transformBranchCounts"], {"identity": 114})
        self.assertFalse(replay["allowNumericTolerance"])

    def test_region_iterator_code_identity_is_frozen(self) -> None:
        facts = RESULT["openedCodeFacts"]
        self.assertEqual(
            facts["selectedRegionIteratorCallOffset"],
            surviving.CAPTURE_BACKDROP_REGION_ITERATE_CALL_OFFSET,
        )
        self.assertEqual(
            facts["selectedRegionIteratorSymbol"],
            surviving.CAPTURE_BACKDROP_REGION_ITERATE_SYMBOL,
        )
        self.assertEqual(
            facts["selectedRegionIteratorPrefixSHA256"],
            surviving.CAPTURE_BACKDROP_EXPECTED_REGION_ITERATE_PREFIX_SHA256,
        )
        self.assertEqual(facts["originBoundsPointerStackOffset"], 0x190)
        self.assertEqual(
            facts["selectedRegionIntersectionInstructionRange"],
            [0x2480, 0x24DC],
        )

    def test_result_does_not_promote_the_opened_data_to_policy_or_parity(self) -> None:
        conclusion = RESULT["conclusion"]
        self.assertFalse(conclusion["selectedRegionPolicyRecovered"])
        self.assertTrue(conclusion["requiresSelectedRegionCapture"])
        self.assertFalse(conclusion["productionShaderAuthorized"])


if __name__ == "__main__":
    unittest.main()
