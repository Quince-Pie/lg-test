#!/usr/bin/env python3
"""Source checks for the helper-semantics static capture."""

from __future__ import annotations

import unittest
from pathlib import Path


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "capture_prepare_layer_small_geometry_helper_semantics_lldb.py"
)


class SmallGeometryHelperSemanticsSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")

    def test_targets_come_only_from_accepted_code_references(self) -> None:
        for offset in (
            "0x394910",
            "0x394928",
            "0x394930",
            "0x394938",
            "0x394940",
            "0x394918",
            "0x394920",
            "0x3944F8",
        ):
            self.assertIn(offset, self.source)
        self.assertIn(
            "GET_BACKDROP_BOUNDS_RELATIVE_TO_PREPARE_LAYER = 364696", self.source
        )
        self.assertIn("GET_BACKDROP_BOUNDS_MAXIMUM_BYTE_COUNT = 65536", self.source)

    def test_values_and_callee_hash_are_unknown_before_capture(self) -> None:
        self.assertIn('"constantValuesAcceptedBeforeCapture": None', self.source)
        self.assertIn('"globalModeFlagValueAcceptedBeforeCapture": None', self.source)
        self.assertIn('"getBackdropBoundsExpectedCodeSHA256": None', self.source)
        self.assertIn('"expectedCodeSHA256": None', self.source)

    def test_all_inherited_callbacks_remain_top_level_visible(self) -> None:
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

    def test_no_dynamic_capture_mechanism_is_added(self) -> None:
        for token in ("BreakpointCreate", "WatchAddress", "StepInstruction", "StepOut"):
            self.assertNotIn(token, self.source)
        self.assertIn('"staticMemoryReadsOnly": True', self.source)
        self.assertIn('"breakpointsAdded": 0', self.source)
        self.assertIn('"instructionStepsAdded": 0', self.source)


if __name__ == "__main__":
    unittest.main()
