#!/usr/bin/env python3
"""Frozen predictor for the schema-4 dense phase-boundary holdout."""

import hashlib
import math
from fractions import Fraction

import raster_tile_selector_model as v1
import validate_raster_tile_phase_holdout as capture


SLOPE_PRECISION_BITS = v1.SLOPE_PRECISION_BITS
CONSTANT_PRECISION_BITS = v1.CONSTANT_PRECISION_BITS
SLOPE_PHASE_FIXED_LOWER = Fraction(3, 8)
SLOPE_PHASE_FIXED_UPPER = Fraction(1, 2)
SLOPE_PHASE_NEAREST_LOWER = Fraction(9, 16)
SLOPE_PHASE_NEAREST_UPPER = Fraction(3, 4)
SLOPE_PHASE_FIXED_TOP = Fraction(15, 16)
PREDICTION_ORDERING = (
    "sealed-case-major,selector-endpoint-major,sample-position-major,"
    "record-component-major"
)


def selected_slope(
    capture_case: capture.CaptureCase,
    endpoint: capture.EndpointCase,
    *,
    axis: int,
    selector_table: tuple[int, ...],
) -> tuple[str, float, Fraction]:
    extent = capture_case.width if axis == 0 else capture_case.height
    opposite_edge = capture_case.height if axis == 0 else capture_case.width
    delta = v1.float32_bits_fraction(endpoint.highBits) - v1.float32_bits_fraction(
        endpoint.lowBits
    )
    if delta == 0:
        return "zero", 0.0, Fraction(0)
    magnitude = abs(delta) / extent
    exponent = v1.floor_binary_exponent(magnitude)
    step = v1.power_of_two(exponent - SLOPE_PRECISION_BITS + 1)
    floor_value = v1.quantize_binary_significand(
        magnitude,
        SLOPE_PRECISION_BITS,
        rounding="down",
    )
    phase = (magnitude - floor_value) / step
    sign = -1 if delta < 0 else 1
    if (
        SLOPE_PHASE_FIXED_LOWER <= phase < SLOPE_PHASE_FIXED_UPPER
        or phase >= SLOPE_PHASE_FIXED_TOP
    ):
        determinant = capture_case.width * capture_case.height
        return (
            "fixed-product",
            v1.fixed_product_slope(
                v1.bits_float32(endpoint.highBits) - v1.bits_float32(endpoint.lowBits),
                opposite_edge=opposite_edge,
                determinant=determinant,
                reciprocal_index=v1.reciprocal_selector(
                    determinant,
                    selector_table,
                ),
            ),
            phase,
        )
    if SLOPE_PHASE_NEAREST_LOWER <= phase < SLOPE_PHASE_NEAREST_UPPER:
        nearest = v1.quantize_binary_significand(
            magnitude,
            SLOPE_PRECISION_BITS,
            rounding="nearest-even",
        )
        return "nearest-middle", float(sign * nearest), phase
    return "strict-below-floor", float(sign * (floor_value - step)), phase


def tile_constant_bits(
    capture_case: capture.CaptureCase,
    endpoint: capture.EndpointCase,
    *,
    axis: int,
    tile: int,
) -> int:
    return v1.tile_constant_bits(
        capture_case,
        endpoint,
        axis=axis,
        tile=tile,
    )


def predict_record_with_setup(
    sample: capture.SamplePosition,
    *,
    slope: float,
    constant: float,
) -> tuple[int, ...]:
    coordinate = sample.x if sample.axis == 0 else sample.y
    local_pixel = coordinate - sample.tile * capture.TILE_SIZE
    pulls = tuple(
        v1.float32_bits(
            v1.float32(math.fma(local_pixel + numerator / 16, slope, constant))
        )
        for numerator in capture.PULL_NUMERATORS
    )
    position = local_pixel + 0.5
    return (
        *pulls,
        v1.center_bits(position, slope, constant),
        v1.derivative_bits(local_pixel, position, slope, constant),
    )


def case_stream(
    capture_case: capture.CaptureCase,
    selector_table: tuple[int, ...],
) -> bytes:
    result = bytearray()
    samples = capture.sample_positions(capture_case)
    for endpoint in capture.ENDPOINTS:
        if endpoint.role != "selector-discovery":
            continue
        slopes = {
            axis: selected_slope(
                capture_case,
                endpoint,
                axis=axis,
                selector_table=selector_table,
            )[1]
            for axis in range(capture.AXIS_COUNT)
        }
        constants = {
            (sample.axis, sample.tile): v1.bits_float32(
                tile_constant_bits(
                    capture_case,
                    endpoint,
                    axis=sample.axis,
                    tile=sample.tile,
                )
            )
            for sample in samples
        }
        for sample in samples:
            result.extend(
                capture.RECORD.pack(
                    *predict_record_with_setup(
                        sample,
                        slope=slopes[sample.axis],
                        constant=constants[(sample.axis, sample.tile)],
                    )
                )
            )
    return bytes(result)


def prediction_streams(
    *,
    role: str = "sealed-holdout",
) -> tuple[bytes, dict[str, bytes]]:
    selector_table = v1.load_selector_table()
    streams = {
        capture_case.name: case_stream(capture_case, selector_table)
        for capture_case in capture.CASES
        if capture_case.role == role
    }
    return b"".join(streams.values()), streams


def prediction_metadata() -> dict[str, object]:
    combined, streams = prediction_streams()
    endpoint_count = sum(
        endpoint.role == "selector-discovery" for endpoint in capture.ENDPOINTS
    )
    return {
        "ordering": PREDICTION_ORDERING,
        "caseRole": "sealed-holdout",
        "endpointRole": "selector-discovery",
        "endpointCount": endpoint_count,
        "recordComponentCount": capture.RECORD_COMPONENT_COUNT,
        "recordBytes": capture.RECORD.size,
        "recordCount": len(combined) // capture.RECORD.size,
        "bytes": len(combined),
        "sha256": hashlib.sha256(combined).hexdigest(),
        "cases": [
            {
                "name": name,
                "recordCount": len(stream) // capture.RECORD.size,
                "bytes": len(stream),
                "sha256": hashlib.sha256(stream).hexdigest(),
            }
            for name, stream in streams.items()
        ],
    }
