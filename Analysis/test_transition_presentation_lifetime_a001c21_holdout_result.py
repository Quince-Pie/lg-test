#!/usr/bin/env python3
"""Tests for the prospective presentation-lifetime matrix result."""

import json
from pathlib import Path
import unittest


RESULT = Path(__file__).with_name(
    "transition_presentation_lifetime_a001c21_holdout_result.json"
)
CAPTURE_COMMIT = "a001c211e77bd64af0ee853dc13c8c5c2b3647d5"
EXPECTED_IDENTITIES = {
    ("clear", "light", "materialize", "circle-452-center"),
    ("clear", "light", "dematerialize", "circle-453-center"),
    ("clear", "dark", "materialize", "circle-460-center"),
    ("clear", "dark", "dematerialize", "circle-461-center"),
    ("regular", "light", "materialize", "circle-468-center"),
    ("regular", "light", "dematerialize", "circle-469-center"),
    ("regular", "dark", "materialize", "circle-476-center"),
    ("regular", "dark", "dematerialize", "circle-477-center"),
}


class TransitionPresentationLifetimeHoldoutResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_result_has_prospective_matrix_authority(self) -> None:
        self.assertEqual(self.result["status"], "passed")
        self.assertEqual(self.result["authority"], "prospective-holdout-matrix")
        self.assertEqual(self.result["captureCommit"], CAPTURE_COMMIT)
        self.assertEqual(self.result["caseCount"], 8)

    def test_all_frozen_cases_have_independent_evidence(self) -> None:
        cases = self.result["cases"]
        identities = {
            (
                case["profile"]["material"],
                case["profile"]["appearance"],
                case["profile"]["direction"],
                case["profile"]["geometry"],
            )
            for case in cases
        }
        self.assertEqual(identities, EXPECTED_IDENTITIES)
        self.assertTrue(all(case["captureCommit"] == CAPTURE_COMMIT for case in cases))
        for digest_field in ("timelineSHA256", "validationSHA256", "pngTreeSHA256"):
            digests = {case[digest_field] for case in cases}
            self.assertEqual(len(digests), 8)
            self.assertTrue(all(len(digest) == 64 for digest in digests))

    def test_matrix_totals_are_exact(self) -> None:
        totals = self.result["matrixTotals"]
        self.assertEqual(totals["windowServerFrameCount"], 264)
        self.assertEqual(totals["presentationStateCount"], 528)
        self.assertEqual(totals["glassBackgroundPresenceCount"], 512)
        self.assertEqual(totals["glassForegroundPresenceCount"], 496)
        self.assertLess(totals["maximumStateBracketSeconds"], 0.1)
        self.assertLess(totals["maximumWindowCaptureSeconds"], 0.1)
        self.assertLess(totals["maximumAbsoluteRequestedProgressError"], 0.01)

    def test_conclusion_closes_only_presentation_lifetime(self) -> None:
        conclusion = self.result["sealedConclusion"]
        self.assertTrue(
            conclusion["observerIndependentPresentationLifetimeTransferPassed"]
        )
        self.assertTrue(conclusion["appearanceDependentPresentationRemovalLawRejected"])
        self.assertTrue(
            conclusion["historicalCombinedSnapshotFailureWasNotProductRemovalProof"]
        )
        self.assertTrue(
            conclusion["presentationLifetimeGateClosedForFrozenProfileMatrix"]
        )
        self.assertFalse(
            conclusion["capturedInputOpticalTemporalMeshSourceMipColorTransferPassed"]
        )
        self.assertFalse(conclusion["physicalRetinaOutputTransferPassed"])
        self.assertFalse(conclusion["independentWalleZeroByteParityPassed"])
        self.assertFalse(conclusion["liquidGlassParityEstablished"])
        self.assertFalse(conclusion["productionShaderChanged"])


if __name__ == "__main__":
    unittest.main()
