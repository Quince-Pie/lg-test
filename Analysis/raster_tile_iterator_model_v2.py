#!/usr/bin/env python3
"""Tile-center replay using the calibrated schema-13 coefficient model."""

import raster_tile_coefficient_model_v2 as coefficients
import raster_tile_iterator_model as v1
import raster_tile_selector_model as arithmetic
import raster_tile_selector_model_v2 as interpolation


def predict_record(
    capture: object,
    capture_case: object,
    endpoint: object,
    sample: object,
    selector_table: tuple[int, ...],
    *,
    policy: coefficients.CoefficientPolicy = coefficients.MEASURED_POLICY,
    force_factorized: bool = True,
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
    step = v1.significand_step(constant, v1.endpoint_step(endpoint))
    coordinate = sample.x if sample.axis == 0 else sample.y
    local_pixel = coordinate - sample.tile * capture.TILE_SIZE
    left, right = v1.quad_center_pair(local_pixel, slope, constant, step)
    pulls = interpolation.predict_record_with_setup(
        sample,
        slope=slope_float,
        constant=arithmetic.bits_float32(constant_bits),
    )[: capture.PULL_COUNT]
    return (
        *pulls,
        right if local_pixel & 1 else left,
        v1.derivative_bits(left, right),
    )
