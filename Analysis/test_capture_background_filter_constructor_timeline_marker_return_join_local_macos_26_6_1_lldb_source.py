#!/usr/bin/env python3
"""Source contracts for the immediate constructor-return overlay."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "capture_background_filter_constructor_timeline_marker_return_join_local_macos_26_6_1_lldb.py"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


class ConstructorReturnCaptureSourceTests(unittest.TestCase):
    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(SOURCE, feature_version=(3, 9))

    def test_exact_five_stop_sequence_is_frozen(self) -> None:
        self.assertIn('"stopsPerSelectedChain": 5', SOURCE)
        for event in (
            '"parameters-builder-call"',
            '"parameters-builder-return"',
            '"constructor-call"',
            '"constructor-return"',
            '"provider-entry"',
        ):
            self.assertIn(event, SOURCE)

    def test_constructor_output_is_read_only_at_immediate_return(self) -> None:
        self.assertIn("CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER", SOURCE)
        self.assertIn('call["constructorOutputAtReturn"] = case22._snapshot(', SOURCE)
        self.assertIn('call["constructorOutputAtProviderEntry"] = None', SOURCE)
        self.assertIn('"constructorOutputAtProviderEntryUsedForJoin": False', SOURCE)
        self.assertIn('"capturedConstructorReturnValueUsedForSelection": False', SOURCE)

    def test_provider_is_armed_only_after_constructor_return(self) -> None:
        return_function = SOURCE.index("def constructor_return(")
        provider_enable = SOURCE.index(
            'direct._state["providerEntryBreakpoint"].SetEnabled(True)',
            return_function,
        )
        provider_function = SOURCE.index("def provider_entry(", provider_enable)
        self.assertLess(return_function, provider_enable)
        self.assertLess(provider_enable, provider_function)
        self.assertIn('call.get("stage") != "constructor-returned"', SOURCE)

    def test_direct_capture_callbacks_are_reexported(self) -> None:
        self.assertIn('__name__ + "." + callback', SOURCE)
        for callback in (
            "timeline_marker",
            "parameters_builder_callsite",
            "parameters_builder_return",
            "constructor_callsite",
            "constructor_return",
            "provider_entry",
        ):
            self.assertIn(f"def {callback}(", SOURCE)


if __name__ == "__main__":
    unittest.main()
