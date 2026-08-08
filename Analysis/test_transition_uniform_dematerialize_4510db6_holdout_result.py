#!/usr/bin/env python3
"""Contracts for the prospective dematerialize uniform-transfer result."""

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).parent
RESULT = ANALYSIS / "transition_uniform_dematerialize_4510db6_holdout_result.json"
EXPECTED_SHA256 = (
    "81812b504be06916ea37195a3c5f2c49bf49d93d391735bca22dea7359bb1790"
)
EXPECTED_CASES = {
    ("clear", "light", "circle-456-center"),
    ("clear", "dark", "circle-464-center"),
    ("regular", "light", "circle-472-center"),
    ("regular", "dark", "circle-480-center"),
}


class DematerializeHoldoutResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_result_is_the_independently_reaggregated_byte_stream(self) -> None:
        self.assertEqual(hashlib.sha256(RESULT.read_bytes()).hexdigest(), EXPECTED_SHA256)
        self.assertEqual(
            self.result["captureCommit"],
            "4510db6f19883f9b6964588643099b9b7857bee7",
        )

    def test_all_numeric_and_structured_records_are_exact(self) -> None:
        aggregate = self.result["aggregate"]
        self.assertEqual(aggregate["profileCount"], 4)
        self.assertEqual(aggregate["dynamicStateCount"], 124)
        self.assertEqual(aggregate["numericFieldCount"], 47)
        self.assertEqual(aggregate["numericComparisonCount"], 5_828)
        self.assertEqual(aggregate["numericExactMatchCount"], 5_828)
        self.assertEqual(aggregate["numericMismatchCount"], 0)
        self.assertEqual(aggregate["structuredRecordCount"], 124)
        self.assertEqual(len(self.result["cases"]), 4)
        self.assertEqual(
            {
                (
                    case["profile"]["material"],
                    case["profile"]["appearance"],
                    case["profile"]["geometry"],
                )
                for case in self.result["cases"]
            },
            EXPECTED_CASES,
        )
        for case in self.result["cases"]:
            self.assertEqual(case["profile"]["direction"], "dematerialize")
            self.assertEqual(case["numericComparisonCount"], 1_457)
            self.assertEqual(case["numericExactMatchCount"], 1_457)

    def test_absent_endpoint_relation_transferred_exactly(self) -> None:
        aggregate = self.result["aggregate"]
        self.assertEqual(aggregate["windowServerFrameCount"], 132)
        self.assertEqual(aggregate["distinctWindowServerFrameCount"], 129)
        self.assertEqual(aggregate["duplicateFrameClassCount"], 1)
        self.assertEqual(
            aggregate["commonAbsentEndpointSHA256"],
            "f93a15f6884c8eccdf4b94203f748def9512e3137538aea2b99a53ece39b48a8",
        )
        self.assertEqual(
            {
                (occurrence["caseId"], occurrence["frame"])
                for occurrence in aggregate["commonAbsentEndpointOccurrences"]
            },
            {
                (
                    case["caseId"],
                    "transition-dematerialize-32-rgba8.png",
                )
                for case in self.result["cases"]
            },
        )

    def test_authority_is_numeric_dematerialize_only(self) -> None:
        conclusion = self.result["conclusion"]
        self.assertTrue(conclusion["fourProfileNumericDematerializeTransferEstablished"])
        self.assertTrue(conclusion["realDynamicRecordTopologyTransferred"])
        self.assertTrue(conclusion["commonAbsentEndpointRelationTransferred"])
        self.assertFalse(conclusion["meshSourceBackdropMipGenerationEstablished"])
        self.assertFalse(conclusion["physicalPixelParityEstablished"])
        self.assertFalse(conclusion["independentWalleZeroByteFrameEstablished"])
        self.assertFalse(conclusion["liquidGlassParityEstablished"])
        self.assertFalse(conclusion["productionShaderChangeAuthorized"])


if __name__ == "__main__":
    unittest.main()
