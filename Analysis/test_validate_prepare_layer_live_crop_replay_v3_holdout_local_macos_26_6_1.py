#!/usr/bin/env python3
"""Source contracts for the frozen unseen v3 live crop holdout."""

import hashlib
import json
from pathlib import Path
import unittest

import validate_prepare_layer_live_crop_replay_v3_holdout_local_macos_26_6_1 as validator


SOURCE = Path(validator.__file__).read_text(encoding="utf-8")
PREREGISTRATION_PATH = Path(__file__).with_name(
    "prepare_layer_live_crop_replay_v3_holdout_local_macos_26_6_1_preregistration.json"
)


class PrepareLayerLiveCropReplayV3HoldoutTests(unittest.TestCase):
    def test_holdout_profile_is_fixed_and_runtime_unseen(self) -> None:
        self.assertEqual(validator.EXPECTED_GEOMETRY, "circle-496-center")
        self.assertEqual(validator.EXPECTED_MATERIAL, "regular")
        self.assertEqual(validator.EXPECTED_APPEARANCE, "dark")
        self.assertEqual(validator.EXPECTED_DIRECTION, "materialize")
        self.assertIn('holdout.get("targetOutputsOpenedAtFreeze") is not False', SOURCE)
        self.assertIn('holdout.get("runtimeEvidenceMatchCountAtFreeze") != 0', SOURCE)

        preregistration = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))
        holdout = preregistration["holdout"]
        self.assertEqual(holdout["geometry"], validator.EXPECTED_GEOMETRY)
        self.assertEqual(holdout["runtimeEvidenceMatchCountAtFreeze"], 0)
        self.assertFalse(holdout["targetOutputsOpenedAtFreeze"])
        self.assertIsNone(preregistration["runtimeOutcomeFrozenBeforeDispatch"])

    def test_gate_requires_exact_bytes_and_grants_no_product_authority(self) -> None:
        for fragment in (
            'model.get("binary32ConversionCount") != 1',
            'replay.get("exactRectangleCount") != 32',
            'replay.get("exactComponentCount") != 128',
            'replay.get("maximumULPDistancesXYWH") != [0, 0, 0, 0]',
            'sealed["productionShaderAuthorized"] = False',
            'sealed["liquidGlassParityEstablished"] = False',
        ):
            self.assertIn(fragment, SOURCE)
        self.assertNotIn("isclose(", SOURCE)

    def test_every_frozen_file_matches_its_preregistered_hash(self) -> None:
        preregistration = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))
        repository = PREREGISTRATION_PATH.parent.parent
        for record in preregistration["frozenFiles"]:
            self.assertEqual(
                hashlib.sha256((repository / record["path"]).read_bytes()).hexdigest(),
                record["sha256"],
            )


if __name__ == "__main__":
    unittest.main()
