#!/usr/bin/env python3
"""Tests for the opened Apple prepare_layer role-state result."""

import json
import math
import struct
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
RESULT = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_capture_backdrop_writer_role_state_result.json"
    ).read_text(encoding="utf-8")
)


class CaptureBackdropWriterRoleStateResultTests(unittest.TestCase):
    def test_successful_prospective_run_and_role_inventory_are_retained(self):
        run = RESULT["run"]
        aggregate = RESULT["rawTraceAggregate"]
        self.assertEqual(run["runID"], 30883442714)
        self.assertEqual(
            run["headSHA"], "c80f4b518fd270d51edcbd5ae716e607193a1bd7"
        )
        self.assertEqual(run["workflowConclusion"], "success")
        self.assertEqual(run["writerTraceValidatorOutcome"], "success")
        self.assertTrue(run["captureTargetExitedNormally"])
        self.assertEqual(aggregate["rawTraceSchemaVersion"], 5)
        self.assertEqual(aggregate["sealedValidatorSchemaVersion"], 4)
        self.assertEqual(aggregate["eventCount"], 24)
        self.assertEqual(aggregate["failureCount"], 0)
        self.assertEqual(aggregate["prepareLayerRoleProbeSuccessCount"], 52)
        self.assertEqual(aggregate["prepareLayerRoleProbeFailureCount"], 0)
        self.assertEqual(aggregate["requiredX19RoleSnapshotCount"], 6)

    def test_recursive_call_and_still_unopened_merge_target_are_exact(self):
        construction = RESULT["openedUpstreamConstruction"]
        recursive = construction["recursiveChildCall"]
        merge = construction["directMergeBranch"]
        self.assertEqual(construction["codeWindow"]["symbolOffsetStart"], 12764)
        self.assertEqual(recursive["instructionOffset"], 0x3258)
        self.assertEqual(recursive["encodingWordHex"], "97fff36a")
        self.assertEqual(recursive["arguments"]["x3"], "x19+1568 child LayerShapes output")
        self.assertEqual(
            merge["instructionOffsets"],
            [0x32B4, 0x32B8, 0x32BC, 0x32C0, 0x32C4],
        )
        self.assertEqual(merge["callInstructionRawLittleEndianHex"], "a8f0ff97")
        self.assertEqual(merge["signedBranchDisplacement"], -0x3D60)
        self.assertEqual(
            merge["targetAddressInRun"],
            construction["prepareLayerSymbolStart"] - 2720,
        )
        self.assertFalse(merge["targetCodeCaptured"])
        self.assertFalse(merge["preAndPostOperandsCaptured"])

    def test_three_public_samples_replay_private_aggregates_bit_for_bit(self):
        join = RESULT["openedPublicPrivateJoin"]
        self.assertEqual(join["threeSampleRule"]["binary64AggregateMatchCount"], 3)
        self.assertEqual(join["threeSampleRule"]["binary64AggregateMismatchCount"], 0)
        for sample in join["samples"]:
            with self.subTest(sample=sample["timelineSampleIndex"]):
                position = sample["carrierPositionP"]
                lower = math.floor(position) - 1
                predicted = [
                    float(lower),
                    1024.0 - position - 640.0 - 8.0,
                    position + 640.0 - lower,
                    position + 640.0 + 8.0 - lower,
                ]
                observed = sample["observedAggregateF64"]
                self.assertEqual(
                    struct.pack("<4d", *predicted),
                    struct.pack("<4d", *observed),
                )
                self.assertEqual(
                    struct.pack("<d", position).hex(),
                    sample["carrierPositionBinary64LittleEndianHex"],
                )
                self.assertTrue(sample["aggregateBinary64BitwiseExact"])

    def test_enclosure_and_border_replay_every_observed_crop_exactly(self):
        for sample in RESULT["openedPublicPrivateJoin"]["samples"]:
            with self.subTest(sample=sample["timelineSampleIndex"]):
                origin_x, origin_y, width, height = sample["observedAggregateF64"]
                enclosed = [
                    math.floor(origin_x),
                    math.floor(origin_y),
                    math.ceil(origin_x + width) - math.floor(origin_x),
                    math.ceil(origin_y + height) - math.floor(origin_y),
                ]
                bordered = [
                    enclosed[0] - 1,
                    enclosed[1] - 1,
                    enclosed[2] + 2,
                    enclosed[3] + 2,
                ]
                self.assertEqual(enclosed, sample["integerEnclosure"])
                self.assertEqual(bordered, sample["onePixelBorderResult"])
                self.assertEqual(
                    bordered,
                    sample["observedWorkingIntegerRectangle"],
                )
                self.assertTrue(sample["integerCropExact"])

    def test_public_policy_and_product_parity_remain_unclaimed(self):
        boundary = RESULT["nextEvidenceBoundary"]
        self.assertFalse(boundary["recursiveLayerShapesMergeRecovered"])
        self.assertFalse(boundary["completePublicCropConstructionRuleRecovered"])
        self.assertFalse(boundary["unseenGeometryTransferPassed"])
        self.assertFalse(boundary["productionShaderAuthorized"])
        self.assertIn(
            "that Apple Liquid Glass parity has been achieved",
            RESULT["notClaimed"],
        )


if __name__ == "__main__":
    unittest.main()
