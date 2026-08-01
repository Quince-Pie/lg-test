#!/usr/bin/env python3
"""Regression tests for the calibrated discarded-column carry."""

import unittest

import raster_tile_coefficient_model_v2 as model


class StickyProductStageTests(unittest.TestCase):
    def test_retains_one_discarded_carry_only(self) -> None:
        common = {
            "multiplicand_exponent": -18,
            "multiplier_exponent": -15,
            "output_bits": 27,
            "truncation_bits": 19,
            "bias_units": 10,
        }
        sticky, _ = model.sticky_product_stage(
            78_150_463,
            multiplier=11_370_496,
            discarded_carry_limit=1,
            **common,
        )
        partial, _ = model.sticky_product_stage(
            78_150_463,
            multiplier=11_370_496,
            discarded_carry_limit=0,
            **common,
        )
        aggregate, _ = model.sticky_product_stage(
            78_150_463,
            multiplier=11_370_496,
            discarded_carry_limit=None,
            **common,
        )
        self.assertEqual(sticky, 105_930_510)
        self.assertEqual(partial, sticky)
        self.assertEqual(aggregate, sticky + 1)

    def test_sticky_carry_crosses_when_one_unit_is_sufficient(self) -> None:
        common = {
            "multiplicand_exponent": -18,
            "multiplier_exponent": -15,
            "output_bits": 27,
            "truncation_bits": 19,
            "bias_units": 10,
        }
        sticky, _ = model.sticky_product_stage(
            78_150_463,
            multiplier=11_108_352,
            discarded_carry_limit=1,
            **common,
        )
        partial, _ = model.sticky_product_stage(
            78_150_463,
            multiplier=11_108_352,
            discarded_carry_limit=0,
            **common,
        )
        aggregate, _ = model.sticky_product_stage(
            78_150_463,
            multiplier=11_108_352,
            discarded_carry_limit=None,
            **common,
        )
        self.assertEqual(sticky, aggregate)
        self.assertEqual(sticky, partial + 1)


if __name__ == "__main__":
    unittest.main()
