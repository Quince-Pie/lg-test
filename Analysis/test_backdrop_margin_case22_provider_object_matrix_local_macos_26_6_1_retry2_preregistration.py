#!/usr/bin/env python3
"""Integrity checks for the binary-transport provider matrix retry."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
REPOSITORY = ANALYSIS.parent
PATH = (
    ANALYSIS
    / "backdrop_margin_case22_provider_object_matrix_local_macos_26_6_1_retry2_preregistration.json"
)


class Case22ProviderObjectMatrixRetry2PreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PATH.read_text(encoding="utf-8"))

    def test_failed_retry_is_preserved_without_authority(self) -> None:
        failed = self.value["failedRetry"]
        self.assertEqual(failed["processExitStatus"], 1)
        self.assertEqual(failed["providerCallCount"], 2)
        self.assertEqual(failed["providerGroupLinkedCallCount"], 2)
        self.assertEqual(failed["traceFailureCount"], 0)
        self.assertFalse(failed["completeTimelinePassed"])
        self.assertFalse(failed["matrixAuthority"])

    def test_binary_choice_is_transport_only(self) -> None:
        diagnostics = self.value["transportDiagnosticsOpenedBeforeFreeze"]
        current = diagnostics["currentBinaryWithoutLLDB"]
        selected = diagnostics["selectedOlderBinaryWithoutLLDB"]
        self.assertFalse(current["providerCaptureAttached"])
        self.assertFalse(selected["providerCaptureAttached"])
        self.assertFalse(selected["providerObjectOrReturnObserved"])
        self.assertTrue(selected["selectedOnlyByCompleteTransport"])
        self.assertEqual(selected["timelineSampleCount"], 33)
        self.assertEqual(selected["timelineSamplesLength"], 33)
        self.assertEqual(selected["timelineFailedSamples"], 0)
        self.assertEqual(selected["processExitStatus"], 0)

    def test_only_binary_transport_changes(self) -> None:
        retry = self.value["retryContract"]
        self.assertTrue(retry["binaryChanged"])
        self.assertFalse(retry["binarySelectionUsesProviderObjectOrReturn"])
        for key in (
            "captureImplementationChanged",
            "profileChanged",
            "environmentChanged",
            "selectionChanged",
            "captureBoundsChanged",
        ):
            self.assertFalse(retry[key], key)
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
