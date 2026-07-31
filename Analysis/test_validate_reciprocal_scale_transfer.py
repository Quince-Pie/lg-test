import unittest

import validate_reciprocal_scale_transfer as scale


class RasterReciprocalScaleTransferTests(unittest.TestCase):
    def test_preregistration_freezes_the_failed_gate_and_predictions(self):
        preregistration = scale.load_preregistration()

        self.assertFalse(preregistration["observedAtPreregistration"])
        self.assertEqual(
            preregistration["sourceEvidence"][
                "failedCombinedTransferRunId"
            ],
            30_654_181_785,
        )
        self.assertFalse(
            preregistration["frozenPredictions"][
                "numericalPredictionsChangedFromFailedCombinedGate"
            ]
        )

    def test_every_triangle_and_sample_is_inside_the_viewport(self):
        for width in scale.capture_widths():
            for geometry in scale.GEOMETRY_CASES:
                self.assertLessEqual(width, scale.VIEWPORT_WIDTH)
                self.assertLessEqual(
                    geometry["originY"] + geometry["height"],
                    scale.TARGET_HEIGHT,
                )
                for sample_side in range(scale.SAMPLE_SIDE_COUNT):
                    position = scale.sample_position(
                        width,
                        geometry,
                        sample_side,
                    )
                    self.assertGreater(
                        position["signedInteriorArea"],
                        scale.MINIMUM_SIGNED_INTERIOR_AREA,
                    )

    def test_only_boundary_class_is_a_calibration_control(self):
        widths = scale.capture_widths()

        self.assertEqual(len(widths), scale.WIDTH_COUNT)
        self.assertEqual(widths[0], 16_384)
        self.assertTrue(all(width > 16_384 for width in widths[1:]))
        self.assertEqual(
            scale.arithmetic.uint32_sha256(widths),
            scale.WIDTHS_SHA256,
        )


if __name__ == "__main__":
    unittest.main()
