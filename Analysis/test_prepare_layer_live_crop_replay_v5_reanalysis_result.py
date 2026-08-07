#!/usr/bin/env python3
"""Contracts for the ten-capture exact v5 retrospective replay."""

import json
from pathlib import Path
import unittest


RESULT_PATH = Path(__file__).with_name(
    "prepare_layer_live_crop_replay_v5_reanalysis_result.json"
)


class PrepareLayerLiveCropReplayV5ReanalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_all_retained_direct_mac_captures_are_bit_exact(self) -> None:
        aggregate = self.result["aggregate"]
        self.assertEqual(aggregate["captureCount"], 10)
        self.assertEqual(aggregate["rectangleCount"], 320)
        self.assertEqual(aggregate["exactRectangleCount"], 320)
        self.assertEqual(aggregate["componentCount"], 1280)
        self.assertEqual(aggregate["exactComponentCount"], 1280)
        self.assertEqual(aggregate["maximumULPDistancesXYWH"], [0, 0, 0, 0])
        self.assertFalse(aggregate["toleranceUsed"])

    def test_shadow_replaces_the_correlated_endpoint_offset(self) -> None:
        aggregate = self.result["aggregate"]
        self.assertEqual(aggregate["positiveShadowExpansionRecordCount"], 320)
        self.assertEqual(aggregate["legacyEndpointBranchRecordCount"], 10)
        self.assertEqual(aggregate["legacyEndpointArithmeticOffsetAppliedCount"], 0)
        self.assertTrue(
            self.result["v4Falsification"]["endpointSDFTranslationFalsified"]
        )

    def test_reanalysis_does_not_claim_unseen_or_product_transfer(self) -> None:
        sealed = self.result["sealedConclusion"]
        self.assertFalse(sealed["v5UnseenGeometryTransferPassed"])
        self.assertFalse(sealed["selectedRegionOriginTransferPassed"])
        self.assertFalse(sealed["opticalTransferPassed"])
        self.assertFalse(sealed["physicalRetinaColorCompositorTransferPassed"])
        self.assertFalse(sealed["independentWalleZeroByteFrameParityPassed"])
        self.assertFalse(sealed["productionShaderAuthorized"])
        self.assertFalse(sealed["liquidGlassParityEstablished"])


if __name__ == "__main__":
    unittest.main()
