#!/usr/bin/env python3
"""Tests for the frozen schema-8 center p27-lattice holdout."""

import hashlib
import json
import re
import tempfile
import unittest
import zlib
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path

import open_raster_tile_center_lattice_holdout as opening
import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v5 as v5
import raster_tile_selector_model_v6 as model
import validate_raster_tile_center_lattice_holdout as capture


class RasterTileCenterLatticeHoldoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration = capture.load_preregistration()
        cls.prediction = model.prediction_metadata()
        cls.preflight = model.preflight_discrimination_metadata()

    def test_layout_is_frozen_before_capture(self) -> None:
        layout = capture.layout_metadata()
        self.assertEqual(layout["caseCount"], 15)
        self.assertEqual(layout["endpointCount"], 178)
        self.assertEqual(layout["recordCount"], 683_520)
        self.assertEqual(layout["rawBytes"], 49_213_440)
        self.assertEqual(layout["expectedRecordCount"], 325_384)
        self.assertEqual(
            layout["caseWordsSha256"],
            "86b9f5492b84429a140cf865a04aa988275f6b8c1fcbce21329692586aaa5a1c",
        )
        self.assertEqual(
            layout["endpointWordsSha256"],
            "4e26aeca71331957f368f709c47ffff1c6c972c7db6ca67b4ecff9b56f577b22",
        )
        self.assertEqual(
            layout["sampleWordsSha256"],
            "f6ed71bb4fefa0444082fddfac0ba1a15a11ce10b199b018ed33fd795ce892cf",
        )
        self.assertFalse(self.preregistration["sealedHoldoutOpenedAtPreregistration"])

    def test_matrix_brackets_both_recovered_phase_boundaries(self) -> None:
        expected = {
            (331, Fraction(31, 32)): Fraction(31, 331),
            (341, Fraction(1)): Fraction(32, 341),
            (651, Fraction(61, 64)): Fraction(61, 651),
            (537, Fraction(19, 32)): Fraction(302, 537),
            (615, Fraction(1, 2)): Fraction(346, 615),
            (775, Fraction(1, 2)): Fraction(436, 775),
            (841, Fraction(53, 64)): Fraction(473, 841),
        }
        phases = {
            (extent, delta): model.signed_p27_lattice(delta / extent)[2]
            for extent, delta in expected
        }
        self.assertEqual(phases, expected)
        self.assertLess(phases[(331, Fraction(31, 32))], Fraction(3, 32))
        self.assertGreater(phases[(341, Fraction(1))], Fraction(3, 32))
        self.assertLess(phases[(651, Fraction(61, 64))], Fraction(3, 32))
        self.assertLess(phases[(537, Fraction(19, 32))], Fraction(9, 16))
        self.assertGreater(phases[(615, Fraction(1, 2))], Fraction(9, 16))
        self.assertGreater(phases[(775, Fraction(1, 2))], Fraction(9, 16))
        self.assertLess(phases[(841, Fraction(53, 64))], Fraction(9, 16))

    def test_boundary_amplifiers_are_exact_nonzero_translations(self) -> None:
        expected_deltas = (
            Fraction(31, 32),
            Fraction(1),
            Fraction(61, 64),
            Fraction(19, 32),
            Fraction(1, 2),
            Fraction(53, 64),
        )
        actual = tuple(
            v1.float32_bits_fraction(high) - v1.float32_bits_fraction(low)
            for _, low, high in capture.BROAD_TRANSLATED_ENDPOINTS
        )
        self.assertEqual(actual, expected_deltas)
        self.assertTrue(
            all(low != 0 and high != 0 for _, low, high in capture.BROAD_TRANSLATED_ENDPOINTS)
        )

    def test_model_and_every_prediction_byte_are_frozen(self) -> None:
        frozen = self.preregistration["model"]
        for key, module in (
            ("sourceSha256", model),
            ("baseSourceSha256", v1),
            ("v2SourceSha256", v2),
            ("v4SourceSha256", v4),
            ("v5SourceSha256", v5),
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
        self.assertEqual(self.prediction["recordCount"], 314_704)
        self.assertEqual(self.prediction["bytes"], 22_658_688)
        self.assertEqual(self.prediction["sha256"], model.PREDICTION_RAW_SHA256)
        archive = model.PREDICTION_ARCHIVE_PATH.read_bytes()
        self.assertEqual(len(archive), 1_177_305)
        self.assertEqual(
            hashlib.sha256(archive).hexdigest(), model.PREDICTION_ARCHIVE_SHA256
        )
        self.assertEqual(
            hashlib.sha256(zlib.decompress(archive)).hexdigest(), expected["sha256"]
        )

    def test_holdout_discriminates_every_plausible_rival_law(self) -> None:
        self.assertEqual(self.preflight, self.preregistration["preflightDiscrimination"])
        self.assertEqual(self.preflight["sealedRecordCount"], 314_704)
        self.assertEqual(self.preflight["sealedWordCount"], 5_664_672)
        self.assertEqual(
            self.preflight["centerAblationDifferences"],
            {
                "binary32-exact-down": {"records": 2_282, "words": 3_162},
                "determinant-rounded-f32": {"records": 2_198, "words": 3_302},
                "direction-symmetric": {"records": 220, "words": 296},
                "lower-boundary-5/64": {"records": 36, "words": 46},
                "lower-boundary-7/64": {"records": 58, "words": 66},
                "lower-branch-removed": {"records": 74, "words": 102},
                "p27-nearest-even": {"records": 780, "words": 1_346},
                "p27-signed-floor": {"records": 260, "words": 344},
                "upper-boundary-1/2": {"records": 26, "words": 30},
                "upper-boundary-17/32": {"records": 26, "words": 30},
                "upper-boundary-19/32": {"records": 60, "words": 80},
                "upper-branch-removed": {"records": 186, "words": 242},
            },
        )
        self.assertTrue(
            all(
                difference["words"] > 0
                for difference in self.preflight[
                    "centerAblationDifferences"
                ].values()
            )
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
            "#if TILE_CENTER_LATTICE_HOLDOUT\nprivate let cases = [",
            maxsplit=1,
        )[1].split("\n]\n#elseif TILE_CENTER_ORIGIN_HOLDOUT", maxsplit=1)[0]
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
            "private let centerLatticePrimaryBase"
            + source.split(
                "#if TILE_CENTER_LATTICE_HOLDOUT\n"
                "private let centerLatticePrimaryBase",
                maxsplit=1,
            )[1].split("\n#elseif TILE_CENTER_ORIGIN_HOLDOUT", maxsplit=1)[0]
        )

        def uint32_array(name: str) -> list[int]:
            body = re.search(
                rf"private let {name}: \[UInt32\] = \[([^]]+)\]",
                endpoint_block,
            )
            self.assertIsNotNone(body)
            return [int(value) for value in re.findall(r"\d+", body.group(1))]

        self.assertEqual(
            uint32_array("centerLatticePrimaryResidues"),
            list(capture.PRIMARY_TRANSLATED_RESIDUES),
        )
        self.assertEqual(
            uint32_array("centerLatticePrimarySpans"),
            list(capture.PRIMARY_NATIVE_SPANS),
        )
        self.assertEqual(
            uint32_array("centerLatticeTransferSpans"),
            list(capture.TRANSFER_NATIVE_SPANS),
        )
        for value in (
            capture.PREREGISTRATION_SHA256,
            str(capture.layout_metadata()["caseWordsSha256"]),
            str(capture.layout_metadata()["endpointWordsSha256"]),
            str(capture.layout_metadata()["sampleWordsSha256"]),
            'layout["rawBytes"] as? Int == 49_213_440',
            'layout["expectedRecordCount"] as? Int == 325_384',
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
                        "Analysis/raster_tile_center_lattice_preregistration.json"
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
        self.assertEqual(report["recordCount"], 325_384)
        self.assertEqual(report["wordMismatchCount"], 0)
        self.assertTrue(report["sealedPredictionHashExact"])
        self.assertTrue(report["exact"])


if __name__ == "__main__":
    unittest.main()
