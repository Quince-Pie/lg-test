#!/usr/bin/env python3
"""Integrity tests for the frozen path-isolation preregistration."""

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

import validate_dynamic_allocation_path_isolation as path_isolation
import validate_transition_input_clamp_probe as clamp


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
PREREGISTRATION = json.loads(
    (
        ANALYSIS_ROOT / "dynamic_allocation_path_isolation_preregistration.json"
    ).read_text(encoding="utf-8")
)
CAPTURE_COMMIT = "d4925578608fd8a25a6bc85bd94593c79cef00b2"


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


class PathIsolationPreregistrationTests(unittest.TestCase):
    def test_intervention_and_input_clamp_matrices_match_code(self) -> None:
        capture = PREREGISTRATION["capture"]
        self.assertEqual(
            capture["sourceInterventionCounts"],
            {
                "25": len(path_isolation.expected_interventions(25)),
                "31": len(path_isolation.expected_interventions(31)),
            },
        )
        self.assertEqual(capture["totalInterventionCount"], 426)
        clamp_question = PREREGISTRATION["inputClampQuestion"]
        self.assertEqual(
            clamp_question["encodedCandidates"],
            list(clamp.ENCODED_CANDIDATES),
        )
        self.assertEqual(
            clamp_question["decodedCandidates"],
            list(clamp.DECODED_CANDIDATES),
        )

    def test_frozen_implementation_hashes_match_files(self) -> None:
        expected = PREREGISTRATION["frozenImplementation"]
        files = {
            "failedRunAuditResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_fixed_state_failed_run_result.json",
            "fixedStateValidatorSHA256": ANALYSIS_ROOT
            / "validate_dynamic_allocation_fixed_state.py",
            "holdoutValidatorSHA256": ANALYSIS_ROOT
            / "validate_dynamic_allocation_holdout.py",
            "inputClampValidatorSHA256": ANALYSIS_ROOT
            / "validate_transition_input_clamp_probe.py",
            "inputClampValidatorTestSHA256": ANALYSIS_ROOT
            / "test_validate_transition_input_clamp_probe.py",
            "pathIsolationAnalyzerSHA256": ANALYSIS_ROOT
            / "analyze_dynamic_allocation_path_isolation.py",
            "pathIsolationAnalyzerTestSHA256": ANALYSIS_ROOT
            / "test_analyze_dynamic_allocation_path_isolation.py",
            "pathIsolationValidatorSHA256": ANALYSIS_ROOT
            / "validate_dynamic_allocation_path_isolation.py",
            "pathIsolationValidatorTestSHA256": ANALYSIS_ROOT
            / "test_validate_dynamic_allocation_path_isolation.py",
            "swiftCaptureSHA256": REPOSITORY_ROOT
            / "Sources/GlassIntrospect/main.swift",
            "workflowSHA256": REPOSITORY_ROOT
            / ".github/workflows/transition-introspect.yml",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                self.assertEqual(committed_sha256(path), expected[name])
        self.assertEqual(
            sha256(REPOSITORY_ROOT.parent / "shaders/frag.glsl"),
            expected["productionShaderSHA256"],
        )

    def test_preregistration_denies_production_authority(self) -> None:
        self.assertIn(
            "production Walle parity",
            PREREGISTRATION["notClaimed"],
        )
        self.assertFalse(PREREGISTRATION["acceptance"]["allowTolerance"])


if __name__ == "__main__":
    unittest.main()
