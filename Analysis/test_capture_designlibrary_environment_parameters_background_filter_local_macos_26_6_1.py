#!/usr/bin/env python3
"""Tests for the exact flags-produced Environment-to-filter join."""

from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

import capture_designlibrary_environment_parameters_background_filter_local_macos_26_6_1 as capture
import capture_designlibrary_public_parameters_background_filter_local_macos_26_6_1 as base


ANALYSIS = Path(__file__).resolve().parent
CAPTURE_PATH = Path(capture.__file__).resolve()
PROBE_PATH = ANALYSIS / capture.PROBE_SOURCE_NAME
BASE_PROBE_PATH = ANALYSIS / base.PROBE_SOURCE_NAME
BRIDGE_PATH = ANALYSIS / base.BRIDGE_SOURCE_NAME
PREDECESSOR_PATH = ANALYSIS / capture.ENVIRONMENT_PARAMETERS_RESULT_NAME
RESULT_PATH = ANALYSIS / (
    "designlibrary_environment_parameters_background_filter_"
    "local_macos_26_6_1_result.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DesignLibraryEnvironmentParametersBackgroundFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.capture_source = CAPTURE_PATH.read_text(encoding="utf-8")
        cls.probe_source = PROBE_PATH.read_text(encoding="utf-8")
        cls.base_probe_source = BASE_PROBE_PATH.read_text(encoding="utf-8")
        cls.bridge_source = BRIDGE_PATH.read_text(encoding="utf-8")
        cls.predecessor = json.loads(PREDECESSOR_PATH.read_text(encoding="utf-8"))
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_sources_predecessor_and_result_are_frozen(self) -> None:
        ast.parse(self.capture_source, feature_version=(3, 9))
        hashes = {
            "capture": sha256(CAPTURE_PATH),
            "probe": sha256(PROBE_PATH),
            "baseProbe": sha256(BASE_PROBE_PATH),
            "bridge": sha256(BRIDGE_PATH),
            "predecessor": sha256(PREDECESSOR_PATH),
            "result": sha256(RESULT_PATH),
        }
        self.assertEqual(
            hashes,
            {
                "capture": (
                    "08708c0f4717d9496202ed14c03278a4084407816e18d1dfbd8ec58779eb7ac5"
                ),
                "probe": (
                    "9536abaf99ae6d78663981c90afcd80aab5654fde12366c996039dd71b01f52c"
                ),
                "baseProbe": capture.EXPECTED_BASE_PROBE_SOURCE_SHA256,
                "bridge": (
                    "47f243595c69d779a5d40e205d255b0b5922164039a5f5da6f9f47f784d850e0"
                ),
                "predecessor": (capture.EXPECTED_ENVIRONMENT_PARAMETERS_RESULT_SHA256),
                "result": (
                    "69c19f885c9de3a4b052f602931b2aba6c5fcf76e8831df0f626a050cb95655a"
                ),
            },
        )
        tool = self.result["tool"]
        self.assertEqual(tool["captureSourceSHA256"], hashes["capture"])
        self.assertEqual(tool["probeSourceSHA256"], hashes["probe"])
        self.assertEqual(tool["includedBaseProbeSourceSHA256"], hashes["baseProbe"])
        self.assertEqual(tool["assemblyBridgeSHA256"], hashes["bridge"])
        self.assertEqual(self.result["predecessor"]["sha256"], hashes["predecessor"])
        self.assertNotIn("/nix/store", self.probe_source)
        self.assertNotIn("/nix/store", self.base_probe_source)
        self.assertNotIn("/nix/store", self.bridge_source)
        self.assertFalse(tool["probeExecutableContainsNixStorePath"])

    def test_host_and_exact_code_gate_are_authenticated(self) -> None:
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
        self.assertEqual(
            self.result["framework"]["uuid"],
            base.EXPECTED_DESIGNLIBRARY_UUID,
        )
        self.assertEqual(
            self.result["exactCodeGate"],
            {
                "constructorModuleOffset": 0xBAD00,
                "constructorByteCount": 1044,
                "constructorSHA256": base.EXPECTED_CONSTRUCTOR_CODE_SHA256,
                "providerModuleOffset": 0xB70B4,
                "providerByteCount": 984,
                "providerSHA256": base.EXPECTED_PROVIDER_CODE_SHA256,
                "codeAuthenticatedBeforeInputsWritten": True,
            },
        )
        self.assertEqual(self.result["tool"]["freshProcessCount"], 3)

    def test_all_36_objects_flags_and_margins_are_bitwise_exact(self) -> None:
        cases = self.result["cases"]
        self.assertEqual(
            [case["name"] for case in cases],
            [expected[0] for expected in capture.EXPECTED_CASES],
        )
        self.assertEqual([case["index"] for case in cases], list(range(36)))
        unique = self.result["uniqueBackgroundFilters"]
        self.assertEqual(len(unique), 11)
        referenced = set()
        for case, expected in zip(cases, capture.EXPECTED_CASES):
            self.assertEqual(case["backgroundFilterSHA256"], expected[1])
            self.assertEqual(case["marginRawLittleEndianHex"], expected[2])
            record = unique[case["backgroundFilterSHA256"]]
            object_raw = bytes.fromhex(record["hex"])
            flags_raw = bytes.fromhex(case["producedFlagsRawLittleEndianHex"])
            self.assertEqual(len(object_raw), base.BACKGROUND_FILTER_BYTE_COUNT)
            self.assertEqual(hashlib.sha256(object_raw).hexdigest(), expected[1])
            self.assertEqual(object_raw[:8], bytes(8))
            self.assertEqual(object_raw[496:504], flags_raw)
            self.assertEqual(
                int.from_bytes(flags_raw, "little"),
                int(case["producedFlagsBits"], 16),
            )
            self.assertIn(case["name"], record["caseNames"])
            referenced.add(expected[1])
        self.assertEqual(referenced, set(unique))

    def test_constructor_copies_all_present_parameters_groups(self) -> None:
        parameter_blobs = self.predecessor["uniqueNormalizedParameters"]
        objects = self.result["uniqueBackgroundFilters"]
        for case in self.result["cases"]:
            parameters = bytes.fromhex(
                parameter_blobs[case["normalizedParametersSHA256"]]["normalizedHex"]
            )
            background_filter = bytes.fromhex(
                objects[case["backgroundFilterSHA256"]]["hex"]
            )
            if parameters[168] != 1:
                self.assertEqual(background_filter[8:152], parameters[24:168])
            if parameters[248] != 1:
                self.assertEqual(background_filter[152:224], parameters[176:248])
            if parameters[308] != 1:
                self.assertEqual(background_filter[224:276], parameters[256:308])
            if parameters[385] != 1:
                self.assertEqual(background_filter[276:349], parameters[312:385])
            if int.from_bytes(parameters[496:498], "little") != 0x200:
                self.assertEqual(background_filter[352:458], parameters[392:498])
            if parameters[816] != 1:
                self.assertEqual(background_filter[464:476], parameters[784:796])
                self.assertEqual(background_filter[480:496], parameters[800:816])

    def test_equal_parameters_can_still_have_distinct_flags_objects(self) -> None:
        by_name = {case["name"]: case for case in self.result["cases"]}
        baseline = by_name["baseline"]
        for name in ("appears_active_false", "has_tinted_elements_true"):
            case = by_name[name]
            self.assertEqual(
                case["normalizedParametersSHA256"],
                baseline["normalizedParametersSHA256"],
            )
            self.assertNotEqual(
                case["producedFlagsBits"], baseline["producedFlagsBits"]
            )
            self.assertNotEqual(
                case["backgroundFilterSHA256"],
                baseline["backgroundFilterSHA256"],
            )
        inactive = by_name["window_active_false"]
        nonforeground = by_name["glass_foreground_false"]
        self.assertEqual(
            inactive["normalizedParametersSHA256"],
            nonforeground["normalizedParametersSHA256"],
        )
        self.assertNotEqual(
            inactive["backgroundFilterSHA256"],
            nonforeground["backgroundFilterSHA256"],
        )

    def test_margin_table_has_two_words_and_exact_clusters(self) -> None:
        groups = {}
        for case in self.result["cases"]:
            groups.setdefault(case["marginRawLittleEndianHex"], []).append(case["name"])
        self.assertEqual(
            set(groups),
            {"0000000000000000", "3433333333332340"},
        )
        self.assertEqual(
            groups["0000000000000000"],
            [
                "window_active_false",
                "glass_foreground_false",
                "reduce_transparency_true",
            ],
        )
        self.assertEqual(len(groups["3433333333332340"]), 33)
        values = {
            case["marginRawLittleEndianHex"]: case["margin"]
            for case in self.result["cases"]
        }
        self.assertEqual(values["0000000000000000"], 0.0)
        self.assertEqual(values["3433333333332340"], 9.600000000000001)

    def test_claim_boundary_keeps_live_crop_retina_and_parity_open(self) -> None:
        invariants = self.result["measuredInvariants"]
        self.assertEqual(invariants["environmentCaseCount"], 36)
        self.assertEqual(invariants["uniqueBackgroundFilterCount"], 11)
        self.assertEqual(invariants["backgroundFilterByteCount"], 504)
        self.assertTrue(invariants["environmentFlagsEmbeddedBitwiseAtObjectOffset496"])
        self.assertTrue(invariants["freshProcessBitwiseStabilityEstablished"])
        self.assertTrue(
            invariants["constructorAndProviderCodeAuthenticatedBeforeInput"]
        )
        self.assertFalse(invariants["capturedObjectOrMarginUsedForSelection"])
        claims = self.result["claims"]
        self.assertTrue(
            claims["controlledFlagsProducedEnvironmentToBackgroundFilterEstablished"]
        )
        self.assertTrue(
            claims["controlledFlagsProducedEnvironmentToMarginTableEstablished"]
        )
        for name in (
            "liveSwiftUIEnvironmentUpdaterEstablished",
            "liveTransitionProgressProductionLawEstablished",
            "liveTransitionMarginMaximumPolicyEstablished",
            "generalIntegerCropAllocationPolicyEstablished",
            "retinaCompositorColorLawEstablished",
            "independentWalleZeroByteFrameParityEstablished",
            "liquidGlassParityEstablished",
            "productionShaderChangeAuthorized",
        ):
            self.assertFalse(claims[name])


if __name__ == "__main__":
    unittest.main()
