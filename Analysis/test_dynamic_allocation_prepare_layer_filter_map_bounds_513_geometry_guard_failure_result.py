#!/usr/bin/env python3
"""Seal the 513-point geometry-guard null result."""

import json
import unittest
from pathlib import Path


RESULT_PATH = (
    Path(__file__).resolve().parent
    / "dynamic_allocation_prepare_layer_filter_map_bounds_513_geometry_guard_failure_result.json"
)


class PrepareLayerFilterMapBounds513GeometryGuardFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_run_and_artifact_identity_are_frozen(self) -> None:
        run = self.result["run"]
        self.assertEqual(run["id"], 31070965886)
        self.assertEqual(run["conclusion"], "failure")
        artifact = self.result["artifact"]
        self.assertEqual(artifact["id"], 8955665381)
        self.assertEqual(
            artifact["digest"],
            "sha256:fd365c2cb0464a80088c225b7bdfc4b5bbe97a6e56a407f980b55cfc47d6c68f",
        )

    def test_failure_precedes_filter_trace(self) -> None:
        observed = self.result["observed"]
        self.assertEqual(observed["requestedGeometry"], "circle-513-center")
        self.assertEqual(observed["inheritedExpectedGeometry"], "circle-1025-center")
        self.assertEqual(observed["filterInstructionStateCount"], 0)
        self.assertEqual(observed["executionEventCount"], 0)
        self.assertIsNone(observed["appleArithmeticOutcome"])

    def test_null_result_cannot_claim_parity(self) -> None:
        conclusion = self.result["conclusion"]
        self.assertTrue(conclusion["contractsPassed"])
        self.assertFalse(conclusion["captureTransportReachedTarget"])
        self.assertFalse(conclusion["newFilterEvidenceProduced"])
        self.assertFalse(conclusion["liquidGlassParityEstablished"])
        retry = self.result["retryScope"]
        self.assertFalse(retry["captureSelectorChanged"])
        self.assertFalse(retry["breakpointOrMemoryReadChanged"])
        self.assertFalse(retry["filterTraceImplementationChanged"])


if __name__ == "__main__":
    unittest.main()
