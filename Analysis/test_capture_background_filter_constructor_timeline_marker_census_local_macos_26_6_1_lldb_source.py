#!/usr/bin/env python3
"""Source contracts for the live producer-boundary census."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "capture_background_filter_constructor_timeline_marker_census_local_macos_26_6_1_lldb.py"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


class ConstructorTimelineMarkerCensusSourceTests(unittest.TestCase):
    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(SOURCE, feature_version=(3, 9))

    def test_direct_callsites_are_authenticated_before_breakpoints(self) -> None:
        self.assertIn("_decode_direct_branch_target", SOURCE)
        self.assertIn("CONSTRUCTOR_CALL_INSTRUCTION_HEX", SOURCE)
        self.assertIn("RESOLVED_RECIPE_BUILDER_CALL_INSTRUCTION_HEX", SOURCE)
        self.assertIn("CONSTRUCTOR_CODE_SHA256", SOURCE)
        self.assertIn("RESOLVED_RECIPE_BUILDER_CODE_SHA256", SOURCE)

    def test_capture_window_uses_only_marker_ordinals(self) -> None:
        self.assertIn("if marker_index == 0:", SOURCE)
        self.assertIn("marker_index == live.TIMELINE_MARKER_COUNT - 1", SOURCE)
        self.assertIn("_set_entry_capture_enabled(True)", SOURCE)
        self.assertIn("_set_entry_capture_enabled(False)", SOURCE)

    def test_census_does_not_read_values(self) -> None:
        for contract in (
            '"capturedParametersUsedForCensusSelection": False',
            '"capturedBackgroundFilterUsedForCensusSelection": False',
            '"capturedProviderObjectUsedForCensusSelection": False',
            '"capturedRegisterArgumentUsedForCensusSelection": False',
            '"capturedAddressValueUsedForCensusSelection": False',
            '"capturedImageUsedForCensusSelection": False',
            '"capturedPixelUsedForCensusSelection": False',
        ):
            self.assertIn(contract, SOURCE)
        for forbidden in (
            "parametersAtEntry",
            "outputAtReturn",
            "outputParametersAtReturn",
            "_register_u64(frame, \"x0\")",
            "_register_u64(frame, \"x8\")",
        ):
            self.assertNotIn(forbidden, SOURCE)

    def test_all_live_callbacks_are_reexported(self) -> None:
        self.assertIn('__name__ + "." + callback', SOURCE)
        for callback in (
            "timeline_marker",
            "selected_callsite",
            "wrapper_entry",
            "provider_entry",
            "provider_return",
            "group_return",
            "selected_caller_return",
            "constructor_callsite",
            "constructor_return",
            "parameters_builder_callsite",
            "parameters_builder_return",
        ):
            self.assertIn(f"def {callback}(", SOURCE)

    def test_census_events_are_separate_from_frozen_provider_events(self) -> None:
        self.assertIn('trace["constructorCensusEvents"] = []', SOURCE)
        self.assertIn('trace["constructorCensusBreakpoints"] = []', SOURCE)
        self.assertNotIn(
            'trace["timelineEvents"].append',
            SOURCE,
        )


if __name__ == "__main__":
    unittest.main()
