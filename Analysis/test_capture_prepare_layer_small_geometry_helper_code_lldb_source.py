#!/usr/bin/env python3
"""Source checks for the small-geometry helper-code capture adapter."""

from __future__ import annotations

import unittest
from pathlib import Path


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "capture_prepare_layer_small_geometry_helper_code_lldb.py"
)


class SmallGeometryHelperCodeSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")

    def test_only_two_structurally_identified_helpers_are_added(self) -> None:
        self.assertIn('"relativeToPrepareLayer": -96880', self.source)
        self.assertIn('"symbolByteCount": 200', self.source)
        self.assertIn('"relativeToPrepareLayer": 364616', self.source)
        self.assertIn('"symbolByteCount": 80', self.source)
        self.assertIn('"expectedCodeSHA256": None', self.source)
        self.assertNotIn('"expectedCodeSHA256": "', self.source)
        for token in ("BreakpointCreate", "WatchAddress", "StepInstruction", "StepOut"):
            self.assertNotIn(token, self.source)

    def test_capture_precedes_the_unchanged_filter_sdf_trace(self) -> None:
        body = self.source.split("def trace_selected_sdf_filter_map_bounds():", 1)[1]
        self.assertLess(
            body.index("_capture_helper_code()"),
            body.index("frozen.trace_selected_sdf_filter_map_bounds()"),
        )
        self.assertIn('"staticMemoryReadsOnly": True', self.source)
        self.assertIn('"breakpointsAdded": 0', self.source)
        self.assertIn('"instructionStepsAdded": 0', self.source)

    def test_every_inherited_callback_remains_top_level_visible(self) -> None:
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

    def test_no_crop_or_output_value_can_select_helper_code(self) -> None:
        self.assertIn('"cropValuesUsedForSelection": False', self.source)
        self.assertIn('"outputValuesUsedForSelection": False', self.source)
        self.assertNotIn("observedProducer", self.source)
        self.assertNotIn("candidateRectangle", self.source)


if __name__ == "__main__":
    unittest.main()
