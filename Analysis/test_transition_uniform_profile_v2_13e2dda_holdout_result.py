#!/usr/bin/env python3
"""Regression contract for the passed v2 four-profile uniform transfer."""

import json
import unittest
from pathlib import Path


RESULT_PATH = Path(__file__).with_name(
    "transition_uniform_profile_v2_13e2dda_holdout_result.json"
)


class TransitionUniformProfileV2HoldoutResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_complete_numeric_matrix_is_exact(self) -> None:
        aggregate = self.result["aggregate"]
        self.assertEqual(aggregate["profileCount"], 4)
        self.assertEqual(aggregate["dynamicStateCount"], 128)
        self.assertEqual(aggregate["numericFieldCount"], 47)
        self.assertEqual(aggregate["numericComparisonCount"], 6_016)
        self.assertEqual(aggregate["numericExactMatchCount"], 6_016)
        self.assertEqual(aggregate["numericMismatchCount"], 0)
        self.assertEqual(aggregate["structuredRecordCount"], 128)

    def test_corrected_frame_relation_is_exact(self) -> None:
        aggregate = self.result["aggregate"]
        self.assertEqual(aggregate["windowServerFrameCount"], 132)
        self.assertEqual(aggregate["distinctWindowServerFrameCount"], 129)
        self.assertEqual(aggregate["duplicateFrameClassCount"], 1)
        self.assertEqual(
            aggregate["commonAbsentEndpointSHA256"],
            "f93a15f6884c8eccdf4b94203f748def9512e3137538aea2b99a53ece39b48a8",
        )
        occurrences = aggregate["commonAbsentEndpointOccurrences"]
        self.assertEqual(len(occurrences), 4)
        self.assertEqual(
            {value["frame"] for value in occurrences},
            {"transition-materialize-00-rgba8.png"},
        )

    def test_all_cases_share_the_frozen_commit(self) -> None:
        self.assertEqual(
            self.result["captureCommit"],
            "13e2ddaa33fb9c21a4ec291480794b370c02cd9f",
        )
        self.assertEqual(len(self.result["cases"]), 4)
        self.assertEqual(
            {case["numericExactMatchCount"] for case in self.result["cases"]},
            {1_504},
        )

    def test_authority_is_numeric_materialize_only(self) -> None:
        conclusion = self.result["conclusion"]
        self.assertIs(
            conclusion["fourProfileNumericMaterializeTransferEstablished"], True
        )
        self.assertIs(conclusion["allSixThousandSixteenNumericWordsExact"], True)
        self.assertIs(conclusion["commonAbsentEndpointRelationTransferred"], True)
        for key in (
            "dematerializeTransferEstablished",
            "nestedResolvedColorTransferEstablished",
            "meshSourceBackdropMipGenerationEstablished",
            "physicalPixelParityEstablished",
            "independentWalleZeroByteFrameEstablished",
            "liquidGlassParityEstablished",
            "productionShaderChangeAuthorized",
        ):
            self.assertIs(conclusion[key], False)


if __name__ == "__main__":
    unittest.main()
