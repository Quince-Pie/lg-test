#!/usr/bin/env python3
"""Regression tests for the live blur-distance lane-4 composition."""

import hashlib
import json
import unittest
from pathlib import Path

import analyze_background_filter_constructor_return_join_blur_distance4_composition as analysis


ANALYSIS = Path(__file__).resolve().parent
SOURCE = Path(analysis.__file__).resolve()
RESULT = (
    ANALYSIS
    / "background_filter_constructor_return_join_blur_distance4_composition_result.json"
)
EXPECTED_SOURCE_SHA256 = (
    "8c505c1a86670eece62a53a5dac803874eff459ebfe6fb5652f668c640402e92"
)
EXPECTED_RESULT_SHA256 = (
    "68a78e4d61262d3373530079f745ab140b0dc9ab532df41b5a9bda623ecb541f"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BlurDistance4CompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_source_and_result_are_frozen(self) -> None:
        self.assertEqual(sha256(SOURCE), EXPECTED_SOURCE_SHA256)
        self.assertEqual(sha256(RESULT), EXPECTED_RESULT_SHA256)
        self.assertEqual(
            self.result["inputs"]["analysisSource"]["sha256"],
            EXPECTED_SOURCE_SHA256,
        )

    def test_all_live_byte_boundaries_are_exact(self) -> None:
        evidence = self.result["allChainEvidence"]
        self.assertEqual(evidence["chainCount"], analysis.CHAIN_COUNT)
        self.assertEqual(
            evidence["parametersBlurDistance4ToConstructorBitwiseMatchCount"],
            analysis.CHAIN_COUNT,
        )
        self.assertEqual(
            evidence["constructorBlurDistance4ToProviderBitwiseMatchCount"],
            analysis.CHAIN_COUNT,
        )
        self.assertEqual(
            evidence["distinctParametersBlurDistance4WordCount"],
            analysis.CHAIN_COUNT,
        )

    def test_corrected_live_49_field_boundary_is_bitwise_exact(self) -> None:
        corrected = self.result["corrected49FieldBoundary"]
        self.assertEqual(corrected["correctedParametersField"], "blur.distances.4")
        self.assertEqual(corrected["correctedParametersByteRange"], [216, 224])
        self.assertEqual(corrected["mappedComponentCount"], 1568)
        self.assertEqual(corrected["mappedComponentBitwiseMatchCount"], 1568)
        self.assertEqual(corrected["mappedComponentBitwiseMismatchCount"], 0)
        self.assertEqual(corrected["fullyExactMappedFieldCount"], 49)
        self.assertTrue(
            self.result["authority"][
                "generalPublicParameters49FieldConstructionLawEstablished"
            ]
        )

    def test_constant_zero_falsification_remains_disclosed(self) -> None:
        corrected = self.result["corrected49FieldBoundary"]
        self.assertEqual(
            corrected["preservedRejectedPrediction"],
            "filterArrayGetter.inputBlurDistance4.constantZero",
        )
        self.assertIn("retrospective", self.result["classification"])


if __name__ == "__main__":
    unittest.main()
