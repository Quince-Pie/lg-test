#!/usr/bin/env python3
"""Tests for the prospective axis-isolated clipped-setup gate."""

import hashlib
from pathlib import Path
import unittest

import validate_raster_clipped_setup_transfer as clipped


class RasterClippedSetupTransferTests(unittest.TestCase):
    def test_preregistration_and_layout_are_frozen(self) -> None:
        preregistration = clipped.load_preregistration()
        self.assertFalse(preregistration["observedAtPreregistration"])
        self.assertEqual(
            preregistration["frozenLayout"],
            clipped.predicted_layout(),
        )
        self.assertEqual(
            hashlib.sha256(clipped.PREREGISTRATION_PATH.read_bytes()).hexdigest(),
            clipped.PREREGISTRATION_SHA256,
        )

    def test_every_geometry_has_the_preregistered_clip_axes_and_grid(self) -> None:
        for width in clipped.WIDTHS:
            for height in clipped.HEIGHTS:
                for variant_index, variant in enumerate(clipped.VARIANTS):
                    left, right, top, bottom = clipped.fixed_geometry(
                        width,
                        height,
                        variant_index,
                    )
                    self.assertEqual((right - left) % 2, 0)
                    self.assertEqual((bottom - top) % 2, 0)
                    self.assertEqual(
                        left < 0 or right > clipped.TARGET_WIDTH * 256,
                        variant["xClipped"],
                    )
                    self.assertEqual(
                        top < 0 or bottom > clipped.TARGET_HEIGHT * 256,
                        variant["yClipped"],
                    )
                    for sample_x in clipped.SAMPLE_XS:
                        sample_x_fixed = sample_x * 256 + 128
                        sample_y_fixed = clipped.SAMPLE_Y * 256 + 128
                        self.assertLess(left, sample_x_fixed)
                        self.assertLess(sample_x_fixed, right)
                        self.assertLess(top, sample_y_fixed)
                        self.assertLess(sample_y_fixed, bottom)

    def test_centered_endpoints_retain_the_exact_delta(self) -> None:
        arithmetic = clipped.factorization.top_left.arithmetic
        for width_index in (0, 1, clipped.WIDTH_COUNT - 1):
            for witness in clipped.WITNESS_SIGNIFICANDS:
                for variant_index, variant in enumerate(clipped.VARIANTS):
                    left_bits, right_bits = clipped.endpoint_bits(
                        width_index,
                        variant_index,
                        witness,
                    )
                    difference = arithmetic.float32_bits(
                        arithmetic.float32_value(right_bits)
                        - arithmetic.float32_value(left_bits)
                    )
                    self.assertEqual(
                        difference,
                        clipped.scaled_delta_bits(
                            width_index,
                            variant_index,
                            witness,
                        ),
                    )
                    self.assertEqual(left_bits != 0, variant["centeredVarying"])

    def test_synthetic_centered_planes_recover_exact_frozen_slopes(self) -> None:
        arithmetic = clipped.factorization.top_left.arithmetic
        selectors = clipped.load_selectors()
        cases = (
            (0, 0, 0),
            (0, clipped.HEIGHT_COUNT - 1, clipped.WITNESS_COUNT - 1),
            (1, 1, 1),
            (clipped.WIDTH_COUNT // 2, 2, 7),
            (
                clipped.WIDTH_COUNT - 1,
                clipped.HEIGHT_COUNT - 1,
                clipped.WITNESS_COUNT - 1,
            ),
        )
        for width_index, height_index, witness_index in cases:
            expected = clipped.expected_slope_bits(
                selectors,
                width_index=width_index,
                height_index=height_index,
                witness_index=witness_index,
            )
            slope = arithmetic.float32_value(expected)
            records = []
            for sample_x in clipped.SAMPLE_XS:
                tile_origin_x = sample_x - sample_x % 32
                constant = arithmetic.float32_value(
                    arithmetic.float32_bits((tile_origin_x - clipped.CENTER_X) * slope)
                )
                local_x = float(sample_x % 32)
                records.append(
                    (
                        arithmetic.float32_bits(local_x * slope + constant),
                        arithmetic.float32_bits(
                            (local_x + clipped.PULL_OFFSETS[1]) * slope + constant
                        ),
                    )
                )
            self.assertEqual(
                clipped.accepted_slopes(tuple(records), expected_bits=expected),
                (expected,),
            )

    def test_swift_probe_embeds_frozen_layout_and_valid_metal_literals(self) -> None:
        source = (
            Path(__file__).parents[1]
            / "Sources"
            / "GlassRasterClippedSetupTransfer"
            / "main.swift"
        ).read_text(encoding="utf-8")
        for digest in (
            clipped.PREREGISTRATION_SHA256,
            clipped.EXPECTED_BASE_SLOPE_SHA256,
            str(clipped.predicted_layout()["fixedGeometrySha256"]),
            str(clipped.predicted_layout()["endpointBitsSha256"]),
            str(clipped.predicted_layout()["coefficientVariantPredictionSha256"]),
        ):
            self.assertIn(digest, source)
        self.assertIn(r"* \(variantCount)u + batch.y;", source)
        self.assertIn(r"\(outputSlotCount)u * input.recordIndex", source)
        self.assertNotIn(r"(\(variantCount))u", source)


if __name__ == "__main__":
    unittest.main()
