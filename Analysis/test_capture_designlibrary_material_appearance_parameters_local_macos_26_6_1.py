#!/usr/bin/env python3
"""Tests for exact regular/clear by light/dark Parameters evidence."""

from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

import capture_designlibrary_material_appearance_parameters_local_macos_26_6_1 as capture
import capture_designlibrary_parameters_mixer_basis_local_macos_26_6_1 as basis


ANALYSIS = Path(__file__).resolve().parent
CAPTURE_PATH = Path(capture.__file__).resolve()
PROBE_PATH = ANALYSIS / capture.PROBE_SOURCE_NAME
ADAPTER_PATH = ANALYSIS / capture.LLDB_ADAPTER_NAME
CONFIGURATION_PREDECESSOR_PATH = ANALYSIS / capture.CONFIGURATION_FLAG_SEED_RESULT_NAME
ENVIRONMENT_PREDECESSOR_PATH = ANALYSIS / capture.ENVIRONMENT_FLAGS_RESULT_NAME
ENVIRONMENT_PARAMETERS_PATH = ANALYSIS / (
    "designlibrary_environment_parameters_local_macos_26_6_1_result.json"
)
PUBLIC_PARAMETERS_PATH = ANALYSIS / (
    "designlibrary_public_parameters_local_macos_26_6_1_result.json"
)
RESULT_PATH = ANALYSIS / (
    "designlibrary_material_appearance_parameters_local_macos_26_6_1_result.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DesignLibraryMaterialAppearanceParametersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.capture_source = CAPTURE_PATH.read_text(encoding="utf-8")
        cls.adapter_source = ADAPTER_PATH.read_text(encoding="utf-8")
        cls.probe_source = PROBE_PATH.read_text(encoding="utf-8")
        cls.environment_parameters = json.loads(
            ENVIRONMENT_PARAMETERS_PATH.read_text(encoding="utf-8")
        )
        cls.public_parameters = json.loads(
            PUBLIC_PARAMETERS_PATH.read_text(encoding="utf-8")
        )
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_sources_predecessors_and_result_are_frozen(self) -> None:
        ast.parse(self.capture_source, feature_version=(3, 9))
        ast.parse(self.adapter_source, feature_version=(3, 9))
        hashes = {
            "capture": sha256(CAPTURE_PATH),
            "adapter": sha256(ADAPTER_PATH),
            "probe": sha256(PROBE_PATH),
            "configurationPredecessor": sha256(CONFIGURATION_PREDECESSOR_PATH),
            "environmentPredecessor": sha256(ENVIRONMENT_PREDECESSOR_PATH),
            "result": sha256(RESULT_PATH),
        }
        self.assertEqual(
            hashes,
            {
                "capture": (
                    "8afc33846b98904cf1af3d1ff29cd8bdb6037b6018af3532eaa9e09bf02b767b"
                ),
                "adapter": (
                    "1320289cf969993fdd39c59f561d5d776c2adb93a8434257f18dc460c6134a97"
                ),
                "probe": (
                    "0343b7cc322922ec08fde41884efae429f4c7f56cce3b821d45235531de07470"
                ),
                "configurationPredecessor": (
                    capture.EXPECTED_CONFIGURATION_FLAG_SEED_RESULT_SHA256
                ),
                "environmentPredecessor": (
                    capture.EXPECTED_ENVIRONMENT_FLAGS_RESULT_SHA256
                ),
                "result": (
                    "fd0b181ef72b27a8738c67601b05a1813081cf125f3b82d277829db05567eb3b"
                ),
            },
        )
        tool = self.result["tool"]
        self.assertEqual(tool["captureSourceSHA256"], hashes["capture"])
        self.assertEqual(tool["lldbAdapterSHA256"], hashes["adapter"])
        self.assertEqual(tool["probeSourceSHA256"], hashes["probe"])
        self.assertFalse(tool["probeExecutableContainsNixStorePath"])
        self.assertNotIn("/nix/store", self.probe_source)

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
        gate = self.result["exactCodeGate"]
        self.assertEqual(
            gate["environmentFlagsProducerSHA256"],
            capture.environment.EXPECTED_ENVIRONMENT_FLAGS_PRODUCER_SHA256,
        )
        self.assertEqual(
            gate["parametersBuilderSHA256"],
            capture.public.EXPECTED_PARAMETERS_BUILDER_SHA256,
        )
        self.assertEqual(
            gate["parametersCallerSHA256"],
            capture.public.EXPECTED_PARAMETERS_CALLER_SHA256,
        )
        self.assertEqual(self.result["tool"]["freshProcessCount"], 3)

    def test_all_four_profile_parameters_are_exact_and_stable(self) -> None:
        cases = self.result["cases"]
        self.assertEqual(
            [case["name"] for case in cases],
            [case[0] for case in capture.PROFILE_CASES],
        )
        self.assertEqual([case["index"] for case in cases], list(range(4)))
        self.assertEqual(
            [case["producedFlagsBits"] for case in cases],
            [case[3] for case in capture.PROFILE_CASES],
        )
        unique = self.result["uniqueNormalizedParameters"]
        self.assertEqual(len(unique), 4)
        for case in cases:
            record = unique[case["normalizedParametersSHA256"]]
            payload = bytes.fromhex(record["normalizedHex"])
            self.assertEqual(len(payload), basis.PARAMETERS_BYTE_COUNT)
            self.assertEqual(
                hashlib.sha256(payload).hexdigest(),
                case["normalizedParametersSHA256"],
            )
            self.assertEqual(len(case["rawParametersSHA256ByFreshProcess"]), 3)
            expected_raw_identity_count = 1 if case["material"] == "regular" else 3
            self.assertEqual(
                len(set(case["rawParametersSHA256ByFreshProcess"])),
                expected_raw_identity_count,
            )
            for start, end in basis.SEMANTIC_PADDING_RANGES:
                self.assertEqual(payload[start:end], bytes(end - start))

    def test_regular_profiles_replicate_independent_environment_table(self) -> None:
        by_name = {case["name"]: case for case in self.result["cases"]}
        environment_by_name = {
            case["name"]: case for case in self.environment_parameters["cases"]
        }
        self.assertEqual(
            by_name["regular_light"]["normalizedParametersSHA256"],
            environment_by_name["baseline"]["normalizedParametersSHA256"],
        )
        self.assertEqual(
            by_name["regular_dark"]["normalizedParametersSHA256"],
            environment_by_name["color_scheme_dark"]["normalizedParametersSHA256"],
        )

    def test_real_flags_clear_profiles_differ_from_zero_flags_initial_state(
        self,
    ) -> None:
        zero_flags_clear = next(
            case
            for case in self.public_parameters["cases"]
            if case["qualifiedName"] == "static:clear"
        )
        by_name = {case["name"]: case for case in self.result["cases"]}
        for name in ("clear_light", "clear_dark"):
            self.assertNotEqual(
                by_name[name]["normalizedParametersSHA256"],
                zero_flags_clear["normalizedParametersSHA256"],
            )

    def test_clear_appearance_difference_is_confined_to_highlights(self) -> None:
        by_name = {case["name"]: case for case in self.result["cases"]}
        unique = self.result["uniqueNormalizedParameters"]
        light = bytes.fromhex(
            unique[by_name["clear_light"]["normalizedParametersSHA256"]][
                "normalizedHex"
            ]
        )
        dark = bytes.fromhex(
            unique[by_name["clear_dark"]["normalizedParametersSHA256"]]["normalizedHex"]
        )
        differences = {
            index for index, pair in enumerate(zip(light, dark)) if pair[0] != pair[1]
        }
        self.assertEqual(len(differences), 50)
        self.assertTrue(differences)
        self.assertTrue(all(520 <= offset < 777 for offset in differences))

    def test_claim_boundary_keeps_live_crop_retina_and_parity_open(self) -> None:
        invariants = self.result["measuredInvariants"]
        self.assertEqual(invariants["profileCaseCount"], 4)
        self.assertEqual(invariants["uniqueNormalizedParametersCount"], 4)
        self.assertTrue(invariants["freshProcessSemanticStabilityEstablished"])
        self.assertTrue(invariants["prospectiveFlagsMatchedBitwise"])
        self.assertFalse(invariants["capturedParametersUsedForSelection"])
        claims = self.result["claims"]
        self.assertTrue(
            claims["controlledRegularClearLightDarkParametersTableEstablished"]
        )
        self.assertTrue(
            claims["environmentFlagsProducerToProfileParametersJoinEstablished"]
        )
        for name in (
            "liveSwiftUIEnvironmentUpdaterEstablished",
            "liveTransitionProgressProductionLawEstablished",
            "generalIntegerCropAllocationPolicyEstablished",
            "retinaCompositorColorLawEstablished",
            "independentWalleZeroByteFrameParityEstablished",
            "liquidGlassParityEstablished",
            "productionShaderChangeAuthorized",
        ):
            self.assertFalse(claims[name])


if __name__ == "__main__":
    unittest.main()
