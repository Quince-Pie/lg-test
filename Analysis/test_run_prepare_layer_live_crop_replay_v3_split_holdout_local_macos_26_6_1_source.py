#!/usr/bin/env python3
"""Source contract for the direct-M1 split-criterion v3 crop executor."""

from pathlib import Path
import unittest


SOURCE = (
    Path(__file__)
    .with_name(
        "run_prepare_layer_live_crop_replay_v3_split_holdout_local_macos_26_6_1.sh"
    )
    .read_text(encoding="utf-8")
)


class RunPrepareLayerLiveCropReplayV3SplitHoldoutTests(unittest.TestCase):
    def test_unseen_profile_and_preregistration_are_fixed(self) -> None:
        for fragment in (
            "LG_GLASS_GEOMETRY=circle-497-center",
            "LG_GLASS_MATERIAL=regular",
            "LG_GLASS_APPEARANCE=dark",
            "LG_TRANSITION_DIRECTION=materialize",
            '--preregistration "$preregistration"',
            "2b7958c6586c1c774b452204fdb31a1aaaa99e8905cab5e6ef1a188b3dc43510",
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
