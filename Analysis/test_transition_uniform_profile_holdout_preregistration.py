#!/usr/bin/env python3
"""Regression contract for the frozen four-profile uniform holdout."""

import json
import unittest
from pathlib import Path

import validate_transition_uniform_profile_holdout as validator


PREREGISTRATION_PATH = Path(__file__).with_name(
    "transition_uniform_profile_holdout_preregistration.json"
)


class TransitionUniformProfileHoldoutPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_case_matrix_is_unopened_and_complete(self) -> None:
        cases = self.value["caseMatrix"]
        self.assertEqual(len(cases), 4)
        self.assertEqual(
            {
                (case["material"], case["appearance"], case["geometry"])
                for case in cases
            },
            set(validator.EXPECTED_CASES),
        )
        for case in cases:
            with self.subTest(case=case["caseId"]):
                self.assertIs(case["appleOutputAvailableAtFreeze"], False)
                self.assertIsNone(case["timelineSHA256"])
                self.assertIsNone(case["numericFieldWords"])
                self.assertIsNone(case["inputClampWords"])

    def test_acceptance_is_bitwise_and_zero_tolerance(self) -> None:
        acceptance = self.value["acceptance"]
        self.assertEqual(acceptance["numericFieldCountPerState"], 47)
        self.assertEqual(acceptance["dynamicStateCountPerCase"], 32)
        self.assertEqual(acceptance["numericComparisonCountPerCase"], 1_504)
        self.assertEqual(acceptance["numericComparisonCountAcrossMatrix"], 6_016)
        self.assertEqual(acceptance["requiredNumericMismatchCount"], 0)
        self.assertIs(acceptance["requireExactBinary32Words"], True)
        self.assertIs(acceptance["requireNativeDarwinPowfClamp"], True)
        self.assertIs(acceptance["zeroTolerance"], True)

    def test_frozen_implementation_hashes_match(self) -> None:
        implementation = self.value["frozenImplementation"]
        analysis = Path(__file__).parent
        for path_key, hash_key in (
            ("model", "modelSHA256"),
            ("nativeClamp", "nativeClampSHA256"),
            ("validator", "validatorSHA256"),
            ("preflight", "preflightSHA256"),
        ):
            path = analysis.parent / implementation[path_key]
            self.assertEqual(validator.sha256_file(path), implementation[hash_key])

    def test_product_authority_remains_narrow(self) -> None:
        authority = self.value["productAuthority"]
        self.assertIs(
            authority["fourProfileNumericMaterializeTransferEstablishedOnCompletePass"],
            True,
        )
        for key, value in authority.items():
            if key.endswith("OnPass") and key != (
                "fourProfileNumericMaterializeTransferEstablishedOnCompletePass"
            ):
                self.assertIs(value, False)


if __name__ == "__main__":
    unittest.main()
