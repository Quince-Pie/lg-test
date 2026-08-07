#!/usr/bin/env python3
"""Source contracts for real dematerialize dynamic-uniform capture."""

import unittest
from pathlib import Path


SOURCE = (
    Path(__file__).parent.parent / "Sources" / "GlassIntrospect" / "main.swift"
).read_text(encoding="utf-8")


class DematerializeUniformCaptureSourceTests(unittest.TestCase):
    def test_dynamic_capture_is_not_restricted_to_materialize(self) -> None:
        self.assertNotIn("dynamic uniform capture requires", SOURCE)
        self.assertNotIn("direction != .materialize", SOURCE)

    def test_absent_endpoint_is_allowed_but_not_synthesized(self) -> None:
        snapshot_loop = SOURCE[SOURCE.index("if dynamicUniformsRequested,") :]
        self.assertIn("else if index != sampleCount - 1", snapshot_loop)
        endpoint_append = snapshot_loop[
            snapshot_loop.index("if direction == .materialize,") :
        ]
        self.assertIn("dynamicUniformSnapshots.append(", endpoint_append)
        self.assertLess(
            endpoint_append.index("if direction == .materialize,"),
            endpoint_append.index("dynamicUniformSnapshots.append("),
        )

    def test_real_presentation_snapshots_remain_the_replay_source(self) -> None:
        self.assertIn(
            "transitionBackgroundFilterSnapshot(\n                            rootLayer: rootLayer",
            SOURCE,
        )
        self.assertIn('presentationLayerReplayed": true', SOURCE)
        self.assertIn('freshStaticCarrier": true', SOURCE)


if __name__ == "__main__":
    unittest.main()
