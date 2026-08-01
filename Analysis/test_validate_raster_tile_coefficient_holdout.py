#!/usr/bin/env python3
"""Tests for the frozen schema-13 raster-coefficient holdout."""

import hashlib
import json
import re
import tempfile
import unittest
import zlib
from dataclasses import asdict
from pathlib import Path

import open_raster_tile_coefficient_holdout as opening
import raster_tile_coefficient_holdout_model as model
import raster_tile_coefficient_model as coefficients
import raster_tile_iterator_model as iterator
import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v6 as v6
import raster_tile_selector_model_v7 as v7
import raster_tile_selector_model_v8 as v8
import validate_raster_tile_coefficient_holdout as capture


class RasterTileCoefficientHoldoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration = capture.load_preregistration()
        cls.prediction = model.prediction_metadata()
        cls.preflight = model.preflight_discrimination_metadata()

    def test_layout_and_prediction_are_frozen_before_capture(self) -> None:
        layout = capture.layout_metadata()
        self.assertEqual(layout["caseCount"], 8)
        self.assertEqual(layout["endpointCount"], 24)
        self.assertEqual(layout["recordCount"], 49_152)
        self.assertEqual(layout["expectedRecordCount"], 23_928)
        self.assertEqual(layout["rawBytes"], 3_538_944)
        self.assertEqual(
            layout["samplesPerCase"],
            [60, 146, 134, 130, 140, 134, 127, 126],
        )
        self.assertEqual(
            layout["caseWordsSha256"],
            "3ecb4d358bb723c713843473db68706d87b0ab6ebceeec67f226a0c68501f7f5",
        )
        self.assertEqual(
            layout["endpointWordsSha256"],
            "16151b2e692e5d7f6f80802ec07cb9e9e7275a70b1cf3900b5a767b9fed9466b",
        )
        self.assertEqual(
            layout["sampleWordsSha256"],
            "63b50ccd0807cba2c7d43ae42da084f5c83ba1a1c67abb8cde31530632b5f262",
        )
        self.assertFalse(
            self.preregistration["appleOutputsObservedAtPreregistration"]
        )

    def test_endpoint_matrix_is_regenerated(self) -> None:
        expected = [
            item
            for name, role, low_bits, high_bits in capture.ENDPOINT_SPECS
            for item in (
                (f"{name}-forward", role, low_bits, high_bits),
                (f"{name}-reverse", role, high_bits, low_bits),
            )
        ]
        actual = [
            (endpoint.name, endpoint.role, endpoint.lowBits, endpoint.highBits)
            for endpoint in capture.ENDPOINTS
        ]
        self.assertEqual(actual, expected)
        factorized = [
            coefficients.uses_factorized_tile_path(endpoint)
            for endpoint in capture.ENDPOINTS
        ]
        self.assertEqual(sum(factorized), 12)

    def test_model_sources_and_every_prediction_byte_are_frozen(self) -> None:
        frozen = self.preregistration["model"]
        for key, module in (
            ("sourceSha256", model),
            ("coefficientSourceSha256", coefficients),
            ("iteratorSourceSha256", iterator),
            ("baseSourceSha256", v1),
            ("v2SourceSha256", v2),
            ("v4SourceSha256", v4),
            ("v6SourceSha256", v6),
            ("v7SourceSha256", v7),
            ("v8SourceSha256", v8),
        ):
            self.assertEqual(
                frozen[key],
                capture.sha256_path(Path(module.__file__)),
            )
        self.assertEqual(
            frozen["selectorTableSha256"],
            v1.SELECTOR_TABLE_COMPRESSED_SHA256,
        )
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
        self.assertEqual(self.prediction["recordCount"], 23_928)
        self.assertEqual(self.prediction["bytes"], 1_722_816)
        self.assertEqual(self.prediction["sha256"], model.PREDICTION_RAW_SHA256)
        archive = model.PREDICTION_ARCHIVE_PATH.read_bytes()
        self.assertEqual(len(archive), 600_348)
        self.assertEqual(
            hashlib.sha256(archive).hexdigest(),
            model.PREDICTION_ARCHIVE_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(zlib.decompress(archive)).hexdigest(),
            model.PREDICTION_RAW_SHA256,
        )

    def test_holdout_distinguishes_every_declared_rival(self) -> None:
        self.assertEqual(
            self.preflight,
            self.preregistration["preflightDiscrimination"],
        )
        self.assertEqual(self.preflight["recordCount"], 23_928)
        self.assertEqual(self.preflight["wordCount"], 430_704)
        differences = self.preflight["ablationDifferences"]
        self.assertEqual(
            differences["partial-tile-product"],
            {"records": 15, "words": 225},
        )
        self.assertEqual(
            differences["legacy-constant-all"],
            {"records": 232, "words": 3_823},
        )
        self.assertTrue(
            all(value["records"] > 0 and value["words"] > 0 for value in differences.values())
        )

    def test_models_have_no_case_or_endpoint_name_selector(self) -> None:
        sources = "\n".join(
            Path(module.__file__).read_text(encoding="utf-8")
            for module in (model, coefficients, iterator)
        )
        for capture_case in capture.CASES:
            self.assertNotIn(f'"{capture_case.name}"', sources)
        for endpoint in capture.ENDPOINTS:
            self.assertNotIn(f'"{endpoint.name}"', sources)

    def test_swift_and_python_matrices_are_identical(self) -> None:
        source = (
            Path(__file__).parents[1]
            / "Sources"
            / "GlassRasterTileNumerator"
            / "main.swift"
        ).read_text(encoding="utf-8")
        case_block = source.split(
            "#elseif TILE_COEFFICIENT_HOLDOUT\nprivate let cases = [",
            maxsplit=1,
        )[1].split("\n]\n#elseif TILE_CENTER_EXTENT_TOMOGRAPHY", maxsplit=1)[0]
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
            'layout["rawBytes"] as? Int == 3_538_944',
            'layout["expectedRecordCount"] as? Int == 23_928',
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
                        "Analysis/raster_tile_coefficient_holdout_preregistration.json"
                    ),
                    "preregistrationSha256": capture.PREREGISTRATION_SHA256,
                    "layout": capture.layout_metadata(),
                    "cases": [asdict(value) for value in capture.CASES],
                    "endpoints": capture.endpoint_metadata(),
                    "recordComponents": capture.record_components(),
                    "pullOffsetsByAxis": capture.pull_offsets(),
                    "ordering": capture.ORDERING,
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                },
            }
            (root / "manifest.json").write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
            report = opening.open_holdout(root)
        self.assertEqual(report["recordCount"], 23_928)
        self.assertEqual(report["wordCount"], 430_704)
        self.assertEqual(report["wordMismatchCount"], 0)
        self.assertTrue(report["predictionHashExact"])
        self.assertTrue(report["exact"])


if __name__ == "__main__":
    unittest.main()
