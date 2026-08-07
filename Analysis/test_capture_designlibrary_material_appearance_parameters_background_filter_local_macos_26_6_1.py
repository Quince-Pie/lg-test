#!/usr/bin/env python3
"""Tests for exact four-profile BackgroundFilter and margin evidence."""

from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

import capture_designlibrary_material_appearance_parameters_background_filter_local_macos_26_6_1 as capture


ANALYSIS = Path(__file__).resolve().parent
CAPTURE_PATH = Path(capture.__file__).resolve()
PROBE_PATH = ANALYSIS / capture.PROBE_SOURCE_NAME
BASE_PROBE_PATH = ANALYSIS / capture.join.base.PROBE_SOURCE_NAME
BRIDGE_PATH = ANALYSIS / capture.join.base.BRIDGE_SOURCE_NAME
PREDECESSOR_PATH = ANALYSIS / capture.PROFILE_PARAMETERS_RESULT_NAME
RESULT_PATH = ANALYSIS / (
    "designlibrary_material_appearance_parameters_background_filter_"
    "local_macos_26_6_1_result.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DesignLibraryMaterialAppearanceBackgroundFilterTests(unittest.TestCase):
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
                    "8def21b0a8e3551377d286cbed469f420bbd84cf7950619354b14917e62f58ec"
                ),
                "probe": capture.EXPECTED_ENVIRONMENT_PROBE_SOURCE_SHA256,
                "baseProbe": capture.join.EXPECTED_BASE_PROBE_SOURCE_SHA256,
                "bridge": (
                    "47f243595c69d779a5d40e205d255b0b5922164039a5f5da6f9f47f784d850e0"
                ),
                "predecessor": capture.EXPECTED_PROFILE_PARAMETERS_RESULT_SHA256,
                "result": (
                    "220b1a7bd8ed778016002a89274efc18ea1d5cd36c4b7990655d689a9dd0c48b"
                ),
            },
        )
        tool = self.result["tool"]
        self.assertEqual(tool["captureSourceSHA256"], hashes["capture"])
        self.assertEqual(tool["probeSourceSHA256"], hashes["probe"])
        self.assertEqual(tool["includedBaseProbeSourceSHA256"], hashes["baseProbe"])
        self.assertEqual(tool["assemblyBridgeSHA256"], hashes["bridge"])
        self.assertEqual(self.result["predecessor"]["sha256"], hashes["predecessor"])
        self.assertFalse(tool["probeExecutableContainsNixStorePath"])

    def test_prediction_and_exact_code_gates_are_frozen(self) -> None:
        self.assertEqual(
            self.result["predictionBasis"],
            {
                "constructorCopyLawUsed": True,
                "exactEnvironmentFlagsUsed": True,
                "authenticatedProviderInstructionReplayUsed": True,
                "expectedObjectAndMarginIdentitiesFixedBeforeNativeJoin": True,
            },
        )
        self.assertEqual(
            self.result["exactCodeGate"],
            {
                "constructorModuleOffset": 0xBAD00,
                "constructorByteCount": 1044,
                "constructorSHA256": (
                    capture.join.base.EXPECTED_CONSTRUCTOR_CODE_SHA256
                ),
                "providerModuleOffset": 0xB70B4,
                "providerByteCount": 984,
                "providerSHA256": capture.join.base.EXPECTED_PROVIDER_CODE_SHA256,
                "codeAuthenticatedBeforeInputsWritten": True,
            },
        )
        self.assertEqual(self.result["tool"]["freshProcessCount"], 3)

    def test_all_four_predicted_objects_and_margins_match_bitwise(self) -> None:
        cases = self.result["cases"]
        self.assertEqual(
            [case["name"] for case in cases],
            [expected[0] for expected in capture.EXPECTED_CASES],
        )
        self.assertEqual([case["index"] for case in cases], list(range(4)))
        unique = self.result["uniqueBackgroundFilters"]
        self.assertEqual(len(unique), 3)
        for case, expected in zip(cases, capture.EXPECTED_CASES):
            self.assertEqual(case["backgroundFilterSHA256"], expected[1])
            self.assertEqual(case["marginRawLittleEndianHex"], expected[2])
            object_raw = bytes.fromhex(unique[expected[1]]["hex"])
            flags_raw = bytes.fromhex(case["producedFlagsRawLittleEndianHex"])
            self.assertEqual(
                len(object_raw), capture.join.base.BACKGROUND_FILTER_BYTE_COUNT
            )
            self.assertEqual(hashlib.sha256(object_raw).hexdigest(), expected[1])
            self.assertEqual(object_raw[:8], bytes(8))
            self.assertEqual(object_raw[496:504], flags_raw)

    def test_clear_appearance_parameters_collapse_at_filter_boundary(self) -> None:
        cases = {case["name"]: case for case in self.result["cases"]}
        clear_light = cases["clear_light"]
        clear_dark = cases["clear_dark"]
        self.assertNotEqual(
            clear_light["normalizedParametersSHA256"],
            clear_dark["normalizedParametersSHA256"],
        )
        self.assertEqual(
            clear_light["backgroundFilterSHA256"],
            clear_dark["backgroundFilterSHA256"],
        )
        self.assertEqual(clear_light["marginRawLittleEndianHex"], "0" * 16)
        self.assertEqual(clear_dark["marginRawLittleEndianHex"], "0" * 16)

    def test_regular_appearance_changes_filter_but_not_margin(self) -> None:
        cases = {case["name"]: case for case in self.result["cases"]}
        regular_light = cases["regular_light"]
        regular_dark = cases["regular_dark"]
        self.assertNotEqual(
            regular_light["backgroundFilterSHA256"],
            regular_dark["backgroundFilterSHA256"],
        )
        self.assertEqual(
            regular_light["marginRawLittleEndianHex"],
            "3433333333332340",
        )
        self.assertEqual(
            regular_dark["marginRawLittleEndianHex"],
            "3433333333332340",
        )

    def test_constructor_output_matches_every_present_parameters_group(self) -> None:
        parameters = self.predecessor["uniqueNormalizedParameters"]
        objects = self.result["uniqueBackgroundFilters"]
        for case in self.result["cases"]:
            source = bytes.fromhex(
                parameters[case["normalizedParametersSHA256"]]["normalizedHex"]
            )
            output = bytes.fromhex(objects[case["backgroundFilterSHA256"]]["hex"])
            if source[168] != 1:
                self.assertEqual(output[8:152], source[24:168])
            if source[248] != 1:
                self.assertEqual(output[152:224], source[176:248])
            if source[308] != 1:
                self.assertEqual(output[224:276], source[256:308])
            if source[385] != 1:
                self.assertEqual(output[276:349], source[312:385])
            if int.from_bytes(source[496:498], "little") != 0x200:
                self.assertEqual(output[352:458], source[392:498])
            if source[816] != 1:
                self.assertEqual(output[464:476], source[784:796])
                self.assertEqual(output[480:496], source[800:816])

    def test_claim_boundary_keeps_live_crop_retina_and_parity_open(self) -> None:
        invariants = self.result["measuredInvariants"]
        self.assertEqual(invariants["profileCaseCount"], 4)
        self.assertEqual(invariants["uniqueBackgroundFilterCount"], 3)
        self.assertTrue(invariants["regularAppearanceObjectsDistinct"])
        self.assertTrue(invariants["clearAppearanceObjectsBitwiseEqual"])
        self.assertEqual(invariants["regularMarginRawWord"], "3433333333332340")
        self.assertEqual(invariants["clearMarginRawWord"], "0000000000000000")
        self.assertTrue(invariants["freshProcessBitwiseStabilityEstablished"])
        self.assertFalse(invariants["capturedObjectOrMarginUsedForSelection"])
        claims = self.result["claims"]
        self.assertTrue(
            claims["controlledRegularClearLightDarkBackgroundFilterTableEstablished"]
        )
        self.assertTrue(claims["controlledMaterialSpecificMarginBoundaryEstablished"])
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
