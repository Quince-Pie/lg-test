#!/usr/bin/env python3
"""Source contracts for the four-stop live direct join."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "capture_background_filter_constructor_timeline_marker_direct_join_local_macos_26_6_1_lldb.py"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


class DirectJoinCaptureSourceTests(unittest.TestCase):
    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(SOURCE, feature_version=(3, 9))

    def test_exact_four_stop_chain_is_frozen(self) -> None:
        self.assertIn('"stopsPerSelectedChain": 4', SOURCE)
        for event in (
            '"parameters-builder-call"',
            '"parameters-builder-return"',
            '"constructor-call"',
            '"provider-entry"',
        ):
            self.assertIn(event, SOURCE)
        self.assertNotIn('"constructor-return"', SOURCE)

    def test_complete_values_are_captured_without_selecting_calls(self) -> None:
        self.assertIn("parked.PARAMETERS_BYTE_COUNT", SOURCE)
        self.assertIn("parked.BACKGROUND_FILTER_BYTE_COUNT", SOURCE)
        for contract in (
            '"capturedParametersUsedForSelection": False',
            '"capturedConstructorOutputUsedForSelection": False',
            '"capturedProviderObjectUsedForSelection": False',
            '"capturedRegisterArgumentUsedForSelection": False',
            '"capturedAddressUsedForSelection": False',
            '"capturedImageUsedForSelection": False',
            '"capturedPixelUsedForSelection": False',
        ):
            self.assertIn(contract, SOURCE)

    def test_direct_branch_targets_and_code_are_authenticated(self) -> None:
        self.assertIn("_decode_direct_branch_target", SOURCE)
        self.assertIn("CONSTRUCTOR_CODE_SHA256", SOURCE)
        self.assertIn("RESOLVED_RECIPE_BUILDER_CODE_SHA256", SOURCE)
        self.assertIn("_capture_provider", SOURCE)
        self.assertIn("_capture_marker_function", SOURCE)

    def test_capture_is_marker_bounded_and_rejects_crossing_chains(self) -> None:
        self.assertIn("if marker_index == 0:", SOURCE)
        self.assertIn("timeline.TIMELINE_MARKER_COUNT - 1", SOURCE)
        self.assertIn("timeline marker crossed an active direct chain", SOURCE)
        self.assertIn("precedingCompletedChainStartIndex", SOURCE)
        self.assertIn("precedingCompletedChainEndIndexExclusive", SOURCE)


if __name__ == "__main__":
    unittest.main()
