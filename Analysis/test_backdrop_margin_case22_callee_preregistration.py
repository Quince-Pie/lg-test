#!/usr/bin/env python3
"""Integrity checks for the frozen case-22 callee diagnostic."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import validate_backdrop_margin_case22_callee as validator


ANALYSIS = Path(__file__).resolve().parent
ROOT = ANALYSIS.parent
PREREGISTRATION = ANALYSIS / "backdrop_margin_case22_callee_preregistration.json"
VALUE = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))


class BackdropMarginCase22CalleePreregistrationTests(unittest.TestCase):
    def test_machine_results_and_runtime_outcome_are_sealed(self) -> None:
        self.assertIs(validator.validate_preregistration(VALUE), VALUE)
        self.assertIsNone(VALUE["runtimeOutcomeFrozenBeforeDispatch"])
        self.assertTrue(
            all(value is None for value in VALUE["unknownBeforeCapture"].values())
        )
        selection = VALUE["selection"]
        self.assertTrue(selection["ordinalChoiceWasRetrospective"])
        self.assertFalse(selection["runtimeSelectionReadsOpenedReturn"])
        self.assertFalse(selection["prospectiveTransferAuthority"])

    def test_frozen_implementation_hashes_match(self) -> None:
        files = VALUE["frozenImplementation"]["files"]
        self.assertGreaterEqual(len(files), 12)
        for record in files:
            path = ROOT / record["path"]
            self.assertTrue(path.is_file(), record["path"])
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                record["sha256"],
                record["path"],
            )

    def test_opened_antecedent_is_exact(self) -> None:
        antecedent = VALUE["antecedent"]
        self.assertEqual(antecedent["runID"], 31118243811)
        self.assertEqual(
            antecedent["headSHA"],
            "f4054b43b1a1b6c16f78c4e78e6350e7678a8763",
        )
        self.assertEqual(antecedent["case22InvocationCount"], 76)
        self.assertEqual(antecedent["case22TargetModuleOffset"], 0x76BC54)
        self.assertFalse(antecedent["case22TargetCodeCaptured"])
        self.assertFalse(antecedent["liquidGlassParityEstablished"])

    def test_quality_locks_and_authority_remain_closed(self) -> None:
        frozen = VALUE["frozenImplementation"]
        self.assertEqual(
            frozen["productionShader"]["sha256"],
            "6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d",
        )
        self.assertEqual(
            frozen["walleFlake"]["sha256"],
            "b166e3c3ca8cca1e9e83544ab30d47c62b1b25fdef37783dcc2183e46669fa01",
        )
        for key in ("productionShader", "walleFlake"):
            record = frozen[key]
            self.assertFalse(record["changed"])
            path = ROOT / record["externalPath"]
            if path.is_file():
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(), record["sha256"]
                )
        authority = VALUE["productAuthority"]
        self.assertTrue(authority["case22ArithmeticMayBeDecodedOnPass"])
        for key, allowed in authority.items():
            if key != "case22ArithmeticMayBeDecodedOnPass":
                self.assertFalse(allowed, key)


if __name__ == "__main__":
    unittest.main()
