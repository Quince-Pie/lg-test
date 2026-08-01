#!/usr/bin/env python3
"""Frozen predictor for the schema-13 raster-coefficient holdout."""

import hashlib
import zlib
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

import raster_tile_coefficient_model as coefficients
import raster_tile_iterator_model as iterator
import raster_tile_selector_model as arithmetic
import validate_raster_tile_coefficient_holdout as capture


type JsonObject = dict[str, Any]

PREDICTION_ORDERING = (
    "case-major,endpoint-major,sample-position-major,record-component-major"
)
PREDICTION_ARCHIVE_PATH = Path(__file__).with_name(
    "raster_tile_coefficient_holdout_predictions.zlib"
)
PREDICTION_ARCHIVE_SHA256 = (
    "8aadb17f8982f5f8dcf6ebcb2a1671e9af6f948e205a1484a5e9efed3a2d7c1c"
)
PREDICTION_RAW_SHA256 = (
    "267e6b4aa6fc51cdf4af5bc2f594fecc75db7c3bf764a18bb472044e3ac755d7"
)


def predict_record(
    capture_case: object,
    endpoint: object,
    sample: object,
    selector_table: tuple[int, ...],
    *,
    policy: coefficients.CoefficientPolicy = coefficients.MEASURED_POLICY,
    force_factorized: bool | None = None,
) -> tuple[int, ...]:
    return iterator.predict_record(
        capture,
        capture_case,
        endpoint,
        sample,
        selector_table,
        policy=policy,
        force_factorized=force_factorized,
    )


def case_stream(
    capture_case: object,
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


def prediction_streams() -> tuple[bytes, dict[str, bytes]]:
    selector_table = arithmetic.load_selector_table()
    streams = {
        capture_case.name: case_stream(capture_case, selector_table)
        for capture_case in capture.CASES
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


ABLATION_POLICIES = {
    "slope-first-bias-14": replace(
        coefficients.MEASURED_POLICY,
        slope_first_bias=14,
    ),
    "constant-first-bias-14": replace(
        coefficients.MEASURED_POLICY,
        constant_first_bias=14,
    ),
    "partial-tile-product": replace(
        coefficients.MEASURED_POLICY,
        aggregate_tile_product=False,
    ),
    "tile-truncation-18": replace(
        coefficients.MEASURED_POLICY,
        tile_truncation_bits=18,
    ),
    "tile-truncation-20": replace(
        coefficients.MEASURED_POLICY,
        tile_truncation_bits=20,
    ),
    "tile-bias-9": replace(
        coefficients.MEASURED_POLICY,
        tile_bias=9,
    ),
    "tile-bias-11": replace(
        coefficients.MEASURED_POLICY,
        tile_bias=11,
    ),
    "reciprocal-truncation-18": replace(
        coefficients.MEASURED_POLICY,
        reciprocal_truncation_bits=18,
    ),
    "reciprocal-truncation-20": replace(
        coefficients.MEASURED_POLICY,
        reciprocal_truncation_bits=20,
    ),
    "reciprocal-bias-19": replace(
        coefficients.MEASURED_POLICY,
        reciprocal_bias=19,
    ),
    "reciprocal-bias-21": replace(
        coefficients.MEASURED_POLICY,
        reciprocal_bias=21,
    ),
}


def positive_factorized_override(endpoint: object) -> bool | None:
    low = arithmetic.float32_bits_fraction(endpoint.lowBits)
    high = arithmetic.float32_bits_fraction(endpoint.highBits)
    if low > 0 and high > 0 and low != high:
        return True
    return None


def alternative_record(
    name: str,
    capture_case: object,
    endpoint: object,
    sample: object,
    selector_table: tuple[int, ...],
) -> tuple[int, ...]:
    if name == "legacy-constant-all":
        return predict_record(
            capture_case,
            endpoint,
            sample,
            selector_table,
            force_factorized=False,
        )
    if name == "factorized-constant-all-positive":
        return predict_record(
            capture_case,
            endpoint,
            sample,
            selector_table,
            force_factorized=positive_factorized_override(endpoint),
        )
    return predict_record(
        capture_case,
        endpoint,
        sample,
        selector_table,
        policy=ABLATION_POLICIES[name],
    )


def preflight_discrimination_metadata() -> JsonObject:
    selector_table = arithmetic.load_selector_table()
    names = (
        "legacy-constant-all",
        "factorized-constant-all-positive",
        *ABLATION_POLICIES,
    )
    differences = {name: Counter() for name in names}
    endpoint_differences = {name: Counter() for name in names}
    record_count = 0
    for capture_case in capture.CASES:
        for endpoint in capture.ENDPOINTS:
            for sample in capture.sample_positions(capture_case):
                record_count += 1
                predicted = predict_record(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table,
                )
                for name in names:
                    alternative = alternative_record(
                        name,
                        capture_case,
                        endpoint,
                        sample,
                        selector_table,
                    )
                    changed = sum(
                        left != right
                        for left, right in zip(
                            predicted,
                            alternative,
                            strict=True,
                        )
                    )
                    differences[name]["records"] += changed != 0
                    differences[name]["words"] += changed
                    if changed:
                        endpoint_differences[name][endpoint.name] += changed
    return {
        "recordCount": record_count,
        "wordCount": record_count * capture.RECORD_COMPONENT_COUNT,
        "ablationDifferences": {
            name: dict(sorted(counter.items()))
            for name, counter in differences.items()
        },
        "ablationEndpointWordDifferences": {
            name: dict(sorted(counter.items()))
            for name, counter in endpoint_differences.items()
        },
    }


def read_prediction_archive() -> bytes:
    compressed = PREDICTION_ARCHIVE_PATH.read_bytes()
    if hashlib.sha256(compressed).hexdigest() != PREDICTION_ARCHIVE_SHA256:
        raise ValueError("schema-13 prediction archive differs")
    raw = zlib.decompress(compressed)
    if hashlib.sha256(raw).hexdigest() != PREDICTION_RAW_SHA256:
        raise ValueError("schema-13 prediction bytes differ")
    return raw
