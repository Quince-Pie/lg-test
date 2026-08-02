#!/usr/bin/env python3
"""Tests for the frozen schema-12 varied-extent tomography contract."""

import json
import re
import unittest
from pathlib import Path

import raster_tile_selector_model as v1
import validate_raster_tile_center_extent_tomography as capture


class RasterTileCenterExtentTomographyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration = capture.load_preregistration()

    def test_layout_is_frozen_before_capture(self) -> None:
        layout = capture.layout_metadata()
        self.assertEqual(layout["caseCount"], 40)
        self.assertEqual(layout["endpointCount"], 78)
        self.assertEqual(layout["recordCount"], 1_965_600)
        self.assertEqual(layout["expectedRecordCount"], 1_432_704)
        self.assertEqual(layout["rawBytes"], 141_523_200)
        self.assertEqual(
            layout["caseWordsSha256"],
            "bcec9916cd8095303f3df9c2c2c32bf96f6eec5fedf006410a8e5a8beb4859b5",
        )
        self.assertEqual(
            layout["endpointWordsSha256"],
            "dbf456fa22c3b4c1d184826ace207ee544fa51cc94762ceddcdcc195731de5f6",
        )
        self.assertEqual(
            layout["sampleWordsSha256"],
            "20d3bb5316478835289c61c80dbe7a1049deb03d4c08a99de9e4fc40dd084b86",
        )
        self.assertFalse(
            self.preregistration["appleOutputsObservedAtPreregistration"]
        )

    def test_extent_matrix_contains_decisive_neighbors_and_factorizations(
        self,
    ) -> None:
        self.assertEqual(
            capture.EFFECTIVE_EXTENTS,
            (
                191,
                193,
                197,
                198,
                199,
                203,
                204,
                211,
                220,
                231,
                251,
                252,
                253,
                255,
                256,
                257,
                315,
            ),
        )
        counts = {
            extent: sum(spec.extent == extent for spec in capture.CASE_SPECS)
            for extent in capture.EFFECTIVE_EXTENTS
        }
        self.assertEqual(counts[198], 2)
        self.assertEqual(counts[252], 2)
        self.assertEqual(counts[256], 2)
        self.assertTrue(all(value == 1 for key, value in counts.items() if key not in {198, 252, 256}))

    def test_dense_samples_cover_each_effective_pixel_and_both_primitives(
        self,
    ) -> None:
        for capture_case in capture.CASES:
            axis, extent, origin, _ = capture.effective_geometry(capture_case)
            samples = capture.sample_positions(capture_case)
            self.assertEqual(len(samples), 2 * extent)
            self.assertEqual({sample.axis for sample in samples}, {axis})
            for primitive in range(capture.PRIMITIVE_COUNT):
                primitive_samples = [
                    sample for sample in samples if sample.primitive == primitive
                ]
                self.assertEqual(
                    {
                        (sample.x if axis == 0 else sample.y) - origin
                        for sample in primitive_samples
                    },
                    set(range(extent)),
                )

    def test_endpoint_matrix_is_regenerated_from_declared_families(self) -> None:
        endpoints = capture.tomography_endpoints()
        self.assertEqual(endpoints, capture.ENDPOINTS)
        self.assertEqual(len(endpoints), 78)
        self.assertEqual(
            sum(endpoint.role == "prospective-control" for endpoint in endpoints),
            2,
        )
        for family in capture.FAMILY_RESIDUES:
            self.assertTrue(any(f"-{family}-" in endpoint.name for endpoint in endpoints))
        self.assertEqual(
            sum("-n15-" in endpoint.name for endpoint in endpoints),
            44,
        )

    def test_preregistration_freezes_discovery_scope_and_zero_claim(self) -> None:
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
                "schema11RetrospectiveScaleCandidateWordMismatchCount"
            ],
            0,
        )

    def test_determinant_control_predictor_is_finite_for_every_case(self) -> None:
        selector_table = v1.load_selector_table()
        for capture_case in capture.CASES:
            for endpoint in capture.ENDPOINTS[:2]:
                for sample in capture.sample_positions(capture_case):
                    prediction = capture.control_pull_prediction(
                        capture_case,
                        endpoint,
                        sample,
                        selector_table,
                    )
                    self.assertEqual(len(prediction), capture.PULL_COUNT)
                    self.assertTrue(all(capture.base.finite(bits) for bits in prediction))

    def test_swift_matrix_and_frozen_hashes_are_present(self) -> None:
        source = (
            Path(__file__).parents[1]
            / "Sources"
            / "GlassRasterTileNumerator"
            / "main.swift"
        ).read_text(encoding="utf-8")
        extent_blocks = re.split(
            r"#(?:if|elseif) TILE_CENTER_EXTENT_TOMOGRAPHY\n"
            r"private let centerExtentSet",
            source,
            maxsplit=1,
        )
        self.assertEqual(len(extent_blocks), 2)
        extent_block = extent_blocks[1]
        case_block = extent_block.split("private let cases = [", maxsplit=1)[1].split(
            "\n]\n#elseif TILE_CENTER_TOMOGRAPHY",
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
                r"CaptureCase\(name: \"(?P<name>[^\"]+)\", "
                r"role: \"(?P<role>[^\"]+)\", width: (?P<width>\d+), "
                r"height: (?P<height>\d+), originX: (?P<origin_x>\d+), "
                r"originY: (?P<origin_y>\d+)\)",
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
            'layout["rawBytes"] as? Int == 141_523_200',
            'layout["expectedRecordCount"] as? Int == 1_432_704',
        ):
            self.assertIn(value, source)

    def test_manifest_metadata_is_json_serializable(self) -> None:
        json.dumps(capture.capture_metadata(), sort_keys=True)


if __name__ == "__main__":
    unittest.main()
