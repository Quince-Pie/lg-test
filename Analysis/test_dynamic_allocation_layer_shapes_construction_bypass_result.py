#!/usr/bin/env python3
"""Tests for the opened failed-closed LayerShapes branch-bypass result."""

import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
RESULT = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_layer_shapes_construction_bypass_result.json"
    ).read_text(encoding="utf-8")
)


class LayerShapesConstructionBypassResultTests(unittest.TestCase):
    def test_capture_existing_validators_and_artifact_succeeded(self):
        run = RESULT["run"]
        self.assertEqual(run["runID"], 30953581966)
        self.assertEqual(run["workflowConclusion"], "failure")
        self.assertEqual(run["captureStepOutcome"], "success")
        self.assertTrue(run["captureTargetExitedNormally"])
        self.assertEqual(run["pathIsolationValidatorOutcome"], "success")
        self.assertEqual(run["inputClampValidatorOutcome"], "success")
        self.assertEqual(run["constructionTraceValidatorOutcome"], "failure")
        self.assertEqual(run["artifactUploadOutcome"], "success")

    def test_static_code_source_selection_and_callback_integrity_passed(self):
        gates = RESULT["successfulStaticAndSelectionGates"]
        self.assertEqual(gates["prepareLayerSymbolByteCount"], 40128)
        self.assertEqual(gates["directCallBreakpointID"], 3)
        self.assertEqual(gates["alternateAfterBreakpointID"], 6)
        self.assertEqual(gates["selectedLateCandidateIndex"], 1)
        self.assertTrue(gates["selectedObjectChainExact"])
        self.assertTrue(gates["selectedPreconvergenceExact"])
        self.assertEqual(gates["rawTraceFailureCount"], 0)

    def test_both_early_armed_branch_sites_have_exactly_zero_hits(self):
        outcome = RESULT["openedBranchOutcome"]
        self.assertEqual(outcome["directCallSiteHitCount"], 0)
        self.assertEqual(outcome["directRecordCount"], 0)
        self.assertEqual(outcome["pendingDirectRecordCount"], 0)
        self.assertEqual(outcome["alternateStoreHitCount"], 0)
        self.assertEqual(outcome["alternateRecordCount"], 0)
        self.assertEqual(outcome["pendingAlternateRecordCount"], 0)
        self.assertEqual(outcome["rejectedAlternateStoreCount"], 0)
        self.assertTrue(
            outcome["constructionBreakpointsWereInstalledBeforeSourceSelection"]
        )
        self.assertTrue(outcome["priorTemporalExplanationFalsified"])

    def test_next_probe_captures_full_code_and_real_path_markers(self):
        boundary = RESULT["nextEvidenceBoundary"]
        changes = boundary["requiredChanges"]
        self.assertTrue(any("complete prepare_layer symbol" in item for item in changes))
        self.assertTrue(any("callback PC" in item for item in changes))
        self.assertTrue(any("marker breakpoints" in item for item in changes))
        self.assertTrue(any("x19+656 writes" in item for item in changes))
        self.assertFalse(boundary["productionShaderAuthorized"])

    def test_parity_and_shader_authority_remain_explicitly_unclaimed(self):
        self.assertIn(
            "that Walle may change its production shader", RESULT["notClaimed"]
        )
        self.assertIn(
            "that Apple Liquid Glass parity has been achieved",
            RESULT["notClaimed"],
        )


if __name__ == "__main__":
    unittest.main()
