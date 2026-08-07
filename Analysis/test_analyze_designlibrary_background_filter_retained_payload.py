import hashlib
import json
import struct
import unittest
from pathlib import Path


ANALYSIS_DIRECTORY = Path(__file__).resolve().parent
SOURCE = ANALYSIS_DIRECTORY / "analyze_designlibrary_background_filter_retained_payload.py"
RESULT = ANALYSIS_DIRECTORY / "designlibrary_background_filter_retained_payload_result.json"
METADATA_RESULT = ANALYSIS_DIRECTORY / (
    "designlibrary_background_filter_metadata_local_macos_26_6_1_result.json"
)


class DesignLibraryBackgroundFilterRetainedPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))
        cls.payload = bytes.fromhex(cls.result["payload"]["hex"])

    def test_result_authenticates_sources(self):
        self.assertEqual(
            self.result["designLibraryBackgroundFilterRetainedPayloadAnalysisSchemaVersion"],
            1,
        )
        self.assertEqual(
            self.result["source"]["sha256"],
            hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.result["inputs"]["metadataResultSHA256"],
            hashlib.sha256(METADATA_RESULT.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.result["inputs"]["traceSHA256"],
            "e6c1075ae00dc9fb98a0768c72ed7155b9461bf6c643ba34bb26285c4439f040",
        )

    def test_complete_payload_extends_the_exact_provider_prefix(self):
        payload = self.result["payload"]
        self.assertEqual(len(self.payload), 504)
        self.assertEqual(payload["byteCount"], 504)
        self.assertEqual(payload["providerPrefixByteCount"], 384)
        self.assertEqual(payload["recoveredTailByteCount"], 120)
        self.assertEqual(
            hashlib.sha256(self.payload).hexdigest(),
            "fb9c92be37bfba81ba4f7a6d9063fe6a0170b66086885bef5116dded0155c14e",
        )
        self.assertEqual(
            hashlib.sha256(self.payload[:384]).hexdigest(),
            "c70501b12b2c3e5003ae9ed96416816832b26b10741845ca23f6e10e990e23d1",
        )
        tail = bytes.fromhex(payload["recoveredTailHex"])
        self.assertEqual(tail, self.payload[384:])
        self.assertEqual(
            hashlib.sha256(tail).hexdigest(),
            "70d3765c2bbfda2f6e1c9af2de8fda14210ddb9ed485f3b7dd7a15d3301e8a6f",
        )

    def test_every_scalar_record_replays_raw_payload_bytes(self):
        names = set()
        format_by_size = {1: "?", 4: "f", 8: None}
        for record in self.result["decodedScalars"]:
            self.assertNotIn(record["name"], names)
            names.add(record["name"])
            offset = int(record["offset"], 16)
            byte_count = record["byteCount"]
            raw = self.payload[offset : offset + byte_count]
            self.assertEqual(raw.hex(), record["hex"])
            code = format_by_size[byte_count]
            if code is not None:
                self.assertEqual(struct.unpack("<" + code, raw)[0], record["value"])

    def test_new_tail_and_previously_ambiguous_fields_are_semantic(self):
        values = {record["name"]: record["value"] for record in self.result["decodedScalars"]}
        self.assertEqual(values["refraction.innerAmount"], -6.10015869140625)
        self.assertEqual(values["bleed.amount"], 5.030663807876408)
        self.assertEqual(values["bleed.useDarkenBlending"], True)
        self.assertEqual(
            values["sdrAdjustment.headroomTransitionPoint"], 1017.66943359375
        )
        self.assertEqual(values["sdrAdjustment.faceDimming.whitePointShift"], 1.0)
        self.assertEqual(values["flags.rawValue"], 98688)

    def test_all_optional_resolved_color_storage_is_retained(self):
        records = self.result["rawOptionalResolvedColors"]
        self.assertEqual(len(records), 9)
        self.assertEqual(
            [record["name"] for record in records],
            [
                "shadow.ycc.normalFill",
                "shadow.ycc.dodgeFill",
                "shadow.ycc.burnFill",
                "face.ycc.normalFill",
                "face.ycc.dodgeFill",
                "face.ycc.burnFill",
                "bleed.ycc.normalFill",
                "bleed.ycc.dodgeFill",
                "bleed.ycc.burnFill",
            ],
        )
        for record in records:
            offset = int(record["offset"], 16)
            self.assertEqual(record["byteCount"], 20)
            self.assertEqual(self.payload[offset : offset + 20].hex(), record["hex"])

    def test_result_does_not_overclaim_parity_or_shader_authority(self):
        claims = self.result["claims"]
        self.assertTrue(claims["completeRetainedPayloadRecovered"])
        self.assertFalse(claims["capturedProviderPrefixWasCompleteValue"])
        self.assertFalse(claims["publicInputConstructionRecovered"])
        self.assertFalse(claims["cropAllocationPolicyRecovered"])
        self.assertFalse(claims["liquidGlassParityEstablished"])
        self.assertFalse(claims["productionShaderChangeAuthorized"])


if __name__ == "__main__":
    unittest.main()
