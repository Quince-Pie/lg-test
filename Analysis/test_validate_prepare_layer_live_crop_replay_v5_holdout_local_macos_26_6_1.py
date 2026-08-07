#!/usr/bin/env python3
"""Source contracts for the frozen runtime-unseen v5 crop holdout."""

import hashlib
import json
from pathlib import Path
import unittest

import validate_prepare_layer_live_crop_replay_v5_holdout_local_macos_26_6_1 as validator


SOURCE = Path(validator.__file__).read_text(encoding="utf-8")
PREREGISTRATION_PATH = Path(__file__).with_name(
    "prepare_layer_live_crop_replay_v5_holdout_local_macos_26_6_1_preregistration.json"
)


class PrepareLayerLiveCropReplayV5HoldoutTests(unittest.TestCase):
    def test_profile_is_frozen_and_runtime_unseen(self) -> None:
        self.assertEqual(validator.EXPECTED_GEOMETRY, "circle-499-center")
        preregistration = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))
        holdout = preregistration["holdout"]
        self.assertEqual(holdout["runtimeEvidenceMatchCountAtFreeze"], 0)
        self.assertFalse(holdout["targetOutputsOpenedAtFreeze"])
        self.assertIsNone(preregistration["runtimeOutcomeFrozenBeforeDispatch"])

    def test_gate_pins_shadow_source_and_exact_replay(self) -> None:
        preregistration = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))
        candidate = preregistration["frozenCandidate"]
        self.assertTrue(candidate["publicBackdropLayerBoundsUsed"])
        self.assertTrue(candidate["authenticatedBackdropBoundsOperationOrder"])
        self.assertTrue(candidate["gaussianShadowExpansionApplied"])
        self.assertFalse(candidate["endpointDerivedSDFTranslationApplied"])
        self.assertFalse(candidate["pointerReuseEventRequired"])
        for fragment in (
            'sdf.get("endpointOffsetGroupedIntoYTranslation") is not False',
            'endpoint.get("arithmeticOffsetApplied") is not False',
            'shadow.get("positiveExpansionRecordCount") != 32',
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
