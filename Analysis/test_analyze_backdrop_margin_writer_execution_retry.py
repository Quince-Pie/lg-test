#!/usr/bin/env python3
"""Integrity checks for the mixed writer retry and opened margin getter."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import analyze_backdrop_margin_writer_execution_retry as analysis


RESULT_PATH = Path(__file__).with_name(
    "backdrop_margin_writer_execution_retry_result.json"
)
RESULT = json.loads(RESULT_PATH.read_text(encoding="utf-8"))


class BackdropMarginWriterExecutionRetryAnalysisTests(unittest.TestCase):
    def test_run_and_four_artifacts_are_immutable(self) -> None:
        self.assertEqual(
            RESULT["backdropMarginWriterExecutionRetryAnalysisSchemaVersion"], 1
        )
        self.assertEqual(RESULT["run"]["runID"], 31113785381)
        self.assertEqual(
            RESULT["run"]["headSHA"],
            "16102867187c66f20b560bb9a36667bdd3ae6115",
        )
        self.assertEqual(RESULT["run"]["conclusion"], "failure")
        artifacts = RESULT["artifacts"]
        self.assertEqual(len(artifacts), 4)
        self.assertEqual(
            {artifact["artifactID"] for artifact in artifacts},
            {8972897031, 8972898736, 8973005023, 8973017885},
        )
        for artifact in artifacts:
            self.assertRegex(artifact["artifactDigest"], r"^sha256:[0-9a-f]{64}$")
            self.assertRegex(artifact["traceSHA256"], r"^[0-9a-f]{64}$")
            self.assertRegex(artifact["timelineSHA256"], r"^[0-9a-f]{64}$")

    def test_regular_jobs_pass_and_clear_jobs_remain_failures(self) -> None:
        artifacts = {artifact["case"]: artifact for artifact in RESULT["artifacts"]}
        for name in (
            "regular-light-materialize-circle-768-center",
            "regular-dark-materialize-circle-1535-center",
        ):
            artifact = artifacts[name]
            self.assertEqual(artifact["jobConclusion"], "success")
            self.assertTrue(artifact["prospectiveRegularBranchResult"])
            self.assertTrue(artifact["independentValidationEqualExceptCallerPaths"])
            self.assertEqual(artifact["completeBitExactChainCount"], 32)
        for name in (
            "clear-light-materialize-circle-408-center",
            "clear-dark-materialize-circle-640-phase-0501",
        ):
            artifact = artifacts[name]
            self.assertEqual(artifact["jobConclusion"], "failure")
            self.assertFalse(artifact["validationOutputExists"])
            self.assertFalse(artifact["prospectiveMaterialLawResult"])
            self.assertFalse(artifact["partialProducerObservationMayCountAsTransfer"])
            self.assertIn("snapshot unavailable", artifact["captureFailure"])

    def test_exact_producer_control_flow_is_gated(self) -> None:
        producer = RESULT["adjacentProducer"]
        self.assertEqual(producer["function"], analysis.PRODUCER_FUNCTION)
        self.assertEqual(producer["moduleOffset"], 0x3715D0)
        self.assertEqual(producer["symbolByteCount"], 732)
        self.assertEqual(producer["instructionCount"], 183)
        self.assertEqual(producer["codeSHA256"], analysis.PRODUCER_CODE_SHA256)
        self.assertTrue(producer["identicalCodeInAllFourArtifacts"])
        self.assertTrue(producer["symbolicArithmeticDecoded"])
        self.assertFalse(producer["publicOperandMappingDecoded"])
        self.assertEqual(
            {
                item["instructionOffset"]: item["targetModuleOffset"]
                for item in producer["directCallTargetModuleOffsets"]
            },
            analysis.EXPECTED_DIRECT_CALL_TARGET_OFFSETS,
        )

    def test_no_mixed_result_is_promoted_to_product_parity(self) -> None:
        sealed = RESULT["sealedConclusion"]
        self.assertTrue(sealed["regularBranchProspectiveBitExactInTwoCases"])
        self.assertTrue(sealed["adjacentProducerCodeOpened"])
        self.assertTrue(sealed["adjacentProducerSymbolicArithmeticDecoded"])
        for key in (
            "clearBranchProspectiveBitExact",
            "materialSpecificFourCaseGatePassed",
            "adjacentProducerPublicInputLawDecoded",
            "independentTemporalInputGenerationPassed",
            "physicalOutputTransferPassed",
            "independentWalleZeroByteFrameParityPassed",
            "productionShaderAuthorized",
            "liquidGlassParityEstablished",
        ):
            self.assertFalse(sealed[key], key)


if __name__ == "__main__":
    unittest.main()
