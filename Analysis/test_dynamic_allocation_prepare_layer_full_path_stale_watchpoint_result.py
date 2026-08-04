#!/usr/bin/env python3
"""Tests for the opened failed full-path/stale-watchpoint result."""

import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
RESULT = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_prepare_layer_full_path_stale_watchpoint_result.json"
    ).read_text(encoding="utf-8")
)


class PrepareLayerFullPathStaleWatchpointResultTests(unittest.TestCase):
    def test_capture_and_existing_gates_succeeded_but_full_gate_failed(self):
        run = RESULT["run"]
        self.assertEqual(run["runID"], 30957433164)
        self.assertEqual(run["headSHA"], "e67f506a425ac07b39f49720a882bd1eec940601")
        self.assertEqual(run["workflowConclusion"], "failure")
        self.assertEqual(run["captureStepOutcome"], "success")
        self.assertTrue(run["captureTargetExitedNormally"])
        self.assertEqual(run["pathIsolationValidatorOutcome"], "success")
        self.assertEqual(run["inputClampValidatorOutcome"], "success")
        self.assertEqual(run["fullPathValidatorOutcome"], "failure")
        self.assertEqual(run["artifactUploadOutcome"], "success")

    def test_complete_function_and_selection_gates_are_exact(self):
        gates = RESULT["successfulStaticAndSelectionGates"]
        self.assertTrue(gates["prepareLayerCallbackPCEqualsSymbolStart"])
        self.assertTrue(gates["prepareLayerBreakpointLocationEqualsSymbolStart"])
        self.assertEqual(gates["prepareLayerSymbolByteCount"], 40128)
        self.assertEqual(
            gates["prepareLayerFullCodeSHA256"],
            "fe58001369708e0276599f26865be03fdf1dd2348524f92a72c1427be8d1817c",
        )
        self.assertTrue(gates["allFivePriorCodeWindowsExact"])
        self.assertTrue(gates["markersInstalledBeforeSourceSelection"])
        self.assertTrue(gates["selectedObjectChainExact"])
        self.assertTrue(gates["selectedPreconvergenceExact"])
        self.assertEqual(gates["rawTraceFailureCount"], 0)

    def test_path_gate_failed_only_at_preregistered_record_bound(self):
        path = RESULT["openedPathOutcome"]
        self.assertTrue(all(value == 0 for value in path["earlyConstructionMarkerHitCounts"].values()))
        self.assertEqual(path["laterMarkerHitCounts"]["sourceLaterHandle"], 129)
        self.assertEqual(path["laterMarkerHitCounts"]["sourceLaterIntegerTail"], 18)
        self.assertEqual(path["retainedMarkerRecordCount"], 402)
        self.assertEqual(path["selectedMarkerRecordCount"], 402)
        self.assertEqual(set(path["discardedMarkerCounts"].values()), {1})
        self.assertIn("marker accounting differs", path["localValidatorFailure"])

    def test_retrospective_watchpoint_is_proven_stale_not_a_writer(self):
        watch = RESULT["openedWatchpointOutcome"]
        self.assertEqual(watch["armMode"], "retrospective-source-selection")
        self.assertNotEqual(
            watch["armMarkerAggregateOriginHex"], watch["watchpointInitialHexAtLaterSourceSelection"]
        )
        self.assertTrue(watch["firstLiveRoleBaseDiffersFromRetrospectiveRoleBase"])
        self.assertEqual(watch["rawWatchpointEventCount"], 24)
        self.assertEqual(watch["rawChangedEventCount"], 6)
        self.assertEqual(watch["eventWithPrepareLayerInBacktraceCount"], 0)
        self.assertFalse(watch["actualSelectedAggregateWriterCaptured"])

    def test_complete_code_narrows_exact_static_mutation_sites(self):
        code = RESULT["openedCompleteCodeBoundary"]
        self.assertEqual(
            code["directOverlappingStoreInstructionOffsets"],
            [0xB58, 0xB5C, 0x33F0, 0x3970, 0x6748],
        )
        self.assertEqual(
            code["directUnionBoundsCallOffsetsWithX19Plus656Destination"],
            [0xCF8, 0x14F0, 0x1E84, 0x1F24, 0x23EC, 0x24EC, 0x32C0, 0x6D64],
        )
        self.assertEqual(code["directUnionBoundsTargetRelativeToPrepareLayer"], -0xAA0)

    def test_next_probe_requires_live_selected_prepare_ancestry(self):
        changes = RESULT["nextEvidenceBoundary"]["requiredChanges"]
        self.assertTrue(any("remove retrospective" in item for item in changes))
        self.assertTrue(any("unwound x19 and x28" in item for item in changes))
        self.assertTrue(any("marker truncation" in item for item in changes))
        self.assertFalse(RESULT["nextEvidenceBoundary"]["productionShaderAuthorized"])

    def test_writer_policy_and_parity_remain_explicitly_unclaimed(self):
        not_claimed = RESULT["notClaimed"]
        self.assertIn(
            "that the actual selected aggregate writer instruction is known",
            not_claimed,
        )
        self.assertIn("that Walle may change its production shader", not_claimed)
        self.assertIn(
            "that Apple Liquid Glass parity has been achieved",
            not_claimed,
        )


if __name__ == "__main__":
    unittest.main()
