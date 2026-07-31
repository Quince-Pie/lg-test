import unittest

import validate_raster_refinement as refinement


class RasterRefinementDefinitionTests(unittest.TestCase):
    def test_expected_records_are_exact_and_unique(self):
        records = refinement.expected_refinement_records()

        self.assertEqual(len(records), 70)
        self.assertEqual(len({record["name"] for record in records}), 70)
        self.assertEqual(
            records[0],
            {
                "name": ("numerator-refinement-discovery-factor-h064-w047-anchor-074"),
                "baseCase": "tomography-discovery-factor-h064-w047",
                "anchorNumeratorIndex": 74,
                "numerators": list(range(42_301, 42_309)),
                "deltaBits": [
                    refinement.float32_bits(value / 65_536)
                    for value in range(42_301, 42_309)
                ],
            },
        )
        self.assertEqual(
            records[-1]["name"],
            ("numerator-refinement-discovery-factor-h064-w124-anchor-197"),
        )
        self.assertTrue(
            all(
                len(record["numerators"]) == 8
                and len(set(record["numerators"])) == 8
                and all(0 < value < 65_536 for value in record["numerators"])
                for record in records
            )
        )


if __name__ == "__main__":
    unittest.main()
