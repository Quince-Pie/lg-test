#!/usr/bin/env python3
"""Integrity checks for the local all-call provider-object freeze."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
REPOSITORY = ANALYSIS.parent
PATH = (
    ANALYSIS
    / "backdrop_margin_case22_provider_object_matrix_local_macos_26_6_1_preregistration.json"
)


class Case22ProviderObjectMatrixPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PATH.read_text(encoding="utf-8"))

    def test_runtime_outcome_is_fully_unknown(self) -> None:
        self.assertIsNone(self.value["runtimeOutcomeFrozenBeforeDispatch"])
        self.assertTrue(
            all(value is None for value in self.value["unknownBeforeDispatch"].values())
        )

    def test_contract_is_output_blind_and_zero_tolerance(self) -> None:
        contract = self.value["captureContract"]
        for key, value in contract.items():
            if key.startswith("captured") and key.endswith("UsedForRuntimeSelection"):
                self.assertFalse(value, key)
        self.assertTrue(contract["zeroTolerance"])
        self.assertTrue(contract["requireProviderReturnEqualsGroupReturnBitwise"])
        self.assertTrue(contract["requireEverySelectedCase22CallToEnterAndReturn"])

    def test_every_frozen_hash_matches(self) -> None:
        for item in self.value["frozenImplementation"]["files"]:
            self.assertEqual(
                hashlib.sha256((REPOSITORY / item["path"]).read_bytes()).hexdigest(),
                item["sha256"],
                item["path"],
            )

    def test_authority_remains_narrow(self) -> None:
        authority = self.value["authorityOnPass"]
        allowed = {
            "exactAllLiveCase22ProviderObjectsForThisOpenedProfile",
            "exactObjectOffsetAndReturnCovarianceForThisOpenedProfile",
        }
        for key, value in authority.items():
            self.assertIs(value, key in allowed, key)


if __name__ == "__main__":
    unittest.main()
