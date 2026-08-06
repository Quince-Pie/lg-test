#!/usr/bin/env python3
"""Integrity contracts for the local-host symbol inventory freeze."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).parent
PREREGISTRATION = ANALYSIS / "local_host_symbol_inventory_preregistration.json"


class LocalHostSymbolInventoryPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    def test_host_drift_and_retina_baseline_are_explicit(self) -> None:
        host = self.value["hostAntecedent"]
        self.assertEqual(host["macOSProductVersion"], "26.6.1")
        self.assertEqual(host["macOSBuildVersion"], "25G76")
        self.assertTrue(host["frameworkIdentityDiffersFromPreviousCIHost"])
        self.assertEqual(host["display"]["physicalPixels"], [3456, 2234])
        baseline = self.value["openedRetinaBaseline"]
        self.assertEqual(baseline["windowBackingScaleFactor"], 2)
        self.assertEqual(baseline["failedSamples"], 0)
        self.assertTrue(baseline["dynamicBackgroundUniformsExecuted"])

    def test_runtime_outcome_and_code_are_sealed(self) -> None:
        self.assertIsNone(self.value["runtimeOutcomeFrozenBeforeDispatch"])
        self.assertTrue(
            all(item is None for item in self.value["unknownBeforeDispatch"].values())
        )
        selection = self.value["selection"]
        for key in (
            "capturedMarginUsedForSelection",
            "capturedCropUsedForSelection",
            "capturedImageUsedForSelection",
            "capturedPixelUsedForSelection",
        ):
            self.assertFalse(selection[key])

    def test_frozen_implementation_hashes_match(self) -> None:
        for record in self.value["frozenImplementation"]["files"]:
            payload = (ANALYSIS.parent / record["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), record["sha256"])

    def test_no_product_authority_is_predeclared(self) -> None:
        authority = self.value["productAuthority"]
        self.assertTrue(authority["hostSpecificExecutionAdapterMayBeFrozenOnPass"])
        for key, granted in authority.items():
            if key != "hostSpecificExecutionAdapterMayBeFrozenOnPass":
                self.assertFalse(granted, key)


if __name__ == "__main__":
    unittest.main()
