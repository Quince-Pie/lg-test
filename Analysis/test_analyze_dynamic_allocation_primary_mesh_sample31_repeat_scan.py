#!/usr/bin/env python3
"""Tests for the sample-31 unit and same-process repeat analyzer."""

import unittest

import analyze_dynamic_allocation_primary_mesh_sample31_repeat_scan as analyzer


class PrimaryMeshSample31RepeatScanAnalyzerTests(unittest.TestCase):
    def test_all_equal_rejects_empty_groups(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty"):
            analyzer.all_equal([])

    def test_all_equal_compares_every_member(self) -> None:
        self.assertTrue(analyzer.all_equal([{"x": 1}] * 4))
        self.assertFalse(analyzer.all_equal([1, 1, 2]))

    def test_intervention_axis_uses_the_frozen_name(self) -> None:
        self.assertEqual(
            analyzer.intervention_axis(
                {"interventionName": "sample31-unit-a-position-x-positive-0"}
            ),
            "x",
        )
        self.assertEqual(
            analyzer.intervention_axis(
                {"interventionName": "repeat-a-position-y-negative-4"}
            ),
            "y",
        )
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            analyzer.intervention_axis({"interventionName": "repeat-base"})

    def test_repeat_keys_freeze_one_base_group_and_twenty_two_pairs(self) -> None:
        keys = analyzer.repeat_keys()
        self.assertEqual(len(keys), 23)
        self.assertEqual(keys[0], ("base", 0))
        self.assertEqual(keys[1], ("x", -12))
        self.assertEqual(keys[11], ("x", 36))
        self.assertEqual(keys[12], ("y", -4))
        self.assertEqual(keys[-1], ("y", 36))

    def test_transition_brackets_preserve_adjacent_observed_values(self) -> None:
        zero = (0.0, 0.0, 0.0, 0.0)
        changed = (1.0, 0.0, 0.0, 0.0)
        runs = analyzer.response_runs([(1, zero), (2, changed), (3, changed)])
        self.assertEqual(
            analyzer.transition_brackets(runs),
            [
                {
                    "lowerObservedValue": 1,
                    "upperObservedValue": 2,
                    "lowerResponse": list(zero),
                    "upperResponse": list(changed),
                }
            ],
        )

    def test_classification_denies_complete_policy(self) -> None:
        self.assertIn("not-a-complete-producer-mesh-policy", analyzer.CLASSIFICATION)


if __name__ == "__main__":
    unittest.main()
