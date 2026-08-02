#!/usr/bin/env python3
"""Integrity tests for the primary-mesh fine-scan preregistration."""

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
        ANALYSIS_ROOT
        / "dynamic_allocation_primary_mesh_fine_scan_preregistration.json"
    ).read_text(encoding="utf-8")
)
CAPTURE_COMMIT = "c1808867bef8e5baa08e15d36e8611a2aa18b804"


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


class PrimaryMeshFineScanPreregistrationTests(unittest.TestCase):
    def test_frozen_matrix_matches_validator(self) -> None:
        capture = PREREGISTRATION["capture"]
        self.assertEqual(
            capture["sourceInterventionCounts"],
            {
                str(sample): len(surviving.fine_scan_interventions(sample))
                for sample in surviving.EXPECTED_SOURCE_SAMPLE_INDICES
            },
        )
        self.assertEqual(capture["totalInterventionCount"], 106)
        self.assertLess(
            capture["totalInterventionCount"],
            PREREGISTRATION["openedEvidence"][
                "observedMonolithicProcessCeiling"
            ],
        )
        self.assertEqual(
            capture["scanPhasesBySample"],
            {
                str(sample): phase
                for sample, phase in surviving.SCAN_PHASES_BY_SAMPLE.items()
            },
        )
        self.assertEqual(
            capture["scanXValuesBySample"],
            {
                str(sample): list(values[0])
                for sample, values in surviving.SCAN_VALUES_BY_SAMPLE.items()
            },
        )
        self.assertEqual(
            capture["scanYValuesBySample"],
            {
                str(sample): list(values[1])
                for sample, values in surviving.SCAN_VALUES_BY_SAMPLE.items()
            },
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
            / "analyze_dynamic_allocation_primary_mesh_fine_scan.py",
            "analyzerTestSHA256": ANALYSIS_ROOT
            / "test_analyze_dynamic_allocation_primary_mesh_fine_scan.py",
            "historicalPreregistrationTestSHA256": ANALYSIS_ROOT
            / "test_dynamic_allocation_surviving_path_threshold_preregistration.py",
            "priorPreregistrationSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_surviving_path_threshold_preregistration.json",
            "priorOpenedAnalysisResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_surviving_path_threshold_result.json",
            "inputClampTransferResultSHA256": ANALYSIS_ROOT
            / "transition_input_clamp_affine_transfer_result.json",
            "productionShaderSHA256": REPOSITORY_ROOT.parent / "shaders/frag.glsl",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                if name == "productionShaderSHA256":
                    self.assertEqual(sha256(path), expected[name])
                else:
                    self.assertEqual(committed_sha256(path), expected[name])

    def test_preregistration_denies_production_authority(self) -> None:
        self.assertFalse(PREREGISTRATION["acceptance"]["allowNumericTolerance"])
        self.assertFalse(PREREGISTRATION["acceptance"]["productionShaderAuthorized"])
        self.assertIn("production Walle parity", PREREGISTRATION["notClaimed"])


if __name__ == "__main__":
    unittest.main()
