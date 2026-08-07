#!/usr/bin/env python3
"""Source contracts for the native public-render/provider runner."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "run_backdrop_margin_case22_provider_public_render_interval_transfer_local_macos_26_6_1.sh"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


class PublicRenderIntervalRunnerSourceTests(unittest.TestCase):
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

    def test_exact_binary_capture_preflight_and_validator_are_hashed(self) -> None:
        for digest in (
            "b9cb4068e77a61ff87794fa20a5c273e007f3ee20dd74503b1ab78839104e8dd",
            "9ef07e96861ba53e6189f7aafd5dd967cb3d00437ab634b72a3f81692e573639",
            "f12a1cbe29629dc843cc3250a46fa686225f3c08bcf1bf1dbdf50aea913926f1",
            "5c5ea02b5d47b0c57c36164303548c63ae961f32e846f8f76f7518ae78fb073d",
        ):
            self.assertIn(digest, SOURCE)
        self.assertNotIn("PLACEHOLDER", SOURCE)

    def test_preflight_precedes_lldb_and_validation_follows(self) -> None:
        preflight = SOURCE.index('"$swift" "$preflight"')
        lldb = SOURCE.index('"$lldb" -b')
        validation = SOURCE.index('"$python" "$validator"')
        self.assertLess(preflight, lldb)
        self.assertLess(lldb, validation)

    def test_runner_clears_environment_and_requires_clean_tracked_state(self) -> None:
        self.assertIn("git status --porcelain --untracked-files=no", SOURCE)
        self.assertIn("LG_*) unset", SOURCE)
        self.assertIn("capture-context.txt", SOURCE)
        self.assertIn("validation-exit-status.txt", SOURCE)


if __name__ == "__main__":
    unittest.main()
