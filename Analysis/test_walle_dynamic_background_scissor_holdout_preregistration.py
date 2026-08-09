#!/usr/bin/env python3
"""Integrity checks for the frozen natural-scissor holdout."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

import analyze_walle_dynamic_background_scissor as analysis


ROOT = Path(__file__).resolve().parent.parent
PREREGISTRATION = (
    ROOT / "Analysis/walle_dynamic_background_scissor_holdout_preregistration.json"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DynamicBackgroundScissorPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    def test_frozen_file_hashes_are_exact(self) -> None:
        for relative, expected in self.value["frozenFiles"].items():
            with self.subTest(path=relative):
                self.assertEqual(sha256_file(ROOT / relative), expected)

    def test_calibration_result_hash_is_exact(self) -> None:
        evidence = self.value["calibrationEvidence"]
        self.assertEqual(
            sha256_file(ROOT / evidence["result"]), evidence["resultSHA256"]
        )

    def test_model_constants_match_the_executable_analyzer(self) -> None:
        model = self.value["frozenModel"]
        self.assertEqual(model["sdfRadiusF32"], analysis.SDF_RADIUS)
        self.assertEqual(
            model["domain"]["sampleIndices"], list(analysis.SAMPLE_INDICES)
        )
        self.assertEqual(
            model["domain"]["geometry"], analysis.EXPECTED_GEOMETRY["name"]
        )

    def test_acceptance_is_zero_tolerance_and_complete(self) -> None:
        acceptance = self.value["acceptance"]
        self.assertEqual(acceptance["comparisonTolerance"], 0)
        self.assertFalse(acceptance["caseExclusionPermitted"])
        self.assertEqual(
            acceptance["scissorI32"], {"componentCount": 32, "mismatchCount": 0}
        )
        self.assertTrue(
            acceptance["allEightRemainingBinary32WordsMustDifferFromCalibration"]
        )


if __name__ == "__main__":
    unittest.main()
