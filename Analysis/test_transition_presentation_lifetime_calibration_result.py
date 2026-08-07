#!/usr/bin/env python3
"""Tests for the corrected presentation-lifetime calibration ledger."""

import json
from pathlib import Path
import unittest


RESULT = Path(__file__).with_name(
    "transition_presentation_lifetime_calibration_result.json"
)


class TransitionPresentationLifetimeCalibrationResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_historical_error_cannot_prove_backdrop_removal(self) -> None:
        audit = self.result["historicalInferenceAudit"]
        helper = audit["snapshotHelperSource"]
        self.assertEqual(len(helper["nilConditions"]), 4)
        self.assertFalse(helper["historicalErrorDistinguishesNilConditions"])
        self.assertFalse(helper["historicalErrorProvesBackdropRemoval"])
        self.assertFalse(audit["appearanceDependentProductLifetimeWasEstablished"])
        self.assertTrue(audit["regularDarkControl"]["unchangedSecondCaptureCompleted"])

    def test_no_debugger_calibrations_are_complete(self) -> None:
        calibrations = self.result["directRetinaCalibrations"]
        self.assertEqual(len(calibrations), 3)
        for calibration in calibrations:
            self.assertEqual(calibration["sampleCount"], 33)
            self.assertEqual(calibration["uniquePixelSHA256Count"], 33)
            self.assertEqual(calibration["presentationStateCount"], 66)
            self.assertEqual(calibration["glassBackgroundPresenceCount"], 64)
            self.assertEqual(calibration["glassForegroundPresenceCount"], 62)
            self.assertLess(calibration["maximumStateBracketSeconds"], 0.1)
            self.assertLess(calibration["maximumWindowCaptureSeconds"], 0.1)
            self.assertLess(calibration["maximumAbsoluteRequestedProgressError"], 0.01)
        uniform = calibrations[1]
        self.assertTrue(uniform["dynamicUniformCollectorExecuted"])
        self.assertEqual(uniform["dynamicUniformRecordCount"], 32)
        self.assertTrue(uniform["sample30SnapshotPresent"])
        self.assertTrue(uniform["sample31SnapshotPresent"])

    def test_calibration_does_not_claim_transfer(self) -> None:
        conclusion = self.result["calibrationConclusion"]
        self.assertTrue(
            conclusion[
                "historicalMissingSnapshotIsNotEvidenceOfAppleRemovingClearLightBackdrop"
            ]
        )
        self.assertFalse(conclusion["observerIndependentProductLifetimeTransferPassed"])
        self.assertFalse(self.result["qualityLocks"]["productionShaderChanged"])


if __name__ == "__main__":
    unittest.main()
