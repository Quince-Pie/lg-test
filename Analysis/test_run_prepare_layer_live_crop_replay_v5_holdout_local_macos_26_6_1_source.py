#!/usr/bin/env python3
"""Source contract for the direct-M1 runtime-unseen v5 crop executor."""

from pathlib import Path
import unittest


SOURCE = (
    Path(__file__)
    .with_name("run_prepare_layer_live_crop_replay_v5_holdout_local_macos_26_6_1.sh")
    .read_text(encoding="utf-8")
)


class RunPrepareLayerLiveCropReplayV5HoldoutTests(unittest.TestCase):
    def test_unseen_profile_and_preregistration_are_fixed(self) -> None:
        for fragment in (
            "LG_GLASS_GEOMETRY=circle-499-center",
            "LG_GLASS_MATERIAL=regular",
            "LG_GLASS_APPEARANCE=dark",
            "LG_TRANSITION_DIRECTION=materialize",
            '--preregistration "$preregistration"',
            "fbcf03a1cf751802e0a515da4f0bde5ad48f52fc63f9d3ca558ec0538dd33cd6",
        ):
            self.assertIn(fragment, SOURCE)

    def test_direct_retina_native_and_nix_analysis_are_separated(self) -> None:
        self.assertIn("/Library/Developer/CommandLineTools/usr/bin/lldb", SOURCE)
        self.assertIn("/nix/var/nix/profiles/default/bin/nix", SOURCE)
        self.assertIn('--extra-experimental-features "nix-command flakes"', SOURCE)
        self.assertIn("native capture environment contains a Nix store path", SOURCE)
        self.assertNotIn("gh run", SOURCE)


if __name__ == "__main__":
    unittest.main()
