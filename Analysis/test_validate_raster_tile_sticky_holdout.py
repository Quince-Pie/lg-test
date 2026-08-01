#!/usr/bin/env python3
"""Tests for the frozen schema-14 sticky-carry holdout."""

import hashlib
import re
import unittest
import zlib
from pathlib import Path

import raster_tile_coefficient_model as coefficient_base
import raster_tile_coefficient_model_v2 as coefficients
import raster_tile_iterator_model as iterator_base
import raster_tile_iterator_model_v2 as iterator
import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v6 as v6
import raster_tile_selector_model_v7 as v7
import raster_tile_selector_model_v8 as v8
import raster_tile_sticky_holdout_model as model
import validate_raster_tile_sticky_holdout as capture


class RasterTileStickyHoldoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration = capture.load_preregistration()
        cls.prediction = model.prediction_metadata()
        cls.preflight = model.preflight_discrimination_metadata()

    def test_layout_and_prediction_are_frozen_before_capture(self) -> None:
        layout = capture.layout_metadata()
        self.assertEqual(layout["caseCount"], 12)
        self.assertEqual(layout["endpointCount"], 36)
        self.assertEqual(layout["recordCount"], 110_592)
        self.assertEqual(layout["expectedRecordCount"], 81_648)
        self.assertEqual(layout["rawBytes"], 7_962_624)
        self.assertEqual(
            layout["samplesPerCase"],
            [198, 178, 198, 210, 210, 118, 114, 234, 214, 186, 194, 214],
        )
        self.assertEqual(
            layout["caseWordsSha256"],
            "c68826a95949092fdf046acb12952ed9974f2a793c3902428cddd3f55ffffd27",
        )
        self.assertEqual(
            layout["endpointWordsSha256"],
            "72f88000946ea0736fd2423faa36b48e4060eebc2ce0ee71b7c87f27d99cbdc9",
        )
        self.assertEqual(
            layout["sampleWordsSha256"],
            "6cf9594e97aa3050c45e3c645281646e8bbd9397f4d99f4fb789be9cfcf43889",
        )
        self.assertFalse(
            self.preregistration["appleOutputsObservedAtPreregistration"]
        )

    def test_model_sources_and_every_prediction_byte_are_frozen(self) -> None:
        frozen = self.preregistration["model"]
        modules = {
            "sourceSha256": model,
            "coefficientSourceSha256": coefficients,
            "coefficientBaseSourceSha256": coefficient_base,
            "iteratorSourceSha256": iterator,
            "iteratorBaseSourceSha256": iterator_base,
            "baseSourceSha256": v1,
            "v2SourceSha256": v2,
            "v4SourceSha256": v4,
            "v6SourceSha256": v6,
            "v7SourceSha256": v7,
            "v8SourceSha256": v8,
        }
        for key, module in modules.items():
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
        self.assertEqual(self.prediction["recordCount"], 81_648)
        self.assertEqual(self.prediction["bytes"], 5_878_656)
        self.assertEqual(self.prediction["sha256"], model.PREDICTION_RAW_SHA256)
        archive = model.PREDICTION_ARCHIVE_PATH.read_bytes()
        self.assertEqual(len(archive), 2_823_187)
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
        self.assertEqual(self.preflight["recordCount"], 81_648)
        self.assertEqual(self.preflight["wordCount"], 1_469_664)
        differences = self.preflight["ablationDifferences"]
        self.assertEqual(
            differences["aggregate-tile-product"],
            {"records": 181, "words": 3_035},
        )
        self.assertEqual(
            differences["partial-tile-product"],
            {"records": 277, "words": 4_627},
        )
        self.assertEqual(
            differences["legacy-combined-product"],
            {"records": 3_141, "words": 52_146},
        )
        self.assertTrue(
            all(
                value["records"] > 0 and value["words"] > 0
                for value in differences.values()
            )
        )

    def test_models_have_no_capture_name_selector(self) -> None:
        sources = "\n".join(
            Path(module.__file__).read_text(encoding="utf-8")
            for module in (model, coefficients, iterator)
        )
        for capture_case in capture.CASES:
            self.assertNotIn(f'"{capture_case.name}"', sources)
        for endpoint in capture.ENDPOINTS:
            self.assertNotIn(f'"{endpoint.name}"', sources)

    def test_swift_and_python_case_matrices_are_identical(self) -> None:
        source = (
            Path(__file__).parents[1]
            / "Sources"
            / "GlassRasterTileNumerator"
            / "main.swift"
        ).read_text(encoding="utf-8")
        case_block = source.split(
            "#if TILE_STICKY_COEFFICIENT_HOLDOUT\nprivate let cases = [",
            maxsplit=1,
        )[1].split("\n]\n#elseif TILE_COEFFICIENT_HOLDOUT", maxsplit=1)[0]
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
            'layout["rawBytes"] as? Int == 7_962_624',
            'layout["expectedRecordCount"] as? Int == 81_648',
        ):
            self.assertIn(value, source)


if __name__ == "__main__":
    unittest.main()
