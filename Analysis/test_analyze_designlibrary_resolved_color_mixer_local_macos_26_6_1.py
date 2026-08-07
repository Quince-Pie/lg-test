#!/usr/bin/env python3
"""Tests for the exact DesignLibrary resolved-color mixer law."""

from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

import analyze_designlibrary_resolved_color_mixer_local_macos_26_6_1 as analyzer


ANALYSIS = Path(__file__).resolve().parent
SOURCE_PATH = Path(analyzer.__file__).resolve()
RESULT_PATH = ANALYSIS / (
    "designlibrary_resolved_color_mixer_local_macos_26_6_1_result.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DesignLibraryResolvedColorMixerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_sources_and_canonical_result_are_frozen(self) -> None:
        ast.parse(self.source, feature_version=(3, 9))
        source_hash = sha256(SOURCE_PATH)
        self.assertEqual(
            source_hash,
            "40509f1210c45588791e39d989d6409fa7496b171a250919f1151ed0a4974ed5",
        )
        self.assertEqual(
            sha256(RESULT_PATH),
            "4a58f3434e13625ab7ce5ff4762e50df1600f6d09e173b950f0480418b4bf683",
        )
        self.assertEqual(self.result["tool"]["sourceSHA256"], source_hash)
        sources = {
            analyzer.PRIVATE_PROBE_NAME: analyzer.PRIVATE_PROBE_SHA256,
            analyzer.PRIVATE_BRIDGE_NAME: analyzer.PRIVATE_BRIDGE_SHA256,
            analyzer.IMPORT_PROBE_NAME: analyzer.IMPORT_PROBE_SHA256,
            analyzer.SWIFT_PROBE_NAME: analyzer.SWIFT_PROBE_SHA256,
        }
        for name, expected in sources.items():
            self.assertEqual(sha256(ANALYSIS / name), expected)

    def test_complete_private_code_and_semantic_instructions_are_exact(self) -> None:
        code = self.result["codeRegion"]
        self.assertEqual(code["start"], "0x240995160")
        self.assertEqual(code["endExclusive"], "0x24099536c")
        self.assertEqual(code["byteCount"], 524)
        self.assertEqual(code["instructionCount"], 131)
        self.assertEqual(code["sha256"], analyzer.COLOR_MIXER_SHA256)
        self.assertEqual(
            {
                int(destination, 16): tuple(int(value, 16) for value in callsites)
                for destination, callsites in code["directCalls"].items()
            },
            analyzer.EXPECTED_DIRECT_CALLS,
        )
        observed = {
            int(record["address"], 16): (
                record["mnemonic"],
                record["operands"],
            )
            for record in code["instructionContracts"]
        }
        self.assertEqual(observed, analyzer.CRITICAL_INSTRUCTIONS)

    def test_imports_resolve_to_exact_public_swiftui_operations(self) -> None:
        self.assertEqual(
            self.result["rgbColorSpace"],
            {"case": "sRGB", "runtimeEnumTag": 0},
        )
        imports = self.result["resolvedImportTargets"]
        self.assertEqual(set(imports), {
            "0x{:x}".format(address) for address in analyzer.EXPECTED_IMPORT_TARGETS
        })
        for stub, expected in analyzer.EXPECTED_IMPORT_TARGETS.items():
            observed = imports["0x{:x}".format(stub)]
            self.assertEqual(observed["staticTarget"], "0x{:x}".format(expected[0]))
            self.assertEqual(observed["image"], expected[1])
            self.assertEqual(observed["symbol"], expected[2])

    def test_direct_private_and_public_composition_are_bitwise_equal(self) -> None:
        validation = self.result["bitwiseValidation"]
        self.assertEqual(validation["curatedSampleCount"], 13)
        self.assertEqual(validation["randomSampleCount"], 192)
        self.assertEqual(validation["totalSampleCount"], 205)
        self.assertEqual(validation["randomSeed"], "0x4c475243")
        self.assertEqual(
            validation["inputSHA256"],
            "5cd46d9c16b59dcdcf6c5fe57adbb9f3c16c914d7d5d52b51e5676c8eac20143",
        )
        self.assertEqual(
            validation["privateOutputSHA256"],
            "096f07a965544de4f41d83fd532eaa397c887d8992e30e4ff67e6e624857a4b9",
        )
        self.assertEqual(
            validation["publicCompositionOutputSHA256"],
            validation["privateOutputSHA256"],
        )
        self.assertTrue(validation["allOutputsBitwiseEqual"])
        by_label = {
            sample["label"]: sample for sample in validation["detailedSamples"]
        }
        self.assertEqual(
            by_label["reference"]["outputRawWords"],
            ["0x3e9d2bff", "0x3ec38d01", "0x3ee42642", "0x3f19999a"],
        )
        self.assertNotEqual(
            by_label["exact-from"]["outputRawWords"],
            by_label["exact-from"]["fromRawWords"],
        )
        self.assertNotEqual(
            by_label["exact-to"]["outputRawWords"],
            by_label["exact-to"]["toRawWords"],
        )

    def test_parameters_semantics_close_without_overclaiming_frame_parity(self) -> None:
        law = self.result["exactLaw"]
        self.assertEqual(
            law["outputConstruction"],
            "public Color.Resolved.init(colorSpace: .sRGB, red:green:blue:opacity:)",
        )
        claims = self.result["claims"]
        self.assertTrue(claims["resolvedColorExactTransferLawEstablished"])
        self.assertTrue(claims["allParametersFieldBlendSemanticsEstablished"])
        self.assertFalse(
            claims["transitionProgressToPublicConfigurationMixByLawEstablished"]
        )
        self.assertFalse(
            claims["publicControlsToResolvedConfigurationSelectionLawEstablished"]
        )
        self.assertFalse(
            claims["environmentToResolvedConfigurationSelectionLawEstablished"]
        )
        self.assertFalse(claims["cropAllocationPolicyEstablished"])
        self.assertFalse(claims["retinaCompositorColorLawEstablished"])
        self.assertFalse(claims["independentWalleZeroByteFrameParityEstablished"])
        self.assertFalse(claims["liquidGlassParityEstablished"])
        self.assertFalse(claims["productionShaderChangeAuthorized"])


if __name__ == "__main__":
    unittest.main()
