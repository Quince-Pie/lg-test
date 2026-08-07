"""Verify the immutable direct-Retina v6 regular pass and clear-path rejection."""

from __future__ import annotations

import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
ROOT = ANALYSIS.parent
RESULT = ANALYSIS / "backdrop_margin_writer_provider_composition_36588cf_matrix_interim_result.json"


def load_hashed(entry: dict[str, object], key: str) -> dict[str, object]:
    path = ROOT / str(entry[key])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry[f"{key}SHA256"]
    return json.loads(path.read_text(encoding="utf-8"))


class BackdropMarginWriterProviderCompositionMatrixInterimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_regular_dark_second_capture_is_a_complete_bitwise_pass(self) -> None:
        record = self.result["regularDark"]["secondCapture"]
        trace = load_hashed(record, "trace")
        timeline = load_hashed(record, "timeline")
        validation = load_hashed(record, "validation")
        self.assertEqual(trace["failures"], [])
        self.assertEqual(len(trace["events"]), record["eventCount"])
        self.assertEqual(
            Counter(event["type"] for event in trace["events"]),
            Counter(record["eventTypeCounts"]),
        )
        self.assertEqual(timeline["sampleCount"], 33)
        self.assertEqual(
            len(timeline["dynamicBackgroundUniforms"]["records"]), 32
        )
        candidate = validation["candidate"]
        self.assertEqual(
            candidate["providerMaximumF64RawLittleEndianHex"],
            record["providerMaximumF64RawLittleEndianHex"],
        )
        self.assertEqual(
            candidate["bleedMaximumF64RawLittleEndianHex"],
            record["bleedMaximumF64RawLittleEndianHex"],
        )
        self.assertEqual(
            candidate["regularGroupContributionMaximumF64RawLittleEndianHex"],
            record["correctedRegularMaximumF64RawLittleEndianHex"],
        )
        self.assertEqual(
            candidate["expectedRenderMarginF32RawLittleEndianHex"],
            record["renderAndBoundsMarginF32RawLittleEndianHex"],
        )
        self.assertEqual(
            validation["writerExecution"]["completeChainCount"], 32
        )
        self.assertTrue(
            validation["sealedConclusion"]
            ["publicProviderGroupWriterCompositionProspectiveBitExactForThisCase"]
        )

    def test_regular_first_capture_failed_closed_before_a_bounds_chain(self) -> None:
        record = self.result["regularDark"]["firstCapture"]
        trace = load_hashed(record, "trace")
        timeline = load_hashed(record, "timeline")
        self.assertEqual(timeline["error"], record["timelineError"])
        self.assertEqual(set(trace["codeGates"]), {"copy", "setter"})
        self.assertFalse(record["partialCaptureAcceptedAsProspectivePass"])

    def test_both_clear_captures_are_exhaustively_positive_zero(self) -> None:
        clear = self.result["clearLight"]
        setter_total = 0
        copy_total = 0
        for record in clear["captures"]:
            trace = load_hashed(record, "trace")
            timeline = load_hashed(record, "timeline")
            self.assertEqual(timeline["error"], clear["commonTimelineError"])
            self.assertEqual(trace["failures"], [])
            self.assertEqual(set(trace["codeGates"]), {"copy", "setter"})
            setters = [
                event for event in trace["events"] if event["type"] == "marginSetter"
            ]
            copies = [
                event
                for event in trace["events"]
                if event["type"] == "copyMarginStore"
            ]
            self.assertTrue(setters)
            self.assertTrue(copies)
            self.assertEqual(
                {event["marginF64RawLittleEndianHex"] for event in setters},
                {"0000000000000000"},
            )
            self.assertEqual(
                {
                    event["producerInvocation"]
                    ["producerReturnF64RawLittleEndianHex"]
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
            setter_total += len(setters)
            copy_total += len(copies)
        self.assertEqual(setter_total, clear["combinedMarginSetterCount"])
        self.assertEqual(copy_total, clear["combinedCopyMarginStoreCount"])
        self.assertFalse(clear["v6CompleteClearTransferPassed"])
        self.assertFalse(clear["partialCapturePromotedToProspectivePass"])

    def test_no_product_parity_is_claimed(self) -> None:
        conclusion = self.result["conclusion"]
        self.assertTrue(conclusion["correctedRegularCompositionProspectivelyEstablished"])
        for key in (
            "v6FourCaseMatrixPassed",
            "allocationMarginCompositionFullyClosed",
            "selectedRegionPolicyEstablished",
            "physicalRetinaColorPixelCompositorTransferEstablished",
            "independentWalleZeroByteFrameParityEstablished",
            "productionShaderAuthorized",
            "liquidGlassParityEstablished",
        ):
            self.assertFalse(conclusion[key], key)


if __name__ == "__main__":
    unittest.main()
