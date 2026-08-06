#!/usr/bin/env python3
"""Source checks for the small-geometry Filter/SDF capture adapter."""

import unittest
from pathlib import Path


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "capture_prepare_layer_filter_sdf_small_geometry_lldb.py"
)


class PrepareLayerFilterSDFSmallGeometrySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")

    def test_only_public_geometry_guard_is_adapted(self) -> None:
        self.assertIn('EXPECTED_GEOMETRY = "circle-127-center"', self.source)
        self.assertIn("regular.EXPECTED_GEOMETRY = EXPECTED_GEOMETRY", self.source)
        self.assertIn(
            "regular.trace_base.EXPECTED_GEOMETRY = EXPECTED_GEOMETRY", self.source
        )
        for token in (
            "BreakpointCreate",
            "WatchAddress",
            "ReadMemory",
            "StepInstruction",
            "StepOut",
        ):
            self.assertNotIn(token, self.source)

    def test_every_inherited_callback_is_top_level_visible(self) -> None:
        for callback in (
            "prepare_layer_entry",
            "crop_transfer_marker",
            "crop_union_call",
            "crop_union_return",
            "nested_crop_store",
            "prepare_layer_mask_entry",
        ):
            self.assertIn(f"def {callback}(", self.source)
            self.assertIn(f'"{callback}"', self.source)

    def test_filter_and_sdf_trace_delegates_unchanged(self) -> None:
        self.assertIn("frozen.trace_selected_sdf_filter_map_bounds()", self.source)


if __name__ == "__main__":
    unittest.main()
