import unittest

import validate_reciprocal_general_height_transfer as general


class RasterReciprocalGeneralHeightTransferTests(unittest.TestCase):
    def test_preregistration_is_frozen(self):
        preregistration = general.load_preregistration()

        self.assertFalse(preregistration["observedAtPreregistration"])
        self.assertEqual(
            preregistration["sourceEvidence"][
                "factorizedTransferExactAcceptanceCount"
            ],
            458_752,
        )

    def test_all_general_height_samples_are_same_tile_and_interior(self):
        for width in general.factorized.geometry_widths():
            for geometry in general.GEOMETRY_CASES:
                high = general.sample_position(width, geometry, 0)
                low = general.sample_position(width, geometry, 1)

                self.assertEqual(high["tile"], low["tile"])
                self.assertEqual(high["x"] - low["x"], 30)
                self.assertGreater(
                    low["signedInteriorArea"],
                    general.MINIMUM_SIGNED_INTERIOR_AREA,
                )


if __name__ == "__main__":
    unittest.main()
