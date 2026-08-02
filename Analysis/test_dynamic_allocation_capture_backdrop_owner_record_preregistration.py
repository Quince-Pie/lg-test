#!/usr/bin/env python3
"""Integrity tests for the owner-record-vector capture preregistration."""

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
CAPTURE_HEAD_SHA = "8998bd56f34a749afa599197c153e58600a20d8f"
PREREGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_capture_backdrop_owner_record_preregistration.json"
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


class CaptureBackdropOwnerRecordPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration = json.loads(
            PREREGISTRATION_PATH.read_text(encoding="utf-8")
        )

    def test_opened_owner_region_run_is_a_prospective_pass(self) -> None:
        opened = self.preregistration["openedOwnerRegionEvidence"]
        self.assertEqual(opened["runID"], 30767931920)
        self.assertEqual(opened["workflowConclusion"], "success")
        self.assertTrue(opened["prospectiveGatePassed"])
        self.assertEqual(opened["completeLiveOperandCaptureCount"], 114)
        self.assertEqual(opened["selectedEqualsOwner248Count"], 114)
        self.assertEqual(opened["selectedEqualsOwner270Count"], 111)
        self.assertEqual(
            sha256(
                ANALYSIS_ROOT
                / "dynamic_allocation_capture_backdrop_owner_region_result.json"
            ),
            opened["ownerRegionAnalysisResultSHA256"],
        )

    def test_schema_four_bounds_preserve_the_falsified_registration(self) -> None:
        capture = self.preregistration["capture"]
        acceptance = self.preregistration["acceptance"]
        self.assertEqual(capture["outerCaptureEvidenceSchemaVersion"], 8)
        self.assertEqual(capture["operandEvidenceSchemaVersion"], 4)
        self.assertEqual(capture["requiredReadMask"], "0x007fffff")
        self.assertEqual(capture["ownerObjectPrefixByteCount"], 768)
        self.assertEqual(capture["ownerRecordPointerOffsets"], [0x50, 0x58, 0x60])
        self.assertEqual(capture["ownerRecordByteCount"], 0xD0)
        self.assertEqual(capture["ownerRecordMaximumCount"], 64)
        self.assertEqual(capture["ownerRecordVectorMaximumByteCount"], 13_312)
        self.assertEqual(capture["sourceStateWindow"], [0x18, 40])
        self.assertTrue(acceptance["sourceKeyMustMatchAtLeastOneRecord"])
        self.assertEqual(acceptance["selectedRecordRule"], "lowest matching index")

    def test_frozen_implementation_hashes_match_the_capture_commit(self) -> None:
        expected = self.preregistration["frozenImplementation"]
        historical_files = {
            "matrixBridgeHeaderSHA256": "Sources/GlassIntrospect/MatrixBridge.h",
            "matrixBridgeSourceSHA256": "Sources/GlassIntrospect/MatrixBridge.c",
            "swiftCaptureSHA256": "Sources/GlassIntrospect/main.swift",
            "workflowSHA256": ".github/workflows/transition-introspect.yml",
            "holdoutValidatorSHA256": (
                "Analysis/validate_dynamic_allocation_holdout.py"
            ),
            "validatorSHA256": (
                "Analysis/validate_dynamic_allocation_surviving_path_threshold.py"
            ),
            "validatorTestSHA256": (
                "Analysis/test_validate_dynamic_allocation_surviving_path_threshold.py"
            ),
            "ownerRegionAnalyzerSHA256": (
                "Analysis/analyze_dynamic_allocation_capture_backdrop_owner_region.py"
            ),
            "ownerRegionAnalyzerTestSHA256": (
                "Analysis/test_analyze_dynamic_allocation_capture_backdrop_owner_region.py"
            ),
            "ownerRegionResultSHA256": (
                "Analysis/dynamic_allocation_capture_backdrop_owner_region_result.json"
            ),
            "ownerRegionPreregistrationSHA256": (
                "Analysis/dynamic_allocation_capture_backdrop_owner_region_preregistration.json"
            ),
            "ownerRecordPreregistrationTestSHA256": (
                "Analysis/test_dynamic_allocation_capture_backdrop_owner_record_preregistration.py"
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

    def test_acceptance_remains_zero_tolerance_and_fails_closed(self) -> None:
        acceptance = self.preregistration["acceptance"]
        self.assertEqual(acceptance["operandCaptureCount"], 114)
        self.assertEqual(acceptance["ownerObjectPrefixExactCount"], 114)
        self.assertEqual(acceptance["ownerRecordVectorExactCount"], 114)
        self.assertEqual(acceptance["sourceStateWindowExactCount"], 114)
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
