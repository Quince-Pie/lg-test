#!/usr/bin/env python3
"""Source checks for the small-geometry helper transport retry."""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
SOURCE_PATH = (
    ANALYSIS_ROOT
    / "capture_prepare_layer_small_geometry_helper_code_callback_retry_lldb.py"
)
FROZEN_PATH = ANALYSIS_ROOT / "capture_prepare_layer_small_geometry_helper_code_lldb.py"
FROZEN_SHA256 = "7dcff793c88e0bfbcf30fcd9bd11ad14a526a6a51c7cd59069db9d9249b50910"


class SmallGeometryHelperCodeCallbackRetrySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")

    def test_failed_capture_is_preserved_byte_for_byte(self) -> None:
        self.assertEqual(
            hashlib.sha256(FROZEN_PATH.read_bytes()).hexdigest(), FROZEN_SHA256
        )

    def test_writer_is_repaired_before_frozen_initialization(self) -> None:
        initialization = self.source.index("def __lldb_init_module")
        repair = self.source.index("_repair_trace_writer()", initialization)
        delegate = self.source.index("frozen.__lldb_init_module", initialization)
        self.assertLess(repair, delegate)
        self.assertIn("frozen.frozen.frozen.frozen._write_trace()", self.source)

    def test_all_dynamic_callbacks_are_top_level_visible(self) -> None:
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

    def test_transport_adds_no_capture_mechanism(self) -> None:
        for token in (
            "BreakpointCreate",
            "WatchAddress",
            "ReadMemory",
            "StepInstruction",
            "ResolveLoadAddress",
        ):
            self.assertNotIn(token, self.source)
        self.assertIn("frozen.trace_selected_sdf_filter_map_bounds()", self.source)


if __name__ == "__main__":
    unittest.main()
