#!/usr/bin/env python3
"""Integrity checks for the local provider field-matrix preregistration."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
REPOSITORY = ANALYSIS.parent
PREREGISTRATION = (
    ANALYSIS / "case22_provider_field_matrix_local_macos_26_6_1_preregistration.json"
)


class Case22ProviderFieldMatrixPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    def test_profile_binary_and_symbol_identity_are_exact(self) -> None:
        self.assertEqual(
            self.value[
                "case22ProviderFieldMatrixLocalMacOSPreregistrationSchemaVersion"
            ],
            1,
        )
        self.assertEqual(self.value["profile"]["material"], "regular")
        self.assertEqual(self.value["profile"]["appearance"], "light")
        self.assertEqual(self.value["profile"]["geometry"], "circle-127-center")
        self.assertFalse(self.value["profile"]["githubActionsRequired"])
        self.assertEqual(
            self.value["binary"]["sha256"],
            "0064fa35159b0d4872370d54528742a93e41662110e3d5456cf3f9e9e234dcb8",
        )
        self.assertEqual(
            self.value["symbols"]["provider"]["codeSHA256"],
            "a76c6f0b03cc6b64c6b040220f495c5f22d7e1e5322efb3cb139554dd397c10b",
        )

    def test_all_interventions_are_fixed_in_order(self) -> None:
        interventions = self.value["interventions"]
        self.assertEqual(len(interventions), 23)
        self.assertEqual(
            [item["index"] for item in interventions],
            list(range(23)),
        )
        self.assertEqual(interventions[0]["name"], "baseline")
        self.assertIsNone(interventions[0]["rawLittleEndianHex"])
        self.assertEqual(
            interventions[7]["rawLittleEndianHex"],
            "00000000000008c00000000000001440",
        )
        for item in interventions[1:]:
            raw = bytes.fromhex(item["rawLittleEndianHex"])
            expected = 16 if item["name"] == "shadow-offset-neg3-pos5" else 4
            self.assertEqual(len(raw), expected, item["name"])

    def test_frozen_implementation_hashes_match(self) -> None:
        for item in self.value["frozenImplementation"]["files"]:
            path = REPOSITORY / item["path"]
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                item["sha256"],
                item["path"],
            )

    def test_calibrations_and_outcomes_are_fail_closed(self) -> None:
        for calibration in self.value["preRegistrationCalibrationExclusions"]:
            self.assertFalse(calibration["authority"])
        self.assertTrue(
            all(
                outcome is None
                for outcome in self.value["unknownBeforeDispatch"].values()
            )
        )
        self.assertIsNone(self.value["runtimeOutcomeFrozenBeforeDispatch"])
        authority = self.value["productAuthority"]
        self.assertTrue(
            authority["exactFilterInputToProviderObjectEffectsMayBeDecodedOnPass"]
        )
        self.assertTrue(authority["observedProviderBranchEffectsMayBeDecodedOnPass"])
        for name, granted in authority.items():
            if name not in {
                "exactFilterInputToProviderObjectEffectsMayBeDecodedOnPass",
                "observedProviderBranchEffectsMayBeDecodedOnPass",
            }:
                self.assertFalse(granted, name)


if __name__ == "__main__":
    unittest.main()
