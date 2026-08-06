#!/usr/bin/env python3
"""Integrity contracts for the opened ``Group.margin`` execution result."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import analyze_backdrop_margin_group_execution as analysis


RESULT_PATH = Path(__file__).with_name("backdrop_margin_group_execution_result.json")
RESULT = json.loads(RESULT_PATH.read_text(encoding="utf-8"))


class BackdropMarginGroupExecutionAnalysisTests(unittest.TestCase):
    def test_run_and_artifact_identity_are_immutable(self) -> None:
        self.assertEqual(
            RESULT["backdropMarginGroupExecutionAnalysisSchemaVersion"], 1
        )
        self.assertEqual(RESULT["run"]["runID"], analysis.RUN_ID)
        self.assertEqual(RESULT["run"]["headSHA"], analysis.HEAD_SHA)
        self.assertEqual(RESULT["run"]["jobID"], analysis.JOB_ID)
        self.assertEqual(RESULT["run"]["conclusion"], "success")
        self.assertEqual(RESULT["artifact"]["artifactID"], analysis.ARTIFACT_ID)
        self.assertEqual(RESULT["artifact"]["digest"], analysis.ARTIFACT_DIGEST)
        self.assertEqual(
            RESULT["artifact"]["sizeBytes"], analysis.ARTIFACT_SIZE_BYTES
        )
        self.assertEqual(len(RESULT["artifact"]["files"]), len(analysis.FILES))

    def test_case22_path_is_exact_but_other_cases_are_unobserved(self) -> None:
        case22 = RESULT["case22"]
        self.assertEqual(case22["invocationCount"], 76)
        self.assertEqual(case22["discriminatorCaseCounts"], {"22": 76})
        self.assertEqual(case22["sideTagCounts"], {"10": 76})
        self.assertEqual(
            case22["projectionFirstWordEqualsIndirectObjectPointerCount"], 76
        )
        self.assertEqual(
            case22["swiftUICoreModuleOffset"], analysis.INDIRECT_TARGET_MODULE_OFFSET
        )
        self.assertEqual(case22["unexercisedDiscriminatorCases"], [1, 2, 3, 21])
        self.assertFalse(case22["targetSymbolCaptured"])
        self.assertFalse(case22["targetCodeCaptured"])

    def test_candidate_match_is_not_promoted_to_a_temporal_join(self) -> None:
        value = RESULT["candidateCorroboration"]
        self.assertEqual(value["timelineRecordCount"], 32)
        self.assertEqual(value["timelineDistinctWordCount"], 8)
        self.assertEqual(value["liveInvocationCount"], 76)
        self.assertEqual(value["liveDistinctReturnWordCount"], 72)
        self.assertEqual(value["timelineRecordsWhoseWordOccursInLiveReturns"], 32)
        self.assertEqual(value["timelineDistinctWordsOccurringInLiveReturns"], 8)
        self.assertEqual(value["binary64Tolerance"], "zero bits")
        self.assertFalse(value["perFrameTemporalJoinCaptured"])
        self.assertFalse(value["prospectiveTransferAuthority"])

    def test_no_diagnostic_is_promoted_to_product_parity(self) -> None:
        sealed = RESULT["sealedConclusion"]
        self.assertTrue(sealed["groupMarginCase22LiveExecutionCaptured"])
        self.assertTrue(sealed["frozenCandidateExactlyCorroboratedOnOpenedProfile"])
        self.assertTrue(sealed["case22TargetIdentityOpened"])
        for key in (
            "case22TargetArithmeticDecoded",
            "discriminatorCases1To3And21LiveMapped",
            "publicInputMarginLawDecoded",
            "prospectiveUnseenProfileTransferPassed",
            "independentTemporalInputGenerationPassed",
            "physicalOutputTransferPassed",
            "independentWalleZeroByteFrameParityPassed",
            "productionShaderAuthorized",
            "liquidGlassParityEstablished",
        ):
            self.assertFalse(sealed[key], key)


if __name__ == "__main__":
    unittest.main()
