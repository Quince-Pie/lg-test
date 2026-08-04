#!/usr/bin/env python3
"""Tests for the opened failed-closed LayerShapes late-arm result."""

import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
RESULT = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_layer_shapes_merge_late_arm_result.json"
    ).read_text(encoding="utf-8")
)


class LayerShapesMergeLateArmResultTests(unittest.TestCase):
    def test_failed_workflow_preserves_successful_capture_and_static_gates(self):
        run = RESULT["run"]
        gates = RESULT["successfulStaticGates"]
        self.assertEqual(run["runID"], 30950358261)
        self.assertEqual(run["workflowConclusion"], "failure")
        self.assertEqual(run["captureStepOutcome"], "success")
        self.assertTrue(run["captureTargetExitedNormally"])
        self.assertEqual(run["pathIsolationValidatorOutcome"], "success")
        self.assertEqual(run["inputClampValidatorOutcome"], "success")
        self.assertEqual(run["mergeTraceValidatorOutcome"], "failure")
        self.assertEqual(run["artifactUploadOutcome"], "success")
        self.assertEqual(gates["mergeCallOffset"], 0x32C0)
        self.assertEqual(gates["mergeTargetRelativeToPrepareLayer"], -0xAA0)
        self.assertEqual(gates["rawTraceFailureCount"], 0)

    def test_exact_union_bounds_target_and_core_float_union_are_opened(self):
        helper = RESULT["openedMergeHelper"]
        union = helper["floatingRectangleUnion"]
        self.assertEqual(
            helper["resolvedName"],
            "CA::Render::Updater::LayerShapes::union_bounds(CA::Rect const&, bool)",
        )
        self.assertEqual(helper["symbolByteCount"], 404)
        self.assertEqual(
            helper["symbolCodeSHA256"],
            "246257a9bc1a608f59dbc07345397a8851b49528c59407eb775e9b9895a2c4b7",
        )
        self.assertEqual(union["instructionRange"], [44, 132])
        self.assertEqual(
            union["decisiveInstructions"][-1],
            {"offset": 132, "instruction": "stp q0, q1, [x20]"},
        )
        self.assertTrue(helper["coreFloatingUnionRecoveredFromInstructions"])
        self.assertFalse(helper["selectedSourcePreAndPostReplayAvailable"])

    def test_zero_hits_prove_the_late_arming_order_failed_closed(self):
        failure = RESULT["failedProspectiveGate"]
        self.assertEqual(failure["rawFailureCount"], 0)
        self.assertEqual(failure["mergeCallSiteHitCount"], 0)
        self.assertEqual(failure["selectedSourceCallCount"], 0)
        self.assertEqual(failure["completeRecordCount"], 0)
        self.assertEqual(failure["validatorFailure"], "merge record bounds differ")
        self.assertIn("already returned", failure["rootCause"])

    def test_retry_requires_early_direct_and_dynamic_alternate_capture(self):
        changes = RESULT["nextEvidenceBoundary"]["requiredChanges"]
        self.assertTrue(any("before the current invocation" in item for item in changes))
        self.assertTrue(any("x19+1312" in item for item in changes))
        self.assertTrue(any("selected-source direct pair" in item for item in changes))
        self.assertFalse(RESULT["nextEvidenceBoundary"]["productionShaderAuthorized"])
        self.assertIn(
            "that Apple Liquid Glass parity has been achieved",
            RESULT["notClaimed"],
        )


if __name__ == "__main__":
    unittest.main()
