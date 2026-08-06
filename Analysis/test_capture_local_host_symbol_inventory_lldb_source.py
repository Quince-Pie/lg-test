#!/usr/bin/env python3
"""Static contracts for the local macOS symbol-inventory bootstrap."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


SOURCE = Path(__file__).with_name("capture_local_host_symbol_inventory_lldb.py")


class LocalHostSymbolInventoryLLDBSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SOURCE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.text)

    def test_stops_before_rendering_and_uses_fixed_symbols(self) -> None:
        self.assertIn('BreakpointCreateByName("main")', self.text)
        self.assertIn("breakpoint.SetOneShot(True)", self.text)
        for literal in (
            "SwiftUI.SDFStyle.Group.margin.getter",
            "SwiftUI.SDFLayer.updateSDFEffects",
            "-[CABackdropLayer setMarginWidth:]",
            "-[CABackdropLayer _copyRenderLayer:layerFlags:commitFlags:]",
            "CA::Render::BackdropLayer::get_bounds(",
        ):
            self.assertIn(literal, self.text)

    def test_selection_cannot_read_output_evidence(self) -> None:
        for literal in (
            '"capturedMarginUsedForSelection": False',
            '"capturedCropUsedForSelection": False',
            '"capturedImageUsedForSelection": False',
            '"capturedPixelUsedForSelection": False',
        ):
            self.assertIn(literal, self.text)
        callback = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "capture_at_main"
        )
        source = ast.get_source_segment(self.text, callback)
        self.assertIsNotNone(source)
        self.assertNotIn("margin", source.lower())
        self.assertNotIn("crop", source.lower())
        self.assertNotIn("image", source.lower())
        self.assertNotIn("pixel", source.lower())

    def test_records_complete_bounded_code_and_build_identity(self) -> None:
        for literal in (
            "MAXIMUM_SYMBOL_BYTE_COUNT = 0x40000",
            '"moduleOffset"',
            '"codeSHA256"',
            '"hex"',
            "module.GetUUIDString()",
            "process.ReadMemory(",
        ):
            self.assertIn(literal, self.text)


if __name__ == "__main__":
    unittest.main()
