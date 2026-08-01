#!/usr/bin/env python3
"""Frozen predictor for the schema-3 near-equal tile-selector holdout."""

import hashlib
import math
import struct
import zlib
from fractions import Fraction
from pathlib import Path

import validate_raster_tile_numerator as capture


SLOPE_PRECISION_BITS = 27
CONSTANT_PRECISION_BITS = 28
SLOPE_PHASE_MIDDLE_LOWER = Fraction(3, 8)
SLOPE_PHASE_MIDDLE_UPPER = Fraction(1, 2)
SLOPE_PHASE_UPPER = Fraction(15, 16)
FIRST_STAGE_OUTPUT_BITS = 27
FIRST_STAGE_TRUNCATION_BITS = 16
FIRST_STAGE_BIAS_UNITS = 14
SECOND_STAGE_OUTPUT_BITS = 27
SECOND_STAGE_TRUNCATION_BITS = 19
SECOND_STAGE_BIAS_UNITS = 20
SELECTOR_TABLE_PATH = Path(__file__).with_name(
    "raster_fractional_subpixel_resolved_selectors.zlib"
)
SELECTOR_TABLE_COMPRESSED_SHA256 = (
    "2b49309da4283726cc894f7aada3c25db41cf8ca71a4c278c952407e9e1eedd3"
)
SELECTOR_TABLE_RAW_SHA256 = (
    "b0990c2ce17fff5ebf06124497a38d38c9cf22e7e9210ccb6f95adb2c6834d53"
)
SELECTOR_TABLE_COUNT = 2_097_153
PREDICTION_ORDERING = (
    "sealed-case-major,selector-endpoint-major,sample-position-major,"
    "record-component-major"
)
RECORD = struct.Struct(f"<{capture.RECORD_COMPONENT_COUNT}I")


def power_of_two(exponent: int) -> Fraction:
    return Fraction(1 << exponent) if exponent >= 0 else Fraction(1, 1 << -exponent)


def float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def float32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def bits_float32(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def float32_bits_fraction(bits: int) -> Fraction:
    sign = -1 if bits & 0x8000_0000 else 1
    exponent = (bits >> 23) & 0xFF
    significand = bits & 0x7F_FFFF
    if exponent == 0xFF:
        raise ValueError("non-finite binary32 has no rational value")
    if exponent == 0:
        return sign * significand * power_of_two(-149)
    return sign * ((1 << 23) | significand) * power_of_two(exponent - 150)


def floor_binary_exponent(value: Fraction) -> int:
    if value <= 0:
        raise ValueError("binary exponent requires a positive value")
    exponent = value.numerator.bit_length() - value.denominator.bit_length()
    return exponent - (value < power_of_two(exponent))


def round_fraction_to_integer_nearest_even(value: Fraction) -> int:
    if value < 0:
        return -round_fraction_to_integer_nearest_even(-value)
    quotient, remainder = divmod(value.numerator, value.denominator)
    doubled = 2 * remainder
    return quotient + (
        doubled > value.denominator
        or (doubled == value.denominator and bool(quotient & 1))
    )


def quantize_binary_significand(
    value: Fraction,
    precision_bits: int,
    *,
    rounding: str,
) -> Fraction:
    if value <= 0 or precision_bits < 2:
        raise ValueError("a positive value and at least two bits are required")
    exponent = floor_binary_exponent(value)
    step = power_of_two(exponent - precision_bits + 1)
    scaled = value / step
    quotient, remainder = divmod(scaled.numerator, scaled.denominator)
    if rounding == "nearest-even":
        quotient = round_fraction_to_integer_nearest_even(scaled)
    elif rounding == "up":
        quotient += bool(remainder)
    elif rounding != "down":
        raise ValueError(f"unknown rounding mode: {rounding}")
    return quotient * step


def round_fraction_to_float32_bits(value: Fraction) -> int:
    if value == 0:
        return 0
    sign = 0x8000_0000 if value < 0 else 0
    rounded = quantize_binary_significand(
        abs(value),
        24,
        rounding="nearest-even",
    )
    exponent = floor_binary_exponent(rounded)
    significand = int(rounded / power_of_two(exponent - 23))
    if significand == 1 << 24:
        significand >>= 1
        exponent += 1
    if not 1 << 23 <= significand < 1 << 24 or not -126 <= exponent <= 127:
        raise ValueError("prediction is outside the normal binary32 range")
    return sign | ((exponent + 127) << 23) | (significand - (1 << 23))


def load_selector_table() -> tuple[int, ...]:
    compressed = SELECTOR_TABLE_PATH.read_bytes()
    if hashlib.sha256(compressed).hexdigest() != SELECTOR_TABLE_COMPRESSED_SHA256:
        raise ValueError("fractional selector archive differs")
    raw = zlib.decompress(compressed)
    if hashlib.sha256(raw).hexdigest() != SELECTOR_TABLE_RAW_SHA256:
        raise ValueError("fractional selector table differs")
    if len(raw) != SELECTOR_TABLE_COUNT * 4:
        raise ValueError("fractional selector table length differs")
    return struct.unpack(f"<{SELECTOR_TABLE_COUNT}I", raw)


def reciprocal_selector(determinant: int, table: tuple[int, ...]) -> int:
    exponent = determinant.bit_length() - 1
    if determinant <= 0 or exponent > 23:
        raise ValueError("determinant is outside the measured selector domain")
    normalized = determinant << (23 - exponent)
    mantissa = normalized - (1 << 23)
    quantized = ((mantissa + 2) // 4) * 4
    return table[quantized // 4]


def float_significand_and_lsb_exponent(bits: int) -> tuple[int, int]:
    exponent = (bits >> 23) & 0xFF
    if bits >> 31 or not 0 < exponent < 0xFF:
        raise ValueError("a positive normal binary32 is required")
    return (1 << 23) | (bits & 0x7F_FFFF), exponent - 150


def partial_product_sum(
    multiplicand: int,
    multiplier: int,
    truncation_bits: int,
) -> int:
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
        raise ValueError("product does not fill its output precision")
    index = (
        partial_product_sum(multiplicand, multiplier, truncation_bits)
        + (bias_units << truncation_bits)
    ) >> product_shift
    return (
        index,
        multiplicand_lsb_exponent + multiplier_lsb_exponent + product_shift,
    )


def fixed_product_slope(
    delta: float,
    *,
    opposite_edge: int,
    determinant: int,
    reciprocal_index: int,
) -> float:
    sign = -1.0 if delta < 0 else 1.0
    delta_significand, delta_exponent = float_significand_and_lsb_exponent(
        float32_bits(float32(abs(delta)))
    )
    edge_significand, edge_exponent = float_significand_and_lsb_exponent(
        float32_bits(float(opposite_edge))
    )
    numerator_index, numerator_exponent = product_stage(
        delta_significand,
        delta_exponent,
        edge_significand,
        edge_exponent,
        output_bits=FIRST_STAGE_OUTPUT_BITS,
        truncation_bits=FIRST_STAGE_TRUNCATION_BITS,
        bias_units=FIRST_STAGE_BIAS_UNITS,
    )
    reciprocal_exponent = -(determinant - 1).bit_length() - 24
    coefficient_index, coefficient_exponent = product_stage(
        numerator_index,
        numerator_exponent,
        reciprocal_index,
        reciprocal_exponent,
        output_bits=SECOND_STAGE_OUTPUT_BITS,
        truncation_bits=SECOND_STAGE_TRUNCATION_BITS,
        bias_units=SECOND_STAGE_BIAS_UNITS,
    )
    return math.copysign(math.ldexp(coefficient_index, coefficient_exponent), sign)


def selected_slope(
    capture_case: capture.CaptureCase,
    endpoint: capture.EndpointCase,
    *,
    axis: int,
    selector_table: tuple[int, ...],
) -> tuple[str, float, Fraction]:
    extent = capture_case.width if axis == 0 else capture_case.height
    opposite_edge = capture_case.height if axis == 0 else capture_case.width
    delta = float32_bits_fraction(endpoint.highBits) - float32_bits_fraction(
        endpoint.lowBits
    )
    if delta == 0:
        return "zero", 0.0, Fraction(0)
    magnitude = abs(delta) / extent
    exponent = floor_binary_exponent(magnitude)
    step = power_of_two(exponent - SLOPE_PRECISION_BITS + 1)
    floor_value = quantize_binary_significand(
        magnitude,
        SLOPE_PRECISION_BITS,
        rounding="down",
    )
    phase = (magnitude - floor_value) / step
    fixed_product = (
        SLOPE_PHASE_MIDDLE_LOWER <= phase < SLOPE_PHASE_MIDDLE_UPPER
        or phase >= SLOPE_PHASE_UPPER
    )
    if fixed_product:
        determinant = capture_case.width * capture_case.height
        return (
            "fixed-product",
            fixed_product_slope(
                bits_float32(endpoint.highBits) - bits_float32(endpoint.lowBits),
                opposite_edge=opposite_edge,
                determinant=determinant,
                reciprocal_index=reciprocal_selector(determinant, selector_table),
            ),
            phase,
        )
    sign = -1 if delta < 0 else 1
    return "strict-below-floor", float(sign * (floor_value - step)), phase


def tile_constant_bits(
    capture_case: capture.CaptureCase,
    endpoint: capture.EndpointCase,
    *,
    axis: int,
    tile: int,
) -> int:
    extent = capture_case.width if axis == 0 else capture_case.height
    origin = capture_case.originX if axis == 0 else capture_case.originY
    displacement = tile * capture.TILE_SIZE - origin
    low = float32_bits_fraction(endpoint.lowBits)
    high = float32_bits_fraction(endpoint.highBits)
    exact = low + (high - low) * displacement / extent
    if exact == 0:
        return 0
    quantized = quantize_binary_significand(
        abs(exact),
        CONSTANT_PRECISION_BITS,
        rounding="nearest-even",
    )
    return round_fraction_to_float32_bits(-quantized if exact < 0 else quantized)


def round_toward_zero_float32(value: float) -> float:
    rounded = float32(value)
    if (value > 0 and rounded > value) or (value < 0 and rounded < value):
        bits = float32_bits(rounded)
        if bits & 0x7FFF_FFFF == 0:
            return rounded
        rounded = bits_float32(bits - 1)
    return rounded


def center_bits(position: float, slope: float, constant: float) -> int:
    return float32_bits(round_toward_zero_float32(position * slope + constant))


def derivative_bits(
    local_pixel: int,
    position: float,
    slope: float,
    constant: float,
) -> int:
    if local_pixel & 1:
        left_position, right_position = position - 1.0, position
    else:
        left_position, right_position = position, position + 1.0
    left = bits_float32(center_bits(left_position, slope, constant))
    right = bits_float32(center_bits(right_position, slope, constant))
    return float32_bits(float32(right - left))


def predict_record(
    capture_case: capture.CaptureCase,
    endpoint: capture.EndpointCase,
    sample: capture.SamplePosition,
    selector_table: tuple[int, ...],
) -> tuple[int, ...]:
    axis = sample.axis
    coordinate = sample.x if axis == 0 else sample.y
    local_pixel = coordinate - sample.tile * capture.TILE_SIZE
    _, slope, _ = selected_slope(
        capture_case,
        endpoint,
        axis=axis,
        selector_table=selector_table,
    )
    constant = bits_float32(
        tile_constant_bits(capture_case, endpoint, axis=axis, tile=sample.tile)
    )
    pulls = tuple(
        float32_bits(float32(math.fma(local_pixel + numerator / 16, slope, constant)))
        for numerator in capture.PULL_NUMERATORS
    )
    position = local_pixel + 0.5
    return (
        *pulls,
        center_bits(position, slope, constant),
        derivative_bits(local_pixel, position, slope, constant),
    )


def prediction_streams() -> tuple[bytes, dict[str, bytes]]:
    selector_table = load_selector_table()
    streams: dict[str, bytes] = {}
    for capture_case in capture.CASES:
        if capture_case.role != "sealed-holdout":
            continue
        case_stream = bytearray()
        for endpoint in capture.ENDPOINTS:
            if endpoint.role != "selector-discovery":
                continue
            for sample in capture.sample_positions(capture_case):
                case_stream.extend(
                    RECORD.pack(
                        *predict_record(
                            capture_case,
                            endpoint,
                            sample,
                            selector_table,
                        )
                    )
                )
        streams[capture_case.name] = bytes(case_stream)
    return b"".join(streams.values()), streams


def prediction_metadata() -> dict[str, object]:
    combined, streams = prediction_streams()
    endpoint_count = sum(
        endpoint.role == "selector-discovery" for endpoint in capture.ENDPOINTS
    )
    return {
        "ordering": PREDICTION_ORDERING,
        "endpointRole": "selector-discovery",
        "endpointCount": endpoint_count,
        "recordComponentCount": capture.RECORD_COMPONENT_COUNT,
        "recordBytes": RECORD.size,
        "recordCount": len(combined) // RECORD.size,
        "bytes": len(combined),
        "sha256": hashlib.sha256(combined).hexdigest(),
        "cases": [
            {
                "name": name,
                "recordCount": len(stream) // RECORD.size,
                "bytes": len(stream),
                "sha256": hashlib.sha256(stream).hexdigest(),
            }
            for name, stream in streams.items()
        ],
    }
