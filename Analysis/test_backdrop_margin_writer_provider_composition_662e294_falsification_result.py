"""Recompute the exact provider-only margin falsification from retained bytes."""

from __future__ import annotations

import hashlib
import json
import math
import struct
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
ROOT = ANALYSIS.parent
RESULT = ANALYSIS / "backdrop_margin_writer_provider_composition_662e294_falsification_result.json"


class BackdropMarginWriterProviderCompositionFalsificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(RESULT.read_text(encoding="utf-8"))
        inputs = cls.value["inputs"]
        cls.paths = {key: ROOT / record["path"] for key, record in inputs.items()}
        for key, path in cls.paths.items():
            assert hashlib.sha256(path.read_bytes()).hexdigest() == inputs[key]["sha256"]
        cls.trace = json.loads(cls.paths["trace"].read_text(encoding="utf-8"))
        cls.timeline = json.loads(cls.paths["timeline"].read_text(encoding="utf-8"))

    def test_capture_is_complete_and_failure_free(self) -> None:
        self.assertEqual(self.trace["failures"], [])
        self.assertEqual(self.trace["finalFailureCount"], 0)
        self.assertEqual(self.trace["eventTypeCounts"], {
            "backdropBounds": 303,
            "copyEntry": 466,
            "copyMarginStore": 270,
            "marginSetter": 149,
        })
        self.assertEqual(self.timeline["sampleCount"], 33)
        self.assertEqual(self.timeline["failedSamples"], 0)
        self.assertEqual(len(self.timeline["dynamicBackgroundUniforms"]["records"]), 32)

    def test_every_producer_return_equals_its_setter_word(self) -> None:
        setters = [event for event in self.trace["events"] if event["type"] == "marginSetter"]
        self.assertEqual(len(setters), 149)
        self.assertTrue(all(event["producerInvocation"]["complete"] for event in setters))
        self.assertTrue(all(
            event["producerInvocation"]["producerReturnF64RawLittleEndianHex"]
            == event["marginF64RawLittleEndianHex"]
            for event in setters
        ))

    def test_all_32_object_joined_chains_equal_maximum_bleed_not_provider(self) -> None:
        events = self.trace["events"]
        setters = [event for event in events if event["type"] == "marginSetter"]
        copies = [event for event in events if event["type"] == "copyMarginStore"]
        bounds = [event for event in events if event["type"] == "backdropBounds"]
        chains = {}
        for bound in bounds:
            candidates = [
                event for event in copies
                if event["renderSelf"] == bound["renderSelf"]
                and event["eventIndex"] < bound["eventIndex"]
            ]
            if not candidates:
                continue
            copy = max(candidates, key=lambda event: event["eventIndex"])
            candidates = [
                event for event in setters
                if event["modelSelf"] == copy["modelSelf"]
                and event["eventIndex"] < copy["eventIndex"]
            ]
            if not candidates:
                continue
            setter = max(candidates, key=lambda event: event["eventIndex"])
            chain = chains.setdefault(copy["eventIndex"], (setter, copy, []))
            chain[2].append(bound)
        self.assertEqual(len(chains), 32)
        for setter, copy, joined_bounds in chains.values():
            self.assertEqual(setter["marginF64RawLittleEndianHex"], "66666666666e6440")
            self.assertEqual(copy["marginF32RawLittleEndianHex"], "33732343")
            self.assertTrue(joined_bounds)
            self.assertEqual(
                {bound["marginF32RawLittleEndianHex"] for bound in joined_bounds},
                {"33732343"},
            )

        records = self.timeline["dynamicBackgroundUniforms"]["records"]
        maximum_bleed = max(
            float(record["filter"]["inputValues"]["inputBleedAmount"])
            for record in records
        )
        provider_returns = []
        for record in records:
            inputs = record["filter"]["inputValues"]
            offset_x, offset_y = struct.unpack(
                "<2d", bytes.fromhex(inputs["inputShadowOffset"]["hex"])
            )
            provider_returns.append(
                max(math.fabs(offset_x), math.fabs(offset_y))
                + math.fabs(float(inputs["inputShadowAmount"]))
            )
        self.assertEqual(struct.pack("<d", maximum_bleed).hex(), "66666666666e6440")
        self.assertEqual(struct.pack("<d", max(provider_returns)).hex(), "0000000000c05440")
        self.assertNotEqual("66666666666e6440", "0000000000c05440")

    def test_result_rejects_parity_authority(self) -> None:
        self.assertTrue(self.value["conclusion"]["providerOnlyRegularGroupMarginCandidateFalsified"])
        self.assertFalse(self.value["conclusion"]["correctedCandidateProspectiveAuthorityEstablished"])
        for key in (
            "allocationMarginCompositionEstablished",
            "selectedRegionPolicyEstablished",
            "physicalRetinaColorPixelCompositorTransferEstablished",
            "independentWalleZeroByteFrameParityEstablished",
            "productionShaderAuthorized",
            "liquidGlassParityEstablished",
        ):
            self.assertFalse(self.value["authority"][key], key)


if __name__ == "__main__":
    unittest.main()
