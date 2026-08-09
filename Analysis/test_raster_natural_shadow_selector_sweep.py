#!/usr/bin/env python3
"""Tests for the finite natural shadow selector calibration inputs."""

import hashlib
import unittest

import numpy as np

import generate_raster_natural_shadow_selector_cases as case_generator
import generate_raster_natural_shadow_selector_witnesses as witnesses
import raster_tile_selector_model as arithmetic
import validate_raster_natural_shadow_selector_sweep as validator
import validate_raster_near_square_selector_sweep as near_square


class NaturalShadowSelectorSweepTests(unittest.TestCase):
    def test_case_generator_reproduces_frozen_domain(self) -> None:
        cases = case_generator.cases()
        self.assertEqual(cases.shape, (validator.CASE_COUNT, 2))
        self.assertEqual(
            hashlib.sha256(cases.tobytes()).hexdigest(),
            validator.CASE_SHA256,
        )

    def test_frozen_witnesses_distinguish_hard_cases(self) -> None:
        cases, assignment_bytes, multipliers = validator.load_frozen_inputs()
        assignments = np.frombuffer(assignment_bytes, dtype=np.uint8).reshape(
            validator.CASE_COUNT,
            validator.WITNESS_SLOT_COUNT,
        )
        for case_index in (0, 354, 621, 65_100):
            width_fixed, height_fixed = map(int, cases[case_index])
            combined = [tuple() for _ in witnesses.RECOVERY_OFFSETS]
            for witness_index in assignments[case_index]:
                records = witnesses.candidate_records(
                    width_fixed,
                    height_fixed,
                    multipliers[int(witness_index)],
                )
                combined = [
                    prefix + record
                    for prefix, record in zip(combined, records, strict=True)
                ]
            self.assertEqual(len(set(combined)), len(witnesses.RECOVERY_OFFSETS))

    def test_normalized_fallback_stays_inside_recovery_window(self) -> None:
        cases, _, _ = validator.load_frozen_inputs()
        table = arithmetic.load_selector_table()
        offsets = []
        for width_value, height_value in cases:
            width_fixed = int(width_value)
            height_fixed = int(height_value)
            offsets.append(
                validator.normalized_fallback_selector(
                    width_fixed,
                    height_fixed,
                    table,
                )
                - near_square.exact_floor_selector(
                    width_fixed,
                    height_fixed,
                )
            )
        self.assertEqual((min(offsets), max(offsets)), (-10, 7))


if __name__ == "__main__":
    unittest.main()
