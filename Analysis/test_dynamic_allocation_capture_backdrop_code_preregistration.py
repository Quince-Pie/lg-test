#!/usr/bin/env python3
"""Integrity tests for the capture_backdrop code preregistration."""

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

import validate_dynamic_allocation_surviving_path_threshold as surviving


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
PREREGISTRATION = json.loads(
    (
        ANALYSIS_ROOT / "dynamic_allocation_capture_backdrop_code_preregistration.json"
    ).read_text(encoding="utf-8")
)
CAPTURE_COMMIT = "6eefa49e882fd6e23a89fe10ae443d2276f8f005"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def committed_sha256(path: Path) -> str:
    relative = path.relative_to(REPOSITORY_ROOT)
    content = subprocess.run(
        ["git", "show", f"{CAPTURE_COMMIT}:{relative.as_posix()}"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return hashlib.sha256(content).hexdigest()


class CaptureBackdropCodePreregistrationTests(unittest.TestCase):
    def test_frozen_capture_bounds_match_validator_constants(self) -> None:
        capture = PREREGISTRATION["capture"]
        self.assertEqual(
            capture["captureBackdropSymbol"], surviving.CAPTURE_BACKDROP_SYMBOL
        )
        self.assertEqual(
            capture["captureBackdropSymbolPrefixByteCount"],
            surviving.CAPTURE_BACKDROP_CODE_BYTE_COUNT,
        )
        self.assertEqual(
            capture["captureBackdropDecisionDirectCallRange"],
            list(surviving.CAPTURE_BACKDROP_DECISION_CALL_RANGE),
        )
        self.assertEqual(
            capture["captureBackdropKnownVertexBindingCallOffset"],
            surviving.CAPTURE_BACKDROP_VERTEX_BINDING_CALL_OFFSET,
        )
        self.assertEqual(
            capture["directCallTargetPrefixByteCount"],
            surviving.CAPTURE_BACKDROP_DIRECT_CALL_TARGET_CODE_BYTE_COUNT,
        )
        self.assertEqual(capture["totalInterventionCount"], 114)

    def test_frozen_opened_result_hash_matches_canonical_file(self) -> None:
        self.assertEqual(
            sha256(
                ANALYSIS_ROOT
                / "dynamic_allocation_primary_mesh_sample31_repeat_scan_result.json"
            ),
            PREREGISTRATION["openedEvidence"]["sample31RepeatScanResultSHA256"],
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
            "analyzerSHA256": ANALYSIS_ROOT
            / "analyze_dynamic_allocation_capture_backdrop_code.py",
            "analyzerTestSHA256": ANALYSIS_ROOT
            / "test_analyze_dynamic_allocation_capture_backdrop_code.py",
            "priorSample31PreregistrationSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_primary_mesh_sample31_repeat_preregistration.json",
            "priorSample31ResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_primary_mesh_sample31_repeat_scan_result.json",
            "priorSample31ResultTestSHA256": ANALYSIS_ROOT
            / "test_dynamic_allocation_primary_mesh_sample31_repeat_scan_result.py",
            "productionShaderSHA256": REPOSITORY_ROOT.parent / "shaders/frag.glsl",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                if name == "productionShaderSHA256":
                    self.assertEqual(sha256(path), expected[name])
                else:
                    self.assertEqual(committed_sha256(path), expected[name])

    def test_preregistration_fails_closed_and_denies_production_authority(
        self,
    ) -> None:
        acceptance = PREREGISTRATION["acceptance"]
        self.assertTrue(acceptance["producerCallSiteSchema5Required"])
        self.assertTrue(
            acceptance["everyDirectCallTargetPrefixMustMatchDeclaredLengthAndSHA256"]
        )
        self.assertFalse(acceptance["allowNumericTolerance"])
        self.assertFalse(acceptance["productionShaderAuthorized"])
        self.assertIn("production Walle parity", PREREGISTRATION["notClaimed"])


if __name__ == "__main__":
    unittest.main()
