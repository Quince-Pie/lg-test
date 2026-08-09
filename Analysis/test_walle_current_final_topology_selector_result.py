#!/usr/bin/env python3
"""Contracts for the accepted current-final topology-selector holdout."""

import hashlib
import json
from pathlib import Path
import unittest


ANALYSIS = Path(__file__).resolve().parent
RESULT = ANALYSIS / "walle_current_final_topology_selector_fd24b42_result.json"
PREREGISTRATION = ANALYSIS / "walle_current_final_topology_selector_preregistration.json"
EXPECTED_RESULT_SHA256 = "a4553d0a36c3e18496ea3e1d28a6a55bfac876ea9b04468a85189c9c37947206"


class AcceptedCurrentFinalTopologySelectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_result_is_the_immutable_direct_retina_validation(self) -> None:
        self.assertEqual(hashlib.sha256(RESULT.read_bytes()).hexdigest(), EXPECTED_RESULT_SHA256)
        self.assertEqual(
            self.result["capture"]["preregistrationSHA256"],
            hashlib.sha256(PREREGISTRATION.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.result["capture"]["timelineSHA256"],
            "d0584a6b95147630018c9477ca542311e71ea95361d2e669962f1444deafb1ce",
        )
        self.assertFalse(self.result["capture"]["githubActionsUsed"])
        self.assertFalse(self.result["capture"]["nativeCaptureDebuggerUsed"])
        self.assertFalse(self.result["capture"]["nixStorePathInNativeBuildOrCapture"])

    def test_negative_one_ulp_discriminator_selects_compact_mesh(self) -> None:
        discriminator = self.result["discriminator"]
        self.assertEqual(discriminator["radiusUlpDelta"], [-1, -1])
        self.assertTrue(discriminator["oldInequalityPredicatePredictedBorder"])
        self.assertFalse(discriminator["directionalPredicatePredictedBorder"])
        self.assertEqual(discriminator["observedVertexCount"], 4)
        self.assertEqual(discriminator["observedIndexCount"], 6)
        self.assertEqual(discriminator["applePassReplayMismatchedBytes"], 0)

    def test_gate_closes_algorithm_unknown_without_claiming_product_parity(self) -> None:
        gate = self.result["gate"]
        self.assertTrue(gate["prospectiveDiscriminatorExact"])
        self.assertTrue(gate["oldPredicateFalsified"])
        self.assertTrue(gate["selectorMayBeIntegratedIntoWalle"])
        self.assertEqual(gate["remainingWalleAlgorithmUnknowns"], 0)
        self.assertFalse(gate["productionWalleParityEstablished"])
        self.assertTrue(gate["freshProductionWalleFrameRequired"])
        self.assertFalse(gate["shaderQualityReductionAllowed"])


if __name__ == "__main__":
    unittest.main()
