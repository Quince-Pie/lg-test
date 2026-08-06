#!/usr/bin/env python3
"""Checks for the exact small-geometry Filter/SDF arithmetic decode."""

from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

import analyze_prepare_layer_filter_sdf_small_geometry as analysis


RESULT_PATH = (
    Path(__file__).resolve().parent
    / "dynamic_allocation_prepare_layer_filter_sdf_small_geometry_analysis.json"
)
RESULT = json.loads(RESULT_PATH.read_text(encoding="utf-8"))


class SmallGeometryAnalysisTests(unittest.TestCase):
    def test_sdf_replay_is_bit_exact(self) -> None:
        target = RESULT["sdf"]
        candidate = analysis.replay_sdf(
            tuple(target["entryF64"]), tuple(target["parametersF32"])
        )
        self.assertEqual(analysis.f64_hex(candidate), target["returnHex"])
        self.assertTrue(target["replayExact"])

    def test_shadow_expansion_closes_the_only_former_residual(self) -> None:
        target = RESULT["filter"]
        residual = RESULT["isolatedFormerResidual"]
        self.assertEqual(target["replayHex"], target["returnHex"])
        self.assertEqual(
            target["shadowExpansionF64"],
            target["gaussianExpansionFactorF64"] * target["shadowRadiusF64"],
        )
        self.assertEqual(
            residual["shadowFarEdgeAdvantageF64"],
            target["shadowFarAfterOffsetF64"][1] - target["expandedFarF64"][1],
        )
        self.assertEqual(
            residual["deltaWithoutShadowExpansionF64"],
            [0.0, 0.149145929943586, 0.0, -0.149145929943586],
        )
        self.assertTrue(residual["yAndHeightAreNowExact"])

    def test_raw_source_and_backdrop_clip_are_not_conflated(self) -> None:
        separation = RESULT["separation"]
        self.assertEqual(
            separation["rawGlassSourceDODF64"], [0.0, 0.0, 127.0, 127.0]
        )
        self.assertEqual(
            separation["backdropReturnedClipF64"], [-83.0, -83.0, 293.0, 293.0]
        )
        self.assertTrue(separation["rawSourceAndRecursiveClipAreDistinct"])
        self.assertFalse(separation["generalEdgeAllocationLawEstablished"])

    def test_result_retains_exact_float32_sdf_parameters(self) -> None:
        parameters = RESULT["sdf"]["parametersF32"]
        self.assertEqual(
            struct.pack("<4f", *parameters).hex(),
            "186d3142000000000000000000000000",
        )

    def test_no_transfer_or_parity_authority_is_claimed(self) -> None:
        conclusion = RESULT["conclusion"]
        self.assertTrue(conclusion["selectedSmallGeometrySDFReplayExact"])
        self.assertTrue(conclusion["selectedSmallGeometryFilterReplayExact"])
        self.assertTrue(conclusion["formerVerticalResidualExplainedExactly"])
        for key in (
            "gaussianHelperGeneralLawDecoded",
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
