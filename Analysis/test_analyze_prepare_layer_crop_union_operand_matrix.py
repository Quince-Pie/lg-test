#!/usr/bin/env python3
"""Tests for the opened two-union matrix and 256/256 crop candidate."""

from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

import analyze_prepare_layer_crop_union_operand_matrix as analyzer


ANALYSIS_ROOT = Path(__file__).resolve().parent
RESULT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_crop_union_operand_matrix_analysis.json"
)
RESULT = json.loads(RESULT_PATH.read_text(encoding="utf-8"))


class PrepareLayerCropUnionOperandMatrixAnalysisTests(unittest.TestCase):
    def test_schema_six_floating_input_is_replayed_bit_for_bit(self):
        candidate, expansion, public_roi = analyzer.public_crop_float_candidate(
            (491.993896484375, 491.993896484375),
            (
                -307.49984741210938,
                -307.49984741210938,
                654.9996948242188,
                654.9996948242188,
            ),
            (491.993896484375, -115.993896484375, 640.0, 648.0),
            1024.0,
            0.062519073486328125,
            0.0,
        )
        self.assertEqual(expansion.hex(), "0x1.6682666666666p-2")
        self.assertEqual(
            struct.pack("<4d", *candidate).hex(),
            "00000000e7bf7e400000004033f064409a999969994d764000000060ffc77640",
        )
        self.assertEqual(
            candidate,
            (
                491.993896484375,
                167.50625610351562,
                356.84995422363284,
                364.4998474121094,
            ),
        )
        self.assertLess(public_roi[0], candidate[0])
        self.assertGreater(public_roi[1], -115.993896484375)

    def test_viewport_is_intersected_after_fractional_enclosure(self):
        record = next(
            record
            for record in RESULT["records"]
            if record["label"] == "crop-1536-clipped" and record["sampleIndex"] == 1
        )
        self.assertEqual(record["candidateEnclosureI32"], [487, -282, 811, 819])
        self.assertEqual(record["candidateViewportIntersectionI32"], [487, 0, 537, 537])
        self.assertEqual(
            record["candidateViewportIntersectionI32"],
            record["observedNestedInputI32"],
        )

    def test_opened_run_keeps_its_prospective_failure(self):
        self.assertEqual(
            RESULT["prepareLayerCropUnionOperandMatrixAnalysisSchemaVersion"], 1
        )
        self.assertEqual(RESULT["runID"], 31057364064)
        self.assertFalse(RESULT["prospectiveGatePassed"])
        self.assertEqual(RESULT["observedDestinationMatchedUnionCountPerMarker"], 2)
        self.assertIn("last", RESULT["openedSelectionRule"])
        self.assertEqual(RESULT["geometryCount"], 8)
        self.assertEqual(RESULT["recordCount"], 256)
        self.assertEqual(RESULT["componentCount"], 1024)

    def test_candidate_closes_every_calibration_operand_without_exceptions(self):
        self.assertEqual(RESULT["exactPublicCropRecordCount"], 256)
        self.assertEqual(RESULT["mismatchedPublicCropRecordCount"], 0)
        self.assertFalse(RESULT["candidate"]["toleranceUsed"])
        self.assertFalse(RESULT["candidate"]["exceptionFitUsed"])
        for record in RESULT["records"]:
            self.assertEqual(
                record["candidateViewportIntersectionI32"],
                record["observedNestedInputI32"],
            )

    def test_product_authority_remains_sealed(self):
        conclusion = RESULT["conclusion"]
        self.assertTrue(conclusion["prospectiveOneMatchGateFalsified"])
        self.assertTrue(conclusion["calibrationMatrixExact"])
        self.assertFalse(conclusion["preIntegerFloatingProducerCapturedAcrossMatrix"])
        self.assertFalse(conclusion["unseenTransferPassed"])
        self.assertFalse(conclusion["generalCropPolicyRecovered"])
        self.assertFalse(conclusion["productionShaderAuthorized"])
        self.assertFalse(conclusion["liquidGlassParityEstablished"])


if __name__ == "__main__":
    unittest.main()
