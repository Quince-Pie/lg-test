#!/usr/bin/env python3
"""Tests for the frozen schema-9 tile-center scale-switch holdout."""

import hashlib
import json
import re
import tempfile
import unittest
import zlib
from dataclasses import asdict
from pathlib import Path

import open_raster_tile_center_scale_holdout as opening
import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v6 as v6
import raster_tile_selector_model_v7 as model
import validate_raster_tile_center_scale_holdout as capture


class RasterTileCenterScaleHoldoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration = capture.load_preregistration()
        cls.prediction = model.prediction_metadata()
        cls.preflight = model.preflight_discrimination_metadata()

    def test_layout_is_frozen_before_capture(self) -> None:
        layout = capture.layout_metadata()
        self.assertEqual(layout["caseCount"], 5)
        self.assertEqual(layout["endpointCount"], 116)
        self.assertEqual(layout["recordCount"], 148_480)
        self.assertEqual(layout["rawBytes"], 10_690_560)
        self.assertEqual(layout["expectedRecordCount"], 69_136)
        self.assertEqual(
            layout["caseWordsSha256"],
            "a958c42f9b5e498249d33d968596a7874ecd2faf63ec6a7faf565684df1ac3e0",
        )
        self.assertEqual(
            layout["endpointWordsSha256"],
            "c6bdc64b32679a5f20b4a4c494186fc1195017351707ef398566d40c03ed17d3",
        )
        self.assertEqual(
            layout["sampleWordsSha256"],
            "7cd6f0a23c24d26af3f8b0b2e17c905ae86e2a442228401a2e0b2048825d10f4",
        )
        self.assertFalse(self.preregistration["sealedHoldoutOpenedAtPreregistration"])

    def test_scale_sweep_changes_only_cancellation_depth(self) -> None:
        grouped: dict[str, list[tuple[int, int]]] = {
            name: [] for name, _ in capture.SCALE_TRANSLATED_BASES
        }
        for endpoint in capture.ENDPOINTS:
            if not endpoint.name.endswith("-forward"):
                continue
            match = re.fullmatch(
                r"translated-scale-(quarter|half|one)-k(\d\d)-forward",
                endpoint.name,
            )
            self.assertIsNotNone(match)
            grouped[match.group(1)].append(
                (int(match.group(2)), model.cancellation_depth(endpoint))
            )
        expected = [(power, 19 - power) for power in capture.SCALE_POWERS]
        self.assertEqual(grouped, {name: expected for name in grouped})

    def test_model_and_every_prediction_byte_are_frozen(self) -> None:
        frozen = self.preregistration["model"]
        for key, module in (
            ("sourceSha256", model),
            ("baseSourceSha256", v1),
            ("v2SourceSha256", v2),
            ("v4SourceSha256", v4),
            ("v6SourceSha256", v6),
        ):
            self.assertEqual(frozen[key], capture.sha256_path(Path(module.__file__)))
        expected = self.preregistration["predictedTruthStream"]
        for key in (
            "ordering",
            "caseRole",
            "endpointRole",
            "endpointCount",
            "recordComponentCount",
            "recordBytes",
            "recordCount",
            "bytes",
            "sha256",
            "cases",
        ):
            self.assertEqual(expected[key], self.prediction[key])
        self.assertEqual(self.prediction["recordCount"], 62_176)
        self.assertEqual(self.prediction["bytes"], 4_476_672)
        self.assertEqual(self.prediction["sha256"], model.PREDICTION_RAW_SHA256)
        archive = model.PREDICTION_ARCHIVE_PATH.read_bytes()
        self.assertEqual(len(archive), 863_076)
        self.assertEqual(
            hashlib.sha256(archive).hexdigest(), model.PREDICTION_ARCHIVE_SHA256
        )
        self.assertEqual(
            hashlib.sha256(zlib.decompress(archive)).hexdigest(), expected["sha256"]
        )

    def test_holdout_discriminates_cutoff_and_arithmetic_rivals(self) -> None:
        self.assertEqual(self.preflight, self.preregistration["preflightDiscrimination"])
        self.assertEqual(self.preflight["sealedRecordCount"], 62_176)
        self.assertEqual(self.preflight["sealedWordCount"], 1_119_168)
        self.assertEqual(
            self.preflight["ablationDifferences"],
            {
                "absolute-delta-exp-minus16": {"records": 504, "words": 1_000},
                "cancellation-14": {"records": 996, "words": 1_980},
                "cancellation-15": {"records": 516, "words": 1_020},
                "cancellation-17": {"records": 480, "words": 960},
                "cancellation-18": {"records": 960, "words": 1_920},
                "determinant-all": {"records": 1_512, "words": 3_000},
                "p27-all": {"records": 7_392, "words": 14_724},
                "translated-exact-constant": {
                    "records": 1_095,
                    "words": 10_032,
                },
            },
        )

    def test_model_contains_no_geometry_or_endpoint_name_selector(self) -> None:
        source = Path(model.__file__).read_text(encoding="utf-8")
        for capture_case in capture.CASES:
            self.assertNotIn(f'"{capture_case.name}"', source)
        for endpoint in capture.ENDPOINTS:
            self.assertNotIn(f'"{endpoint.name}"', source)

    def test_swift_and_python_matrices_are_identical(self) -> None:
        source = (
            Path(__file__).parents[1]
            / "Sources"
            / "GlassRasterTileNumerator"
            / "main.swift"
        ).read_text(encoding="utf-8")
        case_block = source.split(
            "#if TILE_CENTER_SCALE_HOLDOUT\nprivate let cases = [",
            maxsplit=1,
        )[1].split("\n]\n#elseif TILE_CENTER_LATTICE_HOLDOUT", maxsplit=1)[0]
        swift_cases = [
            (
                match.group("name"),
                match.group("role"),
                int(match.group("width")),
                int(match.group("height")),
                int(match.group("origin_x")),
                int(match.group("origin_y")),
            )
            for match in re.finditer(
                r"CaptureCase\(\s*"
                r'name: "(?P<name>[^"]+)", role: "(?P<role>[^"]+)",\s*'
                r"width: (?P<width>\d+), height: (?P<height>\d+),\s*"
                r"originX: (?P<origin_x>\d+), originY: (?P<origin_y>\d+)\s*\)",
                case_block,
            )
        ]
        self.assertEqual(
            swift_cases,
            [
                (
                    value.name,
                    value.role,
                    value.width,
                    value.height,
                    value.originX,
                    value.originY,
                )
                for value in capture.CASES
            ],
        )
        for value in (
            capture.PREREGISTRATION_SHA256,
            str(capture.layout_metadata()["caseWordsSha256"]),
            str(capture.layout_metadata()["endpointWordsSha256"]),
            str(capture.layout_metadata()["sampleWordsSha256"]),
            'layout["rawBytes"] as? Int == 10_690_560',
            'layout["expectedRecordCount"] as? Int == 69_136',
        ):
            self.assertIn(value, source)

    def test_synthetic_frozen_prediction_capture_opens_exactly(self) -> None:
        raw = bytearray(b"\xff" * capture.raw_bytes())
        selector_table = v1.load_selector_table()
        for case_index, capture_case in enumerate(capture.CASES):
            for endpoint_index, endpoint in enumerate(capture.ENDPOINTS):
                for sample in capture.sample_positions(capture_case):
                    record_index = (
                        case_index * len(capture.ENDPOINTS) + endpoint_index
                    ) * capture.SLOT_COUNT + sample.slot
                    capture.RECORD.pack_into(
                        raw,
                        record_index * capture.RECORD.size,
                        *model.predict_record(
                            capture_case,
                            endpoint,
                            sample,
                            selector_table,
                        ),
                    )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw_path = root / "raster-tile-numerator.raw"
            raw_path.write_bytes(raw)
            manifest = {
                "schemaVersion": capture.SCHEMA_VERSION,
                "rigVersion": capture.RIG_VERSION,
                "ciCommit": "0" * 40,
                "rasterTileNumerator": {
                    "file": raw_path.name,
                    "role": capture.ROLE,
                    "preregistrationFile": (
                        "Analysis/raster_tile_center_scale_preregistration.json"
                    ),
                    "preregistrationSha256": capture.PREREGISTRATION_SHA256,
                    "layout": capture.layout_metadata(),
                    "cases": [asdict(value) for value in capture.CASES],
                    "endpoints": capture.endpoint_metadata(),
                    "recordComponents": capture.record_components(),
                    "pullOffsetsByAxis": capture.pull_offsets(),
                    "ordering": (
                        "case-major,endpoint-major,"
                        "axis-primitive-tile-edge-slot-major,component-minor"
                    ),
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                },
            }
            (root / "manifest.json").write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
            report = opening.open_holdout(root)
        self.assertEqual(report["recordCount"], 69_136)
        self.assertEqual(report["wordMismatchCount"], 0)
        self.assertTrue(report["sealedPredictionHashExact"])
        self.assertTrue(report["exact"])


if __name__ == "__main__":
    unittest.main()
