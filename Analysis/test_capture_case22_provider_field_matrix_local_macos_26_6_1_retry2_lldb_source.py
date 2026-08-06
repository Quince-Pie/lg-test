#!/usr/bin/env python3
"""Source checks for the direct-namespace field-matrix retry overlay."""

from __future__ import annotations

import unittest
from pathlib import Path


SOURCE = (
    Path(__file__)
    .with_name(
        "capture_case22_provider_field_matrix_local_macos_26_6_1_retry2_lldb.py"
    )
    .read_text(encoding="utf-8")
)


class Case22ProviderFieldMatrixRetry2SourceTests(unittest.TestCase):
    def test_retry_reuses_the_frozen_capture_and_local_uuid_overlay(self) -> None:
        self.assertIn(
            "import capture_case22_provider_field_matrix_local_macos_26_6_1_retry_lldb as retry",
            SOURCE,
        )
        self.assertIn("frozen = retry.frozen", SOURCE)
        self.assertIn("retry.__lldb_init_module(debugger, internal_dict)", SOURCE)
        self.assertIn("retry.finalize()", SOURCE)

    def test_every_callback_is_exported_from_the_direct_module(self) -> None:
        for needle in (
            '__name__ + "." + callback',
            "marker = frozen.marker",
            "provider_entry = frozen.provider_entry",
            "provider_return = frozen.provider_return",
            "frozen._set_callback = _set_callback",
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
