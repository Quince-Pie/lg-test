#!/usr/bin/env python3
"""Static contracts for the main-symbol presentation diagnostic."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "diagnose_public_render_main_symbol_identity_lldb.py"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


class PublicRenderMainSymbolIdentityDiagnosticSourceTests(unittest.TestCase):
    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(SOURCE, feature_version=(3, 9))

    def test_exact_binary_identity_is_recorded_without_code_payload_duplication(self) -> None:
        for field in (
            '"codeSHA256"',
            '"moduleOffset"',
            '"symbolByteCount"',
            '"mainModule"',
        ):
            self.assertIn(field, SOURCE)
        self.assertIn('value.pop("hex", None)', SOURCE)

    def test_diagnostic_is_one_shot_and_never_selects_a_render_value(self) -> None:
        self.assertIn("_breakpoint.SetEnabled(False)", SOURCE)
        self.assertNotIn("inputShadowAmount", SOURCE)
        self.assertNotIn("inputBlurRadius", SOURCE)
        self.assertNotIn("capturedPixel", SOURCE)


if __name__ == "__main__":
    unittest.main()
