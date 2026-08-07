#!/usr/bin/env python3
"""Unit tests for the five-stop to four-stop validation projection."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate_background_filter_constructor_timeline_marker_return_join_local_macos_26_6_1 as subject


class ConstructorReturnProjectionTests(unittest.TestCase):
    def test_projection_removes_only_return_stop_and_preserves_bytes(self) -> None:
        events = [
            {"eventIndex": 0, "kind": "timeline-marker", "recordIndex": 0},
            {"eventIndex": 1, "kind": "parameters-builder-call", "recordIndex": 0},
            {"eventIndex": 2, "kind": "parameters-builder-return", "recordIndex": 0},
            {"eventIndex": 3, "kind": "constructor-call", "recordIndex": 0},
            {"eventIndex": 4, "kind": "constructor-return", "recordIndex": 0},
            {"eventIndex": 5, "kind": "provider-entry", "recordIndex": 0},
            {"eventIndex": 6, "kind": "timeline-marker", "recordIndex": 1},
        ]
        returned = {"address": 99, "byteCount": 504, "hex": "00" * 504}
        trace = {
            "configuration": {
                "stopsPerSelectedChain": 5,
                "expectedControlFlowSequence": [],
            },
            "breakpoints": [
                {"name": "constructor_callsite"},
                {"name": "constructor_return"},
            ],
            "events": events,
            "chains": [
                {
                    "builderCallEventIndex": 1,
                    "builderReturnEventIndex": 2,
                    "constructorCallEventIndex": 3,
                    "constructorReturnEventIndex": 4,
                    "providerEntryEventIndex": 5,
                    "constructorOutputAtReturn": returned,
                    "constructorOutputAtProviderEntry": None,
                }
            ],
            "timelineMarkers": [{"eventIndex": 0}, {"eventIndex": 6}],
            "finalEventCount": 7,
        }
        projected = subject.project_to_four_stop_contract(trace)
        self.assertEqual(len(projected["events"]), 6)
        self.assertEqual(
            [event["kind"] for event in projected["events"]],
            [
                "timeline-marker",
                "parameters-builder-call",
                "parameters-builder-return",
                "constructor-call",
                "provider-entry",
                "timeline-marker",
            ],
        )
        chain = projected["chains"][0]
        self.assertEqual(chain["providerEntryEventIndex"], 4)
        self.assertEqual(projected["timelineMarkers"][1]["eventIndex"], 5)
        self.assertEqual(chain["constructorOutputAtProviderEntry"], returned)
        self.assertIsNone(trace["chains"][0]["constructorOutputAtProviderEntry"])

    def test_failure_result_hash_is_frozen(self) -> None:
        self.assertEqual(len(subject.DIRECT_FAILURE_RESULT_SHA256), 64)
        int(subject.DIRECT_FAILURE_RESULT_SHA256, 16)


if __name__ == "__main__":
    unittest.main()
