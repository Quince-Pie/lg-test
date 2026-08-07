#!/usr/bin/env python3
"""Tests for the native BackgroundFilter constructor semantics proof."""

from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

import analyze_designlibrary_background_filter_constructor_semantics_local_macos_26_6_1 as analyzer


ANALYSIS = Path(__file__).resolve().parent
SOURCE_PATH = Path(analyzer.__file__).resolve()
RESULT_PATH = (
    ANALYSIS
    / "designlibrary_background_filter_constructor_semantics_local_macos_26_6_1_result.json"
)


class BackgroundFilterConstructorSemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(self.source, feature_version=(3, 9))

    def test_operand_split_preserves_memory_operands(self) -> None:
        self.assertEqual(
            analyzer.split_operands("q25, q8, [x1, #0x24]"),
            ["q25", "q8", "[x1, #0x24]"],
        )

    def test_range_normalization_is_exact(self) -> None:
        self.assertEqual(
            analyzer.ranges([8, 9, 11, 12, 13, 20]),
            [[8, 10], [11, 14], [20, 21]],
        )
        self.assertEqual(analyzer.ranges([]), [])

    def test_expected_present_origin_map_has_exact_491_byte_coverage(self) -> None:
        origins = analyzer.expected_present_output()
        expected_offsets = {
            offset
            for start, end in analyzer.INITIALIZED_RANGES
            for offset in range(start, end)
        }
        self.assertEqual(len(origins), 491)
        self.assertEqual(set(origins), expected_offsets)
        self.assertEqual(origins[8], "parameters:0018")
        self.assertEqual(origins[151], "parameters:00a7")
        self.assertEqual(origins[352], "parameters:0188")
        self.assertEqual(origins[495], "parameters:032f")
        self.assertEqual(origins[503], "environmentFlags:0007")

    def test_native_identities_and_full_present_transfer_are_frozen(self) -> None:
        self.assertEqual(
            self.result["constructor"]["sha256"],
            "71a592bc8a187fe8bcca0fa50c3f4d36ea3c2916dbd5d16f3fa1df05b86f131d",
        )
        self.assertEqual(self.result["constructor"]["instructionCount"], 261)
        self.assertEqual(
            self.result["shadowOptionalHelper"]["sha256"],
            "31156c1bee375fc0b5dd502966dbc45ddfd7902d61538e88bbd9fe2752126d28",
        )
        present = self.result["allPresentPath"]
        self.assertTrue(present["all491WrittenByteOriginsProvedExactly"])
        self.assertFalse(present["arithmeticAppliedToPresentPayloadBytes"])
        self.assertEqual(present["writtenByteCount"], 491)
        self.assertEqual(
            present["transfers"],
            [
                {
                    "source": source,
                    "sourceStart": source_start,
                    "outputStart": output_start,
                    "byteCount": byte_count,
                }
                for source, source_start, output_start, byte_count in analyzer.EXPECTED_PRESENT_TRANSFERS
            ],
        )

    def test_every_optional_presence_path_and_nil_padding_are_frozen(self) -> None:
        proof = self.result["optionalPresenceProof"]
        self.assertEqual(proof["pathCount"], 64)
        self.assertTrue(proof["allPathsPreserveExact491ByteWriteCoverage"])
        self.assertEqual(proof["executedInstructionCountRange"], [178, 214])
        self.assertEqual(
            proof["indeterminateOutputRangesAcrossAnyNilPath"],
            [list(value) for value in analyzer.EXPECTED_NIL_INDETERMINATE_RANGES],
        )
        self.assertEqual(
            proof["indeterminateNestedPaddingByteCountAcrossAnyNilPath"],
            25,
        )
        self.assertEqual(
            proof["indeterminateOriginKinds"],
            ["unknown:gpr11", "unknown:stack"],
        )
        self.assertEqual(len(proof["singleAbsentPaths"]), 6)
        self.assertEqual(proof["allAbsentPath"]["parameterOriginOutputRanges"], [])

    def test_branch_contracts_cover_each_optional_group_once(self) -> None:
        contracts = self.result["optionalBranchContracts"]
        self.assertEqual(len(contracts), 6)
        self.assertEqual(
            {value["group"] for value in contracts},
            set(analyzer.GROUPS),
        )
        self.assertEqual(
            {int(value["branchAddress"], 16) for value in contracts},
            set(analyzer.PRESENT_BRANCHES),
        )

    def test_result_matches_exact_source_and_closes_no_later_gate(self) -> None:
        source_hash = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
        result_hash = hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest()
        self.assertEqual(
            source_hash,
            "128ff559e4dc4952164d57244f05343363b5d9bced2b5350c3364433c475b5a1",
        )
        self.assertEqual(
            result_hash,
            "f2502d578a87e33b8db738846d0278522d75d6a317f14bb169408f1d0a6fe690",
        )
        self.assertEqual(self.result["tool"]["sourceSHA256"], source_hash)
        claims = self.result["claims"]
        self.assertTrue(claims["allOptionalPresencePathsExecutedSymbolically"])
        self.assertFalse(claims["publicParametersConstructionLawEstablished"])
        self.assertFalse(claims["upstreamCropAllocationPolicyEstablished"])
        self.assertFalse(claims["independentWalleZeroByteFrameParityEstablished"])
        self.assertFalse(claims["liquidGlassParityEstablished"])
        self.assertFalse(claims["productionShaderChangeAuthorized"])


if __name__ == "__main__":
    unittest.main()
