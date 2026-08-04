#!/usr/bin/env python3
"""Tests for the preregistered preconvergence crop-writer retry."""

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
PREREGISTRATION = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_capture_backdrop_writer_trace_preconvergence_retry_preregistration.json"
    ).read_text(encoding="utf-8")
)
FAILED_RESULT = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_capture_backdrop_writer_trace_callback_failure_result.json"
    ).read_text(encoding="utf-8")
)


class CaptureBackdropWriterTracePreconvergenceRetryTests(unittest.TestCase):
    def test_callback_failure_is_retained_without_writer_event_claim(self):
        opened = PREREGISTRATION["openedFailedRun"]
        callback = FAILED_RESULT["openedCallbackFailure"]
        conclusion = FAILED_RESULT["conclusion"]
        self.assertEqual(opened["runID"], 30779563755)
        self.assertFalse(opened["captureTargetExitedNormally"])
        self.assertFalse(opened["transitionTimelinePresent"])
        self.assertEqual(opened["watchpointCount"], 4)
        self.assertEqual(opened["eventCount"], 0)
        self.assertEqual(callback["AppleLLDBCallbackArgumentCount"], 3)
        self.assertEqual(callback["harnessCallbackArgumentCount"], 2)
        self.assertFalse(callback["firstStopClassifiedAsCropWriter"])
        self.assertFalse(conclusion["privateWriterPCsCaptured"])
        self.assertFalse(conclusion["productionShaderAuthorized"])

    def test_preconvergence_selection_is_frozen_from_opened_sequence(self):
        sequence = PREREGISTRATION["openedCandidateSequence"]
        acceptance = PREREGISTRATION["acceptance"]
        self.assertEqual(sequence["candidateCount"], 14)
        self.assertEqual(sequence["ownerEqualsLayerStateRectangleCount"], 14)
        self.assertEqual(sequence["sourceEqualsLayerStateRectangleCount"], 1)
        self.assertEqual(sequence["firstSourceEqualsLayerStateCandidateIndex"], 14)
        self.assertEqual(sequence["distinctSourceAddressCount"], 2)
        self.assertEqual(sequence["candidateOneLayerStateReappearsAtCandidate"], 11)
        self.assertTrue(acceptance["selectedCandidatePointerChainExact"])
        self.assertTrue(acceptance["selectedCandidateOwnerEqualsLayerStateRectangle"])
        self.assertTrue(
            acceptance["selectedCandidateSourceDiffersFromLayerStateRectangle"]
        )

    def test_callback_and_watchpoint_identity_corrections_are_bounded(self):
        delta = PREREGISTRATION["frozenRetryDelta"]
        hardware = PREREGISTRATION["hardwareIndexCorrection"]
        acceptance = PREREGISTRATION["acceptance"]
        self.assertEqual(delta["traceSchemaVersionAfter"], 3)
        self.assertEqual(delta["watchpointCallbackArgumentCountAfter"], 3)
        self.assertFalse(delta["thirdCallbackArgumentRead"])
        self.assertFalse(delta["thirdCallbackArgumentMutated"])
        self.assertEqual(hardware["observedValueForEveryWatchpoint"], -1)
        self.assertIn("deprecated", hardware["officialContract"])
        self.assertTrue(acceptance["watchpointIDsDistinct"])
        self.assertEqual(acceptance["deprecatedHardwareIndexValue"], -1)
        self.assertEqual(acceptance["watchpointCount"], 4)
        self.assertEqual(acceptance["maximumTotalEventCount"], 24)
        for name, value in delta.items():
            if name.endswith("Changed"):
                with self.subTest(name=name):
                    self.assertFalse(value)

    def test_apple_capture_inputs_and_quality_lock_are_unchanged(self):
        capture = PREREGISTRATION["capture"]
        acceptance = PREREGISTRATION["acceptance"]
        self.assertEqual(
            capture["workflowInput"]["capture_mode"], "allocation-path-isolation"
        )
        self.assertEqual(capture["totalInterventionCount"], 114)
        self.assertEqual(capture["producerInput"], "unmodified Apple input")
        self.assertFalse(capture["rawStageDumps"])
        self.assertFalse(capture["shaderMutation"])
        self.assertFalse(acceptance["publicCropRuleRecoveredByCaptureAlone"])
        self.assertFalse(acceptance["productionShaderAuthorized"])

    def test_retry_implementation_snapshot_and_unchanged_inputs(self):
        frozen = PREREGISTRATION["frozenImplementation"]
        historical = {
            "lldbTraceHarnessSHA256": (
                "749c4f33d909c482609e1ce9a247c0e0f02d2c5b45882e04a452ba968201ac5c"
            ),
            "lldbTraceHarnessSourceTestSHA256": (
                "527e17de02b0e7a4826251ebc0bcb029befdc24f70022ac9601493eb17fd5218"
            ),
            "sealedTraceValidatorSHA256": (
                "8e19b714831040ad72908f85c7dbcd115a1d6d0bb22050795a3546244c169f2c"
            ),
            "sealedTraceValidatorTestSHA256": (
                "0bc935e876f14ab26ccbfc6d299be0143db396f232e11f938c7a5d6d0b4e188c"
            ),
        }
        for name, digest in historical.items():
            with self.subTest(name=name):
                self.assertEqual(frozen[name], digest)
        files = {
            "callbackFailureResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_capture_backdrop_writer_trace_callback_failure_result.json",
            "workflowSHA256": REPOSITORY_ROOT
            / ".github/workflows/transition-introspect.yml",
            "productionShaderSHA256": REPOSITORY_ROOT.parent / "shaders/frag.glsl",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(), frozen[name]
                )

    def test_writer_semantics_and_parity_remain_unclaimed(self):
        unclaimed = PREREGISTRATION["notClaimed"]
        self.assertIn(
            "that the observed LayerNode deletion stop is a crop writer",
            unclaimed,
        )
        self.assertIn(
            "that Apple Liquid Glass parity has been achieved",
            unclaimed,
        )


if __name__ == "__main__":
    unittest.main()
