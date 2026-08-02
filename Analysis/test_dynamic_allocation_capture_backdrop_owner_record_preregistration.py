#!/usr/bin/env python3
"""Integrity tests for the owner-record-vector capture preregistration."""

import hashlib
import json
import unittest
from pathlib import Path

import validate_dynamic_allocation_surviving_path_threshold as surviving


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
PREREGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_capture_backdrop_owner_record_preregistration.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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

    def test_schema_four_bounds_match_the_validator(self) -> None:
        capture = self.preregistration["capture"]
        acceptance = self.preregistration["acceptance"]
        self.assertEqual(capture["outerCaptureEvidenceSchemaVersion"], 8)
        self.assertEqual(capture["operandEvidenceSchemaVersion"], 4)
        self.assertEqual(capture["requiredReadMask"], "0x007fffff")
        self.assertEqual(
            capture["ownerObjectPrefixByteCount"],
            surviving.CAPTURE_BACKDROP_OWNER_OBJECT_PREFIX_BYTE_COUNT,
        )
        self.assertEqual(
            capture["ownerRecordByteCount"],
            surviving.CAPTURE_BACKDROP_OWNER_RECORD_BYTE_COUNT,
        )
        self.assertEqual(
            capture["ownerRecordMaximumCount"],
            surviving.CAPTURE_BACKDROP_OWNER_RECORD_MAXIMUM_COUNT,
        )
        self.assertEqual(
            capture["ownerRecordVectorMaximumByteCount"],
            surviving.CAPTURE_BACKDROP_OWNER_RECORD_VECTOR_BYTE_COUNT,
        )
        self.assertEqual(
            capture["sourceStateWindow"],
            [
                surviving.CAPTURE_BACKDROP_SOURCE_STATE_WINDOW_OFFSET,
                surviving.CAPTURE_BACKDROP_SOURCE_STATE_WINDOW_BYTE_COUNT,
            ],
        )
        self.assertTrue(acceptance["sourceKeyMustMatchAtLeastOneRecord"])
        self.assertEqual(acceptance["selectedRecordRule"], "lowest matching index")

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
            "ownerRegionAnalyzerSHA256": ANALYSIS_ROOT
            / "analyze_dynamic_allocation_capture_backdrop_owner_region.py",
            "ownerRegionAnalyzerTestSHA256": ANALYSIS_ROOT
            / "test_analyze_dynamic_allocation_capture_backdrop_owner_region.py",
            "ownerRegionResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_capture_backdrop_owner_region_result.json",
            "ownerRegionPreregistrationSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_capture_backdrop_owner_region_preregistration.json",
            "ownerRecordPreregistrationTestSHA256": Path(__file__),
            "productionShaderSHA256": REPOSITORY_ROOT.parent / "shaders/frag.glsl",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                self.assertEqual(sha256(path), expected[name])

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
