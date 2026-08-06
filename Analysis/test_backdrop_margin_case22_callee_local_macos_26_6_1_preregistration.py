#!/usr/bin/env python3
"""Integrity checks for the local macOS 26.6.1 case-22 freeze."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).parent
PREREGISTRATION = (
    ANALYSIS / "backdrop_margin_case22_callee_local_macos_26_6_1_preregistration.json"
)


class LocalMacOSCase22PreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    def test_inventory_and_structural_correspondence_are_exact(self) -> None:
        self.assertEqual(self.value["openedInventory"]["validationStatus"], "passed")
        self.assertTrue(self.value["openedInventory"]["zeroTolerance"])
        structure = self.value["structuralCorrespondence"]
        self.assertTrue(structure["group"]["completeCodeBitwiseEqualToCIHost"])
        self.assertEqual(structure["caller"]["groupCallOffset"], 0x1680)
        self.assertEqual(
            structure["caller"]["decodedGroupTargetModuleOffset"], 0x3715D0
        )
        self.assertEqual(structure["case22Target"]["moduleOffset"], 0x76BC54)
        self.assertEqual(structure["quartzCore"]["copyStoreOffset"], 0x3B4)

    def test_runtime_unknowns_and_outcome_are_sealed(self) -> None:
        self.assertIsNone(self.value["runtimeOutcomeFrozenBeforeDispatch"])
        self.assertTrue(
            all(item is None for item in self.value["unknownBeforeDispatch"].values())
        )
        selection = self.value["selection"]
        self.assertEqual(selection["groupInvocationIndex"], 20)
        for key in (
            "capturedMarginUsedForRuntimeSelection",
            "capturedCropUsedForRuntimeSelection",
            "capturedImageUsedForRuntimeSelection",
            "capturedPixelUsedForRuntimeSelection",
            "prospectiveTransferAuthority",
        ):
            self.assertFalse(selection[key])

    def test_frozen_implementation_hashes_match(self) -> None:
        for record in self.value["frozenImplementation"]["files"]:
            payload = (ANALYSIS.parent / record["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), record["sha256"])

    def test_no_product_authority_is_predeclared(self) -> None:
        authority = self.value["productAuthority"]
        self.assertTrue(authority["case22ArithmeticMayBeDecodedOnPass"])
        for key, granted in authority.items():
            if key != "case22ArithmeticMayBeDecodedOnPass":
                self.assertFalse(granted, key)


if __name__ == "__main__":
    unittest.main()
