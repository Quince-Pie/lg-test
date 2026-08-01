#!/usr/bin/env python3
"""Frozen schema-5 matched-delta raster setup predictor."""

import hashlib
import math
import zlib
from fractions import Fraction
from pathlib import Path

import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import validate_raster_tile_translation_discriminator as capture


type JsonObject = dict[str, object]

ZERO_SETUP_FMA_PHASE_LOWER = Fraction(1, 4)
ZERO_SETUP_FMA_PHASE_UPPER = Fraction(3, 8)
ZERO_CONSTANT_FMA_PHASE_LOWER = Fraction(1, 2)
ZERO_CONSTANT_FMA_PHASE_UPPER = Fraction(9, 16)
ZERO_SETUP_PREVIOUS_PHASE_LOWER = Fraction(3, 8)
ZERO_SETUP_PREVIOUS_PHASE_UPPER = Fraction(1, 2)
ZERO_CONSTANT_PREVIOUS_PHASE_LOWER = Fraction(29, 64)
ZERO_CONSTANT_PREVIOUS_PHASE_UPPER = Fraction(59, 128)
TRANSLATED_REVERSE_PHASE_LOWER = Fraction(15, 32)
TRANSLATED_REVERSE_PHASE_UPPER = Fraction(1, 2)
PREDICTION_ORDERING = (
    "sealed-case-major,all-endpoint-major,sample-position-major,"
    "record-component-major"
)
PREDICTION_ARCHIVE_PATH = Path(__file__).with_name(
    "raster_tile_translation_v3_sealed_predictions.zlib"
)
PREDICTION_ARCHIVE_SHA256 = (
    "a16090cb2eab92bf51c09b73fbef0d2319560745765f4bfbf317c57cdf2c1745"
)
PREDICTION_RAW_SHA256 = (
    "95e16a3c1b7ddf3d5a2a760eea3ae9c31aadf81a3c37eda35d76e2cee819bdc4"
)


def binary_phase(value: Fraction, precision_bits: int) -> Fraction:
    """Return the exact phase within a positive precision lattice step."""

    magnitude = abs(value)
    if magnitude == 0:
        return Fraction(0)
    exponent = v1.floor_binary_exponent(magnitude)
    step = v1.power_of_two(exponent - precision_bits + 1)
    floor_index = int(magnitude / step)
    return (magnitude - floor_index * step) / step


def is_power_of_two(value: Fraction) -> bool:
    magnitude = abs(value)
    return (
        magnitude > 0
        and magnitude.numerator & (magnitude.numerator - 1) == 0
        and magnitude.denominator & (magnitude.denominator - 1) == 0
    )


def determinant_slope(
    capture_case: capture.CaptureCase,
    endpoint: capture.EndpointCase,
    *,
    axis: int,
    selector_table: tuple[int, ...],
) -> tuple[float, Fraction, float]:
    extent = capture_case.width if axis == 0 else capture_case.height
    opposite = capture_case.height if axis == 0 else capture_case.width
    determinant = capture_case.width * capture_case.height
    delta_fraction = v1.float32_bits_fraction(
        endpoint.highBits
    ) - v1.float32_bits_fraction(endpoint.lowBits)
    internal = v1.fixed_product_slope(
        v1.bits_float32(endpoint.highBits) - v1.bits_float32(endpoint.lowBits),
        opposite_edge=opposite,
        determinant=determinant,
        reciprocal_index=v1.reciprocal_selector(determinant, selector_table),
    )
    return (
        v1.bits_float32(v1.float32_bits(internal)),
        binary_phase(delta_fraction / extent, v1.SLOPE_PRECISION_BITS),
        internal,
    )


def translated_reverse_selector(
    endpoint: capture.EndpointCase,
    setup_phase: Fraction,
) -> bool:
    """Select the observed reverse native-significand cancellation branch."""

    low = v1.float32_bits_fraction(endpoint.lowBits)
    high = v1.float32_bits_fraction(endpoint.highBits)
    if (
        high >= low
        or not TRANSLATED_REVERSE_PHASE_LOWER
        <= setup_phase
        < TRANSLATED_REVERSE_PHASE_UPPER
    ):
        return False
    native_span = endpoint.lowBits - endpoint.highBits
    lower_mantissa = endpoint.highBits & 0x7F_FFFF
    return native_span >= 30 or lower_mantissa == 0


def selected_slope(
    capture_case: capture.CaptureCase,
    endpoint: capture.EndpointCase,
    *,
    axis: int,
    selector_table: tuple[int, ...],
) -> tuple[str, float, Fraction, float]:
    rounded, phase, internal = determinant_slope(
        capture_case,
        endpoint,
        axis=axis,
        selector_table=selector_table,
    )
    if (
        endpoint.lowBits != 0
        and endpoint.highBits != 0
        and translated_reverse_selector(endpoint, phase)
    ):
        bits = v1.float32_bits(rounded)
        if bits >> 31 == 0:
            raise ValueError("the reverse cancellation selector requires a negative slope")
        return "translated-reverse-away", v1.bits_float32(bits + 1), phase, internal
    return "determinant-rounded-f32", rounded, phase, internal


def zero_physical_constant_bits(
    capture_case: capture.CaptureCase,
    endpoint: capture.EndpointCase,
    sample: capture.SamplePosition,
    *,
    setup_phase: Fraction,
    setup_internal: float,
    selector_table: tuple[int, ...],
) -> tuple[str, int, Fraction]:
    axis = sample.axis
    extent = capture_case.width if axis == 0 else capture_case.height
    opposite = capture_case.height if axis == 0 else capture_case.width
    origin = capture_case.originX if axis == 0 else capture_case.originY
    low_fraction = v1.float32_bits_fraction(endpoint.lowBits)
    high_fraction = v1.float32_bits_fraction(endpoint.highBits)
    low = float(low_fraction)
    high = float(high_fraction)
    delta = high - low
    if axis == 0 and sample.primitive == 0:
        anchor = high
        anchor_position = origin + extent
    else:
        anchor = low
        anchor_position = origin
    tile_origin = sample.tile * capture.TILE_SIZE
    displacement = tile_origin - anchor_position
    determinant = capture_case.width * capture_case.height
    reciprocal = v1.reciprocal_selector(determinant, selector_table)
    term = (
        v1.fixed_product_slope(
            math.copysign(abs(delta), delta * displacement),
            opposite_edge=opposite * abs(displacement),
            determinant=determinant,
            reciprocal_index=reciprocal,
        )
        if displacement
        else 0.0
    )
    physical = v1.float32_bits(v1.float32(anchor + term))
    exact = low_fraction + (high_fraction - low_fraction) * Fraction(
        tile_origin - origin,
        extent,
    )
    constant_phase = binary_phase(exact, 24)
    delta_fraction = high_fraction - low_fraction
    if (
        anchor != 0.0
        and is_power_of_two(delta_fraction)
        and ZERO_SETUP_FMA_PHASE_LOWER
        <= setup_phase
        < ZERO_SETUP_FMA_PHASE_UPPER
        and ZERO_CONSTANT_FMA_PHASE_LOWER
        <= constant_phase
        < ZERO_CONSTANT_FMA_PHASE_UPPER
    ):
        setup_high = v1.bits_float32(v1.float32_bits(setup_internal))
        return (
            "zero-anchor-rounded-slope-fma",
            v1.float32_bits(
                v1.float32(math.fma(float(displacement), setup_high, anchor))
            ),
            constant_phase,
        )
    if (
        anchor != 0.0
        and is_power_of_two(delta_fraction)
        and ZERO_SETUP_PREVIOUS_PHASE_LOWER
        <= setup_phase
        < ZERO_SETUP_PREVIOUS_PHASE_UPPER
        and ZERO_CONSTANT_PREVIOUS_PHASE_LOWER
        <= constant_phase
        < ZERO_CONSTANT_PREVIOUS_PHASE_UPPER
    ):
        setup_bits = v1.float32_bits(setup_internal)
        if setup_bits & 0x7FFF_FFFF <= 1:
            raise ValueError("the setup coefficient has no normal toward-zero neighbor")
        toward_zero = v1.bits_float32(setup_bits - 1)
        return (
            "zero-anchor-toward-zero-neighbor-fma",
            v1.float32_bits(
                v1.float32(math.fma(float(displacement), toward_zero, anchor))
            ),
            constant_phase,
        )
    return "zero-physical-composite", physical, constant_phase


def selected_constant_bits(
    capture_case: capture.CaptureCase,
    endpoint: capture.EndpointCase,
    sample: capture.SamplePosition,
    *,
    setup_phase: Fraction,
    setup_internal: float,
    selector_table: tuple[int, ...],
) -> tuple[str, int, Fraction | None]:
    if endpoint.lowBits != 0 and endpoint.highBits != 0:
        return (
            "translated-p28-exact-nearest",
            v2.tile_constant_bits(
                capture_case,
                endpoint,
                axis=sample.axis,
                tile=sample.tile,
            ),
            None,
        )
    return zero_physical_constant_bits(
        capture_case,
        endpoint,
        sample,
        setup_phase=setup_phase,
        setup_internal=setup_internal,
        selector_table=selector_table,
    )


def predict_record(
    capture_case: capture.CaptureCase,
    endpoint: capture.EndpointCase,
    sample: capture.SamplePosition,
    selector_table: tuple[int, ...],
) -> tuple[int, ...]:
    _, slope, setup_phase, setup_internal = selected_slope(
        capture_case,
        endpoint,
        axis=sample.axis,
        selector_table=selector_table,
    )
    _, constant_bits, _ = selected_constant_bits(
        capture_case,
        endpoint,
        sample,
        setup_phase=setup_phase,
        setup_internal=setup_internal,
        selector_table=selector_table,
    )
    return v2.predict_record_with_setup(
        sample,
        slope=slope,
        constant=v1.bits_float32(constant_bits),
    )


def case_stream(
    capture_case: capture.CaptureCase,
    selector_table: tuple[int, ...],
) -> bytes:
    result = bytearray()
    for endpoint in capture.ENDPOINTS:
        for sample in capture.sample_positions(capture_case):
            result.extend(
                capture.RECORD.pack(
                    *predict_record(
                        capture_case,
                        endpoint,
                        sample,
                        selector_table,
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


def prediction_metadata() -> JsonObject:
    combined, streams = prediction_streams()
    return {
        "ordering": PREDICTION_ORDERING,
        "caseRole": "sealed-holdout",
        "endpointRole": "all",
        "endpointCount": len(capture.ENDPOINTS),
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


def write_prediction_archive(path: Path = PREDICTION_ARCHIVE_PATH) -> JsonObject:
    raw, _ = prediction_streams()
    compressed = zlib.compress(raw, level=9)
    path.write_bytes(compressed)
    return {
        "path": str(path),
        "bytes": len(compressed),
        "sha256": hashlib.sha256(compressed).hexdigest(),
        "rawBytes": len(raw),
        "rawSha256": hashlib.sha256(raw).hexdigest(),
    }


def read_prediction_archive(path: Path = PREDICTION_ARCHIVE_PATH) -> bytes:
    compressed = path.read_bytes()
    if hashlib.sha256(compressed).hexdigest() != PREDICTION_ARCHIVE_SHA256:
        raise ValueError("schema-5 prediction archive differs")
    raw = zlib.decompress(compressed)
    metadata = prediction_metadata()
    if (
        hashlib.sha256(raw).hexdigest() != PREDICTION_RAW_SHA256
        or hashlib.sha256(raw).hexdigest() != metadata["sha256"]
        or len(raw) != metadata["bytes"]
    ):
        raise ValueError("schema-5 prediction bytes differ")
    return raw
