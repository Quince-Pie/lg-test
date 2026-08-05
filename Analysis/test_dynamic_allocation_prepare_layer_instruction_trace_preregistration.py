#!/usr/bin/env python3
"""Integrity tests for the prospective software-instruction trace."""

import hashlib
import json
import unittest
from pathlib import Path

import validate_prepare_layer_instruction_trace as validator


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
WALLE_ROOT = REPOSITORY_ROOT.parent
PREREGISTRATION_PATH = ANALYSIS_ROOT / (
    "dynamic_allocation_prepare_layer_instruction_trace_preregistration.json"
)
PRODUCTION_SHADER_SHA256 = (
    "6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PrepareLayerInstructionTracePreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_opened_boundary_records_callback_coalescing(self) -> None:
        boundary = self.document["openedEvidenceBoundary"]
        self.assertEqual(boundary["sourceRunID"], 31034880031)
        self.assertEqual(
            boundary["sourceHeadSHA"],
            "06d717ecbf269b7cc2d54df0332f45d0e8502f2c",
        )
        self.assertTrue(boundary["hardwareWatchCallbackCoalescingProved"])
        self.assertEqual(boundary["coalescedFirstStoreRelativeToPrepareLayer"], -89724)
        self.assertEqual(boundary["coalescedSecondStoreRelativeToPrepareLayer"], -89704)
        self.assertEqual(boundary["singleReportedStopRelativeToPrepareLayer"], -89700)
        self.assertFalse(boundary["completeArchitecturalStoreSequenceProved"])
        result_path = REPOSITORY_ROOT / boundary["sourceResultPath"]
        self.assertEqual(sha256(result_path), boundary["sourceResultSHA256"])

    def test_epoch_selection_is_prospective_not_adaptive(self) -> None:
        selection = self.document["selection"]
        correction = self.document["observerOrdinalCorrection"]
        self.assertEqual(correction["sourceRunID"], 31038371480)
        self.assertEqual(correction["registeredLaterEpochOrdinal"], 7)
        self.assertEqual(
            correction["observedSourceKnownDepthFourEpochCountBeforeExactMarker"],
            3,
        )
        self.assertFalse(correction["laterEpochOrdinalStableAcrossObservers"])
        result_path = REPOSITORY_ROOT / correction["sourceResultPath"]
        self.assertEqual(sha256(result_path), correction["sourceResultSHA256"])
        self.assertEqual(selection["prospectiveEpochOrdinal"], 1)
        self.assertTrue(selection["adaptiveEpochSelectionForbidden"])
        self.assertTrue(selection["observerDependentLaterOrdinalForbidden"])
        self.assertEqual(selection["earlyIdentity"], ["threadID", "x19", "x29"])
        self.assertIn("x28", selection["futureIdentity"])
        self.assertEqual(
            self.document["acceptance"]["sourceKnownDepthFourEpochCountAtStop"],
            validator.TARGET_SOURCE_KNOWN_DEPTH_FOUR_EPOCH_ORDINAL,
        )

    def test_scope_inventory_matches_capture_and_validator(self) -> None:
        observed = self.document["instrumentation"]["checkpointScopes"]
        self.assertEqual(observed, validator._scope_configuration())
        self.assertEqual(
            [item["name"] for item in observed],
            [
                "prepareLayer",
                "rectApplyTransform",
                "rectUnapplyTransform",
                "glassBackgroundDOD",
                "filterApply",
                "filterMapBounds",
                "unionBounds",
            ],
        )
        self.assertIsNone(observed[4]["expectedSHA256"])
        self.assertIsNone(observed[5]["expectedSHA256"])
        self.assertIn(
            "cannot influence instruction selection",
            self.document["instrumentation"]["unopenedScopeHashRule"],
        )

    def test_instrumentation_removes_both_callback_collision_sources(self) -> None:
        instrumentation = self.document["instrumentation"]
        self.assertFalse(instrumentation["hardwareWatchpointsUsed"])
        self.assertTrue(
            instrumentation["sampledWriterBreakpointsRetiredAfterSourceSelection"]
        )
        self.assertTrue(
            instrumentation["allSoftwareBreakpointsDisabledBeforeFirstInstructionStep"]
        )
        self.assertTrue(instrumentation["manualSelectionMarkersRetained"])
        self.assertEqual(
            instrumentation["selectedThreadStepAPI"],
            "SBThread.StepInstruction(false, SBError)",
        )
        self.assertEqual(
            instrumentation["opaqueCalleeAPI"], "SBThread.StepOut(SBError)"
        )
        self.assertIn("SetAsync(false)", instrumentation["debuggerModeBeforeStepping"])

    def test_gate_fails_on_any_opaque_aggregate_mutation(self) -> None:
        acceptance = self.document["acceptance"]
        self.assertTrue(acceptance["zeroChangedOpaqueCalleeBoundariesRequired"])
        self.assertTrue(acceptance["continuousBeforeAfterAggregateChainRequired"])
        self.assertTrue(
            acceptance["knownAggregateStateTransferBitExactAndOrderedRequired"]
        )
        null_outcome = "\n".join(self.document["nullOutcome"])
        self.assertIn("opaque callee boundary changes", null_outcome)
        self.assertIn("before/after chain is discontinuous", null_outcome)

    def test_pass_cannot_authorize_shader_or_parity(self) -> None:
        acceptance = self.document["acceptance"]
        self.assertTrue(acceptance["changedInstructionBytesAndOperandsMayBeClaimed"])
        self.assertFalse(acceptance["writerInstructionSemanticsMayBeClaimed"])
        self.assertFalse(acceptance["completeCropPolicyMayBeClaimed"])
        self.assertFalse(acceptance["productionShaderMayChange"])
        self.assertFalse(acceptance["liquidGlassParityMayBeClaimed"])
        forbidden = "\n".join(self.document["notAuthorizedBeforeAcceptance"])
        self.assertIn("production shader", forbidden)
        self.assertIn("parity", forbidden)
        self.assertIn("fixed number", forbidden)

    def test_input_hashes_and_production_shader_are_frozen(self) -> None:
        integrity = self.document["inputProgramIntegrity"]
        self.assertEqual(integrity["productionShaderSHA256"], PRODUCTION_SHADER_SHA256)
        shader = WALLE_ROOT / "shaders/frag.glsl"
        if shader.is_file():
            self.assertEqual(sha256(shader), PRODUCTION_SHADER_SHA256)
        paths = (
            (integrity["coalescingResultPath"], "coalescingResultSHA256"),
            (
                integrity["observerOrdinalResultPath"],
                "observerOrdinalResultSHA256",
            ),
            (integrity["captureProgramPath"], "captureProgramSHA256"),
            (integrity["validatorPath"], "validatorSHA256"),
            (integrity["captureSourceTestPath"], "captureSourceTestSHA256"),
            (integrity["validatorTestPath"], "validatorTestSHA256"),
            (integrity["workflowPath"], "workflowSHA256"),
            (integrity["preregistrationTestPath"], "preregistrationTestSHA256"),
        )
        for relative, field in paths:
            with self.subTest(path=relative):
                self.assertEqual(
                    sha256(REPOSITORY_ROOT / relative), integrity[field]
                )
        self.assertFalse(integrity["productionShaderModifiedByExperiment"])

    def test_first_attempt_is_frozen_and_retry_is_null_before_dispatch(self) -> None:
        outcome = self.document["firstAttemptRuntimeOutcome"]
        self.assertEqual(outcome["runID"], 31038371480)
        self.assertEqual(outcome["registeredEpochOrdinal"], 7)
        self.assertEqual(outcome["observedEpochCountBeforeExactMarker"], 3)
        self.assertFalse(outcome["instructionTraceStarted"])
        self.assertFalse(outcome["productionShaderAuthorized"])
        self.assertIsNone(self.document["retryRuntimeOutcomeFrozenBeforeRun"])


if __name__ == "__main__":
    unittest.main()
