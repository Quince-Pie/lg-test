#!/usr/bin/env python3
"""Tests for the frozen schema-7 center-origin prospective holdout."""

import hashlib
import json
import re
import tempfile
import unittest
import zlib
from dataclasses import asdict
from pathlib import Path

import open_raster_tile_center_origin_holdout as opening
import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v5 as model
import validate_raster_tile_center_origin_holdout as capture


class RasterTileCenterOriginHoldoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration = capture.load_preregistration()
        cls.prediction = model.prediction_metadata()
        cls.preflight = model.preflight_discrimination_metadata()

    def test_layout_is_frozen_before_capture(self) -> None:
        layout = capture.layout_metadata()
        self.assertEqual(layout["caseCount"], 31)
        self.assertEqual(layout["endpointCount"], 68)
        self.assertEqual(layout["recordCount"], 539_648)
        self.assertEqual(layout["rawBytes"], 38_854_656)
        self.assertEqual(layout["expectedRecordCount"], 244_800)
        self.assertEqual(
            layout["caseWordsSha256"],
            "149bdbd30e79c5547ed5f63cc604041619dee961d4b77a793211a0deb0a4c52d",
        )
        self.assertEqual(
            layout["endpointWordsSha256"],
            "6a8b745c8ccb65f5d788979722dd916bb190ccd791428528a72454de85ca7bf4",
        )
        self.assertEqual(
            layout["sampleWordsSha256"],
            "af2aa695005329658fb2ff7134b8ba760bcdde4abdcd5822f6cd1c9c00438754",
        )
        self.assertFalse(self.preregistration["sealedHoldoutOpenedAtPreregistration"])

    def test_matrix_crosses_origin_and_quotient_variables(self) -> None:
        sealed = [case for case in capture.CASES if case.role == "sealed-holdout"]
        self.assertEqual(len(sealed), 30)
        effective = [case for case in sealed if case.name.endswith("-x")]
        by_extent = {
            extent: {case.originX for case in effective if case.width == extent}
            for extent in (198, 204, 231, 252, 255, 315)
        }
        self.assertEqual(by_extent[198], {15, 17, 48, 80})
        self.assertEqual(by_extent[231], {15, 17, 48})
        self.assertEqual(by_extent[204], {15, 16, 17, 48})
        self.assertEqual(by_extent[252], {16, 48})
        self.assertEqual(by_extent[255], {16})
        self.assertEqual(by_extent[315], {16})
        self.assertEqual(
            sum(
                endpoint.role == "arithmetic-holdout" for endpoint in capture.ENDPOINTS
            ),
            66,
        )

    def test_model_and_every_prediction_byte_are_frozen(self) -> None:
        frozen = self.preregistration["model"]
        self.assertEqual(
            frozen["sourceSha256"], capture.sha256_path(Path(model.__file__))
        )
        self.assertEqual(
            frozen["baseSourceSha256"], capture.sha256_path(Path(v1.__file__))
        )
        self.assertEqual(
            frozen["v2SourceSha256"], capture.sha256_path(Path(v2.__file__))
        )
        self.assertEqual(
            frozen["v4SourceSha256"], capture.sha256_path(Path(v4.__file__))
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
        self.assertEqual(self.prediction["recordCount"], 240_720)
        self.assertEqual(self.prediction["bytes"], 17_331_840)
        self.assertEqual(self.prediction["sha256"], model.PREDICTION_RAW_SHA256)
        archive = model.PREDICTION_ARCHIVE_PATH.read_bytes()
        self.assertEqual(len(archive), 486_288)
        self.assertEqual(
            hashlib.sha256(archive).hexdigest(), model.PREDICTION_ARCHIVE_SHA256
        )
        self.assertEqual(
            hashlib.sha256(zlib.decompress(archive)).hexdigest(), expected["sha256"]
        )

    def test_holdout_discriminates_every_confounded_law(self) -> None:
        self.assertEqual(
            self.preflight, self.preregistration["preflightDiscrimination"]
        )
        self.assertEqual(self.preflight["sealedRecordCount"], 240_720)
        self.assertEqual(self.preflight["sealedWordCount"], 4_332_960)
        self.assertEqual(
            self.preflight["centerAblationDifferences"],
            {
                "absolute-origin16-only": {"records": 216, "words": 432},
                "denominator33-determinant": {"records": 596, "words": 1_140},
                "determinant-all": {"records": 52, "words": 52},
                "exact-down-all": {"records": 632, "words": 1_264},
            },
        )

    def test_model_contains_no_geometry_name_selector(self) -> None:
        source = Path(model.__file__).read_text(encoding="utf-8")
        for capture_case in capture.CASES:
            self.assertNotIn(f'"{capture_case.name}"', source)

    def test_swift_and_python_case_matrices_are_identical(self) -> None:
        source = (
            Path(__file__).parents[1]
            / "Sources"
            / "GlassRasterTileNumerator"
            / "main.swift"
        ).read_text(encoding="utf-8")
        case_block = source.split(
            "#if TILE_CENTER_ORIGIN_HOLDOUT\nprivate let cases = [",
            maxsplit=1,
        )[1].split("\n]\n#elseif TILE_DOUBLE_ROUNDING_HOLDOUT", maxsplit=1)[0]
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

        endpoint_block = (
            "private let centerOriginPrimaryBase"
            + source.split(
                "#if TILE_CENTER_ORIGIN_HOLDOUT\nprivate let centerOriginPrimaryBase",
                maxsplit=1,
            )[1].split("\n#elseif TILE_DOUBLE_ROUNDING_HOLDOUT", maxsplit=1)[0]
        )

        def uint32_array(name: str) -> list[int]:
            body = re.search(
                rf"private let {name}: \[UInt32\] = \[([^]]+)\]",
                endpoint_block,
            )
            self.assertIsNotNone(body)
            return [int(value) for value in re.findall(r"\d+", body.group(1))]

        primary = re.search(
            r'private let centerOriginPrimaryBase = \(name: "([^"]+)", '
            r"bits: UInt32\(0x([0-9a-fA-F_]+)\)\)",
            endpoint_block,
        )
        self.assertIsNotNone(primary)
        self.assertEqual(
            (primary.group(1), int(primary.group(2).replace("_", ""), 16)),
            capture.PRIMARY_TRANSLATED_BASE,
        )
        transfer_body = re.search(
            r"private let centerOriginTransferBases:[^=]+ = \[([^]]+)\]",
            endpoint_block,
        )
        self.assertIsNotNone(transfer_body)
        self.assertEqual(
            [
                (name, int(bits.replace("_", ""), 16))
                for name, bits in re.findall(
                    r'\("([^"]+)", 0x([0-9a-fA-F_]+)\)',
                    transfer_body.group(1),
                )
            ],
            list(capture.TRANSFER_TRANSLATED_BASES),
        )
        self.assertEqual(
            uint32_array("centerOriginPrimaryResidues"),
            list(capture.PRIMARY_TRANSLATED_RESIDUES),
        )
        self.assertEqual(
            uint32_array("centerOriginPrimarySpans"),
            list(capture.PRIMARY_NATIVE_SPANS),
        )
        self.assertEqual(
            uint32_array("centerOriginTransferSpans"),
            list(capture.TRANSFER_NATIVE_SPANS),
        )
        for value in (
            capture.PREREGISTRATION_SHA256,
            str(capture.layout_metadata()["caseWordsSha256"]),
            str(capture.layout_metadata()["endpointWordsSha256"]),
            str(capture.layout_metadata()["sampleWordsSha256"]),
            'layout["rawBytes"] as? Int == 38_854_656',
            'layout["expectedRecordCount"] as? Int == 244_800',
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
                        "Analysis/raster_tile_center_origin_preregistration.json"
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
        self.assertEqual(report["recordCount"], 244_800)
        self.assertEqual(report["wordMismatchCount"], 0)
        self.assertTrue(report["sealedPredictionHashExact"])
        self.assertTrue(report["exact"])


if __name__ == "__main__":
    unittest.main()
