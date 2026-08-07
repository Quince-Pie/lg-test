#!/usr/bin/env python3
"""Tests for native BackgroundFilter constructor write coverage."""

from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

import analyze_designlibrary_background_filter_constructor_write_coverage_local_macos_26_6_1 as analyzer


ANALYSIS = Path(__file__).resolve().parent
SOURCE_PATH = (
    ANALYSIS
    / "analyze_designlibrary_background_filter_constructor_write_coverage_local_macos_26_6_1.py"
)
RESULT_PATH = (
    ANALYSIS
    / "designlibrary_background_filter_constructor_write_coverage_local_macos_26_6_1_result.json"
)


class BackgroundFilterConstructorWriteCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(SOURCE_PATH.read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_native_identity_and_constructor_code_are_exact(self) -> None:
        self.assertEqual(
            self.result["host"],
            {
                "designLibraryUUID": "1E980802-69F5-3E69-89EF-50088297FCF5",
                "hardwareModel": "MacBookPro18,2",
                "macOSBuildVersion": "25G76",
                "macOSProductVersion": "26.6.1",
                "machine": "arm64",
                "system": "Darwin",
            },
        )
        self.assertEqual(
            self.result["constructor"],
            {
                "byteCount": 1044,
                "end": "0x24091c114",
                "instructionCount": 261,
                "normalizedInstructionSHA256": "49708bacdc1cd086ea0337a69afe90b9a41098a08f91b5d561093526e3c33505",
                "sha256": "71a592bc8a187fe8bcca0fa50c3f4d36ea3c2916dbd5d16f3fa1df05b86f131d",
                "start": "0x24091bd00",
            },
        )

    def test_terminal_stores_cover_exactly_491_initialized_bytes(self) -> None:
        coverage = self.result["outputWriteCoverage"]
        self.assertEqual(coverage["storeCount"], 59)
        self.assertEqual(coverage["storeBaseRegisters"], ["x1", "x20", "x8"])
        self.assertEqual(
            coverage["initializedRanges"],
            [[0, 349], [352, 458], [464, 476], [480, 504]],
        )
        self.assertEqual(coverage["initializedByteCount"], 491)
        self.assertEqual(
            coverage["paddingRanges"],
            [[349, 352], [458, 464], [476, 480]],
        )
        self.assertEqual(coverage["paddingByteCount"], 13)
        ranges = [
            (record["outputStart"], record["outputEndExclusive"])
            for record in coverage["stores"]
        ]
        self.assertEqual(
            analyzer.merge_ranges(ranges), analyzer.EXPECTED_INITIALIZED_RANGES
        )
        self.assertEqual(
            analyzer.complement_ranges(
                analyzer.merge_ranges(ranges),
                analyzer.BACKGROUND_FILTER_BYTE_COUNT,
            ),
            analyzer.EXPECTED_PADDING_RANGES,
        )

    def test_constructor_never_stores_through_parameters_base(self) -> None:
        stores = self.result["allMemoryStores"]
        self.assertEqual(stores["baseRegisters"], ["sp", "x1", "x20", "x8"])
        self.assertEqual(stores["sourceParametersBaseRegister"], "x22")
        self.assertFalse(stores["sourceParametersBaseAppearsInStore"])
        self.assertFalse(self.result["claims"]["sourceParametersWritten"])

    def test_source_and_canonical_result_hashes_are_frozen(self) -> None:
        source_hash = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
        result_hash = hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest()
        self.assertEqual(
            source_hash,
            "4a993541b521f6dc71319c516ecd65e19900cfcf19f52d3632ee3dddbdb0ca22",
        )
        self.assertEqual(
            self.result["tool"]["sourceSHA256"], source_hash
        )
        self.assertEqual(
            result_hash,
            "4673360ec9cd843d67c528f9c1d7870a6c2dd45244a093f3c77f68399a4cd8c6",
        )

    def test_authority_stays_closed(self) -> None:
        claims = self.result["claims"]
        self.assertTrue(claims["onlyInitialized491BytesAreCausalJoinGate"])
        self.assertFalse(claims["liquidGlassParityEstablished"])
        self.assertFalse(claims["productionShaderChangeAuthorized"])


if __name__ == "__main__":
    unittest.main()
