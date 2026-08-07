#!/usr/bin/env python3
"""Contracts for the runtime-unseen circle-500 origin holdout."""

import hashlib
import json
from pathlib import Path
import unittest


ANALYSIS = Path(__file__).parent
REPOSITORY = ANALYSIS.parent
PREREGISTRATION = ANALYSIS / (
    "variable_blur_selected_region_origin_circle500_holdout_preregistration.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class VariableBlurOriginHoldoutPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    def test_target_is_runtime_unseen_at_freeze(self) -> None:
        holdout = self.contract["holdout"]
        self.assertEqual(holdout["geometry"], "circle-500-center")
        self.assertEqual(holdout["runtimeEvidenceMatchCountAtFreeze"], 0)
        self.assertFalse(holdout["targetOutputsOpenedAtFreeze"])
        self.assertIsNone(self.contract["runtimeOutcomeFrozenBeforeDispatch"])

    def test_selection_is_instruction_and_stack_derived(self) -> None:
        selection = self.contract["selection"]
        self.assertEqual(selection["helperCodeByteCount"], 1_124)
        self.assertEqual(selection["helperOutputCompleteOffset"], 0x370)
        self.assertFalse(selection["resultValuesUsedForSelection"])
        self.assertFalse(selection["cropValuesUsedForSelection"])
        self.assertFalse(selection["imageOrPixelUsedForSelection"])

    def test_exact_origin_and_allocation_are_separate_gates(self) -> None:
        arithmetic = self.contract["frozenArithmetic"]
        gate = self.contract["requiredGate"]
        self.assertIn("floor", arithmetic["integerOrigin"])
        self.assertIn("ceil", arithmetic["desiredUpper"])
        self.assertIn("64", arithmetic["metalAllocationExtent"])
        self.assertEqual(gate["originMismatchedComponents"], 0)
        self.assertEqual(gate["desiredExtentMismatchedComponents"], 0)
        self.assertEqual(gate["allocationExtentMismatchedComponents"], 0)

    def test_every_frozen_file_hash_matches(self) -> None:
        for record in self.contract["frozenFiles"]:
            path = REPOSITORY / record["path"]
            with self.subTest(path=record["path"]):
                self.assertEqual(sha256(path), record["sha256"])

    def test_walle_integrity_remains_sealed(self) -> None:
        integrity = self.contract["outerWalleIntegrity"]
        self.assertEqual(
            sha256(REPOSITORY / integrity["productionShaderPath"]),
            integrity["productionShaderSHA256"],
        )
        self.assertEqual(
            sha256(REPOSITORY / integrity["developmentFlakePath"]),
            integrity["developmentFlakeSHA256"],
        )
        self.assertFalse(integrity["shaderQualityChangeAuthorized"])
        self.assertFalse(
            self.contract["sealedConclusion"]["liquidGlassParityEstablished"]
        )


if __name__ == "__main__":
    unittest.main()
