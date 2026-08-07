#!/usr/bin/env python3
"""Source-contract tests for the direct-Retina live transport calibration."""

import unittest
from pathlib import Path


SOURCE = (
    Path(__file__).with_name(
        "run_prepare_layer_live_transport_calibration_local_macos_26_6_1.sh"
    )
).read_text(encoding="utf-8")


class PrepareLayerLiveTransportCalibrationSourceTests(unittest.TestCase):
    def test_native_capture_is_fixed_to_the_authorized_host_and_profile(self) -> None:
        for fragment in (
            "arm64",
            "26.6.1",
            "25G76",
            "check_local_retina_capture_session_v2.swift",
            "LG_GLASS_MATERIAL=regular",
            "LG_GLASS_APPEARANCE=dark",
            "LG_GLASS_GEOMETRY=circle-800-center",
            "LG_TRANSITION_DIRECTION=materialize",
        ):
            self.assertIn(fragment, SOURCE)

    def test_native_capture_uses_apple_tools_and_live_overlay(self) -> None:
        self.assertIn(
            "readonly lldb=/Library/Developer/CommandLineTools/usr/bin/lldb",
            SOURCE,
        )
        self.assertIn(
            "command script import $capture",
            SOURCE,
        )
        self.assertIn(
            "capture_prepare_layer_crop_policy_holdout_live_local_macos_26_6_1_lldb",
            SOURCE,
        )
        self.assertIn("b9cb4068e77a61ff", SOURCE)

    def test_analysis_uses_nix_profile_not_lldb_python(self) -> None:
        self.assertIn(
            "readonly nix=/nix/var/nix/profiles/default/bin/nix",
            SOURCE,
        )
        self.assertIn('develop --command python "$validator"', SOURCE)
        self.assertIn('"nix-command flakes"', SOURCE)
        self.assertNotIn("readonly nix=/nix/store/", SOURCE)
        self.assertNotIn(
            "/Library/Developer/CommandLineTools/usr/bin/python3",
            SOURCE,
        )

    def test_capture_fails_closed_on_mutable_or_reused_state(self) -> None:
        self.assertIn("git status --porcelain --untracked-files=no", SOURCE)
        self.assertIn('if [[ -e "$output_directory" ]]', SOURCE)
        self.assertIn("require_sha256", SOURCE)
        self.assertIn("native capture environment contains a Nix store path", SOURCE)


if __name__ == "__main__":
    unittest.main()
