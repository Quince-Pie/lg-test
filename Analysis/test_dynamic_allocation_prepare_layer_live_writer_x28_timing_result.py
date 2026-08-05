#!/usr/bin/env python3
"""Integrity tests for the opened x28-timing result."""

import json
import unittest
from pathlib import Path


RESULT = json.loads(
    (Path(__file__).parent / "dynamic_allocation_prepare_layer_live_writer_x28_timing_result.json").read_text(
        encoding="utf-8"
    )
)


class PrepareLayerLiveWriterX28TimingResultTests(unittest.TestCase):
    def test_run_failed_only_after_successful_capture(self):
        run = RESULT["run"]
        self.assertEqual(run["runID"], 30960697537)
        self.assertEqual(run["headSHA"], "65bc6a5d56f80fa65032a0b68524039c4e9bf5cc")
        self.assertEqual(run["workflowConclusion"], "failure")
        self.assertEqual(run["captureStepOutcome"], "success")
        self.assertTrue(run["captureTargetExitedNormally"])
        self.assertEqual(run["captureTargetExitStatus"], 0)
        self.assertEqual(run["pathIsolationValidatorOutcome"], "success")
        self.assertEqual(run["inputClampValidatorOutcome"], "success")
        self.assertEqual(run["liveWriterValidatorOutcome"], "failure")

    def test_exact_arm_and_opened_stop_accounting(self):
        gates = RESULT["successfulStaticSelectionAndArmGates"]
        self.assertEqual(gates["prepareLayerSymbolByteCount"], 40128)
        self.assertTrue(gates["markerAndWatchpointInitialExact"])
        self.assertEqual(
            gates["liveSelectedMarkerAggregateOriginHex"],
            gates["watchpointInitialHex"],
        )
        watch = RESULT["openedWatchpointOutcome"]
        self.assertEqual(watch["rawWatchpointHitCount"], 8193)
        self.assertEqual(watch["ignoredWatchpointHitCount"], 8192)
        self.assertEqual(watch["ignoredPrepareFrameSeenCount"], 196)
        self.assertEqual(watch["qualifiedWatchpointHitCount"], 0)

    def test_direct_writer_and_helper_sites_are_exact(self):
        groups = RESULT["openedPrepareAncestryWriterGroups"]
        direct = {
            group["stopPCRelativeToPrepareLayer"]: group
            for group in groups
            if "precedingWriterInstructionOffset" in group
        }
        self.assertEqual(set(direct), {0xB60, 0x3974})
        self.assertEqual(direct[0xB60]["precedingWriterInstruction"], "str q0, [x19, #656]")
        self.assertEqual(direct[0x3974]["precedingWriterInstruction"], "stp q0, q1, [x19, #656]")
        union = next(group for group in groups if "union_bounds" in group["function"])
        self.assertEqual(union["stopPCRelativeToUnionHelper"], 0x84)

    def test_temporal_x28_predicate_is_falsified(self):
        timing = RESULT["openedTimingConclusion"]
        self.assertTrue(timing["directWriterX19EqualsWatchedRoleAtStop"])
        self.assertTrue(timing["combinedQualificationStillFailed"])
        self.assertTrue(timing["directWriterX28DiffersFromSelectedSourceAtStop"])
        self.assertTrue(timing["selectedSourcePresentLaterAtMarker"])

    def test_next_boundary_and_nonclaims_are_explicit(self):
        required = RESULT["nextEvidenceBoundary"]["requiredChanges"]
        self.assertTrue(any("thread ID" in item and "x29" in item for item in required))
        self.assertTrue(any("epoch boundary" in item for item in required))
        self.assertFalse(RESULT["nextEvidenceBoundary"]["productionShaderAuthorized"])
        nonclaims = RESULT["notClaimed"]
        self.assertIn("that the selected writer dependency slice is captured", nonclaims)
        self.assertIn("that Apple Liquid Glass parity has been achieved", nonclaims)
        self.assertIn("that a fixed number of later CI runs will be sufficient", nonclaims)


if __name__ == "__main__":
    unittest.main()
