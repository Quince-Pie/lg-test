#!/usr/bin/env python3
"""Contracts for the immutable v3 endpoint-order falsification."""

import json
from pathlib import Path
import unittest


RESULT = Path(__file__).with_name(
    "prepare_layer_live_crop_replay_v3_7f0807a_split_holdout_falsification_result.json"
)


class PrepareLayerLiveCropReplayV3SplitFalsificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_pointer_gate_passed_but_arithmetic_failed(self) -> None:
        self.assertTrue(self.result["splitPointerGate"]["pointerGatePassed"])
        replay = self.result["prospectiveReplay"]
        self.assertEqual(replay["exactRectangleCount"], 31)
        self.assertEqual(replay["exactComponentCount"], 126)
        self.assertEqual(replay["maximumULPDistancesXYWH"], [0, 2, 0, 1])
        self.assertEqual(self.result["conclusion"], "falsified")

    def test_opened_correction_has_no_prospective_authority(self) -> None:
        diagnosis = self.result["openedDiagnosis"]
        self.assertTrue(diagnosis["endpointOffsetIsGroupedIntoYTranslation"])
        self.assertTrue(diagnosis["targetOutputsUsedToDeriveCorrection"])
        self.assertFalse(diagnosis["correctedCandidateProspectivelyEstablished"])
        self.assertEqual(
            diagnosis["retrospectiveCorrectedMaximumULPDistancesXYWH"],
            [0, 0, 0, 0],
        )
        sealed = self.result["sealedConclusion"]
        self.assertTrue(sealed["v3UnseenGeometryTransferFalsified"])
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
