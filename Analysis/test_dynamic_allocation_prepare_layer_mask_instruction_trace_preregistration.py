#!/usr/bin/env python3
"""Integrity tests for the prospective prepare_layer_mask body trace."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import validate_prepare_layer_mask_instruction_trace as validator


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_mask_instruction_trace_preregistration.json"
)
OPENED_RESULT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_crop_policy_holdout_callback_retry_result.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerMaskInstructionTracePreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))
        cls.opened = json.loads(OPENED_RESULT_PATH.read_text(encoding="utf-8"))

    def test_capture_is_frozen_before_dispatch(self) -> None:
        registration = self.registration
        self.assertEqual(
            registration[
                "prepareLayerMaskInstructionTracePreregistrationSchemaVersion"
            ],
            1,
        )
        self.assertIn("prospective", registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])
        self.assertIsNone(registration["helper"]["expectedCodeSHA256"])
        self.assertFalse(registration["helper"]["codeKnownBeforeCapture"])

    def test_antecedent_failure_and_opened_boundary_are_preserved(self) -> None:
        antecedent = self.registration["antecedent"]
        self.assertEqual(antecedent["runID"], 31059860458)
        self.assertEqual(
            antecedent["headSHA"], "6ff54c6bd01e6dea04002ca8c11fd1c0f7e4852c"
        )
        self.assertEqual(antecedent["workflowConclusion"], "failure")
        self.assertFalse(antecedent["prospectiveGatePassed"])
        self.assertEqual(antecedent["capturedProducerRecordCount"], 256)
        self.assertEqual(antecedent["exactIntegerCropCount"], 256)
        self.assertEqual(antecedent["exactCombinedIntegerCropCount"], 512)
        self.assertEqual(antecedent["exactCollapsedFloatCount"], 139)
        self.assertEqual(antecedent["exactLocalFloatCount"], 211)
        self.assertEqual(sha256(OPENED_RESULT_PATH), antecedent["openedResultSHA256"])

    def test_helper_identity_comes_from_existing_instruction_evidence(self) -> None:
        helper = self.registration["helper"]
        self.assertEqual(helper["function"], validator.HELPER_FUNCTION)
        self.assertEqual(helper["relativeToPrepareLayer"], -1_209_388)
        self.assertEqual(helper["symbolByteCount"], 2_176)
        self.assertEqual(helper["callOffset"], "0xd90")
        self.assertEqual(helper["callReturnOffset"], "0xd94")
        self.assertEqual(helper["callInstructionRawLittleEndianHex"], "915ffb97")
        self.assertEqual(helper["callerLocalStateOffset"], "0x420")
        self.assertEqual(helper["callerOutputOffset"], "0x290")
        self.assertEqual(helper["existingInstructionTraceRunID"], 31048753297)

    def test_selection_uses_only_preopened_structure(self) -> None:
        selection = self.registration["selection"]
        self.assertEqual(selection["geometry"], "circle-1025-center")
        self.assertEqual(selection["markerInterval"], 2)
        self.assertEqual(selection["qualifiedHelperOrdinalWithinInterval"], 8)
        self.assertTrue(selection["directNormalCallerRequired"])
        self.assertEqual(selection["requiredX1Relationship"], "x1 = x19 + 0x420")
        self.assertEqual(selection["requiredX3Relationship"], "x3 = x19 + 0x290")
        self.assertFalse(selection["cropValueUsed"])
        self.assertFalse(selection["outputValueUsed"])
        self.assertFalse(selection["eventCountMayBeChangedAfterCapture"])

    def test_acceptance_remains_calibration_only(self) -> None:
        acceptance = self.registration["acceptance"]
        self.assertTrue(acceptance["completeHelperCodeRequired"])
        self.assertTrue(acceptance["completeInstructionSequenceRequired"])
        self.assertTrue(acceptance["completeScalarAndSIMDRegistersRequired"])
        self.assertTrue(acceptance["exactHelperReturnToProducerCorrelationRequired"])
        self.assertTrue(acceptance["zeroTraceFailuresRequired"])
        self.assertFalse(acceptance["exactSemanticsMayBeClaimed"])
        self.assertFalse(acceptance["unchangedRepeatMayBeClaimed"])
        self.assertFalse(acceptance["productionShaderMayChange"])
        self.assertFalse(acceptance["liquidGlassParityMayBeClaimed"])

    def test_frozen_configuration_matches_capture_and_validator(self) -> None:
        self.assertEqual(
            self.registration["captureConfiguration"],
            validator.EXPECTED_CONFIGURATION,
        )

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
