#!/usr/bin/env python3
"""Tests for the frozen schema-5 matched-delta discriminator."""

import hashlib
import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

import analyze_raster_tile_translation_discriminator as analysis
import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v3 as model
import validate_raster_tile_translation_discriminator as capture


class RasterTileTranslationDiscriminatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration = capture.load_preregistration()
        cls.prediction_metadata = model.prediction_metadata()

    def test_layout_is_frozen_before_capture(self) -> None:
        layout = capture.layout_metadata()
        self.assertEqual(layout["caseCount"], 29)
        self.assertEqual(layout["endpointCount"], 56)
        self.assertEqual(layout["recordCount"], 415_744)
        self.assertEqual(layout["rawBytes"], 29_933_568)
        self.assertEqual(layout["expectedRecordCount"], 235_200)
        self.assertEqual(
            layout["caseWordsSha256"],
            "13c1e6caf108baf46887dc8ab2545cca5fc7b58f069c49c60983d2cb0e9c94e4",
        )
        self.assertEqual(
            layout["endpointWordsSha256"],
            "d601be7d61acc7ea3a96c12ba7e4519d12b0f4684761e662500b9df9c3253976",
        )
        self.assertEqual(
            layout["sampleWordsSha256"],
            "887eb7020dbc052b39dd7c3281ec7983f60abdcda2959c0f446979b8c3f61334",
        )
        self.assertFalse(
            self.preregistration["sealedHoldoutOpenedAtPreregistration"]
        )

    def test_every_absolute_delta_has_matched_endpoint_translations(self) -> None:
        arithmetic = [
            endpoint
            for endpoint in capture.ENDPOINTS
            if endpoint.role == "arithmetic-discovery"
        ]
        self.assertEqual(len(arithmetic), 54)
        for units in capture.DELTA_UNITS:
            expected = units * 2.0**-25
            selected = [
                endpoint
                for endpoint in arithmetic
                if f"u{units:02d}-" in endpoint.name
            ]
            self.assertEqual(len(selected), 18)
            self.assertEqual(
                sum(endpoint.name.startswith("zero-") for endpoint in selected),
                2,
            )
            self.assertEqual(
                sum(endpoint.name.startswith("translated-") for endpoint in selected),
                16,
            )
            for endpoint in selected:
                delta = abs(
                    capture.base.bits_float32(endpoint.highBits)
                    - capture.base.bits_float32(endpoint.lowBits)
                )
                self.assertEqual(delta, expected)

    def test_sealed_geometry_is_not_available_to_discovery_analysis(self) -> None:
        discovery = [case.name for case in capture.CASES if case.role == "discovery"]
        sealed = [
            case.name for case in capture.CASES if case.role == "sealed-holdout"
        ]
        self.assertEqual(discovery, self.preregistration["capture"]["discoveryCases"])
        self.assertEqual(sealed, self.preregistration["capture"]["sealedCases"])
        self.assertEqual(len(discovery), 4)
        self.assertEqual(len(sealed), 24)
        self.assertTrue(
            self.preregistration["blinding"][
                "sealedPredictionsMustBeCommittedBeforeOpening"
            ]
        )

    def test_discovery_accessor_rejects_a_sealed_record_before_io(self) -> None:
        case_index = next(
            index
            for index, capture_case in enumerate(capture.CASES)
            if capture_case.role == "sealed-holdout"
        )
        sample = capture.sample_positions(capture.CASES[case_index])[0]
        records = analysis.DiscoveryRecords(Path("must-not-be-opened.raw"))
        with self.assertRaises(PermissionError):
            records.record(case_index, 0, sample)
        self.assertEqual(records.discovery_reads, 0)
        self.assertEqual(records.sealed_reads, 1)

    def test_input_only_model_and_every_prediction_byte_are_frozen(self) -> None:
        frozen = self.preregistration["model"]
        prediction = self.preregistration["predictedTruthStream"]
        self.assertEqual(frozen["sourceSha256"], capture.sha256_path(Path(model.__file__)))
        self.assertEqual(frozen["baseSourceSha256"], capture.sha256_path(Path(v1.__file__)))
        self.assertEqual(frozen["v2SourceSha256"], capture.sha256_path(Path(v2.__file__)))
        self.assertTrue(frozen["inputOnly"])
        self.assertFalse(frozen["usesCaseNames"])
        self.assertFalse(frozen["usesCapturedValues"])
        self.assertEqual(self.prediction_metadata["recordCount"], 196_672)
        self.assertEqual(self.prediction_metadata["bytes"], 14_160_384)
        self.assertEqual(
            self.prediction_metadata["sha256"],
            "95e16a3c1b7ddf3d5a2a760eea3ae9c31aadf81a3c37eda35d76e2cee819bdc4",
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
        raw = model.read_prediction_archive()
        self.assertEqual(len(raw), self.prediction_metadata["bytes"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), prediction["sha256"])

    def test_model_has_no_geometry_name_selector(self) -> None:
        source = Path(model.__file__).read_text(encoding="utf-8")
        for capture_case in capture.CASES:
            self.assertNotIn(f'"{capture_case.name}"', source)

    def test_swift_probe_embeds_the_frozen_contract(self) -> None:
        source = (
            Path(__file__).parents[1]
            / "Sources"
            / "GlassRasterTileNumerator"
            / "main.swift"
        ).read_text(encoding="utf-8")
        for value in (
            "#if TILE_TRANSLATION_HOLDOUT",
            capture.PREREGISTRATION_SHA256,
            str(capture.layout_metadata()["caseWordsSha256"]),
            str(capture.layout_metadata()["endpointWordsSha256"]),
            str(capture.layout_metadata()["sampleWordsSha256"]),
            'layout["rawBytes"] as? Int == 29_933_568',
            'layout["expectedRecordCount"] as? Int == 235_200',
        ):
            self.assertIn(value, source)

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
                        "Analysis/"
                        "raster_tile_translation_discriminator_preregistration.json"
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
        self.assertEqual(report["expectedRecords"], 235_200)
        self.assertTrue(report["prospectiveControlExact"])
        self.assertFalse(report["sealedHoldoutOpened"])


if __name__ == "__main__":
    unittest.main()
