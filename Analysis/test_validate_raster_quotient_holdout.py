import unittest

import validate_raster_quotient_holdout as holdout


class RasterQuotientHoldoutTests(unittest.TestCase):
    def test_preregistered_domain_and_prediction_are_sealed(self):
        preregistration = holdout.load_preregistration()
        self.assertFalse(preregistration["holdoutOpenedAtPreregistration"])
        self.assertEqual(holdout.expected_sample_count(), 524_288)
        self.assertEqual(holdout.expected_file_bytes(), 41_943_040)
        self.assertEqual(
            preregistration["predictedTruthTable"]["sha256"],
            holdout.PREDICTED_TRUTH_SHA256,
        )
        self.assertEqual(
            len(preregistration["reciprocalPredictions"]),
            16,
        )
        self.assertEqual(
            holdout.nearest_even_reciprocal_index(100),
            21_474_836,
        )
        self.assertEqual(
            holdout.predicted_float_bits(
                100,
                21_474_837,
                38_209,
            ),
            0x3BBF0B86,
        )


if __name__ == "__main__":
    unittest.main()
