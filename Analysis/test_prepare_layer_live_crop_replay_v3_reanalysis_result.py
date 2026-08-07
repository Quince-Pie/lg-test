#!/usr/bin/env python3
"""Contracts for the canonical opened-evidence crop replay v3 result."""

import json
from pathlib import Path
import unittest


RESULT = Path(__file__).with_name(
    "prepare_layer_live_crop_replay_v3_reanalysis_result.json"
)


class PrepareLayerLiveCropReplayV3ReanalysisResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_all_four_opened_captures_are_bit_exact(self) -> None:
        aggregate = self.result["aggregate"]
        self.assertEqual(aggregate["rectangleCount"], 128)
        self.assertEqual(aggregate["exactRectangleCount"], 128)
        self.assertEqual(aggregate["componentCount"], 512)
        self.assertEqual(aggregate["exactComponentCount"], 512)
        self.assertEqual(aggregate["maximumULPDistancesXYWH"], [0, 0, 0, 0])
        self.assertFalse(aggregate["toleranceUsed"])

    def test_487_is_the_only_opened_nonidentity_precision_discriminator(self) -> None:
        replays = self.result["openedReplays"]
        self.assertEqual(replays["failed485"]["internalInputBleedAmountF32"], 169.75)
        self.assertEqual(replays["dod485"]["internalInputBleedAmountF32"], 169.75)
        self.assertEqual(replays["known800"]["internalInputBleedAmountF32"], 280.0)
        self.assertEqual(
            replays["failed487"]["terminalPublicInputBleedAmountF64"], 170.45
        )
        self.assertEqual(
            replays["failed487"]["internalInputBleedAmountF32"],
            170.4499969482422,
        )

    def test_retrospective_success_grants_no_unseen_or_product_authority(self) -> None:
        sealed = self.result["sealedConclusion"]
        self.assertTrue(sealed["v2UnseenGeometryTransferFalsified"])
        self.assertTrue(sealed["v3OpenedEvidenceReplayPassed"])
        for key in (
            "v2UnseenGeometryTransferPassed",
            "v3UnseenGeometryTransferPassed",
            "selectedRegionOriginTransferPassed",
            "physicalRetinaColorTransferPassed",
            "independentWalleZeroByteFrameParityPassed",
            "productionShaderAuthorized",
            "liquidGlassParityEstablished",
        ):
            self.assertFalse(sealed[key], key)


if __name__ == "__main__":
    unittest.main()
