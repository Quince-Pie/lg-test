#!/usr/bin/env python3
"""Tests for the prospectively fixed Material.Context Parameters matrix."""

from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

import capture_designlibrary_material_context_parameters_local_macos_26_6_1 as capture
import capture_designlibrary_parameters_mixer_basis_local_macos_26_6_1 as basis


ANALYSIS = Path(__file__).resolve().parent
CAPTURE_PATH = Path(capture.__file__).resolve()
ADAPTER_PATH = ANALYSIS / capture.LLDB_ADAPTER_NAME
PROBE_PATH = ANALYSIS / capture.PROBE_SOURCE_NAME
PREREGISTRATION_PATH = ANALYSIS / capture.PREREGISTRATION_NAME
RESULT_PATH = ANALYSIS / (
    "designlibrary_material_context_parameters_local_macos_26_6_1_result.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DesignLibraryMaterialContextParametersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.capture_source = CAPTURE_PATH.read_text(encoding="utf-8")
        cls.adapter_source = ADAPTER_PATH.read_text(encoding="utf-8")
        cls.probe_source = PROBE_PATH.read_text(encoding="utf-8")
        cls.preregistration = json.loads(
            PREREGISTRATION_PATH.read_text(encoding="utf-8")
        )
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_sources_preregistration_and_result_are_frozen(self) -> None:
        ast.parse(self.capture_source, feature_version=(3, 9))
        ast.parse(self.adapter_source, feature_version=(3, 9))
        hashes = {
            "capture": sha256(CAPTURE_PATH),
            "adapter": sha256(ADAPTER_PATH),
            "probe": sha256(PROBE_PATH),
            "preregistration": sha256(PREREGISTRATION_PATH),
            "result": sha256(RESULT_PATH),
        }
        self.assertEqual(
            hashes,
            {
                "capture": (
                    "4600432f909881a09da598081fda2bd9b6f31707769304608fc54399b9d80437"
                ),
                "adapter": (
                    "27875732956787a049444c99d76de75f23342d2a56e2a3cd582641c18bd9beda"
                ),
                "probe": (
                    "69f877a6641a795a45e173693398ada603e7b70e7806de7bb16393702bad07ac"
                ),
                "preregistration": (
                    "5885230533d56b9b20ec7545b40e8ec1204cb58f24eda70db60fab9c721872f2"
                ),
                "result": (
                    "e707178e4f5e6e14d75fa0a953daa834e538be3981e855a2ecc18325aca0167b"
                ),
            },
        )
        tool = self.result["tool"]
        self.assertEqual(tool["captureSourceSHA256"], hashes["capture"])
        self.assertEqual(tool["lldbAdapterSHA256"], hashes["adapter"])
        self.assertEqual(tool["probeSourceSHA256"], hashes["probe"])
        self.assertEqual(
            self.result["predecessors"]["preregistration"]["sha256"],
            hashes["preregistration"],
        )
        self.assertNotIn("/nix/store", self.probe_source)
        self.assertFalse(tool["probeExecutableContainsNixStorePath"])

    def test_exact_material_context_storage_is_used(self) -> None:
        self.assertEqual(
            self.result["materialContextLayout"],
            {
                "byteCount": 73,
                "stride": 80,
                "nilOptionalTag": 1,
                "presentOptionalTag": 0,
                "shapeDimensionsLowerBoundOffset": 24,
                "shapeDimensionsUpperBoundOffset": 32,
                "shapeDimensionsOptionalTagOffset": 40,
            },
        )
        self.assertEqual(self.result["tool"]["freshProcessCount"], 3)
        self.assertEqual(self.result["tool"]["python"], "3.9.6")

    def test_all_21_preregistered_cases_are_stable(self) -> None:
        cases = self.result["cases"]
        frozen = self.preregistration["cases"]
        self.assertEqual(len(cases), 21)
        self.assertEqual([case["index"] for case in cases], list(range(21)))
        self.assertEqual([case["name"] for case in cases], [case[0] for case in frozen])
        self.assertEqual(
            [case["producedFlagsBits"] for case in cases],
            [case[6] for case in frozen],
        )
        for case in cases:
            raw_digests = case["rawParametersSHA256ByFreshProcess"]
            self.assertEqual(len(raw_digests), 3)
            self.assertIn(
                case["normalizedParametersSHA256"],
                self.result["uniqueNormalizedParameters"],
            )
            dimensions = case["shapeDimensions"]
            self.assertEqual(dimensions["present"], case["name"] != "regular_light_nil")

    def test_only_the_closed_range_lower_bound_is_consumed(self) -> None:
        by_name = {case["name"]: case for case in self.result["cases"]}
        lower = by_name["regular_light_127"]["normalizedParametersSHA256"]
        self.assertEqual(
            by_name["regular_light_range_127_143"]["normalizedParametersSHA256"],
            lower,
        )
        self.assertEqual(
            by_name["regular_light_range_127_640"]["normalizedParametersSHA256"],
            lower,
        )

    def test_normalized_payloads_are_exact(self) -> None:
        unique = self.result["uniqueNormalizedParameters"]
        self.assertEqual(len(unique), 19)
        for digest, record in unique.items():
            payload = bytes.fromhex(record["normalizedHex"])
            self.assertEqual(len(payload), basis.PARAMETERS_BYTE_COUNT)
            self.assertEqual(hashlib.sha256(payload).hexdigest(), digest)
            self.assertEqual(basis.normalize_parameters(payload), payload)

    def test_claim_boundary_keeps_live_crop_retina_and_parity_open(self) -> None:
        invariants = self.result["measuredInvariants"]
        self.assertEqual(invariants["caseCount"], 21)
        self.assertEqual(invariants["parametersBuildsPerCase"], 1)
        self.assertTrue(invariants["freshProcessSemanticStabilityEstablished"])
        self.assertTrue(invariants["nilContextBaselineReproducedBitwise"])
        self.assertFalse(invariants["capturedParametersUsedForSelection"])
        claims = self.result["claims"]
        self.assertTrue(
            claims["controlledMaterialContextShapeDimensionParametersTableEstablished"]
        )
        for name in (
            "liveContextValueProductionEstablished",
            "liveTransitionProgressProductionLawEstablished",
            "generalContextToParametersValueLawEstablished",
            "generalIntegerCropAllocationPolicyEstablished",
            "retinaCompositorColorLawEstablished",
            "independentWalleZeroByteFrameParityEstablished",
            "liquidGlassParityEstablished",
            "productionShaderChangeAuthorized",
        ):
            self.assertFalse(claims[name])


if __name__ == "__main__":
    unittest.main()
