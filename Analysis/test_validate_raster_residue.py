import unittest

import validate_raster_residue as residue


class RasterResidueDefinitionTests(unittest.TestCase):
    def test_case_and_role_counts_are_preregistered(self):
        records = residue.expected_residue_records()

        self.assertEqual(len(records), 1_520)
        self.assertEqual(
            sum(record["role"] == "discovery" for record in records),
            1_264,
        )
        self.assertEqual(
            sum(record["role"] == "holdout" for record in records),
            256,
        )
        self.assertEqual(
            {
                int(record["baseCase"][-3:])
                for record in records
                if record["role"] == "holdout"
            },
            residue.HOLDOUT_WIDTHS,
        )

    def test_balanced_residue_selection_is_exact(self):
        self.assertIsNone(residue.residue_numerator_banks(32, 0))
        self.assertEqual(
            residue.residue_numerator_banks(47, 1)[0],
            [24_576, 32_768, 40_960, 30_251, 38_443, 46_635, 44_118, 47_276],
        )
        self.assertEqual(
            residue.residue_numerator_banks(84, 0)[-1],
            [46_976, 55_168, 63_360, 43_695, 51_887, 58_449, 48_606, 53_538],
        )
        self.assertEqual(
            residue.residue_numerator_banks(48, 0)[0],
            [49_152, 65_533, 65_534, 65_530, 65_531, 65_535, 65_527, 65_528],
        )

    def test_every_reachable_residue_is_covered(self):
        seen_groups = set()
        for record in residue.expected_residue_records():
            dimension = int(record["baseCase"][-3:])
            group = (dimension, record["normalizationShift"])
            if group in seen_groups:
                continue
            seen_groups.add(group)
            selected_residues = set(record["productFloorResiduesModulo8"])
            reciprocal_exponent = residue.reciprocal_exponent(dimension)
            quotient_exponent = (
                reciprocal_exponent - record["normalizationShift"]
            )
            reachable = {
                residue.product_floor_residue(numerator, dimension)
                for numerator in range(1, 65_536)
                if residue.ratio_has_binary_exponent(
                    numerator,
                    dimension,
                    quotient_exponent,
                )
            }
            self.assertEqual(selected_residues, reachable)

    def test_each_phase_matrix_uses_64_unique_numerators(self):
        records = residue.expected_residue_records()
        numerators_by_group = {}
        for record in records:
            group = (
                record["baseCase"],
                record["normalizationShift"],
            )
            numerators_by_group.setdefault(group, []).extend(
                record["numerators"]
            )
        self.assertEqual(len(numerators_by_group), 190)
        for numerators in numerators_by_group.values():
            self.assertEqual(len(numerators), 64)
            self.assertEqual(len(set(numerators)), 64)


if __name__ == "__main__":
    unittest.main()
