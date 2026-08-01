#!/usr/bin/env python3
"""Frozen schema-9 model of Apple's tile-center scale switch."""

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
import validate_raster_tile_center_scale_holdout as capture


type JsonObject = dict[str, Any]

CENTER_CANCELLATION_BITS = 16
PREDICTION_ORDERING = (
    "sealed-case-major,all-endpoint-major,sample-position-major,record-component-major"
)
PREDICTION_ARCHIVE_PATH = Path(__file__).with_name(
    "raster_tile_v7_sealed_predictions.zlib"
)
PREDICTION_ARCHIVE_SHA256 = (
    "77aa9fe3f48f0d704660d54d7748d0df0365e6b427d17e15b74ac57344f27efa"
)
PREDICTION_RAW_SHA256 = (
    "d2adc8c4a99860e38c3c00260894e48627a00d64416ddaffcc5a47ba442f11de"
)


def endpoint_delta(endpoint: object) -> Fraction:
    return v1.float32_bits_fraction(
        endpoint.highBits
    ) - v1.float32_bits_fraction(endpoint.lowBits)


def cancellation_depth(endpoint: object) -> int:
    """Return endpoint-scale exponent minus delta exponent."""

    low = v1.float32_bits_fraction(endpoint.lowBits)
    high = v1.float32_bits_fraction(endpoint.highBits)
    delta = high - low
    if low == 0 or high == 0 or delta == 0:
        return 0
    scale = max(abs(low), abs(high))
    return v1.floor_binary_exponent(scale) - v1.floor_binary_exponent(abs(delta))


def selected_coefficients(
    capture_case: object,
    endpoint: object,
    *,
    axis: int,
    selector_table: tuple[int, ...],
    cancellation_bits: int = CENTER_CANCELLATION_BITS,
) -> tuple[str, float, str, float, int]:
    base_bits, _, _ = v4.determinant_slope(
        capture_case,
        endpoint,
        axis=axis,
        selector_table=selector_table,
    )
    determinant_slope = v1.bits_float32(base_bits)
    depth = cancellation_depth(endpoint)
    if depth < cancellation_bits:
        return (
            "determinant-rounded-f32",
            determinant_slope,
            "determinant-rounded-f32",
            determinant_slope,
            depth,
        )
    extent = capture_case.width if axis == 0 else capture_case.height
    _, center_slope, _, _ = v6.recovered_center_slope(
        endpoint_delta(endpoint) / extent
    )
    return (
        "determinant-rounded-f32",
        determinant_slope,
        "translated-signed-p27-phase-selector",
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
    return v4.quantize_composite_constant_bits(
        v4.zero_physical_composite(
            capture_case,
            endpoint,
            sample,
            selector_table=selector_table,
        )
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
    base_bits, _, _ = v4.determinant_slope(
        capture_case,
        endpoint,
        axis=axis,
        selector_table=selector_table,
    )
    determinant_slope = v1.bits_float32(base_bits)
    if endpoint.lowBits == 0 or endpoint.highBits == 0:
        return determinant_slope
    extent = capture_case.width if axis == 0 else capture_case.height
    _, p27_slope, _, _ = v6.recovered_center_slope(
        endpoint_delta(endpoint) / extent
    )
    depth = cancellation_depth(endpoint)
    if policy == "determinant-all":
        return determinant_slope
    if policy == "p27-all":
        return p27_slope
    if policy.startswith("cancellation-"):
        threshold = int(policy.removeprefix("cancellation-"))
        return p27_slope if depth >= threshold else determinant_slope
    if policy == "absolute-delta-exp-minus16":
        exponent = v1.floor_binary_exponent(abs(endpoint_delta(endpoint)))
        return p27_slope if exponent <= -16 else determinant_slope
    if policy == "translated-exact-constant":
        return p27_slope if depth >= CENTER_CANCELLATION_BITS else determinant_slope
    raise ValueError(f"unknown scale-switch ablation policy: {policy}")


def preflight_discrimination_metadata() -> JsonObject:
    selector_table = v1.load_selector_table()
    policies = (
        "determinant-all",
        "p27-all",
        "cancellation-14",
        "cancellation-15",
        "cancellation-17",
        "cancellation-18",
        "absolute-delta-exp-minus16",
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
        raise ValueError("schema-9 prediction archive differs")
    raw = zlib.decompress(compressed)
    if hashlib.sha256(raw).hexdigest() != PREDICTION_RAW_SHA256:
        raise ValueError("schema-9 prediction bytes differ")
    return raw
