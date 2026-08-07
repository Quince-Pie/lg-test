#!/usr/bin/env python3
"""Source contract for the direct-Retina DOD calibration executor."""

import unittest
from pathlib import Path


SOURCE = Path(__file__).with_name(
    "run_prepare_layer_live_dod_source_calibration_local_macos_26_6_1.sh"
).read_text(encoding="utf-8")


class PrepareLayerLiveDODSourceCalibrationRunnerTests(unittest.TestCase):
    def test_capture_and_analysis_paths_are_separated(self) -> None:
        for fragment in (
            "LG_GLASS_GEOMETRY=circle-485-center",
            "/Library/Developer/CommandLineTools/usr/bin/lldb",
            "/nix/var/nix/profiles/default/bin/nix",
            '"nix-command flakes"',
            "capture_prepare_layer_live_dod_source_bounds_local_macos_26_6_1_lldb",
            "validate_prepare_layer_live_dod_source_capture_local_macos_26_6_1.py",
        ):
            self.assertIn(fragment, SOURCE)
        self.assertNotIn("readonly nix=/nix/store/", SOURCE)
        self.assertNotIn("github", SOURCE.lower())

    def test_capture_is_fail_closed(self) -> None:
        self.assertIn("git status --porcelain --untracked-files=no", SOURCE)
        self.assertIn("require_sha256", SOURCE)
        self.assertIn("check_local_retina_capture_session_v2.swift", SOURCE)
        self.assertIn('if [[ -e "$output_directory" ]]', SOURCE)


if __name__ == "__main__":
    unittest.main()
