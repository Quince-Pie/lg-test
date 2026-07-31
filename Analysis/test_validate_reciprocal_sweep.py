import unittest

import validate_reciprocal_sweep as sweep


class RasterReciprocalSweepTests(unittest.TestCase):
    def test_preregistration_and_witness_envelope_are_frozen(self):
        preregistration = sweep.load_preregistration()

        self.assertEqual(preregistration["schemaVersion"], 1)
        self.assertEqual(
            len(sweep.selected_widths(holdout=False)),
            sweep.DISCOVERY_WIDTH_COUNT,
        )
        self.assertEqual(
            len(sweep.selected_widths(holdout=True)),
            sweep.HOLDOUT_WIDTH_COUNT,
        )
        self.assertEqual(sweep.expected_file_bytes(), 15_882_720)
        self.assertEqual(
            sweep.expected_file_bytes(sweep.HOLDOUT_WIDTH_COUNT),
            2_325_120,
        )

    def test_holdout_opening_preserves_the_scientific_boundary(self):
        opening = sweep.load_holdout_opening()

        self.assertTrue(opening["authorized"])
        self.assertTrue(
            opening["scientificLimits"][
                "thisOpeningIsNotProspectiveModelValidation"
            ]
        )
        self.assertTrue(opening["nextProspectiveGate"]["required"])

    def test_holdout_is_closed_under_power_of_two_scaling(self):
        roles_by_class: dict[int, set[bool]] = {}
        for width in range(sweep.WIDTH_LOWER, sweep.WIDTH_UPPER + 1):
            roles_by_class.setdefault(
                sweep.normalization_class(width),
                set(),
            ).add(sweep.is_holdout_width(width))

        self.assertTrue(all(len(roles) == 1 for roles in roles_by_class.values()))
        self.assertTrue(
            all(sweep.is_holdout_width(width) for width in sweep.PRODUCTION_HOLDOUT_WIDTHS)
        )

    def test_visible_position_rule_stays_inside_the_capture_target(self):
        for width in (
            sweep.WIDTH_LOWER,
            800,
            976,
            4_096,
            8_192,
            sweep.WIDTH_UPPER,
        ):
            positions = sweep.expected_positions(width)
            self.assertGreaterEqual(len(positions), 4)
            self.assertLessEqual(
                len(positions),
                sweep.PRIMITIVE_COUNT * sweep.TILE_COUNT,
            )
            self.assertTrue(
                all(
                    0 <= int(position["x"]) < sweep.TARGET_WIDTH
                    and 0 <= int(position["y"]) < sweep.TARGET_HEIGHT
                    for position in positions
                )
            )


if __name__ == "__main__":
    unittest.main()
