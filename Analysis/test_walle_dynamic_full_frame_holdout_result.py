#!/usr/bin/env python3
"""Validate the accepted prospective Walle full-frame result."""

import hashlib
import json
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    REPOSITORY / "Analysis/walle_dynamic_full_frame_holdout_preregistration.json"
)
RESULT = REPOSITORY / "Analysis/walle_dynamic_full_frame_holdout_c0e4ae9_result.json"
SAMPLES = (1, 4, 8, 12, 16, 20, 24, 28)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WalleDynamicFullFrameHoldoutResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_result_is_bound_to_the_frozen_preregistration(self) -> None:
        preregistration = self.result["preregistration"]
        self.assertTrue(preregistration["frozenBeforeCapture"])
        self.assertEqual(preregistration["sha256"], sha256_file(PREREGISTRATION))
        self.assertEqual(
            self.result["status"],
            "accepted-prospective-eight-state-full-frame-exact",
        )

    def test_all_eight_frames_are_bit_identical(self) -> None:
        self.assertEqual(
            tuple(case["sampleIndex"] for case in self.result["cases"]),
            SAMPLES,
        )
        for case in self.result["cases"]:
            with self.subTest(sample=case["sampleIndex"]):
                self.assertEqual(case["referenceSHA256"], case["candidateSHA256"])
        totals = self.result["totals"]
        self.assertEqual(totals["checkedBytes"], 33_554_432)
        self.assertEqual(totals["mismatchedBytes"], 0)
        self.assertEqual(totals["mismatchedPixels"], 0)
        self.assertEqual(totals["maximumChannelDelta"], 0)
        self.assertEqual(totals["tolerance"], 0)

    def test_holdout_exercised_both_emitted_topologies(self) -> None:
        self.assertEqual(self.result["totals"]["sixIndexTopologyCount"], 7)
        self.assertEqual(self.result["totals"]["twentyFourIndexTopologyCount"], 1)
        self.assertEqual(
            {
                (case["highlightVertexCount"], case["highlightIndexCount"])
                for case in self.result["cases"]
            },
            {(4, 6), (16, 24)},
        )

    def test_provenance_is_native_retina_without_github_or_nix(self) -> None:
        capture = self.result["capture"]
        self.assertTrue(capture["nativeRetina"])
        self.assertFalse(capture["githubActionsUsed"])
        self.assertFalse(capture["nativeCaptureDebuggerUsed"])
        self.assertFalse(capture["nixStorePathInNativeBuildOrCapture"])
        self.assertEqual(capture["failedSamples"], 0)

    def test_result_does_not_overclaim_universal_or_product_parity(self) -> None:
        claims = self.result["claims"]
        self.assertTrue(claims["prospectiveEightStateFullFrameExact"])
        self.assertTrue(claims["frozenNaturalTrajectoryPromoted"])
        self.assertFalse(claims["universalTopologySelectorEstablished"])
        self.assertFalse(claims["productionWalleProcessParityEstablished"])
        self.assertFalse(claims["physicalRetinaWalleOutputParityEstablished"])
        self.assertFalse(claims["qualityRegression"])
        self.assertEqual(
            self.result["candidate"]["protectedProductionShaderSHA256"],
            "6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d",
        )


if __name__ == "__main__":
    unittest.main()
