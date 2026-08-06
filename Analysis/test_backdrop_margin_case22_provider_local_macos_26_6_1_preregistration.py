#!/usr/bin/env python3
"""Integrity checks for the frozen local case-22 provider diagnostic."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).parent
PREREGISTRATION = (
    ANALYSIS / "backdrop_margin_case22_provider_local_macos_26_6_1_preregistration.json"
)


class LocalMacOSCase22ProviderPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    def test_parent_and_static_openings_are_exact(self) -> None:
        parent = self.value["openedParentExecution"]
        self.assertEqual(parent["selectedInvocationIndex"], 20)
        self.assertEqual(parent["wrapperInstructionStateCount"], 29)
        self.assertEqual(parent["wrapperOpaqueCalleeCount"], 1)
        self.assertEqual(parent["wrapperFailureCount"], 0)
        self.assertTrue(parent["returnMatchesGroupAndSetterBitwise"])
        opened = self.value["openedStaticProvider"]
        self.assertEqual(opened["dispatchThunk"]["decodedTargetModuleOffset"], 0xB70B4)
        self.assertEqual(opened["provider"]["symbolByteCount"], 984)
        self.assertEqual(opened["helper"]["symbolByteCount"], 276)

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
        self.assertTrue(authority["selectedProviderArithmeticMayBeDecodedOnPass"])
        for key, granted in authority.items():
            if key != "selectedProviderArithmeticMayBeDecodedOnPass":
                self.assertFalse(granted, key)


if __name__ == "__main__":
    unittest.main()
