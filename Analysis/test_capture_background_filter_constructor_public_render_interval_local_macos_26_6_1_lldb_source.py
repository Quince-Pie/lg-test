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
            "CONSTRUCTOR_MODULE_OFFSET = 0xBAD00",
            "CONSTRUCTOR_BYTE_COUNT = 0x414",
            "71a592bc8a187fe8bcca0fa50c3f4d36ea3c2916dbd5d16f3fa1df05b86f131d",
            "PRODUCER_MODULE_OFFSET = 0xB7FA8",
            "PRODUCER_BYTE_COUNT = 0x66C",
            "0729f7b0f874c0fb9fb64fa3383a6f2ed328d1dc55fdce53b82038a188df6f97",
            'CONSTRUCTOR_CALL_INSTRUCTION_HEX = "730a0094"',
            "CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER = 0x38C",
            "CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER = 0x390",
        ):
            self.assertIn(value, SOURCE)

    def test_exact_parameters_builder_and_caller_are_frozen(self) -> None:
        for value in (
            "TRACE_SCHEMA_VERSION = 2",
            "RESOLVED_RECIPE_BUILDER_MODULE_OFFSET = 0x120B4C",
            "RESOLVED_RECIPE_BUILDER_BYTE_COUNT = 0x1334",
            "07d9b8571ca8fed42e1d8e71b312f00a9c9713ce19f406d6f2c15a9d2403fde4",
            "RESOLVED_RECIPE_BUILDER_CALLER_MODULE_OFFSET = 0x11F1BC",
            "RESOLVED_RECIPE_BUILDER_CALLER_BYTE_COUNT = 0xD7C",
            "ba0ad1081cece802ccd1e148660a542145f95bf57a92de4407a3fad55f4679c6",
            'RESOLVED_RECIPE_BUILDER_CALL_INSTRUCTION_HEX = "17030094"',
            "RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER = 0xD34",
            "RESOLVED_RECIPE_BUILDER_RETURN_OFFSET_IN_CALLER = 0xD38",
            "BLEND_DECISION_OFFSET_IN_BUILDER = 0xFB8",
            "BLEND_FINAL_GATE_OFFSET_IN_BUILDER = 0x1174",
            "BLEND_RESOLVED_OFFSET_IN_BUILDER = 0x118C",
        ):
            self.assertIn(value, SOURCE)

    def test_complete_input_output_and_provider_values_are_retained(self) -> None:
        for value in (
            "PARAMETERS_BYTE_COUNT = 0x401",
            "BACKGROUND_FILTER_BYTE_COUNT = 0x1F8",
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
        self.assertIn('"constructor_entry"', SOURCE[install:render_call])
        self.assertIn(
            "_assign_pre_render_calls(interval)",
            SOURCE[render_call:render_return],
        )
        self.assertIn(
            '_constructor_state["entryBreakpoint"].SetEnabled(False)',
            SOURCE[render_return:],
        )

    def test_parameters_builder_capture_retains_every_fixed_boundary(self) -> None:
        install = SOURCE.index("def _install_capture(")
        render_call = SOURCE.index("def render_call(")
        render_return = SOURCE.index("def render_return(")
        for callback in (
            '"parameters_builder_entry"',
            '"parameters_blend_decision"',
            '"parameters_blend_final"',
            '"parameters_blend_resolved"',
            '"parameters_builder_return"',
        ):
            self.assertIn(callback, SOURCE[install:render_call])
        self.assertIn(
            "_assign_pre_render_builder_calls(interval)",
            SOURCE[render_call:render_return],
        )
        for key in (
            '"builderEntryBreakpoint"',
            '"blendDecisionBreakpoint"',
            '"blendFinalBreakpoint"',
            '"blendResolvedBreakpoint"',
            '"builderReturnBreakpoint"',
        ):
            self.assertIn(key, SOURCE[render_return:])

    def test_parameters_blend_inputs_and_outputs_are_complete(self) -> None:
        for value in (
            "BUILDER_FRAME_PARAMETERS_OFFSET = 0x1068",
            "BUILDER_FRAME_ACCUMULATOR_OFFSET = 0x1900",
            "BUILDER_FRAME_WORKING_PARAMETERS_OFFSET = 0xC60",
            "BUILDER_FRAME_COLLECTION_COUNT_OFFSET = 0xB0",
            "BUILDER_FRAME_RESOLVER_FLAG_OFFSET = 0x7C",
            "ANIMATABLE_DATA_BYTE_COUNT = 0x481",
            '"factorD9": _register_record(frame, "d9")',
            '"unityD12": _register_record(frame, "d12")',
            '"currentParameters": case22._snapshot(',
            '"priorAccumulatorAnimatableData": case22._snapshot(',
            'call["preResolverWorkingParameters"] = case22._snapshot(',
            'call["accumulatorAnimatableDataAtFinalGate"] = case22._snapshot(',
            'call["resolvedWorkingParameters"] = case22._snapshot(',
            'call["outputParametersAtReturn"] = case22._snapshot(',
        ):
            self.assertIn(value, SOURCE)

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
            "capturedBlendFactorUsedForSelection",
            "capturedBlendCountUsedForSelection",
            "capturedAnimatableDataUsedForSelection",
            "capturedBuilderOutputUsedForSelection",
        ):
            self.assertIn(f'"{field}": False', SOURCE)

    def test_captured_blend_values_do_not_control_capture(self) -> None:
        decision = SOURCE[SOURCE.index("def parameters_blend_decision(") :]
        decision = decision[: decision.index("def parameters_blend_final(")]
        for forbidden in (
            "if collection_count",
            "if factor",
            "if decision[",
            "if current",
        ):
            self.assertNotIn(forbidden, decision)

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
