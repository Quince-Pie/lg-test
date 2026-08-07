#!/usr/bin/env python3
"""Tests for the direct native DesignLibrary Parameters-mixer basis capture."""

from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

import capture_designlibrary_parameters_mixer_basis_local_macos_26_6_1 as capture


ANALYSIS = Path(__file__).resolve().parent
SOURCE_PATH = Path(capture.__file__).resolve()
C_SOURCE_PATH = ANALYSIS / capture.C_SOURCE_NAME
ASSEMBLY_SOURCE_PATH = ANALYSIS / capture.ASSEMBLY_SOURCE_NAME
RESULT_PATH = ANALYSIS / (
    "designlibrary_parameters_mixer_basis_local_macos_26_6_1_result.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DesignLibraryParametersMixerBasisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_sources_and_canonical_result_are_frozen(self) -> None:
        ast.parse(self.source, feature_version=(3, 9))
        source_hash = sha256(SOURCE_PATH)
        c_source_hash = sha256(C_SOURCE_PATH)
        assembly_source_hash = sha256(ASSEMBLY_SOURCE_PATH)
        self.assertEqual(
            source_hash,
            "829e758062d1905ed5635b09bf458337bebce3e41f506ec301d80c66112d2442",
        )
        self.assertEqual(c_source_hash, capture.C_SOURCE_SHA256)
        self.assertEqual(assembly_source_hash, capture.ASSEMBLY_SOURCE_SHA256)
        self.assertEqual(
            sha256(RESULT_PATH),
            "d07da93bc93981b3d5d2cdc123531e9695a3673834f9482a69d3a74507cc0c77",
        )
        tool = self.result["tool"]
        self.assertEqual(tool["sourceSHA256"], source_hash)
        self.assertEqual(tool["cSourceSHA256"], c_source_hash)
        self.assertEqual(tool["assemblySourceSHA256"], assembly_source_hash)

    def test_host_abi_and_default_parameters_are_exact(self) -> None:
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
            self.result["nativeABI"],
            {
                "staticTextAddress": "0x240861000",
                "staticDefaultInitializerAddress": "0x24093c0f8",
                "staticDefaultStorageAddress": "0x298f0e710",
                "staticMixerAddress": "0x2409406a8",
                "parametersByteCount": 1025,
                "parametersStride": 1032,
            },
        )
        default = self.result["defaultParameters"]
        self.assertEqual(default["repeatCount"], 3)
        self.assertEqual(
            default["normalizedSHA256"], capture.NORMALIZED_DEFAULT_PARAMETERS_SHA256
        )
        normalized = bytes.fromhex(default["normalizedBytes"])
        self.assertEqual(len(normalized), capture.PARAMETERS_STRIDE)
        self.assertEqual(capture.normalize_parameters(normalized), normalized)

    def test_all_numeric_scalar_policies_are_bitwise_gated(self) -> None:
        fields = self.result["scalarFields"]
        self.assertEqual(self.result["scalarFieldCount"], 102)
        self.assertEqual(set(fields), {field.name for field in capture.SCALAR_FIELDS})
        for field in capture.SCALAR_FIELDS:
            observed = fields[field.name]
            self.assertEqual(observed["offset"], field.offset)
            self.assertEqual(observed["policy"], field.policy)
            self.assertEqual(
                tuple(sample["fraction"] for sample in observed["samples"]),
                capture.SAMPLE_FRACTIONS,
            )

        self.assertEqual(
            [sample["valueBits"] for sample in fields["updateRate"]["samples"]],
            ["0x4000000000000000"] * 5,
        )
        self.assertEqual(
            [
                sample["valueBits"]
                for sample in fields["contentOpacity"]["samples"]
            ],
            ["0x40000000"] * 5,
        )
        self.assertEqual(
            [sample["valueBits"] for sample in fields["backdropScale"]["samples"]],
            ["0x40000000"] + ["0x40800000"] * 4,
        )
        self.assertEqual(
            [sample["valueBits"] for sample in self.result["reverseBackdropScale"]],
            ["0x40800000"] * 4 + ["0x40000000"],
        )

    def test_optional_zero_extension_and_boolean_selection_are_exact(self) -> None:
        optionals = self.result["optionalPresence"]
        self.assertEqual(self.result["optionalContainerCount"], 14)
        self.assertEqual(set(optionals), set(capture.CONTAINER_RANGES))
        for optional in optionals.values():
            nil_value = optional["nilValue"]
            present_value = optional["presentValue"]
            self.assertEqual(
                [
                    sample["presenceByte"]
                    for sample in optional["directions"]["nilToSome"]
                ],
                [nil_value] + [present_value] * 4,
            )
            self.assertEqual(
                [
                    sample["presenceByte"]
                    for sample in optional["directions"]["someToNil"]
                ],
                [present_value] * 4 + [nil_value],
            )

        edge = self.result["edgeBleedUseDarkenBlending"]
        self.assertEqual(edge["selectionThreshold"], "to at t >= 0.5; from at t < 0.5")
        self.assertEqual(
            [sample["value"] for sample in edge["directions"]["falseToTrue"]],
            [0, 0, 0, 1, 1, 1, 1],
        )
        self.assertEqual(
            [sample["value"] for sample in edge["directions"]["trueToFalse"]],
            [1, 1, 1, 0, 0, 0, 0],
        )

    def test_resolved_color_boundary_is_measured_without_overclaiming_law(self) -> None:
        colors = self.result["resolvedColors"]
        self.assertEqual(colors["locationCount"], 15)
        self.assertEqual(
            set(colors["locations"]), {field.name for field in capture.COLOR_FIELDS}
        )
        self.assertTrue(colors["allLocationsBitwiseIdenticalByFraction"])
        self.assertTrue(colors["alphaUsesBinary32LinearInterpolation"])
        self.assertTrue(colors["interiorRGBDiffersFromRawBinary32ComponentInterpolation"])
        reference = next(iter(colors["locations"].values()))["samples"]
        for location in colors["locations"].values():
            self.assertEqual(
                [sample["colorBytes"] for sample in location["samples"]],
                [sample["colorBytes"] for sample in reference],
            )

        claims = self.result["claims"]
        self.assertTrue(claims["allEnumeratedNumericScalarPoliciesMeasuredBitwise"])
        self.assertTrue(claims["allFourteenOptionalContainerZeroExtensionPoliciesEstablished"])
        self.assertTrue(claims["edgeBleedBooleanHalfThresholdEstablished"])
        self.assertTrue(claims["allFifteenResolvedColorLocationsShareOneBitwisePolicy"])
        self.assertFalse(claims["resolvedColorExactTransferLawEstablished"])
        self.assertFalse(claims["allParametersFieldBlendSemanticsEstablished"])
        self.assertFalse(claims["cropAllocationPolicyEstablished"])
        self.assertFalse(claims["retinaCompositorColorLawEstablished"])
        self.assertFalse(claims["independentWalleZeroByteFrameParityEstablished"])
        self.assertFalse(claims["liquidGlassParityEstablished"])
        self.assertFalse(claims["productionShaderChangeAuthorized"])


if __name__ == "__main__":
    unittest.main()
