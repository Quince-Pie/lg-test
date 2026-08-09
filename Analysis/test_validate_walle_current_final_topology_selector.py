#!/usr/bin/env python3
"""Tests for the frozen current-final topology-selector holdout."""

import hashlib
import json
from pathlib import Path
import unittest

import analyze_transition_geometry_corpus_local_macos_26_6_1 as model
import validate_walle_current_final_topology_selector as validator


ANALYSIS = Path(__file__).resolve().parent
PREREGISTRATION = ANALYSIS / "walle_current_final_topology_selector_preregistration.json"


class CurrentFinalTopologySelectorTests(unittest.TestCase):
    def test_negative_one_ulp_state_discriminates_old_rule(self) -> None:
        half_x, half_y, radius_x, radius_y = validator.topology_terms(
            494.0770568847656,
            494.0770568847656,
        )
        self.assertEqual(model.float32_bits(half_x), 0x437709DD)
        self.assertEqual(model.float32_bits(half_y), 0x437709DD)
        self.assertEqual(model.float32_bits(radius_x), 0x437709DC)
        self.assertEqual(model.float32_bits(radius_y), 0x437709DC)
        self.assertFalse(
            validator.predicts_border(half_x, half_y, radius_x, radius_y)
        )
        self.assertTrue(
            radius_x != half_x or radius_y != half_y or radius_x != radius_y
        )

    def test_positive_one_ulp_state_selects_border(self) -> None:
        terms = validator.topology_terms(494.0026550292969, 494.0026550292969)
        half_x, half_y, radius_x, radius_y = terms
        self.assertEqual(model.float32_bits(half_x), 0x43770057)
        self.assertEqual(model.float32_bits(radius_x), 0x43770058)
        self.assertTrue(
            validator.predicts_border(half_x, half_y, radius_x, radius_y)
        )

    def test_unequal_equal_round_trip_axes_select_border(self) -> None:
        terms = validator.topology_terms(402.49766540527344, 402.4976654052734)
        half_x, half_y, radius_x, radius_y = terms
        self.assertEqual(model.float32_bits(half_x), 0x43493FB4)
        self.assertEqual(model.float32_bits(half_y), 0x43493FB3)
        self.assertEqual(radius_x, half_x)
        self.assertEqual(radius_y, half_y)
        self.assertTrue(
            validator.predicts_border(half_x, half_y, radius_x, radius_y)
        )

    def test_preregistration_is_output_blind_and_zero_tolerance(self) -> None:
        preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
        self.assertTrue(preregistration["frozenBeforeAppleOutput"])
        self.assertEqual(preregistration["acceptance"]["comparisonTolerance"], 0)
        self.assertEqual(
            preregistration["frozenCandidate"]["prediction"]["indexCount"],
            6,
        )
        self.assertFalse(
            preregistration["claimBoundary"][
                "passingAloneEstablishesProductionWalleParity"
            ]
        )
        self.assertEqual(len(hashlib.sha256(PREREGISTRATION.read_bytes()).digest()), 32)
        repository = ANALYSIS.parent
        for relative, expected in preregistration["sourceSHA256"].items():
            self.assertEqual(
                hashlib.sha256((repository / relative).read_bytes()).hexdigest(),
                expected,
                relative,
            )


if __name__ == "__main__":
    unittest.main()
