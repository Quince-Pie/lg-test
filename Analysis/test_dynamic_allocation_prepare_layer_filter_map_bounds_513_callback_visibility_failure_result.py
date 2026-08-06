#!/usr/bin/env python3
"""Seal the 513 callback-visibility null result."""

import json
import unittest
from pathlib import Path


RESULT_PATH = (
    Path(__file__).resolve().parent
    / "dynamic_allocation_prepare_layer_filter_map_bounds_513_callback_visibility_failure_result.json"
)


class PrepareLayerFilterMapBounds513CallbackVisibilityFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_run_and_artifact_are_frozen(self) -> None:
        self.assertEqual(self.result["run"]["id"], 31071398653)
        self.assertEqual(self.result["run"]["conclusion"], "failure")
        self.assertEqual(self.result["artifact"]["id"], 8955813963)

    def test_geometry_repaired_before_callback_failure(self) -> None:
        observed = self.result["observed"]
        self.assertTrue(observed["geometryGuardRebound"])
        self.assertEqual(observed["traceExpectedGeometry"], "circle-513-center")
        self.assertEqual(observed["terminalStopOffset"], 0)
        self.assertEqual(observed["qualifiedHelperEntryCount"], 0)
        self.assertEqual(observed["filterInstructionStateCount"], 0)
        self.assertIsNone(observed["appleArithmeticOutcome"])

    def test_retry_is_transport_only(self) -> None:
        conclusion = self.result["conclusion"]
        self.assertTrue(conclusion["geometryTransportRepaired"])
        self.assertFalse(conclusion["callbackTransportRepaired"])
        self.assertFalse(conclusion["newFilterEvidenceProduced"])
        self.assertFalse(conclusion["liquidGlassParityEstablished"])
        retry = self.result["retryScope"]
        self.assertFalse(retry["geometryAdapterChanged"])
        self.assertFalse(retry["captureSelectorChanged"])
        self.assertFalse(retry["breakpointOrMemoryReadChanged"])


if __name__ == "__main__":
    unittest.main()
