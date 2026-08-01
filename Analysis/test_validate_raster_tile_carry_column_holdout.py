#!/usr/bin/env python3
"""Tests for the frozen schema-15 carry-column holdout."""

import hashlib
import re
import unittest
import zlib
from pathlib import Path

import raster_tile_carry_column_holdout_model as model
import raster_tile_coefficient_model as coefficient_base
import raster_tile_coefficient_model_v3 as coefficients
import raster_tile_iterator_model as iterator_base
import raster_tile_iterator_model_v3 as iterator
import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v6 as v6
import raster_tile_selector_model_v7 as v7
import raster_tile_selector_model_v8 as v8
import validate_raster_tile_carry_column_holdout as capture


class RasterTileCarryColumnHoldoutTests(unittest.TestCase):
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
        self.assertEqual(layout["expectedRecordCount"], 77_760)
        self.assertEqual(layout["rawBytes"], 7_962_624)
        self.assertEqual(
            layout["samplesPerCase"],
            [202, 190, 194, 182, 158, 142, 178, 170, 230, 182, 170, 162],
        )
        self.assertEqual(
            layout["caseWordsSha256"],
            "1d6f42d0dcdc5dc8e03741a39630baf22fd81fa3b5ebb038c798942deb44c7cc",
        )
        self.assertEqual(
            layout["endpointWordsSha256"],
            "6209d710233d007f57900cd724758434a904919679af6c8c4b2c592072cd8d00",
        )
        self.assertEqual(
            layout["sampleWordsSha256"],
            "a353f703e97c7357e17674c7d2db4b01bd8aadf8a3cd5700324480176c97abec",
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
        self.assertEqual(self.prediction["recordCount"], 77_760)
        self.assertEqual(self.prediction["bytes"], 5_598_720)
        self.assertEqual(self.prediction["sha256"], model.PREDICTION_RAW_SHA256)
        archive = model.PREDICTION_ARCHIVE_PATH.read_bytes()
        self.assertEqual(len(archive), 2_691_932)
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
        self.assertEqual(self.preflight["recordCount"], 77_760)
        self.assertEqual(self.preflight["wordCount"], 1_399_680)
        differences = self.preflight["ablationDifferences"]
        self.assertEqual(
            differences["sticky-one-carry"],
            {"records": 40, "words": 657},
        )
        self.assertEqual(
            differences["propagate-two-columns"],
            {"records": 32, "words": 521},
        )
        self.assertEqual(
            differences["aggregate-tile-product"],
            {"records": 52, "words": 861},
        )
        self.assertEqual(
            differences["partial-tile-product"],
            {"records": 101, "words": 1_693},
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
            "#if TILE_CARRY_COLUMN_HOLDOUT\nprivate let cases = [",
            maxsplit=1,
        )[1].split(
            "\n]\n#elseif TILE_STICKY_COEFFICIENT_HOLDOUT",
            maxsplit=1,
        )[0]
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
            'layout["expectedRecordCount"] as? Int == 77_760',
        ):
            self.assertIn(value, source)


if __name__ == "__main__":
    unittest.main()
