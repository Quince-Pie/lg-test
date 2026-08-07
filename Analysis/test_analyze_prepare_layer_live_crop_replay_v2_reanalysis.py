#!/usr/bin/env python3
"""Contracts for the immutable v2 opened-evidence reanalysis."""

import hashlib
import json
from pathlib import Path
import unittest

import analyze_prepare_layer_live_crop_replay_v2_reanalysis as analyzer


RESULT_PATH = Path(__file__).with_name(
    "prepare_layer_live_crop_replay_v2_reanalysis_result.json"
)
RESULT_SHA256 = "cc85c131e29d6f91434c87872778d85f347fa7ae4301ef118d29559ff06732ec"


class PrepareLayerLiveCropReplayV2ReanalysisTests(unittest.TestCase):
    def test_all_opened_inputs_are_content_addressed(self) -> None:
        self.assertEqual(
            set(analyzer.EXPECTED_INPUTS), {"failed485", "dod485", "known800"}
        )
        for specification in analyzer.EXPECTED_INPUTS.values():
            self.assertEqual(len(specification["traceSHA256"]), 64)
            self.assertEqual(len(specification["timelineSHA256"]), 64)

    def test_direct_dod_source_is_exact(self) -> None:
        self.assertEqual(
            analyzer.EXPECTED_DOD_SOURCE,
            (-169.75, -169.75, 824.5, 824.5),
        )
        self.assertEqual(analyzer.EXPECTED_DOD_SOURCE_COUNT, 80)

    def test_result_seals_only_opened_evidence(self) -> None:
        self.assertEqual(
            hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest(), RESULT_SHA256
        )
        result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(result["aggregate"]["exactComponentCount"], 384)
        self.assertEqual(result["aggregate"]["maximumULPDistancesXYWH"], [0, 0, 0, 0])
        self.assertTrue(result["sealedConclusion"]["v2OpenedEvidenceReplayPassed"])
        self.assertFalse(result["sealedConclusion"]["v2UnseenGeometryTransferPassed"])


if __name__ == "__main__":
    unittest.main()
