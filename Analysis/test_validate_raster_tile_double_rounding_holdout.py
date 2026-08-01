#!/usr/bin/env python3
"""Tests for the frozen schema-6 double-rounding prospective holdout."""

import hashlib
import json
import re
import tempfile
import unittest
import zlib
from dataclasses import asdict
from pathlib import Path

import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v4 as model
import validate_raster_tile_double_rounding_holdout as capture


class RasterTileDoubleRoundingHoldoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration = capture.load_preregistration()
        cls.prediction_metadata = model.prediction_metadata()
        cls.preflight = model.preflight_discrimination_metadata()

    def test_layout_is_frozen_before_capture(self) -> None:
        layout = capture.layout_metadata()
        self.assertEqual(layout["caseCount"], 21)
        self.assertEqual(layout["endpointCount"], 138)
        self.assertEqual(layout["recordCount"], 741_888)
        self.assertEqual(layout["rawBytes"], 53_415_936)
        self.assertEqual(layout["expectedRecordCount"], 339_480)
        self.assertEqual(
            layout["caseWordsSha256"],
            "a763461f47e92a321f23651d67cd651932082451d6f1ecfa6a2cd257e5aff4a1",
        )
        self.assertEqual(
            layout["endpointWordsSha256"],
            "0c973d020f842a2dac63cf0c0d240332f2072081205580f615e13f1353286c00",
        )
        self.assertEqual(
            layout["sampleWordsSha256"],
            "a759e8e87d22679ea09cdfda1972913beda75c2cbb18c428a30d13ce12ad3526",
        )
        self.assertEqual(
            layout["samplesPerCase"],
            [
                60,
                106,
                106,
                110,
                110,
                118,
                118,
                122,
                122,
                128,
                128,
                144,
                144,
                144,
                144,
                54,
                54,
                134,
                134,
                140,
                140,
            ],
        )
        self.assertFalse(self.preregistration["sealedHoldoutOpenedAtPreregistration"])

    def test_endpoint_matrix_crosses_every_frozen_selector_boundary(self) -> None:
        arithmetic = [
            endpoint
            for endpoint in capture.ENDPOINTS
            if endpoint.role == "arithmetic-holdout"
        ]
        self.assertEqual(len(arithmetic), 136)
        self.assertEqual(
            sum(endpoint.name.startswith("zero-") for endpoint in arithmetic),
            16,
        )
        self.assertEqual(
            sum(endpoint.name.startswith("translated-") for endpoint in arithmetic),
            120,
        )
        for units in capture.ZERO_DELTA_UNITS:
            expected = units * 2.0**-25
            selected = [
                endpoint
                for endpoint in arithmetic
                if endpoint.name.startswith(f"zero-u{units:02d}-")
            ]
            self.assertEqual(len(selected), 2)
            for endpoint in selected:
                delta = abs(
                    capture.base.bits_float32(endpoint.highBits)
                    - capture.base.bits_float32(endpoint.lowBits)
                )
                self.assertEqual(delta, expected)

    def test_every_noncontrol_case_is_sealed(self) -> None:
        controls = [
            case.name for case in capture.CASES if case.role == "prospective-control"
        ]
        sealed = [case.name for case in capture.CASES if case.role == "sealed-holdout"]
        self.assertEqual(controls, ["control-square-256"])
        self.assertEqual(sealed, self.preregistration["capture"]["sealedCases"])
        self.assertEqual(len(sealed), 20)

    def test_input_only_model_and_every_prediction_byte_are_frozen(self) -> None:
        frozen = self.preregistration["model"]
        prediction = self.preregistration["predictedTruthStream"]
        self.assertEqual(
            frozen["sourceSha256"], capture.sha256_path(Path(model.__file__))
        )
        self.assertEqual(
            frozen["baseSourceSha256"], capture.sha256_path(Path(v1.__file__))
        )
        self.assertEqual(
            frozen["v2SourceSha256"], capture.sha256_path(Path(v2.__file__))
        )
        self.assertTrue(frozen["centerAndPullMayUseDistinctCoefficients"])
        self.assertEqual(self.prediction_metadata["recordCount"], 331_200)
        self.assertEqual(self.prediction_metadata["bytes"], 23_846_400)
        self.assertEqual(
            self.prediction_metadata["sha256"],
            "14b52a038113e7dfa3c404beaaf81702674a4bcad3fc3a537d236e8b0cd580d5",
        )
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
            self.assertEqual(prediction[key], self.prediction_metadata[key])

        archive = model.PREDICTION_ARCHIVE_PATH.read_bytes()
        self.assertEqual(len(archive), 1_801_884)
        self.assertEqual(
            hashlib.sha256(archive).hexdigest(),
            "3b583f133a822bdfeed9e643bbef3543ad6b7b11d2fceae8aeb94b8823313144",
        )
        raw = zlib.decompress(archive)
        self.assertEqual(len(raw), self.prediction_metadata["bytes"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), prediction["sha256"])

    def test_model_has_no_geometry_name_selector(self) -> None:
        source = Path(model.__file__).read_text(encoding="utf-8")
        for capture_case in capture.CASES:
            self.assertNotIn(f'"{capture_case.name}"', source)

    def test_holdout_discriminates_all_new_arithmetic_rules(self) -> None:
        self.assertEqual(
            self.preflight,
            self.preregistration["preflightDiscrimination"],
        )
        self.assertEqual(self.preflight["sealedRecordCount"], 331_200)
        self.assertEqual(self.preflight["sealedWordCount"], 5_961_600)
        self.assertEqual(self.preflight["slopeSetupCount"], 5_520)
        self.assertEqual(self.preflight["constantGroupCount"], 169_740)
        self.assertEqual(
            self.preflight["sharedPullCenterSlopeAblation"],
            {"recordDifferenceCount": 64, "wordDifferenceCount": 128},
        )
        self.assertEqual(
            self.preflight["singleRoundedZeroConstantAblation"],
            {"recordDifferenceCount": 170, "wordDifferenceCount": 2_891},
        )
        selected = self.preflight[
            "determinantOnlyAblationWordDifferencesBySelectedPath"
        ]
        self.assertEqual(
            selected[
                "pull=determinant-rounded-f32,"
                "center=translated-forward-center-toward-zero"
            ],
            128,
        )
        self.assertEqual(
            selected[
                "pull=translated-forward-pull-toward-zero,"
                "center=translated-forward-center-toward-zero"
            ],
            1_380,
        )
        self.assertEqual(
            selected["pull=translated-reverse-away,center=translated-reverse-away"],
            72,
        )

    def test_swift_probe_embeds_the_frozen_contract(self) -> None:
        source = (
            Path(__file__).parents[1]
            / "Sources"
            / "GlassRasterTileNumerator"
            / "main.swift"
        ).read_text(encoding="utf-8")
        for value in (
            "#if TILE_DOUBLE_ROUNDING_HOLDOUT",
            capture.PREREGISTRATION_SHA256,
            str(capture.layout_metadata()["caseWordsSha256"]),
            str(capture.layout_metadata()["endpointWordsSha256"]),
            str(capture.layout_metadata()["sampleWordsSha256"]),
            'layout["rawBytes"] as? Int == 53_415_936',
            'layout["expectedRecordCount"] as? Int == 339_480',
        ):
            self.assertIn(value, source)

    def test_swift_and_python_capture_matrices_are_identical(self) -> None:
        source = (
            Path(__file__).parents[1]
            / "Sources"
            / "GlassRasterTileNumerator"
            / "main.swift"
        ).read_text(encoding="utf-8")
        case_block = source.split(
            "#if TILE_DOUBLE_ROUNDING_HOLDOUT\nprivate let cases = [",
            maxsplit=1,
        )[1].split("\n]\n#elseif TILE_TRANSLATION_HOLDOUT", maxsplit=1)[0]
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
            "private let doubleRoundingZeroDeltas"
            + source.split(
                "#if TILE_DOUBLE_ROUNDING_HOLDOUT\n"
                "private let doubleRoundingZeroDeltas",
                maxsplit=1,
            )[1].split("\n#elseif TILE_TRANSLATION_HOLDOUT", maxsplit=1)[0]
        )

        def uint32_array(name: str) -> list[int]:
            body = re.search(
                rf"private let {name}: \[UInt32\] = \[([^]]+)\]",
                endpoint_block,
            )
            self.assertIsNotNone(body)
            return [int(value) for value in re.findall(r"\d+", body.group(1))]

        zero_body = re.search(
            r"private let doubleRoundingZeroDeltas:[^=]+ = \[([^]]+)\]",
            endpoint_block,
        )
        self.assertIsNotNone(zero_body)
        zero_deltas = [
            (int(units), int(bits.replace("_", ""), 16))
            for units, bits in re.findall(
                r"\((\d+), 0x([0-9a-fA-F_]+)\)",
                zero_body.group(1),
            )
        ]
        primary = re.search(
            r'private let doubleRoundingPrimaryBase = \(name: "([^"]+)", '
            r"bits: UInt32\(0x([0-9a-fA-F_]+)\)\)",
            endpoint_block,
        )
        self.assertIsNotNone(primary)
        primary_base = (primary.group(1), int(primary.group(2).replace("_", ""), 16))
        transfer_body = re.search(
            r"private let doubleRoundingTransferBases:[^=]+ = \[([^]]+)\]",
            endpoint_block,
        )
        self.assertIsNotNone(transfer_body)
        transfer_bases = [
            (name, int(bits.replace("_", ""), 16))
            for name, bits in re.findall(
                r'\("([^"]+)", 0x([0-9a-fA-F_]+)\)',
                transfer_body.group(1),
            )
        ]
        self.assertEqual(
            zero_deltas,
            [
                (units, capture.base.float32_bits(units * 2.0**-25))
                for units in capture.ZERO_DELTA_UNITS
            ],
        )
        self.assertEqual(primary_base, capture.PRIMARY_TRANSLATED_BASE)
        self.assertEqual(
            uint32_array("doubleRoundingPrimaryResidues"),
            list(capture.PRIMARY_TRANSLATED_RESIDUES),
        )
        self.assertEqual(
            uint32_array("doubleRoundingPrimarySpans"),
            list(capture.PRIMARY_NATIVE_SPANS),
        )
        self.assertEqual(transfer_bases, list(capture.TRANSFER_TRANSLATED_BASES))
        self.assertEqual(
            uint32_array("doubleRoundingTransferResidues"),
            list(capture.TRANSFER_TRANSLATED_RESIDUES),
        )
        self.assertEqual(
            uint32_array("doubleRoundingTransferSpans"),
            list(capture.TRANSFER_NATIVE_SPANS),
        )

    def test_synthetic_capture_validates_without_opening_sealed_values(self) -> None:
        raw = bytearray(b"\xff" * capture.raw_bytes())
        for case_index, capture_case in enumerate(capture.CASES):
            samples = capture.sample_positions(capture_case)
            for endpoint_index, endpoint in enumerate(capture.ENDPOINTS):
                for sample in samples:
                    record_index = (
                        case_index * len(capture.ENDPOINTS) + endpoint_index
                    ) * capture.SLOT_COUNT + sample.slot
                    values = (0,) * capture.RECORD_COMPONENT_COUNT
                    if capture_case.name == "control-square-256" and endpoint.name in {
                        "zero-to-one",
                        "one-to-zero",
                    }:
                        values = (
                            *capture.base.control_pull_prediction(
                                capture_case,
                                endpoint,
                                sample,
                            ),
                            0,
                            0,
                        )
                    capture.RECORD.pack_into(
                        raw,
                        record_index * capture.RECORD.size,
                        *values,
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
                        "Analysis/raster_tile_double_rounding_preregistration.json"
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
            report = capture.validate(root)
        self.assertEqual(report["expectedRecords"], 339_480)
        self.assertTrue(report["prospectiveControlExact"])
        self.assertFalse(report["sealedHoldoutOpened"])
        self.assertFalse(report["productionShaderAuthorized"])


if __name__ == "__main__":
    unittest.main()
