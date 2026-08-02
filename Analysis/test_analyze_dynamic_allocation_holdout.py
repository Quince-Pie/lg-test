#!/usr/bin/env python3
"""Tests for the post-opening dynamic-allocation audit."""

import unittest

import analyze_dynamic_allocation_holdout as audit


GEOMETRY = {
    "centerX": 602.25,
    "centerY": 377.75,
    "height": 640,
    "name": "circle-640-fractional",
    "shape": "circle",
    "width": 640,
    "windowHeight": 1_024,
    "windowWidth": 1_024,
}


class CarrierTests(unittest.TestCase):
    def test_open_state_is_centered_independently_of_target(self) -> None:
        predicted = audit.predicted_carrier(GEOMETRY, 0.5)
        self.assertEqual(predicted["position"], [352.0, 352.0])
        self.assertEqual(predicted["extent"], [320.0, 320.0])

    def test_endpoint_snaps_to_rounded_target_origin(self) -> None:
        predicted = audit.predicted_carrier(GEOMETRY, 1.0)
        self.assertEqual(predicted["position"], [282, 58])
        self.assertEqual(predicted["extent"], [640.0, 640.0])


class AllocationTests(unittest.TestCase):
    def test_allocation_uses_requested_extent_not_carrier_extent(self) -> None:
        bounds = audit.allocation_bounds(GEOMETRY, [352.0, 352.0])
        self.assertEqual(bounds["x"], [352.0, 992.0])
        self.assertEqual(bounds["y"], [32.0, 672.0])

    def test_destination_extent_includes_origin_alignment_slack(self) -> None:
        bounds = {"x": [352.0, 992.0], "y": [32.0, 672.0]}
        self.assertEqual(
            audit.destination_extent(
                bounds,
                scale=0.75,
                effective_origin=[260, 20],
            ),
            [512, 512],
        )

    def test_narrow_origin_candidate_is_four_pixel_aligned(self) -> None:
        bounds = {"x": [352.0, 992.0], "y": [32.0, 672.0]}
        self.assertEqual(
            audit.origin_candidate(bounds, remaining=0.5, scale=0.75),
            [260, 20],
        )

    def test_nonendpoint_crop_clamp_extent_and_scissor(self) -> None:
        bounds = {"x": [352.0, 992.0], "y": [32.0, 672.0]}
        self.assertEqual(
            audit.nonendpoint_allocation_metadata(bounds, scale=0.75),
            {
                "cropOrigin": [265, 24],
                "clampMaximum": [478, 479],
                "producerExtent": [512, 512],
                "scissorExtent": [496, 497],
            },
        )


class MeshTests(unittest.TestCase):
    def test_two_clipped_sides_select_four_quads(self) -> None:
        sides = {
            "xLower": False,
            "xUpper": True,
            "yLower": True,
            "yUpper": False,
        }
        self.assertEqual(audit.expected_nonendpoint_vertex_count(sides), 16)
        primary = {
            "position": [10.0, 20.0, 30.0, 40.0],
            "source": [11.0, 21.0, 31.0, 41.0],
        }
        auxiliary = audit.expected_auxiliary_quad_bounds(primary, sides)
        self.assertEqual(len(auxiliary), 3)
        self.assertEqual(auxiliary[0]["position"], [10.0, 19.0, 30.0, 20.0])
        self.assertEqual(auxiliary[-1]["source"], [30.5, 21.0, 30.5, 41.0])

    def test_four_clipped_sides_select_nine_quads(self) -> None:
        sides = dict.fromkeys(("xLower", "xUpper", "yLower", "yUpper"), True)
        self.assertEqual(audit.expected_nonendpoint_vertex_count(sides), 36)
        primary = {
            "position": [0.0, 0.0, 8.0, 8.0],
            "source": [0.0, 0.0, 16.0, 16.0],
        }
        self.assertEqual(len(audit.expected_auxiliary_quad_bounds(primary, sides)), 8)

    def test_quad4_candidate_preserves_asymmetric_edge_expansion(self) -> None:
        bounds = {
            "x": [361.6697998046875, 1001.6697998046875],
            "y": [22.3302001953125, 662.3302001953125],
        }
        self.assertEqual(
            audit.quad4_primary_bounds_candidate(
                bounds,
                scale=0.7651090621948242,
            ),
            [274, 9, 768, 509],
        )

    def test_primary_position_bounds_requires_one_quad(self) -> None:
        vertices = [
            [2.0, 3.0, 0.0, 1.0, 4.0, 6.0],
            [8.0, 3.0, 0.0, 1.0, 16.0, 6.0],
            [8.0, 9.0, 0.0, 1.0, 16.0, 18.0],
            [2.0, 9.0, 0.0, 1.0, 4.0, 18.0],
        ]
        self.assertEqual(audit.primary_position_bounds(vertices), [2.0, 3.0, 8.0, 9.0])


if __name__ == "__main__":
    unittest.main()
