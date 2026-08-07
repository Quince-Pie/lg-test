#!/usr/bin/env python3
"""Tests for the frozen observer-independent lifetime matrix."""

import hashlib
import json
from pathlib import Path
import unittest


ANALYSIS = Path(__file__).parent
PREREGISTRATION = ANALYSIS / (
    "transition_presentation_lifetime_holdout_preregistration.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TransitionPresentationLifetimePreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    def test_matrix_is_complete_and_output_blind(self) -> None:
        cases = self.value["caseMatrix"]
        self.assertEqual(len(cases), 8)
        self.assertEqual(
            {
                (case["material"], case["appearance"], case["direction"])
                for case in cases
            },
            {
                (material, appearance, direction)
                for material in ("clear", "regular")
                for appearance in ("light", "dark")
                for direction in ("materialize", "dematerialize")
            },
        )
        for case in cases:
            self.assertEqual(case["role"], "prospective-holdout")
            self.assertFalse(case["appleOutputAvailableAtFreeze"])
            self.assertIsNone(case["expectedTimelineSHA256"])
            self.assertIsNone(case["expectedImageSHA256"])
            self.assertIsNone(case["expectedFaceOpacityValues"])

    def test_frozen_implementation_hashes_are_exact(self) -> None:
        frozen = self.value["frozenImplementation"]
        for path_key, hash_key in (
            ("validator", "validatorSHA256"),
            ("aggregator", "aggregatorSHA256"),
            ("preflight", "preflightSHA256"),
        ):
            path = ANALYSIS.parent / frozen[path_key]
            self.assertEqual(sha256(path), frozen[hash_key])
        calibration = self.value["calibrationEvidence"]
        self.assertEqual(
            sha256(ANALYSIS.parent / calibration["path"]),
            calibration["sha256"],
        )

    def test_no_debugger_and_quality_locks_are_mandatory(self) -> None:
        contract = self.value["captureContract"]
        acceptance = self.value["acceptance"]
        self.assertTrue(contract["debuggerForbidden"])
        self.assertTrue(contract["githubActionsForbidden"])
        self.assertTrue(contract["nixStorePathInNativeEnvironmentForbidden"])
        self.assertTrue(acceptance["requireNoDebugger"])
        self.assertTrue(acceptance["requireAllEightCasesFromOneFrozenCommit"])
        self.assertFalse(self.value["qualityLocks"]["productionShader"]["changed"])
        self.assertFalse(
            self.value["productAuthority"]["productionShaderAuthorizedOnPass"]
        )
        self.assertFalse(
            self.value["productAuthority"]["liquidGlassParityEstablishedOnPass"]
        )


if __name__ == "__main__":
    unittest.main()
