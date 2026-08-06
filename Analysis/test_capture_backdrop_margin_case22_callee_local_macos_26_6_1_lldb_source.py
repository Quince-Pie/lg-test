#!/usr/bin/env python3
"""Static contracts for the exact macOS 26.6.1 case-22 host overlay."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


SOURCE = Path(__file__).with_name(
    "capture_backdrop_margin_case22_callee_local_macos_26_6_1_lldb.py"
)


class LocalMacOSCase22LLDBSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SOURCE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.text)

    def test_preserves_the_frozen_case22_adapter(self) -> None:
        self.assertIn(
            "import capture_backdrop_margin_case22_callee_lldb as case22",
            self.text,
        )
        self.assertIn("case22._new_trace = _new_trace", self.text)
        self.assertIn("case22.__lldb_init_module(debugger, internal_dict)", self.text)
        self.assertIn("case22.finalize()", self.text)
        self.assertIn("group._set_callback = _set_local_callback", self.text)
        self.assertIn("case22._selected_thread = _selected_thread", self.text)
        for callback in (
            "copy_entry",
            "margin_setter",
            "copy_margin_store",
            "backdrop_bounds",
            "producer_entry",
            "producer_stage",
        ):
            self.assertIn(f"def {callback}(", self.text)
        for literal in (
            "case22.CASE22_CALL_OFFSET, 0x268",
            "case22.CASE22_RETURN_OFFSET, 0x26C",
            'case22.CASE22_INSTRUCTION_HEX, "910b3fd7"',
            "base.COPY_MARGIN_STORE_OFFSET, 0x3B4",
            'base.COPY_MARGIN_STORE_INSTRUCTION_HEX, "a02600bd"',
            "base.RENDER_MARGIN_OFFSET, 0x24",
        ):
            self.assertIn(literal, self.text)

    def test_substitutes_only_opened_host_identity(self) -> None:
        for literal in (
            'LOCAL_SWIFTUICORE_UUID = "99606D45-C40A-3C69-AE51-5F0C4E32E531"',
            'LOCAL_QUARTZCORE_UUID = "F1BA3189-E95A-3ECA-B59A-5A6872754484"',
            "base.QUARTZCORE_UUID = LOCAL_QUARTZCORE_UUID",
            "base.COPY_CODE_SHA256 = LOCAL_COPY_CODE_SHA256",
            "base.SETTER_CODE_SHA256 = LOCAL_SETTER_CODE_SHA256",
            "base.BOUNDS_CODE_SHA256 = LOCAL_BOUNDS_CODE_SHA256",
            "group.SWIFTUICORE_UUID = LOCAL_SWIFTUICORE_UUID",
        ):
            self.assertIn(literal, self.text)

    def test_thread_reacquisition_requires_exact_process_and_thread(self) -> None:
        function = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_selected_thread"
        )
        source = ast.get_source_segment(self.text, function)
        self.assertIsNotNone(source)
        self.assertIn("_active_callback_threads.get(thread_id)", source)
        self.assertIn("active.GetThreadID() == thread_id", source)
        self.assertIn(
            "active.GetProcess().GetProcessID() == process.GetProcessID()",
            source,
        )
        self.assertIn("debugger.GetSelectedTarget().GetProcess()", source)
        self.assertIn("fresh_process.GetProcessID() != process.GetProcessID()", source)
        self.assertIn("candidate.GetThreadID() == thread_id", source)
        self.assertIn("thread.GetThreadID() != thread_id", source)

        callback = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "producer_stage"
        )
        callback_source = ast.get_source_segment(self.text, callback)
        self.assertIsNotNone(callback_source)
        self.assertIn("_active_callback_threads[thread_id] = thread", callback_source)
        self.assertIn("finally:", callback_source)
        self.assertIn("_active_callback_threads.pop(thread_id, None)", callback_source)

    def test_runtime_selection_remains_output_blind(self) -> None:
        for literal in (
            '"capturedMarginUsedForRuntimeSelection": False',
            '"capturedCropUsedForRuntimeSelection": False',
            '"capturedImageUsedForRuntimeSelection": False',
            '"capturedPixelUsedForRuntimeSelection": False',
        ):
            self.assertIn(literal, self.text)
        initializer = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "__lldb_init_module"
        )
        source = ast.get_source_segment(self.text, initializer)
        self.assertIsNotNone(source)
        self.assertNotIn("margin", source.lower())
        self.assertNotIn("crop", source.lower())
        self.assertNotIn("image", source.lower())
        self.assertNotIn("pixel", source.lower())


if __name__ == "__main__":
    unittest.main()
