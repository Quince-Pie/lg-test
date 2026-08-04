#!/usr/bin/env python3
"""Integrity tests for the live-qualified writer preregistration."""

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
PREREGISTRATION = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_prepare_layer_live_writer_preregistration.json"
    ).read_text(encoding="utf-8")
)
OPENED_STALE_RESULT = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_prepare_layer_full_path_stale_watchpoint_result.json"
    ).read_text(encoding="utf-8")
)


class PrepareLayerLiveWriterPreregistrationTests(unittest.TestCase):
    def test_failed_full_path_run_is_the_exact_antecedent(self):
        opened = PREREGISTRATION["openedEvidenceBoundary"]
        stale = OPENED_STALE_RESULT["openedWatchpointOutcome"]
        self.assertEqual(opened["runID"], 30957433164)
        self.assertEqual(
            opened["headSHA"],
            "e67f506a425ac07b39f49720a882bd1eec940601",
        )
        self.assertEqual(opened["workflowConclusion"], "failure")
        self.assertTrue(opened["captureTargetExitedNormally"])
        self.assertEqual(opened["rawTraceFailureCount"], 0)
        self.assertEqual(opened["prepareLayerFullCodeByteCount"], 40128)
        self.assertEqual(opened["earlyConstructionRegionHitCount"], 0)
        self.assertEqual(opened["watchpointEventWithPrepareLayerCount"], 0)
        self.assertFalse(opened["actualSelectedAggregateWriterCaptured"])
        self.assertFalse(stale["actualSelectedAggregateWriterCaptured"])

    def test_contract_arms_live_and_qualifies_exact_unwound_roles(self):
        contract = PREREGISTRATION["traceContract"]
        self.assertEqual(contract["rawTraceSchemaVersion"], 1)
        self.assertEqual(contract["sealedValidatorSchemaVersion"], 1)
        self.assertEqual(contract["prepareLayerSymbolByteCount"], 40128)
        self.assertEqual(contract["liveArmMarkerOffset"], 0x3EF0)
        self.assertEqual(contract["aggregateOffset"], 656)
        self.assertEqual(contract["watchpointByteCount"], 8)
        self.assertEqual(contract["maximumRawWatchpointHitCount"], 8192)
        self.assertEqual(contract["maximumQualifiedWatchpointEventCount"], 24)
        self.assertEqual(
            contract["prepareFrameRegisterNames"],
            ["x19", "x28", "x29", "x30", "sp", "pc"],
        )
        design = PREREGISTRATION["captureDesign"]
        self.assertIn("never retrospectively", design["watchpointArmRule"])
        self.assertIn("unwound x19", design["watchpointQualificationRule"])
        self.assertIn("unwound x28", design["watchpointQualificationRule"])

    def test_acceptance_rejects_stale_stack_reuse_and_keeps_semantics_sealed(self):
        acceptance = PREREGISTRATION["acceptance"]
        self.assertTrue(acceptance["exactPrepareLayerEntryRequired"])
        self.assertTrue(acceptance["completePrepareLayerCodeRequired"])
        self.assertTrue(acceptance["retrospectiveWatchpointArmForbidden"])
        self.assertTrue(acceptance["markerInitialBytesMustMatch"])
        self.assertTrue(acceptance["exactPrepareFrameAncestryRequired"])
        self.assertTrue(acceptance["unwoundRoleAndSourceMustMatch"])
        self.assertTrue(acceptance["unrelatedStackReuseCannotQualify"])
        self.assertEqual(acceptance["minimumChangedQualifiedEventCount"], 1)
        self.assertTrue(acceptance["fullWriterOperandsRequired"])
        self.assertTrue(acceptance["zeroTraceFailuresRequired"])
        self.assertFalse(acceptance["writerSemanticsMayBeClaimed"])
        self.assertFalse(acceptance["productionShaderMayChange"])

    def test_frozen_implementation_hashes_match_current_files(self):
        frozen = PREREGISTRATION["frozenImplementation"]
        files = {
            "openedStaleResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_prepare_layer_full_path_stale_watchpoint_result.json",
            "openedStaleResultTestSHA256": ANALYSIS_ROOT
            / "test_dynamic_allocation_prepare_layer_full_path_stale_watchpoint_result.py",
            "lldbLiveWriterHarnessSHA256": ANALYSIS_ROOT
            / "capture_prepare_layer_live_writer_trace_lldb.py",
            "lldbFullPathBaseHarnessSHA256": ANALYSIS_ROOT
            / "capture_prepare_layer_full_path_trace_lldb.py",
            "lldbLiveWriterHarnessSourceTestSHA256": ANALYSIS_ROOT
            / "test_capture_prepare_layer_live_writer_trace_lldb_source.py",
            "sealedLiveWriterValidatorSHA256": ANALYSIS_ROOT
            / "validate_prepare_layer_live_writer_trace.py",
            "sealedLiveWriterValidatorTestSHA256": ANALYSIS_ROOT
            / "test_validate_prepare_layer_live_writer_trace.py",
            "workflowSHA256": REPOSITORY_ROOT
            / ".github/workflows/prepare-layer-live-writer-introspect.yml",
            "developmentFlakeSHA256": REPOSITORY_ROOT / "flake.nix",
            "registrationTestSHA256": ANALYSIS_ROOT
            / "test_dynamic_allocation_prepare_layer_live_writer_preregistration.py",
            "productionShaderSHA256": REPOSITORY_ROOT.parent
            / "shaders/frag.glsl",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(), frozen[name]
                )

    def test_frozen_capture_program_and_validator_dependencies_match(self):
        for section in ("frozenCaptureProgram", "frozenValidatorDependencies"):
            for item in PREREGISTRATION[section]:
                with self.subTest(section=section, path=item["path"]):
                    path = REPOSITORY_ROOT / item["path"]
                    self.assertEqual(
                        hashlib.sha256(path.read_bytes()).hexdigest(),
                        item["sha256"],
                    )

    def test_existing_capture_and_product_shader_are_unchanged(self):
        delta = PREREGISTRATION["frozenDelta"]
        self.assertTrue(delta["separateLiveWriterWorkflowAdded"])
        self.assertTrue(delta["separateLiveWriterHarnessAdded"])
        self.assertTrue(delta["separateLiveWriterValidatorAdded"])
        for name, changed in delta.items():
            if name.endswith("Changed"):
                with self.subTest(name=name):
                    self.assertFalse(changed)

    def test_parity_and_run_count_remain_explicitly_unclaimed(self):
        not_claimed = PREREGISTRATION["notClaimed"]
        self.assertIn(
            "that the actual selected aggregate writer instruction is known",
            not_claimed,
        )
        self.assertIn(
            "that the complete public crop-construction rule is recovered",
            not_claimed,
        )
        self.assertIn("that Walle may change its production shader", not_claimed)
        self.assertIn(
            "that Apple Liquid Glass parity has been achieved",
            not_claimed,
        )
        self.assertIn(
            "that a fixed number of later CI runs will be sufficient",
            not_claimed,
        )


if __name__ == "__main__":
    unittest.main()
