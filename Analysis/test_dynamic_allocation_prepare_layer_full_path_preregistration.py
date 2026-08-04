#!/usr/bin/env python3
"""Integrity tests for the full prepare_layer path/writer preregistration."""

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
PREREGISTRATION = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_prepare_layer_full_path_preregistration.json"
    ).read_text(encoding="utf-8")
)
OPENED_BYPASS = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_layer_shapes_construction_bypass_result.json"
    ).read_text(encoding="utf-8")
)


class PrepareLayerFullPathPreregistrationTests(unittest.TestCase):
    def test_failed_early_branch_probe_is_the_exact_antecedent(self):
        opened = PREREGISTRATION["openedEvidenceBoundary"]
        branch = OPENED_BYPASS["openedBranchOutcome"]
        self.assertEqual(opened["runID"], 30953581966)
        self.assertEqual(opened["headSHA"], "56459f06ad4ab16707955b3c175ca949bef9e6c1")
        self.assertEqual(opened["workflowConclusion"], "failure")
        self.assertTrue(opened["captureTargetExitedNormally"])
        self.assertEqual(opened["rawTraceFailureCount"], 0)
        self.assertEqual(opened["directCallSiteHitCount"], 0)
        self.assertEqual(opened["alternateStoreHitCount"], 0)
        self.assertTrue(opened["priorTemporalExplanationFalsified"])
        self.assertEqual(
            opened["directCallSiteHitCount"], branch["directCallSiteHitCount"]
        )
        self.assertEqual(
            opened["alternateStoreHitCount"], branch["alternateStoreHitCount"]
        )
        self.assertTrue(branch["priorTemporalExplanationFalsified"])

    def test_contract_captures_complete_code_and_actual_writer(self):
        contract = PREREGISTRATION["traceContract"]
        self.assertEqual(contract["rawTraceSchemaVersion"], 1)
        self.assertEqual(contract["sealedValidatorSchemaVersion"], 1)
        self.assertEqual(contract["prepareLayerSymbolByteCount"], 40128)
        self.assertEqual(
            [item["offset"] for item in contract["knownPrepareLayerWindows"]],
            [12764, 14064, 17944, 19212, 19216],
        )
        self.assertEqual(contract["aggregateOffset"], 656)
        self.assertEqual(contract["aggregateByteCount"], 32)
        self.assertEqual(contract["watchpointByteCount"], 8)
        self.assertEqual(contract["maximumWatchpointHitCount"], 24)
        self.assertEqual(contract["pathMarkerCount"], 13)
        self.assertEqual(
            contract["laterSelectedMarkerOffsets"], [16112, 19992, 21260, 21264]
        )

    def test_acceptance_keeps_both_watchpoint_arm_routes_and_fails_closed(self):
        acceptance = PREREGISTRATION["acceptance"]
        self.assertTrue(acceptance["exactPrepareLayerEntryRequired"])
        self.assertTrue(acceptance["completePrepareLayerCodeRequired"])
        self.assertTrue(acceptance["markersMustPrecedeSourceSelector"])
        self.assertTrue(acceptance["retrospectiveWatchpointArmAllowed"])
        self.assertTrue(acceptance["liveSelectedMarkerFallbackAllowed"])
        self.assertEqual(acceptance["minimumDistinctSelectedAggregateCount"], 3)
        self.assertEqual(acceptance["minimumChangedWatchpointEventCount"], 1)
        self.assertTrue(acceptance["fullWriterOperandsRequired"])
        self.assertTrue(acceptance["zeroTraceFailuresRequired"])

    def test_preregistered_implementation_hashes_match_current_files(self):
        frozen = PREREGISTRATION["frozenImplementation"]
        files = {
            "openedBypassResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_layer_shapes_construction_bypass_result.json",
            "openedBypassResultTestSHA256": ANALYSIS_ROOT
            / "test_dynamic_allocation_layer_shapes_construction_bypass_result.py",
            "lldbFullPathHarnessSHA256": ANALYSIS_ROOT
            / "capture_prepare_layer_full_path_trace_lldb.py",
            "lldbFullPathHarnessSourceTestSHA256": ANALYSIS_ROOT
            / "test_capture_prepare_layer_full_path_trace_lldb_source.py",
            "sealedFullPathValidatorSHA256": ANALYSIS_ROOT
            / "validate_prepare_layer_full_path_trace.py",
            "sealedFullPathValidatorTestSHA256": ANALYSIS_ROOT
            / "test_validate_prepare_layer_full_path_trace.py",
            "workflowSHA256": REPOSITORY_ROOT
            / ".github/workflows/prepare-layer-full-path-introspect.yml",
            "developmentFlakeSHA256": REPOSITORY_ROOT / "flake.nix",
            "registrationTestSHA256": ANALYSIS_ROOT
            / "test_dynamic_allocation_prepare_layer_full_path_preregistration.py",
            "productionShaderSHA256": REPOSITORY_ROOT.parent
            / "shaders/frag.glsl",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(), frozen[name]
                )

    def test_prior_successes_and_product_shader_are_unchanged(self):
        delta = PREREGISTRATION["frozenDelta"]
        self.assertTrue(delta["separateFullPathWorkflowAdded"])
        self.assertTrue(delta["separateFullPathHarnessAdded"])
        self.assertTrue(delta["separateFullPathValidatorAdded"])
        for name, changed in delta.items():
            if name.endswith("Changed"):
                with self.subTest(name=name):
                    self.assertFalse(changed)

    def test_semantics_transfer_and_product_parity_remain_sealed(self):
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


if __name__ == "__main__":
    unittest.main()
