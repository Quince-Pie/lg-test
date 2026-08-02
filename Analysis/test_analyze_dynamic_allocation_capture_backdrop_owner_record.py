#!/usr/bin/env python3
"""Tests for the prospectively passing owner-record capture audit."""

import json
import unittest
from pathlib import Path

import analyze_dynamic_allocation_capture_backdrop_owner_record as analyzer


ANALYSIS_ROOT = Path(__file__).resolve().parent
RESULT = json.loads(
    (
        ANALYSIS_ROOT / "dynamic_allocation_capture_backdrop_owner_record_result.json"
    ).read_text(encoding="utf-8")
)


class CaptureBackdropOwnerRecordTests(unittest.TestCase):
    def test_result_preserves_the_prospective_pass(self) -> None:
        self.assertEqual(RESULT["runID"], analyzer.EXPECTED_RUN_ID)
        self.assertEqual(RESULT["headSHA"], analyzer.EXPECTED_HEAD_SHA)
        self.assertEqual(RESULT["workflowConclusion"], "success")
        self.assertTrue(RESULT["prospectiveGatePassed"])
        self.assertTrue(RESULT["conclusion"]["frozenOwnerRecordGatePassed"])

    def test_all_live_replay_gates_are_exact(self) -> None:
        aggregate = RESULT["aggregate"]
        self.assertEqual(aggregate["recordCount"], 114)
        self.assertEqual(aggregate["completeLiveOperandCaptureCount"], 114)
        self.assertEqual(aggregate["ownerRecordCountEveryState"], 1)
        self.assertEqual(aggregate["sourceKeyMatchCountEveryState"], 1)
        self.assertEqual(aggregate["selectedRecordIndexEveryState"], 0)
        self.assertEqual(
            aggregate["primaryPositionReplay"]["mismatchedComponents"], 0
        )
        self.assertEqual(aggregate["primarySourceReplay"]["mismatchedComponents"], 0)
        self.assertEqual(aggregate["selectedRegionConsumedRectangleExactCount"], 114)

    def test_vector_is_exact_inline_owner_storage(self) -> None:
        inline = RESULT["openedOwnerInlineStorage"]
        self.assertEqual(inline["ownerRegister"], "x20")
        self.assertEqual(inline["inlineRecordOwnerRange"], [0x70, 0x140])
        self.assertEqual(inline["beginEqualsOwnerPlusInlineOffsetCount"], 114)
        self.assertEqual(inline["endEqualsOwnerPlusInlineEndCount"], 114)
        self.assertEqual(inline["word60EqualsBeginCount"], 114)
        self.assertEqual(inline["inlineBytesEqualIndependentVectorCount"], 114)
        self.assertEqual(inline["opaqueConstantWordValue"], 2)

    def test_every_record_byte_is_accounted_for(self) -> None:
        record = RESULT["openedOwnerRecord"]
        self.assertEqual(record["byteCount"], 0xD0)
        self.assertEqual(record["fullyReconstructedExactCount"], 114)
        self.assertEqual(record["initialPublicBounds"]["exactCount"], 114)
        self.assertEqual(record["auxiliaryBounds"]["allZeroCount"], 114)
        self.assertEqual(record["selectedRegionRectangle"]["exactCount"], 114)
        self.assertEqual(record["generatedPublicBoundsCorners"]["exactCount"], 114)
        self.assertEqual(record["zeroReservedExactCount"], 114)
        self.assertEqual(record["generation"]["exactCount"], 114)
        self.assertEqual(
            record["pointerAndGenerationNormalizedDistinctVariantCount"], 9
        )
        self.assertTrue(
            record["normalizedVariantsAreInOneToOneCorrespondenceWithRectangles"]
        )

    def test_dormant_branch_and_remaining_unknown_are_not_promoted(self) -> None:
        record = RESULT["openedOwnerRecord"]
        instructions = RESULT["openedInstructions"]
        conclusion = RESULT["conclusion"]
        self.assertEqual(record["helperPointer"]["distinctPointerCount"], 14)
        self.assertTrue(record["helperPointer"]["periodExact"])
        self.assertEqual(
            record["helperPointer"]["helperPathBypassedBySingleSelectedRecordCount"],
            114,
        )
        self.assertTrue(
            instructions["singleRecordSelectedBranch"][
                "bypassesOtherRecordTransformAndUnionPath"
            ]
        )
        self.assertFalse(conclusion["singleRecordTransformAndUnionBranchExercised"])
        self.assertFalse(conclusion["publicLayerStateCropRuleRecovered"])
        self.assertTrue(conclusion["upstreamPrivateRegionConstructionStillMissing"])
        self.assertTrue(conclusion["requiresUnseenGeometryTransfer"])
        self.assertFalse(conclusion["productionShaderAuthorized"])


if __name__ == "__main__":
    unittest.main()
