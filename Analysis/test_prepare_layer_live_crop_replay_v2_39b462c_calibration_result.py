#!/usr/bin/env python3
"""Contracts for the direct-Retina v2 crop calibration result."""

import hashlib
import json
from pathlib import Path
import unittest


RESULT_PATH = Path(__file__).with_name(
    "prepare_layer_live_crop_replay_v2_39b462c_calibration_result.json"
)


class PrepareLayerLiveCropReplayV2CalibrationResultTests(unittest.TestCase):
    def test_calibration_is_exact_but_has_no_transfer_authority(self) -> None:
        result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(result["floatingReplay"]["exactRectangleCount"], 32)
        self.assertEqual(result["floatingReplay"]["exactComponentCount"], 128)
        self.assertEqual(
            result["floatingReplay"]["maximumULPDistancesXYWH"], [0, 0, 0, 0]
        )
        self.assertTrue(
            result["sealedConclusion"]["nativeCaptureAndEmbeddedCodeTransportPassed"]
        )
        self.assertFalse(result["sealedConclusion"]["v2UnseenGeometryTransferPassed"])
        self.assertFalse(result["sealedConclusion"]["productionShaderAuthorized"])

    def test_result_is_content_addressable(self) -> None:
        self.assertEqual(len(hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest()), 64)


if __name__ == "__main__":
    unittest.main()
