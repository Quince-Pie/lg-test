#!/usr/bin/env python3
"""Tests for the exact local case-22 provider arithmetic decode."""

from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

import analyze_backdrop_margin_case22_provider_local_macos_26_6_1 as analysis


ANALYSIS_DIR = Path(__file__).resolve().parent
RESULT_PATH = (
    ANALYSIS_DIR / "backdrop_margin_case22_provider_local_macos_26_6_1_analysis.json"
)
EVIDENCE_DIR = (
    ANALYSIS_DIR.parent.parent
    / "artifacts/mac-quince-macos-26.6.1-case22-provider-passed-42f9413"
)
TRACE_PATH = EVIDENCE_DIR / "backdrop-margin-writer-trace.json"
VALIDATION_PATH = EVIDENCE_DIR / "provider-validation.json"
PREREGISTRATION_PATH = (
    ANALYSIS_DIR
    / "backdrop_margin_case22_provider_local_macos_26_6_1_preregistration.json"
)


class LocalMacOSCase22ProviderAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_selected_helper_replay_is_bit_exact(self) -> None:
        selected = self.result["gaussianExpansionFactor"]["selectedReplay"]
        replay = analysis.replay_helper(selected["inputF32"])
        self.assertEqual(
            struct.pack("<d", replay).hex(), selected["returnRawLittleEndianHex"]
        )
        self.assertEqual(selected["inputRawLittleEndianHex"], "e3ada83c")
        self.assertEqual(selected["returnRawLittleEndianHex"], "261fc8d20282e33f")
        self.assertTrue(selected["bitExact"])

    def test_helper_piecewise_boundaries_are_exact(self) -> None:
        self.assertEqual(analysis.f64_raw(analysis.replay_helper(0.005)), "0" * 16)
        below_raw = struct.pack("<f", 0.505)
        below_bits = int.from_bytes(below_raw, "little")
        below = struct.unpack("<f", below_raw)[0]
        above = struct.unpack("<f", (below_bits + 1).to_bytes(4, "little"))[0]
        self.assertLess(below, 0.505)
        self.assertGreater(above, 0.505)
        self.assertLess(analysis.replay_helper(below), 1.65)
        expected_above = ((above - 0.505) / 0.495) * 0.05 + 1.65
        self.assertEqual(
            analysis.f64_raw(analysis.replay_helper(above)),
            analysis.f64_raw(expected_above),
        )
        constants = {
            item["name"]: item["binary64"]
            for item in self.result["gaussianExpansionFactor"]["constants"]
        }
        self.assertEqual(constants["lowThreshold"], 0.005)
        self.assertEqual(constants["highThreshold"], 0.505)
        self.assertEqual(constants["intercept"], 1.65)

    def test_selected_provider_path_and_return_are_frozen(self) -> None:
        provider = self.result["provider"]
        selected = self.result["selectedArithmetic"]
        self.assertEqual(provider["executedInstructionCount"], 74)
        self.assertEqual(
            provider["executedOffsets"], list(analysis.EXPECTED_PROVIDER_PATH)
        )
        self.assertTrue(selected["allRetainedArithmeticCheckpointsMatchedBitwise"])
        self.assertEqual(selected["primaryWinner"], "shapeCandidate")
        self.assertEqual(selected["finalWinner"], "baseCandidate")
        self.assertEqual(selected["baseCandidateF64"], 13.316424369812012)
        self.assertEqual(selected["returnRawLittleEndianHex"], "0000006002a22a40")

    def test_public_meaning_and_product_authority_remain_closed(self) -> None:
        conclusion = self.result["conclusion"]
        self.assertTrue(conclusion["selectedProviderArithmeticDecoded"])
        self.assertTrue(conclusion["selectedProviderReplayBitExact"])
        for key in (
            "publicObjectFieldMeaningsDecoded",
            "completeFiniteProviderLawDecoded",
            "unobservedProviderBranchesProspectivelyValidated",
            "publicInputMarginLawDecoded",
            "upstreamIntegerCropAllocationPolicyDecoded",
            "prospectiveUnseenProfileTransferPassed",
            "capturedInputOpticalParityPassed",
            "physicalOutputTransferPassed",
            "independentWalleZeroByteFrameParityPassed",
            "productionShaderAuthorized",
            "liquidGlassParityEstablished",
        ):
            self.assertFalse(conclusion[key], key)

    @unittest.skipUnless(
        TRACE_PATH.exists() and VALIDATION_PATH.exists(),
        "local Mac provider evidence is external",
    )
    def test_external_evidence_reanalysis_is_exact(self) -> None:
        regenerated = analysis.analyze(
            TRACE_PATH,
            PREREGISTRATION_PATH,
            VALIDATION_PATH,
        )
        expected = self.result.copy()
        expected_inputs = expected["inputs"].copy()
        regenerated_inputs = regenerated["inputs"].copy()
        for key in ("trace", "preregistration", "validation"):
            expected_inputs.pop(key)
            regenerated_inputs.pop(key)
        expected["inputs"] = expected_inputs
        regenerated["inputs"] = regenerated_inputs
        self.assertEqual(regenerated, expected)


if __name__ == "__main__":
    unittest.main()
