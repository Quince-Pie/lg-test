#!/usr/bin/env python3
"""Tests for the passed runtime-unseen circle-500 origin holdout."""

import json
from pathlib import Path
import unittest


ANALYSIS = Path(__file__).parent
RESULT = ANALYSIS / "variable_blur_selected_region_origin_circle500_holdout_result.json"
PREREGISTRATION = ANALYSIS / (
    "variable_blur_selected_region_origin_circle500_holdout_preregistration.json"
)


class VariableBlurOriginHoldoutResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))
        cls.preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    def test_unseen_transfer_passes_every_exact_count(self) -> None:
        result = self.result
        required = self.preregistration["requiredGate"]
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["authority"], "holdout")
        self.assertEqual(result["geometry"], "circle-500-center")
        self.assertEqual(result["sampleCount"], required["helperRecordCount"])
        for prefix in ("origin", "desiredExtent", "allocationExtent"):
            self.assertEqual(
                result[prefix + "ComponentCount"],
                required[prefix + "ComponentCount"],
            )
            self.assertEqual(result[prefix + "MismatchedComponents"], 0)
        self.assertEqual(result["radiusBinary32Count"], 32)
        self.assertEqual(result["radiusBinary32Mismatches"], 0)
        self.assertTrue(result["selectedRegionOriginTransferPassed"])
        self.assertTrue(result["selectedRegionAllocationTransferPassed"])

    def test_phase_and_storage_discriminators_recur(self) -> None:
        states = self.result["states"]
        self.assertEqual(
            {state["alignmentScale"] for state in states},
            {16, 32, 64, 128},
        )
        exposed = [
            state for state in states if state["helperDesiredExtent"] == [736, 736]
        ]
        self.assertEqual(len(exposed), 2)
        self.assertTrue(
            all(state["allocatedExtent"] == [768, 768] for state in exposed)
        )
        self.assertEqual(states[-2]["alignmentScale"], 128)
        self.assertEqual(states[-1]["alignmentScale"], 64)

    def test_remaining_parity_gates_stay_closed(self) -> None:
        for field in (
            "appearanceDependentPresentationLifetimePassed",
            "capturedInputOpticalTransferPassed",
            "temporalMeshSourceMipTransferPassed",
            "physicalRetinaOutputTransferPassed",
            "independentWalleZeroByteParityPassed",
            "liquidGlassParityEstablished",
            "productionShaderChanged",
        ):
            self.assertFalse(self.result[field])


if __name__ == "__main__":
    unittest.main()
