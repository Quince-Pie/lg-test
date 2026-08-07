"""Static safety checks for the direct-M1 clear-removal wrapper."""

from __future__ import annotations

import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parent
    / "run_backdrop_margin_writer_clear_presentation_removal_local_macos_26_6_1.sh"
)


class BackdropMarginWriterClearPresentationRemovalRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_native_debug_uses_only_apple_command_line_tools(self) -> None:
        for tool in ("swift", "lldb", "python3"):
            self.assertIn(
                f"/Library/Developer/CommandLineTools/usr/bin/{tool}", self.source
            )
        self.assertNotIn("/nix/store", self.source)
        self.assertNotIn("github", self.source.lower())
        self.assertIn("glass-transition-introspect-721293f", self.source)
        self.assertIn(
            "b9cb4068e77a61ff87794fa20a5c273e007f3ee20dd74503b1ab78839104e8dd",
            self.source,
        )

    def test_only_the_two_frozen_clear_profiles_are_accepted(self) -> None:
        self.assertIn("clear:light:circle-451-center", self.source)
        self.assertIn("clear:dark:circle-459-center", self.source)
        self.assertNotIn("regular:light", self.source)
        self.assertNotIn("regular:dark", self.source)

    def test_retina_preflight_precedes_native_launch(self) -> None:
        self.assertLess(
            self.source.index('"$swift" "$preflight"'),
            self.source.index('"$lldb" --batch'),
        )
        self.assertIn("LG_BACKDROP_MARGIN_WRITER_TRACE_OUTPUT", self.source)


if __name__ == "__main__":
    unittest.main()
