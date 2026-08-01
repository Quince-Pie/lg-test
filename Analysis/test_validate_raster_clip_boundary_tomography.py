#!/usr/bin/env python3
"""Tests for the preregistered clip-boundary tomography gate."""

import hashlib
from pathlib import Path
import unittest

import validate_raster_clip_boundary_tomography as boundary


class RasterClipBoundaryTomographyTests(unittest.TestCase):
    def test_preregistration_and_layout_are_frozen(self) -> None:
        preregistration = boundary.load_preregistration()
        self.assertFalse(preregistration["observedAtPreregistration"])
        self.assertEqual(preregistration["frozenLayout"], boundary.predicted_layout())
        self.assertEqual(
            hashlib.sha256(boundary.PREREGISTRATION_PATH.read_bytes()).hexdigest(),
            boundary.PREREGISTRATION_SHA256,
        )

    def test_every_boundary_group_contains_candidate_and_safe_control(self) -> None:
        cases, groups = boundary.case_catalog()
        self.assertEqual(len(groups), 8)
        for group in groups:
            group_cases = cases[
                group.first_case : group.first_case + group.case_count
            ]
            edge_index = {
                "left": 0,
                "right": 1,
                "top": 2,
                "bottom": 3,
            }[group.plane]
            edges = [case.geometry_fixed[edge_index] for case in group_cases]
            self.assertIn(group.candidate_edge_fixed, edges)
            self.assertIn(cases[group.safe_case], group_cases)
            fine = range(
                group.candidate_edge_fixed - boundary.UNITS_PER_PIXEL,
                group.candidate_edge_fixed + boundary.UNITS_PER_PIXEL + 1,
            )
            self.assertTrue(set(fine).issubset(edges))
            for case in group_cases:
                left, right, top, bottom = case.geometry_fixed
                for index in range(case.record_count):
                    x, y = case.sample(index)
                    self.assertLess(left, x * boundary.UNITS_PER_PIXEL + 128)
                    self.assertLess(x * boundary.UNITS_PER_PIXEL + 128, right)
                    self.assertLess(top, y * boundary.UNITS_PER_PIXEL + 128)
                    self.assertLess(y * boundary.UNITS_PER_PIXEL + 128, bottom)

    def test_topology_grid_samples_are_strictly_inside_geometry(self) -> None:
        cases, _groups = boundary.case_catalog()
        topology = [case for case in cases if case.mode == "grid"]
        self.assertEqual(len(topology), 37)
        for case in topology:
            left, right, top, bottom = case.geometry_fixed
            for index in range(case.record_count):
                x, y = case.sample(index)
                self.assertLess(left, x * boundary.UNITS_PER_PIXEL + 128)
                self.assertLess(x * boundary.UNITS_PER_PIXEL + 128, right)
                self.assertLess(top, y * boundary.UNITS_PER_PIXEL + 128)
                self.assertLess(y * boundary.UNITS_PER_PIXEL + 128, bottom)

    def test_synthetic_safe_planes_uniquely_recover_each_witness(self) -> None:
        arithmetic = boundary.factorization.top_left.arithmetic
        for span in (320, 640):
            for axis in ("x", "y"):
                records = [
                    [0] * boundary.RECORD_WORD_COUNT
                    for _ in range(boundary.LINE_SAMPLE_COUNT)
                ]
                components = (0, 1) if axis == "x" else (2, 3)
                for witness_index, delta_bits in enumerate(boundary.DELTA_BITS):
                    slope_bits = boundary.float32_bits(
                        boundary.float32_value(delta_bits) / span
                    )
                    slope = boundary.float32_value(slope_bits)
                    for first in (0, 2):
                        constant = arithmetic.float32_value(
                            arithmetic.float32_bits(-32 * slope)
                        ) if first == 0 else 0.0
                        for relative, sample_index in ((0.0, first), (30.0, first + 1)):
                            row = (7 + witness_index) * 4
                            records[sample_index][row + components[0]] = (
                                arithmetic.float32_bits(relative * slope + constant)
                            )
                            records[sample_index][row + components[1]] = (
                                arithmetic.float32_bits(
                                    (relative + boundary.PULL_OFFSET) * slope
                                    + constant
                                )
                            )
                    self.assertEqual(
                        boundary.accepted_baseline_slopes(
                            records,
                            witness_index=witness_index,
                            span_pixels=span,
                            axis=axis,
                        ),
                        (slope_bits,),
                    )

    def test_swift_probe_embeds_every_frozen_digest(self) -> None:
        source = (
            Path(__file__).parents[1]
            / "Sources"
            / "GlassRasterClipBoundaryTomography"
            / "main.swift"
        ).read_text(encoding="utf-8")
        layout = boundary.predicted_layout()
        for digest in (
            boundary.PREREGISTRATION_SHA256,
            layout["caseCatalogSha256"],
            layout["fixedGeometrySha256"],
            layout["caseLayoutSha256"],
            layout["deltaBitsSha256"],
        ):
            self.assertIn(str(digest), source)
        self.assertIn("for viewport in [256, 512]", source)
        self.assertIn("const uint base = record * 15u;", source)
        self.assertNotIn("(recordVectorCount)u", source)


if __name__ == "__main__":
    unittest.main()
