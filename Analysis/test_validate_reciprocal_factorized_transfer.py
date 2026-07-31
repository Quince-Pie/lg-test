import unittest

import validate_reciprocal_factorized_transfer as factorized


class RasterReciprocalFactorizedTransferTests(unittest.TestCase):
    def test_preregistration_and_frozen_hashes(self):
        preregistration = factorized.load_preregistration()

        self.assertFalse(preregistration["observedAtPreregistration"])
        self.assertEqual(
            preregistration["sourceEvidence"][
                "unsaturatedPrefixFrozenCandidateRejectedCount"
            ],
            0,
        )

    def test_factorized_domains_have_frozen_hashes(self):
        self.assertEqual(
            factorized.arithmetic.uint32_sha256(
                factorized.geometry_widths()
            ),
            factorized.GEOMETRY_WIDTHS_SHA256,
        )
        self.assertEqual(
            factorized.arithmetic.uint32_sha256(
                factorized.effective_widths()
            ),
            factorized.EFFECTIVE_WIDTHS_SHA256,
        )
        self.assertEqual(
            factorized.arithmetic.uint32_sha256(
                factorized.scaled_delta_bits()
            ),
            factorized.SCALED_DELTA_BITS_SHA256,
        )

    def test_sample_sides_share_a_thirty_pixel_baseline(self):
        for width in factorized.geometry_widths():
            for geometry in factorized.GEOMETRY_CASES:
                high = factorized.sample_position(width, geometry, 0)
                low = factorized.sample_position(width, geometry, 1)

                self.assertEqual(high["tile"], low["tile"])
                self.assertEqual(high["x"] - low["x"], 30)
                self.assertEqual(high["tileLocalX"], 31)
                self.assertEqual(low["tileLocalX"], 1)


if __name__ == "__main__":
    unittest.main()
