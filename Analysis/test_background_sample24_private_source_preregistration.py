import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PREREGISTRATION = (
    ROOT / "Analysis/background_sample24_private_source_preregistration.json"
)


class BackgroundSample24PrivateSourcePreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    def test_frozen_inputs_match(self) -> None:
        for relative, expected in self.record["frozenInputs"].items():
            actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, relative)

    def test_scope_and_acceptance_are_fail_closed(self) -> None:
        self.assertEqual(self.record["status"], "frozen-before-capture")
        self.assertEqual(self.record["profile"]["sampleIndex"], 24)
        self.assertEqual(self.record["acceptance"]["tolerance"], 0)
        self.assertEqual(self.record["acceptance"]["maximumUnequalHalfWords"], 0)
        self.assertEqual(self.record["acceptance"]["maximumUnequalLayerBytes"], 0)
        self.assertTrue(self.record["acceptance"]["sameRenderPairingRequired"])
        self.assertFalse(
            self.record["acceptance"][
                "capturedCoordinateOrPixelTableMayBecomeProductInput"
            ]
        )

    def test_required_private_and_custom_sources_are_distinct(self) -> None:
        evidence = self.record["requiredEvidence"]
        self.assertEqual(
            evidence["mainHalfSources"],
            ["private-main-final-color", "final-color"],
        )
        self.assertEqual(
            evidence["shadowHalfSources"],
            ["private-shadow-final-color", "custom-shadow-layer"],
        )


if __name__ == "__main__":
    unittest.main()
