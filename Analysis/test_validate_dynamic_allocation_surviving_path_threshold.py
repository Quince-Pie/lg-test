#!/usr/bin/env python3
"""Tests for the reduced surviving-path threshold validator."""

import unittest
from pathlib import Path

import validate_dynamic_allocation_surviving_path_threshold as surviving


class SurvivingPathThresholdValidatorTests(unittest.TestCase):
    def test_matrix_stays_below_observed_capture_ceiling(self) -> None:
        self.assertEqual(len(surviving.expected_interventions(25)), 67)
        self.assertEqual(len(surviving.expected_interventions(31)), 5)
        self.assertEqual(
            sum(
                len(surviving.expected_interventions(sample))
                for sample in surviving.EXPECTED_SOURCE_SAMPLE_INDICES
            ),
            72,
        )
        self.assertLess(72, 114)

    def test_fine_scan_uses_the_measured_brackets_and_remaining_budget(self) -> None:
        self.assertEqual(surviving.FINE_X_VALUES, tuple(range(80, 89)))
        self.assertEqual(surviving.FINE_Y_VALUES, tuple(range(64, 97)))
        self.assertEqual(len(surviving.fine_scan_interventions(25)), 43)
        self.assertEqual(len(surviving.fine_scan_interventions(31)), 63)
        self.assertEqual(
            sum(
                len(surviving.fine_scan_interventions(sample))
                for sample in surviving.EXPECTED_SOURCE_SAMPLE_INDICES
            ),
            106,
        )
        self.assertLess(106, 114)

    def test_cross_axis_scan_repeats_all_four_strong_controls(self) -> None:
        deltas = {
            intervention["delta"]
            for intervention in surviving.fine_scan_interventions(31)
        }
        self.assertTrue(
            {delta for _, delta in surviving.STRONG_DELTAS}.issubset(deltas)
        )

    def test_swift_uses_schema_three_only_for_the_fine_scan(self) -> None:
        source = (
            Path(__file__).parents[1]
            / "Sources"
            / "GlassIntrospect"
            / "main.swift"
        ).read_text(encoding="utf-8")
        fixed_block, path_block = source.split(
            "private func transitionFixedStateAllocationEvidence", maxsplit=1
        )[1].split(
            "private func transitionPathIsolationAllocationEvidence", maxsplit=1
        )
        path_block = path_block.split(
            "private func transitionFloatEvidence", maxsplit=1
        )[0]
        self.assertIn('"schemaVersion": 2', fixed_block)
        self.assertNotIn('"schemaVersion": 3', fixed_block)
        self.assertIn('"schemaVersion": 3', path_block)
        self.assertIn('"scanXValuesBySample"', path_block)
        self.assertIn('"scanYValuesBySample"', path_block)

    def test_live_baseline_changes_only_deepest_position(self) -> None:
        states = [
            {"path": [], "position": [0, 0], "bounds": [0, 0, 10, 10]},
            {
                "path": list(surviving.POSITION_PATH),
                "position": [3.5, -2.0],
                "bounds": [0, 0, 4, 4],
            },
        ]
        changed = surviving.live_baseline_states(states, (90, -134))
        self.assertEqual(changed[0], states[0])
        self.assertEqual(changed[1]["position"], [93.5, -136.0])
        self.assertEqual(changed[1]["bounds"], states[1]["bounds"])
        self.assertEqual(states[1]["position"], [3.5, -2.0])

    def test_every_nonbase_intervention_targets_only_position(self) -> None:
        for builder in (
            surviving.expected_interventions,
            surviving.fine_scan_interventions,
        ):
            for sample in surviving.EXPECTED_SOURCE_SAMPLE_INDICES:
                for intervention in builder(sample)[1:]:
                    self.assertEqual(intervention["path"], surviving.POSITION_PATH)
                    self.assertEqual(intervention["mutation"], "position")

    def test_classification_denies_production_authority(self) -> None:
        self.assertIn("calibration", surviving.CLASSIFICATION)


if __name__ == "__main__":
    unittest.main()
