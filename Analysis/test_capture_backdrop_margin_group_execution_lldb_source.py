"""Static contracts for the bounded Group.margin execution overlay."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


SOURCE = Path(__file__).with_name("capture_backdrop_margin_group_execution_lldb.py")


class BackdropMarginGroupExecutionLLDBSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SOURCE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.text)

    def test_overlay_preserves_both_inherited_capture_layers(self) -> None:
        self.assertIn(
            "import capture_backdrop_margin_writer_producer_lldb as writer",
            self.text,
        )
        self.assertIn("writer._new_trace = _new_trace", self.text)
        self.assertIn("writer.__lldb_init_module(debugger, internal_dict)", self.text)
        self.assertIn("_writer_finalize()", self.text)
        for callback in (
            "copy_entry",
            "margin_setter",
            "copy_margin_store",
            "backdrop_bounds",
        ):
            self.assertIn(f"def {callback}(", self.text)

    def test_selection_is_exact_caller_code_and_never_a_value(self) -> None:
        self.assertIn("CALLER_RETURN_AFTER_PRODUCER_OFFSET = 5764", self.text)
        self.assertIn('"selectedByCapturedMargin": False', self.text)
        for literal in (
            '"capturedMarginUsedForSelection": False',
            '"capturedCropUsedForSelection": False',
            '"capturedImageUsedForSelection": False',
            '"capturedPixelUsedForSelection": False',
        ):
            self.assertIn(literal, self.text)
        selected = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_selected_caller"
        )
        selected_text = ast.get_source_segment(self.text, selected)
        self.assertIsNotNone(selected_text)
        self.assertNotIn("margin", selected_text.lower())
        self.assertNotIn("pixel", selected_text.lower())

    def test_capture_is_bounded_and_retains_every_required_operand_class(self) -> None:
        for literal in (
            "MAXIMUM_COLLECTION_COUNT = 64",
            "MAXIMUM_TAG2_VALUE_COUNT = 256",
            "MAXIMUM_INVOCATION_COUNT = 512",
            "MAXIMUM_STAGE_COUNT = 8192",
            '"bridged-0x80"',
            "GROUP_RECORD_BYTE_COUNT = 0x80",
            "SIDE_ENTRY_BYTE_COUNT = 0x38",
            "SIDE_PAYLOAD_BYTE_COUNT = 0x80",
            "def _capture_group_value(",
            "def _capture_tagged_payloads(",
            "def _capture_direct_calls(",
            "def producer_stage(",
        ):
            self.assertIn(literal, self.text)
        self.assertEqual(
            set(
                offset.value
                for node in self.tree.body
                if isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "STAGE_INSTRUCTIONS"
                    for target in node.targets
                )
                for offset in node.value.keys
                if isinstance(offset, ast.Constant)
            ),
            {
                0x0BC,
                0x0D8,
                0x148,
                0x16C,
                0x184,
                0x1F8,
                0x20C,
                0x268,
                0x26C,
                0x278,
                0x2B0,
            },
        )

    def test_lldb_callbacks_always_resume(self) -> None:
        callbacks = {
            node.name: node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef)
        }
        for name in (
            "producer_entry",
            "producer_stage",
            "copy_entry",
            "margin_setter",
            "copy_margin_store",
            "backdrop_bounds",
        ):
            returns = [
                node
                for node in ast.walk(callbacks[name])
                if isinstance(node, ast.Return)
            ]
            self.assertTrue(returns, name)
        for name in ("producer_entry", "producer_stage"):
            returns = [
                node
                for node in ast.walk(callbacks[name])
                if isinstance(node, ast.Return)
            ]
            self.assertTrue(
                any(
                    isinstance(node.value, ast.Constant) and node.value.value is False
                    for node in returns
                ),
                name,
            )


if __name__ == "__main__":
    unittest.main()
