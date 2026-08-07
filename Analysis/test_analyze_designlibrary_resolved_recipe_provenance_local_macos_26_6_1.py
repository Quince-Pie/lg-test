#!/usr/bin/env python3
"""Tests for the native ResolvedRecipe provenance proof."""

from __future__ import annotations

import ast
import hashlib
import json
import struct
import unittest
from pathlib import Path

import analyze_designlibrary_resolved_recipe_provenance_local_macos_26_6_1 as analyzer


ANALYSIS = Path(__file__).resolve().parent
SOURCE_PATH = Path(analyzer.__file__).resolve()
RESULT_PATH = ANALYSIS / (
    "designlibrary_resolved_recipe_provenance_local_macos_26_6_1_result.json"
)


class ResolvedRecipeProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(self.source, feature_version=(3, 9))

    def test_operand_split_and_range_helpers_are_exact(self) -> None:
        self.assertEqual(
            analyzer.split_operands("q0, q1, [x19, #0x20]"),
            ["q0", "q1", "[x19, #0x20]"],
        )
        merged = analyzer.merge_ranges(((8, 16), (0, 4), (4, 9), (20, 21)))
        self.assertEqual(merged, ((0, 16), (20, 21)))
        self.assertEqual(
            analyzer.complement_ranges(merged, 24),
            ((16, 20), (21, 24)),
        )

    def test_disassembly_parser_strips_comments_without_weakening_operands(
        self,
    ) -> None:
        parsed = analyzer.parse_instructions(
            "0x24093C4FC   adrp     x19, 361938 ; 0x298f0e000\n"
            "0x2409236B8   mov      w2, #0x401\n"
        )
        self.assertEqual(parsed[0x24093C4FC], ("adrp", "x19, 361938"))
        self.assertEqual(parsed[0x2409236B8], ("mov", "w2, #0x401"))

    def test_bl_destination_decoder_is_exact(self) -> None:
        address = 0x2409236BC
        target = analyzer.BYTE_COPY_STUB
        immediate = ((target - address) // 4) & 0x03FFFFFF
        payload = struct.pack("<I", 0x94000000 | immediate)
        section = analyzer.metadata.Section(
            "__TEST",
            "__text",
            {address + index: value for index, value in enumerate(payload)},
        )
        self.assertEqual(analyzer.branch_destination(section, address), target)

    def test_resolved_recipe_field_zero_is_the_exact_parameters_type(self) -> None:
        recipe = self.result["resolvedRecipe"]
        self.assertEqual(recipe["name"], "ResolvedRecipe")
        self.assertEqual(recipe["descriptorAddress"], "0x2409d2f1c")
        self.assertEqual(
            [(field["name"], field["typeReference"]) for field in recipe["fields"]],
            list(analyzer.RESOLVED_RECIPE_FIELDS),
        )
        claims = self.result["claims"]
        self.assertTrue(claims["parametersAreResolvedRecipeFieldZero"])
        self.assertEqual(claims["parametersFieldOffset"], 0)
        self.assertEqual(claims["parametersFieldByteCount"], 0x401)

    def test_entire_native_call_chain_has_frozen_code_identity(self) -> None:
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

    def test_all_four_full_parameters_transfers_use_one_authenticated_stub(
        self,
    ) -> None:
        stub = self.result["byteCopyStub"]
        self.assertEqual(stub["address"], "0x2409a5910")
        self.assertEqual(stub["byteCount"], 16)
        self.assertEqual(stub["sha256"], analyzer.BYTE_COPY_STUB_SHA256)
        self.assertEqual(set(stub["callTargets"].values()), {"0x2409a5910"})
        full_transfers = [
            value
            for value in self.result["provenanceChain"]
            if value.get("byteCount") == 0x401
        ]
        self.assertEqual(len(full_transfers), 3)

    def test_default_seed_direct_writes_and_zero_fill_padding_partition_1025(
        self,
    ) -> None:
        seed = self.result["defaultParametersSeed"]
        self.assertEqual(seed["onceTokenAddress"], "0x298f07d08")
        self.assertEqual(seed["onceTokenInitialBytesHex"], "00" * 8)
        self.assertEqual(seed["zeroFilledCommonStorageAddress"], "0x298f0e710")
        self.assertEqual(seed["byteCount"], 0x401)
        self.assertEqual(seed["initializerDirectWriteByteCount"], 947)
        self.assertEqual(seed["zeroFillOnlyPaddingByteCount"], 78)
        direct = {
            offset
            for value in seed["initializerDirectWriteRanges"]
            for offset in range(value["start"], value["endExclusive"])
        }
        padding = {
            offset
            for value in seed["zeroFillOnlyPaddingRanges"]
            for offset in range(value["start"], value["endExclusive"])
        }
        self.assertFalse(direct.intersection(padding))
        self.assertEqual(direct.union(padding), set(range(0x401)))

    def test_result_matches_source_and_does_not_overclaim_parity(self) -> None:
        source_hash = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
        result_hash = hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest()
        self.assertEqual(
            source_hash,
            "7492526b9ce67f21eee811a5a7d0f5effc1348be97f3aa4c2429d13e7c497145",
        )
        self.assertEqual(
            result_hash,
            "f184a3326cf2b313e492bdc00f6fa8927ea926d9efbb1de2831ba4f3a2f22391",
        )
        self.assertEqual(self.result["tool"]["sourceSHA256"], source_hash)
        self.assertEqual(
            self.result["tool"]["metadataAnalyzerSHA256"],
            analyzer.METADATA_ANALYZER_SHA256,
        )
        claims = self.result["claims"]
        self.assertTrue(claims["resolvedRecipeBuilderIsExactProducerBoundary"])
        self.assertTrue(
            claims["resolveLayersHelperOnlyCopiesAlreadyProducedParameters"]
        )
        self.assertFalse(claims["publicControlsToParametersLawEstablished"])
        self.assertFalse(claims["opticalLawFullyDecoded"])
        self.assertFalse(claims["cropAllocationPolicyEstablished"])
        self.assertFalse(claims["retinaCompositorColorLawEstablished"])
        self.assertFalse(claims["independentWalleZeroByteFrameParityEstablished"])
        self.assertFalse(claims["liquidGlassParityEstablished"])
        self.assertFalse(claims["productionShaderChangeAuthorized"])


if __name__ == "__main__":
    unittest.main()
