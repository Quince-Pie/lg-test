#!/usr/bin/env python3
"""Tests for the failed live path-isolation run audit."""

import unittest

import analyze_dynamic_allocation_path_isolation_failed_run as audit


class PathIsolationFailedRunAuditTests(unittest.TestCase):
    def test_requested_delta_requires_the_declared_field_only(self) -> None:
        position = {
            "targetPresentInBaseAndObserved": True,
            "boundsOrigin": [0, 0],
            "position": [90, 0],
        }
        self.assertTrue(audit.requested_delta_survived("position", (90, 0), position))
        self.assertFalse(
            audit.requested_delta_survived("bounds-origin", (90, 0), position)
        )

    def test_missing_target_cannot_count_as_surviving(self) -> None:
        missing = {
            "targetPresentInBaseAndObserved": False,
            "boundsOrigin": None,
            "position": None,
        }
        self.assertFalse(
            audit.requested_delta_survived("position", (90, 0), missing)
        )

    def test_decoded_policy_removes_only_raw_payload_identity_fields(self) -> None:
        value = {
            "cropOrigin": [1, 2],
            "producerMesh": {
                "vertexDrawConsumedPayloadSHA256": "a" * 64,
                "vertexSnapshotPayloadByteCount": 4096,
                "primaryVertices": [[1.0, 2.0]],
            },
        }
        decoded = audit.decoded_policy(value)
        self.assertNotIn(
            "vertexDrawConsumedPayloadSHA256", decoded["producerMesh"]
        )
        self.assertNotIn(
            "vertexSnapshotPayloadByteCount", decoded["producerMesh"]
        )
        self.assertEqual(decoded["producerMesh"]["primaryVertices"], [[1.0, 2.0]])

    def test_classification_cannot_be_mistaken_for_acceptance(self) -> None:
        self.assertIn("failed", audit.CLASSIFICATION)
        self.assertIn("not-an-accepted", audit.CLASSIFICATION)

    def test_affine_expansion_rounds_multiply_before_add(self) -> None:
        encoded = audit.float32(1.0140576362609863)
        expanded = audit.affine_expanded_base(encoded)
        direct = audit.float_base(encoded)
        self.assertIsInstance(expanded, float)
        self.assertEqual(len(audit.float32_bits(expanded)), 8)
        self.assertNotEqual(audit.float32_bits(expanded), audit.float32_bits(direct))
        self.assertEqual(
            audit.float32_bits(expanded),
            audit.float32_bits(audit.mixed_base(encoded)),
        )


if __name__ == "__main__":
    unittest.main()
