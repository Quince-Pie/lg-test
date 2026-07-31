import unittest

import validate_raster_quotient_fine_mantissa as fine


class RasterQuotientFineMantissaTests(unittest.TestCase):
    def test_preregistered_prediction_recomputes_exact_hash(self):
        preregistration = fine.load_preregistration()
        self.assertFalse(preregistration["fineMantissaObservedAtPreregistration"])
        self.assertEqual(
            fine.expected_file_bytes(),
            15_728_640,
        )
        self.assertEqual(
            fine.predicted_float_bits(
                100,
                21_474_837,
                38_209 << 8,
            ),
            0x3BBF0B86,
        )
        self.assertEqual(
            preregistration["predictedTruthTable"]["sha256"],
            fine.PREDICTED_TRUTH_SHA256,
        )


if __name__ == "__main__":
    unittest.main()
