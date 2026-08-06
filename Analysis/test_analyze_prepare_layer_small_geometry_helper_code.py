#!/usr/bin/env python3
"""Checks for the accepted small-geometry helper-code decode."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import analyze_prepare_layer_small_geometry_helper_code as analysis


RESULT_PATH = (
    Path(__file__).resolve().parent
    / "dynamic_allocation_prepare_layer_small_geometry_helper_code_analysis.json"
)
RESULT = json.loads(RESULT_PATH.read_text(encoding="utf-8"))


class SmallGeometryHelperCodeAnalysisTests(unittest.TestCase):
    def test_arm64_decoders_recover_frozen_references(self) -> None:
        fake_adrp = {"pc": 0x19A384018, "rawLittleEndianHex": "c80f0090"}
        fake_ldr = {"rawLittleEndianHex": "018944fd"}
        self.assertEqual(analysis.decode_adrp_target(fake_adrp), 0x19A57C000)
        self.assertEqual(analysis.decode_ldr_d_unsigned_offset(fake_ldr), 0x910)
        fake_bl = {"pc": 0x19A3F4AE8, "rawLittleEndianHex": "0b000094"}
        self.assertEqual(analysis.decode_bl_target(fake_bl), 0x19A3F4B14)

    def test_gaussian_control_flow_and_all_data_references_are_retained(self) -> None:
        gaussian = RESULT["gaussianExpansionFactor"]
        self.assertEqual(
            gaussian["codeSHA256"],
            "7834bbb95f84915a6544d34b4148f7f267fcc94d2ae730888644535ffc57c0dd",
        )
        self.assertEqual(len(gaussian["dataConstants"]), 8)
        self.assertEqual(
            [item["moduleRelativeOffset"] for item in gaussian["dataConstants"]],
            [
                0x394910,
                0x394928,
                0x394930,
                0x394938,
                0x394940,
                0x394918,
                0x394920,
                0x3944F8,
            ],
        )
        self.assertTrue(RESULT["conclusion"]["gaussianSymbolicControlFlowDecoded"])
        self.assertFalse(gaussian["generalNumericLawDecoded"])

    def test_backdrop_wrapper_points_at_the_actual_allocation_function(self) -> None:
        backdrop = RESULT["backdropGetBounds"]
        self.assertEqual(backdrop["activeFlagMask"], 0x500)
        self.assertEqual(backdrop["delegatedFunctionRelativeToPrepareLayer"], 364696)
        self.assertIn("get_backdrop_bounds", backdrop["delegatedFunction"])
        self.assertTrue(RESULT["conclusion"]["backdropWrapperSemanticsDecoded"])
        self.assertFalse(backdrop["allocationGeneralLawDecoded"])

    def test_no_transfer_or_product_parity_is_claimed(self) -> None:
        conclusion = RESULT["conclusion"]
        self.assertTrue(conclusion["transportRetryPassed"])
        self.assertTrue(conclusion["helperCodeOpeningPassed"])
        for key in (
            "gaussianGeneralNumericLawDecoded",
            "backdropAllocationGeneralLawDecoded",
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
