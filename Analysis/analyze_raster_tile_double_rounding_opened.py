#!/usr/bin/env python3
"""Localize schema-6 failures after its sealed records have been opened."""

import argparse
import json
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any

import open_raster_tile_double_rounding_holdout as opening
import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v4 as model
import validate_raster_tile_double_rounding_holdout as capture


type JsonObject = dict[str, Any]

COMPONENT_NAMES = (
    *(f"pull@{numerator}/16" for numerator in capture.PULL_NUMERATORS),
    "center",
    "axis-derivative(center)",
)
NEIGHBOR_OFFSETS = range(-4, 5)


def fraction_metadata(value: Fraction) -> JsonObject:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal": float(value),
    }


def candidate_differences(
    samples: list[capture.SamplePosition],
    actual_records: list[tuple[int, ...]],
    constants: list[int],
    base_bits: int,
) -> tuple[dict[int, int], dict[int, int]]:
    pull_differences: dict[int, int] = {}
    center_differences: dict[int, int] = {}
    for neighbor_offset in NEIGHBOR_OFFSETS:
        slope = v1.bits_float32(base_bits + neighbor_offset)
        pull_words = 0
        center_words = 0
        for sample, actual, constant_bits in zip(
            samples,
            actual_records,
            constants,
            strict=True,
        ):
            predicted = v2.predict_record_with_setup(
                sample,
                slope=slope,
                constant=v1.bits_float32(constant_bits),
            )
            pull_words += sum(
                left != right
                for left, right in zip(
                    actual[: capture.PULL_COUNT],
                    predicted[: capture.PULL_COUNT],
                    strict=True,
                )
            )
            center_words += sum(
                left != right
                for left, right in zip(
                    actual[capture.PULL_COUNT :],
                    predicted[capture.PULL_COUNT :],
                    strict=True,
                )
            )
        pull_differences[neighbor_offset] = pull_words
        center_differences[neighbor_offset] = center_words
    return pull_differences, center_differences


def slope_value_differences(
    samples: list[capture.SamplePosition],
    actual_records: list[tuple[int, ...]],
    constants: list[int],
    slope: float,
) -> tuple[int, int]:
    """Count pull and center words for a non-binary32 setup coefficient."""

    pull_words = 0
    center_words = 0
    for sample, actual, constant_bits in zip(
        samples,
        actual_records,
        constants,
        strict=True,
    ):
        predicted = v2.predict_record_with_setup(
            sample,
            slope=slope,
            constant=v1.bits_float32(constant_bits),
        )
        pull_words += sum(
            left != right
            for left, right in zip(
                actual[: capture.PULL_COUNT],
                predicted[: capture.PULL_COUNT],
                strict=True,
            )
        )
        center_words += sum(
            left != right
            for left, right in zip(
                actual[capture.PULL_COUNT :],
                predicted[capture.PULL_COUNT :],
                strict=True,
            )
        )
    return pull_words, center_words


def best_candidates(differences: dict[int, int]) -> JsonObject:
    minimum = min(differences.values())
    return {
        "minimumWordMismatchCount": minimum,
        "offsetsFromDeterminant": [
            offset for offset, count in differences.items() if count == minimum
        ],
        "exactOffsetsFromDeterminant": [
            offset for offset, count in differences.items() if count == 0
        ],
        "wordMismatchCountsByOffset": {
            f"{offset:+d}": count for offset, count in differences.items()
        },
    }


def arithmetic_candidate_offsets(
    exact: Fraction,
    base_bits: int,
) -> JsonObject:
    sign = -1 if exact < 0 else 1
    magnitude = abs(exact)
    result: JsonObject = {
        "exactBinary32Nearest": (v1.round_fraction_to_float32_bits(exact) - base_bits)
    }
    for precision_bits in range(24, 33):
        for rounding in ("down", "nearest-even", "up"):
            quantized = v1.quantize_binary_significand(
                magnitude,
                precision_bits,
                rounding=rounding,
            )
            bits = v1.round_fraction_to_float32_bits(sign * quantized)
            result[f"p{precision_bits}-{rounding}"] = bits - base_bits
    return result


def float32_floor_bits(value: float) -> int:
    bits = v1.float32_bits(value)
    rounded = v1.bits_float32(bits)
    if rounded > value:
        bits += 1 if value < 0 else -1
    return bits


def analyze(root: Path) -> JsonObject:
    validation, streams = opening.actual_case_streams(root)
    selector_table = v1.load_selector_table()
    record_count = 0
    word_mismatches = 0
    record_mismatches = 0
    component_mismatches: Counter[str] = Counter()
    mismatches_by_setup: dict[tuple[str, str, int], Counter[str]] = defaultdict(Counter)
    records_by_setup: dict[
        tuple[str, str, int],
        list[tuple[capture.SamplePosition, tuple[int, ...]]],
    ] = defaultdict(list)

    for capture_case in capture.CASES:
        samples = capture.sample_positions(capture_case)
        stream = streams[capture_case.name]
        offset = 0
        for endpoint in capture.ENDPOINTS:
            for sample in samples:
                actual = capture.RECORD.unpack_from(stream, offset)
                offset += capture.RECORD.size
                key = (capture_case.name, endpoint.name, sample.axis)
                records_by_setup[key].append((sample, actual))
                predicted = model.predict_record(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table,
                )
                differing = [
                    index
                    for index, (predicted_word, actual_word) in enumerate(
                        zip(predicted, actual, strict=True)
                    )
                    if predicted_word != actual_word
                ]
                record_count += 1
                if not differing:
                    continue
                record_mismatches += 1
                word_mismatches += len(differing)
                names = [COMPONENT_NAMES[index] for index in differing]
                component_mismatches.update(names)
                mismatches_by_setup[key].update(names)

    cases_by_name = {value.name: value for value in capture.CASES}
    endpoints_by_name = {value.name: value for value in capture.ENDPOINTS}
    setup_reports: list[JsonObject] = []
    pull_candidate_law_mismatches: Counter[str] = Counter()
    center_candidate_law_mismatches: Counter[str] = Counter()
    pull_candidate_law_exact_setups: Counter[str] = Counter()
    center_candidate_law_exact_setups: Counter[str] = Counter()
    determinant_pull_failures: list[JsonObject] = []
    determinant_center_failures: list[JsonObject] = []
    translated_internal_floor_center_failures: list[JsonObject] = []
    for key in sorted(records_by_setup):
        case_name, endpoint_name, axis = key
        capture_case = cases_by_name[case_name]
        endpoint = endpoints_by_name[endpoint_name]
        records = records_by_setup[key]
        samples = [sample for sample, _ in records]
        actual_records = [actual for _, actual in records]
        constants = [
            model.selected_constant_bits(
                capture_case,
                endpoint,
                sample,
                selector_table=selector_table,
            )[1]
            for sample in samples
        ]
        base_bits, phase, internal = model.determinant_slope(
            capture_case,
            endpoint,
            axis=axis,
            selector_table=selector_table,
        )
        (
            pull_name,
            pull_bits,
            center_name,
            center_bits,
            _,
            _,
        ) = model.selected_slope_bits(
            capture_case,
            endpoint,
            axis=axis,
            selector_table=selector_table,
        )
        pull_differences, center_differences = candidate_differences(
            samples,
            actual_records,
            constants,
            base_bits,
        )
        extent = capture_case.width if axis == 0 else capture_case.height
        opposite = capture_case.height if axis == 0 else capture_case.width
        delta = v1.float32_bits_fraction(endpoint.highBits) - v1.float32_bits_fraction(
            endpoint.lowBits
        )
        native_span = abs(endpoint.highBits - endpoint.lowBits)
        lower_bits = min(endpoint.lowBits, endpoint.highBits)
        arithmetic_offsets = arithmetic_candidate_offsets(delta / extent, base_bits)
        arithmetic_offsets["translatedFixedProductInternalFloor"] = (
            float32_floor_bits(internal) - base_bits
            if endpoint.lowBits != 0 and endpoint.highBits != 0
            else 0
        )
        arithmetic_offsets["exactQuotientBinary32Floor"] = (
            float32_floor_bits(float(delta / extent)) - base_bits
        )
        internal_pull_words, internal_center_words = slope_value_differences(
            samples,
            actual_records,
            constants,
            internal,
        )
        pull_candidate_law_mismatches["fixed-product-internal-p27"] += (
            internal_pull_words
        )
        pull_candidate_law_exact_setups["fixed-product-internal-p27"] += (
            internal_pull_words == 0
        )
        center_candidate_law_mismatches["fixed-product-internal-p27"] += (
            internal_center_words
        )
        center_candidate_law_exact_setups["fixed-product-internal-p27"] += (
            internal_center_words == 0
        )
        exact_quotient_pull_words, exact_quotient_center_words = (
            slope_value_differences(
                samples,
                actual_records,
                constants,
                float(delta / extent),
            )
        )
        pull_candidate_law_mismatches["exact-quotient-binary64"] += (
            exact_quotient_pull_words
        )
        pull_candidate_law_exact_setups["exact-quotient-binary64"] += (
            exact_quotient_pull_words == 0
        )
        center_candidate_law_mismatches["exact-quotient-binary64"] += (
            exact_quotient_center_words
        )
        center_candidate_law_exact_setups["exact-quotient-binary64"] += (
            exact_quotient_center_words == 0
        )
        for name, neighbor_offset in {
            "determinant-rounded-f32": 0,
            "v4": pull_bits - base_bits,
            **arithmetic_offsets,
        }.items():
            differences = pull_differences[neighbor_offset]
            pull_candidate_law_mismatches[name] += differences
            pull_candidate_law_exact_setups[name] += differences == 0
        for name, neighbor_offset in {
            "determinant-rounded-f32": 0,
            "v4": center_bits - base_bits,
            **arithmetic_offsets,
        }.items():
            differences = center_differences[neighbor_offset]
            center_candidate_law_mismatches[name] += differences
            center_candidate_law_exact_setups[name] += differences == 0
        setup_identity = {
            "case": case_name,
            "endpoint": endpoint_name,
            "axis": "x" if axis == 0 else "y",
            "extent": extent,
            "oppositeExtent": opposite,
            "origin": capture_case.originX if axis == 0 else capture_case.originY,
            "nativeSpan": native_span,
            "lowerEndpointMantissa": lower_bits & 0x7F_FFFF,
            "direction": "forward" if delta > 0 else "reverse",
            "p27Phase": fraction_metadata(phase),
        }
        if pull_differences[0]:
            determinant_pull_failures.append(
                {
                    **setup_identity,
                    "wordMismatchCount": pull_differences[0],
                    "exactOffsetsFromDeterminant": best_candidates(pull_differences)[
                        "exactOffsetsFromDeterminant"
                    ],
                }
            )
        if center_differences[0]:
            determinant_center_failures.append(
                {
                    **setup_identity,
                    "wordMismatchCount": center_differences[0],
                    "exactOffsetsFromDeterminant": best_candidates(center_differences)[
                        "exactOffsetsFromDeterminant"
                    ],
                }
            )
        internal_floor_differences = center_differences[
            arithmetic_offsets["translatedFixedProductInternalFloor"]
        ]
        if internal_floor_differences:
            translated_internal_floor_center_failures.append(
                {
                    **setup_identity,
                    "wordMismatchCount": internal_floor_differences,
                    "selectedOffsetFromDeterminant": arithmetic_offsets[
                        "translatedFixedProductInternalFloor"
                    ],
                    "exactOffsetsFromDeterminant": best_candidates(center_differences)[
                        "exactOffsetsFromDeterminant"
                    ],
                }
            )
        if key not in mismatches_by_setup:
            continue
        setup_reports.append(
            {
                "case": case_name,
                "endpoint": endpoint_name,
                "axis": "x" if axis == 0 else "y",
                "extent": extent,
                "oppositeExtent": opposite,
                "determinant": capture_case.width * capture_case.height,
                "origin": capture_case.originX if axis == 0 else capture_case.originY,
                "endpointLowBits": f"0x{endpoint.lowBits:08x}",
                "endpointHighBits": f"0x{endpoint.highBits:08x}",
                "lowerEndpointMantissa": lower_bits & 0x7F_FFFF,
                "nativeSpan": native_span,
                "direction": "forward" if delta > 0 else "reverse",
                "p27Phase": fraction_metadata(phase),
                "exactSlope": fraction_metadata(delta / extent),
                "determinantSlopeBits": f"0x{base_bits:08x}",
                "determinantInternalBits": f"0x{v1.float32_bits(internal):08x}",
                "arithmeticCandidateOffsetsFromDeterminant": arithmetic_offsets,
                "modelPullSelector": pull_name,
                "modelPullBits": f"0x{pull_bits:08x}",
                "modelPullOffsetFromDeterminant": pull_bits - base_bits,
                "modelCenterSelector": center_name,
                "modelCenterBits": f"0x{center_bits:08x}",
                "modelCenterOffsetFromDeterminant": center_bits - base_bits,
                "observedMismatchCounts": dict(
                    sorted(mismatches_by_setup[key].items())
                ),
                "pullCoefficientCandidates": best_candidates(pull_differences),
                "centerCoefficientCandidates": best_candidates(center_differences),
            }
        )

    return {
        "rasterTileDoubleRoundingOpenedAnalysisSchemaVersion": 1,
        "source": str(root),
        "sourceRawSha256": validation["rawSha256"],
        "recordCount": record_count,
        "wordCount": record_count * capture.RECORD_COMPONENT_COUNT,
        "recordMismatchCount": record_mismatches,
        "wordMismatchCount": word_mismatches,
        "componentMismatchCounts": dict(sorted(component_mismatches.items())),
        "coefficientSetupCount": len(records_by_setup),
        "pullCandidateLawWordMismatchCounts": dict(
            sorted(pull_candidate_law_mismatches.items())
        ),
        "centerCandidateLawWordMismatchCounts": dict(
            sorted(center_candidate_law_mismatches.items())
        ),
        "pullCandidateLawExactSetupCounts": dict(
            sorted(pull_candidate_law_exact_setups.items())
        ),
        "centerCandidateLawExactSetupCounts": dict(
            sorted(center_candidate_law_exact_setups.items())
        ),
        "determinantPullMismatchingSetups": determinant_pull_failures,
        "determinantCenterMismatchingSetups": determinant_center_failures,
        "translatedFixedProductInternalFloorCenterMismatchingSetups": (
            translated_internal_floor_center_failures
        ),
        "mismatchingSetupCount": len(mismatches_by_setup),
        "mismatchingSetups": setup_reports,
        "schema6WasOpenedBeforeThisAnalysis": True,
        "prospectiveEvidenceForAnyRefit": False,
        "productionShaderAuthorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report = analyze(arguments.root)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
