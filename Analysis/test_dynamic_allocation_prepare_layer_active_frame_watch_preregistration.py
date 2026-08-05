import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
WALLE_ROOT = REPOSITORY_ROOT.parent
PREREGISTRATION_PATH = ANALYSIS_ROOT / (
    "dynamic_allocation_prepare_layer_active_frame_watch_preregistration.json"
)
PRODUCTION_SHADER_SHA256 = (
    "6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ActiveFrameWatchPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_opened_boundary_is_exact_and_does_not_overclaim(self) -> None:
        boundary = self.document["openedEvidenceBoundary"]
        self.assertEqual(boundary["runID"], 31022198697)
        self.assertEqual(boundary["selectedPrepareLayerRecursionDepth"], 4)
        self.assertTrue(boundary["sameInvocationFrameCorrelationProved"])
        self.assertTrue(boundary["selectedAggregateChainClosedAtMarker"])
        self.assertFalse(boundary["completeCausalWriterListProved"])

    def test_four_watch_lanes_cover_exactly_thirty_two_bytes(self) -> None:
        acceptance = self.document["acceptance"]
        offsets = acceptance["watchLaneOffsets"]
        byte_count = acceptance["watchLaneByteCount"]
        covered = {
            byte for offset in offsets for byte in range(offset, offset + byte_count)
        }
        self.assertEqual(offsets, [0, 8, 16, 24])
        self.assertEqual(covered, set(range(32)))
        self.assertTrue(acceptance["allFourHardwareWatchpointsRequired"])
        self.assertTrue(acceptance["fullThirtyTwoByteCoverageRequired"])
        self.assertTrue(acceptance["singlePhysicalBreakpointPerSharedAddressRequired"])
        self.assertTrue(acceptance["inheritedCallbackMustRunBeforeActiveCallback"])
        self.assertTrue(
            acceptance["everyInheritedCallbackMustBeExportedByLoadedModule"]
        )
        self.assertTrue(acceptance["allNonEpochSampledWriterBreakpointsMustBeRetired"])
        self.assertEqual(acceptance["sampledBreakpointRetirementCallbackSequence"], 2)
        self.assertFalse(acceptance["retiredBreakpointEnabledStateRequired"])
        self.assertTrue(acceptance["retainedControlBreakpointEnabledStateRequired"])

    def test_early_identity_excludes_future_x28(self) -> None:
        acceptance = self.document["acceptance"]
        self.assertEqual(acceptance["earlyIdentityFields"], ["threadID", "x19", "x29"])
        self.assertTrue(
            acceptance["structuralDepthIndependentOfRegisterAvailabilityRequired"]
        )
        self.assertEqual(
            acceptance["liveFrameMembershipFields"],
            ["threadID", "SBFrame.GetFP"],
        )
        self.assertTrue(acceptance["topX29MustEqualSBFrameGetFP"])
        self.assertTrue(acceptance["futureX28IdentityForbiddenAtEpoch"])
        self.assertTrue(acceptance["watchRetirementWithLiveFrameRequired"])

    def test_sealed_acceptance_requires_new_contiguous_writer_evidence(self) -> None:
        acceptance = self.document["acceptance"]
        self.assertTrue(acceptance["zeroIgnoredWatchpointHitsRequired"])
        self.assertTrue(acceptance["allOrdinaryMarkerRejectionsMustBeRetained"])
        self.assertTrue(acceptance["contiguousFullAggregateChainRequired"])
        self.assertEqual(acceptance["minimumSelectedChangedTransitionCount"], 3)
        self.assertEqual(acceptance["minimumSelectedDistinctAggregateCount"], 4)
        self.assertTrue(acceptance["newChangedWriterOutsideSampledSitesRequired"])
        self.assertTrue(acceptance["lastAggregateMustBitMatchBothMarkers"])
        self.assertTrue(
            acceptance["knownAggregateStateTransferBitExactAndOrderedRequired"]
        )
        self.assertTrue(acceptance["currentInheritedStaticSourceMarkerContextMustPass"])
        self.assertFalse(acceptance["currentInheritedSampledSuffixGateRequired"])
        self.assertFalse(acceptance["writerInstructionSemanticsMayBeClaimed"])
        self.assertFalse(acceptance["productionShaderMayChange"])

    def test_input_program_hashes_are_frozen(self) -> None:
        integrity = self.document["inputProgramIntegrity"]
        self.assertEqual(integrity["productionShaderSHA256"], PRODUCTION_SHADER_SHA256)
        production_shader = WALLE_ROOT / "shaders/frag.glsl"
        if production_shader.is_file():
            self.assertEqual(sha256(production_shader), PRODUCTION_SHADER_SHA256)
        paths = (
            (
                REPOSITORY_ROOT
                / "Analysis/dynamic_allocation_prepare_layer_frame_writer_result.json",
                "openedFrameWriterResultSHA256",
            ),
            (
                REPOSITORY_ROOT
                / "Analysis/capture_prepare_layer_active_frame_watch_trace_lldb.py",
                "captureProgramSHA256",
            ),
            (
                REPOSITORY_ROOT
                / "Analysis/validate_prepare_layer_active_frame_watch_trace.py",
                "validatorSHA256",
            ),
            (
                REPOSITORY_ROOT
                / "Analysis/test_capture_prepare_layer_active_frame_watch_trace_lldb_source.py",
                "captureSourceTestSHA256",
            ),
            (
                REPOSITORY_ROOT
                / "Analysis/test_validate_prepare_layer_active_frame_watch_trace.py",
                "validatorTestSHA256",
            ),
            (
                REPOSITORY_ROOT
                / ".github/workflows/prepare-layer-active-frame-watch-introspect.yml",
                "workflowSHA256",
            ),
            (
                REPOSITORY_ROOT
                / "Analysis/test_dynamic_allocation_prepare_layer_active_frame_watch_preregistration.py",
                "preregistrationTestSHA256",
            ),
        )
        for path, field in paths:
            with self.subTest(path=path):
                self.assertEqual(sha256(path), integrity[field])
        self.assertFalse(integrity["productionShaderModifiedByExperiment"])

    def test_runtime_outcome_records_coalescing_and_forbids_product_claims(self) -> None:
        correction = self.document["preCaptureContractCorrection"]
        self.assertEqual(correction["runID"], 31025339792)
        self.assertFalse(correction["captureAttempted"])
        self.assertFalse(correction["appleRuntimeObserved"])
        self.assertFalse(correction["artifactProduced"])
        duplicate = self.document["duplicateBreakpointCaptureCorrection"]
        self.assertEqual(duplicate["runID"], 31025574711)
        self.assertEqual(
            duplicate["captureTargetStopReason"],
            "breakpoint 2.1 3.1 at exact prepare_layer entry",
        )
        self.assertTrue(duplicate["completePrepareLayerCodeHashMatched"])
        self.assertFalse(duplicate["hardwareWatchpointInstalled"])
        self.assertFalse(duplicate["causalWriterOutcomeObserved"])
        forwarding = self.document["nestedModuleCallbackCaptureCorrection"]
        self.assertEqual(forwarding["runID"], 31026257919)
        self.assertEqual(
            forwarding["captureTargetStopReason"],
            "breakpoint 3.1 at CA::Rect::apply_transform +200",
        )
        self.assertTrue(forwarding["sharedPrepareEntryWorked"])
        self.assertEqual(forwarding["activeEpochMarkerHitCount"], 3)
        self.assertFalse(forwarding["hardwareWatchpointInstalled"])
        self.assertFalse(forwarding["causalWriterOutcomeObserved"])
        unwind = self.document["unwoundRegisterDepthCaptureCorrection"]
        self.assertEqual(unwind["runID"], 31026802793)
        self.assertTrue(unwind["captureTargetExitedNormally"])
        self.assertTrue(unwind["inheritedFrameWriterGatePassed"])
        self.assertEqual(unwind["inheritedSelectedStructuralPrepareDepth"], 4)
        self.assertEqual(unwind["inheritedSelectedPrepareFrameIndices"], [0, 1, 2, 3])
        self.assertEqual(unwind["rejectedEpochDepthCount"], 13)
        self.assertFalse(unwind["hardwareWatchpointInstalled"])
        self.assertFalse(unwind["causalWriterOutcomeObserved"])
        collision = self.document["sampledBreakpointHardwareWatchCollisionCorrection"]
        self.assertEqual(collision["runID"], 31029790210)
        self.assertTrue(collision["captureTargetExitedNormally"])
        self.assertEqual(collision["acceptedEpochRecordCount"], 3)
        self.assertEqual(collision["selectedWriterEventCount"], 7)
        self.assertEqual(collision["selectedDistinctAggregateCount"], 6)
        self.assertTrue(
            collision["inheritedSelectedSuffixEndsAtRequiredPaddedIntermediate"]
        )
        self.assertFalse(collision["inheritedSelectedSuffixClosesAtFinalMarker"])
        self.assertTrue(collision["requiredPaddedIntermediateMissingFromActiveStates"])
        self.assertEqual(
            collision["knownSampledWriterOffsetMissingFromActiveEvents"], -89720
        )
        self.assertFalse(collision["knownAggregateStateTransferGatePassed"])
        self.assertFalse(collision["completeCausalWriterListProved"])
        self.assertFalse(collision["scientificOutcomeChanged"])
        contract = self.document["traceContract"]
        self.assertEqual(contract["rawTraceSchemaVersion"], 3)
        self.assertEqual(contract["sealedValidatorSchemaVersion"], 3)
        self.assertEqual(contract["identityFrameRegisterNames"], ["x19", "x29", "pc"])
        self.assertEqual(
            contract["selectionFrameRegisterNames"],
            ["x19", "x28", "x29", "pc"],
        )
        self.assertEqual(
            contract["retainedControlBreakpointNames"],
            [
                "zeroInitializationAfter",
                "sourceLaterHandle",
                "recursivePrepareReturn",
            ],
        )
        coalescing = self.document["hardwareWatchCallbackCoalescingCorrection"]
        self.assertEqual(coalescing["runID"], 31034880031)
        self.assertTrue(coalescing["captureTargetExitedNormally"])
        self.assertTrue(coalescing["allNonEpochSampledWriterBreakpointsRetired"])
        self.assertEqual(coalescing["acceptedEpochRecordCount"], 7)
        self.assertEqual(
            coalescing["selectedSourceKnownDepthFourEpochOrdinal"], 7
        )
        self.assertEqual(
            coalescing["coalescedFirstStoreRelativeToPrepareLayer"], -89724
        )
        self.assertEqual(
            coalescing["coalescedSecondStoreRelativeToPrepareLayer"], -89704
        )
        self.assertEqual(
            coalescing["singleReportedStopRelativeToPrepareLayer"], -89700
        )
        self.assertTrue(coalescing["hardwareWatchCallbackCoalescingProved"])
        self.assertFalse(coalescing["completeArchitecturalStoreSequenceProved"])
        result_path = REPOSITORY_ROOT / coalescing["resultPath"]
        self.assertEqual(sha256(result_path), coalescing["resultSHA256"])
        outcome = self.document["runtimeOutcomeFrozenBeforeRun"]
        self.assertEqual(outcome["runID"], 31034880031)
        self.assertFalse(outcome["knownAggregateStateTransferGatePassed"])
        self.assertFalse(outcome["completeCausalWriterListProved"])
        self.assertFalse(outcome["productionShaderAuthorized"])
        forbidden = "\n".join(self.document["notAuthorizedBeforeAcceptance"])
        self.assertIn("production shader", forbidden)
        self.assertIn("parity", forbidden)
        self.assertIn("fixed number", forbidden)


if __name__ == "__main__":
    unittest.main()
