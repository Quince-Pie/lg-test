#!/usr/bin/env python3
"""Tests for the exact eight-regime crop-transfer replay."""

import json
import struct
import unittest
from pathlib import Path

import analyze_prepare_layer_crop_transfer_matrix as analyzer


ANALYSIS_ROOT = Path(__file__).resolve().parent
RESULT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_crop_transfer_matrix_analysis.json"
)
RESULT = json.loads(RESULT_PATH.read_text(encoding="utf-8"))


class PrepareLayerCropTransferMatrixAnalysisTests(unittest.TestCase):
    def test_opened_primitives_preserve_operation_order(self):
        transformed = (399.9984130859375, 360.0015869140625, 256.0, 264.0)
        ancestor = (372.0, 373.0, 279.0, 279.0)
        child_crop = analyzer.integer_crop(transformed)
        ancestor_crop = analyzer.integer_crop(ancestor)
        intersection = analyzer.intersect_i32(child_crop, ancestor_crop)
        predicted = analyzer.union_bounds_f64(
            transformed, tuple(float(value) for value in intersection)
        )
        self.assertEqual(child_crop, (398, 359, 259, 267))
        self.assertEqual(ancestor_crop, (372, 373, 279, 279))
        self.assertEqual(intersection, (398, 373, 253, 253))
        self.assertEqual(
            struct.pack("<4d", *predicted).hex(),
            "0000000000e07840000000800680764000000080f91f704000000080f99f7040",
        )

    def test_result_is_the_complete_opened_discovery_matrix(self):
        self.assertEqual(
            RESULT["prepareLayerCropTransferMatrixAnalysisSchemaVersion"], 1
        )
        self.assertEqual(RESULT["runID"], 31055266553)
        self.assertEqual(RESULT["geometryCount"], 8)
        self.assertEqual(RESULT["recordCount"], 256)
        self.assertEqual(RESULT["componentCount"], 1024)
        self.assertEqual(RESULT["exactRecordCount"], 250)
        self.assertEqual(RESULT["mismatchedRecordCount"], 6)
        self.assertEqual(RESULT["exactComponentCount"], 1015)
        self.assertEqual(RESULT["mismatchedComponentCount"], 9)

    def test_every_mismatch_is_retained_without_tolerance(self):
        mismatch_projection = [
            (
                record["label"],
                record["sampleIndex"],
                record["mismatchedComponentIndices"],
            )
            for record in RESULT["mismatchRecords"]
        ]
        self.assertEqual(
            mismatch_projection,
            [
                ("crop-256-center", 28, [2]),
                ("crop-256-center", 29, [2]),
                ("crop-256-center", 30, [1, 3]),
                ("crop-256-center", 31, [1, 3]),
                ("crop-640-center", 31, [1, 3]),
                ("crop-640-half-signed", 20, [3]),
            ],
        )
        self.assertEqual(
            sum(len(record["mismatches"]) for record in RESULT["mismatchRecords"]),
            9,
        )
        for record in RESULT["mismatchRecords"]:
            for mismatch in record["mismatches"]:
                self.assertNotEqual(
                    mismatch["predicted"]["littleEndianHex"],
                    mismatch["observed"]["littleEndianHex"],
                )

    def test_result_keeps_product_authority_sealed(self):
        conclusion = RESULT["conclusion"]
        self.assertEqual(
            conclusion["missingExactOperand"],
            "the signed-int rectangle converted at prepare_layer+0x8570 "
            "and passed at +0x85dc to LayerShapes::union_bounds",
        )
        self.assertFalse(conclusion["ancestorAggregateProxyExactForEveryComponent"])
        self.assertFalse(conclusion["generalCropPolicyRecovered"])
        self.assertFalse(conclusion["unseenTransferPassed"])
        self.assertFalse(conclusion["productionShaderAuthorized"])
        self.assertFalse(conclusion["liquidGlassParityEstablished"])


if __name__ == "__main__":
    unittest.main()
