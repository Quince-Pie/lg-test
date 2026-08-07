#!/usr/bin/env python3
"""Contracts for the immutable circle-496 v3 holdout outcome."""

import json
from pathlib import Path
import unittest


RESULT = Path(__file__).with_name(
    "prepare_layer_live_crop_replay_v3_a2ff533_holdout_outcome_result.json"
)


class PrepareLayerLiveCropReplayV3A2FF533OutcomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_frozen_compound_gate_remains_failed(self) -> None:
        gate = self.result["frozenCompoundGate"]
        self.assertEqual(gate["conclusion"], "failure")
        self.assertFalse(gate["relabelledAsPass"])
        self.assertEqual(gate["failedArithmeticTerms"], [])
        self.assertEqual(len(gate["failedCoverageTerms"]), 3)

    def test_unseen_arithmetic_is_bit_exact(self) -> None:
        replay = self.result["prospectiveArithmeticResult"]
        self.assertEqual(replay["rectangleCount"], 32)
        self.assertEqual(replay["exactRectangleCount"], 32)
        self.assertEqual(replay["componentCount"], 128)
        self.assertEqual(replay["exactComponentCount"], 128)
        self.assertEqual(replay["mismatchedRectangleCount"], 0)
        self.assertEqual(replay["mismatchedComponentCount"], 0)
        self.assertEqual(replay["maximumULPDistancesXYWH"], [0, 0, 0, 0])

    def test_failed_coverage_is_absence_not_a_pointer_mismatch(self) -> None:
        pointer = self.result["observedPointerCoverage"]
        self.assertEqual(pointer["matchingStoreRecordCount"], 32)
        self.assertEqual(pointer["pointerReuseRecordCount"], 0)
        self.assertTrue(pointer["allSingletonMatches"])
        self.assertFalse(pointer["pointerReuseBranchExecuted"])
        self.assertFalse(pointer["pointerSelectionMismatchObserved"])

    def test_no_product_or_full_transfer_authority_is_claimed(self) -> None:
        sealed = self.result["sealedConclusion"]
        self.assertTrue(sealed["v3UnseenGeometryArithmeticPassed"])
        self.assertFalse(sealed["v3CompoundHoldoutPassed"])
        for key in (
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
