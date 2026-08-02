#!/usr/bin/env python3
"""Integrity tests for the dual-owner-region capture preregistration."""

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

import validate_dynamic_allocation_surviving_path_threshold as surviving


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
CAPTURE_HEAD_SHA = "cab92e1411947cf6dc96313e6a343a7019994b0e"
PREREGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_capture_backdrop_owner_region_preregistration.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_at_capture_commit(relative_path: str) -> str | None:
    completed = subprocess.run(
        ["git", "show", f"{CAPTURE_HEAD_SHA}:{relative_path}"],
        cwd=REPOSITORY_ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return (
        hashlib.sha256(completed.stdout).hexdigest()
        if completed.returncode == 0
        else None
    )


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

    def test_frozen_implementation_hashes_match_the_capture_commit(self) -> None:
        expected = self.preregistration["frozenImplementation"]
        historical_files = {
            "matrixBridgeHeaderSHA256": "Sources/GlassIntrospect/MatrixBridge.h",
            "matrixBridgeSourceSHA256": "Sources/GlassIntrospect/MatrixBridge.c",
            "swiftCaptureSHA256": "Sources/GlassIntrospect/main.swift",
            "workflowSHA256": ".github/workflows/transition-introspect.yml",
            "validatorSHA256": (
                "Analysis/validate_dynamic_allocation_surviving_path_threshold.py"
            ),
            "validatorTestSHA256": (
                "Analysis/test_validate_dynamic_allocation_surviving_path_threshold.py"
            ),
            "failedRunAnalyzerSHA256": (
                "Analysis/analyze_dynamic_allocation_capture_backdrop_selected_region_failed_run.py"
            ),
            "failedRunAnalyzerTestSHA256": (
                "Analysis/test_analyze_dynamic_allocation_capture_backdrop_selected_region_failed_run.py"
            ),
            "failedRunResultSHA256": (
                "Analysis/dynamic_allocation_capture_backdrop_selected_region_failed_run_result.json"
            ),
            "selectedRegionPreregistrationSHA256": (
                "Analysis/dynamic_allocation_capture_backdrop_selected_region_preregistration.json"
            ),
            "selectedRegionPreregistrationTestSHA256": (
                "Analysis/test_dynamic_allocation_capture_backdrop_selected_region_preregistration.py"
            ),
            "ownerRegionPreregistrationTestSHA256": (
                "Analysis/test_dynamic_allocation_capture_backdrop_owner_region_preregistration.py"
            ),
        }
        available_historical_objects = 0
        for name, relative_path in historical_files.items():
            with self.subTest(name=name):
                self.assertRegex(expected[name], r"^[0-9a-f]{64}$")
                historical_sha = sha256_at_capture_commit(relative_path)
                if historical_sha is not None:
                    available_historical_objects += 1
                    self.assertEqual(historical_sha, expected[name])
        self.assertIn(
            available_historical_objects,
            {0, len(historical_files)},
        )
        self.assertEqual(
            sha256(REPOSITORY_ROOT.parent / "shaders/frag.glsl"),
            expected["productionShaderSHA256"],
        )

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
