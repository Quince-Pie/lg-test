#!/usr/bin/env python3
"""Source checks for the minimal live provider-object matrix."""

from __future__ import annotations

import unittest
from pathlib import Path


SOURCE = (
    Path(__file__)
    .with_name(
        "capture_backdrop_margin_case22_provider_object_matrix_minimal_local_macos_26_6_1_lldb.py"
    )
    .read_text(encoding="utf-8")
)


class MinimalCase22ProviderObjectMatrixSourceTests(unittest.TestCase):
    def test_only_four_structural_callbacks_define_the_selected_chain(self) -> None:
        for callback in (
            "wrapper_entry",
            "provider_entry",
            "provider_return",
            "group_return",
        ):
            self.assertIn(callback, SOURCE)
        self.assertIn('"activeBreakpointCountPerSelectedCall": 4', SOURCE)
        self.assertIn('"inheritedWriterOrGroupBreakpointsInstalled": False', SOURCE)

    def test_every_code_identity_is_exact(self) -> None:
        for needle in (
            "local.LOCAL_GROUP_CODE_SHA256",
            "field.WRAPPER_CODE_SHA256",
            "opened.PROVIDER_CODE_SHA256",
            "retry._capture_local_wrapper",
            "field._capture_provider",
            "GROUP_RETURN_OFFSET = 0x26C",
        ):
            self.assertIn(needle, SOURCE)

    def test_object_and_returns_are_joined_bitwise(self) -> None:
        for needle in (
            "PROVIDER_OBJECT_OFFSET_FROM_WRAPPER = 0x10",
            'snapshot["hex"] != call["wrapperEntryObject"]["hex"]',
            'return_object["hex"] != call["providerEntryObject"]["hex"]',
            'v0.hex() != call["returnV0RawLittleEndianHex"]',
        ):
            self.assertIn(needle, SOURCE)

    def test_no_captured_value_can_select_a_call(self) -> None:
        for name in (
            "capturedObjectUsedForSelection",
            "capturedReturnUsedForSelection",
            "capturedMarginUsedForSelection",
            "capturedCropUsedForSelection",
            "capturedImageUsedForSelection",
            "capturedPixelUsedForSelection",
        ):
            self.assertIn(f'"{name}": False', SOURCE)

    def test_lldb_callbacks_use_the_direct_import_namespace(self) -> None:
        self.assertIn('__name__ + "." + callback', SOURCE)


if __name__ == "__main__":
    unittest.main()
