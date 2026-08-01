#!/usr/bin/env python3
"""Frozen schema-6 model of Apple tile setup and center interpolation."""

import hashlib
import math
import zlib
from collections import Counter
from fractions import Fraction
from pathlib import Path
from types import ModuleType
from typing import Any

import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import validate_raster_tile_double_rounding_holdout as capture


type JsonObject = dict[str, Any]

CONSTANT_INTERNAL_PRECISION_BITS = 28
FORWARD_CENTER_PHASE_UPPER = Fraction(1, 8)
FORWARD_PULL_NATIVE_SPAN_LOWER = 8
REVERSE_PHASE_LOWER = Fraction(15, 32)
REVERSE_PHASE_UPPER = Fraction(1, 2)
REVERSE_NATIVE_SPAN_LOWER = 30
PREDICTION_ORDERING = (
    "sealed-case-major,all-endpoint-major,sample-position-major,record-component-major"
)
PREDICTION_ARCHIVE_PATH = Path(__file__).with_name(
    "raster_tile_v4_sealed_predictions.zlib"
)
PREDICTION_ARCHIVE_SHA256 = (
    "3b583f133a822bdfeed9e643bbef3543ad6b7b11d2fceae8aeb94b8823313144"
)
PREDICTION_RAW_SHA256 = (
    "14b52a038113e7dfa3c404beaaf81702674a4bcad3fc3a537d236e8b0cd580d5"
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


def determinant_slope(
    capture_case: object,
    endpoint: object,
    *,
    axis: int,
    selector_table: tuple[int, ...],
) -> tuple[int, Fraction, float]:
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
        v1.float32_bits(internal),
        binary_phase(delta_fraction / extent, v1.SLOPE_PRECISION_BITS),
        internal,
    )


def selected_slope_bits(
    capture_case: object,
    endpoint: object,
    *,
    axis: int,
    selector_table: tuple[int, ...],
) -> tuple[str, int, str, int, Fraction, float]:
    """Select independent pull and center coefficients from input bits only."""

    base_bits, phase, internal = determinant_slope(
        capture_case,
        endpoint,
        axis=axis,
        selector_table=selector_table,
    )
    pull_name = "determinant-rounded-f32"
    center_name = "determinant-rounded-f32"
    pull_bits = base_bits
    center_bits = base_bits
    if endpoint.lowBits == 0 or endpoint.highBits == 0:
        return pull_name, pull_bits, center_name, center_bits, phase, internal

    low = v1.float32_bits_fraction(endpoint.lowBits)
    high = v1.float32_bits_fraction(endpoint.highBits)
    if high > low and phase < FORWARD_CENTER_PHASE_UPPER:
        if base_bits >> 31:
            raise ValueError("the forward selector requires a positive coefficient")
        center_name = "translated-forward-center-toward-zero"
        center_bits -= 1
        if endpoint.highBits - endpoint.lowBits >= FORWARD_PULL_NATIVE_SPAN_LOWER:
            pull_name = "translated-forward-pull-toward-zero"
            pull_bits -= 1
    elif high < low and REVERSE_PHASE_LOWER <= phase < REVERSE_PHASE_UPPER:
        native_span = endpoint.lowBits - endpoint.highBits
        lower_mantissa = endpoint.highBits & 0x7F_FFFF
        if native_span >= REVERSE_NATIVE_SPAN_LOWER or lower_mantissa == 0:
            if base_bits >> 31 == 0:
                raise ValueError("the reverse selector requires a negative coefficient")
            pull_name = "translated-reverse-away"
            center_name = "translated-reverse-away"
            pull_bits += 1
            center_bits += 1
    return pull_name, pull_bits, center_name, center_bits, phase, internal


def quantize_composite_constant_bits(value: Fraction) -> int:
    """Apply the observed 28-bit-nearest then binary32-nearest double rounding."""

    if value == 0:
        return 0
    internal = v1.quantize_binary_significand(
        abs(value),
        CONSTANT_INTERNAL_PRECISION_BITS,
        rounding="nearest-even",
    )
    return v1.round_fraction_to_float32_bits(-internal if value < 0 else internal)


def translated_constant_bits(
    capture_case: object,
    endpoint: object,
    sample: object,
) -> int:
    extent = capture_case.width if sample.axis == 0 else capture_case.height
    origin = capture_case.originX if sample.axis == 0 else capture_case.originY
    low = v1.float32_bits_fraction(endpoint.lowBits)
    high = v1.float32_bits_fraction(endpoint.highBits)
    exact = low + (high - low) * Fraction(
        sample.tile * capture.TILE_SIZE - origin,
        extent,
    )
    return quantize_composite_constant_bits(exact)


def zero_physical_composite(
    capture_case: object,
    endpoint: object,
    sample: object,
    *,
    selector_table: tuple[int, ...],
) -> Fraction:
    axis = sample.axis
    extent = capture_case.width if axis == 0 else capture_case.height
    opposite = capture_case.height if axis == 0 else capture_case.width
    origin = capture_case.originX if axis == 0 else capture_case.originY
    low = v1.bits_float32(endpoint.lowBits)
    high = v1.bits_float32(endpoint.highBits)
    delta = high - low
    if axis == 0 and sample.primitive == 0:
        anchor = high
        anchor_position = origin + extent
    else:
        anchor = low
        anchor_position = origin
    displacement = sample.tile * capture.TILE_SIZE - anchor_position
    determinant = capture_case.width * capture_case.height
    term = (
        v1.fixed_product_slope(
            math.copysign(abs(delta), delta * displacement),
            opposite_edge=opposite * abs(displacement),
            determinant=determinant,
            reciprocal_index=v1.reciprocal_selector(determinant, selector_table),
        )
        if displacement
        else 0.0
    )
    return Fraction.from_float(anchor) + Fraction.from_float(term)


def selected_constant_bits(
    capture_case: object,
    endpoint: object,
    sample: object,
    *,
    selector_table: tuple[int, ...],
) -> tuple[str, int]:
    if endpoint.lowBits != 0 and endpoint.highBits != 0:
        return (
            "translated-exact-p28-nearest-double-round",
            translated_constant_bits(capture_case, endpoint, sample),
        )
    return (
        "zero-physical-p28-nearest-double-round",
        quantize_composite_constant_bits(
            zero_physical_composite(
                capture_case,
                endpoint,
                sample,
                selector_table=selector_table,
            )
        ),
    )


def predict_record(
    capture_case: object,
    endpoint: object,
    sample: object,
    selector_table: tuple[int, ...],
) -> tuple[int, ...]:
    (
        _,
        pull_slope_bits,
        _,
        center_slope_bits,
        _,
        _,
    ) = selected_slope_bits(
        capture_case,
        endpoint,
        axis=sample.axis,
        selector_table=selector_table,
    )
    _, constant_bits = selected_constant_bits(
        capture_case,
        endpoint,
        sample,
        selector_table=selector_table,
    )
    constant = v1.bits_float32(constant_bits)
    pull_record = v2.predict_record_with_setup(
        sample,
        slope=v1.bits_float32(pull_slope_bits),
        constant=constant,
    )
    if center_slope_bits == pull_slope_bits:
        return pull_record
    center_record = v2.predict_record_with_setup(
        sample,
        slope=v1.bits_float32(center_slope_bits),
        constant=constant,
    )
    return (*pull_record[: capture.PULL_COUNT], *center_record[capture.PULL_COUNT :])


def case_stream(
    capture_module: ModuleType,
    capture_case: object,
    selector_table: tuple[int, ...],
) -> bytes:
    result = bytearray()
    for endpoint in capture_module.ENDPOINTS:
        for sample in capture_module.sample_positions(capture_case):
            result.extend(
                capture_module.RECORD.pack(
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
    capture_module: ModuleType = capture,
    *,
    role: str = "sealed-holdout",
) -> tuple[bytes, dict[str, bytes]]:
    selector_table = v1.load_selector_table()
    streams = {
        capture_case.name: case_stream(
            capture_module,
            capture_case,
            selector_table,
        )
        for capture_case in capture_module.CASES
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


def preflight_discrimination_metadata() -> JsonObject:
    """Quantify how the sealed matrix distinguishes each newly frozen rule."""

    selector_table = v1.load_selector_table()
    determinant_ablation_words: Counter[str] = Counter()
    records = 0
    center_split_records = 0
    center_split_words = 0
    double_rounded_records = 0
    double_rounding_words = 0
    slope_groups: set[tuple[str, str, int]] = set()
    constant_groups: set[tuple[str, str, int, int, int]] = set()
    for capture_case in capture.CASES:
        if capture_case.role != "sealed-holdout":
            continue
        for endpoint in capture.ENDPOINTS:
            for sample in capture.sample_positions(capture_case):
                records += 1
                (
                    pull_name,
                    pull_bits,
                    center_name,
                    center_bits,
                    _,
                    internal,
                ) = selected_slope_bits(
                    capture_case,
                    endpoint,
                    axis=sample.axis,
                    selector_table=selector_table,
                )
                _, constant_bits = selected_constant_bits(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table=selector_table,
                )
                constant = v1.bits_float32(constant_bits)
                final = predict_record(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table,
                )
                determinant = v2.predict_record_with_setup(
                    sample,
                    slope=v1.bits_float32(v1.float32_bits(internal)),
                    constant=constant,
                )
                determinant_ablation_words[
                    f"pull={pull_name},center={center_name}"
                ] += sum(
                    actual != ablated
                    for actual, ablated in zip(final, determinant, strict=True)
                )
                if pull_bits != center_bits:
                    shared = v2.predict_record_with_setup(
                        sample,
                        slope=v1.bits_float32(pull_bits),
                        constant=constant,
                    )
                    difference = sum(
                        final[index] != shared[index]
                        for index in range(
                            capture.PULL_COUNT, capture.RECORD_COMPONENT_COUNT
                        )
                    )
                    center_split_records += difference != 0
                    center_split_words += difference
                if endpoint.lowBits == 0 or endpoint.highBits == 0:
                    composite = zero_physical_composite(
                        capture_case,
                        endpoint,
                        sample,
                        selector_table=selector_table,
                    )
                    direct_bits = v1.round_fraction_to_float32_bits(composite)
                    if direct_bits != constant_bits:
                        direct_pull = v2.predict_record_with_setup(
                            sample,
                            slope=v1.bits_float32(pull_bits),
                            constant=v1.bits_float32(direct_bits),
                        )
                        direct_center = (
                            direct_pull
                            if center_bits == pull_bits
                            else v2.predict_record_with_setup(
                                sample,
                                slope=v1.bits_float32(center_bits),
                                constant=v1.bits_float32(direct_bits),
                            )
                        )
                        direct = (
                            *direct_pull[: capture.PULL_COUNT],
                            *direct_center[capture.PULL_COUNT :],
                        )
                        difference = sum(
                            actual != ablated
                            for actual, ablated in zip(final, direct, strict=True)
                        )
                        double_rounded_records += difference != 0
                        double_rounding_words += difference
                slope_groups.add((capture_case.name, endpoint.name, sample.axis))
                constant_groups.add(
                    (
                        capture_case.name,
                        endpoint.name,
                        sample.axis,
                        sample.primitive,
                        sample.tile,
                    )
                )
    return {
        "sealedRecordCount": records,
        "sealedWordCount": records * capture.RECORD_COMPONENT_COUNT,
        "slopeSetupCount": len(slope_groups),
        "constantGroupCount": len(constant_groups),
        "determinantOnlyAblationWordDifferencesBySelectedPath": dict(
            sorted(determinant_ablation_words.items())
        ),
        "sharedPullCenterSlopeAblation": {
            "recordDifferenceCount": center_split_records,
            "wordDifferenceCount": center_split_words,
        },
        "singleRoundedZeroConstantAblation": {
            "recordDifferenceCount": double_rounded_records,
            "wordDifferenceCount": double_rounding_words,
        },
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
        raise ValueError("schema-6 prediction archive differs")
    raw = zlib.decompress(compressed)
    metadata = prediction_metadata()
    if (
        hashlib.sha256(raw).hexdigest() != PREDICTION_RAW_SHA256
        or hashlib.sha256(raw).hexdigest() != metadata["sha256"]
        or len(raw) != metadata["bytes"]
    ):
        raise ValueError("schema-6 prediction bytes differ")
    return raw
