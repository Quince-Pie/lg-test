#!/usr/bin/env python3
"""Discriminators for the public-state dynamic producer geometry join."""

from __future__ import annotations

import unittest

import analyze_prepare_layer_crop_union_operand_matrix as crop_policy
import analyze_transition_geometry_corpus_local_macos_26_6_1 as geometry_model
import analyze_walle_dynamic_backdrop_producer_geometry as analysis
import analyze_walle_dynamic_background_scissor as scissor_model


class DynamicBackdropProducerGeometryTests(unittest.TestCase):
    NATURAL_REMAINING = (
        0.96751880645751953,
        0.87391281127929688,
        0.74975967407226562,
        0.62483692169189453,
        0.49960422515869141,
        0.37418651580810547,
        0.24934291839599609,
        0.12448215484619141,
    )
    CONTROLLED_REMAINING = (
        0.96827316284179688,
        0.87442970275878906,
        0.74844932556152344,
        0.62440586090087891,
        0.49914741516113281,
        0.37360668182373047,
        0.24873256683349609,
        0.12386131286621094,
    )
    EXPECTED_VISIBLE = (
        (110, 95, 819, 819),
        (133, 72, 819, 819),
        (162, 42, 820, 820),
        (192, 12, 820, 820),
        (222, 0, 802, 802),
        (252, 0, 772, 772),
        (282, 0, 742, 742),
        (312, 0, 712, 712),
    )

    def test_two_distinct_retina_streams_have_exact_guards(self) -> None:
        for stream in (self.NATURAL_REMAINING, self.CONTROLLED_REMAINING):
            for remaining, expected in zip(stream, self.EXPECTED_VISIBLE, strict=True):
                with self.subTest(remaining=remaining):
                    result = analysis.predict_producer_guard(
                        scissor_model.EXPECTED_GEOMETRY, remaining
                    )
                    self.assertEqual(tuple(result["visibleI32"]), expected)

    def test_nested_integer_union_is_observable_at_late_state(self) -> None:
        result = analysis.predict_producer_guard(
            scissor_model.EXPECTED_GEOMETRY,
            self.CONTROLLED_REMAINING[4],
        )
        simple_dod = crop_policy.intersect_i32(
            crop_policy.integer_crop(tuple(result["filterDODF64"])),
            (0, 0, 1024, 1024),
        )
        self.assertEqual(simple_dod, (223, 0, 801, 801))
        self.assertEqual(tuple(result["visibleI32"]), (222, 0, 802, 802))

    def test_viewport_clip_is_observable(self) -> None:
        result = analysis.predict_producer_guard(
            scissor_model.EXPECTED_GEOMETRY,
            self.CONTROLLED_REMAINING[-1],
        )
        self.assertEqual(tuple(result["workingI32"]), (312, -108, 820, 820))
        self.assertEqual(tuple(result["visibleI32"]), (312, 0, 712, 712))

    def test_source_uses_division_not_rounded_reciprocal_multiplication(self) -> None:
        scale = geometry_model.float32(self.CONTROLLED_REMAINING[1] * -0.75 + 1.0)
        position = 328.0
        divided = geometry_model.float32(position / scale)
        multiplied = geometry_model.float32(
            position * geometry_model.float32(1.0 / scale)
        )
        self.assertEqual(divided, 952.9960327148438)
        self.assertNotEqual(
            geometry_model.float32_bits(divided),
            geometry_model.float32_bits(multiplied),
        )


if __name__ == "__main__":
    unittest.main()
