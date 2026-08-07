"""Integrity checks for the no-event live-UUID transport failure."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
ROOT = ANALYSIS.parent
RESULT = (
    ANALYSIS
    / "backdrop_margin_writer_provider_composition_d949727_"
    "structural_transport_failure_result.json"
)


class BackdropMarginWriterProviderCompositionStructuralFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_retained_inputs_are_exact(self) -> None:
        for key in ("retinaPreflight", "trace", "timeline", "liveModuleIdentityDiagnostic"):
            record = self.value[key]
            path = ROOT / record["path"]
            self.assertTrue(path.is_file(), record["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record["sha256"])

    def test_no_writer_or_candidate_value_was_available(self) -> None:
        self.assertEqual(self.value["trace"]["eventCount"], 0)
        self.assertEqual(self.value["timeline"]["dynamicPublicRecordCount"], 0)
        outcome = self.value["outcome"]
        for key in (
            "completeTimelineCreated",
            "writerEventObserved",
            "appleMarginObserved",
            "appleCropObserved",
            "dynamicCandidateInputObserved",
            "candidateTested",
            "caseAcceptedAsProspectiveEvidence",
        ):
            self.assertFalse(outcome[key], key)

    def test_failure_has_no_product_authority(self) -> None:
        for key, value in self.value["authority"].items():
            self.assertFalse(value, key)


if __name__ == "__main__":
    unittest.main()
