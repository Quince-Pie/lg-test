#!/usr/bin/env python3
"""Recover the tile multiplier's discarded-column carry propagation depth."""

import argparse
import json
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import open_raster_tile_sticky_holdout as opening
import raster_tile_coefficient_model as coefficient_base
import raster_tile_coefficient_model_v2 as coefficients
import raster_tile_selector_model as arithmetic
import raster_tile_sticky_holdout_model as model
import validate_raster_tile_sticky_holdout as capture


type JsonObject = dict[str, Any]

TRUNCATION_BITS = coefficient_base.TILE_STAGE_TRUNCATION_BITS
BIAS_UNITS = coefficient_base.TILE_STAGE_BIAS_UNITS
OUTPUT_BITS = coefficient_base.TILE_STAGE_OUTPUT_BITS


@dataclass(frozen=True, slots=True)
class CarryConstraint:
    """One product whose observed record distinguishes two carry endpoints."""

    multiplicand: int
    multiplier: int
    product_shift: int
    partial_index: int
    aggregate_index: int
    expected_index: int
    label: str


def tile_displacement(
    capture_case: object,
    endpoint: object,
    sample: object,
) -> int:
    axis = sample.axis
    extent = capture_case.width if axis == 0 else capture_case.height
    origin = capture_case.originX if axis == 0 else capture_case.originY
    anchor_position = (
        origin + extent if axis == 0 and sample.primitive == 0 else origin
    )
    return sample.tile * capture.TILE_SIZE - anchor_position


def product_indices(
    multiplicand: int,
    multiplier: int,
) -> tuple[int, int, int]:
    product = multiplicand * multiplier
    product_shift = product.bit_length() - OUTPUT_BITS
    partial = arithmetic.partial_product_sum(
        multiplicand,
        multiplier,
        TRUNCATION_BITS,
    )
    bias = BIAS_UNITS << TRUNCATION_BITS
    partial_index = (partial + bias) >> product_shift
    aggregate_index = (
        ((product >> TRUNCATION_BITS) << TRUNCATION_BITS) + bias
    ) >> product_shift
    return product_shift, partial_index, aggregate_index


def recover_constraints(root: Path) -> tuple[list[CarryConstraint], JsonObject]:
    _, actual_streams = opening.actual_case_streams(root)
    selector_table = arithmetic.load_selector_table()
    partial_policy = replace(
        coefficients.MEASURED_POLICY,
        tile_discarded_carry_limit=0,
    )
    aggregate_policy = replace(
        coefficients.MEASURED_POLICY,
        tile_discarded_carry_limit=None,
    )
    constraints: dict[tuple[str, str, int, int, int], CarryConstraint] = {}
    target_counts: Counter[str] = Counter()
    discriminating_records = 0
    intermediate_differences = 0
    neither_endpoint = 0

    for capture_case in capture.CASES:
        actual_stream = actual_streams[capture_case.name]
        offset = 0
        for endpoint in capture.ENDPOINTS:
            for sample in capture.sample_positions(capture_case):
                actual_record = capture.RECORD.unpack_from(actual_stream, offset)
                offset += capture.RECORD.size
                displacement = tile_displacement(capture_case, endpoint, sample)
                if displacement == 0:
                    continue
                _, numerator, _ = coefficient_base.first_stage_numerator(
                    capture_case,
                    endpoint,
                    axis=sample.axis,
                    bias_units=coefficients.MEASURED_POLICY.constant_first_bias,
                )
                distance, _ = arithmetic.float_significand_and_lsb_exponent(
                    arithmetic.float32_bits(float(abs(displacement)))
                )
                product_shift, partial_index, aggregate_index = product_indices(
                    numerator,
                    distance,
                )
                if partial_index == aggregate_index:
                    continue
                intermediate_differences += 1
                partial_record = model.predict_record(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table,
                    policy=partial_policy,
                )
                aggregate_record = model.predict_record(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table,
                    policy=aggregate_policy,
                )
                if partial_record == aggregate_record:
                    continue
                discriminating_records += 1
                if actual_record == partial_record:
                    target = "partial"
                    expected_index = partial_index
                elif actual_record == aggregate_record:
                    target = "aggregate"
                    expected_index = aggregate_index
                else:
                    neither_endpoint += 1
                    continue
                target_counts[target] += 1
                key = (
                    capture_case.name,
                    endpoint.name,
                    sample.axis,
                    sample.primitive,
                    sample.tile,
                )
                constraint = CarryConstraint(
                    multiplicand=numerator,
                    multiplier=distance,
                    product_shift=product_shift,
                    partial_index=partial_index,
                    aggregate_index=aggregate_index,
                    expected_index=expected_index,
                    label=(
                        f"{capture_case.name}/{endpoint.name}/axis{sample.axis}/"
                        f"primitive{sample.primitive}/tile{sample.tile}"
                    ),
                )
                previous = constraints.setdefault(key, constraint)
                if previous != constraint:
                    raise ValueError(f"inconsistent target for {constraint.label}")

    metadata: JsonObject = {
        "intermediateDifferenceRecordCount": intermediate_differences,
        "recordDiscriminationCount": discriminating_records,
        "neitherEndpointRecordCount": neither_endpoint,
        "targetRecordCounts": dict(sorted(target_counts.items())),
        "uniqueConstraintCount": len(constraints),
    }
    return list(constraints.values()), metadata


def top_column_carry(
    multiplicand: int,
    multiplier: int,
    *,
    depth: int,
    truncation_bits: int = TRUNCATION_BITS,
) -> int:
    """Propagate only the highest ``depth`` discarded product columns."""

    if not 0 <= depth <= truncation_bits:
        raise ValueError("carry depth is outside the discarded-column range")
    cutoff = truncation_bits - depth
    low_mask = (1 << truncation_bits) - 1
    remainders = tuple(
        (multiplicand << bit) & low_mask
        for bit in range(multiplier.bit_length())
        if multiplier & (1 << bit)
    )
    carry = 0
    for column in range(cutoff, truncation_bits):
        column_total = carry + sum(
            (remainder >> column) & 1 for remainder in remainders
        )
        carry = column_total >> 1
    return carry


def predicted_index(
    constraint: CarryConstraint,
    *,
    depth: int,
    swapped: bool,
) -> int:
    multiplicand, multiplier = (
        (constraint.multiplier, constraint.multiplicand)
        if swapped
        else (constraint.multiplicand, constraint.multiplier)
    )
    partial = arithmetic.partial_product_sum(
        multiplicand,
        multiplier,
        TRUNCATION_BITS,
    )
    carry = top_column_carry(
        multiplicand,
        multiplier,
        depth=depth,
    )
    adjusted = partial + ((carry + BIAS_UNITS) << TRUNCATION_BITS)
    return adjusted >> constraint.product_shift


def limited_carry_product_stage(
    multiplicand: int,
    multiplicand_exponent: int,
    multiplier: int,
    multiplier_exponent: int,
    *,
    output_bits: int,
    truncation_bits: int,
    bias_units: int,
    discarded_carry_limit: int | None,
) -> tuple[int, int]:
    """Replay a one-column carry-propagation tile multiplier candidate."""

    del discarded_carry_limit
    product = multiplicand * multiplier
    product_shift = product.bit_length() - output_bits
    partial = arithmetic.partial_product_sum(
        multiplicand,
        multiplier,
        truncation_bits,
    )
    carry = top_column_carry(
        multiplicand,
        multiplier,
        depth=1,
        truncation_bits=truncation_bits,
    )
    adjusted = partial + ((carry + bias_units) << truncation_bits)
    return (
        adjusted >> product_shift,
        multiplicand_exponent + multiplier_exponent + product_shift,
    )


def compare_full_capture(root: Path) -> JsonObject:
    _, actual_streams = opening.actual_case_streams(root)
    selector_table = arithmetic.load_selector_table()
    original_stage = coefficients.sticky_product_stage
    record_mismatches = 0
    word_mismatches = 0
    case_results: list[JsonObject] = []
    try:
        coefficients.sticky_product_stage = limited_carry_product_stage
        for capture_case in capture.CASES:
            actual_stream = actual_streams[capture_case.name]
            offset = 0
            case_record_mismatches = 0
            case_word_mismatches = 0
            for endpoint in capture.ENDPOINTS:
                for sample in capture.sample_positions(capture_case):
                    actual_record = capture.RECORD.unpack_from(actual_stream, offset)
                    offset += capture.RECORD.size
                    predicted_record = model.predict_record(
                        capture_case,
                        endpoint,
                        sample,
                        selector_table,
                    )
                    differences = sum(
                        actual != predicted
                        for actual, predicted in zip(
                            actual_record,
                            predicted_record,
                            strict=True,
                        )
                    )
                    if differences:
                        case_record_mismatches += 1
                        case_word_mismatches += differences
            record_mismatches += case_record_mismatches
            word_mismatches += case_word_mismatches
            case_results.append(
                {
                    "name": capture_case.name,
                    "recordMismatchCount": case_record_mismatches,
                    "wordMismatchCount": case_word_mismatches,
                    "exact": case_record_mismatches == 0,
                }
            )
    finally:
        coefficients.sticky_product_stage = original_stage
    return {
        "recordCount": sum(
            len(capture.sample_positions(capture_case))
            * len(capture.ENDPOINTS)
            for capture_case in capture.CASES
        ),
        "recordMismatchCount": record_mismatches,
        "wordMismatchCount": word_mismatches,
        "exact": record_mismatches == 0,
        "cases": case_results,
    }


def compare_schema13(root: Path) -> JsonObject:
    import open_raster_tile_coefficient_holdout as opening13
    import raster_tile_iterator_model_v2 as iterator
    import validate_raster_tile_coefficient_holdout as capture13

    _, actual_streams = opening13.actual_case_streams(root)
    selector_table = arithmetic.load_selector_table()
    original_stage = coefficients.sticky_product_stage
    record_mismatches = 0
    word_mismatches = 0
    record_count = 0
    try:
        coefficients.sticky_product_stage = limited_carry_product_stage
        for capture_case in capture13.CASES:
            actual_stream = actual_streams[capture_case.name]
            offset = 0
            for endpoint in capture13.ENDPOINTS:
                for sample in capture13.sample_positions(capture_case):
                    actual_record = capture13.RECORD.unpack_from(
                        actual_stream,
                        offset,
                    )
                    offset += capture13.RECORD.size
                    predicted_record = iterator.predict_record(
                        capture13,
                        capture_case,
                        endpoint,
                        sample,
                        selector_table,
                        force_factorized=True,
                    )
                    differences = sum(
                        actual != predicted
                        for actual, predicted in zip(
                            actual_record,
                            predicted_record,
                            strict=True,
                        )
                    )
                    record_count += 1
                    if differences:
                        record_mismatches += 1
                        word_mismatches += differences
    finally:
        coefficients.sticky_product_stage = original_stage
    return {
        "source": str(root.resolve()),
        "recordCount": record_count,
        "recordMismatchCount": record_mismatches,
        "wordMismatchCount": word_mismatches,
        "exact": record_mismatches == 0,
    }


def compare_recovered_setups(report_paths: list[Path]) -> JsonObject:
    from explore_schema34_post_reciprocal_constant import (
        constant_bits,
        load_setups,
    )

    setup_count = 0
    mismatch_count = 0
    report_results: list[JsonObject] = []
    for report_path in report_paths:
        report_setup_count = 0
        report_mismatch_count = 0
        for setup in load_setups(report_path, 15):
            report_setup_count += 1
            setup_count += 1
            if setup.displacement == 0:
                term = 0
            else:
                distance_index, distance_exponent = (
                    arithmetic.float_significand_and_lsb_exponent(
                        arithmetic.float32_bits(float(abs(setup.displacement)))
                    )
                )
                middle_index, middle_exponent = limited_carry_product_stage(
                    setup.numerator_index,
                    setup.numerator_exponent,
                    distance_index,
                    distance_exponent,
                    output_bits=OUTPUT_BITS,
                    truncation_bits=TRUNCATION_BITS,
                    bias_units=BIAS_UNITS,
                    discarded_carry_limit=None,
                )
                result_index, result_exponent = arithmetic.product_stage(
                    middle_index,
                    middle_exponent,
                    setup.reciprocal_index,
                    setup.reciprocal_exponent,
                    output_bits=27,
                    truncation_bits=19,
                    bias_units=20,
                )
                term = (
                    result_index * arithmetic.power_of_two(result_exponent)
                )
                if setup.displacement < 0:
                    term = -term
            if constant_bits(setup, term) not in setup.allowed_bits:
                report_mismatch_count += 1
                mismatch_count += 1
        report_results.append(
            {
                "path": str(report_path.resolve()),
                "setupCount": report_setup_count,
                "mismatchCount": report_mismatch_count,
                "exact": report_mismatch_count == 0,
            }
        )
    return {
        "setupCount": setup_count,
        "mismatchCount": mismatch_count,
        "exact": mismatch_count == 0,
        "reports": report_results,
    }


def analyze(
    root: Path,
    *,
    schema13_root: Path | None,
    recovered_reports: list[Path],
) -> JsonObject:
    constraints, metadata = recover_constraints(root)
    candidates: list[JsonObject] = []
    for swapped in (False, True):
        for depth in range(TRUNCATION_BITS + 1):
            failures = [
                constraint
                for constraint in constraints
                if predicted_index(
                    constraint,
                    depth=depth,
                    swapped=swapped,
                )
                != constraint.expected_index
            ]
            candidates.append(
                {
                    "orientation": (
                        "distance-by-numerator"
                        if swapped
                        else "numerator-by-distance"
                    ),
                    "propagatedDiscardedColumnCount": depth,
                    "mismatchCount": len(failures),
                    "mismatchExamples": [
                        constraint.label for constraint in failures[:8]
                    ],
                }
            )
    candidates.sort(
        key=lambda candidate: (
            candidate["mismatchCount"],
            candidate["orientation"],
            candidate["propagatedDiscardedColumnCount"],
        )
    )
    result: JsonObject = {
        "source": str(root.resolve()),
        **metadata,
        "candidateCount": len(candidates),
        "exactCandidates": [
            candidate for candidate in candidates if candidate["mismatchCount"] == 0
        ],
        "bestCandidates": candidates[:16],
        "oneColumnFullCapture": compare_full_capture(root),
    }
    if schema13_root is not None:
        result["schema13FullCapture"] = compare_schema13(schema13_root)
    if recovered_reports:
        result["recoveredSetups"] = compare_recovered_setups(recovered_reports)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--schema13", type=Path)
    parser.add_argument("--recovered-report", action="append", type=Path, default=[])
    arguments = parser.parse_args()
    print(
        json.dumps(
            analyze(
                arguments.capture,
                schema13_root=arguments.schema13,
                recovered_reports=arguments.recovered_report,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
