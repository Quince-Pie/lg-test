#!/usr/bin/env python3
"""Integrity tests for the corrected owner-record-vector retry."""

import hashlib
import json
import unittest
from pathlib import Path

import validate_dynamic_allocation_surviving_path_threshold as surviving


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
PREREGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_capture_backdrop_owner_record_retry_preregistration.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CaptureBackdropOwnerRecordRetryPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration = json.loads(
            PREREGISTRATION_PATH.read_text(encoding="utf-8")
        )

    def test_opened_owner_record_run_remains_a_prospective_failure(self) -> None:
        opened = self.preregistration["openedOwnerRecordEvidence"]
        self.assertEqual(opened["runID"], 30770107772)
        self.assertEqual(opened["workflowConclusion"], "failure")
        self.assertFalse(opened["prospectiveGatePassed"])
        self.assertEqual(opened["partialOperandCaptureCount"], 114)
        self.assertEqual(opened["retainedOwnerRecordVectorCount"], 0)
        self.assertEqual(opened["beginEndSpanByteCounts"], {"208": 114})
        self.assertEqual(opened["ownerWord60EqualsBeginCount"], 114)
        self.assertEqual(
            sha256(
                ANALYSIS_ROOT
                / "dynamic_allocation_capture_backdrop_owner_record_failed_run_result.json"
            ),
            opened["failedRunAnalysisResultSHA256"],
        )

    def test_retry_uses_only_instruction_proven_begin_and_end(self) -> None:
        capture = self.preregistration["capture"]
        acceptance = self.preregistration["acceptance"]
        self.assertEqual(capture["outerCaptureEvidenceSchemaVersion"], 8)
        self.assertEqual(capture["operandEvidenceSchemaVersion"], 4)
        self.assertEqual(capture["requiredReadMask"], "0x007fffff")
        self.assertEqual(
            capture["ownerRecordOffsets"],
            surviving.CAPTURE_BACKDROP_OWNER_RECORD_OFFSETS,
        )
        self.assertNotIn("capacity", capture["ownerRecordOffsets"])
        self.assertTrue(capture["ownerWord60CapturedButUninterpreted"])
        self.assertEqual(capture["ownerRecordByteCount"], 0xD0)
        self.assertEqual(capture["ownerRecordMaximumCount"], 64)
        self.assertEqual(capture["ownerRecordVectorMaximumByteCount"], 13_312)
        self.assertEqual(acceptance["ownerRecordCountExactPerState"], 1)
        self.assertEqual(acceptance["selectedOwnerRecordIndexExactPerState"], 0)
        self.assertEqual(
            surviving.CAPTURE_BACKDROP_OWNER_RECORD_EXPECTED_COUNT,
            acceptance["ownerRecordCountExactPerState"],
        )
        self.assertEqual(
            surviving.CAPTURE_BACKDROP_OWNER_RECORD_EXPECTED_MATCH_COUNT,
            acceptance["sourceKeyMatchCountExactPerState"],
        )
        self.assertEqual(
            surviving.CAPTURE_BACKDROP_OWNER_RECORD_EXPECTED_SELECTED_INDEX,
            acceptance["selectedOwnerRecordIndexExactPerState"],
        )

    def test_frozen_implementation_hashes_match_files(self) -> None:
        expected = self.preregistration["frozenImplementation"]
        files = {
            "matrixBridgeHeaderSHA256": REPOSITORY_ROOT
            / "Sources/GlassIntrospect/MatrixBridge.h",
            "matrixBridgeSourceSHA256": REPOSITORY_ROOT
            / "Sources/GlassIntrospect/MatrixBridge.c",
            "swiftCaptureSHA256": REPOSITORY_ROOT
            / "Sources/GlassIntrospect/main.swift",
            "workflowSHA256": REPOSITORY_ROOT
            / ".github/workflows/transition-introspect.yml",
            "holdoutValidatorSHA256": ANALYSIS_ROOT
            / "validate_dynamic_allocation_holdout.py",
            "validatorSHA256": ANALYSIS_ROOT
            / "validate_dynamic_allocation_surviving_path_threshold.py",
            "validatorTestSHA256": ANALYSIS_ROOT
            / "test_validate_dynamic_allocation_surviving_path_threshold.py",
            "failedRunAnalyzerSHA256": ANALYSIS_ROOT
            / "analyze_dynamic_allocation_capture_backdrop_owner_record_failed_run.py",
            "failedRunAnalyzerTestSHA256": ANALYSIS_ROOT
            / "test_analyze_dynamic_allocation_capture_backdrop_owner_record_failed_run.py",
            "failedRunResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_capture_backdrop_owner_record_failed_run_result.json",
            "ownerRegionResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_capture_backdrop_owner_region_result.json",
            "ownerRecordPreregistrationSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_capture_backdrop_owner_record_preregistration.json",
            "ownerRecordPreregistrationTestSHA256": ANALYSIS_ROOT
            / "test_dynamic_allocation_capture_backdrop_owner_record_preregistration.py",
            "ownerRecordRetryPreregistrationTestSHA256": Path(__file__),
            "productionShaderSHA256": REPOSITORY_ROOT.parent / "shaders/frag.glsl",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                self.assertEqual(sha256(path), expected[name])

    def test_acceptance_is_exact_and_fails_closed(self) -> None:
        acceptance = self.preregistration["acceptance"]
        self.assertEqual(acceptance["operandCaptureCount"], 114)
        self.assertEqual(acceptance["ownerObjectPrefixExactCount"], 114)
        self.assertEqual(acceptance["ownerRecordVectorExactCount"], 114)
        self.assertEqual(acceptance["sourceStateWindowExactCount"], 114)
        self.assertEqual(acceptance["sourceKeyMatchCountExactPerState"], 1)
        self.assertTrue(acceptance["ownerRegionWindowEmbeddedInPrefixEveryState"])
        self.assertFalse(acceptance["callbackAttemptMayReplaceLiveOperands"])
        self.assertFalse(acceptance["allowNumericTolerance"])
        self.assertFalse(acceptance["productionShaderAuthorized"])

    def test_public_policy_and_product_parity_remain_out_of_scope(self) -> None:
        self.assertIn("production Walle parity", self.preregistration["notClaimed"])
        self.assertIn(
            "a public-state-only owner-region construction policy",
            self.preregistration["notClaimed"],
        )
        plan = self.preregistration["analysisPlan"]
        self.assertIn("record", plan["recordInventory"])
        self.assertIn("public", plan["policyReplay"])
        self.assertIn("unseen", plan["nextGate"])


if __name__ == "__main__":
    unittest.main()
