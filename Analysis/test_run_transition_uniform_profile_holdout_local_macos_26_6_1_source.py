#!/usr/bin/env python3
"""Static safety checks for the direct-Mac uniform holdout runner."""

import unittest
from pathlib import Path


RUNNER_PATH = Path(__file__).with_name(
    "run_transition_uniform_profile_holdout_local_macos_26_6_1.sh"
)


class TransitionUniformProfileHoldoutRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = RUNNER_PATH.read_text(encoding="utf-8")

    def test_uses_direct_process_without_debugger(self) -> None:
        self.assertNotIn("lldb", self.source.lower())
        self.assertNotIn("github", self.source.lower())
        self.assertIn("NATIVE_CAPTURE_DEBUGGER_USED=0", self.source)
        self.assertIn('"$repository/$binary" "$output_directory"', self.source)

    def test_enables_dense_dynamic_uniform_capture(self) -> None:
        for assignment in (
            "LG_TRANSITION_TIMELINE=1",
            "LG_TRANSITION_UNIFORMS=1",
            "LG_TRANSITION_ALLOCATION_ONLY=1",
            "LG_TRANSITION_ALLOCATION_DENSE=1",
            "LG_TRANSITION_CONTROLLED_BACKDROP=0",
        ):
            self.assertIn(assignment, self.source)

    def test_native_capture_precedes_nix_validation(self) -> None:
        native_offset = self.source.index('"$repository/$binary" "$output_directory"')
        nix_offset = self.source.index('"$nix" --extra-experimental-features')
        self.assertLess(native_offset, nix_offset)
        self.assertIn(
            "native capture environment contains a Nix store path", self.source
        )

    def test_all_four_unopened_profiles_are_allowlisted(self) -> None:
        for profile in (
            "clear:light:circle-454-center",
            "clear:dark:circle-462-center",
            "regular:light:circle-470-center",
            "regular:dark:circle-478-center",
        ):
            self.assertIn(profile, self.source)


if __name__ == "__main__":
    unittest.main()
