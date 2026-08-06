#!/usr/bin/env python3
"""Source checks for the all-live-call provider-object matrix."""

from __future__ import annotations

import unittest
from pathlib import Path


SOURCE = (
    Path(__file__)
    .with_name(
        "capture_backdrop_margin_case22_provider_object_matrix_local_macos_26_6_1_lldb.py"
    )
    .read_text(encoding="utf-8")
)


class Case22ProviderObjectMatrixSourceTests(unittest.TestCase):
    def test_matrix_uses_the_exact_local_group_and_provider_gates(self) -> None:
        for needle in (
            "local._apply_local_host_profile()",
            "retry._capture_local_wrapper",
            "field._capture_provider",
            'offset not in (0x268, 0x26C)',
            'stage.get("authenticatedIndirectTargetRaw")',
        ):
            self.assertIn(needle, SOURCE)

    def test_provider_object_identity_and_return_join_are_bitwise(self) -> None:
        for needle in (
            "PROVIDER_OBJECT_OFFSET_FROM_WRAPPER = 0x10",
            'base._register_u64(frame, "x20")',
            'base._register_bytes(frame, "v0")',
            'group_raw != call["returnF64RawLittleEndianHex"]',
            'return_object["hex"] != call["entryObject"]["hex"]',
        ):
            self.assertIn(needle, SOURCE)

    def test_matrix_cannot_select_on_any_captured_output(self) -> None:
        for name in (
            "capturedObjectUsedForSelection",
            "capturedReturnUsedForSelection",
            "capturedMarginUsedForSelection",
            "capturedCropUsedForSelection",
            "capturedImageUsedForSelection",
            "capturedPixelUsedForSelection",
        ):
            self.assertIn(f'"{name}": False', SOURCE)

    def test_callbacks_are_exported_from_the_direct_lldb_module(self) -> None:
        self.assertIn('__name__ + "." + callback', SOURCE)
        for callback in (
            "copy_entry",
            "margin_setter",
            "copy_margin_store",
            "backdrop_bounds",
            "producer_entry",
            "producer_stage",
            "provider_entry",
            "provider_return",
        ):
            self.assertIn(callback, SOURCE)


if __name__ == "__main__":
    unittest.main()
