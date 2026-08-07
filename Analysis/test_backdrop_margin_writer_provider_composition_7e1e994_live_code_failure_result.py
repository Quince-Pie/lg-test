"""Integrity checks for the complete-input/live-code identity failure."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
ROOT = ANALYSIS.parent
RESULT = ANALYSIS / "backdrop_margin_writer_provider_composition_7e1e994_live_code_failure_result.json"


class BackdropMarginWriterProviderCompositionLiveCodeFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_inputs_match(self) -> None:
        for record in self.value["inputs"].values():
            path = ROOT / record["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record["sha256"])

    def test_input_opened_but_target_did_not(self) -> None:
        self.assertEqual(self.value["retinaTimeline"]["dynamicPublicRecordCount"], 32)
        self.assertEqual(self.value["writerTrace"]["setterEventCount"], 0)
        self.assertEqual(self.value["writerTrace"]["copyStoreEventCount"], 0)
        outcome = self.value["outcome"]
        self.assertTrue(outcome["candidateInputOpened"])
        self.assertFalse(outcome["targetWriterMarginObserved"])
        self.assertFalse(outcome["candidateTestedAgainstTarget"])
        self.assertFalse(outcome["caseAcceptedAsProspectiveEvidence"])

    def test_failure_has_no_product_authority(self) -> None:
        for key, value in self.value["authority"].items():
            self.assertFalse(value, key)


if __name__ == "__main__":
    unittest.main()
