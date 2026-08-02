#!/usr/bin/env python3
"""Tests for the prospective dynamic-allocation holdout gate."""

import unittest

import validate_dynamic_allocation_holdout as holdout


OPENED_GEOMETRY = {
    "centerX": 512,
    "centerY": 512,
    "height": 800,
    "shape": "circle",
    "width": 800,
    "windowHeight": 1_024,
    "windowWidth": 1_024,
}


class PolicyTests(unittest.TestCase):
    def test_retrospective_fractional_state_remains_exact(self) -> None:
        predicted = holdout.predict_policy(
            OPENED_GEOMETRY,
            remaining=0.8749866485595703,
            scale=0.5625066757202148,
        )
        self.assertEqual(predicted["cropOrigin"], [92, 35])
        self.assertEqual(
            predicted["textureCoordinateClamp"],
            [0, 0, 448, 448],
        )
        self.assertEqual(predicted["producerExtent"], [512, 512])
        self.assertEqual(predicted["destinationExtent"], [512, 512])
        self.assertEqual(predicted["effectiveOrigin"], [88, 32])

    def test_small_geometry_endpoint_crosses_two_allocation_quanta(
        self,
    ) -> None:
        geometry = {
            **OPENED_GEOMETRY,
            "width": 256,
            "height": 256,
        }
        predicted = holdout.predict_policy(
            geometry,
            remaining=1.0,
            scale=0.5,
        )
        self.assertEqual(predicted["cropOrigin"], [193, 192])
        self.assertEqual(
            predicted["textureCoordinateClamp"],
            [0, 0, 126, 127],
        )
        self.assertEqual(predicted["producerExtent"], [128, 128])
        self.assertEqual(predicted["destinationExtent"], [128, 128])
        self.assertEqual(predicted["effectiveOrigin"], [188, 188])

    def test_clipped_geometry_endpoint_uses_full_window_span(self) -> None:
        geometry = {
            **OPENED_GEOMETRY,
            "width": 1_536,
            "height": 1_536,
        }
        predicted = holdout.predict_policy(
            geometry,
            remaining=1.0,
            scale=0.5,
        )
        self.assertEqual(predicted["cropOrigin"], [1, 0])
        self.assertEqual(
            predicted["textureCoordinateClamp"],
            [0, 0, 510, 511],
        )
        self.assertEqual(predicted["producerExtent"], [512, 512])
        self.assertEqual(predicted["destinationExtent"], [512, 512])
        self.assertEqual(predicted["effectiveOrigin"], [-4, -4])

    def test_origin_phase_changes_at_frozen_halfway_boundary(self) -> None:
        before = holdout.predict_policy(
            OPENED_GEOMETRY,
            remaining=0.499,
            scale=1.0 - 0.499 / 2.0,
        )
        after = holdout.predict_policy(
            OPENED_GEOMETRY,
            remaining=0.5,
            scale=0.75,
        )
        self.assertEqual(before["effectiveOrigin"][0] % 4, 0)
        self.assertEqual(after["effectiveOrigin"][0] % 4, 0)
        self.assertEqual(before["effectiveOrigin"][1] % 4, 0)
        self.assertEqual(after["effectiveOrigin"][1] % 4, 0)


class MetadataTests(unittest.TestCase):
    def test_raw_stage_file_is_rejected_recursively(self) -> None:
        self.assertTrue(
            holdout.no_raw_stage_dumps({"snapshots": [{"width": 64, "height": 64}]})
        )
        self.assertFalse(
            holdout.no_raw_stage_dumps({"snapshots": [{"rawFile": "opened.raw"}]})
        )

    def test_alignment_rejects_empty_allocation(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            holdout.align_up(0)


if __name__ == "__main__":
    unittest.main()
