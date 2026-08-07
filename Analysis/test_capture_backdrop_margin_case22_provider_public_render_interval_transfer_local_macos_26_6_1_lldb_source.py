#!/usr/bin/env python3
"""Static contracts for the public-render/provider LLDB adapter."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "capture_backdrop_margin_case22_provider_public_render_interval_transfer_local_macos_26_6_1_lldb.py"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


class PublicRenderIntervalCaptureSourceTests(unittest.TestCase):
    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(SOURCE, feature_version=(3, 9))

    def test_exact_binary_and_direct_call_are_frozen(self) -> None:
        for value in (
            "F8B0B6E3-3270-3C94-817F-B4914852D04C",
            "1ca54720d237eb6970b65dd2ecc88b8372b64667f4ea2d28ef4bc8414668e2fd",
            "0c661f1010199a56e6730d897079fda69fc4a267f7f48d1e2054b14ff9270e0c",
            'RENDER_CALL_OFFSET = 0x1000',
            'RENDER_RETURN_OFFSET = 0x1004',
            'RENDER_CALL_INSTRUCTION_HEX = "dfcfff97"',
        ):
            self.assertIn(value, SOURCE)

    def test_demangled_presentation_cannot_override_exact_binary_identity(self) -> None:
        self.assertNotIn('record.get("function") != function', SOURCE)
        self.assertIn('not isinstance(record.get("function"), str)', SOURCE)
        self.assertIn('record.get("codeSHA256") != digest', SOURCE)
        self.assertIn('record.get("symbolByteCount") != byte_count', SOURCE)

    def test_framework_identity_does_not_inherit_a_stale_transitive_uuid(self) -> None:
        self.assertIn("def _capture_framework_symbol(", SOURCE)
        self.assertNotIn("field._capture_wrapper(process, swift_module)", SOURCE)
        self.assertNotIn("field._capture_provider(process, design_module)", SOURCE)
        for field in (
            "field.WRAPPER_MODULE_OFFSET",
            "field.WRAPPER_BYTE_COUNT",
            "field.WRAPPER_CODE_SHA256",
            "field.PROVIDER_MODULE_OFFSET",
            "field.PROVIDER_BYTE_COUNT",
            "field.PROVIDER_CODE_SHA256",
        ):
            self.assertIn(field, SOURCE)
        self.assertIn('record_module.get("loadAddress") != module["loadAddress"]', SOURCE)
        self.assertIn('.endswith(path_suffix)', SOURCE)

    def test_callbacks_are_bound_to_this_directly_imported_module(self) -> None:
        self.assertIn(
            'breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)',
            SOURCE,
        )
        self.assertNotIn("field._set_callback(", SOURCE)
        for callback in (
            '"bootstrap"',
            '"render_call"',
            '"render_return"',
            '"provider_entry"',
            '"provider_return"',
        ):
            self.assertIn(callback, SOURCE)

    def test_render_call_and_return_structurally_gate_provider_capture(self) -> None:
        call = SOURCE.index("def render_call(")
        returned = SOURCE.index("def render_return(")
        entry = SOURCE.index("def provider_entry(")
        self.assertIn(
            '_state["providerBreakpoint"].SetEnabled(True)',
            SOURCE[call:returned],
        )
        self.assertIn(
            '_state["providerBreakpoint"].SetEnabled(False)',
            SOURCE[returned:entry],
        )
        self.assertIn(
            'if _state["pendingCalls"]:',
            SOURCE[returned:entry],
        )

    def test_no_captured_value_can_select_an_interval_or_call(self) -> None:
        for field in (
            "capturedObjectUsedForSelection",
            "capturedReturnUsedForSelection",
            "capturedPublicInputUsedForSelection",
            "capturedMarginUsedForSelection",
            "capturedCropUsedForSelection",
            "capturedImageUsedForSelection",
            "capturedPixelUsedForSelection",
        ):
            self.assertIn(f'"{field}": False', SOURCE)
        self.assertNotIn("inputShadowAmount", SOURCE)
        self.assertNotIn("inputBlurRadius", SOURCE)

    def test_objects_and_returns_are_captured_without_mutation(self) -> None:
        for needle in (
            'object_address = base._register_u64(frame, "x20")',
            '"providerObject": case22._snapshot(',
            'v0 = base._register_bytes(frame, "v0")',
            '"objectChanged"',
            'trace["finalPendingCallCount"]',
            'trace["allIntervalsClosed"]',
        ):
            self.assertIn(needle, SOURCE)


if __name__ == "__main__":
    unittest.main()
