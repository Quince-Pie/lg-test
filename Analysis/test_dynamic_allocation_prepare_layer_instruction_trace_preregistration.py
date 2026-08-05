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

    def test_epoch_selection_is_dual_source_linked_not_adaptive(self) -> None:
        selection = self.document["selection"]
        correction = self.document["observerOrdinalCorrection"]
        reuse = self.document["frameReuseCorrection"]
        self.assertEqual(correction["sourceRunID"], 31038371480)
        self.assertEqual(correction["registeredLaterEpochOrdinal"], 7)
        self.assertEqual(
            correction["observedSourceKnownDepthFourEpochCountBeforeExactMarker"],
            3,
        )
        self.assertFalse(correction["laterEpochOrdinalStableAcrossObservers"])
        result_path = REPOSITORY_ROOT / correction["sourceResultPath"]
        self.assertEqual(sha256(result_path), correction["sourceResultSHA256"])
        self.assertEqual(reuse["sourceRunID"], 31039587304)
        self.assertFalse(reuse["firstSourceKnownDepthFourEpochIsSelectedInvocation"])
        self.assertTrue(reuse["uniqueExactSelectionInEveryRetainedRun"])
        self.assertFalse(reuse["x20Minus24AloneIsSufficient"])
        reuse_result_path = REPOSITORY_ROOT / reuse["sourceResultPath"]
        self.assertEqual(sha256(reuse_result_path), reuse["sourceResultSHA256"])
        self.assertEqual(
            selection["prospectiveSourceLinkCells"],
            [
                {
                    "baseRegister": spec["baseRegister"],
                    "signedOffset": spec["signedOffset"],
                    "decode": "little-endian uint64",
                }
                for spec in validator.SOURCE_LINK_CELL_SPECS
            ],
        )
        self.assertTrue(selection["adaptiveEpochSelectionForbidden"])
        self.assertTrue(selection["observerDependentLaterOrdinalForbidden"])
        self.assertTrue(selection["stackAddressEqualityAloneForbidden"])
        self.assertTrue(selection["futureMarkerBasedEpochSelectionForbidden"])
        self.assertEqual(selection["earlyIdentity"], ["threadID", "x19", "x29"])
        self.assertIn("x28", selection["futureIdentity"])
        self.assertEqual(
            self.document["acceptance"]["sourceLinkedDepthFourEpochCountAtStop"],
            1,
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
                "filterApplyDOD",
                "filterApply",
                "filterMapBounds",
                "addBackgroundFilters",
                "unionBounds",
            ],
        )
        self.assertIsNone(observed[4]["expectedSHA256"])
        self.assertIsNone(observed[5]["expectedSHA256"])
        self.assertIsNone(observed[6]["expectedSHA256"])
        self.assertIsNone(observed[7]["expectedSHA256"])
        self.assertIn(
            "cannot influence instruction selection",
            self.document["instrumentation"]["unopenedScopeHashRule"],
        )
        correction = self.document["opaqueScopeCorrection"]
        self.assertEqual(correction["sourceRunID"], 31041421876)
        self.assertEqual(correction["changedOpaqueCalleeBoundaryCount"], 1)
        self.assertEqual(
            correction["onlyChangedOpaqueBoundary"]["relativeToPrepareLayer"],
            -609324,
        )
        self.assertEqual(correction["onlyChangedOpaqueBoundary"]["byteCount"], 1092)
        result_path = REPOSITORY_ROOT / correction["sourceResultPath"]
        self.assertEqual(sha256(result_path), correction["sourceResultSHA256"])

    def test_successful_instruction_chain_is_the_opened_boundary(self) -> None:
        boundary = self.document["successfulInstructionChainBoundary"]
        self.assertEqual(boundary["sourceRunID"], 31042429686)
        self.assertEqual(boundary["instructionStepCount"], 7356)
        self.assertEqual(boundary["aggregateTransitionCount"], 12)
        self.assertEqual(boundary["changedOpaqueCalleeBoundaryCount"], 0)
        self.assertEqual(boundary["selectedGlassDODEntryStepIndex"], 715)
        self.assertEqual(boundary["selectedGlassDODExecutedInstructionCount"], 267)
        self.assertTrue(boundary["completeArchitecturalWriterSequenceCaptured"])
        self.assertFalse(boundary["selectedGlassDODCompleteRegisterStateCaptured"])
        result_path = REPOSITORY_ROOT / boundary["sourceResultPath"]
        self.assertEqual(sha256(result_path), boundary["sourceResultSHA256"])

    def test_selected_dod_semantics_are_the_new_opened_boundary(self) -> None:
        boundary = self.document["selectedGlassDODSemanticBoundary"]
        self.assertEqual(boundary["sourceRunID"], 31044659120)
        self.assertEqual(boundary["selectedDODInstructionStateCount"], 267)
        self.assertEqual(boundary["shadowOffset"], [0.0, 8.0])
        self.assertEqual(
            boundary["expansionRule"],
            "e = 2.8 * max(2 * blurRadius, bleedBlurRadius)",
        )
        self.assertTrue(boundary["glassDODArithmeticDecoded"])
        self.assertFalse(boundary["upstreamIntegerCropProductionDecoded"])
        result_path = REPOSITORY_ROOT / boundary["sourceResultPath"]
        self.assertEqual(sha256(result_path), boundary["sourceResultSHA256"])

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
        self.assertEqual(
            instrumentation["semanticDODSelection"].split(";", 1)[0],
            "At every glassBackgroundDOD +0x0 entry retain the exact x3 register record",
        )
        self.assertIn("x0-x30", instrumentation["semanticDODInstructionState"][1])
        self.assertIn("v0-v31", instrumentation["semanticDODInstructionState"][2])
        self.assertIn(
            "canonical SHA-256", instrumentation["semanticDODReturnState"][-1]
        )
        self.assertEqual(instrumentation["semanticCropExpectedInvocationCount"], 4)
        self.assertEqual(instrumentation["semanticCropMaximumInvocationCount"], 8)
        self.assertIn(
            "x5 = live caller x19 + 0x290", instrumentation["semanticCropTargetRule"]
        )
        self.assertIn("+0x55c0", instrumentation["semanticCropStoreLink"])
        self.assertIn("+0x8570", instrumentation["semanticCropUnionLink"])

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
        self.assertTrue(acceptance["selectedGlassDODExactDynamicReplayMayBeClaimed"])
        self.assertTrue(
            acceptance["backgroundFilterCropExactDynamicReplayMayBeClaimed"]
        )
        self.assertTrue(acceptance["backgroundFilterCropStoreAndUnionLinkMayBeClaimed"])
        self.assertFalse(
            acceptance["backgroundFilterCropInstructionSemanticsMayBeClaimed"]
        )
        self.assertTrue(
            acceptance[
                "everyExecutedSelectedGlassDODInstructionMustHaveOneCompletePreState"
            ]
        )
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
            (integrity["frameReuseResultPath"], "frameReuseResultSHA256"),
            (
                integrity["applyDODScopeResultPath"],
                "applyDODScopeResultSHA256",
            ),
            (
                integrity["successfulInstructionChainResultPath"],
                "successfulInstructionChainResultSHA256",
            ),
            (
                integrity["selectedDODSemanticResultPath"],
                "selectedDODSemanticResultSHA256",
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
                self.assertEqual(sha256(REPOSITORY_ROOT / relative), integrity[field])
        self.assertFalse(integrity["productionShaderModifiedByExperiment"])

    def test_three_negative_attempts_success_and_successor_are_frozen(self) -> None:
        outcome = self.document["firstAttemptRuntimeOutcome"]
        self.assertEqual(outcome["runID"], 31038371480)
        self.assertEqual(outcome["registeredEpochOrdinal"], 7)
        self.assertEqual(outcome["observedEpochCountBeforeExactMarker"], 3)
        self.assertFalse(outcome["instructionTraceStarted"])
        self.assertFalse(outcome["productionShaderAuthorized"])
        retry = self.document["retryRuntimeOutcome"]
        self.assertEqual(retry["runID"], 31039587304)
        self.assertTrue(retry["instructionTraceStarted"])
        self.assertEqual(retry["instructionStepCount"], 5669)
        self.assertTrue(retry["selectedFrameReturnedBeforeMarker"])
        self.assertFalse(retry["firstEpochDualSourceLinkPassed"])
        self.assertFalse(retry["productionShaderAuthorized"])
        selected = self.document["dualSourceLinkRuntimeOutcome"]
        self.assertEqual(selected["runID"], 31041421876)
        self.assertTrue(selected["dualSourceLinkSelectorPassed"])
        self.assertTrue(selected["selectedFrameReachedExactMarker"])
        self.assertEqual(selected["changedOpaqueCalleeBoundaryCount"], 1)
        self.assertFalse(selected["productionShaderAuthorized"])
        expanded = self.document["expandedScopeRuntimeOutcome"]
        self.assertEqual(expanded["runID"], 31042429686)
        self.assertEqual(expanded["changedOpaqueCalleeBoundaryCount"], 0)
        self.assertFalse(expanded["selectedGlassDODCompleteRegisterStateCaptured"])
        self.assertIsNone(
            self.document["semanticRegisterTraceRuntimeOutcomeFrozenBeforeRun"]
        )
        self.assertIsNone(self.document["cropWriterTraceRuntimeOutcomeFrozenBeforeRun"])


if __name__ == "__main__":
    unittest.main()
