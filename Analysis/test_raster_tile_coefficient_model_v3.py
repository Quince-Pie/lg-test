#!/usr/bin/env python3
"""Regression tests for the measured one-column carry propagation."""

import unittest
from dataclasses import replace

import raster_tile_coefficient_model_v3 as model


class ColumnProductStageTests(unittest.TestCase):
    COMMON = {
        "multiplicand_exponent": -18,
        "multiplier_exponent": -15,
        "output_bits": 27,
        "truncation_bits": 19,
        "bias_units": 10,
        "propagated_column_count": 1,
        "sticky_carry_limit": 1,
    }

    def stage(self, multiplicand: int, multiplier: int, mode: str) -> int:
        result, _ = model.column_product_stage(
            multiplicand,
            multiplier=multiplier,
            carry_mode=mode,
            **self.COMMON,
        )
        return result

    def test_top_column_can_discard_a_lower_column_carry(self) -> None:
        multiplicand = 78_150_463
        multiplier = 11_370_496
        column = self.stage(multiplicand, multiplier, "top-columns")
        sticky = self.stage(multiplicand, multiplier, "sticky")
        aggregate = self.stage(multiplicand, multiplier, "aggregate")
        self.assertEqual(column, 105_930_510)
        self.assertEqual(sticky, column)
        self.assertEqual(aggregate, column + 1)

    def test_top_column_can_retain_more_than_one_carry_unit(self) -> None:
        multiplicand = 101_783_134
        multiplier = 14_139_392
        column = self.stage(multiplicand, multiplier, "top-columns")
        sticky = self.stage(multiplicand, multiplier, "sticky")
        aggregate = self.stage(multiplicand, multiplier, "aggregate")
        self.assertEqual(column, 85_780_122)
        self.assertEqual(column, aggregate)
        self.assertEqual(column, sticky + 1)

    def test_partial_ablation_propagates_zero_columns(self) -> None:
        policy = replace(
            model.MEASURED_POLICY,
            tile_propagated_column_count=0,
        )
        self.assertEqual(policy.tile_propagated_column_count, 0)


if __name__ == "__main__":
    unittest.main()
