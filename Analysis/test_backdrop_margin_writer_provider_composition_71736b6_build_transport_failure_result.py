"""Integrity checks for the pre-launch SDK-sysroot transport failure."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
ROOT = ANALYSIS.parent
RESULT = (
    ANALYSIS
    / "backdrop_margin_writer_provider_composition_71736b6_"
    "build_transport_failure_result.json"
)


class BackdropMarginWriterProviderCompositionBuildFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_retina_session_passed_but_no_application_launched(self) -> None:
        self.assertTrue(self.value["retinaPreflight"]["passed"])
        outcome = self.value["outcome"]
        for key in (
            "applicationBuilt",
            "applicationLaunched",
            "lldbStarted",
            "timelineCreated",
            "writerTraceCreated",
            "appleMarginObserved",
            "appleCropObserved",
            "appleImageObserved",
            "candidateTested",
            "caseConsumedAsProspectiveEvidence",
        ):
            self.assertFalse(outcome[key], key)

    def test_retained_diagnostics_match(self) -> None:
        for record in (self.value["retinaPreflight"], self.value["buildFailure"]):
            path_key = "path" if "path" in record else "stderrPath"
            path = ROOT / record[path_key]
            self.assertTrue(path.is_file())
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record["sha256"] if "sha256" in record else record["stderrSHA256"])

    def test_failure_has_no_product_authority(self) -> None:
        for key, value in self.value["authority"].items():
            self.assertFalse(value, key)


if __name__ == "__main__":
    unittest.main()
