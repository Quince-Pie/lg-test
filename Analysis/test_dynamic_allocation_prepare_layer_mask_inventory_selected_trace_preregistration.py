#!/usr/bin/env python3
"""Integrity tests for the fixed inventory-mapped producer trace."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_mask_inventory_selected_trace_preregistration.json"
)
INVENTORY_RESULT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_mask_instruction_inventory_result.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerMaskInventorySelectedTracePreregistrationTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))
        cls.inventory = json.loads(INVENTORY_RESULT_PATH.read_text(encoding="utf-8"))

    def test_selected_trace_is_frozen_without_runtime_outcome(self) -> None:
        registration = self.registration
        self.assertEqual(
            registration[
                "prepareLayerMaskInventorySelectedTracePreregistrationSchemaVersion"
            ],
            1,
        )
        self.assertIn("prospective", registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])

    def test_inventory_failure_and_exact_opening_are_preserved(self) -> None:
        antecedent = self.registration["antecedent"]
        self.assertEqual(antecedent["runID"], 31065261980)
        self.assertEqual(
            antecedent["originalValidatorFailure"],
            "inventory helper marker links leave trailing entries",
        )
        self.assertEqual(antecedent["qualifiedHelperEntryCount"], 447)
        self.assertEqual(antecedent["trailingHelperEntryCount"], 1)
        self.assertEqual(antecedent["callbackEventCount"], 831)
        self.assertEqual(antecedent["inventoryResultSHA256"], sha256(INVENTORY_RESULT_PATH))

    def test_target_is_fixed_before_dispatch_from_structural_identity(self) -> None:
        selection = self.registration["selection"]
        self.assertEqual(selection["markerInterval"], 2)
        self.assertEqual(selection["qualifiedHelperOrdinal"], 14)
        self.assertEqual(selection["helperEventIndex"], 40)
        self.assertEqual(selection["producerStoreEventIndex"], 41)
        self.assertEqual(selection["matchingPriorHelperCount"], 1)
        self.assertFalse(selection["cropValueUsed"])
        self.assertFalse(selection["outputValueUsed"])
        self.assertEqual(
            self.inventory["structuralSelection"]["sample2TargetQualifiedOrdinal"],
            14,
        )

    def test_acceptance_remains_trace_calibration_only(self) -> None:
        acceptance = self.registration["acceptance"]
        self.assertTrue(acceptance["helperReturnMustMatchProducerBitForBit"])
        self.assertTrue(acceptance["completeInstructionSequenceRequired"])
        self.assertTrue(acceptance["freshProcessRequired"])
        self.assertFalse(acceptance["exactSemanticsMayBeClaimed"])
        self.assertFalse(acceptance["unchangedRepeatMayBeClaimed"])
        self.assertFalse(acceptance["productionShaderMayChange"])
        self.assertFalse(acceptance["liquidGlassParityMayBeClaimed"])

    def test_frozen_implementation_hashes_match(self) -> None:
        for record in self.registration["frozenImplementation"]["files"]:
            self.assertEqual(sha256(REPOSITORY_ROOT / record["path"]), record["sha256"])
        shader = self.registration["frozenImplementation"]["productionShader"]
        self.assertEqual(
            shader["sha256"],
            "6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d",
        )
        local_shader = REPOSITORY_ROOT.parent / "shaders" / "frag.glsl"
        if local_shader.is_file():
            self.assertEqual(sha256(local_shader), shader["sha256"])


if __name__ == "__main__":
    unittest.main()
