#!/usr/bin/env python3
"""Source contracts for the direct-M1 constructor-return join shell script."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "run_background_filter_constructor_timeline_marker_return_join_local_macos_26_6_1.sh"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


class ConstructorReturnRunnerSourceTests(unittest.TestCase):
    def test_bash_source_is_valid_and_executable(self) -> None:
        self.assertTrue(SOURCE_PATH.stat().st_mode & 0o111)
        subprocess.run(["bash", "-n", str(SOURCE_PATH)], check=True)

    def test_native_capture_has_no_nix_store_or_github_path(self) -> None:
        self.assertNotIn("/nix/store", SOURCE)
        self.assertNotIn("gh run", SOURCE)
        self.assertNotIn("actions/", SOURCE)
        for path in (
            "/Library/Developer/CommandLineTools/usr/bin/swift",
            "/Library/Developer/CommandLineTools/usr/bin/lldb",
            "/Library/Developer/CommandLineTools/usr/bin/python3",
        ):
            self.assertIn(path, SOURCE)

    def test_preflight_and_exact_main_precede_import(self) -> None:
        self.assertLess(SOURCE.index('"$swift" "$preflight"'), SOURCE.index('"$lldb" -b'))
        main = SOURCE.index("breakpoint set --shlib $binary --name main")
        run = SOURCE.index("-o run", main)
        imported = SOURCE.index("command script import $capture", run)
        continued = SOURCE.index("-o continue", imported)
        self.assertLess(main, run)
        self.assertLess(run, imported)
        self.assertLess(imported, continued)

    def test_hash_placeholders_are_resolved_before_freeze(self) -> None:
        self.assertNotIn("PLACEHOLDER", SOURCE)


if __name__ == "__main__":
    unittest.main()
