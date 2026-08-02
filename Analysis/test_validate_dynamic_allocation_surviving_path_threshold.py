#!/usr/bin/env python3
"""Tests for the reduced surviving-path threshold validator."""

import unittest

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
        for sample in surviving.EXPECTED_SOURCE_SAMPLE_INDICES:
            for intervention in surviving.expected_interventions(sample)[1:]:
                self.assertEqual(intervention["path"], surviving.POSITION_PATH)
                self.assertEqual(intervention["mutation"], "position")

    def test_classification_denies_production_authority(self) -> None:
        self.assertIn("calibration", surviving.CLASSIFICATION)


if __name__ == "__main__":
    unittest.main()
