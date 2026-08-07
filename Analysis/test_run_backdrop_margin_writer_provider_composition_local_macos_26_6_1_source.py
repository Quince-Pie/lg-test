"""Static safety checks for the direct physical-M1 capture wrapper."""

from __future__ import annotations

import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parent
    / "run_backdrop_margin_writer_provider_composition_local_macos_26_6_1.sh"
)


class BackdropMarginWriterProviderCompositionRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_native_build_and_debug_use_apple_command_line_tools(self) -> None:
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
        self.assertNotIn('readonly clang=', self.source)
        self.assertNotIn('readonly swiftc=', self.source)

    def test_only_four_frozen_profiles_are_accepted(self) -> None:
        for identity in (
            "clear:light:circle-451-center",
            "clear:dark:circle-459-center",
            "regular:light:circle-467-center",
            "regular:dark:circle-475-center",
        ):
            self.assertIn(identity, self.source)

    def test_retina_preflight_precedes_native_launch(self) -> None:
        preflight = self.source.index('"$swift" "$preflight"')
        launch = self.source.index('"$lldb" --batch')
        self.assertLess(preflight, launch)
        self.assertIn("LG_BACKDROP_MARGIN_WRITER_TRACE_OUTPUT", self.source)


if __name__ == "__main__":
    unittest.main()
