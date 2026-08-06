#!/usr/bin/env python3
"""Source checks for backdrop-state and writer discovery."""

from __future__ import annotations

import unittest
from pathlib import Path


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "capture_prepare_layer_backdrop_state_writer_discovery_lldb.py"
)


class BackdropStateWriterDiscoverySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")

    def test_live_reads_wrap_only_the_accepted_opaque_boundary(self) -> None:
        self.assertIn("_original_trace_opaque_callee", self.source)
        self.assertIn("_trace_opaque_callee_with_backdrop_state", self.source)
        self.assertIn("BACKDROP_OBJECT_BYTE_COUNT = 0x90", self.source)
        self.assertIn("LAYER_OBJECT_BYTE_COUNT = 0x140", self.source)
        self.assertIn("RECT_BYTE_COUNT = 0x20", self.source)
        self.assertIn('"primaryRectBefore": _snapshot(', self.source)
        self.assertIn('record["primaryRectAfter"] = _snapshot(', self.source)
        self.assertIn('"selfLayerPointerDeltaAcceptedBeforeCapture": None', self.source)
        self.assertIn('"backdropFieldValuesAcceptedBeforeCapture": None', self.source)

    def test_static_inventory_is_class_scoped_and_unpredicted(self) -> None:
        self.assertIn('SYMBOL_NAME_SUBSTRING = "BackdropLayer"', self.source)
        self.assertIn("MAXIMUM_MATCHED_CODE_SYMBOL_COUNT = 256", self.source)
        self.assertIn("MAXIMUM_INDIVIDUAL_SYMBOL_BYTE_COUNT = 65536", self.source)
        self.assertIn("MAXIMUM_TOTAL_SYMBOL_BYTE_COUNT = 2 * 1024 * 1024", self.source)
        self.assertIn('"symbolNamesAcceptedBeforeCapture": None', self.source)
        self.assertIn('"symbolCodeHashesAcceptedBeforeCapture": None', self.source)
        self.assertIn('"expectedCodeSHA256": None', self.source)

    def test_no_new_dynamic_mechanism_is_added(self) -> None:
        for token in ("BreakpointCreate", "WatchAddress", "StepInstruction"):
            self.assertNotIn(token, self.source)
        self.assertIn('"newBreakpointsAdded": 0', self.source)
        self.assertIn('"newInstructionStepsAdded": 0', self.source)
        self.assertIn('"existingOpaqueBoundaryStepWrapped": True', self.source)

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


if __name__ == "__main__":
    unittest.main()
