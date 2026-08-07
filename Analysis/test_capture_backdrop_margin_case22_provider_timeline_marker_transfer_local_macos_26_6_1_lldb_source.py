#!/usr/bin/env python3
"""Source contracts for the timeline-marker/provider LLDB capture."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "capture_backdrop_margin_case22_provider_timeline_marker_transfer_local_macos_26_6_1_lldb.py"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


class TimelineMarkerCaptureSourceTests(unittest.TestCase):
    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(SOURCE, feature_version=(3, 9))

    def test_exact_marker_symbol_is_authenticated(self) -> None:
        self.assertIn("TIMELINE_MARKER_MODULE_OFFSET = 0x8BE38", SOURCE)
        self.assertIn("TIMELINE_MARKER_BYTE_COUNT = 0x674", SOURCE)
        self.assertIn(
            "f17ee5eb93c3732cfca195760366e9b7107fb5053d4cff519c5de3092a83fc85",
            SOURCE,
        )
        self.assertIn("hashlib.sha256(payload).hexdigest()", SOURCE)
        self.assertIn(
            'record_module.get("loadAddress") != module["loadAddress"]', SOURCE
        )

    def test_provider_capture_is_bounded_by_marker_ordinals_only(self) -> None:
        self.assertIn("if marker_index == 0:", SOURCE)
        self.assertIn(".SetEnabled(True)", SOURCE)
        self.assertIn("marker_index == TIMELINE_MARKER_COUNT - 1", SOURCE)
        self.assertIn(".SetEnabled(False)", SOURCE)
        self.assertIn('"markerOrdinalUsedForSampleSelection": True', SOURCE)
        self.assertIn('"capturedPublicInputUsedForSelection": False', SOURCE)
        self.assertIn('"capturedTimelineStateUsedForSelection": False', SOURCE)

    def test_every_call_has_ordered_entry_and_completion_events(self) -> None:
        self.assertIn('"provider-call-entry"', SOURCE)
        self.assertIn('"provider-call-complete"', SOURCE)
        self.assertIn('"precedingCompletedCallStartIndex"', SOURCE)
        self.assertIn('"precedingCompletedCallEndIndexExclusive"', SOURCE)
        self.assertIn('minimal._state["pendingByThread"]', SOURCE)
        self.assertIn('minimal._state["selectedByThread"]', SOURCE)

    def test_callbacks_are_exported_from_this_overlay(self) -> None:
        self.assertIn('__name__ + "." + callback', SOURCE)
        for callback in (
            "selected_callsite",
            "wrapper_entry",
            "provider_entry",
            "provider_return",
            "group_return",
            "selected_caller_return",
            "timeline_marker",
        ):
            self.assertIn(callback, SOURCE)


if __name__ == "__main__":
    unittest.main()
