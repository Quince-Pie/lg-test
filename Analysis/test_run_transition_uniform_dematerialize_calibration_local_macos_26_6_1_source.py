#!/usr/bin/env python3
"""Source contracts for the direct dematerialize-uniform calibration launcher."""

import unittest
from pathlib import Path


SOURCE = (
    Path(__file__)
    .with_name("run_transition_uniform_dematerialize_calibration_local_macos_26_6_1.sh")
    .read_text(encoding="utf-8")
)


class DematerializeUniformCalibrationRunnerTests(unittest.TestCase):
    def test_profile_matrix_and_direction_are_fixed(self) -> None:
        self.assertIn("readonly direction=dematerialize", SOURCE)
        for identity in (
            "clear:light:circle-453-center",
            "clear:dark:circle-461-center",
            "regular:light:circle-469-center",
            "regular:dark:circle-477-center",
        ):
            self.assertIn(identity, SOURCE)

    def test_dematerialize_capable_binary_retina_and_clean_tree_are_required(
        self,
    ) -> None:
        self.assertIn(
            "6711ec851453405e2c19a1f731465f1f40b1db1b05f1bd5cd3835a3974cc351d",
            SOURCE,
        )
        self.assertIn("glass-transition-introspect-9b5c502", SOURCE)
        self.assertIn("check_local_retina_capture_session_v2.swift", SOURCE)
        self.assertIn("git status --porcelain --untracked-files=no", SOURCE)
        self.assertIn("native capture environment contains a Nix store path", SOURCE)

    def test_dense_uniform_capture_is_native_and_observer_independent(self) -> None:
        for setting in (
            "LG_TRANSITION_ALLOCATION_DENSE=1",
            "LG_TRANSITION_ALLOCATION_ONLY=1",
            'LG_TRANSITION_DIRECTION="$direction"',
            "LG_TRANSITION_TIMELINE=1",
            "LG_TRANSITION_UNIFORMS=1",
            "NATIVE_CAPTURE_DEBUGGER_USED=0",
            "GITHUB_ACTIONS_USED=0",
        ):
            self.assertIn(setting, SOURCE)


if __name__ == "__main__":
    unittest.main()
