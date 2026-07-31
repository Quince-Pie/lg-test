import unittest

import validate_reciprocal_transfer as transfer


class RasterReciprocalTransferTests(unittest.TestCase):
    def test_preregistration_and_frozen_predictions_are_immutable(self):
        preregistration = transfer.load_preregistration()

        self.assertEqual(preregistration["schemaVersion"], 1)
        self.assertFalse(preregistration["observedAtPreregistration"])
        self.assertEqual(
            preregistration["frozenPredictions"][
                "selectedReciprocalTableSha256"
            ],
            transfer.CANONICAL_RECIPROCAL_SHA256,
        )

    def test_width_domain_is_unseen_and_hash_frozen(self):
        widths = transfer.prospective_widths()

        self.assertEqual(len(widths), transfer.WIDTH_COUNT)
        self.assertEqual(widths[0], transfer.WIDTH_LOWER)
        self.assertEqual(widths[-1], transfer.WIDTH_UPPER)
        self.assertTrue(all(width > 16_384 for width in widths))
        self.assertEqual(
            transfer.uint32_sha256(widths),
            transfer.WIDTHS_SHA256,
        )

    def test_no_evidence_failure_amends_only_the_viewport(self):
        amendment = transfer.load_amendment()

        self.assertFalse(
            amendment["failedRun"][
                "appleReciprocalOrCoefficientOutputsObserved"
            ]
        )
        self.assertEqual(
            amendment["technicalChange"]["previousValue"],
            transfer.PREREGISTERED_VIEWPORT_WIDTH,
        )
        self.assertEqual(
            amendment["technicalChange"]["newValue"],
            transfer.VIEWPORT_WIDTH,
        )
        self.assertFalse(
            amendment["unchangedFrozenPredictions"][
                "acceptanceCriteriaChanged"
            ]
        )

    def test_empty_runs_amend_routing_without_changing_predictions(self):
        amendment = transfer.load_routing_amendment()

        self.assertFalse(amendment["observedAtAmendment"])
        self.assertTrue(
            all(
                not run["pullCorpusUploaded"]
                for run in amendment["failedRuns"]
            )
        )
        self.assertFalse(
            amendment["unchangedFrozenPredictions"][
                "numericAcceptanceCriteriaChanged"
            ]
        )

    def test_every_geometry_sample_is_safely_interior(self):
        for width in transfer.prospective_widths():
            for geometry in transfer.GEOMETRY_CASES:
                for sample_side in range(transfer.SAMPLE_SIDE_COUNT):
                    position = transfer.sample_position(
                        width,
                        geometry,
                        sample_side,
                    )
                    self.assertGreater(
                        position["signedInteriorArea"],
                        transfer.MINIMUM_SIGNED_INTERIOR_AREA,
                    )
                    self.assertLess(
                        position["originX"],
                        transfer.VIEWPORT_WIDTH,
                    )
                    self.assertGreater(
                        position["originX"] + width,
                        0,
                    )

    def test_float_pair_acceptance_round_trips_a_known_line(self):
        slope_bits = transfer.float32_bits(0.001953125)
        slope = transfer.float32_value(slope_bits)
        position = 13
        constant = 0.25
        pulls = (
            transfer.float32_bits(position * slope + constant),
            transfer.float32_bits(
                (position + 0.9375) * slope + constant
            ),
        )

        self.assertTrue(
            transfer.pair_accepts_slope(
                slope_bits,
                position=position,
                pulls=pulls,
            )
        )

    def test_physical_product_has_a_frozen_control(self):
        self.assertEqual(
            transfer.physical_product_bits(
                32_768,
                16_777_216,
                12_310_539,
            ),
            0x37BB_D80B,
        )


if __name__ == "__main__":
    unittest.main()
