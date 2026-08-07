"""Verify the direct-Retina clear-dark zero-margin pass and removal rejection."""

from __future__ import annotations

import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
ROOT = ANALYSIS.parent
RESULT = ANALYSIS / "backdrop_margin_writer_clear_dark_0e39ce7_result.json"


def load_hashed(entry: dict[str, str]) -> object:
    path = ROOT / entry["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return path.read_text(encoding="utf-8")


class BackdropMarginWriterClearDarkResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))
        inputs = cls.result["inputs"]
        cls.trace = load_hashed(inputs["trace"])
        cls.timeline = load_hashed(inputs["timeline"])
        cls.validation = load_hashed(inputs["zeroMarginValidation"])
        cls.rejection = load_hashed(inputs["combinedGateRejection"])
        load_hashed(inputs["preflight"])
        load_hashed(inputs["captureContext"])

    def test_complete_dark_capture_retains_bounds(self) -> None:
        capture = self.result["capture"]
        self.assertEqual(self.trace["failures"], [])
        self.assertEqual(len(self.trace["events"]), capture["eventCount"])
        self.assertEqual(
            Counter(event["type"] for event in self.trace["events"]),
            Counter(capture["eventTypeCounts"]),
        )
        self.assertEqual(set(self.trace["codeGates"]), {"copy", "setter", "bounds"})
        self.assertEqual(self.timeline["sampleCount"], 33)
        self.assertEqual(self.timeline["failedSamples"], 0)
        self.assertEqual(
            len(self.timeline["dynamicBackgroundUniforms"]["records"]), 32
        )

    def test_every_live_margin_word_is_positive_zero(self) -> None:
        events = self.trace["events"]
        setters = [event for event in events if event["type"] == "marginSetter"]
        copies = [event for event in events if event["type"] == "copyMarginStore"]
        bounds = [event for event in events if event["type"] == "backdropBounds"]
        self.assertEqual(
            {event["marginF64RawLittleEndianHex"] for event in setters},
            {"0000000000000000"},
        )
        self.assertEqual(
            {
                event["producerInvocation"]["producerReturnF64RawLittleEndianHex"]
                for event in setters
            },
            {"0000000000000000"},
        )
        self.assertTrue(
            all(
                event["producerInvocation"]["complete"] is True
                and event["producerInvocation"]
                ["producerReturnF64RawLittleEndianHex"]
                == event["marginF64RawLittleEndianHex"]
                for event in setters
            )
        )
        self.assertEqual(
            {event["marginF32RawLittleEndianHex"] for event in copies},
            {"00000000"},
        )
        self.assertEqual(
            {event["marginF32RawLittleEndianHex"] for event in bounds},
            {"00000000"},
        )

    def test_unchanged_v6_validator_grants_prospective_bitwise_pass(self) -> None:
        self.assertEqual(self.validation["conclusion"], "success")
        self.assertEqual(self.validation["profile"]["caseRole"], "prospective-holdout")
        self.assertEqual(
            self.validation["candidate"]["maximumRequiredMarginF64RawLittleEndianHex"],
            "0000000000000000",
        )
        self.assertEqual(
            self.validation["candidate"]["expectedRenderMarginF32RawLittleEndianHex"],
            "00000000",
        )
        self.assertEqual(self.validation["writerExecution"]["completeChainCount"], 32)
        self.assertTrue(
            self.validation["sealedConclusion"]
            ["publicProviderGroupWriterCompositionProspectiveBitExactForThisCase"]
        )

    def test_combined_removal_gate_failed_for_the_declared_reason(self) -> None:
        self.assertIn("clear presentation removal error differs", self.rejection)
        lifetime = self.result["presentationLifetime"]
        self.assertTrue(lifetime["universalClearRemovalCandidateFalsified"])
        self.assertFalse(lifetime["generalAppearanceDependentLifetimePolicyEstablished"])

    def test_product_parity_remains_unclaimed(self) -> None:
        conclusion = self.result["conclusion"]
        self.assertTrue(conclusion["regularMarginCompositionProspectivelyEstablished"])
        self.assertTrue(conclusion["clearMarginCompositionProspectivelyEstablished"])
        for key in (
            "generalSelectedRegionAndLifetimePolicyEstablished",
            "physicalRetinaColorPixelCompositorTransferEstablished",
            "independentWalleZeroByteFrameParityEstablished",
            "productionShaderAuthorized",
            "liquidGlassParityEstablished",
        ):
            self.assertFalse(conclusion[key], key)


if __name__ == "__main__":
    unittest.main()
