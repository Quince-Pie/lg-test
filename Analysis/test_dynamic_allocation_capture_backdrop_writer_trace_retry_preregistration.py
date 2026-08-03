#!/usr/bin/env python3
"""Tests for the unchanged LLDB crop-writer trace compatibility retry."""

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
PREREGISTRATION = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_capture_backdrop_writer_trace_retry_preregistration.json"
    ).read_text(encoding="utf-8")
)
FAILED_RESULT = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_capture_backdrop_writer_trace_failed_run_result.json"
    ).read_text(encoding="utf-8")
)


class CaptureBackdropWriterTraceRetryPreregistrationTests(unittest.TestCase):
    def test_failed_run_is_retained_without_promoting_writer_evidence(self):
        opened = PREREGISTRATION["openedFailedRun"]
        conclusion = FAILED_RESULT["conclusion"]
        self.assertEqual(opened["runID"], 30776569148)
        self.assertEqual(opened["failureCount"], 1)
        self.assertEqual(opened["watchpointCount"], 0)
        self.assertEqual(opened["eventCount"], 0)
        self.assertFalse(opened["captureBackdropCodeHashProspectivelyProven"])
        self.assertTrue(conclusion["AppleCaptureIntegrityPassed"])
        self.assertFalse(conclusion["hardwareWatchpointsArmed"])
        self.assertFalse(conclusion["privateWriterPCsCaptured"])
        self.assertFalse(conclusion["productionShaderAuthorized"])

    def test_retry_changes_only_diagnostic_file_spec_path_formatting(self):
        delta = PREREGISTRATION["frozenRetryDelta"]
        self.assertIn("GetDirectory()/GetFilename()", delta["allowedSourceChange"])
        for name, value in delta.items():
            if name.endswith("Changed"):
                with self.subTest(name=name):
                    self.assertFalse(value)

    def test_capture_and_watchpoint_bounds_are_unchanged(self):
        capture = PREREGISTRATION["capture"]
        acceptance = PREREGISTRATION["acceptance"]
        self.assertEqual(capture["totalInterventionCount"], 114)
        self.assertEqual(capture["operandEvidenceSchemaVersion"], 5)
        self.assertEqual(acceptance["hardwareWatchpointCount"], 4)
        self.assertEqual(acceptance["watchpointByteCount"], 8)
        self.assertEqual(acceptance["maximumHitsPerWatchpoint"], 6)
        self.assertEqual(acceptance["maximumTotalEventCount"], 24)
        self.assertEqual(acceptance["maximumBacktraceFrameCount"], 32)
        self.assertFalse(acceptance["publicCropRuleRecoveredByCaptureAlone"])
        self.assertFalse(acceptance["productionShaderAuthorized"])

    def test_retry_implementation_hashes_match_current_files(self):
        frozen = PREREGISTRATION["frozenImplementation"]
        files = {
            "failedRunResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_capture_backdrop_writer_trace_failed_run_result.json",
            "lldbTraceHarnessSHA256": ANALYSIS_ROOT
            / "capture_backdrop_writer_trace_lldb.py",
            "lldbTraceHarnessSourceTestSHA256": ANALYSIS_ROOT
            / "test_capture_backdrop_writer_trace_lldb_source.py",
            "sealedTraceValidatorSHA256": ANALYSIS_ROOT
            / "validate_capture_backdrop_writer_trace.py",
            "sealedTraceValidatorTestSHA256": ANALYSIS_ROOT
            / "test_validate_capture_backdrop_writer_trace.py",
            "workflowSHA256": REPOSITORY_ROOT
            / ".github/workflows/transition-introspect.yml",
            "productionShaderSHA256": REPOSITORY_ROOT.parent / "shaders/frag.glsl",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(), frozen[name]
                )


if __name__ == "__main__":
    unittest.main()
