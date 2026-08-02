#!/usr/bin/env python3
"""Tests for Darwin/CoreGraphics inputClamp probe validation."""

import unittest

import validate_transition_input_clamp_probe as clamp


class InputClampProbeContractTests(unittest.TestCase):
    def test_candidate_matrix_is_frozen(self) -> None:
        self.assertEqual(len(clamp.ENCODED_CANDIDATES), 4)
        self.assertEqual(len(clamp.DECODED_CANDIDATES), 6)
        self.assertEqual(len(clamp.EXPECTED_CANDIDATE_NAMES), 24)
        self.assertEqual(len(set(clamp.EXPECTED_CANDIDATE_NAMES)), 24)

    def test_float_evidence_checks_binary32_word(self) -> None:
        value, bits = clamp.float_evidence(
            {"value": 1.5, "bits": "3fc00000"},
            "fixture",
        )
        self.assertEqual(value, 1.5)
        self.assertEqual(bits, "3fc00000")
        with self.assertRaisesRegex(ValueError, "value and bits"):
            clamp.float_evidence(
                {"value": 1.5, "bits": "3fc00001"},
                "fixture",
            )

    def test_classification_does_not_claim_rendering_transfer(self) -> None:
        self.assertIn("candidate", clamp.CLASSIFICATION)
        self.assertNotIn("unseen-rendering-transfer;", clamp.CLASSIFICATION)


if __name__ == "__main__":
    unittest.main()
