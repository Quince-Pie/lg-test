#!/usr/bin/env python3
"""Static contracts for the constructor/public-render LLDB adapter."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "capture_background_filter_constructor_public_render_interval_local_macos_26_6_1_lldb.py"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


class BackgroundFilterConstructorCaptureSourceTests(unittest.TestCase):
    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(SOURCE, feature_version=(3, 9))

    def test_exact_constructor_and_producer_are_frozen(self) -> None:
        for value in (
            'CONSTRUCTOR_MODULE_OFFSET = 0xBAD00',
            'CONSTRUCTOR_BYTE_COUNT = 0x414',
            "71a592bc8a187fe8bcca0fa50c3f4d36ea3c2916dbd5d16f3fa1df05b86f131d",
            'PRODUCER_MODULE_OFFSET = 0xB7FA8',
            'PRODUCER_BYTE_COUNT = 0x66C',
            "0729f7b0f874c0fb9fb64fa3383a6f2ed328d1dc55fdce53b82038a188df6f97",
            'CONSTRUCTOR_CALL_INSTRUCTION_HEX = "730a0094"',
            'CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER = 0x38C',
            'CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER = 0x390',
        ):
            self.assertIn(value, SOURCE)

    def test_complete_input_output_and_provider_values_are_retained(self) -> None:
        for value in (
            'PARAMETERS_BYTE_COUNT = 0x401',
            'BACKGROUND_FILTER_BYTE_COUNT = 0x1F8',
            'parameters_address = base._register_u64(frame, "x0")',
            'layer_index = base._register_u64(frame, "x1")',
            'flags_raw_value = base._register_u64(frame, "x2")',
            'output_address = base._register_u64(frame, "x8")',
            '"parametersAtEntry": case22._snapshot(',
            '"outputAtReturn"] = output',
            'call["providerObjectComplete"] = case22._snapshot(',
            'call["returnObjectComplete"] = returned',
        ):
            self.assertIn(value, SOURCE)

    def test_constructor_capture_spans_pre_render_construction(self) -> None:
        install = SOURCE.index("def _install_capture(")
        render_call = SOURCE.index("def render_call(")
        render_return = SOURCE.index("def render_return(")
        self.assertIn(
            '"constructor_entry"', SOURCE[install:render_call]
        )
        self.assertIn(
            '_assign_pre_render_calls(interval)',
            SOURCE[render_call:render_return],
        )
        self.assertIn(
            '_constructor_state["entryBreakpoint"].SetEnabled(False)',
            SOURCE[render_return:],
        )

    def test_assignment_uses_only_structural_event_order(self) -> None:
        for value in (
            '"preRenderConstructorCallIndices"',
            '"inRenderConstructorCallIndices"',
            '"timingRelativeToRender"] = "pre-render"',
            '"structuralNextSampleIndexAtEntry"',
        ):
            self.assertIn(value, SOURCE)
        self.assertNotIn("if output[", SOURCE)
        self.assertNotIn("if parameters[", SOURCE)

    def test_no_captured_value_selects_runtime_capture(self) -> None:
        for field in (
            "capturedParametersUsedForSelection",
            "capturedConstructorOutputUsedForSelection",
            "capturedProviderObjectUsedForSelection",
            "capturedAddressUsedForSelection",
        ):
            self.assertIn(f'"{field}": False', SOURCE)

    def test_parent_callbacks_are_replaced_before_parent_initialization(self) -> None:
        initialization = SOURCE.index("def __lldb_init_module(")
        tail = SOURCE[initialization:]
        for assignment in (
            "public._new_trace = _new_trace",
            "public._install_capture = _install_capture",
            "public.render_call = render_call",
            "public.render_return = render_return",
            "public.provider_entry = provider_entry",
            "public.provider_return = provider_return",
        ):
            self.assertIn(assignment, tail)
        self.assertLess(
            tail.index("public._install_capture = _install_capture"),
            tail.index("public.__lldb_init_module(debugger, internal_dict)"),
        )


if __name__ == "__main__":
    unittest.main()
