#!/usr/bin/env python3
"""Integrity checks for the provider-object matrix transport retry."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
REPOSITORY = ANALYSIS.parent
PATH = (
    ANALYSIS
    / "backdrop_margin_case22_provider_object_matrix_local_macos_26_6_1_retry_preregistration.json"
)


class Case22ProviderObjectMatrixRetryPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PATH.read_text(encoding="utf-8"))

    def test_failed_attempt_is_preserved_without_authority(self) -> None:
        failed = self.value["failedAttempt"]
        self.assertEqual(failed["processExitStatus"], 1)
        self.assertEqual(failed["providerCallCount"], 2)
        self.assertEqual(failed["providerGroupLinkedCallCount"], 2)
        self.assertEqual(failed["traceFailureCount"], 0)
        self.assertFalse(failed["completeTimelinePassed"])
        self.assertFalse(failed["matrixAuthority"])
        self.assertFalse(failed["productAuthority"])

    def test_retry_changes_only_the_explicit_transport_gate(self) -> None:
        retry = self.value["retryContract"]
        for key, value in retry.items():
            if key.endswith("Changed"):
                self.assertFalse(value, key)
        self.assertEqual(retry["requireProcessExitStatus"], 0)
        self.assertEqual(retry["requireTimelineSampleCount"], 33)
        self.assertEqual(retry["requireTimelineSamplesLength"], 33)
        self.assertEqual(retry["requireTimelineFailedSamples"], 0)
        self.assertTrue(retry["requireTimelineErrorAbsent"])
        self.assertTrue(retry["zeroTolerance"])

    def test_every_frozen_hash_matches(self) -> None:
        for item in self.value["frozenImplementation"]["files"]:
            self.assertEqual(
                hashlib.sha256((REPOSITORY / item["path"]).read_bytes()).hexdigest(),
                item["sha256"],
                item["path"],
            )

    def test_outcome_is_unknown_and_authority_stays_narrow(self) -> None:
        self.assertIsNone(self.value["runtimeOutcomeFrozenBeforeRetryDispatch"])
        self.assertTrue(
            all(
                value is None
                for value in self.value["unknownBeforeRetryDispatch"].values()
            )
        )
        authority = self.value["authorityOnPass"]
        allowed = {
            "exactAllLiveCase22ProviderObjectsForThisOpenedProfile",
            "exactObjectOffsetAndReturnCovarianceForThisOpenedProfile",
        }
        for key, value in authority.items():
            self.assertIs(value, key in allowed, key)


if __name__ == "__main__":
    unittest.main()
