#!/usr/bin/env python3
"""Tests for live-read-back path-isolation allocation validation."""

import unittest

import validate_dynamic_allocation_path_isolation as path_isolation


class PathIsolationContractTests(unittest.TestCase):
    def test_intervention_counts_are_frozen(self) -> None:
        self.assertEqual(
            len(path_isolation.expected_interventions(25)),
            337,
        )
        self.assertEqual(
            len(path_isolation.expected_interventions(31)),
            89,
        )
        self.assertEqual(
            len(path_isolation.expected_interventions(25))
            + len(path_isolation.expected_interventions(31)),
            426,
        )

    def test_single_field_mutation_does_not_touch_sibling_state(self) -> None:
        states = [
            {
                "path": [1, 0, 1, 0],
                "bounds": [2.5, 3.5, 640, 640],
                "position": [4.5, 5.5],
            },
            {
                "path": [1, 0, 1, 1],
                "bounds": [7.5, 8.5, 640, 640],
                "position": [9.5, 10.5],
            },
        ]
        intervention = {
            "path": (1, 0, 1, 0),
            "mutation": "bounds-origin",
            "delta": (90, -134),
        }
        result = path_isolation.requested_layer_states(states, intervention)
        self.assertEqual(result[0]["bounds"], [92.5, -130.5, 640, 640])
        self.assertEqual(result[0]["position"], [4.5, 5.5])
        self.assertEqual(result[1], states[1])
        self.assertEqual(states[0]["bounds"], [2.5, 3.5, 640, 640])

    def test_classification_is_calibration_not_transfer(self) -> None:
        self.assertIn("calibration", path_isolation.CLASSIFICATION)
        self.assertNotIn("unseen", path_isolation.CLASSIFICATION)


if __name__ == "__main__":
    unittest.main()
