#!/usr/bin/env python3
"""Tests for the fixed-post-clip arithmetic discriminator."""

import hashlib
from pathlib import Path
import struct
import unittest

import validate_raster_clip_arithmetic_discriminator as discriminator


class RasterClipArithmeticDiscriminatorTests(unittest.TestCase):
    def test_preregistration_and_layout_are_frozen(self) -> None:
        preregistration = discriminator.load_preregistration()
        self.assertFalse(preregistration["observedAtPreregistration"])
        self.assertEqual(
            preregistration["frozenLayout"],
            discriminator.predicted_layout(),
        )
        self.assertEqual(
            hashlib.sha256(discriminator.PREREGISTRATION_PATH.read_bytes()).hexdigest(),
            discriminator.PREREGISTRATION_SHA256,
        )

    def test_catalog_covers_every_axis_sign_scale_span_and_distance(self) -> None:
        cases, groups = discriminator.case_catalog()
        self.assertEqual(len(groups), 16)
        self.assertEqual(len(cases), 131_088)
        self.assertEqual(
            {group.plane for group in groups},
            {"left", "right", "top", "bottom"},
        )
        for group in groups:
            group_cases = cases[group.first_case : group.first_case + group.case_count]
            self.assertEqual(len(group_cases), discriminator.DISTANCE_COUNT)
            self.assertEqual(group_cases[0].distance_fixed, 0)
            self.assertEqual(
                group_cases[-1].distance_fixed,
                discriminator.DISTANCE_FIXED_MAX,
            )

    def test_clipping_every_outside_case_produces_one_fixed_rectangle(self) -> None:
        cases, groups = discriminator.case_catalog()
        for group in groups:
            expected = None
            for case in cases[
                group.first_case + 1 : group.first_case + group.case_count
            ]:
                left, right, top, bottom = case.geometry_fixed
                if group.plane == "left":
                    left = group.guard_fixed
                elif group.plane == "right":
                    right = group.guard_fixed
                elif group.plane == "top":
                    top = group.guard_fixed
                else:
                    bottom = group.guard_fixed
                clipped = (left, right, top, bottom)
                if expected is None:
                    expected = clipped
                self.assertEqual(clipped, expected)
            self.assertIsNotNone(expected)

    def test_samples_share_one_tile_and_are_strictly_interior(self) -> None:
        cases, groups = discriminator.case_catalog()
        for group in groups:
            along = [sample[0 if group.axis == "x" else 1] for sample in group.samples]
            self.assertEqual([value % 32 for value in along], [0, 15, 31])
            self.assertEqual(len({value // 32 for value in along}), 1)
            control = cases[group.first_case]
            left, right, top, bottom = control.geometry_fixed
            for x, y in group.samples:
                x_fixed = x * discriminator.UNITS_PER_PIXEL + 128
                y_fixed = y * discriminator.UNITS_PER_PIXEL + 128
                self.assertLess(left, x_fixed)
                self.assertLess(x_fixed, right)
                self.assertLess(top, y_fixed)
                self.assertLess(y_fixed, bottom)

    def test_centered_witness_endpoints_reconstruct_every_delta(self) -> None:
        for delta_bits in discriminator.DELTA_BITS:
            half_bits = delta_bits - 0x0080_0000
            negative = struct.unpack("<f", struct.pack("<I", half_bits | 0x8000_0000))[
                0
            ]
            positive = struct.unpack("<f", struct.pack("<I", half_bits))[0]
            reconstructed = struct.unpack("<I", struct.pack("<f", positive - negative))[
                0
            ]
            self.assertEqual(reconstructed, delta_bits)

    def test_swift_probe_embeds_frozen_identity_and_stride(self) -> None:
        source = (
            Path(__file__).parents[1]
            / "Sources"
            / "GlassRasterClipArithmeticDiscriminator"
            / "main.swift"
        ).read_text(encoding="utf-8")
        layout = discriminator.predicted_layout()
        for digest in (
            discriminator.PREREGISTRATION_SHA256,
            layout["caseCatalogSha256"],
            layout["fixedGeometrySha256"],
            layout["sampleCoordinatesSha256"],
            layout["distanceFixedSha256"],
            layout["deltaBitsSha256"],
        ):
            self.assertIn(str(digest), source)
        self.assertIn("const uint base = record * 18u;", source)
        self.assertIn("dfdx(center0)", source)
        self.assertIn("dfdy(center0)", source)


if __name__ == "__main__":
    unittest.main()
