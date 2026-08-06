#!/usr/bin/env python3
"""Tests for the complete profile-transfer retry aggregate."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import aggregate_prepare_layer_filter_map_bounds_profile_transfer_retry as aggregate
import validate_prepare_layer_filter_map_bounds_profile_transfer_retry as validator


def validation(material: str, appearance: str, direction: str) -> dict:
    endpoint_count = 1 if material == "regular" else 0
    return {
        "prepareLayerFilterMapBoundsProfileTransferRetryValidationSchemaVersion": 1,
        "conclusion": "success",
        "inputs": {"traceSHA256": "a" * 64, "timelineSHA256": "b" * 64},
        "profile": {
            "material": material,
            "appearance": appearance,
            "direction": direction,
            "geometry": "circle-800-center",
            "backingScaleFactor": 1,
        },
        "sdfState": {
            "recordCount": 32,
            "expectedParametersHex": validator.EXPECTED_SDF_PARAMETERS_HEX[material],
        },
        "endpointYOffset": {"appliedRecordCount": endpoint_count},
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
        "sealedConclusion": {
            "singleProfileExactCropReplayPassed": True,
            "completeProfileMatrixPassed": False,
            "filterOpCropProfileTransferPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


class PrepareLayerFilterMapBoundsProfileTransferRetryAggregateTests(unittest.TestCase):
    def populate(self, root: Path) -> None:
        for material, appearance, direction in aggregate.EXPECTED_PROFILES:
            directory = root / (
                f"{aggregate.RESULT_ARTIFACT_PREFIX}{material}-{appearance}-"
                f"{direction}-123"
            )
            directory.mkdir()
            (directory / aggregate.VALIDATION_FILE_NAME).write_text(
                json.dumps(validation(material, appearance, direction)),
                encoding="utf-8",
            )

    def test_complete_matrix_is_aggregated_without_product_parity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.populate(root)
            result = aggregate.aggregate(root, 123, "a" * 40)
        self.assertEqual(result["profileCount"], 8)
        self.assertEqual(result["exactRectangleCount"], 256)
        self.assertEqual(result["exactComponentCount"], 1024)
        self.assertEqual(result["sdfStateRecordCount"], 256)
        self.assertEqual(result["endpointYOffsetAppliedRecordCount"], 4)
        sealed = result["sealedConclusion"]
        self.assertTrue(sealed["completeProfileMatrixPassed"])
        self.assertTrue(sealed["filterOpCropProfileTransferPassed"])
        self.assertFalse(sealed["opticalMaterialAppearanceDirectionTransferPassed"])
        self.assertFalse(sealed["productionShaderAuthorized"])
        self.assertFalse(sealed["liquidGlassParityEstablished"])

    def test_missing_profile_fails_closed(self) -> None:
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
            payload["floatingReplay"]["maximumULPDistancesXYWH"][1] = 1
            target.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "validation differs"):
                aggregate.aggregate(root, 123, "c" * 40)


if __name__ == "__main__":
    unittest.main()
