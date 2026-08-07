#!/usr/bin/env python3
"""Small invariant tests for the direct-join validator."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate_background_filter_constructor_timeline_marker_direct_join_local_macos_26_6_1 as subject


class DirectJoinValidatorTests(unittest.TestCase):
    def test_event_validator_preserves_exact_identity(self) -> None:
        events = [
            {"eventIndex": 0, "kind": "constructor-call", "recordIndex": 4}
        ]
        self.assertEqual(
            subject.validate_event(events, 0, "constructor-call", 4, "test"), 0
        )
        with self.assertRaisesRegex(ValueError, "event differs"):
            subject.validate_event(events, 0, "provider-entry", 4, "test")

    def test_direct_join_uses_complete_widths(self) -> None:
        self.assertEqual(subject.parked.PARAMETERS_BYTE_COUNT, 1025)
        self.assertEqual(subject.parked.BACKGROUND_FILTER_BYTE_COUNT, 504)
        self.assertEqual(
            subject.parked.BACKGROUND_FILTER_INITIALIZED_BYTE_COUNT,
            491,
        )

    def test_census_failure_identity_is_not_placeholder(self) -> None:
        self.assertEqual(len(subject.CENSUS_FAILURE_RESULT_SHA256), 64)
        int(subject.CENSUS_FAILURE_RESULT_SHA256, 16)


if __name__ == "__main__":
    unittest.main()
