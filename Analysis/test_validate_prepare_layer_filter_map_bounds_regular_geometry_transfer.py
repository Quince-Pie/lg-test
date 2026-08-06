#!/usr/bin/env python3
"""Tests for the regular Filter/SDF unseen-geometry validator."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from unittest import mock

import validate_prepare_layer_filter_map_bounds_profile_transfer_retry as profile
import validate_prepare_layer_filter_map_bounds_regular_geometry_transfer as regular


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "validate_prepare_layer_filter_map_bounds_regular_geometry_transfer.py"
)


def producer(child: tuple[float, float, float, float]) -> dict:
    return {"roleIntermediates": {"recursiveChildF64": list(child)}}


class PrepareLayerFilterMapBoundsRegularGeometryTransferValidatorTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_exact_source_dod_is_frozen_for_all_geometries(self) -> None:
        for geometry, width in regular.EXPECTED_GEOMETRY_WIDTHS.items():
            extent = float(width + 560)
            expected = (-280.0, -280.0, extent, extent)
            self.assertEqual(regular.expected_source_bounds(geometry), expected)
            self.assertEqual(
                regular.validate_recursive_source(
                    [producer((0.0, 0.0, extent, extent))] * 32,
                    geometry,
                ),
                expected,
            )

    def test_unknown_geometry_and_wrong_child_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "expected regular geometry differs"):
            regular.expected_source_bounds("circle-800-center")
        with self.assertRaisesRegex(ValueError, "recursive child differs"):
            regular.validate_recursive_source(
                [producer((0.0, 0.0, 687.0, 687.0))],
                "circle-128-center",
            )

    def test_parent_validator_is_reused_and_restored(self) -> None:
        installed = profile.source_bounds

        def parent_validate(
            _trace,
            _timeline,
            geometry,
            material,
            appearance,
            direction,
        ):
            self.assertEqual(material, "regular")
            self.assertEqual(appearance, "dark")
            self.assertEqual(direction, "dematerialize")
            extent = regular.EXPECTED_GEOMETRY_WIDTHS[geometry] + 560.0
            records = [producer((0.0, 0.0, extent, extent))] * 32
            source = profile.source_bounds(material, records)
            return {
                "sourceBounds": {"f64": list(source)},
                "sealedConclusion": {},
            }

        with mock.patch.object(profile, "validate", parent_validate):
            result = regular.validate(
                Path("trace"),
                Path("timeline"),
                "circle-511-center",
                "dark",
                "dematerialize",
            )
        self.assertIs(profile.source_bounds, installed)
        self.assertEqual(
            result[
                "prepareLayerFilterMapBoundsRegularGeometryTransferValidationSchemaVersion"
            ],
            1,
        )
        self.assertEqual(
            result["sourceBounds"]["f64"], [-280.0, -280.0, 1071.0, 1071.0]
        )
        self.assertTrue(
            result["sealedConclusion"][
                "singleRegularGeometryProfileExactCropReplayPassed"
            ]
        )
        self.assertFalse(
            result["sealedConclusion"]["regularUnseenGeometryTransferPassed"]
        )

    def test_no_tolerance_or_product_parity_authority_is_added(self) -> None:
        self.assertNotIn('"liquidGlassParityEstablished": True', self.source)
        self.assertNotIn('"productionShaderAuthorized": True', self.source)
        self.assertNotIn("isclose(", self.source)
        self.assertNotIn("approx", self.source.lower())
        self.assertIn("geometryOrProducerOutputUsedToFitRule", self.source)


if __name__ == "__main__":
    unittest.main()
