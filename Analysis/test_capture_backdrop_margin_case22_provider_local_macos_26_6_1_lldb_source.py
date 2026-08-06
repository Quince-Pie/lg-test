#!/usr/bin/env python3
"""Source checks for the frozen local DesignLibrary provider trace."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


SOURCE = Path(__file__).with_name(
    "capture_backdrop_margin_case22_provider_local_macos_26_6_1_lldb.py"
)


class LocalMacOSCase22ProviderSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SOURCE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.text)

    def test_exact_opened_provider_identity_is_embedded(self) -> None:
        for literal in (
            'DESIGN_LIBRARY_UUID = "1E980802-69F5-3E69-89EF-50088297FCF5"',
            "THUNK_MODULE_OFFSET = 0xB7F4C",
            'THUNK_INSTRUCTION_HEX = "5afcff17"',
            "PROVIDER_MODULE_OFFSET = 0xB70B4",
            "PROVIDER_BYTE_COUNT = 984",
            '"a76c6f0b03cc6b64c6b040220f495c5f22d7e1e5322efb3cb139554dd397c10b"',
            "HELPER_MODULE_OFFSET = 0xC682C",
            "HELPER_BYTE_COUNT = 276",
            '"f58da9879a4b367144e8acaf1ad099161b3e27f00e0769dd4fa6e18e9ef9edc1"',
        ):
            self.assertIn(literal, self.text)

    def test_provider_trace_is_nested_inside_the_frozen_case22_trace(self) -> None:
        self.assertIn("local.trace_selected_case22()", self.text)
        self.assertIn("local.finalize()", self.text)
        self.assertIn(
            "case22._capture_opaque_callee = _capture_provider_dispatch",
            self.text,
        )
        function = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_capture_provider_dispatch"
        )
        source = ast.get_source_segment(self.text, function)
        self.assertIsNotNone(source)
        self.assertIn("_case22_capture_opaque_callee(", source)
        self.assertIn("_trace_provider(", source)
        self.assertIn('"kind": "opaque-callee"', source)

    def test_callbacks_bind_to_the_directly_imported_provider_module(self) -> None:
        self.assertIn("local._set_local_callback = _set_provider_callback", self.text)
        for callback in (
            "copy_entry",
            "margin_setter",
            "copy_margin_store",
            "backdrop_bounds",
            "producer_entry",
            "producer_stage",
        ):
            function = next(
                node
                for node in self.tree.body
                if isinstance(node, ast.FunctionDef) and node.name == callback
            )
            source = ast.get_source_segment(self.text, function)
            self.assertIsNotNone(source)
            self.assertIn("return local.", source)

    def test_live_trace_is_bounded_and_complete(self) -> None:
        function = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_trace_provider"
        )
        source = ast.get_source_segment(self.text, function)
        self.assertIsNotNone(source)
        self.assertIn("MAXIMUM_PROVIDER_INSTRUCTION_COUNT", source)
        self.assertIn("_capture_provider_instruction(", source)
        self.assertIn("_capture_provider_helper(", source)
        self.assertIn('extension["status"] = "provider-trace-closed"', source)

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
        for forbidden in ("margin", "crop", "image", "pixel"):
            self.assertNotIn(forbidden, source.lower())


if __name__ == "__main__":
    unittest.main()
