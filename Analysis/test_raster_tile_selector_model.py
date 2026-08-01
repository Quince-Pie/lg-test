import hashlib
import math
import unittest

import open_raster_tile_selector_holdout as holdout
import raster_tile_selector_model as model
import validate_raster_tile_numerator as capture


class RasterTileSelectorModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preregistration, cls.metadata = holdout.load_preregistration()

    def test_prediction_stream_is_frozen_before_opening(self):
        self.assertFalse(self.preregistration["holdoutOpenedAtPreregistration"])
        self.assertEqual(self.metadata["endpointCount"], 190)
        self.assertEqual(self.metadata["recordCount"], 129_200)
        self.assertEqual(self.metadata["bytes"], 9_302_400)
        self.assertEqual(
            self.metadata["sha256"],
            "08d2a53307e94ea4d390e61e313766f89ea98cad38a4fd2e1392bd6cf1de02c1",
        )

    def test_prediction_cases_are_only_the_sealed_domain(self):
        self.assertEqual(
            [record["name"] for record in self.metadata["cases"]],
            [
                capture_case.name
                for capture_case in capture.CASES
                if capture_case.role == "sealed-holdout"
            ],
        )

    def test_float32_toward_zero_steps_one_binary32_value(self):
        positive = 1.0 + math.ldexp(3.0, -25)
        negative = -positive
        self.assertEqual(
            model.float32_bits(model.round_toward_zero_float32(positive)), 0x3F800000
        )
        self.assertEqual(
            model.float32_bits(model.round_toward_zero_float32(negative)), 0xBF800000
        )

    def test_selector_table_is_frozen(self):
        compressed = model.SELECTOR_TABLE_PATH.read_bytes()
        self.assertEqual(
            hashlib.sha256(compressed).hexdigest(),
            model.SELECTOR_TABLE_COMPRESSED_SHA256,
        )
        self.assertEqual(len(model.load_selector_table()), model.SELECTOR_TABLE_COUNT)


if __name__ == "__main__":
    unittest.main()
