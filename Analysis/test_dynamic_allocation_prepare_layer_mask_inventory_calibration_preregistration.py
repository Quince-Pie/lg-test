#!/usr/bin/env python3
"""Integrity tests for the output-blind helper inventory calibration."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import validate_prepare_layer_mask_instruction_inventory as inventory_validator


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_mask_inventory_calibration_preregistration.json"
)
RETRY_RESULT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_mask_instruction_trace_retry_result.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerMaskInventoryCalibrationPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))
        cls.retry_result = json.loads(RETRY_RESULT_PATH.read_text(encoding="utf-8"))

    def test_calibration_is_frozen_without_a_runtime_outcome(self) -> None:
        registration = self.registration
        self.assertEqual(
            registration[
                "prepareLayerMaskInventoryCalibrationPreregistrationSchemaVersion"
            ],
            1,
        )
        self.assertIn("output-blind", registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])

    def test_ordinal_eight_failure_is_preserved_exactly(self) -> None:
        antecedent = self.registration["antecedent"]
        self.assertEqual(antecedent["runID"], 31064203802)
        self.assertEqual(antecedent["workflowConclusion"], "failure")
        self.assertEqual(antecedent["validatorFailure"], "helper output does not match structural producer")
        self.assertEqual(antecedent["selectedQualifiedOrdinal"], 8)
        self.assertEqual(antecedent["selectedMatchedStoreRecordIndex"], 10)
        self.assertEqual(antecedent["structuralProducerStoreRecordIndex"], 14)
        self.assertFalse(antecedent["ordinalEightMappingHypothesisPassed"])
        self.assertEqual(antecedent["resultSHA256"], sha256(RETRY_RESULT_PATH))

    def test_two_pass_selection_is_structural_and_fresh(self) -> None:
        protocol = self.registration["protocol"]
        self.assertEqual(
            protocol["inventorySentinelOrdinal"],
            inventory_validator.INVENTORY_SENTINEL_ORDINAL,
        )
        self.assertEqual(
            protocol["selectionRule"],
            "within marker interval 2 choose the last helper-entry event before "
            "the independently selected producer-store event whose caller role "
            "and prepare recursion depth equal that producer",
        )
        self.assertTrue(protocol["selectedTraceUsesFreshProcess"])
        self.assertFalse(protocol["cropValueUsed"])
        self.assertFalse(protocol["outputValueUsed"])
        self.assertFalse(protocol["targetOrdinalKnownBeforeInventory"])

    def test_acceptance_remains_calibration_only(self) -> None:
        acceptance = self.registration["acceptance"]
        self.assertTrue(acceptance["allHelperEntriesMustBeRetained"])
        self.assertTrue(acceptance["allCallbackEventsMustBeAccounted"])
        self.assertTrue(acceptance["freshSelectedHelperMustMatchProducerBitForBit"])
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
