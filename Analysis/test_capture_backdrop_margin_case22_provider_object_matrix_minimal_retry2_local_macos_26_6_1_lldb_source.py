#!/usr/bin/env python3
"""Source checks for the bound-only minimal provider-matrix retry."""

from __future__ import annotations

import unittest
from pathlib import Path


SOURCE = (
    Path(__file__)
    .with_name(
        "capture_backdrop_margin_case22_provider_object_matrix_minimal_retry2_local_macos_26_6_1_lldb.py"
    )
    .read_text(encoding="utf-8")
)


class MinimalCase22ProviderObjectMatrixRetry2SourceTests(unittest.TestCase):
    def test_retry_imports_the_frozen_callsite_gate(self) -> None:
        self.assertIn(
            "import capture_backdrop_margin_case22_provider_object_matrix_minimal_retry_local_macos_26_6_1_lldb as frozen",
            SOURCE,
        )
        self.assertIn("frozen.__lldb_init_module(debugger, internal_dict)", SOURCE)
        self.assertIn("frozen.finalize()", SOURCE)

    def test_only_the_finite_bound_changes(self) -> None:
        self.assertIn("MAXIMUM_CALL_COUNT = 4096", SOURCE)
        self.assertIn("minimal.MAXIMUM_CALL_COUNT = MAXIMUM_CALL_COUNT", SOURCE)
        self.assertIn('"previousMaximumCallCount": 512', SOURCE)
        self.assertIn('"boundChangeOnly": True', SOURCE)

    def test_all_runtime_callbacks_use_the_direct_namespace(self) -> None:
        self.assertIn('__name__ + "." + callback', SOURCE)
        for callback in (
            "selected_callsite",
            "wrapper_entry",
            "provider_entry",
            "provider_return",
            "group_return",
            "selected_caller_return",
        ):
            self.assertIn(callback + " = frozen." + callback, SOURCE)

    def test_no_captured_value_selects_the_bound(self) -> None:
        self.assertIn('"capturedValueUsedToSelectNewBound": False', SOURCE)
        for forbidden in (
            "wrapperEntryObject",
            "providerEntryObject",
            "returnF64RawLittleEndianHex",
            "capturedMargin",
            "capturedCrop",
            "capturedImage",
            "capturedPixel",
        ):
            self.assertNotIn(forbidden, SOURCE)


if __name__ == "__main__":
    unittest.main()
