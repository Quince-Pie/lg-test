#!/usr/bin/env python3
"""Source-contract tests for the small-clear final color runner."""

import hashlib
import json
from pathlib import Path
import unittest


ANALYSIS = Path(__file__).resolve().parent
REPOSITORY = ANALYSIS.parent
RUNNER = ANALYSIS / "run_small_clear_final_color_intervention_local_macos_26_6_1.sh"
PREREGISTRATION = ANALYSIS / "small_clear_final_color_intervention_preregistration.json"
AMENDMENT = ANALYSIS / "small_clear_final_color_intervention_transport_amendment.json"
QUAD_FALLBACK_AMENDMENT = (
    ANALYSIS / "small_clear_final_color_intervention_quad_fallback_amendment.json"
)


class SmallClearFinalColorRunnerSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = RUNNER.read_text(encoding="utf-8")
        self.preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
        self.amendment = json.loads(AMENDMENT.read_text(encoding="utf-8"))
        self.quad_fallback_amendment = json.loads(
            QUAD_FALLBACK_AMENDMENT.read_text(encoding="utf-8")
        )

    def test_runner_uses_the_frozen_native_case(self) -> None:
        for assignment in (
            "LG_GLASS_APPEARANCE=light",
            "LG_GLASS_GEOMETRY=circle-047-center",
            "LG_GLASS_MATERIAL=clear",
            "LG_TRANSITION_DIRECTION=materialize",
            "LG_TRANSITION_SMALL_CLEAR_FINAL_COLOR_TRACE=1",
            "LG_TRANSITION_HIGHLIGHT_VERTEX_TAIL_TRACE=0",
            "LG_TRANSITION_FINAL_SOURCE_TRACE=0",
        ):
            self.assertIn(assignment, self.source)
        self.assertNotIn("MTL_CAPTURE_ENABLED", self.source)
        self.assertIn("GITHUB_ACTIONS_USED=0", self.source)

    def test_runner_pins_every_compiled_input_and_the_preregistration(self) -> None:
        for relative, digest in self.quad_fallback_amendment["sourceSHA256"].items():
            self.assertEqual(
                hashlib.sha256((REPOSITORY / relative).read_bytes()).hexdigest(),
                digest,
            )
            self.assertIn(digest, self.source)
        preregistration_digest = hashlib.sha256(
            PREREGISTRATION.read_bytes()
        ).hexdigest()
        self.assertIn(preregistration_digest, self.source)
        amendment_digest = hashlib.sha256(AMENDMENT.read_bytes()).hexdigest()
        self.assertIn(amendment_digest, self.source)
        quad_fallback_digest = hashlib.sha256(
            QUAD_FALLBACK_AMENDMENT.read_bytes()
        ).hexdigest()
        self.assertIn(quad_fallback_digest, self.source)
        self.assertIn('--transport-amendment "$transport_amendment"', self.source)
        self.assertIn(
            '--quad-fallback-amendment "$quad_fallback_amendment"',
            self.source,
        )

    def test_nix_is_only_used_after_native_capture_for_validation(self) -> None:
        native_launch = self.source.index(
            '"$build_directory/glassintrospect" "$output_directory"'
        )
        validation = self.source.index('develop --command python "$validator"')
        self.assertLess(native_launch, validation)
        self.assertIn("native probe contains a Nix store path", self.source)


if __name__ == "__main__":
    unittest.main()
