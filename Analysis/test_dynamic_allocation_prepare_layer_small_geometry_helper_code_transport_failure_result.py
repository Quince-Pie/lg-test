#!/usr/bin/env python3
"""Integrity checks for the failed small-geometry helper transport."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


RESULT_PATH = (
    Path(__file__).resolve().parent
    / "dynamic_allocation_prepare_layer_small_geometry_helper_code_transport_failure_result.json"
)


class SmallGeometryHelperCodeTransportFailureResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_failed_run_identity_is_immutable(self) -> None:
        run = self.result["run"]
        artifact = self.result["artifact"]
        self.assertEqual(run["id"], 31086167113)
        self.assertEqual(run["headSHA"], "1019a15720e2a9cd1dc3efb7bfc639cee1da3199")
        self.assertEqual(run["conclusion"], "failure")
        self.assertEqual(artifact["id"], 8961552790)
        self.assertFalse(artifact["timelinePresent"])
        self.assertFalse(artifact["validationPresent"])

    def test_failure_is_transport_not_semantic_evidence(self) -> None:
        failure = self.result["transportFailure"]
        conclusion = self.result["conclusion"]
        self.assertFalse(failure["inheritedExecutionTraceCompleted"])
        self.assertFalse(failure["scientificAcceptanceGateRan"])
        self.assertTrue(conclusion["staticBytesSalvagedAsFailureEvidence"])
        self.assertFalse(conclusion["helperCodeOpeningAccepted"])
        self.assertFalse(conclusion["liquidGlassParityEstablished"])

    def test_retained_targets_are_never_promoted_to_acceptance(self) -> None:
        evidence = self.result["retainedStaticEvidence"]
        self.assertTrue(evidence["selectionWasOutputBlind"])
        self.assertEqual(len(evidence["targets"]), 2)
        for target in evidence["targets"]:
            self.assertEqual(len(target["observedCodeSHA256"]), 64)
        retry = self.result["retryScope"]
        self.assertFalse(retry["codeHashAcceptedBeforeRetry"])
        self.assertFalse(retry["staticTargetChanged"])
        self.assertFalse(retry["selectorChanged"])
        self.assertFalse(retry["memoryReadChanged"])


if __name__ == "__main__":
    unittest.main()
