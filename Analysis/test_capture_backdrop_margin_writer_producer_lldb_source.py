"""Static contracts for the immutable-base producer-capture overlay."""

from __future__ import annotations

import ast
import hashlib
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
SOURCE = ANALYSIS / "capture_backdrop_margin_writer_producer_lldb.py"
BASE = ANALYSIS / "capture_backdrop_margin_writer_execution_lldb.py"
BASE_SHA256 = "f91ba6afb61b491d949ea5dc9d4fc1c82c165e0016aefa84db00a0b15d435ecd"


class BackdropMarginWriterProducerLLDBSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SOURCE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.text)

    def test_frozen_base_is_unchanged(self) -> None:
        self.assertEqual(hashlib.sha256(BASE.read_bytes()).hexdigest(), BASE_SHA256)
        self.assertIn(
            "import capture_backdrop_margin_writer_execution_lldb as base",
            self.text,
        )
        self.assertIn(f'BASE_CAPTURE_SHA256 = "{BASE_SHA256}"', self.text)

    def test_producer_selection_is_exact_code_shape_only(self) -> None:
        for literal in (
            "SETTER_CALL_FROM_RETURN_PC = -4",
            "PRODUCER_BRIDGE_FROM_RETURN_PC = -8",
            "PRODUCER_CALL_FROM_RETURN_PC = -12",
            'PRODUCER_BRIDGE_INSTRUCTION_HEX = "e0031caa"',
            '"producerSelectedByCapturedMargin": False',
            '"capturedMarginUsedForSelection": False',
        ):
            self.assertIn(literal, self.text)
        self.assertIn("def _decode_bl_target(", self.text)
        self.assertIn("def _capture_producer_code(", self.text)
        self.assertIn("def _capture_producer_invocation(", self.text)

    def test_overlay_proxies_every_inherited_lldb_callback(self) -> None:
        self.assertIn("base._new_trace = _new_trace", self.text)
        self.assertIn("base.__lldb_init_module(debugger, internal_dict)", self.text)
        self.assertIn("def _install_callback_proxies(", self.text)
        self.assertIn('SetScriptCallbackFunction(__name__ + "." + callback)', self.text)
        for callback in (
            "copy_entry",
            "margin_setter",
            "copy_margin_store",
            "backdrop_bounds",
        ):
            self.assertIn(f"def {callback}(", self.text)
        self.assertNotIn("BreakpointCreate", self.text)
        callbacks = {
            node.name: node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef)
        }
        returns = [
            node
            for node in ast.walk(callbacks["margin_setter"])
            if isinstance(node, ast.Return)
        ]
        self.assertTrue(
            any(
                isinstance(node.value, ast.Constant) and node.value.value is False
                for node in returns
            )
        )

    def test_capture_is_bounded_and_finalized(self) -> None:
        self.assertIn("MAXIMUM_PRODUCER_COUNT = 64", self.text)
        self.assertIn("MAXIMUM_PRODUCER_BYTE_COUNT = 131072", self.text)
        self.assertIn(
            "MAXIMUM_TOTAL_PRODUCER_BYTE_COUNT = 2 * 1024 * 1024",
            self.text,
        )
        self.assertIn("PRODUCER_SELF_SNAPSHOT_BYTE_COUNT = 0x60", self.text)
        self.assertIn('trace["finalProducerCalleeCount"]', self.text)
        self.assertIn('trace["finalProducerCalleeCodeByteCount"]', self.text)


if __name__ == "__main__":
    unittest.main()
