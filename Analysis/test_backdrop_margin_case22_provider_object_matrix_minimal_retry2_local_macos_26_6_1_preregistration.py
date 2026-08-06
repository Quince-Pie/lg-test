#!/usr/bin/env python3
"""Integrity checks for the bound-only minimal provider-matrix retry."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
REPOSITORY = ANALYSIS.parent
PATH = (
    ANALYSIS
    / "backdrop_margin_case22_provider_object_matrix_minimal_retry2_local_macos_26_6_1_preregistration.json"
)


class MinimalCase22ProviderObjectMatrixRetry2PreregistrationTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PATH.read_text(encoding="utf-8"))

    def test_prior_run_is_preserved_as_a_bound_failure(self) -> None:
        failed = self.value["failed512BoundRun"]
        self.assertEqual(failed["processExitStatus"], 0)
        self.assertEqual(failed["timelineSamplesLength"], 33)
        self.assertEqual(failed["timelineFailedSamples"], 0)
        self.assertEqual(failed["completedProviderCallCount"], 512)
        self.assertEqual(failed["failureCount"], 699)
        self.assertFalse(failed["captureContractPassed"])
        self.assertFalse(failed["matrixAuthority"])
        self.assertFalse(failed["productAuthority"])

    def test_retry_changes_only_the_finite_bound(self) -> None:
        retry = self.value["retry2Overlay"]
        self.assertTrue(retry["boundChangeOnly"])
        self.assertEqual(retry["previousMaximumCallCount"], 512)
        self.assertEqual(retry["maximumCallCount"], 4096)
        self.assertEqual(retry["boundMultiplier"], 8)
        for key, value in retry.items():
            if key.endswith("Changed"):
                self.assertFalse(value, key)
        self.assertFalse(
            retry["capturedObjectReturnMarginCropImageOrPixelUsedToSelectBound"]
        )

    def test_launch_transport_is_exact_and_observation_free(self) -> None:
        opening = self.value["launchTransportOpening"]
        self.assertEqual(opening["resolvedCallsiteBreakpointCount"], 1)
        self.assertEqual(opening["resolvedCallsiteFunctionOffset"], 5760)
        self.assertTrue(opening["callbackNamespaceDirect"])
        self.assertFalse(opening["capturedObjectOrReturnObserved"])
        self.assertFalse(opening["productAuthority"])

    def test_candidate_semantics_have_no_mapping_authority(self) -> None:
        candidate = self.value["retrospectiveCandidateSemanticsFromFailedRun"]
        self.assertEqual(len(candidate["equalBinary64Words"]), 4)
        self.assertFalse(candidate["authenticatedTemporalJoin"])
        self.assertFalse(candidate["publicInputMappingAuthority"])
        self.assertFalse(candidate["productAuthority"])

    def test_every_frozen_hash_matches(self) -> None:
        for item in self.value["frozenImplementation"]["files"]:
            self.assertEqual(
                hashlib.sha256((REPOSITORY / item["path"]).read_bytes()).hexdigest(),
                item["sha256"],
                item["path"],
            )

    def test_outcome_is_unknown_and_authority_stays_narrow(self) -> None:
        self.assertIsNone(self.value["runtimeOutcomeFrozenBeforeDispatch"])
        self.assertTrue(
            all(value is None for value in self.value["unknownBeforeDispatch"].values())
        )
        authority = self.value["authorityOnPass"]
        allowed = {
            "exactAllLiveCase22ProviderObjectsForThisOpenedAllocationProfile",
            "exactObjectOffsetAndReturnCovarianceForThisOpenedAllocationProfile",
        }
        for key, value in authority.items():
            self.assertIs(value, key in allowed, key)


if __name__ == "__main__":
    unittest.main()
