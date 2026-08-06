#!/usr/bin/env python3
"""Source checks for the 513 callback-transport retry."""

import hashlib
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
SOURCE_PATH = (
    ANALYSIS_ROOT / "capture_prepare_layer_filter_map_bounds_513_callback_retry_lldb.py"
)
FROZEN_PATH = ANALYSIS_ROOT / "capture_prepare_layer_filter_map_bounds_lldb.py"
FROZEN_SHA256 = "0755924cd34936f6cc433d1efe322989229f94423a832107a73ae087da0c1320"


class PrepareLayerFilterMapBounds513CallbackRetrySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")

    def test_frozen_capture_remains_unchanged(self) -> None:
        self.assertEqual(
            hashlib.sha256(FROZEN_PATH.read_bytes()).hexdigest(), FROZEN_SHA256
        )

    def test_geometry_is_configured_before_frozen_initialization(self) -> None:
        self.assertIn('EXPECTED_GEOMETRY = "circle-513-center"', self.source)
        initialization = self.source.index("def __lldb_init_module")
        configure = self.source.index("_configure_geometry()", initialization)
        delegate = self.source.index("frozen.__lldb_init_module", initialization)
        self.assertLess(configure, delegate)

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
        ):
            self.assertNotIn(token, self.source)
        self.assertIn("frozen.trace_selected_filter_map_bounds()", self.source)


if __name__ == "__main__":
    unittest.main()
