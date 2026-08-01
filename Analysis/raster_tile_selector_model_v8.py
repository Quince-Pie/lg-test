#!/usr/bin/env python3
"""Frozen schema-10 model of Apple's directional tile-center boundaries."""

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
import raster_tile_selector_model_v6 as v6
import raster_tile_selector_model_v7 as v7
import validate_raster_tile_center_boundary_holdout as capture


type JsonObject = dict[str, Any]

FORWARD_PHASE_MIN_DEPTH = 11
FORWARD_FLOOR_MIN_DEPTH = 8
REVERSE_P27_MIN_DEPTH = 16
PREDICTION_ORDERING = (
    "sealed-case-major,all-endpoint-major,sample-position-major,record-component-major"
)
PREDICTION_ARCHIVE_PATH = Path(__file__).with_name(
    "raster_tile_v8_sealed_predictions.zlib"
)
PREDICTION_ARCHIVE_SHA256 = (
    "f9ab4416dc74faf6b0cbf409e311896e7082ab900b86229d05610f6f248bc879"
)
PREDICTION_RAW_SHA256 = (
    "eab3abd0345367892343bed3eb13fe017facf423f16d45886dde85cd6090bf44"
)


def endpoint_delta(endpoint: object) -> Fraction:
    return v7.endpoint_delta(endpoint)


def cancellation_depth(endpoint: object) -> int:
    return v7.cancellation_depth(endpoint)


def determinant_slope(
    capture_case: object,
    endpoint: object,
    *,
    axis: int,
    selector_table: tuple[int, ...],
) -> float:
    bits, _, _ = v4.determinant_slope(
        capture_case,
        endpoint,
        axis=axis,
        selector_table=selector_table,
    )
    return v1.bits_float32(bits)


def center_slope_for_boundaries(
    capture_case: object,
    endpoint: object,
    *,
    axis: int,
    selector_table: tuple[int, ...],
    forward_phase_min_depth: int = FORWARD_PHASE_MIN_DEPTH,
    forward_floor_min_depth: int = FORWARD_FLOOR_MIN_DEPTH,
    reverse_p27_min_depth: int = REVERSE_P27_MIN_DEPTH,
) -> tuple[str, float, int]:
    determinant = determinant_slope(
        capture_case,
        endpoint,
        axis=axis,
        selector_table=selector_table,
    )
    if endpoint.lowBits == 0 or endpoint.highBits == 0:
        return "zero-endpoint-determinant-rounded-f32", determinant, 0

    delta = endpoint_delta(endpoint)
    depth = cancellation_depth(endpoint)
    extent = capture_case.width if axis == 0 else capture_case.height
    quotient = delta / extent
    if delta > 0:
        if depth >= forward_phase_min_depth:
            _, slope, _, _ = v6.recovered_center_slope(quotient)
            return "forward-signed-p27-phase-selector", slope, depth
        if depth >= forward_floor_min_depth:
            floor, _, _ = v6.signed_p27_lattice(quotient)
            return "forward-signed-p27-floor", float(floor), depth
        return "forward-determinant-rounded-f32", determinant, depth
    if delta < 0 and depth >= reverse_p27_min_depth:
        floor, _, _ = v6.signed_p27_lattice(quotient)
        return "reverse-signed-p27-floor", float(floor), depth
    return "reverse-determinant-rounded-f32", determinant, depth


def selected_coefficients(
    capture_case: object,
    endpoint: object,
    *,
    axis: int,
    selector_table: tuple[int, ...],
) -> tuple[str, float, str, float, int]:
    pull_slope = determinant_slope(
        capture_case,
        endpoint,
        axis=axis,
        selector_table=selector_table,
    )
    center_name, center_slope, depth = center_slope_for_boundaries(
        capture_case,
        endpoint,
        axis=axis,
        selector_table=selector_table,
    )
    return (
        "determinant-rounded-f32",
        pull_slope,
        center_name,
        center_slope,
        depth,
    )


def physical_constant_bits(
    capture_case: object,
    endpoint: object,
    sample: object,
    *,
    selector_table: tuple[int, ...],
) -> int:
    return v7.physical_constant_bits(
        capture_case,
        endpoint,
        sample,
        selector_table=selector_table,
    )


def predict_record(
    capture_case: object,
    endpoint: object,
    sample: object,
    selector_table: tuple[int, ...],
) -> tuple[int, ...]:
    _, pull_slope, _, center_slope, _ = selected_coefficients(
        capture_case,
        endpoint,
        axis=sample.axis,
        selector_table=selector_table,
    )
    constant = v1.bits_float32(
        physical_constant_bits(
            capture_case,
            endpoint,
            sample,
            selector_table=selector_table,
        )
    )
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


def alternative_center_slope(
    policy: str,
    capture_case: object,
    endpoint: object,
    *,
    axis: int,
    selector_table: tuple[int, ...],
) -> float:
    determinant = determinant_slope(
        capture_case,
        endpoint,
        axis=axis,
        selector_table=selector_table,
    )
    if endpoint.lowBits == 0 or endpoint.highBits == 0:
        return determinant
    delta = endpoint_delta(endpoint)
    extent = capture_case.width if axis == 0 else capture_case.height
    quotient = delta / extent
    floor, _, _ = v6.signed_p27_lattice(quotient)
    if policy == "determinant-all":
        return determinant
    if policy == "p27-floor-all":
        return float(floor)
    if policy == "p27-phase-all":
        return v6.recovered_center_slope(quotient)[1]

    phase_min = FORWARD_PHASE_MIN_DEPTH
    floor_min = FORWARD_FLOOR_MIN_DEPTH
    reverse_min = REVERSE_P27_MIN_DEPTH
    if policy.startswith("forward-phase-min-"):
        phase_min = int(policy.removeprefix("forward-phase-min-"))
    elif policy.startswith("forward-floor-min-"):
        floor_min = int(policy.removeprefix("forward-floor-min-"))
    elif policy.startswith("reverse-p27-min-"):
        reverse_min = int(policy.removeprefix("reverse-p27-min-"))
    elif policy == "symmetric-forward-boundaries":
        reverse_min = FORWARD_FLOOR_MIN_DEPTH
    elif policy != "translated-exact-constant":
        raise ValueError(f"unknown boundary ablation policy: {policy}")
    return center_slope_for_boundaries(
        capture_case,
        endpoint,
        axis=axis,
        selector_table=selector_table,
        forward_phase_min_depth=phase_min,
        forward_floor_min_depth=floor_min,
        reverse_p27_min_depth=reverse_min,
    )[1]


def preflight_discrimination_metadata() -> JsonObject:
    selector_table = v1.load_selector_table()
    policies = (
        "determinant-all",
        "p27-floor-all",
        "p27-phase-all",
        "forward-phase-min-10",
        "forward-phase-min-12",
        "forward-floor-min-7",
        "forward-floor-min-9",
        "reverse-p27-min-15",
        "reverse-p27-min-17",
        "symmetric-forward-boundaries",
        "translated-exact-constant",
    )
    differences = {policy: Counter() for policy in policies}
    sealed_records = 0
    for capture_case in capture.CASES:
        if capture_case.role != "sealed-holdout":
            continue
        for endpoint in capture.ENDPOINTS:
            for sample in capture.sample_positions(capture_case):
                sealed_records += 1
                predicted = predict_record(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table,
                )
                physical_bits = physical_constant_bits(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table=selector_table,
                )
                for policy, counter in differences.items():
                    slope = alternative_center_slope(
                        policy,
                        capture_case,
                        endpoint,
                        axis=sample.axis,
                        selector_table=selector_table,
                    )
                    constant_bits = (
                        v4.translated_constant_bits(
                            capture_case,
                            endpoint,
                            sample,
                        )
                        if policy == "translated-exact-constant"
                        and endpoint.lowBits != 0
                        and endpoint.highBits != 0
                        else physical_bits
                    )
                    alternative = v2.predict_record_with_setup(
                        sample,
                        slope=slope,
                        constant=v1.bits_float32(constant_bits),
                    )
                    changed = sum(
                        left != right
                        for left, right in zip(
                            predicted[capture.PULL_COUNT :],
                            alternative[capture.PULL_COUNT :],
                            strict=True,
                        )
                    )
                    if policy == "translated-exact-constant":
                        changed += sum(
                            left != right
                            for left, right in zip(
                                predicted[: capture.PULL_COUNT],
                                alternative[: capture.PULL_COUNT],
                                strict=True,
                            )
                        )
                    counter["records"] += changed != 0
                    counter["words"] += changed
    return {
        "sealedRecordCount": sealed_records,
        "sealedWordCount": sealed_records * capture.RECORD_COMPONENT_COUNT,
        "ablationDifferences": {
            policy: dict(sorted(counter.items()))
            for policy, counter in differences.items()
        },
    }


def read_prediction_archive() -> bytes:
    compressed = PREDICTION_ARCHIVE_PATH.read_bytes()
    if hashlib.sha256(compressed).hexdigest() != PREDICTION_ARCHIVE_SHA256:
        raise ValueError("schema-10 prediction archive differs")
    raw = zlib.decompress(compressed)
    if hashlib.sha256(raw).hexdigest() != PREDICTION_RAW_SHA256:
        raise ValueError("schema-10 prediction bytes differ")
    return raw
