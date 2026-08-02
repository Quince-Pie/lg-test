#!/usr/bin/env python3
"""Tests for the same-run allocation-repeat determinism analyzer."""

import unittest

import analyze_dynamic_allocation_within_run_repeat_determinism as analyzer


class WithinRunRepeatDeterminismAnalyzerTests(unittest.TestCase):
    def test_repeat_pairs_are_same_sample_controls_with_order_separation(self) -> None:
        self.assertEqual(
            analyzer.EXPECTED_REPEAT_GROUPS,
            {
                (25, (-90, 0)): (1, 9),
                (25, (90, 0)): (2, 29),
                (25, (0, -134)): (3, 38),
                (25, (0, 134)): (4, 62),
            },
        )
        self.assertEqual(
            max(second - first for first, second in analyzer.EXPECTED_REPEAT_GROUPS.values()),
            58,
        )

    def test_projection_rejects_missing_consumed_field(self) -> None:
        with self.assertRaisesRegex(ValueError, "fields are missing"):
            analyzer.projection({}, analyzer.DRAW_CONSUMED_FIELDS)

    def test_full_snapshot_hashes_are_outside_consumed_projection(self) -> None:
        left = {field: field for field in analyzer.DRAW_CONSUMED_FIELDS}
        right = dict(left)
        left["vertexPayloadSHA256"] = "a"
        right["vertexPayloadSHA256"] = "b"
        self.assertEqual(
            analyzer.projection(left, analyzer.DRAW_CONSUMED_FIELDS),
            analyzer.projection(right, analyzer.DRAW_CONSUMED_FIELDS),
        )

    def test_classification_denies_exact_policy_recovery(self) -> None:
        self.assertIn("not-an-exact-policy-recovery", analyzer.CLASSIFICATION)


if __name__ == "__main__":
    unittest.main()
