#!/usr/bin/env python3
"""Source-level checks for the geometry-only 513 LLDB adapter."""

import ast
import hashlib
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
ADAPTER_PATH = ANALYSIS_ROOT / "capture_prepare_layer_filter_map_bounds_513_lldb.py"
FROZEN_PATH = ANALYSIS_ROOT / "capture_prepare_layer_filter_map_bounds_lldb.py"
FROZEN_SHA256 = "0755924cd34936f6cc433d1efe322989229f94423a832107a73ae087da0c1320"


class PrepareLayerFilterMapBounds513SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = ADAPTER_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_frozen_capture_is_unchanged(self) -> None:
        self.assertEqual(
            hashlib.sha256(FROZEN_PATH.read_bytes()).hexdigest(), FROZEN_SHA256
        )

    def test_adapter_changes_only_geometry_then_delegates(self) -> None:
        self.assertIn('EXPECTED_GEOMETRY = "circle-513-center"', self.source)
        self.assertIn("frozen.base.EXPECTED_GEOMETRY = EXPECTED_GEOMETRY", self.source)
        self.assertIn("frozen.trace_selected_filter_map_bounds()", self.source)
        self.assertIn("frozen.__lldb_init_module(debugger, internal_dict)", self.source)
        forbidden = (
            "BreakpointCreate",
            "WatchAddress",
            "ReadMemory",
            "StepInstruction",
        )
        for token in forbidden:
            self.assertNotIn(token, self.source)

    def test_adapter_defines_no_selector_or_callback(self) -> None:
        names = {
            node.name
            for node in self.tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertEqual(
            names,
            {
                "_configure_geometry",
                "trace_selected_filter_map_bounds",
                "finalize",
                "__lldb_init_module",
            },
        )


if __name__ == "__main__":
    unittest.main()
