#!/usr/bin/env python3
"""AGX raster coefficient arithmetic with measured carry-column propagation."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

import raster_tile_coefficient_model as v1
import raster_tile_selector_model as arithmetic
import raster_tile_selector_model_v4 as composite
import raster_tile_selector_model_v8 as legacy


type TileCarryMode = Literal["top-columns", "sticky", "aggregate"]


@dataclass(frozen=True, slots=True)
class CoefficientPolicy:
    """Measured parameters plus explicit discarded-column alternatives."""

    slope_first_bias: int = v1.SLOPE_FIRST_STAGE_BIAS_UNITS
    constant_first_bias: int = v1.CONSTANT_FIRST_STAGE_BIAS_UNITS
    tile_truncation_bits: int = v1.TILE_STAGE_TRUNCATION_BITS
    tile_bias: int = v1.TILE_STAGE_BIAS_UNITS
    tile_carry_mode: TileCarryMode = "top-columns"
    tile_propagated_column_count: int = 1
    tile_sticky_carry_limit: int = 1
    reciprocal_truncation_bits: int = v1.RECIPROCAL_STAGE_TRUNCATION_BITS
    reciprocal_bias: int = v1.RECIPROCAL_STAGE_BIAS_UNITS


MEASURED_POLICY = CoefficientPolicy()


def propagated_discarded_carry(
    multiplicand: int,
    multiplier: int,
    truncation_bits: int,
    propagated_column_count: int,
) -> int:
    """Propagate carry through the selected highest discarded columns."""

    if not 0 <= propagated_column_count <= truncation_bits:
        raise ValueError("propagated column count is outside the discarded range")
    cutoff = truncation_bits - propagated_column_count
    low_mask = (1 << truncation_bits) - 1
    remainders = tuple(
        (multiplicand << bit) & low_mask
        for bit in range(multiplier.bit_length())
        if multiplier & (1 << bit)
    )
    carry = 0
    for column in range(cutoff, truncation_bits):
        column_total = carry + sum(
            (remainder >> column) & 1 for remainder in remainders
        )
        carry = column_total >> 1
    return carry


def column_product_stage(
    multiplicand: int,
    multiplicand_exponent: int,
    multiplier: int,
    multiplier_exponent: int,
    *,
    output_bits: int,
    truncation_bits: int,
    bias_units: int,
    carry_mode: TileCarryMode,
    propagated_column_count: int,
    sticky_carry_limit: int,
) -> tuple[int, int]:
    """Truncate partial products and apply the selected carry propagation."""

    product = multiplicand * multiplier
    product_shift = product.bit_length() - output_bits
    if product_shift < 0:
        raise ValueError("product does not fill its output precision")
    partial = arithmetic.partial_product_sum(
        multiplicand,
        multiplier,
        truncation_bits,
    )
    aggregate_units = product >> truncation_bits
    partial_units = partial >> truncation_bits
    discarded_carry = aggregate_units - partial_units
    if discarded_carry < 0:
        raise ValueError("partial products exceed the aggregate product")
    match carry_mode:
        case "top-columns":
            retained_carry = propagated_discarded_carry(
                multiplicand,
                multiplier,
                truncation_bits,
                propagated_column_count,
            )
        case "sticky":
            retained_carry = min(discarded_carry, sticky_carry_limit)
        case "aggregate":
            retained_carry = discarded_carry
    adjusted = partial + ((retained_carry + bias_units) << truncation_bits)
    return (
        adjusted >> product_shift,
        multiplicand_exponent + multiplier_exponent + product_shift,
    )


def determinant_slope(
    capture_case: object,
    endpoint: object,
    *,
    axis: int,
    selector_table: tuple[int, ...],
    policy: CoefficientPolicy = MEASURED_POLICY,
) -> float:
    return v1.determinant_slope(
        capture_case,
        endpoint,
        axis=axis,
        selector_table=selector_table,
        policy=policy,
    )


def tile_term(
    capture_case: object,
    endpoint: object,
    *,
    axis: int,
    displacement: int,
    selector_table: tuple[int, ...],
    policy: CoefficientPolicy = MEASURED_POLICY,
) -> Fraction:
    sign, numerator_index, numerator_exponent = v1.first_stage_numerator(
        capture_case,
        endpoint,
        axis=axis,
        bias_units=policy.constant_first_bias,
    )
    if sign == 0 or displacement == 0:
        return Fraction(0)
    distance_index, distance_exponent = (
        arithmetic.float_significand_and_lsb_exponent(
            arithmetic.float32_bits(float(abs(displacement)))
        )
    )
    middle_index, middle_exponent = column_product_stage(
        numerator_index,
        numerator_exponent,
        distance_index,
        distance_exponent,
        output_bits=v1.TILE_STAGE_OUTPUT_BITS,
        truncation_bits=policy.tile_truncation_bits,
        bias_units=policy.tile_bias,
        carry_mode=policy.tile_carry_mode,
        propagated_column_count=policy.tile_propagated_column_count,
        sticky_carry_limit=policy.tile_sticky_carry_limit,
    )
    determinant = capture_case.width * capture_case.height
    index, exponent = v1.reciprocal_stage(
        middle_index,
        middle_exponent,
        determinant=determinant,
        selector_table=selector_table,
        policy=policy,
    )
    value = Fraction(index) * arithmetic.power_of_two(exponent)
    return -value if sign * displacement < 0 else value


def factorized_constant_bits(
    capture_case: object,
    endpoint: object,
    sample: object,
    *,
    selector_table: tuple[int, ...],
    policy: CoefficientPolicy = MEASURED_POLICY,
) -> int:
    axis = sample.axis
    extent = capture_case.width if axis == 0 else capture_case.height
    origin = capture_case.originX if axis == 0 else capture_case.originY
    if axis == 0 and sample.primitive == 0:
        anchor_bits = endpoint.highBits
        anchor_position = origin + extent
    else:
        anchor_bits = endpoint.lowBits
        anchor_position = origin
    displacement = sample.tile * 32 - anchor_position
    value = arithmetic.float32_bits_fraction(anchor_bits) + tile_term(
        capture_case,
        endpoint,
        axis=axis,
        displacement=displacement,
        selector_table=selector_table,
        policy=policy,
    )
    return composite.quantize_composite_constant_bits(value)


def physical_constant_bits(
    capture_case: object,
    endpoint: object,
    sample: object,
    *,
    selector_table: tuple[int, ...],
    policy: CoefficientPolicy = MEASURED_POLICY,
    force_factorized: bool = True,
) -> int:
    if not force_factorized:
        return legacy.physical_constant_bits(
            capture_case,
            endpoint,
            sample,
            selector_table=selector_table,
        )
    return factorized_constant_bits(
        capture_case,
        endpoint,
        sample,
        selector_table=selector_table,
        policy=policy,
    )
