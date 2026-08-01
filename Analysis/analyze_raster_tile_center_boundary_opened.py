#!/usr/bin/env python3
"""Recover schema-10 directional laws and localize every remaining word."""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import open_raster_tile_center_boundary_holdout as opening
import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v6 as v6
import raster_tile_selector_model_v8 as v8
import validate_raster_tile_center_boundary_holdout as capture


type JsonObject = dict[str, Any]

COMPONENT_NAMES = (
    *(f"pull@{numerator}/16" for numerator in capture.PULL_NUMERATORS),
    "center",
    "axis-derivative(center)",
)


def odd_native_span(endpoint: object) -> int:
    span = abs(endpoint.highBits - endpoint.lowBits)
    if span == 0:
        return 0
    return span >> ((span & -span).bit_length() - 1)


def recovered_center_slope(
    capture_case: object,
    endpoint: object,
    *,
    axis: int,
    selector_table: tuple[int, ...],
) -> tuple[str, float]:
    determinant = v8.determinant_slope(
        capture_case,
        endpoint,
        axis=axis,
        selector_table=selector_table,
    )
    if endpoint.lowBits == 0 or endpoint.highBits == 0:
        return "zero-endpoint-determinant", determinant

    delta = v8.endpoint_delta(endpoint)
    depth = v8.cancellation_depth(endpoint)
    extent = capture_case.width if axis == 0 else capture_case.height
    floor, _, _ = v6.signed_p27_lattice(delta / extent)
    native_span = odd_native_span(endpoint)
    if delta > 0 and native_span == 15 and depth >= 7:
        return "n15-forward-signed-p27-floor", float(floor)
    if delta < 0 and native_span == 1 and depth >= 10:
        return "n01-reverse-signed-p27-floor", float(floor)
    return "determinant-rounded-f32", determinant


def predict_record(
    capture_case: object,
    endpoint: object,
    sample: object,
    selector_table: tuple[int, ...],
) -> tuple[int, ...]:
    pull_slope = v8.determinant_slope(
        capture_case,
        endpoint,
        axis=sample.axis,
        selector_table=selector_table,
    )
    _, center_slope = recovered_center_slope(
        capture_case,
        endpoint,
        axis=sample.axis,
        selector_table=selector_table,
    )
    constant = v1.bits_float32(
        v8.physical_constant_bits(
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
    center_record = v2.predict_record_with_setup(
        sample,
        slope=center_slope,
        constant=constant,
    )
    return (*pull_record[: capture.PULL_COUNT], *center_record[capture.PULL_COUNT :])


def analyze(root: Path) -> JsonObject:
    validation, streams = opening.actual_case_streams(root)
    selector_table = v1.load_selector_table()
    record_count = 0
    record_mismatches = 0
    word_mismatches = 0
    component_mismatches: Counter[str] = Counter()
    mismatch_cases: Counter[str] = Counter()
    mismatch_endpoints: Counter[str] = Counter()
    selected_laws: Counter[str] = Counter()
    examples: list[JsonObject] = []
    for capture_case in capture.CASES:
        samples = capture.sample_positions(capture_case)
        stream = streams[capture_case.name]
        offset = 0
        for endpoint in capture.ENDPOINTS:
            for sample in samples:
                actual = capture.RECORD.unpack_from(stream, offset)
                offset += capture.RECORD.size
                law, _ = recovered_center_slope(
                    capture_case,
                    endpoint,
                    axis=sample.axis,
                    selector_table=selector_table,
                )
                selected_laws[law] += 1
                predicted = predict_record(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table,
                )
                differing = [
                    index
                    for index, (actual_word, predicted_word) in enumerate(
                        zip(actual, predicted, strict=True)
                    )
                    if actual_word != predicted_word
                ]
                record_count += 1
                if not differing:
                    continue
                record_mismatches += 1
                word_mismatches += len(differing)
                component_mismatches.update(
                    COMPONENT_NAMES[index] for index in differing
                )
                mismatch_cases[capture_case.name] += len(differing)
                mismatch_endpoints[endpoint.name] += len(differing)
                if len(examples) < 32:
                    examples.append(
                        {
                            "case": capture_case.name,
                            "endpoint": endpoint.name,
                            "axis": "x" if sample.axis == 0 else "y",
                            "primitive": sample.primitive,
                            "tile": sample.tile,
                            "edge": sample.edge,
                            "x": sample.x,
                            "y": sample.y,
                            "law": law,
                            "components": [
                                {
                                    "name": COMPONENT_NAMES[index],
                                    "predictedBits": f"0x{predicted[index]:08x}",
                                    "actualBits": f"0x{actual[index]:08x}",
                                }
                                for index in differing
                            ],
                        }
                    )
    return {
        "rasterTileCenterBoundaryRecoverySchemaVersion": 1,
        "source": str(root),
        "sourceManifestSha256": validation["manifestSha256"],
        "sourceRawSha256": validation["rawSha256"],
        "sourceCiCommit": json.loads(
            (root / "manifest.json").read_text(encoding="utf-8")
        )["ciCommit"],
        "recordCount": record_count,
        "wordCount": record_count * capture.RECORD_COMPONENT_COUNT,
        "recordMismatchCount": record_mismatches,
        "wordMismatchCount": word_mismatches,
        "exact": word_mismatches == 0,
        "componentMismatchCounts": dict(sorted(component_mismatches.items())),
        "caseWordMismatchCounts": dict(sorted(mismatch_cases.items())),
        "endpointWordMismatchCounts": dict(sorted(mismatch_endpoints.items())),
        "selectedLawRecordCounts": dict(sorted(selected_laws.items())),
        "mismatchExamples": examples,
        "inference": (
            "The frozen phase/depth selector is rejected. Input-derived family and "
            "direction rules remove 5,820 of its 6,036 word mismatches. The 216 "
            "remaining words are a dense-tomography target, not evidence for a "
            "geometry-name branch."
        ),
        "remainingGate": (
            "Resolve the sub-p27 center coefficient, tile constant, and evaluator "
            "using the preregistered schema-11 dense capture; then replay all opened "
            "schemas exactly before freezing a new holdout."
        ),
        "productionShaderAuthorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = analyze(arguments.root)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(rendered, end="")
    else:
        arguments.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
