#!/usr/bin/env python3
"""Contracts for the prospective direct-Retina v5 holdout pass."""

import json
from pathlib import Path
import unittest


RESULT_PATH = Path(__file__).with_name(
    "prepare_layer_live_crop_replay_v5_0769cd9_holdout_result.json"
)


class PrepareLayerLiveCropReplayV5HoldoutResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_prospective_profile_and_retina_session_passed(self) -> None:
        self.assertEqual(self.result["conclusion"], "success")
        self.assertTrue(self.result["profile"]["geometryWasRuntimeUnseenAtFreeze"])
        self.assertFalse(self.result["profile"]["targetOutputsOpenedAtFreeze"])
        self.assertTrue(self.result["retinaPreflight"]["passed"])
        self.assertEqual(self.result["retinaPreflight"]["physicalPixels"], [3456, 2234])
        self.assertEqual(self.result["run"]["lldbExitStatus"], 0)
        self.assertEqual(self.result["run"]["validationExitStatus"], 0)
        self.assertTrue(self.result["run"]["independentLocalValidationByteIdentical"])

    def test_crop_dod_transfer_is_bit_exact(self) -> None:
        replay = self.result["floatingReplay"]
        self.assertEqual(replay["exactRectangleCount"], 32)
        self.assertEqual(replay["exactComponentCount"], 128)
        self.assertEqual(replay["maximumULPDistancesXYWH"], [0, 0, 0, 0])
        self.assertFalse(replay["toleranceUsed"])
        self.assertEqual(
            self.result["shadowArithmetic"]["positiveExpansionRecordCount"], 32
        )
        self.assertFalse(
            self.result["shadowArithmetic"]["endpointDerivedSDFTranslationApplied"]
        )
        self.assertTrue(self.result["pointerSelection"]["pointerReuseBranchExecuted"])

    def test_authority_stops_before_optics_and_walle(self) -> None:
        sealed = self.result["sealedConclusion"]
        self.assertTrue(sealed["v5UnseenGeometryTransferPassed"])
        self.assertTrue(sealed["regularDarkMaterializeCropDODGeometryTransferPassed"])
        self.assertFalse(sealed["selectedRegionOriginTransferPassed"])
        self.assertFalse(sealed["opticalTransferPassed"])
        self.assertFalse(sealed["physicalRetinaColorCompositorTransferPassed"])
        self.assertFalse(sealed["independentWalleZeroByteFrameParityPassed"])
        self.assertFalse(sealed["productionShaderAuthorized"])
        self.assertFalse(sealed["liquidGlassParityEstablished"])
        self.assertEqual(len(self.result["remainingMajorProductBoundaries"]), 4)


if __name__ == "__main__":
    unittest.main()
