#!/usr/bin/env python3
"""Tests for ResolvedConfiguration.Mix routing into the Parameters mixer."""

from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

import analyze_designlibrary_resolved_configuration_mix_parameters_consumer_local_macos_26_6_1 as analyzer


ANALYSIS = Path(__file__).resolve().parent
SOURCE_PATH = Path(analyzer.__file__).resolve()
RESULT_PATH = ANALYSIS / (
    "designlibrary_resolved_configuration_mix_parameters_consumer_"
    "local_macos_26_6_1_result.json"
)


class ResolvedConfigurationMixParametersConsumerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(self.source, feature_version=(3, 9))

    def test_exact_key_configuration_mix_and_parameters_layouts_are_frozen(
        self,
    ) -> None:
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

    def test_complete_regions_callers_call_graph_and_floating_ops_are_frozen(
        self,
    ) -> None:
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
            {
                int(destination, 16): tuple(
                    int(address, 16) for address in addresses
                )
                for destination, addresses in self.result[
                    "parametersMixerDirectCallGraph"
                ].items()
            },
            analyzer.EXPECTED_PARAMETERS_MIXER_CALL_GRAPH,
        )
        self.assertEqual(
            self.result["floatingInstructionInventories"],
            analyzer.EXPECTED_FLOATING_INVENTORIES,
        )

    def test_builder_mix_dispatch_and_recursive_consumer_join_are_exact(
        self,
    ) -> None:
        model = self.result["consumerModel"]
        self.assertEqual(model["resolvedConfigurationByteCount"], 48)
        self.assertEqual(model["mixDiscriminatorValue"], 2)
        self.assertEqual(
            model["mixPayloadSemanticOffsets"],
            {"from": 0, "to": 48, "fraction": 96},
        )
        self.assertEqual(
            model["mixPayloadBoxOffsets"],
            {"from": 16, "to": 64, "fraction": 112},
        )
        claims = self.result["claims"]
        self.assertTrue(claims["builderKeyResolvedConfigurationConsumerJoinEstablished"])
        self.assertTrue(claims["builderSeparatesResolvedConfigurationAndColorScheme"])
        self.assertTrue(claims["resolvedConfigurationMixDispatchEstablished"])
        self.assertTrue(claims["resolvedConfigurationMixEndpointsRecursivelyConsumed"])
        self.assertTrue(
            claims["resolvedConfigurationMixFractionPassedToMixerBitwiseUnchanged"]
        )

    def test_parameters_mixer_abi_transfer_and_weight_derivation_are_exact(
        self,
    ) -> None:
        model = self.result["parametersMixerModel"]
        self.assertEqual(
            {
                "from": model["fromRegister"],
                "to": model["toRegister"],
                "fraction": model["fractionRegister"],
                "output": model["outputRegister"],
            },
            {"from": "x20", "to": "x0", "fraction": "d0", "output": "x8"},
        )
        self.assertEqual(model["parametersByteCount"], 1025)
        self.assertEqual(
            model["universalBinary64Weights"],
            {"from": "1.0 - t", "to": "t", "operation": "one binary64 fsub"},
        )
        self.assertEqual(model["binary32WeightConversionCount"], 2)
        self.assertEqual(
            model["backdropScale"],
            {
                "type": "Float",
                "tLessThanOrEqualToZero": "from",
                "tGreaterThanOrEqualToOne": "to",
                "strictInteriorOrderedInputs": "larger of from and to",
            },
        )

    def test_result_matches_source_and_does_not_overclaim_parity(self) -> None:
        source_hash = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
        result_hash = hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest()
        self.assertEqual(
            source_hash,
            "611ef68e46ec5f1cd962e6e870fa2b140ba73c5da4cf7b3f95408a90d6be1b0f",
        )
        self.assertEqual(
            result_hash,
            "596aae0aa2d366a61fc964877b594ffcf23c6b6151adbe449c4c391c4918e30e",
        )
        self.assertEqual(self.result["tool"]["sourceSHA256"], source_hash)
        claims = self.result["claims"]
        self.assertFalse(claims["allParametersFieldBlendSemanticsEstablished"])
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
        self.assertFalse(claims["cropAllocationPolicyEstablished"])
        self.assertFalse(claims["retinaCompositorColorLawEstablished"])
        self.assertFalse(claims["independentWalleZeroByteFrameParityEstablished"])
        self.assertFalse(claims["liquidGlassParityEstablished"])
        self.assertFalse(claims["productionShaderChangeAuthorized"])


if __name__ == "__main__":
    unittest.main()
