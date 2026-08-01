#!/usr/bin/env python3
"""Replay the schema-12 normalized 36-bit center model on an earlier corpus."""

import argparse
import importlib
import json
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any

import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v8 as default_coefficient_model
import raster_tile_iterator_model as iterator


type JsonObject = dict[str, Any]

def raw_capture(root: Path) -> tuple[JsonObject, bytes]:
    manifest: JsonObject = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    evidence = manifest["rasterTileNumerator"]
    return manifest, (root / str(evidence["file"])).read_bytes()


def center_pair(
    capture: ModuleType,
    capture_case: object,
    endpoint: object,
    sample: object,
    selector_table: tuple[int, ...],
    coefficient_model: ModuleType,
) -> tuple[int, int, int, float, int]:
    slope_float = (
        0.0
        if endpoint.lowBits == endpoint.highBits
        else coefficient_model.determinant_slope(
            capture_case,
            endpoint,
            axis=sample.axis,
            selector_table=selector_table,
        )
    )
    slope_bits = v1.float32_bits(slope_float)
    slope = v1.float32_bits_fraction(slope_bits)
    constant_bits = (
        endpoint.lowBits
        if endpoint.lowBits == endpoint.highBits
        else coefficient_model.physical_constant_bits(
            capture_case,
            endpoint,
            sample,
            selector_table=selector_table,
        )
    )
    constant = v1.float32_bits_fraction(constant_bits)
    fallback_step = iterator.endpoint_step(endpoint)
    step = iterator.significand_step(constant, fallback_step)
    coordinate = sample.x if sample.axis == 0 else sample.y
    local_pixel = coordinate - sample.tile * capture.TILE_SIZE
    left, right = iterator.quad_center_pair(
        local_pixel,
        slope,
        constant,
        step,
    )
    return (
        right if local_pixel & 1 else left,
        iterator.derivative_bits(left, right),
        local_pixel,
        slope_float,
        constant_bits,
    )


def analyze(
    capture: ModuleType,
    root: Path,
    *,
    verify_pulls: bool,
    coefficient_model: ModuleType = default_coefficient_model,
) -> JsonObject:
    manifest, raw = raw_capture(root)
    selector_table = v1.load_selector_table()
    records = 0
    words = 0
    sentinels = 0
    pull_word_mismatches = 0
    pull_record_mismatches = 0
    center_mismatches = 0
    derivative_mismatches = 0
    component_mismatches: Counter[str] = Counter()
    mismatch_cases: Counter[str] = Counter()
    mismatch_endpoints: Counter[str] = Counter()
    examples: list[JsonObject] = []

    for case_index, capture_case in enumerate(capture.CASES):
        for endpoint_index, endpoint in enumerate(capture.ENDPOINTS):
            for sample in capture.sample_positions(capture_case):
                record_index = (
                    case_index * len(capture.ENDPOINTS) + endpoint_index
                ) * capture.SLOT_COUNT + sample.slot
                actual = capture.RECORD.unpack_from(
                    raw,
                    record_index * capture.RECORD.size,
                )
                if actual == capture.SENTINEL:
                    sentinels += 1
                    continue
                records += 1
                words += len(actual)
                (
                    predicted_center,
                    predicted_derivative,
                    local_pixel,
                    slope_float,
                    constant_bits,
                ) = center_pair(
                    capture,
                    capture_case,
                    endpoint,
                    sample,
                    selector_table,
                    coefficient_model,
                )
                center_bad = predicted_center != actual[capture.PULL_COUNT]
                derivative_bad = (
                    predicted_derivative != actual[capture.PULL_COUNT + 1]
                )
                center_mismatches += center_bad
                derivative_mismatches += derivative_bad
                if center_bad:
                    component_mismatches["center"] += 1
                if derivative_bad:
                    component_mismatches["derivative"] += 1

                pull_bad = 0
                if verify_pulls:
                    constant = v1.bits_float32(constant_bits)
                    predicted_pulls = v2.predict_record_with_setup(
                        sample,
                        slope=slope_float,
                        constant=constant,
                    )[: capture.PULL_COUNT]
                    for index, (expected, predicted) in enumerate(
                        zip(
                            actual[: capture.PULL_COUNT],
                            predicted_pulls,
                            strict=True,
                        )
                    ):
                        if expected != predicted:
                            pull_bad += 1
                            component_mismatches[
                                f"pull@{capture.PULL_NUMERATORS[index]}/16"
                            ] += 1
                    pull_word_mismatches += pull_bad
                    pull_record_mismatches += bool(pull_bad)

                if center_bad or derivative_bad or pull_bad:
                    mismatch_cases[capture_case.name] += (
                        center_bad + derivative_bad + pull_bad
                    )
                    mismatch_endpoints[endpoint.name] += (
                        center_bad + derivative_bad + pull_bad
                    )
                    if len(examples) < 128:
                        coordinate = sample.x if sample.axis == 0 else sample.y
                        examples.append(
                            {
                                "case": capture_case.name,
                                "caseRole": capture_case.role,
                                "endpoint": endpoint.name,
                                "endpointRole": endpoint.role,
                                "axis": sample.axis,
                                "primitive": sample.primitive,
                                "tile": sample.tile,
                                "coordinate": coordinate,
                                "localPixel": local_pixel,
                                "pullWordMismatches": pull_bad,
                                "actualCenter": f"0x{actual[capture.PULL_COUNT]:08x}",
                                "predictedCenter": f"0x{predicted_center:08x}",
                                "centerMismatch": center_bad,
                                "actualDerivative": (
                                    f"0x{actual[capture.PULL_COUNT + 1]:08x}"
                                ),
                                "predictedDerivative": (
                                    f"0x{predicted_derivative:08x}"
                                ),
                                "derivativeMismatch": derivative_bad,
                            }
                        )

    mismatch_words = (
        pull_word_mismatches + center_mismatches + derivative_mismatches
    )
    return {
        "normalizedCenterReplaySchemaVersion": 1,
        "captureModule": capture.__name__,
        "captureSchemaVersion": capture.SCHEMA_VERSION,
        "captureRigVersion": capture.RIG_VERSION,
        "source": str(root),
        "sourceCiCommit": manifest.get("ciCommit"),
        "sourceRawSha256": manifest["rasterTileNumerator"]["sha256"],
        "verifyPulls": verify_pulls,
        "recordCount": records,
        "wordCount": words,
        "sentinelSampleCount": sentinels,
        "pullRecordMismatchCount": pull_record_mismatches,
        "pullWordMismatchCount": pull_word_mismatches,
        "centerMismatchCount": center_mismatches,
        "derivativeMismatchCount": derivative_mismatches,
        "totalComparedComponentMismatchCount": mismatch_words,
        "exact": mismatch_words == 0,
        "componentMismatchCounts": dict(sorted(component_mismatches.items())),
        "mismatchCaseCounts": dict(mismatch_cases.most_common()),
        "mismatchEndpointCounts": dict(mismatch_endpoints.most_common()),
        "mismatchExamples": examples,
        "model": {
            "coefficient": "determinant fixed-product rounded to binary32",
            "constant": "physical 28-significand-bit composite rounded to binary32",
            "centerAccumulatorPrecisionBits": iterator.CENTER_PRECISION_BITS,
            "centerAccumulatorScale": "tile-start constant binary exponent",
            "centerAccumulatorRounding": "floor",
            "centerOutputRounding": "binary32 toward zero",
            "quadRule": "even base plus one coefficient for odd lane",
            "coefficientModelModule": coefficient_model.__name__,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_module")
    parser.add_argument("root", type=Path)
    parser.add_argument("--verify-pulls", action="store_true")
    parser.add_argument(
        "--coefficient-model",
        default=default_coefficient_model.__name__,
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    capture = importlib.import_module(arguments.capture_module)
    coefficient_model = importlib.import_module(arguments.coefficient_model)
    report = analyze(
        capture,
        arguments.root,
        verify_pulls=arguments.verify_pulls,
        coefficient_model=coefficient_model,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(rendered, end="")
    else:
        arguments.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
