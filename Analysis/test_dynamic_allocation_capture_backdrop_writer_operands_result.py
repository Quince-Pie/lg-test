#!/usr/bin/env python3
"""Tests for the opened Apple crop-writer operand result."""

import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
RESULT = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_capture_backdrop_writer_operands_result.json"
    ).read_text(encoding="utf-8")
)


class CaptureBackdropWriterOperandsResultTests(unittest.TestCase):
    def test_successful_prospective_run_is_retained(self):
        run = RESULT["run"]
        aggregate = RESULT["rawTraceAggregate"]
        self.assertEqual(run["runID"], 30881161586)
        self.assertEqual(run["headSHA"], "4a862fa24abcac080350896566941a0691bdb6ee")
        self.assertEqual(run["workflowConclusion"], "success")
        self.assertEqual(run["writerTraceValidatorOutcome"], "success")
        self.assertTrue(run["captureTargetExitedNormally"])
        self.assertEqual(aggregate["rawTraceSchemaVersion"], 4)
        self.assertEqual(aggregate["sealedValidatorSchemaVersion"], 3)
        self.assertEqual(aggregate["eventCount"], 24)
        self.assertEqual(aggregate["failureCount"], 0)
        self.assertEqual(aggregate["pcContainingCodeWindowCount"], 12)

    def test_stopped_pc_is_proven_to_follow_each_store(self):
        causality = RESULT["openedStoppedPCCausality"]
        stores = causality["stores"]
        self.assertEqual(len(stores), 5)
        for store in stores:
            with self.subTest(store=store["watchpointName"]):
                self.assertEqual(store["stopOffset"] - store["storeOffset"], 4)
        self.assertEqual(
            [store["encodingHex"] for store in stores],
            ["202701f9", "001f803d", "965300b9", "804305fc", "802f803d"],
        )
        self.assertEqual(causality["sourceCompletionInstruction"]["liveW9"], 652)

    def test_exact_enclosure_and_intersection_primitives_are_opened(self):
        arithmetic = RESULT["openedConstructionArithmetic"]
        enclosure = arithmetic["integerEnclosure"]
        intersection = arithmetic["integerRectangleIntersection"]
        self.assertEqual(enclosure["lowerClampF64"], -536870911.0)
        self.assertEqual(enclosure["upperClampF64"], 536870912.0)
        self.assertEqual(enclosure["inputOriginOffset"], 752)
        self.assertEqual(enclosure["inputSizeOffset"], 768)
        self.assertEqual(intersection["workingRectangleOffset"], 624)
        self.assertEqual(
            intersection["decisiveInstructions"][-1],
            {
                "offset": 21540,
                "encodingHex": "609e803d",
                "instruction": "str q0, [x19, #624]",
            },
        )

    def test_missing_operand_range_is_measured_not_inferred(self):
        boundary = RESULT["operandBoundary"]
        self.assertEqual(boundary["genericPointerProbeByteCount"], 256)
        self.assertEqual(boundary["genericPointerProbeBacktrack"], 64)
        self.assertEqual(boundary["genericForwardCoverageFromRegisterValue"], 192)
        self.assertEqual(
            boundary["missingRoleRelativeOffsets"]["workingRectangleI32"],
            [624, 640],
        )
        self.assertGreater(
            boundary["missingRoleRelativeOffsets"]["helperScratchRectangle"][1],
            boundary["genericForwardCoverageFromRegisterValue"],
        )

    def test_public_policy_and_product_parity_remain_unclaimed(self):
        self.assertFalse(
            RESULT["nextEvidenceBoundary"]["publicCropConstructionRuleRecovered"]
        )
        self.assertFalse(RESULT["nextEvidenceBoundary"]["productionShaderAuthorized"])
        self.assertIn(
            "that the complete public layer-state crop-allocation policy is recovered",
            RESULT["notClaimed"],
        )
        self.assertIn(
            "that Apple Liquid Glass parity has been achieved",
            RESULT["notClaimed"],
        )


if __name__ == "__main__":
    unittest.main()
