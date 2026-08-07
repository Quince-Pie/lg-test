#!/usr/bin/env python3
"""Contracts for the frozen unseen-geometry Retina store holdout."""

import hashlib
import json
import unittest
from pathlib import Path

import validate_prepare_layer_live_store_pointer_holdout_local_macos_26_6_1 as validator


ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION_PATH = (
    ROOT
    / "Analysis/prepare_layer_live_store_pointer_holdout_local_macos_26_6_1_preregistration.json"
)
RUNNER_PATH = (
    ROOT
    / "Analysis/run_prepare_layer_live_store_pointer_holdout_local_macos_26_6_1.sh"
)
PREREGISTRATION = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))
RUNNER = RUNNER_PATH.read_text(encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PrepareLayerLiveStorePointerHoldoutTests(unittest.TestCase):
    def test_preregistration_is_unopened_and_output_independent(self) -> None:
        validated = validator._preregistration(PREREGISTRATION_PATH)
        candidate = validated["frozenCandidate"]
        holdout = validated["holdout"]
        self.assertIsNone(validated["runtimeOutcomeFrozenBeforeDispatch"])
        self.assertFalse(holdout["targetOutputsOpenedAtFreeze"])
        self.assertEqual(holdout["trackedRuntimeEvidenceMatchCountAtFreeze"], 0)
        self.assertEqual(holdout["geometry"], validator.EXPECTED_GEOMETRY)
        self.assertEqual(holdout["backingScaleFactor"], 2)
        self.assertFalse(candidate["cropOrProducerValuesUsedForSelection"])
        self.assertFalse(candidate["imageOrPixelValuesUsedForSelection"])
        self.assertFalse(candidate["toleranceUsed"])

    def test_every_frozen_implementation_hash_matches(self) -> None:
        for entry in PREREGISTRATION["frozenImplementation"]["files"]:
            path = ROOT / entry["path"]
            self.assertEqual(sha256(path), entry["sha256"], entry["path"])
        self.assertEqual(
            sha256(ROOT.parent / "shaders/frag.glsl"),
            PREREGISTRATION["frozenImplementation"]["productionShader"][
                "sha256"
            ],
        )
        self.assertEqual(
            sha256(ROOT.parent / "flake.nix"),
            PREREGISTRATION["frozenImplementation"]["developmentFlake"][
                "sha256"
            ],
        )

    def test_runner_is_fixed_to_native_capture_and_nix_analysis(self) -> None:
        for fragment in (
            "LG_GLASS_GEOMETRY=circle-485-center",
            "LG_GLASS_MATERIAL=regular",
            "LG_GLASS_APPEARANCE=dark",
            "LG_TRANSITION_DIRECTION=materialize",
            "/Library/Developer/CommandLineTools/usr/bin/lldb",
            "/nix/var/nix/profiles/default/bin/nix",
            '"nix-command flakes"',
            "check_local_retina_capture_session_v2.swift",
        ):
            self.assertIn(fragment, RUNNER)
        self.assertNotIn("HOLDOUT_", RUNNER)
        self.assertNotIn("github", RUNNER.lower())
        self.assertNotIn("readonly nix=/nix/store/", RUNNER)

    def test_validator_cannot_promote_pixel_or_product_parity(self) -> None:
        source = Path(validator.__file__).read_text(encoding="utf-8")
        self.assertIn('pointer.get("pointerReuseRecordCount", 0) < 1', source)
        self.assertIn('replay.get("maximumULPDistancesXYWH")', source)
        self.assertIn(
            'sealed["lastStorePointerReuseUnseenHoldoutPassed"] = True', source
        )
        for forbidden in (
            'sealed["selectedRegionOriginTransferPassed"] = True',
            'sealed["physicalRetina2xAndColorTransferPassed"] = True',
            'sealed["productionShaderAuthorized"] = True',
            'sealed["liquidGlassParityEstablished"] = True',
            "isclose(",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
