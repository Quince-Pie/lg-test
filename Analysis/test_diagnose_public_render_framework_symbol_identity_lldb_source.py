#!/usr/bin/env python3
"""Static contracts for the framework-symbol identity diagnostic."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "diagnose_public_render_framework_symbol_identity_lldb.py"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


class PublicRenderFrameworkIdentityDiagnosticSourceTests(unittest.TestCase):
    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(SOURCE, feature_version=(3, 9))

    def test_both_framework_symbols_and_complete_identities_are_recorded(self) -> None:
        for field in (
            "PROVIDER_CODE_SHA256",
            "PROVIDER_MODULE_OFFSET",
            "PROVIDER_BYTE_COUNT",
            "WRAPPER_CODE_SHA256",
            "WRAPPER_MODULE_OFFSET",
            "WRAPPER_BYTE_COUNT",
        ):
            self.assertIn(field, SOURCE)
        self.assertIn('value.pop("hex", None)', SOURCE)

    def test_diagnostic_is_one_shot_and_value_blind(self) -> None:
        self.assertIn("_breakpoint.SetEnabled(False)", SOURCE)
        self.assertNotIn("inputShadowAmount", SOURCE)
        self.assertNotIn("inputBlurRadius", SOURCE)
        self.assertNotIn("capturedPixel", SOURCE)


if __name__ == "__main__":
    unittest.main()
