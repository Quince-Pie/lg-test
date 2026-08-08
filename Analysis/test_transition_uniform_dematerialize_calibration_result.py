#!/usr/bin/env python3
"""Contracts for the exact four-profile dematerialize calibration."""

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).parent
RESULT_PATH = ANALYSIS / "transition_uniform_dematerialize_calibration_result.json"
CLAMP_RESULT_PATH = (
    ANALYSIS
    / "transition_uniform_dematerialize_clamp_local_macos_26_6_1_calibration_result.json"
)
CLAMP_SOURCE_PATH = (
    ANALYSIS
    / "analyze_transition_uniform_dematerialize_clamp_local_macos_26_6_1.swift"
)
RESULT = json.loads(RESULT_PATH.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DematerializeCalibrationResultTests(unittest.TestCase):
    def test_complete_numeric_and_structured_coverage_is_exact(self) -> None:
        aggregate = RESULT["aggregate"]
        self.assertEqual(aggregate["profileCount"], 4)
        self.assertEqual(aggregate["dynamicSampleCount"], 124)
        self.assertEqual(aggregate["nonClampComparisonCount"], 5_704)
        self.assertEqual(aggregate["nativeClampComparisonCount"], 124)
        self.assertEqual(aggregate["numericComparisonCount"], 5_828)
        self.assertEqual(aggregate["numericExactMatchCount"], 5_828)
        self.assertEqual(aggregate["numericMismatchCount"], 0)
        self.assertEqual(aggregate["structuredRecordCount"], 124)
        for case in RESULT["cases"]:
            self.assertEqual(case["dynamicSampleCount"], 31)
            self.assertEqual(case["numericFieldCount"], 47)
            self.assertEqual(case["numericComparisonCount"], 1_457)
            self.assertEqual(case["numericExactMatchCount"], 1_457)
            self.assertEqual(case["structuredRecordCount"], 31)
            self.assertEqual(set(case["fieldExactMatchCounts"].values()), {31})

    def test_native_source_and_result_provenance_are_bound(self) -> None:
        native = RESULT["nativeClampResult"]
        self.assertEqual(native["sha256"], sha256_file(CLAMP_RESULT_PATH))
        self.assertEqual(native["sourceSHA256"], sha256_file(CLAMP_SOURCE_PATH))
        self.assertEqual(native["comparisonCount"], 124)

    def test_glibc_divergence_sentinels_are_retained_exactly(self) -> None:
        clear_dark = next(
            case for case in RESULT["cases"] if case["name"] == "clear-dark-circle461"
        )
        records = {record["sampleIndex"]: record for record in clear_dark["records"]}
        self.assertEqual(records[1]["inputClampBaseBits"], "3f919b07")
        self.assertEqual(records[1]["inputClampBits"], "3fae650b")
        self.assertEqual(records[15]["inputClampBaseBits"], "3f89ab32")
        self.assertEqual(records[15]["inputClampBits"], "3f9871b5")

    def test_calibration_does_not_claim_transfer_or_shader_authority(self) -> None:
        conclusion = RESULT["conclusion"]
        self.assertTrue(conclusion["openedCalibrationExact"])
        self.assertTrue(conclusion["sameLawAsFunctionOfRemainingFraction"])
        self.assertFalse(conclusion["prospectiveDematerializeTransferEstablished"])
        self.assertFalse(conclusion["productionShaderChangeAuthorized"])
        self.assertFalse(conclusion["liquidGlassParityEstablished"])


if __name__ == "__main__":
    unittest.main()
