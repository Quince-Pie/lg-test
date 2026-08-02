#!/usr/bin/env python3
"""Integrity tests for the selected-region capture preregistration."""

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

import validate_dynamic_allocation_surviving_path_threshold as surviving


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
CAPTURE_HEAD_SHA = "ddbd6dfa13fe5cee468acd378e3cdc3acd94fd12"
PREREGISTRATION = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_capture_backdrop_selected_region_preregistration.json"
    ).read_text(encoding="utf-8")
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_at_commit(relative_path: str) -> str | None:
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


class CaptureBackdropSelectedRegionPreregistrationTests(unittest.TestCase):
    def test_opened_operand_run_remains_a_failed_prospective_gate(self) -> None:
        opened = PREREGISTRATION["openedOperandEvidence"]
        self.assertEqual(opened["runID"], 30764095287)
        self.assertEqual(opened["workflowConclusion"], "failure")
        self.assertFalse(opened["prospectiveGatePassed"])
        self.assertEqual(
            sha256(
                ANALYSIS_ROOT
                / "dynamic_allocation_capture_backdrop_operand_failed_run_result.json"
            ),
            opened["failedRunAnalysisResultSHA256"],
        )

    def test_region_layout_and_byte_gates_match_the_validator(self) -> None:
        capture = PREREGISTRATION["capture"]
        acceptance = PREREGISTRATION["acceptance"]
        stack = capture["capturedStackFields"]
        self.assertEqual(capture["outerCaptureEvidenceSchemaVersion"], 6)
        self.assertEqual(capture["operandEvidenceSchemaVersion"], 2)
        self.assertEqual(capture["requiredReadMask"], "0x0001ffff")
        self.assertEqual(stack["rendererPointer"][0], 0x228)
        self.assertEqual(stack["regionHandle"][0], 0x2A0)
        self.assertEqual(stack["regionIterator"][0], 0x3C0)
        self.assertEqual(
            acceptance["pinnedShapeIteratorPrefixSHA256"],
            surviving.CAPTURE_BACKDROP_EXPECTED_REGION_ITERATE_PREFIX_SHA256,
        )
        self.assertEqual(
            acceptance["pinnedShapeIteratorSymbol"],
            surviving.CAPTURE_BACKDROP_REGION_ITERATE_SYMBOL,
        )
        self.assertEqual(
            PREREGISTRATION["openedCodeFacts"]["selectedRegionIteratorCallOffset"],
            surviving.CAPTURE_BACKDROP_REGION_ITERATE_CALL_OFFSET,
        )

    def test_frozen_implementation_hashes_match_the_capture_commit(self) -> None:
        expected = PREREGISTRATION["frozenImplementation"]
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
                "Analysis/analyze_dynamic_allocation_capture_backdrop_operand_failed_run.py"
            ),
            "failedRunAnalyzerTestSHA256": (
                "Analysis/test_analyze_dynamic_allocation_capture_backdrop_operand_failed_run.py"
            ),
            "failedRunResultSHA256": (
                "Analysis/dynamic_allocation_capture_backdrop_operand_failed_run_result.json"
            ),
            "operandPreregistrationSHA256": (
                "Analysis/dynamic_allocation_capture_backdrop_operand_preregistration.json"
            ),
        }
        available_historical_objects = 0
        for name, relative_path in historical_files.items():
            with self.subTest(name=name):
                self.assertRegex(expected[name], r"^[0-9a-f]{64}$")
                historical_sha = sha256_at_commit(relative_path)
                if historical_sha is not None:
                    available_historical_objects += 1
                    self.assertEqual(historical_sha, expected[name])
        self.assertIn(available_historical_objects, {0, len(historical_files)})
        self.assertEqual(
            sha256(REPOSITORY_ROOT.parent / "shaders/frag.glsl"),
            expected["productionShaderSHA256"],
        )

    def test_acceptance_is_bitwise_and_denies_production_authority(self) -> None:
        acceptance = PREREGISTRATION["acceptance"]
        self.assertEqual(acceptance["selectedRegionConsumedRectangleExactCount"], 114)
        self.assertEqual(acceptance["primaryPositionMismatchedComponents"], 0)
        self.assertEqual(acceptance["primarySourceMismatchedComponents"], 0)
        self.assertFalse(acceptance["allowNumericTolerance"])
        self.assertFalse(acceptance["productionShaderAuthorized"])
        self.assertIn("production Walle parity", PREREGISTRATION["notClaimed"])


if __name__ == "__main__":
    unittest.main()
