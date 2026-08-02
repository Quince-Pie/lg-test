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

    def test_frozen_implementation_remains_historical(self) -> None:
        expected = PREREGISTRATION["frozenImplementation"]
        self.assertEqual(
            expected["lgTestCommitBeforeRegistration"],
            "3226bf4733290df8409d227bacd1379fa4d2b8be",
        )
        self.assertEqual(
            expected["validatorSHA256"],
            "e751223a16bf793b32ba10cec3f381b344e6e2cfce8aa4cf81e2593ccd9c3492",
        )
        self.assertEqual(
            expected["productionShaderSHA256"],
            sha256(REPOSITORY_ROOT.parent / "shaders/frag.glsl"),
        )
        for name, digest in expected.items():
            if name.endswith("SHA256"):
                with self.subTest(name=name):
                    self.assertEqual(len(digest), 64)
                    int(digest, 16)

    def test_preregistration_denies_production_authority(self) -> None:
        acceptance = PREREGISTRATION["acceptance"]
        self.assertFalse(acceptance["allowNumericTolerance"])
        self.assertFalse(acceptance["productionShaderAuthorized"])
        self.assertIn("production Walle parity", PREREGISTRATION["notClaimed"])


if __name__ == "__main__":
    unittest.main()
