#!/usr/bin/env python3
"""Tests for the exhaustive normalized-P25 selector calibration."""

import unittest

import numpy as np

import generate_raster_natural_shadow_selector_witnesses as scalar_witness
import generate_raster_p25_selector_cases as case_generator
import generate_raster_p25_selector_witnesses as witness
import validate_raster_p25_selector_sweep as validate


class RasterP25SelectorSweepTests(unittest.TestCase):
    def test_preregistered_inputs_are_frozen(self) -> None:
        preregistration, preflight = validate.load_preregistered_inputs()
        self.assertEqual(preregistration["role"], validate.ROLE)
        self.assertEqual(
            preflight["witness"]["candidateConstantDistinctCount"],
            witness.KEY_COUNT - 1,
        )

    def test_special_normalization_boundaries(self) -> None:
        self.assertEqual(validate.normalized_p25_key(1 << 34), 1 << 24)
        self.assertEqual(
            validate.selector_candidates_for_determinant(1 << 34, 1 << 24),
            (1 << 24, 1 << 24),
        )
        rounded_upper = (1 << 35) - 1
        self.assertEqual(validate.normalized_p25_key(rounded_upper), 1 << 25)
        self.assertEqual(
            validate.selector_candidates_for_determinant(
                rounded_upper,
                1 << 25,
            ),
            (1 << 24, 1 << 24),
        )

    def test_vector_witness_matches_scalar_model(self) -> None:
        indices = np.asarray(
            [0, 1, 17, 65_535, 1_048_575, 8_388_607, witness.KEY_COUNT - 1],
            dtype=np.int64,
        )
        keys = np.asarray(witness.KEY_LOWER + indices, dtype=np.uint64)
        widths, heights, _ = case_generator.representatives(keys.astype(np.int64))
        widths = widths.astype(np.uint64)
        heights = heights.astype(np.uint64)
        lower, upper = witness.reciprocal_candidates(keys)
        for reciprocals in (lower, upper):
            predicted = witness.candidate_constant_bits(
                widths,
                heights,
                reciprocals,
            )
            for slot, reciprocal in enumerate(reciprocals):
                context = scalar_witness.prediction_context(
                    int(widths[slot]),
                    int(heights[slot]),
                    witness.ENDPOINT_MULTIPLIER_BITS,
                    witness.SAMPLE_X,
                )
                expected = scalar_witness.prediction(
                    context,
                    reciprocal_index=int(reciprocal),
                )[0]
                self.assertEqual(int(predicted[slot]), expected)

    def test_frozen_controls_have_one_consistent_key_choice(self) -> None:
        bitmap = bytearray(witness.KEY_COUNT // 8)
        choices: dict[int, int] = {}
        for _, width, height, measured in validate.frozen_control_records():
            determinant = width * height
            key = validate.normalized_p25_key(determinant)
            lower, upper = validate.selector_candidates_for_determinant(
                determinant,
                key,
            )
            self.assertIn(measured, (lower, upper))
            if lower == upper:
                continue
            choice = int(measured == upper)
            prior = choices.setdefault(key, choice)
            self.assertEqual(prior, choice)
            bit_index = key - witness.KEY_LOWER
            bitmap[bit_index >> 3] |= choice << (bit_index & 7)
        result = validate.validate_controls(bytes(bitmap))
        self.assertTrue(result["passed"])
        self.assertEqual(result["caseCount"], validate.CONTROL_CASE_COUNT)
        self.assertEqual(
            result["uniqueNormalizedKeyCount"],
            validate.CONTROL_UNIQUE_KEY_COUNT,
        )


if __name__ == "__main__":
    unittest.main()
