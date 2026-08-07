#!/usr/bin/env python3
"""Tests for public Configuration mix pass-through and direct one-hot resolution."""

from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

import analyze_designlibrary_configuration_mix_selection_local_macos_26_6_1 as analyzer


ANALYSIS = Path(__file__).resolve().parent
SOURCE_PATH = Path(analyzer.__file__).resolve()
RESULT_PATH = ANALYSIS / (
    "designlibrary_configuration_mix_selection_local_macos_26_6_1_result.json"
)


class ConfigurationMixSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(self.source, feature_version=(3, 9))

    def test_exact_mix_key_and_resolved_layouts_are_frozen(self) -> None:
        observed = self.result["swiftDescriptors"]
        self.assertEqual(set(observed), set(analyzer.DESCRIPTORS))
        for role, expected in analyzer.DESCRIPTORS.items():
            descriptor = observed[role]
            self.assertEqual(
                descriptor["descriptorAddress"],
                "0x{:x}".format(expected["address"]),
            )
            self.assertEqual(descriptor["name"], expected["name"])
            self.assertEqual(
                tuple(field["name"] for field in descriptor["fields"]),
                expected["fields"],
            )
            if expected["offsets"] is None:
                self.assertIsNone(descriptor["metadata"])
            else:
                layout = descriptor["metadata"]
                self.assertEqual(tuple(layout["fieldOffsets"]), expected["offsets"])
                self.assertEqual(layout["size"], expected["size"])
                self.assertEqual(layout["stride"], expected["stride"])

    def test_all_code_regions_callers_and_floating_operations_are_frozen(self) -> None:
        regions = self.result["codeRegions"]
        self.assertEqual(set(regions), set(analyzer.CODE_REGIONS))
        for name, (start, end, expected_sha256) in analyzer.CODE_REGIONS.items():
            record = regions[name]
            self.assertEqual(record["start"], "0x{:x}".format(start))
            self.assertEqual(record["endExclusive"], "0x{:x}".format(end))
            self.assertEqual(record["byteCount"], end - start)
            self.assertEqual(record["instructionCount"], (end - start) // 4)
            self.assertEqual(record["sha256"], expected_sha256)
        self.assertEqual(
            {
                name: tuple(int(address, 16) for address in addresses)
                for name, addresses in self.result["directBLCallsites"].items()
            },
            analyzer.EXPECTED_DIRECT_CALLS,
        )
        self.assertEqual(
            self.result["floatingInstructionInventories"],
            analyzer.EXPECTED_FLOATING_INVENTORIES,
        )

    def test_public_fraction_is_copied_to_resolved_mix_without_arithmetic(self) -> None:
        model = self.result["configurationMixModel"]
        self.assertEqual(model["sourceFields"], ["from", "to", "fraction"])
        self.assertEqual(model["sourceFractionType"], "Double")
        self.assertEqual(
            model["resolvedLayout"],
            {
                "fromOffset": 0,
                "toOffset": 48,
                "fractionOffset": 96,
                "size": 104,
                "stride": 104,
            },
        )
        self.assertEqual(
            self.result["floatingInstructionInventories"]["publicConfigurationMix"],
            {},
        )
        self.assertEqual(
            self.result["floatingInstructionInventories"][
                "resolvedConfigurationMixBuilder"
            ],
            {},
        )

    def test_direct_resolve_emits_one_exact_key_at_binary64_one(self) -> None:
        header = self.result["directDictionaryStorageHeader"]
        self.assertEqual(header["address"], "0x2409af6f0")
        self.assertEqual(header["bytes"], analyzer.DIRECT_DICTIONARY_HEADER.hex())
        self.assertEqual(header["littleEndianWords"], [1, 2])
        model = self.result["directResolveCompositeModel"]
        self.assertEqual(model["keyType"], "(ResolvedConfiguration, ColorScheme)")
        self.assertEqual(model["dictionaryEntryCount"], 1)
        self.assertEqual(model["dictionaryValueBits"], "0x3ff0000000000000")
        self.assertEqual(model["dictionaryValue"], 1.0)

    def test_public_mix_and_resolved_animation_are_not_conflated(self) -> None:
        boundary = self.result["mechanismBoundary"]
        self.assertFalse(boundary["sameMechanism"])
        claims = self.result["claims"]
        self.assertTrue(claims["publicConfigurationMixByStoredBitwiseUnchanged"])
        self.assertTrue(
            claims["configurationMixByCopiedToResolvedFractionBitwiseUnchanged"]
        )
        self.assertTrue(claims["directResolveProducesExactlyOneKeyAtBinary64One"])
        self.assertTrue(
            claims["publicConfigurationMixDistinctFromResolvedAnimationWeights"]
        )

    def test_result_matches_source_and_does_not_overclaim_parity(self) -> None:
        source_hash = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
        result_hash = hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest()
        self.assertEqual(
            source_hash,
            "93c95c65c326765c675f3f4e727285706bf48adb5d42d5bdcd11ad0c3600d1de",
        )
        self.assertEqual(
            result_hash,
            "b9e7fb7167e932f6b10409db09a3abd99d0ca019a56bb104572d8188f35d928d",
        )
        self.assertEqual(self.result["tool"]["sourceSHA256"], source_hash)
        claims = self.result["claims"]
        self.assertFalse(
            claims["transitionProgressToPublicConfigurationMixByLawEstablished"]
        )
        self.assertFalse(
            claims["publicControlsToResolvedConfigurationSelectionLawEstablished"]
        )
        self.assertFalse(
            claims["environmentToResolvedConfigurationSelectionLawEstablished"]
        )
        self.assertFalse(claims["allRuntimeWeightProductionLawEstablished"])
        self.assertFalse(
            claims["resolvedConfigurationMixConsumptionArithmeticEstablished"]
        )
        self.assertFalse(claims["cropAllocationPolicyEstablished"])
        self.assertFalse(claims["retinaCompositorColorLawEstablished"])
        self.assertFalse(claims["independentWalleZeroByteFrameParityEstablished"])
        self.assertFalse(claims["liquidGlassParityEstablished"])
        self.assertFalse(claims["productionShaderChangeAuthorized"])


if __name__ == "__main__":
    unittest.main()
