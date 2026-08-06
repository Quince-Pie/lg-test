#!/usr/bin/env python3
"""Static contracts for the case-22 callee instruction-trace overlay."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


SOURCE = Path(__file__).with_name("capture_backdrop_margin_case22_callee_lldb.py")


class BackdropMarginCase22CalleeLLDBSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SOURCE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.text)

    def test_overlay_preserves_the_complete_group_capture(self) -> None:
        self.assertIn(
            "import capture_backdrop_margin_group_execution_lldb as group",
            self.text,
        )
        self.assertIn("group._new_trace = _new_trace", self.text)
        self.assertIn("group.producer_stage = producer_stage", self.text)
        self.assertIn("group.__lldb_init_module(debugger, internal_dict)", self.text)
        self.assertIn("_group_finalize()", self.text)
        self.assertIn("_group_producer_stage(return_frame, None, None)", self.text)

    def test_runtime_selection_is_fixed_ordinal_and_never_an_output(self) -> None:
        self.assertIn("SELECTED_INVOCATION_INDEX = 20", self.text)
        self.assertIn("CASE22_TARGET_MODULE_OFFSET = 0x76BC54", self.text)
        for literal in (
            '"capturedMarginUsedForRuntimeSelection": False',
            '"capturedCropUsedForRuntimeSelection": False',
            '"capturedImageUsedForRuntimeSelection": False',
            '"capturedPixelUsedForRuntimeSelection": False',
        ):
            self.assertIn(literal, self.text)
        function = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "producer_stage"
        )
        source = ast.get_source_segment(self.text, function)
        self.assertIsNotNone(source)
        self.assertNotIn("returnF64", source)
        self.assertNotIn("marginF64", source)
        self.assertNotIn("pixel", source.lower())

    def test_trace_is_bounded_and_captures_exact_machine_state(self) -> None:
        for literal in (
            "OBJECT_BYTE_COUNT = 0x1000",
            "STACK_BYTE_COUNT = 0x400",
            "MAXIMUM_INSTRUCTION_COUNT = 8192",
            "MAXIMUM_OPAQUE_CALLEE_COUNT = 512",
            "MAXIMUM_SYMBOL_BYTE_COUNT = 0x20000",
            "def _full_register_snapshot(",
            "thread.StepInstruction(False, error)",
            "thread.StepOut(error)",
            "def _capture_pointer_probes(",
            "def _capture_symbol(",
        ):
            self.assertIn(literal, self.text)
        self.assertIn('"instructionStates": []', self.text)
        self.assertIn('"opaqueCallees": []', self.text)
        self.assertIn('"executionEvents": []', self.text)

    def test_return_breakpoint_is_restored_after_manual_trace(self) -> None:
        function = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_trace_case22"
        )
        source = ast.get_source_segment(self.text, function)
        self.assertIsNotNone(source)
        self.assertIn("return_breakpoint.SetEnabled(False)", source)
        self.assertIn("finally:", source)
        self.assertIn("return_breakpoint.SetEnabled(return_was_enabled)", source)
        self.assertIn("group_return_pc + 4", source)


if __name__ == "__main__":
    unittest.main()
