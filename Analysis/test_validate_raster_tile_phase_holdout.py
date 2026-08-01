#!/usr/bin/env python3
"""Tests for the frozen schema-4 tile-selector phase holdout."""

import hashlib
import unittest
from pathlib import Path

import raster_tile_selector_model_v2 as model
import validate_raster_tile_phase_holdout as capture


class RasterTilePhaseHoldoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration = capture.load_preregistration()
        cls.metadata = model.prediction_metadata()

    def test_layout_and_prediction_are_frozen(self) -> None:
        self.assertEqual(capture.raw_bytes(), 98_721_792)
        self.assertEqual(capture.layout_metadata()["expectedRecordCount"], 721_206)
        self.assertEqual(
            capture.layout_metadata()["caseWordsSha256"],
            "8a02f012c3c1f8eb7efb206b81128816258ede1a25bdffac3edfb4213b072d66",
        )
        self.assertFalse(self.preregistration["holdoutOpenedAtPreregistration"])
        self.assertEqual(self.metadata["recordCount"], 389_500)
        self.assertEqual(self.metadata["bytes"], 28_044_000)
        self.assertEqual(
            self.metadata["sha256"],
            "e50b06d43600090e66f969aab46cc1d2ce8a790f40ce2934876021b1730d78d5",
        )

    def test_model_selects_each_frozen_branch_from_inputs(self) -> None:
        selector_table = model.v1.load_selector_table()
        endpoint = next(
            endpoint
            for endpoint in capture.ENDPOINTS
            if endpoint.name == "mantissa-b0-r00-s08"
        )
        expected = {
            "opened-tall-509x907": (0, "nearest-middle", "295/509"),
            "opened-tall-511x896": (0, "strict-below-floor", "256/511"),
            "opened-phase-769x251": (1, "fixed-product", "241/251"),
        }
        by_name = {capture_case.name: capture_case for capture_case in capture.CASES}
        for name, (axis, branch, phase) in expected.items():
            selected_branch, _, selected_phase = model.selected_slope(
                by_name[name],
                endpoint,
                axis=axis,
                selector_table=selector_table,
            )
            self.assertEqual(selected_branch, branch)
            self.assertEqual(str(selected_phase), phase)

    def test_swift_probe_embeds_both_frozen_contracts(self) -> None:
        source = (
            Path(__file__).parents[1]
            / "Sources"
            / "GlassRasterTileNumerator"
            / "main.swift"
        ).read_text(encoding="utf-8")
        for value in (
            "#if TILE_PHASE_HOLDOUT",
            capture.PREREGISTRATION_SHA256,
            str(capture.layout_metadata()["caseWordsSha256"]),
            str(capture.layout_metadata()["endpointWordsSha256"]),
            str(capture.layout_metadata()["sampleWordsSha256"]),
            'layout["rawBytes"] as? Int == 98_721_792',
            'layout["expectedRecordCount"] as? Int == 721_206',
        ):
            self.assertIn(value, source)

    def test_frozen_model_sources_match_preregistration(self) -> None:
        frozen = self.preregistration["model"]
        self.assertEqual(
            hashlib.sha256(Path(model.__file__).read_bytes()).hexdigest(),
            frozen["sourceSha256"],
        )
        self.assertEqual(
            hashlib.sha256(Path(model.v1.__file__).read_bytes()).hexdigest(),
            frozen["baseSourceSha256"],
        )


if __name__ == "__main__":
    unittest.main()
