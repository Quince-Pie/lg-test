#!/usr/bin/env python3
"""Integrity tests for the live-stack-qualified code-capture retry."""

import hashlib
import json
import unittest
from pathlib import Path

import validate_dynamic_allocation_surviving_path_threshold as surviving


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
PREREGISTRATION = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_capture_backdrop_code_retry_preregistration.json"
    ).read_text(encoding="utf-8")
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CaptureBackdropCodeRetryPreregistrationTests(unittest.TestCase):
    def test_retry_changes_only_the_selector_and_latch(self) -> None:
        correction = PREREGISTRATION["frozenCorrection"]
        self.assertIn("selector only", correction["scope"])
        self.assertIn("capture_backdrop", correction["prequalificationRule"])
        self.assertIn("producerGeometryCallSiteCaptured", correction["latchRule"])
        self.assertEqual(PREREGISTRATION["capture"]["totalInterventionCount"], 114)
        self.assertEqual(
            PREREGISTRATION["capture"]["captureBackdropDecisionDirectCallRange"],
            list(surviving.CAPTURE_BACKDROP_DECISION_CALL_RANGE),
        )

    def test_failed_run_is_retained_as_failed(self) -> None:
        failed = PREREGISTRATION["openedFailedEvidence"]
        self.assertFalse(failed["frozenGatePassed"])
        self.assertEqual(failed["captureBackdropCodeCaptureCount"], 0)
        self.assertEqual(
            sha256(
                ANALYSIS_ROOT
                / "dynamic_allocation_capture_backdrop_code_failed_run_result.json"
            ),
            failed["failedRunResultSHA256"],
        )

    def test_frozen_implementation_hashes_match_files(self) -> None:
        expected = PREREGISTRATION["frozenImplementation"]
        files = {
            "swiftCaptureSHA256": REPOSITORY_ROOT
            / "Sources/GlassIntrospect/main.swift",
            "workflowSHA256": REPOSITORY_ROOT
            / ".github/workflows/transition-introspect.yml",
            "validatorSHA256": ANALYSIS_ROOT
            / "validate_dynamic_allocation_surviving_path_threshold.py",
            "validatorTestSHA256": ANALYSIS_ROOT
            / "test_validate_dynamic_allocation_surviving_path_threshold.py",
            "codeAnalyzerSHA256": ANALYSIS_ROOT
            / "analyze_dynamic_allocation_capture_backdrop_code.py",
            "codeAnalyzerTestSHA256": ANALYSIS_ROOT
            / "test_analyze_dynamic_allocation_capture_backdrop_code.py",
            "failedRunAnalyzerSHA256": ANALYSIS_ROOT
            / "analyze_dynamic_allocation_capture_backdrop_code_failed_run.py",
            "failedRunAnalyzerTestSHA256": ANALYSIS_ROOT
            / "test_analyze_dynamic_allocation_capture_backdrop_code_failed_run.py",
            "originalCodePreregistrationSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_capture_backdrop_code_preregistration.json",
            "failedRunResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_capture_backdrop_code_failed_run_result.json",
            "priorSample31ResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_primary_mesh_sample31_repeat_scan_result.json",
            "productionShaderSHA256": REPOSITORY_ROOT.parent / "shaders/frag.glsl",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                self.assertEqual(sha256(path), expected[name])

    def test_retry_still_denies_production_authority(self) -> None:
        acceptance = PREREGISTRATION["acceptance"]
        self.assertFalse(acceptance["allowNumericTolerance"])
        self.assertFalse(acceptance["productionShaderAuthorized"])
        self.assertIn("production Walle parity", PREREGISTRATION["notClaimed"])


if __name__ == "__main__":
    unittest.main()
