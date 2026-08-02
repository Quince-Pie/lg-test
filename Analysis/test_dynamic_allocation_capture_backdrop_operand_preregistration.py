#!/usr/bin/env python3
"""Integrity tests for the live capture_backdrop operand preregistration."""

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
        / "dynamic_allocation_capture_backdrop_operand_preregistration.json"
    ).read_text(encoding="utf-8")
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CaptureBackdropOperandPreregistrationTests(unittest.TestCase):
    def test_capture_layout_matches_the_frozen_validator(self) -> None:
        capture = PREREGISTRATION["capture"]
        acceptance = PREREGISTRATION["acceptance"]
        self.assertEqual(capture["totalInterventionCount"], 114)
        self.assertEqual(capture["outerCaptureEvidenceSchemaVersion"], 5)
        self.assertEqual(
            capture["capturedStackFields"]["rect"][0],
            surviving.CAPTURE_BACKDROP_STACK_OFFSETS["rect"],
        )
        self.assertEqual(
            capture["capturedStackFields"]["affine"][0],
            surviving.CAPTURE_BACKDROP_STACK_OFFSETS["affine"],
        )
        self.assertEqual(
            acceptance["pinnedSymbolPrefixSHA256"],
            surviving.CAPTURE_BACKDROP_EXPECTED_SYMBOL_PREFIX_SHA256,
        )
        self.assertEqual(
            bytes.fromhex(acceptance["pinnedPrologueHex"]),
            surviving.CAPTURE_BACKDROP_EXPECTED_PROLOGUE,
        )
        self.assertEqual(acceptance["primaryPositionComponentCount"], 114 * 8)

    def test_opened_retry_remains_a_failed_prospective_gate(self) -> None:
        opened = PREREGISTRATION["openedRetryEvidence"]
        self.assertEqual(opened["workflowConclusion"], "failure")
        self.assertFalse(opened["prospectiveGatePassed"])
        self.assertEqual(opened["runID"], 30762428154)
        self.assertEqual(
            sha256(
                ANALYSIS_ROOT
                / "dynamic_allocation_capture_backdrop_code_retry_result.json"
            ),
            opened["retrospectiveCodeAnalysisResultSHA256"],
        )

    def test_frozen_implementation_hashes_match_files(self) -> None:
        expected = PREREGISTRATION["frozenImplementation"]
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
            "codeAnalyzerSHA256": ANALYSIS_ROOT
            / "analyze_dynamic_allocation_capture_backdrop_code.py",
            "codeAnalyzerTestSHA256": ANALYSIS_ROOT
            / "test_analyze_dynamic_allocation_capture_backdrop_code.py",
            "retrospectiveCodeResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_capture_backdrop_code_retry_result.json",
            "retryPreregistrationSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_capture_backdrop_code_retry_preregistration.json",
            "productionShaderSHA256": REPOSITORY_ROOT.parent
            / "shaders/frag.glsl",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                self.assertEqual(sha256(path), expected[name])

    def test_preregistration_denies_production_authority(self) -> None:
        acceptance = PREREGISTRATION["acceptance"]
        self.assertFalse(acceptance["allowNumericTolerance"])
        self.assertFalse(acceptance["productionShaderAuthorized"])
        self.assertIn("production Walle parity", PREREGISTRATION["notClaimed"])


if __name__ == "__main__":
    unittest.main()
