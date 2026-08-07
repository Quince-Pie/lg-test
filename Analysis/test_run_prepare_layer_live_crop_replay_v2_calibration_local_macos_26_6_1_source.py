#!/usr/bin/env python3
"""Source contract for the direct-M1 v2 crop calibration executor."""

from pathlib import Path
import unittest


SOURCE = (
    Path(__file__)
    .with_name(
        "run_prepare_layer_live_crop_replay_v2_calibration_local_macos_26_6_1.sh"
    )
    .read_text(encoding="utf-8")
)


class RunPrepareLayerLiveCropReplayV2CalibrationTests(unittest.TestCase):
    def test_native_and_analysis_environments_are_separated(self) -> None:
        self.assertIn("/Library/Developer/CommandLineTools/usr/bin/lldb", SOURCE)
        self.assertIn("/nix/var/nix/profiles/default/bin/nix", SOURCE)
        self.assertIn('--extra-experimental-features "nix-command flakes"', SOURCE)
        self.assertIn("native capture environment contains a Nix store path", SOURCE)

    def test_opened_calibration_profile_is_fixed(self) -> None:
        for fragment in (
            "LG_GLASS_GEOMETRY=circle-485-center",
            "LG_GLASS_MATERIAL=regular",
            "LG_GLASS_APPEARANCE=dark",
            "LG_TRANSITION_DIRECTION=materialize",
            "LG_TRANSITION_ALLOCATION_DENSE=1",
        ):
            self.assertIn(fragment, SOURCE)


if __name__ == "__main__":
    unittest.main()
