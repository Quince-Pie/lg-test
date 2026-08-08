#!/usr/bin/env python3
"""Tests for the frozen small-clear Tghn intervention validator."""

import json
from pathlib import Path
import tempfile
import unittest

import validate_small_clear_background_intervention as subject


FRAGMENT = bytes.fromhex(
    "40fc733c000000000000000040fc73bc4038b4c0eb5d083f7d6f963f"
    "ba41ae3f003cc0bd003c40bde691123e00000000000000000000807f"
    "330e6b4028d2d93e000000000000803d000000000000807f063ca313"
    "c609351ffe0c073c3805351f0d0c5614063c351f003c16ac849e812c"
    "daa4a43b9e9e812cdea414ac0d3c812cf73bc8a225950000019ce43b"
    "89950000109cb8a2fc3b000000000000be739a3c022ea32c00007ca5"
    "e0c102ae00000000022e00000000022e003c0000000000000000003c"
    "02ae02aa0f3c0000fa3b0000003c"
)
VERTEX = bytes.fromhex(
    "b9eafd432cbce043000000000000803f30fdb6b53ffcf3c040aeda40"
    "00ea61c0003c003c003c003c000000000000f03fd9a50d442cbce043"
    "000000000000803fffff5f423ffcf3c0cb2e834200ea61c0003c003c"
    "003c003cb036666f01000000d9a50d44930e0144000000000000803f"
    "ffff5f4200006042cb2e83422fe97c42003c003c003c003c00000000"
    "00000000b9eafd43930e0144000000000000803f30fdb6b500006042"
    "40aeda402fe97c42003c003c003c003c000000000000f03f"
)


class SmallClearBackgroundValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.inputs = {
            "fragment": FRAGMENT,
            "vertex": VERTEX,
            "index": subject.EXPECTED_INDEX,
        }

    def test_retained_sample_three_is_x_halfway_discriminator(self) -> None:
        decision = subject.decision_from_inputs(self.inputs)
        self.assertEqual(decision["origin"], [501, 453])
        self.assertEqual(decision["extent"], [56, 56])
        self.assertEqual(
            [axis["name"] for axis in decision["differing"]],
            ["x"],
        )
        axis = decision["differing"][0]
        self.assertEqual(subject.f32_bits(axis["rounded"]), 0x42832ECC)
        self.assertEqual(subject.f32_bits(axis["captured"]), 0x42832ECB)

    def test_mutations_are_exactly_scoped(self) -> None:
        decision = subject.decision_from_inputs(self.inputs)
        streams = subject.mutated_vertex_streams(VERTEX, decision)
        ties = streams[subject.INTERVENTIONS[0]]
        differing = [
            index for index, (left, right) in enumerate(zip(VERTEX, ties, strict=True))
            if left != right
        ]
        self.assertEqual(differing, [72, 120])
        zero_tail = streams[subject.INTERVENTIONS[1]]
        finite_tail = streams[subject.INTERVENTIONS[2]]
        for vertex in range(subject.VERTEX_COUNT):
            start = vertex * subject.VERTEX_STRIDE + subject.TAIL_OFFSET
            self.assertEqual(zero_tail[start : start + 8], bytes(8))
            self.assertEqual(
                finite_tail[start : start + 8], subject.FINITE_TAIL
            )

    def test_binary32_halfway_rejects_nearby_non_midpoint(self) -> None:
        low = subject.f32_from_bits(0x42832ECB)
        high = subject.f32_from_bits(0x42832ECC)
        midpoint = (float(low) + float(high)) / 2.0
        self.assertTrue(subject.binary32_halfway(midpoint))
        self.assertFalse(subject.binary32_halfway(midpoint + 2.0**-30))

    def test_exact_comparison_has_literal_zero_tolerance(self) -> None:
        exact = {
            "compared": True,
            "exactByteMatch": True,
            "byteCount": 16,
            "mismatchedByteCount": 0,
            "mismatchedPixelCount": 0,
            "matchingPixelFraction": 1.0,
            "meanAbsoluteChannelDelta": 0.0,
            "rootMeanSquareChannelDelta": 0.0,
            "maximumChannelDelta": 0,
            "firstMismatchedByte": -1,
        }
        subject.validate_exact_comparison(exact, 16, "synthetic")
        exact["mismatchedByteCount"] = 1
        with self.assertRaisesRegex(ValueError, "mismatchedByteCount"):
            subject.validate_exact_comparison(exact, 16, "synthetic")

    def test_raw_payload_reads_every_byte(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = bytes(range(16))
            (root / "frame.raw").write_bytes(payload)
            snapshot = {
                "width": 2,
                "height": 2,
                "pixelFormat": 80,
                "rawBytes": 16,
                "rawFile": "frame.raw",
            }
            self.assertEqual(
                subject.raw_payload(root, snapshot, "synthetic"), payload
            )
            (root / "frame.raw").write_bytes(payload[:-1])
            with self.assertRaisesRegex(ValueError, "disk bytes"):
                subject.raw_payload(root, snapshot, "synthetic")

    def test_source_hash_validation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preregistration.json"
            path.write_text(json.dumps({}), encoding="utf-8")
            preregistration = {
                "sourceSHA256": {
                    str(path): "0" * 64,
                }
            }
            with self.assertRaisesRegex(ValueError, "pinned source"):
                subject.validate_sources(preregistration)


if __name__ == "__main__":
    unittest.main()
