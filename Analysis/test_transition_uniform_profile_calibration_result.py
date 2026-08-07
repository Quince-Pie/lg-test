#!/usr/bin/env python3
"""Regression contract for the committed four-profile calibration result."""

import json
import unittest
from pathlib import Path

import analyze_transition_uniform_profile_calibration as model


RESULT_PATH = Path(__file__).with_name(
    "transition_uniform_profile_calibration_result.json"
)
CLAMP_RESULT_PATH = Path(__file__).with_name(
    "transition_uniform_profile_clamp_local_macos_26_6_1_calibration_result.json"
)


class TransitionUniformProfileCalibrationResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
        cls.clamp = json.loads(CLAMP_RESULT_PATH.read_text(encoding="utf-8"))

    def test_numeric_calibration_is_complete_and_exact(self) -> None:
        aggregate = self.result["aggregate"]
        self.assertEqual(aggregate["profileCount"], 4)
        self.assertEqual(aggregate["dynamicSampleCount"], 128)
        self.assertEqual(aggregate["numericComparisonCount"], 6_016)
        self.assertEqual(aggregate["numericExactMatchCount"], 6_016)
        self.assertEqual(aggregate["numericMismatchCount"], 0)
        self.assertEqual(aggregate["structuredRecordCount"], 128)

    def test_every_field_is_exact_in_every_case(self) -> None:
        self.assertEqual(len(self.result["cases"]), 4)
        for case in self.result["cases"]:
            with self.subTest(case=case["name"]):
                self.assertEqual(case["numericFieldCount"], 47)
                self.assertEqual(case["numericComparisonCount"], 1_504)
                self.assertEqual(case["numericExactMatchCount"], 1_504)
                self.assertEqual(set(case["fieldExactMatchCounts"].values()), {32})

    def test_native_darwin_powf_clamp_is_exact(self) -> None:
        self.assertEqual(self.clamp["comparisonCount"], 128)
        self.assertEqual(self.clamp["exactMatchCount"], 128)
        self.assertIs(self.clamp["allCandidateWordsExact"], True)
        self.assertEqual(
            self.result["nativeClampResult"]["sha256"],
            model.sha256_file(CLAMP_RESULT_PATH),
        )

    def test_calibration_does_not_claim_transfer_or_parity(self) -> None:
        conclusion = self.result["conclusion"]
        self.assertIs(conclusion["openedCalibrationExact"], True)
        for key in (
            "prospectiveTransferEstablished",
            "dematerializeTransferEstablished",
            "physicalPixelParityEstablished",
            "independentWalleZeroByteFrameEstablished",
            "liquidGlassParityEstablished",
            "productionShaderChangeAuthorized",
        ):
            self.assertIs(conclusion[key], False)


if __name__ == "__main__":
    unittest.main()
