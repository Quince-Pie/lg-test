#!/usr/bin/env python3
"""Source checks for the local-UUID-only field-matrix retry overlay."""

from __future__ import annotations

import unittest
from pathlib import Path


SOURCE = (
    Path(__file__)
    .with_name("capture_case22_provider_field_matrix_local_macos_26_6_1_retry_lldb.py")
    .read_text(encoding="utf-8")
)


class Case22ProviderFieldMatrixRetrySourceTests(unittest.TestCase):
    def test_retry_changes_only_wrapper_identity_resolution(self) -> None:
        self.assertIn(
            "import capture_case22_provider_field_matrix_local_macos_26_6_1_lldb as frozen",
            SOURCE,
        )
        self.assertIn("frozen._capture_wrapper = _capture_local_wrapper", SOURCE)
        self.assertIn("frozen.__lldb_init_module(debugger, internal_dict)", SOURCE)
        self.assertIn("frozen.finalize()", SOURCE)

    def test_local_uuid_and_every_exact_wrapper_gate_remain_required(self) -> None:
        for needle in (
            'identity.get("uuid") != frozen.SWIFTUICORE_UUID',
            'endswith("/SwiftUICore")',
            "frozen.WRAPPER_MODULE_OFFSET",
            "frozen.WRAPPER_FUNCTION",
            "frozen.WRAPPER_BYTE_COUNT",
            "frozen.WRAPPER_CODE_SHA256",
        ):
            self.assertIn(needle, SOURCE)

    def test_retry_cannot_select_on_captured_values(self) -> None:
        for forbidden in (
            "providerObject",
            "returnF64",
            "capturedMargin",
            "capturedCrop",
            "capturedImage",
            "capturedPixel",
        ):
            self.assertNotIn(forbidden, SOURCE)


if __name__ == "__main__":
    unittest.main()
