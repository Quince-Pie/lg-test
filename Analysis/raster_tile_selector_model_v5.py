#!/usr/bin/env python3
"""Frozen schema-7 model of Apple tile-center origin behavior."""

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
import validate_raster_tile_double_rounding_holdout as capture
import validate_raster_tile_center_origin_holdout as holdout


type JsonObject = dict[str, Any]

PREDICTION_ORDERING = (
    "sealed-case-major,all-endpoint-major,sample-position-major,record-component-major"
)
PREDICTION_ARCHIVE_PATH = Path(__file__).with_name(
    "raster_tile_v5_sealed_predictions.zlib"
)
PREDICTION_ARCHIVE_SHA256 = (
    "d26fbd2092bd6cdaf2eae22bcd504384f059b2edce75a3e166e6e574e4de1369"
)
PREDICTION_RAW_SHA256 = (
    "acccb96dc6660a08016c4583385c43de09641a087890c1f4b66f8c3fcdecbf87"
)


def round_fraction_to_float32_down_bits(value: Fraction) -> int:
    """Round an exact normal value toward negative infinity."""

    bits = v1.round_fraction_to_float32_bits(value)
    rounded = v1.float32_bits_fraction(bits)
    if rounded > value:
        return bits + 1 if value < 0 else bits - 1
    return bits


def selected_slope_bits(
    capture_case: object,
    endpoint: object,
    *,
    axis: int,
    selector_table: tuple[int, ...],
) -> tuple[str, int, str, int, Fraction, float]:
    """Select pull and center coefficients from inputs available before capture."""

    base_bits, phase, internal = v4.determinant_slope(
        capture_case,
        endpoint,
        axis=axis,
        selector_table=selector_table,
    )
    if endpoint.lowBits == 0 or endpoint.highBits == 0:
        return (
            "determinant-rounded-f32",
            base_bits,
            "determinant-rounded-f32",
            base_bits,
            phase,
            internal,
        )

    extent = capture_case.width if axis == 0 else capture_case.height
    origin = capture_case.originX if axis == 0 else capture_case.originY
    delta = v1.float32_bits_fraction(endpoint.highBits) - v1.float32_bits_fraction(
        endpoint.lowBits
    )
    if origin % capture.TILE_SIZE == capture.TILE_SIZE // 2:
        center_name = "half-tile-origin-determinant-rounded-f32"
        center_bits = base_bits
    else:
        center_name = "exact-quotient-binary32-down"
        center_bits = round_fraction_to_float32_down_bits(delta / extent)
    return (
        "determinant-rounded-f32",
        base_bits,
        center_name,
        center_bits,
        phase,
        internal,
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
    _, constant_bits = v4.selected_constant_bits(
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
    capture_module: ModuleType = holdout,
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
        "endpointCount": len(holdout.ENDPOINTS),
        "recordComponentCount": holdout.RECORD_COMPONENT_COUNT,
        "recordBytes": holdout.RECORD.size,
        "recordCount": len(combined) // holdout.RECORD.size,
        "bytes": len(combined),
        "sha256": hashlib.sha256(combined).hexdigest(),
        "cases": [
            {
                "name": name,
                "recordCount": len(stream) // holdout.RECORD.size,
                "bytes": len(stream),
                "sha256": hashlib.sha256(stream).hexdigest(),
            }
            for name, stream in streams.items()
        ],
    }


def alternative_center_bits(
    policy: str,
    capture_case: object,
    endpoint: object,
    *,
    axis: int,
    base_bits: int,
) -> int:
    if endpoint.lowBits == 0 or endpoint.highBits == 0:
        return base_bits
    extent = capture_case.width if axis == 0 else capture_case.height
    origin = capture_case.originX if axis == 0 else capture_case.originY
    delta = v1.float32_bits_fraction(endpoint.highBits) - v1.float32_bits_fraction(
        endpoint.lowBits
    )
    exact_down = round_fraction_to_float32_down_bits(delta / extent)
    if policy == "determinant-all":
        return base_bits
    if policy == "exact-down-all":
        return exact_down
    if policy == "denominator33-determinant":
        return base_bits if extent in {198, 231} else exact_down
    if policy == "absolute-origin16-only":
        return base_bits if origin == 16 else exact_down
    raise ValueError(f"unknown center ablation policy: {policy}")


def preflight_discrimination_metadata() -> JsonObject:
    selector_table = v1.load_selector_table()
    differences: dict[str, Counter[str]] = {
        policy: Counter()
        for policy in (
            "determinant-all",
            "exact-down-all",
            "denominator33-determinant",
            "absolute-origin16-only",
        )
    }
    sealed_records = 0
    for capture_case in holdout.CASES:
        if capture_case.role != "sealed-holdout":
            continue
        for endpoint in holdout.ENDPOINTS:
            for sample in holdout.sample_positions(capture_case):
                sealed_records += 1
                predicted = predict_record(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table,
                )
                base_bits = v4.determinant_slope(
                    capture_case,
                    endpoint,
                    axis=sample.axis,
                    selector_table=selector_table,
                )[0]
                _, constant_bits = v4.selected_constant_bits(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table=selector_table,
                )
                for policy, counter in differences.items():
                    alternative_bits = alternative_center_bits(
                        policy,
                        capture_case,
                        endpoint,
                        axis=sample.axis,
                        base_bits=base_bits,
                    )
                    alternative = v2.predict_record_with_setup(
                        sample,
                        slope=v1.bits_float32(alternative_bits),
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
                    counter["records"] += changed != 0
                    counter["words"] += changed
    return {
        "sealedRecordCount": sealed_records,
        "sealedWordCount": sealed_records * holdout.RECORD_COMPONENT_COUNT,
        "centerAblationDifferences": {
            policy: dict(sorted(counter.items()))
            for policy, counter in differences.items()
        },
    }


def read_prediction_archive() -> bytes:
    compressed = PREDICTION_ARCHIVE_PATH.read_bytes()
    if hashlib.sha256(compressed).hexdigest() != PREDICTION_ARCHIVE_SHA256:
        raise ValueError("schema-7 prediction archive differs")
    raw = zlib.decompress(compressed)
    if hashlib.sha256(raw).hexdigest() != PREDICTION_RAW_SHA256:
        raise ValueError("schema-7 prediction bytes differ")
    return raw
