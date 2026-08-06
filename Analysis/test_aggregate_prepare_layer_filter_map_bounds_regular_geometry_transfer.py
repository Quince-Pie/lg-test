#!/usr/bin/env python3
"""Tests for the 32-case regular geometry/profile aggregate."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import aggregate_prepare_layer_filter_map_bounds_regular_geometry_transfer as aggregate
import validate_prepare_layer_filter_map_bounds_profile_transfer_retry as profile
import validate_prepare_layer_filter_map_bounds_regular_geometry_transfer as regular


def validation(geometry: str, appearance: str, direction: str) -> dict:
    return {
        "prepareLayerFilterMapBoundsRegularGeometryTransferValidationSchemaVersion": 1,
        "conclusion": "success",
        "inputs": {"traceSHA256": "a" * 64, "timelineSHA256": "b" * 64},
        "profile": {
            "material": "regular",
            "appearance": appearance,
            "direction": direction,
            "geometry": geometry,
            "backingScaleFactor": 1,
        },
        "sourceBounds": {
            "f64": list(regular.expected_source_bounds(geometry)),
            "geometryWidth": regular.EXPECTED_GEOMETRY_WIDTHS[geometry],
            "exactExpansionPerEdge": 280.0,
            "geometryOrProducerOutputUsedToFitRule": False,
        },
        "sdfState": {
            "recordCount": 32,
            "expectedParametersHex": profile.EXPECTED_SDF_PARAMETERS_HEX["regular"],
        },
        "endpointYOffset": {"appliedRecordCount": 1},
        "floatingReplay": {
            "rectangleCount": 32,
            "componentCount": 128,
            "exactRectangleCount": 32,
            "exactComponentCount": 128,
            "mismatchedRectangleCount": 0,
            "mismatchedComponentCount": 0,
            "maximumAbsoluteErrorsXYWH": [0.0, 0.0, 0.0, 0.0],
            "maximumULPDistancesXYWH": [0, 0, 0, 0],
            "allRectanglesExact": True,
            "allComponentsExact": True,
        },
        "structuralSelection": {
            "cropOrProducerValuesUsedForSelection": False,
            "twoStageRegularCropChainExactCount": 32,
        },
        "sealedConclusion": {
            "singleRegularGeometryProfileExactCropReplayPassed": True,
            "regularGeometryProfileCartesianTransferPassed": False,
            "regularUnseenGeometryTransferPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


class PrepareLayerFilterMapBoundsRegularGeometryTransferAggregateTests(
    unittest.TestCase
):
    def populate(self, root: Path) -> None:
        for geometry, appearance, direction in aggregate.EXPECTED_CASES:
            directory = root / (
                f"{aggregate.RESULT_ARTIFACT_PREFIX}{geometry}-{appearance}-"
                f"{direction}-123"
            )
            directory.mkdir()
            (directory / aggregate.VALIDATION_FILE_NAME).write_text(
                json.dumps(validation(geometry, appearance, direction)),
                encoding="utf-8",
            )

    def test_complete_cartesian_matrix_opens_only_regular_crop_transfer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.populate(root)
            result = aggregate.aggregate(root, 123, "a" * 40)
        self.assertEqual(result["geometryCount"], 8)
        self.assertEqual(result["profilePerGeometryCount"], 4)
        self.assertEqual(result["caseCount"], 32)
        self.assertEqual(result["exactRectangleCount"], 1024)
        self.assertEqual(result["exactComponentCount"], 4096)
        self.assertEqual(result["sdfStateRecordCount"], 1024)
        self.assertEqual(result["endpointYOffsetAppliedRecordCount"], 32)
        sealed = result["sealedConclusion"]
        self.assertTrue(sealed["regularGeometryProfileCartesianTransferPassed"])
        self.assertTrue(sealed["regularUnseenGeometryTransferPassed"])
        self.assertTrue(sealed["filterOpCropProfileTransferPassed"])
        self.assertFalse(sealed["currentShaderCapturedInputOpticalTransferPassed"])
        self.assertFalse(sealed["productionShaderAuthorized"])
        self.assertFalse(sealed["liquidGlassParityEstablished"])

    def test_missing_case_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.populate(root)
            target = next(root.iterdir())
            (target / aggregate.VALIDATION_FILE_NAME).unlink()
            with self.assertRaisesRegex(ValueError, "validation is missing"):
                aggregate.aggregate(root, 123, "b" * 40)

    def test_nonzero_error_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.populate(root)
            target = next(root.iterdir()) / aggregate.VALIDATION_FILE_NAME
            payload = json.loads(target.read_text(encoding="utf-8"))
            payload["floatingReplay"]["maximumULPDistancesXYWH"][0] = 1
            target.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "validation differs"):
                aggregate.aggregate(root, 123, "c" * 40)


if __name__ == "__main__":
    unittest.main()
