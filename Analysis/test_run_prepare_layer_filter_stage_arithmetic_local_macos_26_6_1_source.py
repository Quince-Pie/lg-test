#!/usr/bin/env python3
"""Source contracts for the direct-M1 FilterOp/DOD stage capture runner."""

import unittest
from pathlib import Path


SOURCE_PATH = Path(__file__).with_name(
    "run_prepare_layer_filter_stage_arithmetic_local_macos_26_6_1.sh"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


class PrepareLayerFilterStageRunnerTests(unittest.TestCase):
    def test_native_capture_uses_apple_tools_and_no_nix_store_path(self) -> None:
        self.assertIn(
            "readonly swift=/Library/Developer/CommandLineTools/usr/bin/swift",
            SOURCE,
        )
        self.assertIn(
            "readonly lldb=/Library/Developer/CommandLineTools/usr/bin/lldb",
            SOURCE,
        )
        self.assertIn("native capture environment contains a Nix store path", SOURCE)
        self.assertNotIn("github", SOURCE.lower())

    def test_opened_geometry_and_capture_are_fixed(self) -> None:
        self.assertIn("LG_GLASS_GEOMETRY=circle-498-center", SOURCE)
        self.assertIn(
            "capture_prepare_layer_filter_stage_arithmetic_local_macos_26_6_1_lldb.py",
            SOURCE,
        )
        self.assertIn(
            "dc21160e6cebd4cd962005ab0d3b1ceb64da0dcafc1b2d4f74cda601f5278c89",
            SOURCE,
        )

    def test_capture_runs_only_from_clean_tracked_state(self) -> None:
        self.assertIn("git status --porcelain --untracked-files=no", SOURCE)
        self.assertIn("tracked repository state is dirty", SOURCE)


if __name__ == "__main__":
    unittest.main()
