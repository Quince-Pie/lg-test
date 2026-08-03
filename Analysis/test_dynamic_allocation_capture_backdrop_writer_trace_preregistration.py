#!/usr/bin/env python3
"""Tests for the preregistered private crop-writer trace."""

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
PREREGISTRATION = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_capture_backdrop_writer_trace_preregistration.json"
    ).read_text(encoding="utf-8")
)


class CaptureBackdropWriterTracePreregistrationTests(unittest.TestCase):
    def test_question_is_frozen_from_the_passing_upstream_capture(self):
        opened = PREREGISTRATION["openedUpstreamEvidence"]
        self.assertEqual(opened["runID"], 30773890196)
        self.assertEqual(opened["completeLiveOperandCaptureCount"], 114)
        self.assertEqual(opened["requiredReadMask"], "0x3fffffff")
        self.assertEqual(opened["selectedRectangleCrossObjectExactCount"], 114)
        self.assertEqual(opened["distinctLayerStateInputBoundsAtA0"], 83)
        self.assertEqual(opened["distinctSelectedRectanglesAtB0"], 9)
        self.assertEqual(opened["sameInputWithMultipleObservedOutputs"], 0)

    def test_trace_is_bounded_and_targets_all_four_private_fields(self):
        question = PREREGISTRATION["frozenQuestion"]
        acceptance = PREREGISTRATION["acceptance"]
        self.assertIn("source+0x50", question["watchpointRule"])
        self.assertIn("owner+0xe0", question["watchpointRule"])
        self.assertIn("owner+0x248", question["watchpointRule"])
        self.assertIn("layerState+0xb0", question["watchpointRule"])
        self.assertEqual(acceptance["hardwareWatchpointCount"], 4)
        self.assertEqual(acceptance["watchpointByteCount"], 8)
        self.assertEqual(acceptance["maximumHitsPerWatchpoint"], 6)
        self.assertEqual(acceptance["maximumTotalEventCount"], 24)
        self.assertEqual(acceptance["maximumBacktraceFrameCount"], 32)

    def test_ci_gate_cannot_open_semantics_or_authorize_shader(self):
        question = PREREGISTRATION["frozenQuestion"]
        acceptance = PREREGISTRATION["acceptance"]
        self.assertIn("semantics", question["semanticSeal"])
        self.assertFalse(acceptance["publicCropRuleRecoveredByCaptureAlone"])
        self.assertFalse(acceptance["productionShaderAuthorized"])
        self.assertIn(
            "that Apple Liquid Glass parity has been achieved",
            PREREGISTRATION["notClaimed"],
        )

    def test_quality_lock_remains_exact(self):
        frozen = PREREGISTRATION["frozenImplementation"]
        self.assertEqual(
            frozen["productionShaderSHA256"],
            "11f3dd2ab07bf41230f9b53fc4db7a9b788bd5300695a9d8a62b0ef741c9a2f3",
        )

    def test_successor_implementation_hashes_match_current_files(self):
        frozen = PREREGISTRATION["frozenImplementation"]
        files = {
            "postOpeningAnalyzerSHA256": ANALYSIS_ROOT
            / "analyze_dynamic_allocation_capture_backdrop_upstream_writer.py",
            "postOpeningResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_capture_backdrop_upstream_writer_result.json",
            "postOpeningAnalyzerTestSHA256": ANALYSIS_ROOT
            / "test_analyze_dynamic_allocation_capture_backdrop_upstream_writer.py",
            "lldbTraceHarnessSHA256": ANALYSIS_ROOT
            / "capture_backdrop_writer_trace_lldb.py",
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
