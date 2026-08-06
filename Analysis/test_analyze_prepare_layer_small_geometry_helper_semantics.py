#!/usr/bin/env python3
"""Checks for the Gaussian and delegated backdrop semantics decode."""

from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

import analyze_prepare_layer_small_geometry_helper_semantics as analysis


RESULT_PATH = (
    Path(__file__).resolve().parent
    / "dynamic_allocation_prepare_layer_small_geometry_helper_semantics_analysis.json"
)
RESULT = json.loads(RESULT_PATH.read_text(encoding="utf-8"))


class SmallGeometryHelperSemanticsAnalysisTests(unittest.TestCase):
    def test_gaussian_selected_replay_is_bit_exact(self) -> None:
        gaussian = RESULT["gaussianExpansionFactor"]
        constants = {item["name"]: item["binary64"] for item in gaussian["constants"]}
        selected = gaussian["selectedReplay"]
        replay = analysis.replay_gaussian(selected["inputF64"], constants)
        self.assertEqual(analysis.f64_hex(replay), selected["returnHex"])
        self.assertTrue(selected["bitExact"])

    def test_gaussian_exact_constants_and_continuous_join_are_retained(self) -> None:
        gaussian = RESULT["gaussianExpansionFactor"]
        constants = {item["name"]: item["binary64"] for item in gaussian["constants"]}
        self.assertEqual(constants["lowThreshold"], 0.005)
        self.assertEqual(constants["highThreshold"], 0.505)
        self.assertEqual(constants["activeShift"], -0.005)
        self.assertEqual(constants["logIntercept"], 1.65)
        self.assertEqual(constants["logSlope"], 0.3)
        self.assertEqual(constants["alternateModeReturn"], 2.8)
        self.assertTrue(gaussian["exactLaw"]["activeHighJoinIsBitExact"])
        self.assertEqual(gaussian["exactLaw"]["joinHex"], struct.pack("<d", 1.65).hex())

    def test_delegated_bounds_code_is_complete_and_condition_is_explicit(self) -> None:
        bounds = RESULT["getBackdropBounds"]
        self.assertEqual(bounds["symbolByteCount"], 188)
        self.assertEqual(bounds["instructionCount"], 47)
        self.assertEqual(
            bounds["codeSHA256"],
            "3296daa4d858acc2a259be7771e48c312ff7010fa3d7cd590a9f28bd17a4ff17",
        )
        conditional = bounds["conditionalNominalBaseMargin83Replay"]
        self.assertTrue(conditional["matchesReturn"])
        self.assertFalse(conditional["directlyCapturedFact"])

    def test_bounds_replay_preserves_binary32_margin_conversion(self) -> None:
        replay = analysis.replay_get_backdrop_bounds((0.0, 0.0, 127.0, 127.0), 83.0)
        self.assertEqual(replay, (-83.0, -83.0, 293.0, 293.0))

    def test_remaining_authority_is_fail_closed(self) -> None:
        conclusion = RESULT["conclusion"]
        self.assertTrue(conclusion["gaussianExactPiecewiseLawDecoded"])
        self.assertTrue(conclusion["getBackdropBoundsCompleteSemanticsDecoded"])
        for key in (
            "liveBackdropBaseAndMarginFieldsCaptured",
            "backdropMarginWriterDecoded",
            "dynamicTopologyLawDecoded",
            "prospectiveUnseenGeometryTransferPassed",
            "capturedInputOpticalParityPassed",
            "independentPrivateInputGenerationPassed",
            "physicalOutputTransferPassed",
            "independentWalleZeroByteFrameParityPassed",
            "productionShaderAuthorized",
            "liquidGlassParityEstablished",
        ):
            self.assertFalse(conclusion[key], key)


if __name__ == "__main__":
    unittest.main()
