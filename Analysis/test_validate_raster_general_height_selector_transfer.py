#!/usr/bin/env python3
"""Tests for two-stage arithmetic and selector-transfer preregistration."""

import hashlib
import json
import zlib
from pathlib import Path
import unittest

import explore_exact_general_height_numerator as previous
import model_raster_general_height_arithmetic as two_stage
import recover_raster_general_height_reciprocals as recovery
import validate_raster_general_height_selector_transfer as selector


class RasterGeneralHeightSelectorTransferTests(unittest.TestCase):
    def test_swift_probe_embeds_frozen_shader_strides_and_hashes(self) -> None:
        source = (
            Path(__file__).parents[1]
            / "Sources"
            / "GlassRasterGeneralHeightSelectorTransfer"
            / "main.swift"
        ).read_text(encoding="utf-8")
        lines = source.splitlines()
        self.assertIn(
            r"    const uint localCaseIndex = instanceID / \(witnessCount)u;",
            lines,
        )
        self.assertIn(
            r"        \(samplePositionCount)u * input.recordIndex + input.outputSlot",
            lines,
        )
        self.assertNotIn(
            "    const uint localCaseIndex = instanceID / witnessCount;",
            lines,
        )
        for digest in (
            selector.PREREGISTRATION_SHA256,
            selector.MASK_RAW_SHA256,
            str(selector.predicted_layout()["caseDeltaBitsSha256"]),
            str(selector.predicted_layout()["uniquePredictionSha256"]),
        ):
            self.assertIn(digest, source)

    def test_preregistration_and_recovered_candidates_are_frozen(self) -> None:
        preregistration = selector.load_preregistration()
        self.assertEqual(
            preregistration["freshWitnessSelection"]["significands"],
            list(selector.WITNESS_SIGNIFICANDS),
        )
        masks, report = recovery.recover()
        compressed = zlib.compress(masks, level=9)
        report["compressedCandidateMaskBytes"] = len(compressed)
        report["compressedCandidateMaskSha256"] = hashlib.sha256(
            compressed
        ).hexdigest()
        expected = json.loads(
            Path("Analysis/raster_general_height_reciprocal_recovery.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(report, expected)
        self.assertEqual(compressed, selector.MASK_PATH.read_bytes())

    def test_two_stage_model_matches_old_exact_normalized_corpus(self) -> None:
        widths = selector.factorization.low_exponent.factorized.geometry_widths()
        shifts = (
            selector.factorization.low_exponent.factorized.delta_exponent_shift_bits()
        )
        witness_bits = selector.factorization.low_exponent.arithmetic.witness_delta_bits()
        canonical = (
            selector.factorization.low_exponent.factorized.canonical_reciprocals()
        )
        slopes = previous.recovered_slopes()
        match_count = 0
        for width_index, width in enumerate(widths):
            for geometry_index, height in enumerate(previous.HEIGHTS):
                determinant = width * height
                normalized = previous.exact_normalized_class(determinant)
                if normalized is None:
                    continue
                normalized_class, _ = normalized
                reciprocal = canonical[normalized_class - 8_192]
                for witness_index, delta_bits in enumerate(witness_bits):
                    actual = slopes[
                        (width_index * len(witness_bits) + witness_index)
                        * len(previous.HEIGHTS)
                        + geometry_index
                    ]
                    for bias in two_stage.FIRST_STAGE_BIAS_UNITS:
                        self.assertEqual(
                            two_stage.slope_bits(
                                delta_bits - shifts[width_index],
                                opposite_edge=height,
                                determinant=determinant,
                                reciprocal_index=reciprocal,
                                first_stage_bias_units=bias,
                            ),
                            actual,
                        )
                    match_count += 1
        self.assertEqual(match_count, 6_776)

    def test_every_frozen_candidate_slope_is_observationally_unique(self) -> None:
        masks = selector.load_candidate_masks()
        arithmetic = selector.factorization.top_left.arithmetic
        positions = tuple(
            position
            for x in selector.SAMPLE_XS
            for position in (float(x), float(x) + 0.9375)
        )
        candidate_path_count = 0
        for width_index, width in enumerate(selector.WIDTHS):
            for height_index, height in enumerate(selector.HEIGHTS):
                case_index = width_index * selector.HEIGHT_COUNT + height_index
                determinant = width * height
                reciprocals = selector.candidate_reciprocals(
                    masks,
                    case_index=case_index,
                    determinant=determinant,
                )
                for significand in selector.WITNESS_SIGNIFICANDS:
                    delta_bits = selector.scaled_delta_bits(width_index, significand)
                    direct_bits = arithmetic.float32_bits(
                        arithmetic.float32_value(delta_bits) / width
                    )
                    for reciprocal in reciprocals:
                        expected = two_stage.slope_bits(
                            delta_bits,
                            opposite_edge=height,
                            determinant=determinant,
                            reciprocal_index=reciprocal,
                            first_stage_bias_units=(
                                two_stage.FIRST_STAGE_BIAS_UNITS[0]
                            ),
                        )
                        slope = arithmetic.float32_value(expected)
                        observations = tuple(
                            arithmetic.float32_bits(position * slope)
                            for position in positions
                        )
                        accepted = tuple(
                            direct_bits + offset
                            for offset in range(
                                -selector.CANDIDATE_RADIUS_FLOAT_ULPS,
                                selector.CANDIDATE_RADIUS_FLOAT_ULPS + 1,
                            )
                            if all(
                                arithmetic.float32_bits(
                                    position
                                    * arithmetic.float32_value(direct_bits + offset)
                                )
                                == observation
                                for position, observation in zip(
                                    positions,
                                    observations,
                                    strict=True,
                                )
                            )
                        )
                        self.assertEqual(accepted, (expected,))
                        candidate_path_count += 1
        self.assertEqual(candidate_path_count, 459_130)


if __name__ == "__main__":
    unittest.main()
