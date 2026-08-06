#!/usr/bin/env python3
"""Source checks for the callsite-gated minimal matrix retry."""

from __future__ import annotations

import unittest
from pathlib import Path


SOURCE = (
    Path(__file__)
    .with_name(
        "capture_backdrop_margin_case22_provider_object_matrix_minimal_retry_local_macos_26_6_1_lldb.py"
    )
    .read_text(encoding="utf-8")
)


class MinimalCase22ProviderObjectMatrixRetrySourceTests(unittest.TestCase):
    def test_retry_imports_the_frozen_minimal_adapter(self) -> None:
        self.assertIn(
            "import capture_backdrop_margin_case22_provider_object_matrix_minimal_local_macos_26_6_1_lldb as frozen",
            SOURCE,
        )
        self.assertIn("frozen._install_exact_breakpoints(frame)", SOURCE)
        self.assertIn("frozen.finalize()", SOURCE)

    def test_exact_update_sdf_call_and_return_gate_the_capture(self) -> None:
        for needle in (
            "local.LOCAL_CALLER_MODULE_OFFSET",
            "group.CALLER_FUNCTION",
            "local.LOCAL_CALLER_CODE_SHA256",
            "CALLER_BYTE_COUNT = 6844",
            "CALLER_CALL_OFFSET = local.LOCAL_CALLER_CALL_OFFSET",
            "CALLER_RETURN_OFFSET = group.CALLER_RETURN_AFTER_PRODUCER_OFFSET",
            "local.LOCAL_CALLER_CALL_INSTRUCTION_HEX",
            "selected_callsite",
            "selected_caller_return",
        ):
            self.assertIn(needle, SOURCE)

    def test_unrelated_breakpoints_are_disarmed(self) -> None:
        self.assertIn("breakpoint.SetEnabled(False)", SOURCE)
        self.assertIn("_set_selected_breakpoints_enabled(True)", SOURCE)
        self.assertIn('"unrelatedWrapperOrProviderCallbacksArmed": False', SOURCE)
        self.assertIn('"perSelectedCallMaximumStopCount": 6', SOURCE)

    def test_retry_never_reads_a_captured_value_for_selection(self) -> None:
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

    def test_callbacks_use_the_direct_import_namespace(self) -> None:
        self.assertIn('__name__ + "." + callback', SOURCE)
        for callback in (
            "selected_callsite",
            "wrapper_entry",
            "provider_entry",
            "provider_return",
            "group_return",
            "selected_caller_return",
        ):
            self.assertIn(callback, SOURCE)


if __name__ == "__main__":
    unittest.main()
