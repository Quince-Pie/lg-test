#!/usr/bin/env python3
"""Tests for the measured fractional-width raster-grid transfer."""

import hashlib
import json
import zlib
from pathlib import Path
import unittest

import numpy as np

import analyze_raster_fractional_subpixel_transfer as transfer
import build_raster_fractional_selector_witness_map as witness_map


class RasterFractionalSubpixelTransferTests(unittest.TestCase):
    def test_quantizer_is_one_over_256_pixel_half_up(self) -> None:
        actual = transfer.quantized_mantissas(quantum=4, bias=2)
        self.assertEqual(
            actual[:10].tolist(),
            [0, 0, 4, 4, 4, 4, 8, 8, 8, 8],
        )
        self.assertEqual(
            actual[-4:].tolist(),
            [8_388_604, 8_388_604, 8_388_608, 8_388_608],
        )

    def test_quantized_class_partition_is_complete(self) -> None:
        starts = transfer.class_starts()
        ends = np.append(starts[1:], witness_map.MANTISSA_COUNT)
        sizes = ends - starts
        unique, counts = np.unique(sizes, return_counts=True)
        self.assertEqual(
            dict(zip(unique.tolist(), counts.tolist(), strict=True)),
            {2: 2, 4: 2_097_151},
        )
        self.assertEqual(int(sizes.sum()), witness_map.MANTISSA_COUNT)

    def test_materialized_selector_table_is_frozen_and_transfers_controls(
        self,
    ) -> None:
        path = Path(__file__).with_name(
            "raster_fractional_subpixel_resolved_selectors.zlib"
        )
        compressed = path.read_bytes()
        self.assertEqual(
            hashlib.sha256(compressed).hexdigest(),
            transfer.SELECTOR_COMPRESSED_SHA256,
        )
        selectors = zlib.decompress(compressed)
        self.assertEqual(
            hashlib.sha256(selectors).hexdigest(),
            transfer.SELECTOR_TABLE_SHA256,
        )
        table = np.frombuffer(selectors, dtype="<u4")
        self.assertEqual(len(table), 2_097_153)
        self.assertEqual(transfer.control_match_counts(table), (8_192, 32_768))

    def test_analysis_report_records_falsification_and_exhaustive_gate(
        self,
    ) -> None:
        path = Path(__file__).with_name(
            "raster_fractional_subpixel_transfer_analysis.json"
        )
        report = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(report["ciRunId"], transfer.CI_RUN_ID)
        self.assertEqual(report["ciCommit"], transfer.CI_COMMIT)
        self.assertEqual(report["rawSha256"], transfer.RAW_SHA256)
        self.assertTrue(
            report["prospectiveHypothesis"][
                "exactFloatingWidthHypothesisFalsified"
            ]
        )
        self.assertEqual(
            report["quantizerIdentification"]["fullDomainMatchingPolicies"],
            [{"quantumMantissaUlps": 4, "roundingBias": 2}],
        )
        measurement = report["measurement"]
        self.assertTrue(measurement["allInputRecordsExplained"])
        self.assertEqual(
            measurement["jointSelectorUniqueClassCount"],
            measurement["quantizedClassCount"],
        )
        self.assertTrue(measurement["sealedControlGate"])


if __name__ == "__main__":
    unittest.main()
