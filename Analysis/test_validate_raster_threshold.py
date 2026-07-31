import unittest

import validate_raster_threshold as threshold


class RasterThresholdDefinitionTests(unittest.TestCase):
    def test_case_and_role_counts_are_preregistered(self):
        records = threshold.expected_threshold_records()

        self.assertEqual(len(records), 190)
        self.assertEqual(
            sum(record["role"] == "discovery" for record in records),
            158,
        )
        self.assertEqual(
            sum(record["role"] == "holdout" for record in records),
            32,
        )
        self.assertEqual(
            {
                int(record["baseCase"][-3:])
                for record in records
                if record["role"] == "holdout"
            },
            threshold.HOLDOUT_WIDTHS,
        )

    def test_product_phase_selection_is_exact(self):
        self.assertIsNone(
            threshold.threshold_numerators(
                32,
                0,
                tuple(range(40, 48)),
            )
        )
        self.assertEqual(
            threshold.threshold_numerators(
                47,
                1,
                tuple(range(22, 30)),
            ),
            [30_976, 28_288, 25_600, 31_104, 28_416, 25_728, 31_232, 28_544],
        )
        self.assertEqual(
            threshold.threshold_numerators(
                84,
                0,
                tuple(range(40, 48)),
            ),
            [46_080, 48_256, 50_432, 44_416, 46_592, 48_768, 50_944, 44_928],
        )


if __name__ == "__main__":
    unittest.main()
