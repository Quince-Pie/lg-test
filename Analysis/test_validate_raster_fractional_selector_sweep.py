#!/usr/bin/env python3
"""Tests for the exhaustive fractional-width selector calibration."""

import hashlib
import json
import math
import random
import zlib
from pathlib import Path
import unittest

import numpy as np

import build_raster_fractional_selector_witness_map as witness_map
import model_raster_general_height_arithmetic as two_stage
import validate_raster_fractional_selector_sweep as sweep


class RasterFractionalSelectorSweepTests(unittest.TestCase):
    def test_witness_map_and_report_are_reproducible(self) -> None:
        actual_map, actual_report = witness_map.build()
        compressed = zlib.compress(actual_map, level=9)
        actual_report["compressedWitnessIndexBytes"] = len(compressed)
        actual_report["compressedWitnessIndexSha256"] = hashlib.sha256(
            compressed
        ).hexdigest()
        expected_map = sweep.WITNESS_INDEX_PATH.read_bytes()
        expected_report = json.loads(
            sweep.WITNESS_REPORT_PATH.read_text(encoding="utf-8")
        )
        self.assertEqual(actual_map, expected_map)
        self.assertEqual(actual_report, expected_report)

    def test_vector_product_matches_scalar_two_stage_model(self) -> None:
        generator = random.Random(0x5E_1E_C7)
        arithmetic = sweep.general_selector.factorization.top_left.arithmetic
        for significand in generator.sample(witness_map.witness_significands(), 8):
            numerator, numerator_exponent = witness_map.first_stage(significand)
            reciprocals = np.asarray(
                [generator.randrange(1 << 24, 1 << 25) for _ in range(64)],
                dtype=np.uint64,
            )
            actual = witness_map.vector_slope_bits(
                reciprocals,
                numerator_index=numerator,
                numerator_lsb_exponent=numerator_exponent,
            )
            expected: list[int] = []
            for reciprocal in reciprocals.tolist():
                coefficient, coefficient_exponent = two_stage.product_stage(
                    numerator,
                    numerator_exponent,
                    reciprocal,
                    witness_map.RECIPROCAL_LSB_EXPONENT,
                    output_bits=two_stage.SECOND_STAGE_OUTPUT_BITS,
                    truncation_bits=two_stage.SECOND_STAGE_TRUNCATION_BITS,
                    bias_units=two_stage.SECOND_STAGE_BIAS_UNITS,
                )
                expected.append(
                    arithmetic.float32_bits(
                        math.ldexp(coefficient, coefficient_exponent)
                    )
                )
            self.assertEqual(actual.tolist(), expected)

    def test_preregistration_and_sealed_controls_are_frozen(self) -> None:
        preregistration = sweep.load_preregistration()
        controls = sweep.sealed_controls()
        self.assertFalse(preregistration["observedAtPreregistration"])
        self.assertEqual(len(controls["canonical"]), 8_192)
        self.assertEqual(len(controls["generalValues"]), 32_768)
        self.assertEqual(len(controls["combined"]), 39_934)

    def test_candidate_acceptance_uses_every_frozen_pull(self) -> None:
        arithmetic = sweep.general_selector.factorization.top_left.arithmetic
        slopes = np.asarray([0x3800_0000, 0x3800_0001], dtype=np.uint32)
        constants = np.asarray([0x3E80_0000, 0x3E80_0000], dtype=np.uint32)
        observations = np.empty((2, len(witness_map.SAMPLE_OFFSETS)), dtype=np.uint32)
        for row, slope_bits in enumerate(slopes.tolist()):
            slope = arithmetic.float32_value(slope_bits)
            constant = arithmetic.float32_value(int(constants[row]))
            for slot, position in enumerate(witness_map.SAMPLE_OFFSETS):
                observations[row, slot] = arithmetic.float32_bits(
                    position * slope + constant
                )
        self.assertEqual(
            sweep.accepts_candidate(observations, slopes).tolist(),
            [True, True],
        )
        observations[1, -1] += 1
        self.assertEqual(
            sweep.accepts_candidate(observations, slopes).tolist(),
            [True, False],
        )

    def test_swift_probe_embeds_frozen_domain_and_hashes(self) -> None:
        source = (
            Path(__file__).parents[1]
            / "Sources"
            / "GlassRasterFractionalSelectorSweep"
            / "main.swift"
        ).read_text(encoding="utf-8")
        for expected in (
            "0x46000000u + caseIndex",
            sweep.PREREGISTRATION_SHA256,
            sweep.WITNESS_INDEX_SHA256,
            "instanceCount: casesInBatch",
        ):
            self.assertIn(expected, source)


if __name__ == "__main__":
    unittest.main()
