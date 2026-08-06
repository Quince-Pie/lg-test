#!/usr/bin/env python3
"""Integrity tests for the namespace-only helper-body trace retry."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import validate_prepare_layer_mask_instruction_trace_retry as validator


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_mask_instruction_trace_retry_preregistration.json"
)
FAILED_RESULT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_mask_instruction_trace_failed_run_result.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerMaskInstructionTraceRetryPreregistrationTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))
        cls.failed = json.loads(FAILED_RESULT_PATH.read_text(encoding="utf-8"))

    def test_retry_is_frozen_without_a_runtime_outcome(self) -> None:
        registration = self.registration
        self.assertEqual(
            registration[
                "prepareLayerMaskInstructionTraceRetryPreregistrationSchemaVersion"
            ],
            1,
        )
        self.assertIn("namespace-only", registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])

    def test_failed_run_and_helper_identity_are_immutable(self) -> None:
        antecedent = self.registration["failedRun"]
        self.assertEqual(antecedent["runID"], 31063528744)
        self.assertEqual(antecedent["workflowConclusion"], "failure")
        self.assertEqual(
            antecedent["failedResultSHA256"], sha256(FAILED_RESULT_PATH)
        )
        self.assertEqual(
            antecedent["helperCodeSHA256"],
            validator.KNOWN_HELPER_CODE_SHA256,
        )
        self.assertEqual(
            self.failed["openedEvidence"]["helperCodeSHA256"],
            validator.KNOWN_HELPER_CODE_SHA256,
        )
        self.assertEqual(antecedent["selectedHelperEntryCount"], 0)
        self.assertIsNone(antecedent["selectorOutcome"])

    def test_amendment_changes_only_constant_ownership_and_visibility(self) -> None:
        amendment = self.registration["technicalAmendment"]
        self.assertEqual(
            amendment["runtimeAlias"],
            "crop_base.PREPARE_LAYER_FUNCTION = "
            "capture_base.PREPARE_LAYER_FUNCTION",
        )
        self.assertTrue(amendment["inheritedCallbacksForwardedAtTopLevel"])
        for key in (
            "newBreakpointAdded",
            "newMemoryReadAdded",
            "selectorChanged",
            "captureByteRangeChanged",
            "steppingRuleChanged",
            "acceptanceChanged",
        ):
            self.assertFalse(amendment[key])

    def test_original_selector_and_sealed_authority_are_preserved(self) -> None:
        selection = self.registration["selection"]
        self.assertEqual(selection["geometry"], "circle-1025-center")
        self.assertEqual(selection["markerInterval"], 2)
        self.assertEqual(selection["qualifiedHelperOrdinalWithinInterval"], 8)
        self.assertFalse(selection["cropValueUsed"])
        self.assertFalse(selection["outputValueUsed"])
        acceptance = self.registration["acceptance"]
        self.assertTrue(acceptance["knownHelperCodeMustRepassBitForBit"])
        self.assertTrue(acceptance["zeroTraceFailuresRequired"])
        self.assertFalse(acceptance["exactSemanticsMayBeClaimed"])
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
