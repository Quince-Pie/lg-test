#!/usr/bin/env python3
"""Tests for exact headless public Configuration-to-Parameters evidence."""

from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

import capture_designlibrary_parameters_mixer_basis_local_macos_26_6_1 as basis
import capture_designlibrary_public_parameters_local_macos_26_6_1 as capture


ANALYSIS = Path(__file__).resolve().parent
CAPTURE_PATH = Path(capture.__file__).resolve()
LLDB_PATH = ANALYSIS / capture.LLDB_ADAPTER_NAME
PROBE_PATH = ANALYSIS / capture.PROBE_SOURCE_NAME
BRIDGE_PATH = ANALYSIS / capture.BRIDGE_SOURCE_NAME
BASIS_PATH = Path(basis.__file__).resolve()
RESULT_PATH = ANALYSIS / (
    "designlibrary_public_parameters_local_macos_26_6_1_result.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DesignLibraryPublicParametersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.capture_source = CAPTURE_PATH.read_text(encoding="utf-8")
        cls.lldb_source = LLDB_PATH.read_text(encoding="utf-8")
        cls.probe_source = PROBE_PATH.read_text(encoding="utf-8")
        cls.bridge_source = BRIDGE_PATH.read_text(encoding="utf-8")
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_sources_and_canonical_result_are_frozen(self) -> None:
        ast.parse(self.capture_source, feature_version=(3, 9))
        ast.parse(self.lldb_source, feature_version=(3, 9))
        hashes = {
            "capture": sha256(CAPTURE_PATH),
            "lldb": sha256(LLDB_PATH),
            "probe": sha256(PROBE_PATH),
            "bridge": sha256(BRIDGE_PATH),
            "basis": sha256(BASIS_PATH),
            "result": sha256(RESULT_PATH),
        }
        self.assertEqual(
            hashes,
            {
                "capture": "ff54baa77b1d2d8d3b6dedf05a4ce5edf341a8b86966726701107a3dcd288610",
                "lldb": "c82fc09d0c3bcef58f40ff6fb13ac593c85bb01ceab65bf12380f4f344cadfb9",
                "probe": "59c54e502eceb9a2d789f3729c7f4ba2de8067e83086a4cd8d5c7343e10cee8f",
                "bridge": "8abad01a65462ff5f25bb77710733a7b38d1e5809e6065631e42d232c1d73b90",
                "basis": "829e758062d1905ed5635b09bf458337bebce3e41f506ec301d80c66112d2442",
                "result": "9cbf0a22a9c313b46147dfb2dacb6d64be4e5a928e0199470e08439ec070e02a",
            },
        )
        tool = self.result["tool"]
        self.assertEqual(tool["captureSourceSHA256"], hashes["capture"])
        self.assertEqual(tool["lldbAdapterSHA256"], hashes["lldb"])
        self.assertEqual(tool["probeSourceSHA256"], hashes["probe"])
        self.assertEqual(tool["assemblyBridgeSHA256"], hashes["bridge"])
        self.assertEqual(tool["parametersBasisSourceSHA256"], hashes["basis"])
        self.assertNotIn("/nix/store", self.probe_source)
        self.assertNotIn("/nix/store", self.bridge_source)
        self.assertNotIn("import DesignLibrary", self.capture_source)
        self.assertFalse(tool["probeExecutableContainsNixStorePath"])

    def test_host_frameworks_and_exact_code_gate_are_frozen(self) -> None:
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
            self.result["frameworks"]["DesignLibrary"]["uuid"],
            capture.EXPECTED_DESIGNLIBRARY_UUID,
        )
        self.assertEqual(
            self.result["frameworks"]["SwiftUICore"]["uuid"],
            capture.EXPECTED_SWIFTUICORE_UUID,
        )
        self.assertEqual(
            self.result["exactCodeGate"],
            {
                "parametersBuilderModuleOffset": 0x120B4C,
                "parametersBuilderByteCount": 0x1334,
                "parametersBuilderCodeSHA256": (
                    capture.EXPECTED_PARAMETERS_BUILDER_SHA256
                ),
                "parametersCallerModuleOffset": 0x11F1BC,
                "parametersCallerByteCount": 0xD7C,
                "parametersCallerCodeSHA256": (
                    capture.EXPECTED_PARAMETERS_CALLER_SHA256
                ),
                "parametersCallerReturnOffset": 0xD38,
            },
        )

    def test_every_fixed_public_case_has_one_stable_semantic_payload(self) -> None:
        cases = self.result["cases"]
        self.assertEqual(
            [record["qualifiedName"] for record in cases],
            list(capture.EXPECTED_CASE_NAMES),
        )
        self.assertEqual([record["index"] for record in cases], list(range(42)))
        self.assertEqual(
            [record["category"] for record in cases],
            ["static"] * 27 + ["mix"] * 7 + ["modifier"] * 8,
        )
        self.assertEqual(self.result["tool"]["freshProcessCount"], 3)
        for record in cases:
            self.assertEqual(len(record["rawParametersSHA256ByFreshProcess"]), 3)
            self.assertTrue(
                all(
                    len(digest) == 64
                    for digest in record["rawParametersSHA256ByFreshProcess"]
                )
            )
            self.assertIn(
                record["normalizedParametersSHA256"],
                self.result["uniqueNormalizedParameters"],
            )
        unstable = [
            record["qualifiedName"]
            for record in cases
            if not record["rawParametersStableAcrossFreshProcesses"]
        ]
        self.assertEqual(unstable, ["static:monogram"])

    def test_normalized_parameters_are_exact_and_padding_is_zero(self) -> None:
        layout = self.result["parametersLayout"]
        self.assertEqual(layout["byteCount"], basis.PARAMETERS_BYTE_COUNT)
        self.assertEqual(layout["semanticByteCount"], 873)
        self.assertEqual(
            layout["normalizedPaddingRanges"],
            [list(pair) for pair in basis.SEMANTIC_PADDING_RANGES],
        )
        unique = self.result["uniqueNormalizedParameters"]
        self.assertEqual(len(unique), 27)
        for digest, record in unique.items():
            payload = bytes.fromhex(record["normalizedHex"])
            self.assertEqual(len(payload), basis.PARAMETERS_BYTE_COUNT)
            self.assertEqual(hashlib.sha256(payload).hexdigest(), digest)
            for start, end in basis.SEMANTIC_PADDING_RANGES:
                self.assertEqual(payload[start:end], bytes(end - start))
        referenced = {
            record["normalizedParametersSHA256"]
            for record in self.result["cases"]
        }
        self.assertEqual(referenced, set(unique))

    def test_equivalence_clusters_and_mix_distinctions_are_measured(self) -> None:
        by_name = {
            record["qualifiedName"]: record["normalizedParametersSHA256"]
            for record in self.result["cases"]
        }
        regular_cluster = {
            name
            for name, digest in by_name.items()
            if digest == by_name["static:regular"]
        }
        self.assertEqual(
            regular_cluster,
            {
                "static:regular",
                "static:bubbles",
                "static:sidebar",
                *(
                    "modifier:" + name
                    for name in capture.MODIFIER_NAMES
                ),
            },
        )
        self.assertEqual(
            by_name["static:focusBorder"],
            by_name["static:focusPlatter"],
        )
        self.assertEqual(
            {
                by_name["static:clear"],
                by_name["static:avplayer"],
                by_name["static:facetime"],
                by_name["static:controlCenter"],
            },
            {by_name["static:clear"]},
        )
        mix_digests = {
            by_name["mix:" + name] for name in capture.MIX_NAMES
        }
        self.assertEqual(len(mix_digests), len(capture.MIX_NAMES))
        self.assertTrue(mix_digests.isdisjoint({by_name["static:regular"]}))
        self.assertTrue(mix_digests.isdisjoint({by_name["static:clear"]}))

    def test_claim_boundary_does_not_overstate_parity(self) -> None:
        invariants = self.result["measuredInvariants"]
        self.assertEqual(invariants["totalCaseCount"], 42)
        self.assertEqual(invariants["parametersBuildsPerCase"], 1)
        self.assertEqual(invariants["uniqueNormalizedParametersCount"], 27)
        self.assertTrue(invariants["freshProcessSemanticStabilityEstablished"])
        self.assertTrue(invariants["everyFixedIntervalRetained"])
        self.assertFalse(invariants["capturedParametersUsedForSelection"])
        self.assertFalse(invariants["capturedBuilderArgumentsUsedForSelection"])
        claims = self.result["claims"]
        self.assertTrue(
            claims["defaultContextPublicConfigurationToParametersTableEstablished"]
        )
        self.assertTrue(claims["defaultContextPublicMixToParametersTableEstablished"])
        self.assertTrue(
            claims["defaultContextPublicModifierToParametersTableEstablished"]
        )
        for name in (
            "liveSwiftUIEnvironmentSelectionLawEstablished",
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
