#!/usr/bin/env python3
"""Tests for the frozen schema-10 tile-center boundary holdout."""

import hashlib
import json
import re
import tempfile
import unittest
import zlib
from dataclasses import asdict
from pathlib import Path

import open_raster_tile_center_boundary_holdout as opening
import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v6 as v6
import raster_tile_selector_model_v7 as v7
import raster_tile_selector_model_v8 as model
import validate_raster_tile_center_boundary_holdout as capture


class RasterTileCenterBoundaryHoldoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration = capture.load_preregistration()
        cls.prediction = model.prediction_metadata()
        cls.preflight = model.preflight_discrimination_metadata()

    def test_layout_is_frozen_before_capture(self) -> None:
        layout = capture.layout_metadata()
        self.assertEqual(layout["caseCount"], 7)
        self.assertEqual(layout["endpointCount"], 158)
        self.assertEqual(layout["recordCount"], 283_136)
        self.assertEqual(layout["rawBytes"], 20_385_792)
        self.assertEqual(layout["expectedRecordCount"], 120_080)
        self.assertEqual(layout["samplesPerCase"], [60, 102, 102, 118, 118, 130, 130])
        self.assertEqual(
            layout["caseWordsSha256"],
            "f0222b0b673d7ef9ca721500545890e750e00ebeb1f0854a6af4cea47052f516",
        )
        self.assertEqual(
            layout["endpointWordsSha256"],
            "69c94cb2395f2374549291f07bf28ad37161ee61206c90d1b493536a9e3dbbfa",
        )
        self.assertEqual(
            layout["sampleWordsSha256"],
            "dac4a1d9ead2c8c83366aa79d2e8afa5d46731b89661c1bc54d52b80056267c7",
        )
        self.assertFalse(self.preregistration["sealedHoldoutOpenedAtPreregistration"])

    def test_endpoint_names_bits_and_depths_are_regenerated(self) -> None:
        expected: list[tuple[str, int, int, int]] = []
        for base_name, base_bits in capture.TRANSLATED_BASES:
            for family_name, significand, residue in capture.SLOPE_FAMILIES:
                for depth in capture.CANCELLATION_DEPTHS:
                    power = 23 - (significand.bit_length() - 1) - depth
                    low = base_bits + residue
                    high = low + (significand << power)
                    stem = f"translated-confirm-{base_name}-{family_name}-d{depth:02d}"
                    expected.extend(
                        (
                            (f"{stem}-forward", low, high, depth),
                            (f"{stem}-reverse", high, low, depth),
                        )
                    )
        actual = [
            (
                endpoint.name,
                endpoint.lowBits,
                endpoint.highBits,
                model.cancellation_depth(endpoint),
            )
            for endpoint in capture.ENDPOINTS[2:]
        ]
        self.assertEqual(actual, expected)

    def test_model_and_every_prediction_byte_are_frozen(self) -> None:
        frozen = self.preregistration["model"]
        for key, module in (
            ("sourceSha256", model),
            ("baseSourceSha256", v1),
            ("v2SourceSha256", v2),
            ("v4SourceSha256", v4),
            ("v6SourceSha256", v6),
            ("v7SourceSha256", v7),
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
        self.assertEqual(self.prediction["recordCount"], 110_600)
        self.assertEqual(self.prediction["bytes"], 7_963_200)
        self.assertEqual(self.prediction["sha256"], model.PREDICTION_RAW_SHA256)
        archive = model.PREDICTION_ARCHIVE_PATH.read_bytes()
        self.assertEqual(len(archive), 1_015_522)
        self.assertEqual(
            hashlib.sha256(archive).hexdigest(), model.PREDICTION_ARCHIVE_SHA256
        )
        self.assertEqual(
            hashlib.sha256(zlib.decompress(archive)).hexdigest(), expected["sha256"]
        )

    def test_holdout_discriminates_every_boundary_and_arithmetic_rival(self) -> None:
        self.assertEqual(
            self.preflight, self.preregistration["preflightDiscrimination"]
        )
        self.assertEqual(self.preflight["sealedRecordCount"], 110_600)
        self.assertEqual(self.preflight["sealedWordCount"], 1_990_800)
        self.assertEqual(
            self.preflight["ablationDifferences"],
            {
                "determinant-all": {"records": 2_208, "words": 4_416},
                "forward-floor-min-7": {"records": 264, "words": 528},
                "forward-floor-min-9": {"records": 288, "words": 576},
                "forward-phase-min-10": {"records": 276, "words": 552},
                "forward-phase-min-12": {"records": 288, "words": 576},
                "p27-floor-all": {"records": 4_440, "words": 8_880},
                "p27-phase-all": {"records": 3_036, "words": 6_072},
                "reverse-p27-min-15": {"records": 276, "words": 552},
                "reverse-p27-min-17": {"records": 276, "words": 552},
                "symmetric-forward-boundaries": {
                    "records": 1_656,
                    "words": 3_312,
                },
                "translated-exact-constant": {"records": 276, "words": 276},
            },
        )
        self.assertTrue(
            all(
                difference["words"] > 0
                for difference in self.preflight["ablationDifferences"].values()
            )
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
            "#if TILE_CENTER_BOUNDARY_HOLDOUT\nprivate let cases = [",
            maxsplit=1,
        )[1].split("\n]\n#elseif TILE_CENTER_SCALE_HOLDOUT", maxsplit=1)[0]
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
            'layout["rawBytes"] as? Int == 20_385_792',
            'layout["expectedRecordCount"] as? Int == 120_080',
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
                        "Analysis/raster_tile_center_boundary_preregistration.json"
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
        self.assertEqual(report["recordCount"], 120_080)
        self.assertEqual(report["wordMismatchCount"], 0)
        self.assertTrue(report["sealedPredictionHashExact"])
        self.assertTrue(report["exact"])


if __name__ == "__main__":
    unittest.main()
