#!/usr/bin/env python3
"""Tests for the opened live-writer x28-timing failure result."""

import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
RESULT = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_prepare_layer_live_writer_x28_timing_result.json"
    ).read_text(encoding="utf-8")
)


class PrepareLayerLiveWriterX28TimingResultTests(unittest.TestCase):
    def test_capture_succeeded_but_live_writer_gate_failed(self):
        run = RESULT["run"]
        self.assertEqual(run["runID"], 30960697537)
        self.assertEqual(
            run["headSHA"],
            "65bc6a5d56f80fa65032a0b68524039c4e9bf5cc",
        )
        self.assertEqual(run["workflowConclusion"], "failure")
        self.assertEqual(run["captureStepOutcome"], "success")
        self.assertTrue(run["captureTargetExitedNormally"])
        self.assertEqual(run["captureTargetExitStatus"], 0)
        self.assertEqual(run["pathIsolationValidatorOutcome"], "success")
        self.assertEqual(run["inputClampValidatorOutcome"], "success")
        self.assertEqual(run["liveWriterValidatorOutcome"], "failure")
        self.assertEqual(run["artifactUploadOutcome"], "success")

    def test_live_marker_and_watchpoint_initial_value_are_exact(self):
        gates = RESULT["successfulStaticSelectionAndArmGates"]
        self.assertEqual(gates["prepareLayerSymbolByteCount"], 40128)
        self.assertEqual(
            gates["prepareLayerFullCodeSHA256"],
            "fe58001369708e0276599f26865be03fdf1dd2348524f92a72c1427be8d1817c",
        )
        self.assertTrue(gates["selectedObjectChainExact"])
        self.assertTrue(gates["selectedPreconvergenceExact"])
        self.assertEqual(gates["markerHitCount"], 2)
        self.assertEqual(gates["discardedMarkerHitCount"], 0)
        self.assertEqual(
            gates["liveSelectedMarkerAggregateOriginHex"],
            gates["watchpointInitialHex"],
        )
        self.assertTrue(gates["markerAndWatchpointInitialExact"])

    def test_raw_bound_opens_prepare_ancestry_but_no_qualified_event(self):
        watch = RESULT["openedWatchpointOutcome"]
        self.assertEqual(watch["rawWatchpointHitCount"], 8193)
        self.assertEqual(watch["maximumRawWatchpointHitCount"], 8192)
        self.assertEqual(watch["ignoredWatchpointHitCount"], 8192)
        self.assertEqual(watch["ignoredDiagnosticHitSum"], 8192)
        self.assertEqual(watch["unretainedIgnoredWatchpointHitCount"], 0)
        self.assertEqual(watch["ignoredPrepareFrameSeenCount"], 196)
        self.assertEqual(watch["qualifiedWatchpointHitCount"], 0)
        self.assertEqual(watch["rawTraceFailure"], "raw watchpoint hit bound exceeded")

    def test_exact_direct_writer_sites_are_decoded(self):
        groups = RESULT["openedPrepareAncestryWriterGroups"]
        direct = {
            group["stopPCRelativeToPrepareLayer"]: group
            for group in groups
            if "precedingWriterInstructionOffset" in group
        }
        self.assertEqual(set(direct), {0xB60, 0x3974})
        self.assertEqual(
            direct[0xB60]["precedingWriterInstruction"],
            "str q0, [x19, #656]",
        )
        self.assertEqual(
            direct[0x3974]["precedingWriterInstruction"],
            "stp q0, q1, [x19, #656]",
        )
        union = next(
            group for group in groups if "union_bounds" in group["function"]
        )
        self.assertEqual(union["stopPCRelativeToUnionHelper"], 0x84)
        self.assertEqual(union["hitCount"], 52)
        self.assertEqual(union["changedCount"], 39)

    def test_simultaneous_x28_rule_is_falsified_by_store_address(self):
        timing = RESULT["openedTimingConclusion"]
        self.assertTrue(timing["directWriterX19EqualsWatchedRoleAtStop"])
        self.assertTrue(timing["combinedQualificationStillFailed"])
        self.assertTrue(timing["directWriterX28DiffersFromSelectedSourceAtStop"])
        self.assertTrue(timing["selectedSourcePresentLaterAtMarker"])

    def test_next_probe_correlates_a_still_live_frame(self):
        boundary = RESULT["nextEvidenceBoundary"]
        changes = boundary["requiredChanges"]
        self.assertTrue(any("thread ID" in item and "x29" in item for item in changes))
        self.assertTrue(any("epoch boundary" in item for item in changes))
        self.assertTrue(any("long-lived" in item for item in changes))
        self.assertFalse(boundary["productionShaderAuthorized"])

    def test_parity_and_run_count_remain_explicitly_unclaimed(self):
        not_claimed = RESULT["notClaimed"]
        self.assertIn(
            "that the selected writer dependency slice is captured",
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
