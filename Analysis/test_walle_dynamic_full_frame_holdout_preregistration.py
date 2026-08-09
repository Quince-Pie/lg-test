#!/usr/bin/env python3
"""Contract tests for the prospective Walle full-frame holdout."""

import hashlib
import json
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    REPOSITORY / "Analysis/walle_dynamic_full_frame_holdout_preregistration.json"
)
RUNNER = (
    REPOSITORY / "Analysis/run_walle_dynamic_full_frame_holdout_local_macos_26_6_1.sh"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WalleDynamicFullFrameHoldoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_preregistration_is_frozen_before_capture(self) -> None:
        self.assertEqual(self.preregistration["schemaVersion"], 1)
        self.assertEqual(self.preregistration["status"], "frozen-before-first-capture")
        self.assertIsNone(self.preregistration["result"])
        self.assertEqual(
            self.preregistration["case"]["sampleIndices"],
            [1, 4, 8, 12, 16, 20, 24, 28],
        )

    def test_native_capture_sources_match_frozen_hashes(self) -> None:
        for relative, expected in self.preregistration[
            "frozenCaptureSourceSHA256"
        ].items():
            with self.subTest(relative=relative):
                self.assertEqual(sha256_file(REPOSITORY / relative), expected)

    def test_acceptance_is_bitwise_and_forbids_quality_regression(self) -> None:
        acceptance = self.preregistration["acceptance"]
        self.assertEqual(acceptance["caseCount"], 8)
        self.assertEqual(acceptance["totalComparedBytes"], 33_554_432)
        self.assertEqual(acceptance["requiredMismatchedBytes"], 0)
        self.assertEqual(acceptance["requiredMismatchedPixels"], 0)
        self.assertEqual(acceptance["requiredMaximumChannelDelta"], 0)
        self.assertEqual(acceptance["tolerance"], 0)
        self.assertFalse(acceptance["algorithmFittingAfterCapturePermitted"])
        self.assertFalse(acceptance["qualityRegressionPermitted"])
        self.assertFalse(acceptance["protectedProductionShaderMutationPermitted"])

    def test_runner_pins_preregistration_and_uses_native_tools(self) -> None:
        self.assertIn(
            f'require_sha256 "$preregistration" {sha256_file(PREREGISTRATION)}',
            self.runner,
        )
        self.assertIn(
            "readonly swiftc=/Library/Developer/CommandLineTools/usr/bin/swiftc",
            self.runner,
        )
        self.assertIn("readonly clang=/usr/bin/xcrun", self.runner)
        self.assertNotIn("nix develop", self.runner)
        self.assertNotIn("/nix/var/", self.runner)
        self.assertIn(
            "native build/capture environment contains a Nix store path",
            self.runner,
        )

    def test_runner_environment_is_the_preregistered_environment(self) -> None:
        for key, value in self.preregistration["captureEnvironment"].items():
            with self.subTest(key=key):
                self.assertIn(f"{key}={value}", self.runner)

    def test_claim_boundary_keeps_selector_and_production_open(self) -> None:
        excluded = self.preregistration["claimBoundary"]["successfulGateDoesNotPromote"]
        self.assertTrue(any("topology selector" in claim for claim in excluded))
        self.assertTrue(any("production Walle" in claim for claim in excluded))


if __name__ == "__main__":
    unittest.main()
