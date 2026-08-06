#!/usr/bin/env python3
"""Integrity checks for the provider-matrix authority correction."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
PATH = ANALYSIS / "backdrop_margin_case22_provider_object_matrix_domain_correction.json"
VALUE = json.loads(PATH.read_text(encoding="utf-8"))


class ProviderObjectMatrixDomainCorrectionTests(unittest.TestCase):
    def test_withdraws_only_unsupported_domain_authority(self) -> None:
        correction = VALUE["correction"]
        self.assertFalse(correction["completeProcessLifetimeSelectionEstablished"])
        self.assertFalse(
            correction["everyCase22IterationUntilSelectedCallerReturnEstablished"]
        )
        self.assertFalse(
            correction["exactAllLiveProviderObjectsForOpenedProfileEstablished"]
        )
        self.assertTrue(correction["exactObservedCallChainIntegrityEstablished"])

    def test_retains_exact_observed_counts_and_zero_words(self) -> None:
        evidence = VALUE["retainedExactEvidence"]
        self.assertEqual(evidence["allocationObservedCallCount"], 1228)
        self.assertEqual(evidence["normalObservedCallCount"], 1232)
        self.assertEqual(evidence["liveObservedCallCount"], 1222)
        self.assertEqual(evidence["allObservedReturnWords"], ["0000000000000000"])
        self.assertTrue(evidence["allObservedProviderReturnsJoinedToGroupBitwise"])
        self.assertFalse(evidence["productAuthority"])

    def test_records_exact_session_boundary_without_claiming_causation(self) -> None:
        confound = VALUE["presentationSessionConfound"]
        self.assertEqual(confound["sessionLockStartedUnix"], 1786050234)
        self.assertIn("not yet", confound["causalStatus"])

    def test_result_is_canonical_json(self) -> None:
        self.assertEqual(
            PATH.read_text(encoding="utf-8"),
            json.dumps(VALUE, indent=2, sort_keys=True) + "\n",
        )


if __name__ == "__main__":
    unittest.main()
