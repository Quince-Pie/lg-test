#!/usr/bin/env python3
"""Tests for direct public Configuration-to-Resolved native evidence."""

from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

import capture_designlibrary_public_configuration_resolution_local_macos_26_6_1 as capture


ANALYSIS = Path(__file__).resolve().parent
CAPTURE_PATH = Path(capture.__file__).resolve()
PROBE_PATH = ANALYSIS / capture.SOURCE_NAME
BRIDGE_PATH = ANALYSIS / capture.BRIDGE_NAME
RESULT_PATH = ANALYSIS / (
    "designlibrary_public_configuration_resolution_local_macos_26_6_1_result.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DesignLibraryPublicConfigurationResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.capture_source = CAPTURE_PATH.read_text(encoding="utf-8")
        cls.probe_source = PROBE_PATH.read_text(encoding="utf-8")
        cls.bridge_source = BRIDGE_PATH.read_text(encoding="utf-8")
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_sources_and_canonical_result_are_frozen(self) -> None:
        ast.parse(self.capture_source, feature_version=(3, 9))
        hashes = {
            "capture": sha256(CAPTURE_PATH),
            "probe": sha256(PROBE_PATH),
            "bridge": sha256(BRIDGE_PATH),
            "result": sha256(RESULT_PATH),
        }
        self.assertEqual(
            hashes,
            {
                "capture": "188feac1ce112a4e988fbbfe12e157ab3e6a9b734687d67f1c30c177395e49c6",
                "probe": "46db6fb3fa1f2803fe1aaa14c7221f8eca24babee05613b441d1e13143c54d58",
                "bridge": "9f58cbef6e4875f9fb377f4018913d6336b6c906c1a37a1117d137ac373fef2d",
                "result": "65939d2055fb3c097c3718bb1f8cab06e7ebd3a1854d67cfc54c6ceed630ea59",
            },
        )
        tool = self.result["tool"]
        self.assertEqual(tool["captureSourceSHA256"], hashes["capture"])
        self.assertEqual(tool["probeSourceSHA256"], hashes["probe"])
        self.assertEqual(tool["assemblyBridgeSHA256"], hashes["bridge"])
        self.assertNotIn("/nix/store", self.probe_source)
        self.assertNotIn("import DesignLibrary", self.capture_source)

    def test_host_runtime_layouts_and_initial_state_are_exact(self) -> None:
        self.assertEqual(
            self.result["host"],
            {
                "system": "Darwin",
                "machine": "arm64",
                "macOSProductVersion": "26.6.1",
                "macOSBuildVersion": "25G76",
                "hardwareModel": "MacBookPro18,2",
            },
        )
        layouts = self.result["runtimeLayouts"]
        for name, expected in capture.EXPECTED_LAYOUTS.items():
            observed = layouts[name]
            self.assertEqual((observed["size"], observed["stride"]), expected[:2])
            self.assertEqual(
                observed["valueWitnessFlags"],
                "0x{0:08x}".format(expected[2]),
            )
            self.assertEqual(observed["extraInhabitantCount"], expected[3])
            self.assertEqual(
                [(field["name"], field["offset"]) for field in observed["fields"]],
                list(capture.EXPECTED_FIELDS.get(name, ())),
            )
        self.assertEqual(
            self.result["initialState"],
            {
                "adaptedColorSchemeStorage": 2,
                "awaitingInitialLuminanceStorage": 1,
                "flagsBits": "0x0000000000000000",
                "fixedBackgroundColorStorageHex": "00" * 16 + "01",
            },
        )

    def test_all_exported_static_configuration_defaults_are_resolved(self) -> None:
        records = {
            record["name"]: record["resolvedConfiguration"]
            for record in self.result["staticConfigurations"]
        }
        self.assertEqual(tuple(records), capture.STATIC_NAMES)
        self.assertEqual(len(records), 27)
        self.assertEqual(
            records["regular"],
            {
                "baseStorageHex": "010000000000000000000000c0",
                "subvariantStorage": 0,
                "frostStorage": 0,
                "optionsBits": "0x0000000000004000",
                "environmentFlagsBits": "0x0000000000000000",
                "interactionStorage": 0,
                "optimizationLevelStorage": 0,
                "contentEffectStorage": 0,
                "layersBits": "0x000000000006035f",
                "colorSchemeStorage": 0,
            },
        )
        self.assertEqual(records["clear"]["baseStorageHex"], "03" + "00" * 11 + "c0")
        self.assertEqual(records["clear"]["layersBits"], "0x000000000006031e")
        self.assertEqual(records["identity"]["baseStorageHex"], "00" * 12 + "c0")
        self.assertEqual(records["identity"]["layersBits"], "0x000000000004035f")
        self.assertEqual(records["focusBorder"], records["focusPlatter"])
        self.assertEqual(records["avplayer"], records["facetime"])
        self.assertNotEqual(records["appIcons"]["layersBits"], records["widgets"]["layersBits"])

    def test_regular_clear_mix_payload_and_fraction_bits_are_exact(self) -> None:
        records = self.result["regularToClearMixes"]
        self.assertEqual(
            [(record["name"], record["fraction"]) for record in records],
            list(capture.MIX_FRACTIONS),
        )
        self.assertEqual(
            [record["fractionBits"] for record in records],
            [
                "0xbfd0000000000000",
                "0x0000000000000000",
                "0x3fd0000000000000",
                "0x3fe0000000000000",
                "0x3fe8000000000000",
                "0x3ff0000000000000",
                "0x3ff4000000000000",
            ],
        )
        self.assertEqual({record["outerBaseRepresentation"]["tagByte"] for record in records}, {128})
        self.assertEqual({json.dumps(record["from"], sort_keys=True) for record in records}, {
            json.dumps(records[0]["from"], sort_keys=True)
        })
        self.assertEqual({json.dumps(record["to"], sort_keys=True) for record in records}, {
            json.dumps(records[0]["to"], sort_keys=True)
        })
        half = records[3]
        self.assertEqual(half["from"]["environmentFlagsBits"], "0x0000000000099183")
        self.assertEqual(half["to"]["environmentFlagsBits"], "0x0000000000088183")
        self.assertEqual(half["from"]["baseStorageHex"], "010000000000000000000000c0")
        self.assertEqual(half["to"]["baseStorageHex"], "030000000000000000000000c0")

    def test_color_and_adaptive_modifier_policies_are_exact(self) -> None:
        records = {record["name"]: record for record in self.result["regularModifiers"]}
        self.assertEqual(tuple(records), capture.MODIFIER_NAMES)
        self.assertEqual(records["color_scheme_light"]["publicConfigurationColorSchemeStorage"], 0)
        self.assertEqual(records["color_scheme_dark"]["publicConfigurationColorSchemeStorage"], 1)
        self.assertEqual(
            records["color_scheme_light"]["resolvedConfiguration"],
            records["color_scheme_dark"]["resolvedConfiguration"],
        )
        expected_options = {
            "color_scheme_light": "0x0000000000000000",
            "color_scheme_dark": "0x0000000000000000",
            "adaptive_false": "0x0000000000000000",
            "adaptive_true": "0x0000000000004000",
            "adaptive_light": "0x0000000000004000",
            "adaptive_dark": "0x0000000000004000",
            "adaptive_animatable_false": "0x0000000000404000",
            "adaptive_animatable_true": "0x0000000000004000",
        }
        self.assertEqual(
            {
                name: record["publicConfigurationOptionsBits"]
                for name, record in records.items()
            },
            expected_options,
        )
        self.assertEqual(
            {
                name: record["resolvedConfiguration"]["optionsBits"]
                for name, record in records.items()
            },
            expected_options,
        )

    def test_claims_close_only_the_measured_boundary(self) -> None:
        invariants = self.result["measuredInvariants"]
        self.assertEqual(invariants["staticConfigurationCount"], 27)
        self.assertEqual(invariants["mixFractionCount"], 7)
        self.assertEqual(invariants["modifierCount"], 8)
        self.assertTrue(invariants["providerInitializerCopiesAllConfigurationBytes"])
        self.assertTrue(invariants["resolvedStyleCopiesAllConfigurationBytes"])
        self.assertTrue(invariants["publicMixFractionPreservedBitwise"])
        self.assertTrue(invariants["freshProcessSemanticStabilityEstablished"])
        claims = self.result["claims"]
        self.assertTrue(claims["publicStaticConfigurationDefaultsToResolvedKeysEstablished"])
        self.assertTrue(claims["publicRegularClearMixRuntimePayloadEstablished"])
        self.assertTrue(claims["publicRegularColorAndAdaptiveModifierResolutionEstablished"])
        self.assertTrue(claims["initialProviderStateLayoutEstablished"])
        self.assertFalse(claims["environmentToConfigurationSelectionLawEstablished"])
        self.assertFalse(claims["transitionProgressProductionLawEstablished"])
        self.assertFalse(claims["integerCropAllocationPolicyEstablished"])
        self.assertFalse(claims["retinaCompositorColorLawEstablished"])
        self.assertFalse(claims["independentWalleZeroByteFrameParityEstablished"])
        self.assertFalse(claims["liquidGlassParityEstablished"])
        self.assertFalse(claims["productionShaderChangeAuthorized"])


if __name__ == "__main__":
    unittest.main()
