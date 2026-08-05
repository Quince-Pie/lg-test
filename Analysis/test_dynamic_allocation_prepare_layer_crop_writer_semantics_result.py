#!/usr/bin/env python3
"""Integrity tests for the opened inline integer-crop result."""

import json
import unittest
from pathlib import Path

import analyze_prepare_layer_crop_writer_semantics as analyzer


ANALYSIS_ROOT = Path(__file__).resolve().parent
RESULT = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_prepare_layer_crop_writer_semantics_result.json"
    ).read_text(encoding="utf-8")
)


class PrepareLayerCropWriterSemanticResultTests(unittest.TestCase):
    def test_run_and_artifact_identity_are_frozen(self) -> None:
        self.assertEqual(RESULT["run"]["runID"], 31048753297)
        self.assertEqual(
            RESULT["run"]["headSHA"], "9780f93745efa4c59dc7f8751154453de45a75f8"
        )
        self.assertEqual(RESULT["artifact"]["artifactID"], 8947713091)
        self.assertEqual(
            RESULT["artifact"]["digest"],
            "sha256:4858ee27b4e8c110ab10efd4b2533ce7f9a3a4d46aeae93c6c9f9623c7008cf4",
        )

    def test_add_background_hypothesis_is_explicitly_falsified(self) -> None:
        correction = RESULT["openedCorrection"]
        self.assertEqual(correction["outcome"], "falsified on the selected path")
        self.assertEqual(correction["invocationCount"], 4)
        self.assertEqual(correction["executedInstructionCountPerInvocation"], 45)
        self.assertEqual(correction["opaqueCalleeCount"], 0)
        self.assertEqual(correction["argumentMemoryChangedInvocationCount"], 0)
        self.assertEqual(correction["callerRoleChangedInvocationCount"], 0)
        self.assertEqual(correction["x5TargetChangedInvocationCount"], 0)

    def test_every_observed_crop_replays_with_exact_integer_arithmetic(self) -> None:
        observed = 0
        for invocation in RESULT["invocations"]:
            clamped, enclosure = analyzer.integer_enclosure(invocation["inputRectF64"])
            self.assertEqual(list(enclosure), invocation["integerEnclosureI32"])
            replay = (
                analyzer.padded(enclosure)
                if invocation["onePixelBorderExecuted"]
                else enclosure
            )
            self.assertEqual(list(replay), invocation["replayedWorkingCropI32"])
            self.assertEqual(len(clamped), 4)
            if invocation.get("observedDownstreamCropI32") is not None:
                observed += 1
                self.assertEqual(list(replay), invocation["observedDownstreamCropI32"])
        self.assertEqual(observed, 3)

    def test_remaining_parity_gates_are_not_promoted(self) -> None:
        boundary = RESULT["remainingBoundary"]
        conclusion = RESULT["conclusion"]
        self.assertTrue(boundary["selectedNestedCropProductionDecoded"])
        self.assertFalse(boundary["generalFloatingRectangleProductionDecoded"])
        self.assertFalse(boundary["unseenGeometryAndBoundaryTransferPassed"])
        self.assertFalse(boundary["materialAppearanceDirectionTransferPassed"])
        self.assertFalse(boundary["retina2xTransferPassed"])
        self.assertFalse(boundary["endToEndWallePixelParityPassed"])
        self.assertFalse(conclusion["productionShaderAuthorized"])
        self.assertFalse(conclusion["liquidGlassParityEstablished"])


if __name__ == "__main__":
    unittest.main()
