#!/usr/bin/env python3
"""Unit tests for topology-only constructor census summaries."""

from __future__ import annotations

import unittest
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate_background_filter_constructor_timeline_marker_census_local_macos_26_6_1 as subject


def call(entry_marker: int, return_marker: int, entry_event: int, return_event: int):
    return {
        "entryAfterMarkerIndex": entry_marker,
        "returnAfterMarkerIndex": return_marker,
        "entryEventIndex": entry_event,
        "returnEventIndex": return_event,
    }


class ConstructorCensusTopologyTests(unittest.TestCase):
    def test_empty_census_is_valid_discovery_information(self) -> None:
        summary = subject.topology_summary([], [])
        self.assertEqual(summary["constructorCallCount"], 0)
        self.assertEqual(summary["parametersBuilderCallCount"], 0)
        self.assertEqual(summary["intervalsWithConstructorCalls"], 0)
        self.assertEqual(len(summary["intervals"]), 32)

    def test_fully_contained_calls_are_partitioned_by_marker_interval(self) -> None:
        constructors = [call(3, 3, 12, 13), call(4, 5, 20, 24)]
        builders = [call(3, 3, 8, 9), call(7, 7, 30, 31)]
        summary = subject.topology_summary(constructors, builders)
        interval = summary["intervals"][3]
        self.assertEqual(interval["fullyContainedConstructorCallCount"], 1)
        self.assertEqual(interval["fullyContainedParametersBuilderCallCount"], 1)
        self.assertTrue(
            interval["allContainedBuilderReturnsPrecedeAllContainedConstructorCalls"]
        )
        self.assertEqual(summary["constructorCallsCrossingMarkerCount"], 1)
        self.assertEqual(summary["parametersBuilderCallsCrossingMarkerCount"], 0)

    def test_ordering_claim_requires_both_call_types(self) -> None:
        summary = subject.topology_summary([call(2, 2, 9, 10)], [])
        self.assertFalse(
            summary["intervals"][2][
                "allContainedBuilderReturnsPrecedeAllContainedConstructorCalls"
            ]
        )

    def test_marker_cumulative_count_excludes_current_interval(self) -> None:
        histogram = {0: 4, 1: 3, 2: 8}
        self.assertEqual(subject.marker_cumulative_count(histogram, 0), 0)
        self.assertEqual(subject.marker_cumulative_count(histogram, 1), 4)
        self.assertEqual(subject.marker_cumulative_count(histogram, 3), 15)


if __name__ == "__main__":
    unittest.main()
