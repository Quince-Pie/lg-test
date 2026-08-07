#!/usr/bin/env python3
"""Contracts for the immutable v4 failure and target-opened v5 diagnosis."""

import json
from pathlib import Path
import unittest


RESULT_PATH = Path(__file__).with_name(
    "prepare_layer_live_crop_replay_v4_cc25df6_holdout_falsification_result.json"
)


class PrepareLayerLiveCropReplayV4FalsificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_failed_v4_gate_is_preserved(self) -> None:
        candidate = self.result["v4FrozenCandidate"]
        self.assertTrue(candidate["failed"])
        self.assertEqual(candidate["rectangleCount"], 32)
        self.assertEqual(candidate["exactRectangleCount"], 0)
        self.assertEqual(candidate["exactComponentCount"], 79)
        self.assertEqual(candidate["maximumULPDistancesXYWH"], [4, 4, 1, 1])
        self.assertFalse(
            self.result["sealedConclusion"]["v4UnseenGeometryTransferPassed"]
        )

    def test_v5_diagnosis_is_exact_but_not_a_holdout(self) -> None:
        diagnosis = self.result["v5OpenedDiagnosis"]
        self.assertTrue(diagnosis["targetOutputsUsedForDiagnosis"])
        self.assertTrue(diagnosis["legacyEndpointTranslationFalsified"])
        self.assertTrue(diagnosis["gaussianShadowExpansionApplied"])
        self.assertEqual(diagnosis["exactRectangleCount"], 32)
        self.assertEqual(diagnosis["exactComponentCount"], 128)
        self.assertEqual(diagnosis["maximumULPDistancesXYWH"], [0, 0, 0, 0])
        self.assertFalse(
            self.result["sealedConclusion"]["v5UnseenGeometryTransferPassed"]
        )

    def test_product_authority_remains_closed(self) -> None:
        sealed = self.result["sealedConclusion"]
        self.assertFalse(sealed["selectedRegionOriginTransferPassed"])
        self.assertFalse(sealed["opticalTransferPassed"])
        self.assertFalse(sealed["independentWalleZeroByteFrameParityPassed"])
        self.assertFalse(sealed["productionShaderAuthorized"])
        self.assertFalse(sealed["liquidGlassParityEstablished"])


if __name__ == "__main__":
    unittest.main()
