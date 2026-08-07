#!/usr/bin/env python3
"""Tests for both prospectively frozen Material.Context live transfers."""

from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
ZERO_PREFIX = "designlibrary_material_context_live_timeline_transfer_local_macos_26_6_1"
FLAGS_PREFIX = (
    "designlibrary_material_context_flags_live_timeline_transfer_local_macos_26_6_1"
)
PATHS = {
    "zeroCapture": ANALYSIS / ("capture_" + ZERO_PREFIX + ".py"),
    "zeroAdapter": ANALYSIS / ("capture_" + ZERO_PREFIX + "_lldb.py"),
    "zeroProbe": ANALYSIS / ("probe_" + ZERO_PREFIX + ".c"),
    "zeroPreregistration": ANALYSIS / (ZERO_PREFIX + "_preregistration.json"),
    "zeroResult": ANALYSIS / (ZERO_PREFIX + "_result.json"),
    "flagsCapture": ANALYSIS / ("capture_" + FLAGS_PREFIX + ".py"),
    "flagsAdapter": ANALYSIS / ("capture_" + FLAGS_PREFIX + "_lldb.py"),
    "flagsProbe": ANALYSIS / ("probe_" + FLAGS_PREFIX + ".c"),
    "flagsPreregistration": ANALYSIS / (FLAGS_PREFIX + "_preregistration.json"),
    "flagsResult": ANALYSIS / (FLAGS_PREFIX + "_result.json"),
}
EXPECTED_HASHES = {
    "zeroCapture": "62667bb3c41eced5d3ef4768e409b3ed121dad1a5c758d18cf85be7bf5149d9c",
    "zeroAdapter": "53980221e3cb6873f0995683e3b76f51a8f0b199c56d3cafc7653b5ca4156cb9",
    "zeroProbe": "a97f15fd7bf56f419a4352598082457b1a23ef71010f3132f6b7f6f433e26deb",
    "zeroPreregistration": "73b818343f93a133dc5fff1d5f2fa8a9aaad7642f63e95c9f3e1365257679331",
    "zeroResult": "6237b29fa78c1626df9ed95aed6d3d8ad6c026b290c66def1e3af8380b54f570",
    "flagsCapture": "ded67bfeaa863a550ccecdfb993bc60b9ddbaca7e5a033e01b225c2506023d39",
    "flagsAdapter": "64e5d15bef6d37363f33ff521a7e36daddbc2cf89d8904d600e630f38f1f079f",
    "flagsProbe": "d89154a8833fc985d0c1b86421830d014d9889fa5e5120e10291fa628f52c12b",
    "flagsPreregistration": "e9bb1fd4e05d1744961366721f6118cd206a141cce61ce08550bf9341d60ad8b",
    "flagsResult": "7df7230548463675d00a7bc78dac0003cd08a9beb19e9b53268b3a6073c15ac7",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DesignLibraryMaterialContextLiveTimelineTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sources = {
            name: path.read_text(encoding="utf-8")
            for name, path in PATHS.items()
            if name.endswith(("Capture", "Adapter", "Probe"))
        }
        cls.zero_preregistration = json.loads(
            PATHS["zeroPreregistration"].read_text(encoding="utf-8")
        )
        cls.flags_preregistration = json.loads(
            PATHS["flagsPreregistration"].read_text(encoding="utf-8")
        )
        cls.zero = json.loads(PATHS["zeroResult"].read_text(encoding="utf-8"))
        cls.flags = json.loads(PATHS["flagsResult"].read_text(encoding="utf-8"))

    def test_all_sources_preregistrations_and_results_are_frozen(self) -> None:
        for name in ("zeroCapture", "zeroAdapter", "flagsCapture", "flagsAdapter"):
            ast.parse(self.sources[name], feature_version=(3, 9))
        hashes = {name: sha256(path) for name, path in PATHS.items()}
        self.assertEqual(hashes, EXPECTED_HASHES)
        for prefix, result in (("zero", self.zero), ("flags", self.flags)):
            tool = result["tool"]
            self.assertEqual(tool["captureSourceSHA256"], hashes[prefix + "Capture"])
            self.assertEqual(tool["lldbAdapterSHA256"], hashes[prefix + "Adapter"])
            self.assertEqual(tool["probeSourceSHA256"], hashes[prefix + "Probe"])
            self.assertEqual(
                result["predecessors"]["preregistration"]["sha256"],
                hashes[prefix + "Preregistration"],
            )
            self.assertNotIn("/nix/store", self.sources[prefix + "Probe"])
            self.assertFalse(tool["probeExecutableContainsNixStorePath"])
            self.assertEqual(tool["freshProcessCount"], 3)
            self.assertEqual(tool["python"], "3.9.6")

    def test_preregistered_inputs_match_all_native_cases(self) -> None:
        for preregistration, result, count, qualified_prefix in (
            (self.zero_preregistration, self.zero, 31, "material_context_live:"),
            (
                self.flags_preregistration,
                self.flags,
                32,
                "material_context_flags_live:",
            ),
        ):
            frozen = preregistration["cases"]
            cases = result["cases"]
            self.assertEqual(len(frozen), count)
            self.assertEqual(len(cases), count)
            self.assertEqual(
                [case["name"] for case in cases], [case[0] for case in frozen]
            )
            self.assertEqual(
                [case["qualifiedName"] for case in cases],
                [qualified_prefix + case[0] for case in frozen],
            )
            self.assertEqual(
                [case["fractionBits"] for case in cases],
                [case[1] for case in frozen],
            )
            self.assertEqual(
                [case["shapeDimensionBits"] for case in cases],
                [case[2] for case in frozen],
            )
            for case in cases:
                raw_digests = case["rawParametersSHA256ByFreshProcess"]
                self.assertEqual(len(raw_digests), 3)
                self.assertIn(
                    case["normalizedParametersSHA256"],
                    result["uniqueNormalizedParameters"],
                )

    def test_environment_profiles_are_distinct(self) -> None:
        self.assertEqual(
            {case["environmentFlagsBits"] for case in self.zero["cases"]},
            {"0x0000000000000000"},
        )
        self.assertEqual(
            {case["environmentFlagsBits"] for case in self.flags["cases"]},
            {"0x0000000000099183"},
        )
        self.assertEqual(
            self.zero["predecessors"]["publicTimeline"]["sha256"],
            "1dd73cfa4e696c43a0612c107e9a5edcb78c72b14ba80e67a53e4e99b06d931f",
        )
        self.assertEqual(
            self.flags["predecessors"]["publicTimeline"]["sha256"],
            "0a7db5d9416c4c69f19b608de73e9225e7edf8629e112de2be0d07cab1adc711",
        )

    def test_all_252_opened_live_words_match_bitwise(self) -> None:
        zero_invariants = self.zero["measuredInvariants"]
        flags_invariants = self.flags["measuredInvariants"]
        self.assertEqual(zero_invariants["totalProviderPredictionCount"], 124)
        self.assertEqual(zero_invariants["totalProviderPredictionMatchCount"], 124)
        self.assertEqual(flags_invariants["totalPublicPredictionCount"], 128)
        self.assertEqual(flags_invariants["totalPublicPredictionMatchCount"], 128)
        for case in self.zero["cases"]:
            self.assertTrue(case["allProviderPredictionsMatchBitwise"])
            self.assertTrue(
                all(item["matchedBitwise"] for item in case["providerPredictions"])
            )
        for case in self.flags["cases"]:
            self.assertTrue(case["allPublicPredictionsMatchBitwise"])
            self.assertTrue(
                all(item["matchedBitwise"] for item in case["publicPredictions"])
            )

    def test_claim_boundaries_remain_fail_closed(self) -> None:
        self.assertTrue(
            self.zero["claims"][
                "exactZeroFlagsContextToOpenedLiveProviderFieldsTransferEstablished"
            ]
        )
        self.assertTrue(
            self.flags["claims"][
                "exactFlagsProducedContextToOpenedLivePublicFieldsTransferEstablished"
            ]
        )
        for result in (self.zero, self.flags):
            for name in (
                "completeLiveParametersTransferEstablished",
                "generalContextToParametersValueLawEstablished",
                "generalIntegerCropAllocationPolicyEstablished",
                "retinaCompositorColorLawEstablished",
                "independentWalleZeroByteFrameParityEstablished",
                "liquidGlassParityEstablished",
                "productionShaderChangeAuthorized",
            ):
                self.assertFalse(result["claims"][name])


if __name__ == "__main__":
    unittest.main()
