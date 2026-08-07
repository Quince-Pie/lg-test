#!/usr/bin/env python3
"""Tests for the exact public Parameters-to-BackgroundFilter margin join."""

from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

import capture_designlibrary_public_parameters_background_filter_local_macos_26_6_1 as capture


ANALYSIS = Path(__file__).resolve().parent
CAPTURE_PATH = Path(capture.__file__).resolve()
PROBE_PATH = ANALYSIS / capture.PROBE_SOURCE_NAME
BRIDGE_PATH = ANALYSIS / capture.BRIDGE_SOURCE_NAME
PREDECESSOR_PATH = ANALYSIS / capture.PUBLIC_PARAMETERS_RESULT_NAME
RESULT_PATH = ANALYSIS / (
    "designlibrary_public_parameters_background_filter_local_macos_26_6_1_result.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DesignLibraryPublicParametersBackgroundFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.capture_source = CAPTURE_PATH.read_text(encoding="utf-8")
        cls.probe_source = PROBE_PATH.read_text(encoding="utf-8")
        cls.bridge_source = BRIDGE_PATH.read_text(encoding="utf-8")
        cls.predecessor = json.loads(PREDECESSOR_PATH.read_text(encoding="utf-8"))
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_sources_predecessor_and_result_are_frozen(self) -> None:
        ast.parse(self.capture_source, feature_version=(3, 9))
        hashes = {
            "capture": sha256(CAPTURE_PATH),
            "probe": sha256(PROBE_PATH),
            "bridge": sha256(BRIDGE_PATH),
            "predecessor": sha256(PREDECESSOR_PATH),
            "result": sha256(RESULT_PATH),
        }
        self.assertEqual(
            hashes,
            {
                "capture": "51b6bd9e723373ad45d6235750f793dec4ca2fd1e7817982fc1cc8477ff7739b",
                "probe": "674bec9de543da7827e283ef493ec5f10bd82458b1afec6bc3c65d09e403ef06",
                "bridge": "47f243595c69d779a5d40e205d255b0b5922164039a5f5da6f9f47f784d850e0",
                "predecessor": capture.EXPECTED_PUBLIC_PARAMETERS_RESULT_SHA256,
                "result": "6abfb22e24c5868db0154a3b83038920f76625f7174494ea1dd01d816e0d038f",
            },
        )
        tool = self.result["tool"]
        self.assertEqual(tool["captureSourceSHA256"], hashes["capture"])
        self.assertEqual(tool["probeSourceSHA256"], hashes["probe"])
        self.assertEqual(tool["assemblyBridgeSHA256"], hashes["bridge"])
        self.assertEqual(self.result["predecessor"]["sha256"], hashes["predecessor"])
        self.assertNotIn("/nix/store", self.probe_source)
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
            capture.EXPECTED_DESIGNLIBRARY_UUID,
        )
        self.assertEqual(
            self.result["exactCodeGate"],
            {
                "constructorModuleOffset": 0xBAD00,
                "constructorByteCount": 1044,
                "constructorSHA256": capture.EXPECTED_CONSTRUCTOR_CODE_SHA256,
                "providerModuleOffset": 0xB70B4,
                "providerByteCount": 984,
                "providerSHA256": capture.EXPECTED_PROVIDER_CODE_SHA256,
                "codeAuthenticatedBeforeInputsWritten": True,
            },
        )
        self.assertEqual(
            self.result["controlledConstructorArguments"],
            {"layerIndex": 0, "environmentFlagsRawValue": "0x0000000000000000"},
        )

    def test_all_42_constructor_objects_are_bitwise_exact(self) -> None:
        cases = self.result["cases"]
        self.assertEqual(
            [case["qualifiedName"] for case in cases],
            [case[0] for case in capture.EXPECTED_CASES],
        )
        self.assertEqual([case["index"] for case in cases], list(range(42)))
        unique = self.result["uniqueBackgroundFilters"]
        self.assertEqual(len(unique), 27)
        referenced = set()
        for case, expected in zip(cases, capture.EXPECTED_CASES):
            self.assertEqual(case["backgroundFilterSHA256"], expected[1])
            self.assertEqual(case["marginRawLittleEndianHex"], expected[2])
            record = unique[case["backgroundFilterSHA256"]]
            object_raw = bytes.fromhex(record["hex"])
            self.assertEqual(len(object_raw), capture.BACKGROUND_FILTER_BYTE_COUNT)
            self.assertEqual(hashlib.sha256(object_raw).hexdigest(), expected[1])
            self.assertIn(case["qualifiedName"], record["caseNames"])
            self.assertEqual(object_raw[:8], bytes(8))
            self.assertEqual(object_raw[496:504], bytes(8))
            referenced.add(expected[1])
        self.assertEqual(referenced, set(unique))

    def test_apple_constructor_copies_every_present_provider_group(self) -> None:
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
        identity = self.result["cases"][4]
        identity_object = bytes.fromhex(
            objects[identity["backgroundFilterSHA256"]]["hex"]
        )
        self.assertEqual(identity_object[224:276], bytes(52))

    def test_margin_table_has_three_exact_words_and_fixed_clusters(self) -> None:
        groups = {}
        for case in self.result["cases"]:
            groups.setdefault(case["marginRawLittleEndianHex"], []).append(
                case["qualifiedName"]
            )
        self.assertEqual(
            set(groups),
            {
                "0000000000000000",
                "0000000000005040",
                "3433333333332340",
            },
        )
        self.assertEqual(groups["0000000000005040"], ["static:text"])
        self.assertEqual(
            groups["3433333333332340"],
            [
                "static:siriSnippet",
                "mix:negative_quarter",
                "mix:zero",
                "mix:quarter",
                "mix:half",
                "mix:three_quarters",
            ],
        )
        self.assertEqual(len(groups["0000000000000000"]), 35)
        values = {
            case["marginRawLittleEndianHex"]: case["margin"]
            for case in self.result["cases"]
        }
        self.assertEqual(values["0000000000000000"], 0.0)
        self.assertEqual(values["0000000000005040"], 64.0)
        self.assertEqual(values["3433333333332340"], 9.600000000000001)

    def test_claim_boundary_keeps_animated_crop_and_parity_open(self) -> None:
        invariants = self.result["measuredInvariants"]
        self.assertEqual(invariants["caseCount"], 42)
        self.assertEqual(invariants["uniqueBackgroundFilterCount"], 27)
        self.assertEqual(invariants["backgroundFilterByteCount"], 504)
        self.assertTrue(invariants["freshProcessBitwiseStabilityEstablished"])
        self.assertTrue(
            invariants["constructorAndProviderCodeAuthenticatedBeforeInput"]
        )
        self.assertFalse(invariants["capturedObjectOrMarginUsedForSelection"])
        claims = self.result["claims"]
        self.assertTrue(
            claims["defaultContextPublicParametersToBackgroundFilterEstablished"]
        )
        self.assertTrue(
            claims["defaultContextPublicParametersToMarginTableEstablished"]
        )
        for name in (
            "liveTransitionParametersProductionEstablished",
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
