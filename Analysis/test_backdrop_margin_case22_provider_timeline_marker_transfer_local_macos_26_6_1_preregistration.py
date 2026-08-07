#!/usr/bin/env python3
"""Integrity checks for the timeline-marker/provider preregistration."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
REPOSITORY = ANALYSIS.parent
PREREGISTRATION_PATH = (
    ANALYSIS
    / "backdrop_margin_case22_provider_timeline_marker_transfer_local_macos_26_6_1_preregistration.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TimelineMarkerPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_runtime_outcome_is_sealed(self) -> None:
        self.assertIsNone(self.value["runtimeOutcomeFrozenBeforeDispatch"])

    def test_every_frozen_file_hash_matches(self) -> None:
        for record in self.value["frozenImplementation"]["files"]:
            path = REPOSITORY / record["path"]
            self.assertTrue(path.is_file(), record["path"])
            self.assertEqual(sha256(path), record["sha256"], record["path"])

    def test_failed_interval_hypothesis_is_not_relabelled(self) -> None:
        predecessor = self.value["rejectedPredecessor"]
        self.assertEqual(predecessor["providerCallsInsideIntervals"], 0)
        self.assertTrue(predecessor["all32RenderIntervalsClosed"])
        self.assertTrue(predecessor["replacementRuntimeWindowChanged"])

    def test_transport_correction_saw_no_marker_or_provider_call(self) -> None:
        amendment = self.value["transportOperationalAmendment"]
        self.assertEqual(amendment["failedCaptureFinalTimelineMarkerCount"], 0)
        self.assertEqual(amendment["failedCaptureFinalProviderCallCount"], 0)
        self.assertFalse(amendment["opticalPredictionsEvaluatedBeforeCorrection"])
        self.assertTrue(amendment["prospectiveOpticalPredictionsUnchanged"])
        self.assertTrue(amendment["providerWindowUnchanged"])

    def test_marker_window_is_structural_and_exact(self) -> None:
        marker = self.value["timelineMarkerBoundary"]
        self.assertEqual(marker["markerCount"], 33)
        self.assertEqual(marker["moduleOffset"], 0x8BE38)
        self.assertEqual(marker["providerCaptureEnabledAfterMarkerIndex"], 0)
        self.assertEqual(marker["providerCaptureDisabledAtMarkerIndex"], 32)
        self.assertEqual(marker["sampleIndexRule"], "zero-based marker ordinal")

    def test_nonendpoint_predictions_are_prospective_and_bitwise(self) -> None:
        predictions = self.value["prospectivePredictions"]
        self.assertTrue(
            predictions["exactlyOneFullSignatureMatchPerMarkerBatchSamples1Through31"]
        )
        self.assertTrue(predictions["all18LoadedFieldPredictionsMatchForSelectedCalls"])
        self.assertTrue(predictions["marker32EndpointMatchCountIsExploratory"])
        self.assertTrue(self.value["captureContract"]["zeroTolerance"])

    def test_captured_values_cannot_select_runtime_capture(self) -> None:
        policy = self.value["selectionPolicy"]
        self.assertFalse(policy["capturedObjectOrOutputMaySelectCall"])
        self.assertEqual(
            policy["sampleBatches"], "preceding structural marker interval"
        )

    def test_product_authority_remains_narrow(self) -> None:
        authority = self.value["productAuthority"]
        self.assertTrue(
            authority["authenticatedMarkerBatchTemporalJoinMayPassForSamples1Through31"]
        )
        for key in (
            "freshMaterialAppearanceGeometryProfileTransferEstablishedOnPass",
            "upstreamCropAllocationPolicyEstablishedOnPass",
            "physicalRetinaColorPixelCompositorTransferEstablishedOnPass",
            "independentWalleZeroByteFrameParityEstablishedOnPass",
            "liquidGlassParityEstablishedOnPass",
            "productionShaderAuthorizedOnPass",
        ):
            self.assertFalse(authority[key])


if __name__ == "__main__":
    unittest.main()
