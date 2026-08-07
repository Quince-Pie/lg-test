#!/usr/bin/env python3
"""Contracts for the canonical opened-evidence crop replay v4 result."""

import json
from pathlib import Path
import unittest


RESULT = Path(__file__).with_name(
    "prepare_layer_live_crop_replay_v4_reanalysis_result.json"
)


class PrepareLayerLiveCropReplayV4ReanalysisResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_all_six_opened_captures_are_bit_exact(self) -> None:
        aggregate = self.result["aggregate"]
        self.assertEqual(aggregate["rectangleCount"], 192)
        self.assertEqual(aggregate["exactRectangleCount"], 192)
        self.assertEqual(aggregate["componentCount"], 768)
        self.assertEqual(aggregate["exactComponentCount"], 768)
        self.assertEqual(aggregate["maximumULPDistancesXYWH"], [0, 0, 0, 0])
        self.assertFalse(aggregate["toleranceUsed"])

    def test_result_preserves_v3_falsification_and_no_product_authority(self) -> None:
        sealed = self.result["sealedConclusion"]
        self.assertTrue(sealed["v3UnseenGeometryTransferFalsified"])
        self.assertTrue(sealed["v4OpenedEvidenceReplayPassed"])
        for key in (
            "v3UnseenGeometryTransferPassed",
            "v4UnseenGeometryTransferPassed",
            "selectedRegionOriginTransferPassed",
            "physicalRetinaColorTransferPassed",
            "independentWalleZeroByteFrameParityPassed",
            "productionShaderAuthorized",
            "liquidGlassParityEstablished",
        ):
            self.assertFalse(sealed[key], key)


if __name__ == "__main__":
    unittest.main()
