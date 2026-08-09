#!/usr/bin/env python3
"""Contracts for the prospective sample-28 arithmetic holdout."""

import hashlib
import json
from pathlib import Path
import unittest


ANALYSIS = Path(__file__).resolve().parent
RESULT_PATH = ANALYSIS / (
    "natural_sample28_border_highlight_arithmetic_holdout_result.json"
)
PREREGISTRATION_PATH = ANALYSIS / (
    "natural_sample28_border_highlight_arithmetic_preregistration.json"
)
EXPECTED_RESULT_SHA256 = (
    "732663167e7307d70b3620fa69d3afdfc04dfe7ee7868f0e983bb9b6f4bde7d1"
)


class Sample28BorderHighlightArithmeticHoldoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_compact_result_is_immutable(self) -> None:
        self.assertEqual(
            hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest(),
            EXPECTED_RESULT_SHA256,
        )

    def test_capture_used_the_output_blind_preregistration(self) -> None:
        capture = self.result["capture"]
        self.assertEqual(
            capture["arithmeticPreregistrationSha256"],
            hashlib.sha256(PREREGISTRATION_PATH.read_bytes()).hexdigest(),
        )
        self.assertTrue(self.result["inputs"]["candidateFrozenBeforeAppleOutput"])
        self.assertEqual(capture["holdoutCaseCount"], 4)
        self.assertEqual(capture["diagnosticPipelineCountPerCase"], 9)
        self.assertEqual(capture["diagnosticReplayCount"], 36)
        self.assertEqual(
            capture["capturedPrivateVsCurrentSystemMismatchedBytes"], 0
        )
        correction = capture["commitLabelCorrection"]
        self.assertNotEqual(correction["recorded"], correction["correct"])
        self.assertTrue(correction["sourceBlobHashesMatchCorrectCommit"])
        self.assertFalse(correction["renderedEvidenceModified"])

    def test_candidate_is_exact_and_old_rule_is_nonvacuous(self) -> None:
        control = self.result["positiveControl"]
        self.assertTrue(control["passed"])
        self.assertEqual(control["caseCount"], 4)
        self.assertEqual(control["exactCaseCount"], 0)
        self.assertEqual(control["mismatchedWords"], 483_328)
        candidate = self.result["candidate"]
        self.assertEqual(candidate["stageCaseCount"], 152)
        self.assertEqual(candidate["checkedStageWords"], 159_383_552)
        self.assertEqual(candidate["checkedSdfWords"], 12_582_912)
        self.assertEqual(candidate["checkedAlphaHalfWords"], 4_194_304)
        self.assertEqual(candidate["totalCheckedWords"], 176_160_768)
        self.assertEqual(candidate["totalMismatchedWords"], 0)
        self.assertEqual(candidate["maximumBitDistance"], 0)

    def test_promotion_is_guarded_and_does_not_claim_product_parity(self) -> None:
        gate = self.result["gate"]
        self.assertTrue(gate["prospectiveHoldoutExact"])
        self.assertTrue(gate["calibrationPromoted"])
        self.assertTrue(gate["safeForGuardedWalleIntegration"])
        self.assertTrue(gate["eightStateAmdFrameGateRequired"])
        self.assertTrue(gate["generalTopologySelectorRequired"])
        self.assertEqual(gate["remainingAlgorithmFamilyUnknowns"], 1)
        self.assertFalse(gate["productionWalleParityEstablished"])
        self.assertFalse(gate["productionShaderModified"])
        self.assertFalse(gate["shaderQualityReductionAllowed"])


if __name__ == "__main__":
    unittest.main()
