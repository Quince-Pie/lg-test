#!/usr/bin/env python3
"""Tests for the failed fixed-state allocation run audit."""

import unittest

import analyze_dynamic_allocation_fixed_state_run as audit


class FixedStateFailedRunAuditTests(unittest.TestCase):
    def test_semantic_policy_ignores_only_snapshot_storage_hashes(self) -> None:
        source = {
            "cropOrigin": [1, 2],
            "producerMesh": {
                "vertexPayloadSHA256": "a" * 64,
                "mvpPayloadSHA256": "b" * 64,
                "vertexDrawConsumedPayloadSHA256": "c" * 64,
                "primaryVertices": [[1, 2, 3, 4, 5, 6, 7, 8]],
            },
        }
        replay = {
            "cropOrigin": [1, 2],
            "producerMesh": {
                "vertexPayloadSHA256": "d" * 64,
                "mvpPayloadSHA256": "e" * 64,
                "vertexDrawConsumedPayloadSHA256": "c" * 64,
                "primaryVertices": [[1, 2, 3, 4, 5, 6, 7, 8]],
            },
        }
        self.assertEqual(audit.semantic_policy(source), audit.semantic_policy(replay))
        self.assertIn(
            "vertexDrawConsumedPayloadSHA256",
            audit.semantic_policy(source)["producerMesh"],
        )
        self.assertIn("vertexPayloadSHA256", source["producerMesh"])

    def test_edge_delta_is_signed_observed_minus_reference(self) -> None:
        reference = {
            "producerMesh": {
                "primaryVertices": [
                    [1, 2, 0, 0, 0, 0],
                    [5, 2, 0, 0, 0, 0],
                    [5, 7, 0, 0, 0, 0],
                    [1, 7, 0, 0, 0, 0],
                ]
            }
        }
        observed = {
            "producerMesh": {
                "primaryVertices": [
                    [2, 1, 0, 0, 0, 0],
                    [6, 1, 0, 0, 0, 0],
                    [6, 7, 0, 0, 0, 0],
                    [2, 7, 0, 0, 0, 0],
                ]
            }
        }
        self.assertEqual(audit.edge_delta(reference, observed), [1, -1, 1, 0])

    def test_classification_cannot_be_mistaken_for_acceptance(self) -> None:
        self.assertIn("failed", audit.CLASSIFICATION)
        self.assertIn("not-an-accepted", audit.CLASSIFICATION)


if __name__ == "__main__":
    unittest.main()
