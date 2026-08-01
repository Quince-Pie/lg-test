#!/usr/bin/env python3
"""Input-only model of AGX tile-center and derivative evaluation."""

from fractions import Fraction

import raster_tile_coefficient_model as coefficients
import raster_tile_selector_model as arithmetic
import raster_tile_selector_model_v2 as interpolation


CENTER_PRECISION_BITS = 36


def toward_zero_float32_bits(value: Fraction) -> int:
    """Round a finite rational toward zero to binary32."""

    if value == 0:
        return 0
    bits = arithmetic.round_fraction_to_float32_bits(value)
    rounded = arithmetic.float32_bits_fraction(bits)
    if (value > 0 and rounded > value) or (value < 0 and rounded < value):
        bits -= 1
    return bits


def endpoint_step(endpoint: object) -> Fraction:
    low = abs(arithmetic.float32_bits_fraction(endpoint.lowBits))
    high = abs(arithmetic.float32_bits_fraction(endpoint.highBits))
    scale = max(low, high)
    return arithmetic.power_of_two(
        arithmetic.floor_binary_exponent(scale) - CENTER_PRECISION_BITS + 1
    )


def significand_step(value: Fraction, fallback: Fraction) -> Fraction:
    if value == 0:
        return fallback
    return arithmetic.power_of_two(
        arithmetic.floor_binary_exponent(abs(value))
        - CENTER_PRECISION_BITS
        + 1
    )


def quad_center_pair(
    local_pixel: int,
    slope: Fraction,
    constant: Fraction,
    step: Fraction,
) -> tuple[int, int]:
    quad_local = local_pixel & ~1
    exact_base = constant + Fraction(2 * quad_local + 1, 2) * slope
    index = exact_base // step
    left = index * step
    right = left + slope
    return toward_zero_float32_bits(left), toward_zero_float32_bits(right)


def derivative_bits(left_bits: int, right_bits: int) -> int:
    return arithmetic.float32_bits(
        arithmetic.float32(
            arithmetic.bits_float32(right_bits)
            - arithmetic.bits_float32(left_bits)
        )
    )


def predict_record(
    capture: object,
    capture_case: object,
    endpoint: object,
    sample: object,
    selector_table: tuple[int, ...],
    *,
    policy: coefficients.CoefficientPolicy = coefficients.MEASURED_POLICY,
    force_factorized: bool | None = None,
) -> tuple[int, ...]:
    slope_float = coefficients.determinant_slope(
        capture_case,
        endpoint,
        axis=sample.axis,
        selector_table=selector_table,
        policy=policy,
    )
    slope = arithmetic.float32_bits_fraction(
        arithmetic.float32_bits(slope_float)
    )
    constant_bits = coefficients.physical_constant_bits(
        capture_case,
        endpoint,
        sample,
        selector_table=selector_table,
        policy=policy,
        force_factorized=force_factorized,
    )
    constant = arithmetic.float32_bits_fraction(constant_bits)
    step = significand_step(constant, endpoint_step(endpoint))
    coordinate = sample.x if sample.axis == 0 else sample.y
    local_pixel = coordinate - sample.tile * capture.TILE_SIZE
    left, right = quad_center_pair(local_pixel, slope, constant, step)
    pulls = interpolation.predict_record_with_setup(
        sample,
        slope=slope_float,
        constant=arithmetic.bits_float32(constant_bits),
    )[: capture.PULL_COUNT]
    return (
        *pulls,
        right if local_pixel & 1 else left,
        derivative_bits(left, right),
    )
