#!/usr/bin/env python3
"""Source checks for the SDF diagnostic callback retry."""

import hashlib
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
SOURCE_PATH = (
    ANALYSIS_ROOT
    / "capture_prepare_layer_sdf_map_bounds_diagnostic_callback_retry_lldb.py"
)
FROZEN_PATH = ANALYSIS_ROOT / "capture_prepare_layer_sdf_map_bounds_diagnostic_lldb.py"
FROZEN_SHA256 = "a9c35bfe48a3547bfb428022bb2d2a6151e11c33155d31a5748a94e1237424e0"


class PrepareLayerSDFMapBoundsCallbackRetrySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")

    def test_frozen_sdf_capture_remains_unchanged(self) -> None:
        self.assertEqual(
            hashlib.sha256(FROZEN_PATH.read_bytes()).hexdigest(), FROZEN_SHA256
        )

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

    def test_dynamic_callbacks_are_rebound_after_entry(self) -> None:
        entry = self.source.index("def prepare_layer_entry")
        delegate = self.source.index("regular.prepare_layer_entry", entry)
        rebind = self.source.index("_install_callback_proxies()", delegate)
        self.assertLess(delegate, rebind)

    def test_retry_adds_no_capture_mechanism(self) -> None:
        for token in (
            "BreakpointCreate",
            "WatchAddress",
            "ReadMemory",
            "StepInstruction",
            "StepOut",
        ):
            self.assertNotIn(token, self.source)
        self.assertIn("frozen.trace_selected_sdf_filter_map_bounds()", self.source)


if __name__ == "__main__":
    unittest.main()
