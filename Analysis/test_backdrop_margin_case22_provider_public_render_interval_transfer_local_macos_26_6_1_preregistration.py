#!/usr/bin/env python3
"""Integrity checks for the public-render/provider transfer contract."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
PREREGISTRATION_PATH = (
    ANALYSIS
    / "backdrop_margin_case22_provider_public_render_interval_transfer_local_macos_26_6_1_preregistration.json"
)
VALUE = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))


class PublicRenderIntervalTransferPreregistrationTests(unittest.TestCase):
    def test_preregistration_is_canonical_json(self) -> None:
        self.assertEqual(
            PREREGISTRATION_PATH.read_text(encoding="utf-8"),
            json.dumps(VALUE, indent=2, sort_keys=True) + "\n",
        )

    def test_every_frozen_implementation_hash_matches(self) -> None:
        for record in VALUE["frozenImplementation"]["files"]:
            path = ANALYSIS.parent / record["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record["sha256"])

    def test_structural_boundary_is_exact_and_value_blind(self) -> None:
        boundary = VALUE["structuralRenderBoundary"]
        self.assertEqual(boundary["mainUUID"], "F8B0B6E3-3270-3C94-817F-B4914852D04C")
        self.assertEqual(boundary["renderCallOffset"], 0x1000)
        self.assertEqual(boundary["renderReturnOffset"], 0x1004)
        self.assertEqual(boundary["renderCallInstructionHex"], "dfcfff97")
        self.assertFalse(boundary["capturedValueUsedForSelection"])

    def test_predictions_are_complete_and_frozen_before_dispatch(self) -> None:
        predictions = VALUE["prospectivePredictions"]
        self.assertEqual(len(predictions["selector"]), 4)
        self.assertEqual(predictions["loadedScalarFieldCount"], 18)
        self.assertEqual(predictions["uniqueFullSignatureMatchesPerSamples1Through31"], 1)
        self.assertEqual(predictions["fullSignatureMatchesForRepeatedEndpointSample32"], 2)
        self.assertEqual(predictions["partialSignatureMatchesPerInterval"], 0)
        self.assertIsNone(VALUE["runtimeOutcomeFrozenBeforeDispatch"])
        self.assertTrue(VALUE["unknownBeforeDispatch"])
        self.assertTrue(all(value is None for value in VALUE["unknownBeforeDispatch"].values()))

    def test_native_capture_requires_unlocked_awake_retina(self) -> None:
        preflight = VALUE["nativeSessionPreflight"]
        self.assertFalse(preflight["requireSessionLocked"])
        self.assertTrue(preflight["requireSessionOnConsole"])
        self.assertTrue(preflight["requireDisplayActive"])
        self.assertFalse(preflight["requireDisplayAsleep"])
        self.assertEqual(preflight["requirePhysicalPixels"], [3456, 2234])
        self.assertEqual(preflight["requireLogicalPoints"], [1728, 1117])
        self.assertEqual(preflight["requireBackingScaleFactor"], 2)

    def test_preflight_correction_precedes_dispatch_and_preserves_predictions(self) -> None:
        amendment = VALUE["operationalAmendment"]
        self.assertTrue(amendment["noAppleApplicationDispatchedBeforeCorrection"])
        self.assertTrue(amendment["prospectivePredictionsUnchanged"])
        self.assertTrue(amendment["runtimeOutcomeStillNull"])
        self.assertFalse(
            amendment["observedUnlockedSessionEvidence"][
                "cgSessionScreenIsLockedKeyPresent"
            ]
        )

    def test_symbol_presentation_correction_saw_no_optical_intervals(self) -> None:
        amendment = VALUE["symbolIdentityOperationalAmendment"]
        self.assertEqual(amendment["failedCaptureFinalIntervalCount"], 0)
        self.assertEqual(amendment["failedCaptureFinalCallCount"], 0)
        self.assertFalse(amendment["opticalPredictionsEvaluatedBeforeCorrection"])
        self.assertTrue(amendment["prospectiveOpticalPredictionsUnchanged"])

    def test_framework_identity_correction_saw_no_optical_intervals(self) -> None:
        amendment = VALUE["frameworkSymbolIdentityOperationalAmendment"]
        self.assertEqual(amendment["failedCaptureFinalIntervalCount"], 0)
        self.assertEqual(amendment["failedCaptureFinalCallCount"], 0)
        self.assertFalse(amendment["opticalPredictionsEvaluatedBeforeCorrection"])
        self.assertTrue(amendment["prospectiveOpticalPredictionsUnchanged"])

    def test_product_authority_remains_narrow_even_on_pass(self) -> None:
        authority = VALUE["productAuthority"]
        self.assertTrue(authority["authenticatedPerRenderCallbackIntervalJoinMayPass"])
        self.assertTrue(authority["prospectiveOpenedProfilePublicWordTransferMayPass"])
        for key, value in authority.items():
            if key.endswith("OnPass"):
                self.assertFalse(value, key)


if __name__ == "__main__":
    unittest.main()
