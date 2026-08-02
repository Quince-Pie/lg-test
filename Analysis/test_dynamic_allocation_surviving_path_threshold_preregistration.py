#!/usr/bin/env python3
"""Integrity tests for the reduced surviving-path preregistration."""

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

import validate_dynamic_allocation_surviving_path_threshold as surviving
import validate_transition_input_clamp_probe as clamp


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
PREREGISTRATION = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_surviving_path_threshold_preregistration.json"
    ).read_text(encoding="utf-8")
)
CAPTURE_COMMIT = "e22d64258e5c28f27d5c90e4de4b258a554e450c"


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


class SurvivingPathThresholdPreregistrationTests(unittest.TestCase):
    def test_frozen_matrices_match_code(self) -> None:
        capture = PREREGISTRATION["capture"]
        self.assertEqual(
            capture["sourceInterventionCounts"],
            {
                "25": len(surviving.expected_interventions(25)),
                "31": len(surviving.expected_interventions(31)),
            },
        )
        self.assertEqual(capture["totalInterventionCount"], 72)
        self.assertEqual(
            PREREGISTRATION["inputClampTransfer"]["candidateName"],
            clamp.RECOVERED_TRANSFER_CANDIDATE,
        )

    def test_frozen_implementation_hashes_match_files(self) -> None:
        expected = PREREGISTRATION["frozenImplementation"]
        files = {
            "failedRunAnalyzerSHA256": ANALYSIS_ROOT
            / "analyze_dynamic_allocation_path_isolation_failed_run.py",
            "failedRunAnalyzerTestSHA256": ANALYSIS_ROOT
            / "test_analyze_dynamic_allocation_path_isolation_failed_run.py",
            "failedRunResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_path_isolation_failed_run_result.json",
            "inputClampValidatorSHA256": ANALYSIS_ROOT
            / "validate_transition_input_clamp_probe.py",
            "inputClampValidatorTestSHA256": ANALYSIS_ROOT
            / "test_validate_transition_input_clamp_probe.py",
            "productionShaderSHA256": REPOSITORY_ROOT.parent / "shaders/frag.glsl",
            "survivingPathAnalyzerSHA256": ANALYSIS_ROOT
            / "analyze_dynamic_allocation_surviving_path_threshold.py",
            "survivingPathAnalyzerTestSHA256": ANALYSIS_ROOT
            / "test_analyze_dynamic_allocation_surviving_path_threshold.py",
            "survivingPathValidatorSHA256": ANALYSIS_ROOT
            / "validate_dynamic_allocation_surviving_path_threshold.py",
            "survivingPathValidatorTestSHA256": ANALYSIS_ROOT
            / "test_validate_dynamic_allocation_surviving_path_threshold.py",
            "swiftCaptureSHA256": REPOSITORY_ROOT
            / "Sources/GlassIntrospect/main.swift",
            "workflowSHA256": REPOSITORY_ROOT
            / ".github/workflows/transition-introspect.yml",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                if name == "productionShaderSHA256":
                    self.assertEqual(sha256(path), expected[name])
                else:
                    self.assertEqual(committed_sha256(path), expected[name])

    def test_preregistration_denies_production_authority(self) -> None:
        self.assertFalse(PREREGISTRATION["acceptance"]["allowNumericTolerance"])
        self.assertIn("production Walle parity", PREREGISTRATION["notClaimed"])


if __name__ == "__main__":
    unittest.main()
