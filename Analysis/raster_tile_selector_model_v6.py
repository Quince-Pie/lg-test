#!/usr/bin/env python3
"""Frozen schema-8 model of Apple's translated tile-center coefficient."""

import hashlib
import zlib
from collections import Counter
from fractions import Fraction
from pathlib import Path
from types import ModuleType
from typing import Any

import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v5 as v5
import validate_raster_tile_center_lattice_holdout as capture


type JsonObject = dict[str, Any]

CENTER_PRECISION_BITS = 27
FORWARD_PHASE_LOWER = Fraction(3, 32)
FORWARD_PHASE_UPPER = Fraction(9, 16)
PREDICTION_ORDERING = (
    "sealed-case-major,all-endpoint-major,sample-position-major,record-component-major"
)
PREDICTION_ARCHIVE_PATH = Path(__file__).with_name(
    "raster_tile_v6_sealed_predictions.zlib"
)
PREDICTION_ARCHIVE_SHA256 = (
    "835e33732c9084c285215b0c52b369eff861a91f29938a81b851bc666e3fdd79"
)
PREDICTION_RAW_SHA256 = (
    "08ceb5ccab6fde6d1c880c0e8059f88ed98350fdd467d1772002dc66171b6277"
)


def signed_p27_lattice(value: Fraction) -> tuple[Fraction, Fraction, Fraction]:
    """Return numerical floor, step, and magnitude phase on the p27 lattice."""

    if value == 0:
        return Fraction(0), Fraction(0), Fraction(0)
    magnitude = abs(value)
    exponent = v1.floor_binary_exponent(magnitude)
    step = v1.power_of_two(exponent - CENTER_PRECISION_BITS + 1)
    scaled = value / step
    floor_index = scaled.numerator // scaled.denominator
    magnitude_floor_index = int(magnitude / step)
    phase = (magnitude - magnitude_floor_index * step) / step
    return floor_index * step, step, phase


def recovered_center_slope(value: Fraction) -> tuple[str, float, Fraction, int]:
    """Apply the input-only signed-p27 selector recovered from schemas 5-7."""

    floor_value, step, phase = signed_p27_lattice(value)
    action = 0
    if value > 0:
        if phase < FORWARD_PHASE_LOWER:
            action = -1
        elif phase >= FORWARD_PHASE_UPPER:
            action = 1
    return (
        "translated-signed-p27-phase-selector",
        float(floor_value + action * step),
        phase,
        action,
    )


def selected_coefficients(
    capture_case: object,
    endpoint: object,
    *,
    axis: int,
    selector_table: tuple[int, ...],
) -> tuple[str, float, str, float, Fraction, int]:
    """Select pull and center coefficients using only preregistered inputs."""

    base_bits, _, _ = v4.determinant_slope(
        capture_case,
        endpoint,
        axis=axis,
        selector_table=selector_table,
    )
    pull_slope = v1.bits_float32(base_bits)
    if endpoint.lowBits == 0 or endpoint.highBits == 0:
        return (
            "determinant-rounded-f32",
            pull_slope,
            "zero-endpoint-determinant-rounded-f32",
            pull_slope,
            Fraction(0),
            0,
        )
    extent = capture_case.width if axis == 0 else capture_case.height
    delta = v1.float32_bits_fraction(
        endpoint.highBits
    ) - v1.float32_bits_fraction(endpoint.lowBits)
    center_name, center_slope, phase, action = recovered_center_slope(delta / extent)
    return (
        "determinant-rounded-f32",
        pull_slope,
        center_name,
        center_slope,
        phase,
        action,
    )


def predict_record(
    capture_case: object,
    endpoint: object,
    sample: object,
    selector_table: tuple[int, ...],
) -> tuple[int, ...]:
    (
        _,
        pull_slope,
        _,
        center_slope,
        _,
        _,
    ) = selected_coefficients(
        capture_case,
        endpoint,
        axis=sample.axis,
        selector_table=selector_table,
    )
    _, constant_bits = v4.selected_constant_bits(
        capture_case,
        endpoint,
        sample,
        selector_table=selector_table,
    )
    constant = v1.bits_float32(constant_bits)
    pull_record = v2.predict_record_with_setup(
        sample,
        slope=pull_slope,
        constant=constant,
    )
    if center_slope == pull_slope:
        return pull_record
    center_record = v2.predict_record_with_setup(
        sample,
        slope=center_slope,
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


def threshold_center_slope(
    value: Fraction,
    *,
    lower: Fraction,
    upper: Fraction,
    apply_to_reverse: bool = False,
) -> float:
    floor_value, step, phase = signed_p27_lattice(value)
    action = 0
    if value > 0 or apply_to_reverse:
        if phase < lower:
            action = -1
        elif phase >= upper:
            action = 1
    return float(floor_value + action * step)


def alternative_center_slope(
    policy: str,
    capture_case: object,
    endpoint: object,
    *,
    axis: int,
    base_slope: float,
) -> float:
    if endpoint.lowBits == 0 or endpoint.highBits == 0:
        return base_slope
    extent = capture_case.width if axis == 0 else capture_case.height
    value = (
        v1.float32_bits_fraction(endpoint.highBits)
        - v1.float32_bits_fraction(endpoint.lowBits)
    ) / extent
    floor_value, _, _ = signed_p27_lattice(value)
    if policy == "determinant-rounded-f32":
        return base_slope
    if policy == "binary32-exact-down":
        return v1.bits_float32(v5.round_fraction_to_float32_down_bits(value))
    if policy == "p27-signed-floor":
        return float(floor_value)
    if policy == "p27-nearest-even":
        nearest = v1.quantize_binary_significand(
            abs(value),
            CENTER_PRECISION_BITS,
            rounding="nearest-even",
        )
        return float(-nearest if value < 0 else nearest)
    if policy == "lower-boundary-5/64":
        return threshold_center_slope(
            value,
            lower=Fraction(5, 64),
            upper=FORWARD_PHASE_UPPER,
        )
    if policy == "lower-boundary-7/64":
        return threshold_center_slope(
            value,
            lower=Fraction(7, 64),
            upper=FORWARD_PHASE_UPPER,
        )
    if policy == "lower-branch-removed":
        return threshold_center_slope(
            value,
            lower=Fraction(0),
            upper=FORWARD_PHASE_UPPER,
        )
    if policy == "upper-boundary-1/2":
        return threshold_center_slope(
            value,
            lower=FORWARD_PHASE_LOWER,
            upper=Fraction(1, 2),
        )
    if policy == "upper-boundary-17/32":
        return threshold_center_slope(
            value,
            lower=FORWARD_PHASE_LOWER,
            upper=Fraction(17, 32),
        )
    if policy == "upper-boundary-19/32":
        return threshold_center_slope(
            value,
            lower=FORWARD_PHASE_LOWER,
            upper=Fraction(19, 32),
        )
    if policy == "upper-branch-removed":
        return threshold_center_slope(
            value,
            lower=FORWARD_PHASE_LOWER,
            upper=Fraction(1),
        )
    if policy == "direction-symmetric":
        return threshold_center_slope(
            value,
            lower=FORWARD_PHASE_LOWER,
            upper=FORWARD_PHASE_UPPER,
            apply_to_reverse=True,
        )
    raise ValueError(f"unknown center ablation policy: {policy}")


def center_words(sample: object, *, slope: float, constant: float) -> tuple[int, int]:
    coordinate = sample.x if sample.axis == 0 else sample.y
    local_pixel = coordinate - sample.tile * capture.TILE_SIZE
    position = local_pixel + 0.5
    return (
        v1.center_bits(position, slope, constant),
        v1.derivative_bits(local_pixel, position, slope, constant),
    )


def preflight_discrimination_metadata() -> JsonObject:
    selector_table = v1.load_selector_table()
    policies = (
        "determinant-rounded-f32",
        "binary32-exact-down",
        "p27-signed-floor",
        "p27-nearest-even",
        "lower-boundary-5/64",
        "lower-boundary-7/64",
        "lower-branch-removed",
        "upper-boundary-1/2",
        "upper-boundary-17/32",
        "upper-boundary-19/32",
        "upper-branch-removed",
        "direction-symmetric",
    )
    differences = {policy: Counter() for policy in policies}
    sealed_records = sum(
        len(capture.sample_positions(capture_case)) * len(capture.ENDPOINTS)
        for capture_case in capture.CASES
        if capture_case.role == "sealed-holdout"
    )
    for capture_case in capture.CASES:
        if capture_case.role != "sealed-holdout":
            continue
        for endpoint in capture.ENDPOINTS:
            if endpoint.lowBits == 0 or endpoint.highBits == 0:
                continue
            recovered_by_axis: dict[int, float] = {}
            alternatives_by_axis: dict[int, dict[str, float]] = {}
            for axis in range(capture.AXIS_COUNT):
                base_bits = v4.determinant_slope(
                    capture_case,
                    endpoint,
                    axis=axis,
                    selector_table=selector_table,
                )[0]
                recovered_by_axis[axis] = selected_coefficients(
                    capture_case,
                    endpoint,
                    axis=axis,
                    selector_table=selector_table,
                )[3]
                alternatives_by_axis[axis] = {
                    policy: alternative_center_slope(
                        policy,
                        capture_case,
                        endpoint,
                        axis=axis,
                        base_slope=v1.bits_float32(base_bits),
                    )
                    for policy in policies
                }
            for sample in capture.sample_positions(capture_case):
                _, constant_bits = v4.selected_constant_bits(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table=selector_table,
                )
                constant = v1.bits_float32(constant_bits)
                predicted = center_words(
                    sample,
                    slope=recovered_by_axis[sample.axis],
                    constant=constant,
                )
                for policy, counter in differences.items():
                    alternative = center_words(
                        sample,
                        slope=alternatives_by_axis[sample.axis][policy],
                        constant=constant,
                    )
                    changed = sum(
                        left != right
                        for left, right in zip(
                            predicted,
                            alternative,
                            strict=True,
                        )
                    )
                    counter["records"] += changed != 0
                    counter["words"] += changed
    return {
        "sealedRecordCount": sealed_records,
        "sealedWordCount": sealed_records * capture.RECORD_COMPONENT_COUNT,
        "centerAblationDifferences": {
            policy: dict(sorted(counter.items()))
            for policy, counter in differences.items()
        },
    }


def read_prediction_archive() -> bytes:
    compressed = PREDICTION_ARCHIVE_PATH.read_bytes()
    if hashlib.sha256(compressed).hexdigest() != PREDICTION_ARCHIVE_SHA256:
        raise ValueError("schema-8 prediction archive differs")
    raw = zlib.decompress(compressed)
    if hashlib.sha256(raw).hexdigest() != PREDICTION_RAW_SHA256:
        raise ValueError("schema-8 prediction bytes differ")
    return raw
