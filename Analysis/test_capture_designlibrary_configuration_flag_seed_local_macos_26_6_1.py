#!/usr/bin/env python3
"""Tests for authenticated Configuration flag-seed evidence."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

ANALYSIS = Path(__file__).resolve().parent
CAPTURE_PATH = ANALYSIS / (
    "capture_designlibrary_configuration_flag_seed_local_macos_26_6_1.py"
)


def load_capture():
    specification = importlib.util.spec_from_file_location(
        "designlibrary_configuration_flag_seed_capture_test",
        CAPTURE_PATH,
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("Configuration flag-seed capture module is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


capture = load_capture()
PROBE_PATH = ANALYSIS / capture.SOURCE_NAME
BRIDGE_PATH = ANALYSIS / capture.BRIDGE_NAME
PUBLIC_BRIDGE_PATH = ANALYSIS / capture.PUBLIC_BRIDGE_NAME
RESULT_PATH = ANALYSIS / (
    "designlibrary_configuration_flag_seed_local_macos_26_6_1_result.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DesignLibraryConfigurationFlagSeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.capture_source = CAPTURE_PATH.read_text(encoding="utf-8")
        cls.probe_source = PROBE_PATH.read_text(encoding="utf-8")
        cls.bridge_source = BRIDGE_PATH.read_text(encoding="utf-8")
        cls.public_bridge_source = PUBLIC_BRIDGE_PATH.read_text(encoding="utf-8")
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_sources_and_canonical_result_are_frozen(self) -> None:
        ast.parse(self.capture_source, feature_version=(3, 9))
        hashes = {
            "capture": sha256(CAPTURE_PATH),
            "probe": sha256(PROBE_PATH),
            "bridge": sha256(BRIDGE_PATH),
            "publicBridge": sha256(PUBLIC_BRIDGE_PATH),
            "result": sha256(RESULT_PATH),
        }
        self.assertEqual(
            hashes,
            {
                "capture": "ceb3a0ed930e619638368fec14ed4187ca7184586e2ccd0918a786c7f0ebde61",
                "probe": "d710af104b063fdd4964c7d4ea9c86d2b4a377479c230c83bbbc0d1bd470bdae",
                "bridge": "8de57e8bfb88bb3590de5b27c3dd7f631245d2a697f90936540c8ddd732a57e2",
                "publicBridge": "9f58cbef6e4875f9fb377f4018913d6336b6c906c1a37a1117d137ac373fef2d",
                "result": "1cf97c5ccf4b51c85c882cce1f8b0b91335ab80508908c4fcc763d9b2768390a",
            },
        )
        tool = self.result["tool"]
        self.assertEqual(tool["captureSourceSHA256"], hashes["capture"])
        self.assertEqual(tool["probeSourceSHA256"], hashes["probe"])
        self.assertEqual(tool["assemblyBridgeSHA256"], hashes["bridge"])
        self.assertEqual(
            tool["publicAssemblyBridgeSHA256"], hashes["publicBridge"]
        )
        self.assertEqual(tool["freshProcessRunsPerMode"], 3)

    def test_capture_uses_direct_apple_toolchain_without_nix_paths(self) -> None:
        self.assertIn('XCRUN = Path("/usr/bin/xcrun")', self.capture_source)
        self.assertIn('b"/nix/store" in executable.read_bytes()', self.capture_source)
        self.assertNotIn("/nix/store", self.probe_source)
        self.assertNotIn("/nix/store", self.bridge_source)
        self.assertNotIn("/nix/store", self.public_bridge_source)
        self.assertNotIn("import DesignLibrary", self.capture_source)

    def test_host_framework_and_runtime_mix_layout_are_exact(self) -> None:
        self.assertEqual(
            self.result["designLibraryConfigurationFlagSeedCaptureSchemaVersion"],
            1,
        )
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
            "1E980802-69F5-3E69-89EF-50088297FCF5",
        )
        self.assertEqual(
            self.result["runtimeMixLayout"],
            {
                "size": 296,
                "stride": 296,
                "valueWitnessFlags": "0x00030007",
                "extraInhabitantCount": 0x7FFFFFFF,
                "fieldOffsets": [0, 144, 288],
                "projector": "swift_projectBox",
            },
        )

    def test_private_code_ranges_and_metadata_are_authenticated(self) -> None:
        static = self.result["staticEvidence"]
        self.assertEqual(
            static["flagSeedHelper"],
            {
                "start": "0x240974e60",
                "endExclusive": "0x240975028",
                "byteCount": 456,
                "instructionCount": 114,
                "criticalInstructionCount": 40,
                "sha256": "ac4057c8edc1ffa817b6a1dc9693d2b9ef95650ab9b70223a98e00642b5c8076",
            },
        )
        self.assertEqual(
            static["mixMetadataAccessor"],
            {
                "start": "0x240912fe0",
                "endExclusive": "0x240913000",
                "sha256": "b9fda459e045c61886dd72ab311a8edf74c62e1cb72913f8f79bef50e88ed86b",
            },
        )
        self.assertEqual(
            static["projectorStub"],
            {
                "start": "0x2409a5cd0",
                "endExclusive": "0x2409a5ce0",
                "sha256": "0f34a958e6e6dd9580d38018a9dacd58477f007093fd695020c19a398c1ee166",
                "runtimeBinding": "swift_projectBox",
            },
        )
        self.assertEqual(
            static["mixDescriptor"],
            {
                "address": "0x2409d2188",
                "name": "Mix",
                "fieldNames": ["from", "to", "fraction"],
                "fieldCount": 3,
                "fieldOffsetVectorWords": 2,
            },
        )

    def test_direct_law_boundaries_are_exact(self) -> None:
        options = (
            capture.NOISE_OPTIONS
            | capture.DISPLAY_ANGLE
            | capture.ADAPTIVE
            | capture.EXTERNAL_LUMINANCE
        )
        for subvariant in (14, 19):
            self.assertEqual(capture.expected_direct(0, subvariant, options), options)
        for subvariant in range(15, 19):
            self.assertEqual(
                capture.expected_direct(0, subvariant, options),
                options & ~capture.DISPLAY_ANGLE,
            )

        for subvariant in (11, 13):
            self.assertEqual(
                capture.expected_direct(capture.REGULAR_BASE, subvariant, options),
                options,
            )
        self.assertEqual(
            capture.expected_direct(capture.REGULAR_BASE, 12, options),
            options & ~capture.ADAPTIVE,
        )

        clear_options = capture.NOISE_OPTIONS
        for subvariant in (1, 20):
            self.assertEqual(
                capture.expected_direct(
                    capture.CLEAR_BASE, subvariant, clear_options
                ),
                clear_options | capture.ADAPTIVE,
            )
        self.assertEqual(
            capture.expected_direct(capture.CLEAR_BASE, 8, clear_options),
            clear_options | capture.DISPLAY_ANGLE,
        )
        for subvariant in (0, 2, 7, 9, 19, 21):
            self.assertEqual(
                capture.expected_direct(
                    capture.CLEAR_BASE, subvariant, clear_options
                ),
                clear_options,
            )

        self.assertEqual(
            capture.expected_direct(1 << 62, 15, options),
            options,
        )
        self.assertEqual(
            capture.expected_direct(0xC000000000000080, 12, options),
            options,
        )
        with self.assertRaises(ValueError):
            capture.expected_direct(2 << 62, 0, options)

    def test_indirect_mix_law_and_non_recursive_behavior_are_exact(self) -> None:
        noise = capture.NOISE_OPTIONS
        endpoint_only_noise = 1 << 48
        self.assertEqual(
            capture.expected_mix(
                capture.DISPLAY_ANGLE | capture.EXTERNAL_LUMINANCE | endpoint_only_noise,
                capture.ADAPTIVE | capture.EXTERNAL_LUMINANCE | endpoint_only_noise,
                noise,
            ),
            noise
            | capture.DISPLAY_ANGLE
            | capture.ADAPTIVE
            | capture.EXTERNAL_LUMINANCE,
        )
        self.assertEqual(
            capture.expected_mix(
                capture.EXTERNAL_LUMINANCE,
                0,
                noise,
            ),
            noise,
        )
        outer = noise | capture.EXTERNAL_LUMINANCE | endpoint_only_noise
        self.assertEqual(capture.expected_mix(0, 0, outer), outer)

        nested = self.result["publicValidation"]["nestedMixCases"]
        self.assertEqual(nested[0]["resultBits"], "0x0000000000004000")
        self.assertEqual(nested[0]["optionsBits"], "0x0000000000000000")
        self.assertEqual(
            [record["resultBits"] for record in nested[1:]],
            ["0x0000000000000002", "0x0000000000000002"],
        )
        self.assertEqual(
            [record["fromOptionsBits"] for record in nested[1:]],
            ["0x0000000000000000", "0x0000000000000002"],
        )
        self.assertEqual(
            [record["toOptionsBits"] for record in nested[1:]],
            ["0x0000000000000002", "0x0000000000000000"],
        )

    def test_public_validation_matrix_and_special_cases_are_exact(self) -> None:
        public = self.result["publicValidation"]
        self.assertEqual(public["staticConfigurationCount"], 27)
        self.assertEqual(public["orderedStaticMixCount"], 729)
        self.assertEqual(public["totalPublicConfigurationCount"], 36)
        self.assertEqual(public["totalPublicMixCount"], 741)
        self.assertEqual(
            public["normalizedStreamSHA256"],
            "482d34307dc6fa96e9c552bad18b7d18d2984102655da23ff3c2efacd46339f8",
        )
        self.assertEqual(public["subvariants"], capture.EXPECTED_SUBVARIANTS)
        self.assertEqual(
            [
                (record["name"], record["subvariantStorage"], record["resultBits"])
                for record in public["subvariantSpecialCases"]
            ],
            [
                ("regular_entryField", 12, "0x0000000000000000"),
                ("clear_watchPasscode", 20, "0x0000000000004000"),
                ("text_watchFacePhotos", 15, "0x0000000000000000"),
            ],
        )
        self.assertEqual(
            [record["resultBits"] for record in public["optionMixCases"]],
            [
                "0x000000000000c000",
                "0x0000000000004000",
                "0x0000000000000002",
            ],
        )

    def test_exhaustive_domains_and_streams_are_exact(self) -> None:
        exhaustive = self.result["exhaustiveValidation"]
        self.assertEqual(exhaustive["directBaseRepresentationCount"], 5)
        self.assertEqual(exhaustive["subvariantStorageCountPerDirectRepresentation"], 256)
        self.assertEqual(exhaustive["relevantOptionCombinationCount"], 8)
        self.assertEqual(exhaustive["directCaseCount"], 10_240)
        self.assertEqual(exhaustive["indirectCaseCount"], 512)
        self.assertEqual(exhaustive["totalCaseCount"], 10_752)
        self.assertEqual(
            exhaustive["directStreamSHA256"],
            "98267356ea230ed1a0a469cda7f050c8746526fa6754ebfc6aae1932671735ba",
        )
        self.assertEqual(
            exhaustive["indirectStreamSHA256"],
            "8a6f1b087d9d4722e9b37bc34a25676c8c4e0cf1cacdb852f3325a9a2b266025",
        )
        self.assertEqual(
            exhaustive["combinedStreamSHA256"],
            "454fec1c7bc2b9ae943736615c492e2340670f06e77c9307bfca7ec63c96f81c",
        )
        self.assertIn("not a claim", exhaustive["classification"])

    def test_claims_close_only_the_measured_boundary(self) -> None:
        invariants = self.result["measuredInvariants"]
        self.assertTrue(all(invariants.values()))
        claims = self.result["claims"]
        self.assertTrue(claims["configurationToFlagSeedLawEstablished"])
        self.assertTrue(claims["arbitraryNestedConfigurationMixFlagSeedLawEstablished"])
        self.assertFalse(claims["liveSwiftUIEnvironmentUpdateLawEstablished"])
        self.assertFalse(claims["transitionProgressProductionLawEstablished"])
        self.assertFalse(claims["integerCropAllocationPolicyEstablished"])
        self.assertFalse(claims["retinaCompositorColorLawEstablished"])
        self.assertFalse(claims["independentWalleZeroByteFrameParityEstablished"])
        self.assertFalse(claims["liquidGlassParityEstablished"])
        self.assertFalse(claims["productionShaderChangeAuthorized"])


if __name__ == "__main__":
    unittest.main()
