#!/usr/bin/env python3
"""Integer model of Apple's two-stage raster coefficient arithmetic."""

import math

import explore_general_height as general


FIRST_STAGE_OUTPUT_BITS = 27
FIRST_STAGE_TRUNCATION_BITS = 16
FIRST_STAGE_BIAS_UNITS = (14, 15)
SECOND_STAGE_OUTPUT_BITS = 27
SECOND_STAGE_TRUNCATION_BITS = 19
SECOND_STAGE_BIAS_UNITS = 20


def partial_product_sum(
    multiplicand: int,
    multiplier: int,
    truncation_bits: int,
) -> int:
    if multiplicand <= 0 or multiplier <= 0 or truncation_bits < 0:
        raise ValueError("positive operands and a nonnegative truncation are required")
    return sum(
        ((multiplicand << bit) >> truncation_bits) << truncation_bits
        for bit in range(multiplier.bit_length())
        if multiplier & (1 << bit)
    )


def product_stage(
    multiplicand: int,
    multiplicand_lsb_exponent: int,
    multiplier: int,
    multiplier_lsb_exponent: int,
    *,
    output_bits: int,
    truncation_bits: int,
    bias_units: int,
) -> tuple[int, int]:
    product_shift = (multiplicand * multiplier).bit_length() - output_bits
    if product_shift < 0:
        raise ValueError("product does not fill the requested output precision")
    product_index = (
        partial_product_sum(multiplicand, multiplier, truncation_bits)
        + (bias_units << truncation_bits)
    ) >> product_shift
    return (
        product_index,
        multiplicand_lsb_exponent
        + multiplier_lsb_exponent
        + product_shift,
    )


def slope_bits(
    delta_bits: int,
    *,
    opposite_edge: int,
    determinant: int,
    reciprocal_index: int,
    first_stage_bias_units: int,
) -> int:
    if first_stage_bias_units not in FIRST_STAGE_BIAS_UNITS:
        raise ValueError("first-stage bias is outside the measured equivalence class")
    arithmetic = general.general.arithmetic
    delta_significand, delta_lsb_exponent = (
        general.float_significand_and_lsb_exponent(delta_bits)
    )
    edge_bits = arithmetic.float32_bits(float(opposite_edge))
    if arithmetic.float32_value(edge_bits) != opposite_edge:
        raise ValueError("opposite edge is not exactly representable in binary32")
    edge_significand, edge_lsb_exponent = (
        general.float_significand_and_lsb_exponent(edge_bits)
    )
    numerator_index, numerator_lsb_exponent = product_stage(
        delta_significand,
        delta_lsb_exponent,
        edge_significand,
        edge_lsb_exponent,
        output_bits=FIRST_STAGE_OUTPUT_BITS,
        truncation_bits=FIRST_STAGE_TRUNCATION_BITS,
        bias_units=first_stage_bias_units,
    )
    reciprocal_lsb_exponent = -(determinant - 1).bit_length() - 24
    coefficient_index, coefficient_lsb_exponent = product_stage(
        numerator_index,
        numerator_lsb_exponent,
        reciprocal_index,
        reciprocal_lsb_exponent,
        output_bits=SECOND_STAGE_OUTPUT_BITS,
        truncation_bits=SECOND_STAGE_TRUNCATION_BITS,
        bias_units=SECOND_STAGE_BIAS_UNITS,
    )
    return arithmetic.float32_bits(
        math.ldexp(coefficient_index, coefficient_lsb_exponent)
    )
