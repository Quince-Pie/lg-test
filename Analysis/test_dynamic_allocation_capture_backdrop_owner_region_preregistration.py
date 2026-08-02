#!/usr/bin/env python3
"""Integrity tests for the dual-owner-region capture preregistration."""

import hashlib
import json
import unittest
from pathlib import Path

import validate_dynamic_allocation_surviving_path_threshold as surviving


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
PREREGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_capture_backdrop_owner_region_preregistration.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CaptureBackdropOwnerRegionPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration = json.loads(
            PREREGISTRATION_PATH.read_text(encoding="utf-8")
        )

    def test_failed_selected_region_run_is_not_promoted(self) -> None:
        opened = self.preregistration["openedSelectedRegionEvidence"]
        self.assertEqual(opened["runID"], 30765781334)
        self.assertEqual(opened["workflowConclusion"], "failure")
        self.assertEqual(
            opened["workflowGateError"],
            "capture_backdrop operand capture count differs at 31/9",
        )
        self.assertFalse(opened["prospectiveGatePassed"])
        self.assertEqual(opened["completeLiveOperandCaptureCount"], 113)
        self.assertEqual(opened["missingLiveOperandCaptureCount"], 1)
        self.assertFalse(opened["sameStateRepeatPromoted"])
        self.assertEqual(
            sha256(
                ANALYSIS_ROOT
                / "dynamic_allocation_capture_backdrop_selected_region_failed_run_result.json"
            ),
            opened["failedRunAnalysisResultSHA256"],
        )

    def test_schema_three_dual_owner_layout_matches_the_validator(self) -> None:
        capture = self.preregistration["capture"]
        acceptance = self.preregistration["acceptance"]
        self.assertEqual(capture["outerCaptureEvidenceSchemaVersion"], 7)
        self.assertEqual(capture["operandEvidenceSchemaVersion"], 3)
        self.assertEqual(capture["requiredReadMask"], "0x000fffff")
        self.assertEqual(
            capture["memoryReadMaximumAttemptCount"],
            surviving.CAPTURE_BACKDROP_MEMORY_READ_MAXIMUM_ATTEMPT_COUNT,
        )
        self.assertEqual(
            capture["callbackMaximumAttemptCountPerRecord"],
            surviving.CAPTURE_BACKDROP_CALLBACK_MAXIMUM_ATTEMPT_COUNT,
        )
        self.assertEqual(
            capture["callbackMaximumFrameCount"],
            surviving.CAPTURE_BACKDROP_CALLBACK_MAXIMUM_FRAME_COUNT,
        )
        self.assertEqual(
            capture["ownerRegionPrefixMaximumByteCount"],
            surviving.CAPTURE_BACKDROP_OWNER_REGION_PREFIX_BYTE_COUNT,
        )
        self.assertEqual(
            capture["ownerRegionWindow"],
            [surviving.CAPTURE_BACKDROP_OWNER_REGION_WINDOW_OFFSET, 256],
        )
        self.assertEqual(
            capture["eligibleProducerFragments"],
            sorted(surviving.CAPTURE_BACKDROP_OPERAND_FRAGMENTS),
        )
        self.assertEqual(
            acceptance["pinnedShapeIteratorPrefixSHA256"],
            surviving.CAPTURE_BACKDROP_EXPECTED_REGION_ITERATE_PREFIX_SHA256,
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
            "validatorSHA256": ANALYSIS_ROOT
            / "validate_dynamic_allocation_surviving_path_threshold.py",
            "validatorTestSHA256": ANALYSIS_ROOT
            / "test_validate_dynamic_allocation_surviving_path_threshold.py",
            "failedRunAnalyzerSHA256": ANALYSIS_ROOT
            / "analyze_dynamic_allocation_capture_backdrop_selected_region_failed_run.py",
            "failedRunAnalyzerTestSHA256": ANALYSIS_ROOT
            / "test_analyze_dynamic_allocation_capture_backdrop_selected_region_failed_run.py",
            "failedRunResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_capture_backdrop_selected_region_failed_run_result.json",
            "selectedRegionPreregistrationSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_capture_backdrop_selected_region_preregistration.json",
            "selectedRegionPreregistrationTestSHA256": ANALYSIS_ROOT
            / "test_dynamic_allocation_capture_backdrop_selected_region_preregistration.py",
            "ownerRegionPreregistrationTestSHA256": Path(__file__),
            "productionShaderSHA256": REPOSITORY_ROOT.parent / "shaders/frag.glsl",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                self.assertEqual(sha256(path), expected[name])

    def test_acceptance_is_bitwise_and_callback_attempts_cannot_substitute(
        self,
    ) -> None:
        acceptance = self.preregistration["acceptance"]
        self.assertEqual(acceptance["operandCaptureCount"], 114)
        self.assertEqual(acceptance["selectedRegionConsumedRectangleExactCount"], 114)
        self.assertEqual(acceptance["owner248PackedHandleCount"], 114)
        self.assertEqual(acceptance["owner270PackedHandleCount"], 112)
        self.assertEqual(acceptance["owner270PointerHandleCount"], 2)
        self.assertEqual(
            acceptance["owner270PointerPrefixMinimumByteCountPerPointerCapture"],
            surviving.CAPTURE_BACKDROP_REGION_PREFIX_BYTE_COUNT,
        )
        self.assertEqual(
            acceptance["owner270PointerPrefixMaximumByteCountPerPointerCapture"],
            surviving.CAPTURE_BACKDROP_OWNER_REGION_PREFIX_BYTE_COUNT,
        )
        self.assertEqual(acceptance["selectedEqualsOwner248Count"], 114)
        self.assertEqual(acceptance["selectedEqualsOwner270Count"], 111)
        self.assertEqual(acceptance["primaryPositionMismatchedComponents"], 0)
        self.assertEqual(acceptance["primarySourceMismatchedComponents"], 0)
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
        self.assertIn("public", plan["policyMapping"])
        self.assertIn("unseen", plan["nextGate"])


if __name__ == "__main__":
    unittest.main()
