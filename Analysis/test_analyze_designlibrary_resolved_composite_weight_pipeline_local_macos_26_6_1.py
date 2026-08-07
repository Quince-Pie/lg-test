#!/usr/bin/env python3
"""Tests for the native ResolvedComposite keyed-weight pipeline proof."""

from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

import analyze_designlibrary_resolved_composite_weight_pipeline_local_macos_26_6_1 as analyzer


ANALYSIS = Path(__file__).resolve().parent
SOURCE_PATH = Path(analyzer.__file__).resolve()
RESULT_PATH = ANALYSIS / (
    "designlibrary_resolved_composite_weight_pipeline_local_macos_26_6_1_result.json"
)


class ResolvedCompositeWeightPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(self.source, feature_version=(3, 9))

    def test_exact_swift_descriptors_and_layouts_are_frozen(self) -> None:
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

    def test_values_key_and_mix_types_are_semantically_exact(self) -> None:
        descriptors = self.result["swiftDescriptors"]
        values = descriptors["resolvedComposite"]["fields"][0]
        self.assertEqual(values["name"], "values")
        self.assertEqual(
            values["typeReference"],
            analyzer.EXPECTED_TYPE_REFERENCES[("resolvedComposite", "values")],
        )
        key_fields = descriptors["resolvedCompositeKey"]["fields"]
        self.assertEqual(
            tuple(field["name"] for field in key_fields),
            ("resolved", "colorScheme"),
        )
        mix = descriptors["resolvedConfigurationMix"]
        self.assertEqual(
            tuple(field["name"] for field in mix["fields"]),
            ("from", "to", "fraction"),
        )
        self.assertEqual(tuple(mix["metadata"]["fieldOffsets"]), (0, 48, 96))
        self.assertEqual(mix["metadata"]["size"], 104)

    def test_all_code_regions_callers_and_arithmetic_are_frozen(self) -> None:
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

    def test_composite_arithmetic_contract_is_exact(self) -> None:
        model = self.result["resolvedCompositeModel"]
        self.assertEqual(model["valuesType"], "Dictionary<ResolvedComposite.Key, Double>")
        self.assertEqual(model["keyType"], "(ResolvedConfiguration, ColorScheme)")
        self.assertEqual(model["luminanceType"], "Float")
        self.assertEqual(model["zero"]["values"], "empty dictionary")
        self.assertEqual(
            model["addition"]["sharedKeyOperation"], "binary64 addition"
        )
        self.assertEqual(
            model["subtraction"]["rightOnlyOperation"], "binary64 negation"
        )
        self.assertEqual(
            model["scale"]["nonzeroValueOperation"],
            "each binary64 value multiplied by binary64 factor",
        )
        self.assertEqual(
            model["scale"]["zeroFactorOperation"],
            "canonical empty dictionary and zero luminance",
        )

    def test_exact_dictionary_pointer_reaches_builder_count_and_d9(self) -> None:
        join = self.result["builderWeightJoin"]
        self.assertEqual(join["producer"], "Resolved.composite.values at runtime offset 0")
        self.assertEqual(join["publicResolveLayersHelperCallsite"], "0x240923628")
        self.assertEqual(join["resolvedRecipeBuilderRegister"], "x2")
        self.assertEqual(join["builderDictionarySlot"], "builder stack + 0x88")
        self.assertEqual(join["builderCountSlot"], "builder stack + 0xb0")
        self.assertEqual(join["builderFactorRegister"], "d9")
        self.assertTrue(join["preservesDictionaryPointerAcrossJoin"])

    def test_result_matches_source_and_does_not_overclaim_parity(self) -> None:
        source_hash = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
        result_hash = hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest()
        self.assertEqual(
            source_hash,
            "530922f37038ca23dbfe3cca43c3fe3a703fdf337dde7f393afda180b41ea3d0",
        )
        self.assertEqual(
            result_hash,
            "f5e87599e3eb8e6a734e0618b51b077742bb04558355b2dad48a580b51edb558",
        )
        self.assertEqual(self.result["tool"]["sourceSHA256"], source_hash)
        claims = self.result["claims"]
        self.assertTrue(claims["resolvedCompositeValuesAreKeyedBinary64Weights"])
        self.assertTrue(claims["resolvedCompositeVectorArithmeticEstablished"])
        self.assertTrue(
            claims["resolvedCompositeDictionaryPointerReachesRecipeBuilderUnchanged"]
        )
        self.assertTrue(claims["recipeBuilderD9FactorComesFromResolvedCompositeValues"])
        self.assertFalse(
            claims["publicControlsToResolvedConfigurationSelectionLawEstablished"]
        )
        self.assertFalse(
            claims["environmentToResolvedConfigurationSelectionLawEstablished"]
        )
        self.assertFalse(claims["transitionProgressToMixFractionLawEstablished"])
        self.assertFalse(claims["allRuntimeWeightProductionLawEstablished"])
        self.assertFalse(claims["cropAllocationPolicyEstablished"])
        self.assertFalse(claims["retinaCompositorColorLawEstablished"])
        self.assertFalse(claims["independentWalleZeroByteFrameParityEstablished"])
        self.assertFalse(claims["liquidGlassParityEstablished"])
        self.assertFalse(claims["productionShaderChangeAuthorized"])


if __name__ == "__main__":
    unittest.main()
