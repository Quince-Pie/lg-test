#!/usr/bin/env python3
"""Integrity tests for the sample-31 repeat-scan preregistration."""

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
        / "dynamic_allocation_primary_mesh_sample31_repeat_preregistration.json"
    ).read_text(encoding="utf-8")
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PrimaryMeshSample31RepeatPreregistrationTests(unittest.TestCase):
    def test_frozen_matrix_matches_validator(self) -> None:
        capture = PREREGISTRATION["capture"]
        interventions = surviving.sample31_repeat_interventions(31)
        self.assertEqual(capture["sourceSampleIndices"], [31])
        self.assertEqual(
            capture["sourceInterventionCounts"], {"31": len(interventions)}
        )
        self.assertEqual(capture["totalInterventionCount"], 114)
        self.assertEqual(
            capture["totalInterventionCount"],
            PREREGISTRATION["openedEvidence"]["observedSuccessfulRecordCapacity"],
        )
        self.assertEqual(capture["scanXValues"], list(surviving.SAMPLE31_UNIT_X_VALUES))
        self.assertEqual(capture["scanYValues"], list(surviving.SAMPLE31_UNIT_Y_VALUES))
        self.assertEqual(
            capture["repeatXValues"], list(surviving.SAMPLE31_REPEAT_X_VALUES)
        )
        self.assertEqual(
            capture["repeatYValues"], list(surviving.SAMPLE31_REPEAT_Y_VALUES)
        )

    def test_frozen_record_layout_matches_intervention_order(self) -> None:
        interventions = surviving.sample31_repeat_interventions(31)
        layout = PREREGISTRATION["capture"]["recordLayout"]
        self.assertEqual(interventions[layout["initialBase"]]["name"], "base")
        self.assertEqual(interventions[layout["lateRepeatBase"]]["name"], "repeat-base")
        zero_indices = [
            index
            for index, intervention in enumerate(interventions)
            if intervention["delta"] == (0, 0)
        ]
        self.assertEqual(zero_indices, layout["zeroStateEquivalenceGroup"])
        self.assertEqual(layout["unitXInclusive"], [1, 49])
        self.assertEqual(layout["unitYInclusive"], [50, 90])
        self.assertEqual(layout["repeatXInclusive"], [92, 102])
        self.assertEqual(layout["repeatYInclusive"], [103, 113])

    def test_frozen_opened_evidence_hashes_match_canonical_results(self) -> None:
        opened = PREREGISTRATION["openedEvidence"]
        files = {
            "fineScanResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_primary_mesh_fine_scan_result.json",
            "normalizedResponseResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_primary_mesh_normalized_response_result.json",
            "pixelCenterTransferResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_primary_mesh_pixel_center_transfer_result.json",
            "withinRunRepeatResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_within_run_repeat_determinism_result.json",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                self.assertEqual(sha256(path), opened[name])

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
            / "analyze_dynamic_allocation_primary_mesh_sample31_repeat_scan.py",
            "analyzerTestSHA256": ANALYSIS_ROOT
            / "test_analyze_dynamic_allocation_primary_mesh_sample31_repeat_scan.py",
            "priorFineScanPreregistrationSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_primary_mesh_fine_scan_preregistration.json",
            "priorFineScanResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_primary_mesh_fine_scan_result.json",
            "priorNormalizedResponseResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_primary_mesh_normalized_response_result.json",
            "priorPixelCenterTransferResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_primary_mesh_pixel_center_transfer_result.json",
            "priorWithinRunRepeatResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_within_run_repeat_determinism_result.json",
            "productionShaderSHA256": REPOSITORY_ROOT.parent / "shaders/frag.glsl",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                self.assertEqual(sha256(path), expected[name])

    def test_preregistration_denies_production_authority(self) -> None:
        acceptance = PREREGISTRATION["acceptance"]
        self.assertEqual(acceptance["sameStateRepeatComparisonTolerance"], 0)
        self.assertFalse(acceptance["allowNumericTolerance"])
        self.assertFalse(acceptance["productionShaderAuthorized"])
        self.assertIn("production Walle parity", PREREGISTRATION["notClaimed"])


if __name__ == "__main__":
    unittest.main()
