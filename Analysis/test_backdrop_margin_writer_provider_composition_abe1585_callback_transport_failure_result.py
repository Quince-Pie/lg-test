"""Integrity checks for the direct-callback namespace transport failure."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
ROOT = ANALYSIS.parent
RESULT = (
    ANALYSIS
    / "backdrop_margin_writer_provider_composition_abe1585_"
    "callback_transport_failure_result.json"
)


class BackdropMarginWriterProviderCompositionCallbackFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_retained_files_match(self) -> None:
        for key in ("retinaPreflight", "trace", "lldb"):
            record = self.value[key]
            path = ROOT / record["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record["sha256"])

    def test_no_candidate_input_or_writer_event_exists(self) -> None:
        self.assertEqual(self.value["trace"]["eventCount"], 0)
        self.assertEqual(self.value["trace"]["codeGateCount"], 0)
        outcome = self.value["outcome"]
        for key in (
            "applicationCompleted",
            "timelineCreated",
            "writerEventObserved",
            "appleMarginObserved",
            "appleCropObserved",
            "candidateTested",
            "caseAcceptedAsProspectiveEvidence",
        ):
            self.assertFalse(outcome[key], key)

    def test_failure_has_no_product_authority(self) -> None:
        for key, value in self.value["authority"].items():
            self.assertFalse(value, key)


if __name__ == "__main__":
    unittest.main()
