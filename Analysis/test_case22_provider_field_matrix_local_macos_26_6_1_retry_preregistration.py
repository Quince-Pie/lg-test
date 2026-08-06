#!/usr/bin/env python3
"""Integrity checks for the local provider field-matrix retry freeze."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
REPOSITORY = ANALYSIS.parent
PATH = (
    ANALYSIS
    / "case22_provider_field_matrix_local_macos_26_6_1_retry_preregistration.json"
)


class Case22ProviderFieldMatrixRetryPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PATH.read_text(encoding="utf-8"))

    def test_failed_attempt_is_exact_and_has_no_authority(self) -> None:
        failed = self.value["failedAttempt"]
        self.assertEqual(failed["intervalCount"], 0)
        self.assertEqual(failed["providerCallCount"], 0)
        self.assertEqual(failed["failureCount"], 46)
        self.assertFalse(failed["appleProviderObjectOrReturnCaptured"])
        self.assertFalse(failed["authority"])

    def test_retry_scope_cannot_change_the_matrix(self) -> None:
        retry = self.value["retryOverlay"]
        self.assertTrue(retry["baseCaptureImportedUnchanged"])
        for key, value in retry.items():
            if key.endswith("Changed"):
                self.assertFalse(value, key)
        self.assertIn("local SwiftUICore UUID", retry["onlyBehavioralChange"])

    def test_every_frozen_hash_matches(self) -> None:
        for item in self.value["frozenImplementation"]["files"]:
            self.assertEqual(
                hashlib.sha256((REPOSITORY / item["path"]).read_bytes()).hexdigest(),
                item["sha256"],
                item["path"],
            )

    def test_retry_outcome_and_product_claims_are_sealed(self) -> None:
        self.assertTrue(
            all(
                value is None
                for value in self.value["unknownBeforeRetryDispatch"].values()
            )
        )
        self.assertIsNone(self.value["runtimeOutcomeFrozenBeforeRetryDispatch"])
        authority = self.value["productAuthority"]
        allowed = {
            "exactFilterInputToProviderObjectEffectsMayBeDecodedOnPass",
            "observedProviderBranchEffectsMayBeDecodedOnPass",
        }
        for key, value in authority.items():
            self.assertIs(value, key in allowed, key)


if __name__ == "__main__":
    unittest.main()
