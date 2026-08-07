#!/usr/bin/env python3
"""Source contract for the direct-Retina lifetime executor."""

from pathlib import Path
import unittest


SOURCE = (
    Path(__file__)
    .with_name("run_transition_presentation_lifetime_holdout_local_macos_26_6_1.sh")
    .read_text(encoding="utf-8")
)


class TransitionPresentationLifetimeRunnerSourceTests(unittest.TestCase):
    def test_native_capture_has_no_debugger_or_nix_store_tool(self) -> None:
        self.assertNotIn("lldb", SOURCE.lower())
        self.assertIn("NATIVE_CAPTURE_DEBUGGER_USED=0", SOURCE)
        self.assertIn("LG_TRANSITION_UNIFORMS=0", SOURCE)
        self.assertIn("native capture environment contains a Nix store path", SOURCE)
        self.assertLess(
            SOURCE.index('"$repository/$binary"'),
            SOURCE.index('"$nix" --extra-experimental-features'),
        )

    def test_runner_pins_the_frozen_contract(self) -> None:
        for digest in (
            "b9cb4068e77a61ff87794fa20a5c273e007f3ee20dd74503b1ab78839104e8dd",
            "d980712c71f7d2c9cf2cd72fc773c6c9e3900efca87b01e8dfd4991d5edb2881",
            "4fe4c55fa02582c4c1b5b76f08a05415d1dca8a8c16fd9208d4619eecc373f55",
            "f12a1cbe29629dc843cc3250a46fa686225f3c08bcf1bf1dbdf50aea913926f1",
        ):
            self.assertIn(digest, SOURCE)
        self.assertEqual(SOURCE.count("prospective-holdout"), 0)

    def test_all_eight_cases_are_explicit(self) -> None:
        for geometry in (452, 453, 460, 461, 468, 469, 476, 477):
            self.assertIn(f"circle-{geometry}-center", SOURCE)


if __name__ == "__main__":
    unittest.main()
