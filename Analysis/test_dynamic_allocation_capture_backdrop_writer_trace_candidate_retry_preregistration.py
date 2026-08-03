#!/usr/bin/env python3
"""Tests for the bounded exact-candidate crop-writer trace retry."""

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
PREREGISTRATION = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_capture_backdrop_writer_trace_candidate_retry_preregistration.json"
    ).read_text(encoding="utf-8")
)
FAILED_RESULT = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_capture_backdrop_writer_trace_late_mismatch_result.json"
    ).read_text(encoding="utf-8")
)


class CaptureBackdropWriterTraceCandidateRetryPreregistrationTests(unittest.TestCase):
    def test_second_failed_run_is_retained_without_writer_evidence(self):
        opened = PREREGISTRATION["openedFailedRun"]
        failure = FAILED_RESULT["openedFailure"]
        conclusion = FAILED_RESULT["conclusion"]
        self.assertEqual(opened["runID"], 30778280502)
        self.assertEqual(opened["failureStage"], "capture_backdrop-late")
        self.assertTrue(opened["captureBackdropCodeHashProspectivelyProven"])
        self.assertTrue(opened["objectPointerChainPassedBeforeFailure"])
        self.assertFalse(opened["mismatchingRectangleValuesCommitted"])
        self.assertEqual(failure["watchpointCount"], 0)
        self.assertEqual(failure["eventCount"], 0)
        self.assertFalse(conclusion["privateWriterPCsCaptured"])
        self.assertFalse(conclusion["productionShaderAuthorized"])

    def test_retry_preserves_exact_selection_and_watchpoint_gates(self):
        delta = PREREGISTRATION["frozenRetryDelta"]
        acceptance = PREREGISTRATION["acceptance"]
        self.assertEqual(delta["traceSchemaVersionAfter"], 2)
        self.assertEqual(delta["maximumLateCandidateCount"], 512)
        self.assertEqual(delta["maximumRetainedRejectedCandidateDiagnostics"], 16)
        for name, value in delta.items():
            if name.endswith("Changed"):
                with self.subTest(name=name):
                    self.assertFalse(value)
        self.assertTrue(acceptance["selectedCandidatePointerChainExact"])
        self.assertTrue(acceptance["selectedCandidateMirroredRectanglesExact"])
        self.assertEqual(acceptance["hardwareWatchpointCount"], 4)
        self.assertEqual(acceptance["maximumTotalEventCount"], 24)
        self.assertFalse(acceptance["publicCropRuleRecoveredByCaptureAlone"])
        self.assertFalse(acceptance["productionShaderAuthorized"])

    def test_apple_capture_inputs_remain_unchanged(self):
        capture = PREREGISTRATION["capture"]
        self.assertEqual(
            capture["workflowInput"]["capture_mode"], "allocation-path-isolation"
        )
        self.assertEqual(capture["totalInterventionCount"], 114)
        self.assertEqual(capture["operandEvidenceSchemaVersion"], 5)
        self.assertEqual(capture["producerInput"], "unmodified Apple input")
        self.assertFalse(capture["rawStageDumps"])
        self.assertFalse(capture["shaderMutation"])

    def test_retry_implementation_hashes_match_current_files(self):
        frozen = PREREGISTRATION["frozenImplementation"]
        files = {
            "lateMismatchResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_capture_backdrop_writer_trace_late_mismatch_result.json",
            "workflowSHA256": REPOSITORY_ROOT
            / ".github/workflows/transition-introspect.yml",
            "productionShaderSHA256": REPOSITORY_ROOT.parent / "shaders/frag.glsl",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(), frozen[name]
                )
        historical_hashes = {
            "lldbTraceHarnessSHA256": "a197b1461e33cc7630e9bc408f78a557ab101b87a823414be5a07502942ff42d",
            "lldbTraceHarnessSourceTestSHA256": "a3aa51bde9bd584d437dcf044246fc95a141f38873e803e183ce5509f937ab1b",
            "sealedTraceValidatorSHA256": "ae4448603b15cac2c3d9f169c3c6b936cd86052e4c29303efe74e12a1eba8e3f",
            "sealedTraceValidatorTestSHA256": "86578201b1cb71581ba4f23f5db6c90a55180078ed1aa47eb34f1bdee3120455",
        }
        for name, digest in historical_hashes.items():
            with self.subTest(name=name):
                self.assertEqual(frozen[name], digest)

    def test_parity_and_public_crop_rule_remain_unclaimed(self):
        unclaimed = PREREGISTRATION["notClaimed"]
        self.assertIn(
            "that Apple Liquid Glass parity has been achieved",
            unclaimed,
        )
        self.assertIn(
            "which mirrored rectangle differed at the failed run's first late invocation",
            unclaimed,
        )


if __name__ == "__main__":
    unittest.main()
