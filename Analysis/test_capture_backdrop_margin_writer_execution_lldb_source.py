"""Static contract tests for the LLDB writer-chain adapter."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


SOURCE = Path(__file__).with_name(
    "capture_backdrop_margin_writer_execution_lldb.py"
)


class BackdropMarginWriterExecutionLLDBSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SOURCE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.text)

    def test_source_is_valid_python(self) -> None:
        self.assertIsInstance(self.tree, ast.Module)

    def test_all_three_structural_symbols_are_breakpointed(self) -> None:
        self.assertIn(
            "-[CABackdropLayer setMarginWidth:]", self.text
        )
        self.assertIn(
            "-[CABackdropLayer _copyRenderLayer:layerFlags:commitFlags:]",
            self.text,
        )
        self.assertIn(
            "CA::Render::BackdropLayer::get_bounds(", self.text
        )
        self.assertEqual(self.text.count("_install_named_breakpoint("), 4)

    def test_copy_store_is_fixed_by_exact_code_offset(self) -> None:
        self.assertIn("COPY_MARGIN_STORE_OFFSET = 948", self.text)
        self.assertIn(
            'COPY_MARGIN_STORE_INSTRUCTION_HEX = "a02600bd"', self.text
        )
        self.assertIn("BreakpointCreateByAddress(address)", self.text)

    def test_callbacks_never_select_by_captured_value(self) -> None:
        for literal in (
            '"capturedMarginUsedForSelection": False',
            '"capturedCropUsedForSelection": False',
            '"capturedImageUsedForSelection": False',
        ):
            self.assertIn(literal, self.text)
        callbacks = {
            node.name: node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef)
        }
        for name in (
            "copy_entry",
            "copy_margin_store",
            "margin_setter",
            "backdrop_bounds",
        ):
            returns = [
                node
                for node in ast.walk(callbacks[name])
                if isinstance(node, ast.Return)
            ]
            self.assertTrue(
                any(
                    isinstance(node.value, ast.Constant)
                    and node.value.value is False
                    for node in returns
                ),
                name,
            )

    def test_trace_is_bounded(self) -> None:
        self.assertIn("MAXIMUM_EVENT_COUNT = 8192", self.text)
        self.assertIn("MAXIMUM_CALLER_COUNT = 64", self.text)
        self.assertIn("MAXIMUM_TOTAL_CALLER_BYTE_COUNT = 2 * 1024 * 1024", self.text)


if __name__ == "__main__":
    unittest.main()
