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
        for width in scale.arithmetic.prospective_widths():
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


if __name__ == "__main__":
    unittest.main()
