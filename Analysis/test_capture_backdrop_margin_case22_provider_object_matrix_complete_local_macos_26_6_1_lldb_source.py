#!/usr/bin/env python3
"""Static fail-closed checks for the complete provider-matrix adapter."""

from __future__ import annotations

import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
SOURCE = (
    ANALYSIS
    / "capture_backdrop_margin_case22_provider_object_matrix_complete_local_macos_26_6_1_lldb.py"
).read_text(encoding="utf-8")


class CompleteProviderObjectMatrixAdapterSourceTests(unittest.TestCase):
    def test_bootstraps_before_launch_at_exact_caller_entry(self) -> None:
        self.assertIn(
            "target.BreakpointCreateByName(group.CALLER_FUNCTION)", SOURCE
        )
        self.assertIn("bootstrap_caller_entry", SOURCE)
        self.assertIn('gate._capture_local_caller(frame, 0)', SOURCE)
        self.assertNotIn("breakpoint set -n main", SOURCE)

    def test_keeps_all_case22_callbacks_until_caller_return(self) -> None:
        group_body = SOURCE.split("def group_return(", 1)[1].split(
            "def selected_caller_return(", 1
        )[0]
        self.assertNotIn("SetEnabled(False)", group_body)
        self.assertIn('selected["completedProviderCallCount"] += 1', group_body)
        self.assertIn("not call_indices", SOURCE)
        self.assertIn(
            'selected["completedProviderCallCount"] != len(call_indices)',
            SOURCE,
        )

    def test_selection_is_structural_and_value_blind(self) -> None:
        self.assertIn("_selected_group_caller", SOURCE)
        self.assertIn("CALLER_RETURN_OFFSET", SOURCE)
        self.assertNotIn("if returnF64", SOURCE)
        self.assertNotIn("if captured", SOURCE)

    def test_stop_formula_covers_multiple_case22_records(self) -> None:
        self.assertIn('"2 + 4 * case22ProviderCallCount"', SOURCE)
        self.assertIn('"providerCallIndexWithinSelectedCaller"', SOURCE)
        self.assertIn('"finalMaximumProviderCallsPerSelectedCaller"', SOURCE)


if __name__ == "__main__":
    unittest.main()
