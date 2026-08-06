#!/usr/bin/env python3
"""Integrity checks for the frozen Group.margin execution diagnostic."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import validate_backdrop_margin_group_execution as validator


ANALYSIS = Path(__file__).resolve().parent
ROOT = ANALYSIS.parent
PREREGISTRATION = ANALYSIS / "backdrop_margin_group_execution_preregistration.json"
VALUE = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))


class BackdropMarginGroupExecutionPreregistrationTests(unittest.TestCase):
    def test_semantic_contract_is_sealed(self) -> None:
        self.assertIs(validator.validate_preregistration(VALUE), VALUE)
        self.assertEqual(VALUE["runtimeOutcomeFrozenBeforeDispatch"], None)
        self.assertTrue(VALUE["profile"]["exactPublicProfilePreviouslyCaptured"])
        self.assertFalse(VALUE["profile"]["exactGroupExecutionPreviouslyCaptured"])
        self.assertTrue(
            all(value is None for value in VALUE["unknownBeforeCapture"].values())
        )

    def test_frozen_implementation_hashes_match(self) -> None:
        files = VALUE["frozenImplementation"]["files"]
        self.assertEqual(len(files), 10)
        for record in files:
            path = ROOT / record["path"]
            self.assertTrue(path.is_file(), record["path"])
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                record["sha256"],
                record["path"],
            )

    def test_quality_locks_are_immutable(self) -> None:
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
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    record["sha256"],
                )

    def test_diagnostic_grants_no_product_authority(self) -> None:
        authority = VALUE["productAuthority"]
        self.assertTrue(authority["groupExecutionMayBeOpenedOnPass"])
        for key, allowed in authority.items():
            if key != "groupExecutionMayBeOpenedOnPass":
                self.assertFalse(allowed, key)


if __name__ == "__main__":
    unittest.main()
