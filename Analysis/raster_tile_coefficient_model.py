#!/usr/bin/env python3
"""Input-only model of Apple's AGX raster coefficient setup arithmetic."""

import math
from dataclasses import dataclass
from fractions import Fraction

import raster_tile_selector_model as v1
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v8 as legacy


FIRST_STAGE_OUTPUT_BITS = 27
FIRST_STAGE_TRUNCATION_BITS = 16
SLOPE_FIRST_STAGE_BIAS_UNITS = 15
CONSTANT_FIRST_STAGE_BIAS_UNITS = 15
TILE_STAGE_OUTPUT_BITS = 27
TILE_STAGE_TRUNCATION_BITS = 19
TILE_STAGE_BIAS_UNITS = 10
RECIPROCAL_STAGE_OUTPUT_BITS = 27
RECIPROCAL_STAGE_TRUNCATION_BITS = 19
RECIPROCAL_STAGE_BIAS_UNITS = 20


@dataclass(frozen=True, slots=True)
class CoefficientPolicy:
    """Measured fixed-function precisions, exposed for holdout ablations."""

    slope_first_bias: int = SLOPE_FIRST_STAGE_BIAS_UNITS
    constant_first_bias: int = CONSTANT_FIRST_STAGE_BIAS_UNITS
    tile_truncation_bits: int = TILE_STAGE_TRUNCATION_BITS
    tile_bias: int = TILE_STAGE_BIAS_UNITS
    aggregate_tile_product: bool = True
    reciprocal_truncation_bits: int = RECIPROCAL_STAGE_TRUNCATION_BITS
    reciprocal_bias: int = RECIPROCAL_STAGE_BIAS_UNITS


MEASURED_POLICY = CoefficientPolicy()


def aggregate_product_stage(
    multiplicand: int,
    multiplicand_exponent: int,
    multiplier: int,
    multiplier_exponent: int,
    *,
    output_bits: int,
    truncation_bits: int,
    bias_units: int,
) -> tuple[int, int]:
    """Truncate the aggregate product, then add the measured bias."""

    product = multiplicand * multiplier
    product_shift = product.bit_length() - output_bits
    if product_shift < 0:
        raise ValueError("product does not fill its output precision")
    truncated = (product >> truncation_bits) << truncation_bits
    return (
        (truncated + (bias_units << truncation_bits)) >> product_shift,
        multiplicand_exponent + multiplier_exponent + product_shift,
    )


def first_stage_numerator(
    capture_case: object,
    endpoint: object,
    *,
    axis: int,
    bias_units: int,
) -> tuple[int, int, int]:
    opposite = capture_case.height if axis == 0 else capture_case.width
    low = v1.bits_float32(endpoint.lowBits)
    high = v1.bits_float32(endpoint.highBits)
    delta = v1.float32(high - low)
    if delta == 0.0:
        return 0, 0, 0
    delta_index, delta_exponent = v1.float_significand_and_lsb_exponent(
        v1.float32_bits(abs(delta))
    )
    opposite_index, opposite_exponent = (
        v1.float_significand_and_lsb_exponent(
            v1.float32_bits(float(opposite))
        )
    )
    numerator_index, numerator_exponent = v1.product_stage(
        delta_index,
        delta_exponent,
        opposite_index,
        opposite_exponent,
        output_bits=FIRST_STAGE_OUTPUT_BITS,
        truncation_bits=FIRST_STAGE_TRUNCATION_BITS,
        bias_units=bias_units,
    )
    return (-1 if delta < 0.0 else 1), numerator_index, numerator_exponent


def reciprocal_stage(
    index: int,
    exponent: int,
    *,
    determinant: int,
    selector_table: tuple[int, ...],
    policy: CoefficientPolicy = MEASURED_POLICY,
) -> tuple[int, int]:
    reciprocal_index = v1.reciprocal_selector(determinant, selector_table)
    reciprocal_exponent = -(determinant - 1).bit_length() - 24
    return v1.product_stage(
        index,
        exponent,
        reciprocal_index,
        reciprocal_exponent,
        output_bits=RECIPROCAL_STAGE_OUTPUT_BITS,
        truncation_bits=policy.reciprocal_truncation_bits,
        bias_units=policy.reciprocal_bias,
    )


def determinant_slope(
    capture_case: object,
    endpoint: object,
    *,
    axis: int,
    selector_table: tuple[int, ...],
    policy: CoefficientPolicy = MEASURED_POLICY,
) -> float:
    sign, numerator_index, numerator_exponent = first_stage_numerator(
        capture_case,
        endpoint,
        axis=axis,
        bias_units=policy.slope_first_bias,
    )
    if sign == 0:
        return 0.0
    determinant = capture_case.width * capture_case.height
    index, exponent = reciprocal_stage(
        numerator_index,
        numerator_exponent,
        determinant=determinant,
        selector_table=selector_table,
        policy=policy,
    )
    return v1.bits_float32(v1.float32_bits(math.ldexp(sign * index, exponent)))


def uses_factorized_tile_path(endpoint: object) -> bool:
    low = v1.float32_bits_fraction(endpoint.lowBits)
    high = v1.float32_bits_fraction(endpoint.highBits)
    lower = min(low, high)
    upper = max(low, high)
    delta = upper - lower
    return (
        lower > 0
        and lower < Fraction(1, 2) <= upper
        and not (
            delta.numerator & (delta.numerator - 1) == 0
            and delta.denominator & (delta.denominator - 1) == 0
        )
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
    sign, numerator_index, numerator_exponent = first_stage_numerator(
        capture_case,
        endpoint,
        axis=axis,
        bias_units=policy.constant_first_bias,
    )
    if sign == 0 or displacement == 0:
        return Fraction(0)
    distance_index, distance_exponent = v1.float_significand_and_lsb_exponent(
        v1.float32_bits(float(abs(displacement)))
    )
    middle_stage = (
        aggregate_product_stage
        if policy.aggregate_tile_product
        else v1.product_stage
    )
    middle_index, middle_exponent = middle_stage(
        numerator_index,
        numerator_exponent,
        distance_index,
        distance_exponent,
        output_bits=TILE_STAGE_OUTPUT_BITS,
        truncation_bits=policy.tile_truncation_bits,
        bias_units=policy.tile_bias,
    )
    determinant = capture_case.width * capture_case.height
    index, exponent = reciprocal_stage(
        middle_index,
        middle_exponent,
        determinant=determinant,
        selector_table=selector_table,
        policy=policy,
    )
    value = Fraction(index) * v1.power_of_two(exponent)
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
    value = v1.float32_bits_fraction(anchor_bits) + tile_term(
        capture_case,
        endpoint,
        axis=axis,
        displacement=displacement,
        selector_table=selector_table,
        policy=policy,
    )
    return v4.quantize_composite_constant_bits(value)


def physical_constant_bits(
    capture_case: object,
    endpoint: object,
    sample: object,
    *,
    selector_table: tuple[int, ...],
    policy: CoefficientPolicy = MEASURED_POLICY,
    force_factorized: bool | None = None,
) -> int:
    factorized = (
        uses_factorized_tile_path(endpoint)
        if force_factorized is None
        else force_factorized
    )
    if not factorized:
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
