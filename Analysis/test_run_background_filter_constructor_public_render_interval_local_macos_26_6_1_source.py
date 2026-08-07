#!/usr/bin/env python3
"""Source contracts for the native constructor/public-render runner."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "run_background_filter_constructor_public_render_interval_local_macos_26_6_1.sh"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


class BackgroundFilterConstructorRunnerSourceTests(unittest.TestCase):
    def test_bash_source_is_valid_and_executable(self) -> None:
        self.assertTrue(SOURCE_PATH.stat().st_mode & 0o111)
        subprocess.run(["bash", "-n", str(SOURCE_PATH)], check=True)

    def test_native_capture_contains_no_nix_store_path(self) -> None:
        self.assertNotIn("/nix/store", SOURCE)
        for path in (
            "/Library/Developer/CommandLineTools/usr/bin/swift",
            "/Library/Developer/CommandLineTools/usr/bin/lldb",
            "/Library/Developer/CommandLineTools/usr/bin/python3",
        ):
            self.assertIn(path, SOURCE)

    def test_predecessor_must_validate_before_preflight_or_app_launch(self) -> None:
        predecessor = SOURCE.index('"$python" "$predecessor_validator"')
        preflight = SOURCE.index('"$swift" "$preflight"')
        lldb = SOURCE.index('"$lldb" -b')
        self.assertLess(predecessor, preflight)
        self.assertLess(preflight, lldb)
        self.assertIn(
            "local-case22-provider-public-render-interval-d18aca7-run1",
            SOURCE,
        )

    def test_exact_sources_are_hashed_without_placeholders(self) -> None:
        for digest in (
            "b9cb4068e77a61ff87794fa20a5c273e007f3ee20dd74503b1ab78839104e8dd",
            "38d8829faf92397dfd85e631ac2336ab3c4d702f03a1e7eb7d5cbd221d279c6c",
            "f12a1cbe29629dc843cc3250a46fa686225f3c08bcf1bf1dbdf50aea913926f1",
            "bf24f979bc6edfa9e8ed8b2fbcf4b7ec88bf3e90249e2fd4ece87883e787ea0c",
            "1f7ff6bd50b67404dcc86db4e73990b7247bdc52198c16923034764eef18781d",
        ):
            self.assertIn(digest, SOURCE)
        self.assertNotIn("PLACEHOLDER", SOURCE)

    def test_runner_clears_environment_and_requires_clean_tracked_state(self) -> None:
        self.assertIn("git status --porcelain --untracked-files=no", SOURCE)
        self.assertIn("LG_*) unset", SOURCE)
        self.assertIn("capture-context.txt", SOURCE)
        self.assertIn("validation-exit-status.txt", SOURCE)


if __name__ == "__main__":
    unittest.main()
