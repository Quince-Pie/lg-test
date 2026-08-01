#!/usr/bin/env python3
"""Tests for the preregistered per-tile plane-numerator capture."""

import hashlib
import json
import struct
import tempfile
from pathlib import Path
import unittest

import validate_raster_tile_numerator as numerator


class RasterTileNumeratorTests(unittest.TestCase):
    def test_preregistration_and_layout_are_frozen(self) -> None:
        preregistration = numerator.load_preregistration()
        self.assertEqual(
            preregistration["capture"]["layout"],
            numerator.layout_metadata(),
        )
        self.assertEqual(numerator.raw_bytes(), 786_432)
        self.assertEqual(
            numerator.layout_metadata(),
            {
                "caseCount": 24,
                "endpointCount": 16,
                "axisCount": 2,
                "primitiveCount": 2,
                "tileCount": 32,
                "slotCount": 128,
                "recordBytes": 16,
                "recordCount": 49_152,
                "rawBytes": 786_432,
                "expectedRecordCount": 32_144,
                "caseWordsSha256": (
                    "966c0bf7ec9e7e611feb29468163009eba67bc5b12cadc18ba4c59e1260c9008"
                ),
                "endpointWordsSha256": (
                    "ba0e93cdee2a5f19b63f7a01560da3fa431911dbf37e6775f3950802d4c10bf7"
                ),
                "sampleWordsSha256": (
                    "36f12f51ccb2ba9f0c7d7739a213532ad7b6baa70898e00195264096b7d39c09"
                ),
                "samplesPerCase": [
                    32,
                    68,
                    84,
                    104,
                    112,
                    58,
                    62,
                    60,
                    62,
                    66,
                    74,
                    88,
                    96,
                    96,
                    67,
                    98,
                    96,
                    90,
                    88,
                    108,
                    108,
                    113,
                    113,
                    66,
                ],
            },
        )

    def test_samples_are_unique_safe_and_control_predictions_are_frozen(self) -> None:
        prediction_digest = hashlib.sha256()
        for capture_case in numerator.CASES:
            samples = numerator.sample_positions(capture_case)
            self.assertEqual(len(samples), len({sample.slot for sample in samples}))
            for sample in samples:
                coordinate = sample.x if sample.axis == 0 else sample.y
                self.assertEqual(coordinate // numerator.TILE_SIZE, sample.tile)
                self.assertIn(sample.axis, range(numerator.AXIS_COUNT))
                self.assertIn(sample.primitive, range(numerator.PRIMITIVE_COUNT))
                local = coordinate - (
                    capture_case.originX if sample.axis == 0 else capture_case.originY
                )
                if sample.axis == 0:
                    left = capture_case.height * (2 * local + 1)
                    if sample.primitive == 0:
                        self.assertGreater(left, capture_case.width)
                    else:
                        self.assertLess(
                            left,
                            (2 * capture_case.height - 1) * capture_case.width,
                        )
                else:
                    left = capture_case.width * (2 * local + 1)
                    if sample.primitive == 0:
                        self.assertGreater(left, capture_case.height)
                    else:
                        self.assertLess(
                            left,
                            (2 * capture_case.width - 1) * capture_case.height,
                        )
        for endpoint in numerator.ENDPOINTS[:2]:
            for sample in numerator.sample_positions(numerator.CASES[0]):
                prediction_digest.update(
                    struct.pack(
                        "<2I",
                        *numerator.control_pull_prediction(
                            numerator.CASES[0], endpoint, sample
                        ),
                    )
                )
        self.assertEqual(
            prediction_digest.hexdigest(),
            "886de06237d6c028d0e96ae1585723655de0e98a190ff72fa22223c7dd9ec954",
        )

    def test_synthetic_complete_capture_passes_and_undeclared_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_path = root / "raster-tile-numerator.raw"
            raw = bytearray(b"\xff" * numerator.raw_bytes())
            for case_index, capture_case in enumerate(numerator.CASES):
                samples = numerator.sample_positions(capture_case)
                for endpoint_index, endpoint in enumerate(numerator.ENDPOINTS):
                    for sample in samples:
                        record = (0, 0, 0, 0)
                        if (
                            capture_case.name == "control-square-256"
                            and endpoint.name in {"zero-to-one", "one-to-zero"}
                        ):
                            record = (
                                *numerator.control_pull_prediction(
                                    capture_case, endpoint, sample
                                ),
                                0,
                                0,
                            )
                        record_index = (
                            case_index * len(numerator.ENDPOINTS) + endpoint_index
                        ) * numerator.SLOT_COUNT + sample.slot
                        numerator.RECORD.pack_into(
                            raw, record_index * numerator.RECORD.size, *record
                        )
            raw_path.write_bytes(raw)

            def write_manifest() -> None:
                evidence = {
                    "role": numerator.ROLE,
                    "preregistrationFile": (
                        "Analysis/raster_tile_numerator_preregistration.json"
                    ),
                    "preregistrationSha256": numerator.PREREGISTRATION_SHA256,
                    "layout": numerator.layout_metadata(),
                    "cases": [
                        {
                            "name": value.name,
                            "role": value.role,
                            "width": value.width,
                            "height": value.height,
                            "originX": value.originX,
                            "originY": value.originY,
                        }
                        for value in numerator.CASES
                    ],
                    "endpoints": [
                        {
                            "name": value.name,
                            "lowBits": f"0x{value.lowBits:08x}",
                            "highBits": f"0x{value.highBits:08x}",
                        }
                        for value in numerator.ENDPOINTS
                    ],
                    "recordComponents": numerator.preregistration_payload()["capture"][
                        "recordComponents"
                    ],
                    "pullOffsetsByAxis": numerator.preregistration_payload()["capture"][
                        "pullOffsetsByAxis"
                    ],
                    "ordering": numerator.preregistration_payload()["capture"][
                        "ordering"
                    ],
                    "file": raw_path.name,
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
                manifest = {
                    "schemaVersion": numerator.SCHEMA_VERSION,
                    "rigVersion": numerator.RIG_VERSION,
                    "ciCommit": "0" * 40,
                    "rasterTileNumerator": evidence,
                }
                (root / "manifest.json").write_text(
                    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )

            write_manifest()
            report = numerator.validate(root)
            self.assertTrue(report["prospectiveControlExact"])
            self.assertEqual(report["expectedRecords"], 32_144)
            self.assertEqual(report["discoveryRecords"], 32_080)

            numerator.RECORD.pack_into(raw, 0, 0, 0, 0, 0)
            raw_path.write_bytes(raw)
            write_manifest()
            with self.assertRaisesRegex(ValueError, "undeclared"):
                numerator.validate(root)

    def test_swift_probe_embeds_frozen_contract(self) -> None:
        source = (
            Path(__file__).parents[1]
            / "Sources"
            / "GlassRasterTileNumerator"
            / "main.swift"
        ).read_text(encoding="utf-8")
        for value in (
            numerator.PREREGISTRATION_SHA256,
            str(numerator.layout_metadata()["caseWordsSha256"]),
            str(numerator.layout_metadata()["endpointWordsSha256"]),
            str(numerator.layout_metadata()["sampleWordsSha256"]),
        ):
            self.assertIn(value, source)
        self.assertIn('layout["rawBytes"] as? Int == 786_432', source)
        self.assertIn('layout["expectedRecordCount"] as? Int == 32_144', source)
        self.assertIn(
            r"results[\(slotCount)u * input.recordIndex + input.outputSlot]",
            source,
        )


if __name__ == "__main__":
    unittest.main()
