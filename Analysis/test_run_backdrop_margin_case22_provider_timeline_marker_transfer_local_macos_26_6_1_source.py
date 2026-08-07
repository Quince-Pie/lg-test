#!/usr/bin/env python3
"""Source contracts for the native timeline-marker/provider runner."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "run_backdrop_margin_case22_provider_timeline_marker_transfer_local_macos_26_6_1.sh"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


class TimelineMarkerRunnerSourceTests(unittest.TestCase):
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

    def test_preflight_precedes_lldb(self) -> None:
        self.assertLess(
            SOURCE.index('"$swift" "$preflight"'), SOURCE.index('"$lldb" -b')
        )
        self.assertIn("git status --porcelain --untracked-files=no", SOURCE)
        self.assertIn("LG_*) unset", SOURCE)

    def test_exact_sources_are_hashed(self) -> None:
        for digest in (
            "b9cb4068e77a61ff87794fa20a5c273e007f3ee20dd74503b1ab78839104e8dd",
            "145cf4d04650769f150f865e32f90671f9ab7f3d536d907e970b9f01bf690a59",
            "f12a1cbe29629dc843cc3250a46fa686225f3c08bcf1bf1dbdf50aea913926f1",
            "3672f7a53ad50500fe97e20d60316be6caf83aa73ac278669abcefb95aa84512",
        ):
            self.assertIn(digest, SOURCE)
        self.assertNotIn("PLACEHOLDER", SOURCE)

    def test_validation_runs_only_after_capture(self) -> None:
        self.assertLess(SOURCE.index("-o run"), SOURCE.index('"$python" "$validator"'))
        self.assertIn("validation-exit-status.txt", SOURCE)

    def test_capture_imports_at_exact_main_stop_after_dyld_load(self) -> None:
        main_breakpoint = SOURCE.index("breakpoint set --shlib $binary --name main")
        first_run = SOURCE.index("-o run", main_breakpoint)
        capture_import = SOURCE.index("command script import $capture", first_run)
        continuation = SOURCE.index("-o continue", capture_import)
        self.assertLess(main_breakpoint, first_run)
        self.assertLess(first_run, capture_import)
        self.assertLess(capture_import, continuation)


if __name__ == "__main__":
    unittest.main()
