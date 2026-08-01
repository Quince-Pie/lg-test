#!/usr/bin/env python3
"""Tests for the frozen schema-11 dense tile-center tomography capture."""

import json
import re
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

import validate_raster_tile_center_tomography as capture


class RasterTileCenterTomographyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration = capture.load_preregistration()

    def test_layout_is_frozen_before_capture(self) -> None:
        layout = capture.layout_metadata()
        self.assertEqual(layout["caseCount"], 12)
        self.assertEqual(layout["endpointCount"], 78)
        self.assertEqual(layout["recordCount"], 471_744)
        self.assertEqual(layout["rawBytes"], 33_965_568)
        self.assertEqual(layout["expectedRecordCount"], 471_744)
        self.assertEqual(layout["samplesPerCase"], [504] * 12)
        self.assertEqual(
            layout["caseWordsSha256"],
            "0e69bd8ba8f9f0a9fd09783830549ba92c99ff3a0d43622c97155d6db8e5680f",
        )
        self.assertEqual(
            layout["endpointWordsSha256"],
            "eb2f94ef3d830bafba4122f60e3211489a06a3e41bcf5c4f9b92441817a69d3a",
        )
        self.assertEqual(
            layout["sampleWordsSha256"],
            "96a6fd4e885f4ddebb95fbe67e9adf494d0e9469c69baa0b707ad80fd6daa9e5",
        )
        self.assertFalse(
            self.preregistration["appleOutputsObservedAtPreregistration"]
        )

    def test_dense_samples_cover_every_effective_axis_pixel(self) -> None:
        for capture_case in capture.CASES:
            samples = capture.sample_positions(capture_case)
            axis = 0 if capture_case.width == capture.EFFECTIVE_EXTENT else 1
            origin = capture_case.originX if axis == 0 else capture_case.originY
            self.assertEqual({sample.axis for sample in samples}, {axis})
            self.assertEqual({sample.slot for sample in samples}, set(range(504)))
            for primitive in range(capture.PRIMITIVE_COUNT):
                primitive_samples = [
                    sample for sample in samples if sample.primitive == primitive
                ]
                self.assertEqual(len(primitive_samples), capture.EFFECTIVE_EXTENT)
                self.assertEqual(
                    {
                        (sample.x if axis == 0 else sample.y) - origin
                        for sample in primitive_samples
                    },
                    set(range(capture.EFFECTIVE_EXTENT)),
                )

    def test_endpoint_bits_and_depths_are_regenerated(self) -> None:
        expected = list(capture.tomography_endpoints())
        self.assertEqual(list(capture.ENDPOINTS), expected)
        self.assertEqual(len(expected), 78)
        self.assertEqual(
            sum(endpoint.role == "prospective-control" for endpoint in expected),
            2,
        )
        self.assertEqual(
            sum("-quarter-" in endpoint.name for endpoint in expected),
            60,
        )
        self.assertEqual(
            sum("-one-" in endpoint.name for endpoint in expected),
            16,
        )

    def test_preregistration_freezes_capture_and_discovery_scope(self) -> None:
        self.assertEqual(self.preregistration["capture"], capture.capture_metadata())
        self.assertTrue(self.preregistration["acceptance"]["discoveryCapture"])
        self.assertFalse(
            self.preregistration["acceptance"]["prospectiveParityClaim"]
        )
        self.assertFalse(
            self.preregistration["acceptance"][
                "productionShaderAuthorizedByThisCapture"
            ]
        )
        self.assertEqual(
            self.preregistration["derivationEvidence"][
                "schema10PostOpeningResidualWordCount"
            ],
            216,
        )

    def test_swift_and_python_case_matrices_are_identical(self) -> None:
        source = (
            Path(__file__).parents[1]
            / "Sources"
            / "GlassRasterTileNumerator"
            / "main.swift"
        ).read_text(encoding="utf-8")
        case_block = source.split(
            "#if TILE_CENTER_TOMOGRAPHY\nprivate let cases = [",
            maxsplit=1,
        )[1].split("\n]\n#else\n#if TILE_CENTER_BOUNDARY_HOLDOUT", maxsplit=1)[0]
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
            'layout["rawBytes"] as? Int == 33_965_568',
            'layout["expectedRecordCount"] as? Int == 471_744',
        ):
            self.assertIn(value, source)

    def test_manifest_metadata_is_json_serializable(self) -> None:
        json.dumps(capture.capture_metadata(), sort_keys=True)

    def test_synthetic_capture_passes_structural_and_control_gates(self) -> None:
        raw = bytearray(capture.raw_bytes())
        for case_index, capture_case in enumerate(capture.CASES):
            samples = capture.sample_positions(capture_case)
            for endpoint_index, endpoint in enumerate(capture.ENDPOINTS[:2]):
                for sample in samples:
                    record_index = (
                        case_index * len(capture.ENDPOINTS) + endpoint_index
                    ) * capture.SLOT_COUNT + sample.slot
                    capture.RECORD.pack_into(
                        raw,
                        record_index * capture.RECORD.size,
                        *capture.base.control_pull_prediction(
                            capture_case, endpoint, sample
                        ),
                        0,
                        0,
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
                    "role": capture.ROLE,
                    "preregistrationFile": (
                        "Analysis/raster_tile_center_tomography_preregistration.json"
                    ),
                    "preregistrationSha256": capture.PREREGISTRATION_SHA256,
                    "layout": capture.layout_metadata(),
                    "cases": [asdict(value) for value in capture.CASES],
                    "endpoints": capture.endpoint_metadata(),
                    "recordComponents": capture.record_components(),
                    "pullOffsetsByAxis": capture.pull_offsets(),
                    "ordering": capture.ORDERING,
                    "file": raw_path.name,
                    "bytes": len(raw),
                    "sha256": capture.sha256_path(raw_path),
                },
            }
            (root / "manifest.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            report = capture.validate(root)
        self.assertEqual(report["expectedRecords"], 471_744)
        self.assertEqual(report["finiteWords"], 8_491_392)
        self.assertEqual(report["prospectiveControlRecords"], 12_096)
        self.assertEqual(report["prospectiveControlPullMismatches"], 0)
        self.assertTrue(report["prospectiveControlExact"])


if __name__ == "__main__":
    unittest.main()
