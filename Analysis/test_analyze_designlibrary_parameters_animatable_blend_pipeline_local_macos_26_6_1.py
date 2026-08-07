#!/usr/bin/env python3
"""Tests for the native Parameters weighted-blend pipeline proof."""

from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

import analyze_designlibrary_parameters_animatable_blend_pipeline_local_macos_26_6_1 as analyzer


ANALYSIS = Path(__file__).resolve().parent
SOURCE_PATH = Path(analyzer.__file__).resolve()
RESULT_PATH = ANALYSIS / (
    "designlibrary_parameters_animatable_blend_pipeline_local_macos_26_6_1_result.json"
)


class ParametersAnimatableBlendPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(self.source, feature_version=(3, 9))

    def test_all_pipeline_code_regions_and_callers_are_frozen(self) -> None:
        regions = self.result["codeRegions"]
        self.assertEqual(set(regions), set(analyzer.CODE_REGIONS))
        for name, (start, end, expected_sha256) in analyzer.CODE_REGIONS.items():
            self.assertEqual(regions[name]["start"], "0x{:x}".format(start))
            self.assertEqual(regions[name]["endExclusive"], "0x{:x}".format(end))
            self.assertEqual(regions[name]["byteCount"], end - start)
            self.assertEqual(regions[name]["instructionCount"], (end - start) // 4)
            self.assertEqual(regions[name]["sha256"], expected_sha256)
        self.assertEqual(
            {
                name: tuple(int(address, 16) for address in addresses)
                for name, addresses in self.result["directBLCallsites"].items()
            },
            analyzer.EXPECTED_DIRECT_CALLS,
        )

    def test_scale_and_add_arithmetic_inventories_are_exact(self) -> None:
        inventories = self.result["floatingInstructionInventories"]
        self.assertEqual(inventories, analyzer.EXPECTED_FLOATING_INVENTORIES)
        scale_mnemonics = {
            mnemonic
            for name in (
                "animatableScaleBy",
                "shadowScaleHelper",
                "edgeBleedScaleHelper",
                "highlightsScaleHelper",
            )
            for mnemonic in inventories[name]
            if mnemonic != "fcvt"
        }
        self.assertTrue(scale_mnemonics)
        self.assertTrue(
            all(mnemonic.startswith("fmul") for mnemonic in scale_mnemonics)
        )
        add_mnemonics = {
            mnemonic
            for name in (
                "animatableAdd",
                "radiosityAddHelper",
                "packedAddHelper",
            )
            for mnemonic in inventories[name]
            if mnemonic != "fmov"
        }
        self.assertTrue(add_mnemonics)
        self.assertTrue(all(mnemonic.startswith("fadd") for mnemonic in add_mnemonics))

    def test_all_authenticated_copies_use_the_exact_byte_copy_stub(self) -> None:
        observed = self.result["authenticatedByteCopies"]
        self.assertEqual(len(observed), len(analyzer.BYTE_COPY_CALLS))
        self.assertEqual(
            {int(value["callsite"], 16): value["byteCount"] for value in observed},
            analyzer.BYTE_COPY_CALLS,
        )
        self.assertEqual(
            {value["target"] for value in observed},
            {"0x{:x}".format(analyzer.provenance.BYTE_COPY_STUB)},
        )

    def test_converter_write_and_nonwrite_ranges_partition_1153_bytes(self) -> None:
        coverage = self.result["parametersToAnimatableDataWriteCoverage"]
        written_ranges = tuple(
            (value["start"], value["endExclusive"])
            for value in coverage["writtenRanges"]
        )
        nonwrite_ranges = tuple(
            (value["start"], value["endExclusive"])
            for value in coverage["notWrittenRanges"]
        )
        self.assertEqual(written_ranges, analyzer.EXPECTED_CONVERTER_WRITE_RANGES)
        self.assertEqual(coverage["writtenByteCount"], 989)
        self.assertEqual(coverage["notWrittenByteCount"], 164)
        written = {
            offset for start, end in written_ranges for offset in range(start, end)
        }
        not_written = {
            offset for start, end in nonwrite_ranges for offset in range(start, end)
        }
        self.assertFalse(written.intersection(not_written))
        self.assertEqual(
            written.union(not_written),
            set(range(analyzer.ANIMATABLE_DATA_BYTE_COUNT)),
        )

    def test_weighted_recurrence_is_exact_convert_scale_add(self) -> None:
        recurrence = self.result["weightedRecurrence"]
        self.assertEqual(
            recurrence["equation"],
            "A_next = A + scale(parameters.animatableData, factor)",
        )
        self.assertEqual(
            recurrence["parametersToAnimatableDataCallsite"], "0x2409820d0"
        )
        self.assertEqual(recurrence["scaleFactorRegister"], "d9/v9")
        self.assertEqual(recurrence["scaleCallsite"], "0x2409820dc")
        self.assertEqual(recurrence["scaledValueStableCopyByteCount"], 0x481)
        self.assertEqual(recurrence["addCallsite"], "0x24098210c")
        self.assertEqual(recurrence["resolverCallsite"], "0x240982cd4")

    def test_single_value_unity_path_is_a_bitwise_parameters_copy(self) -> None:
        fast_path = self.result["singleValueUnityFastPath"]
        self.assertEqual(fast_path["collectionCountPredicate"], "equal to 1")
        self.assertEqual(fast_path["runtimeFactorRegister"], "d9")
        self.assertEqual(fast_path["unityConstant"], 1.0)
        self.assertEqual(fast_path["factorPredicate"], "ordered equal to 1.0")
        self.assertEqual(fast_path["fullParametersCopyByteCount"], 0x401)
        self.assertEqual(fast_path["fullParametersCopyCallsite"], "0x240982b28")
        self.assertTrue(fast_path["flagClearedAfterFullCopy"])
        self.assertTrue(fast_path["fastPathSkipsResolver"])

    def test_result_matches_source_and_does_not_overclaim_parity(self) -> None:
        source_hash = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
        result_hash = hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest()
        self.assertEqual(
            source_hash,
            "bb89ef7135b3a0f955ff46b0afd20a6df3480fda1e7b053882333362a11dec33",
        )
        self.assertEqual(
            result_hash,
            "ab702bb92880f277cc525d19c405c15909c8ece1d778d4f27895b694e54f0f2b",
        )
        self.assertEqual(self.result["tool"]["sourceSHA256"], source_hash)
        claims = self.result["claims"]
        self.assertTrue(claims["weightedParametersBlendPipelineEstablished"])
        self.assertTrue(claims["singleValueUnityFastPathAvoidsFloatingRoundTrip"])
        self.assertFalse(claims["publicControlsToLayerSelectionLawEstablished"])
        self.assertFalse(claims["environmentToLayerSelectionLawEstablished"])
        self.assertFalse(claims["runtimeWeightProductionLawEstablished"])
        self.assertFalse(claims["allNestedConversionSemanticsDecoded"])
        self.assertFalse(claims["cropAllocationPolicyEstablished"])
        self.assertFalse(claims["retinaCompositorColorLawEstablished"])
        self.assertFalse(claims["independentWalleZeroByteFrameParityEstablished"])
        self.assertFalse(claims["liquidGlassParityEstablished"])
        self.assertFalse(claims["productionShaderChangeAuthorized"])


if __name__ == "__main__":
    unittest.main()
