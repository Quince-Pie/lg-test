#!/usr/bin/env python3
"""Integrity checks for the first SDF diagnostic's null result."""

import json
import unittest
from pathlib import Path


RESULT_PATH = (
    Path(__file__).resolve().parent
    / "dynamic_allocation_prepare_layer_sdf_map_bounds_diagnostic_null_result.json"
)


class PrepareLayerSDFMapBoundsNullResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_transport_identity_is_frozen(self) -> None:
        result = self.result
        self.assertEqual(result["runID"], 31077148370)
        self.assertEqual(result["headSHA"], "a5334f79d287db504304f6891164622a010725df")
        self.assertEqual(result["workflowConclusion"], "failure")
        self.assertEqual(result["artifact"]["id"], 8958020650)
        self.assertEqual(
            result["artifact"]["digest"],
            "sha256:0cde26f28c9800f844def31c3e4bd8cbcd211544c95711babbe8259d96da92f5",
        )

    def test_failure_precedes_selector_and_capture(self) -> None:
        observed = self.result["observedFailure"]
        self.assertEqual(observed["processStoppedAt"], "prepare_layer+0")
        self.assertEqual(observed["dynamicDispatchCount"], 0)
        self.assertEqual(observed["sdfInstructionStateCount"], 0)
        self.assertFalse(observed["targetCodeCaptured"])
        self.assertFalse(observed["cropOrOutputValuesReadForSelection"])
        root = self.result["rootCause"]
        self.assertFalse(root["selectorReached"])
        self.assertFalse(root["captureRuleExercised"])
        self.assertFalse(root["scientificHypothesisTested"])

    def test_no_parity_claim_is_opened(self) -> None:
        sealed = self.result["sealedConclusion"]
        self.assertTrue(sealed["nullRun"])
        self.assertFalse(sealed["sdfCodeCaptured"])
        self.assertFalse(sealed["sdfArithmeticDiagnosed"])
        self.assertFalse(sealed["completeProfileMatrixPassed"])
        self.assertFalse(sealed["productionShaderAuthorized"])
        self.assertFalse(sealed["liquidGlassParityEstablished"])


if __name__ == "__main__":
    unittest.main()
