#!/usr/bin/env python3
"""Tests for exact-state allocation intervention validation."""

import unittest

import validate_dynamic_allocation_fixed_state as fixed


class FixedStateContractTests(unittest.TestCase):
    def test_intervention_matrix_is_frozen(self) -> None:
        self.assertEqual(fixed.EXPECTED_SOURCE_SAMPLE_INDICES, (18, 23, 25, 28, 31))
        self.assertEqual(len(fixed.EXPECTED_TRANSLATIONS), 23)
        self.assertIn(("target-integer", (90, -134)), fixed.EXPECTED_TRANSLATIONS)
        self.assertIn(("target-half-even", (91, -133)), fixed.EXPECTED_TRANSLATIONS)
        self.assertIn(("target-half-signed", (-90, 135)), fixed.EXPECTED_TRANSLATIONS)

    def test_translation_changes_only_frozen_fields(self) -> None:
        source = [
            {
                "path": [1, 0, 1],
                "class": "CALayer",
                "bounds": [2.5, 3.5, 640, 640],
                "position": [2.5, 3.5],
                "backdropScale": None,
            },
            {
                "path": [1, 0, 0],
                "class": "CALayer",
                "bounds": [0, 0, 0, 0],
                "position": [0, 0],
                "backdropScale": None,
            },
        ]
        translated = fixed.translated_layer_states(source, (90, -134))
        self.assertEqual(translated[0]["bounds"], [92.5, -130.5, 640, 640])
        self.assertEqual(translated[0]["position"], [92.5, -130.5])
        self.assertEqual(translated[1], source[1])
        self.assertEqual(source[0]["bounds"], [2.5, 3.5, 640, 640])

    def test_result_cannot_be_classified_as_unseen_transfer(self) -> None:
        self.assertIn("calibration", fixed.CLASSIFICATION)
        self.assertNotIn("unseen", fixed.CLASSIFICATION)

    def test_zero_policy_ignores_only_unconsumed_snapshot_storage(self) -> None:
        first = {
            "cropOrigin": [4, 8],
            "producerMesh": {
                "vertexPayloadSHA256": "a" * 64,
                "mvpPayloadSHA256": "b" * 64,
                "vertexDrawConsumedPayloadSHA256": "c" * 64,
            },
        }
        second = {
            "cropOrigin": [4, 8],
            "producerMesh": {
                "vertexPayloadSHA256": "d" * 64,
                "mvpPayloadSHA256": "e" * 64,
                "vertexDrawConsumedPayloadSHA256": "c" * 64,
            },
        }
        self.assertEqual(fixed.semantic_policy(first), fixed.semantic_policy(second))
        second["producerMesh"]["vertexDrawConsumedPayloadSHA256"] = "f" * 64
        self.assertNotEqual(
            fixed.semantic_policy(first),
            fixed.semantic_policy(second),
        )


if __name__ == "__main__":
    unittest.main()
