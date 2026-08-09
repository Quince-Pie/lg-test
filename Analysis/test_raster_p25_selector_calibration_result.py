#!/usr/bin/env python3
"""Regression gate for the accepted exhaustive P25 calibration."""

import hashlib
import json
import unittest
import zlib
from pathlib import Path

import validate_raster_p25_selector_sweep as validate


ANALYSIS = Path(__file__).parent
RESULT = ANALYSIS / "raster_p25_selector_calibration_3dedcca_result.json"
BITMAP = ANALYSIS / "raster_p25_selector_ceil_bits.bin"
ARCHIVE = ANALYSIS / "raster_p25_selector_ceil_bits.zlib"


class RasterP25SelectorCalibrationResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))
        cls.bitmap = BITMAP.read_bytes()
        cls.archive = ARCHIVE.read_bytes()

    def test_exhaustive_gate_passed_without_tolerance(self) -> None:
        self.assertEqual(
            self.result["captureCommit"],
            "3dedccad9afecb5635505d035ca2fc8f94442963",
        )
        self.assertEqual(self.result["input"]["finiteWordCount"], 1 << 24)
        self.assertEqual(self.result["input"]["missingRecordCount"], 0)
        self.assertEqual(
            self.result["predeclaredRecovery"]["floorMatchCount"]
            + self.result["predeclaredRecovery"]["ceilMatchCount"],
            (1 << 24) - 1,
        )
        self.assertEqual(
            self.result["predeclaredRecovery"]["exactPowerBoundaryMatchCount"],
            1,
        )
        self.assertEqual(self.result["predeclaredRecovery"]["zeroMatchCount"], 0)
        self.assertEqual(
            self.result["predeclaredRecovery"]["ambiguousMatchCount"],
            0,
        )
        self.assertTrue(self.result["measurement"]["calibrationComplete"])
        self.assertEqual(self.result["gate"]["qualityTolerance"], 0)

    def test_materialized_bitmap_is_exact(self) -> None:
        record = self.result["selectorBitmap"]
        self.assertEqual(len(self.bitmap), 1 << 21)
        self.assertEqual(hashlib.sha256(self.bitmap).hexdigest(), record["sha256"])
        self.assertEqual(
            hashlib.sha256(self.archive).hexdigest(),
            record["archiveSha256"],
        )
        self.assertEqual(zlib.decompress(self.archive), self.bitmap)

    def test_all_frozen_controls_transfer(self) -> None:
        controls = validate.validate_controls(self.bitmap)
        self.assertTrue(controls["passed"])
        self.assertEqual(controls, self.result["frozenControls"])

    def test_selector_is_admitted_but_product_parity_is_not_claimed(self) -> None:
        gate = self.result["gate"]
        self.assertTrue(gate["portableNormalizedP25SelectorEstablished"])
        self.assertTrue(gate["productionSelectorUseAuthorized"])
        self.assertFalse(gate["productionParityAuthorized"])


if __name__ == "__main__":
    unittest.main()
