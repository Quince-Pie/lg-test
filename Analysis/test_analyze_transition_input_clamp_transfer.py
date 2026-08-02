#!/usr/bin/env python3
"""Tests for the frozen inputClamp transfer analyzer."""

import unittest

import analyze_transition_input_clamp_transfer as transfer
import validate_transition_input_clamp_probe as clamp


class InputClampTransferAnalyzerTests(unittest.TestCase):
    def test_contract_accepts_only_unique_recovered_candidate(self) -> None:
        result = {
            "transitionInputClampProbeResultSchemaVersion": 1,
            "classification": clamp.CLASSIFICATION,
            "probeSchemaVersion": 2,
            "aggregate": {
                "sampleCount": 32,
                "candidateCount": 28,
                "recoveredTransferCandidate": clamp.RECOVERED_TRANSFER_CANDIDATE,
                "recoveredTransferCandidateExact": True,
                "exactEveryStateCandidateNames": [
                    clamp.RECOVERED_TRANSFER_CANDIDATE
                ],
            },
            "conclusion": {
                "captureIntegrityPassed": True,
                "affineExpandedTransferPassed": True,
                "productionShaderAuthorized": False,
            },
        }
        transfer.validate_result(result)
        result["aggregate"]["exactEveryStateCandidateNames"] = []
        with self.assertRaisesRegex(ValueError, "differs"):
            transfer.validate_result(result)

    def test_classification_denies_rendering_transfer(self) -> None:
        self.assertIn("not-an-unseen-rendering", transfer.CLASSIFICATION)


if __name__ == "__main__":
    unittest.main()
