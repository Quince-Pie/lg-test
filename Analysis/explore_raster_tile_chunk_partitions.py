#!/usr/bin/env python3
"""Search segmented partial-product layouts for the tile product stage."""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import raster_tile_selector_model as arithmetic
from explore_schema34_post_reciprocal_constant import load_setups


TRUNCATION_BITS = 19
BIAS_UNITS = 10
OUTPUT_BITS = 27


@dataclass(frozen=True, slots=True)
class ProductCase:
    multiplicand: int
    multiplier: int
    expected_index: int


def normalized_distance(displacement: int) -> int:
    index, _ = arithmetic.float_significand_and_lsb_exponent(
        arithmetic.float32_bits(float(abs(displacement)))
    )
    return index


def aggregate_index(multiplicand: int, multiplier: int) -> int:
    product = multiplicand * multiplier
    shift = product.bit_length() - OUTPUT_BITS
    return (
        ((product >> TRUNCATION_BITS) << TRUNCATION_BITS)
        + (BIAS_UNITS << TRUNCATION_BITS)
    ) >> shift


def partition_masks(bit_count: int, width: int, phase: int) -> tuple[int, ...]:
    boundaries = {0, bit_count}
    boundary = phase
    while boundary < bit_count:
        if boundary > 0:
            boundaries.add(boundary)
        boundary += width
    ordered = sorted(boundaries)
    return tuple(
        ((1 << end) - 1) ^ ((1 << start) - 1)
        for start, end in zip(ordered, ordered[1:])
    )


def segmented_index(
    multiplicand: int,
    multiplier: int,
    *,
    width: int,
    phase: int,
) -> int:
    product = multiplicand * multiplier
    shift = product.bit_length() - OUTPUT_BITS
    subtotal = sum(
        ((multiplicand * (multiplier & mask)) >> TRUNCATION_BITS)
        << TRUNCATION_BITS
        for mask in partition_masks(multiplier.bit_length(), width, phase)
    )
    return (subtotal + (BIAS_UNITS << TRUNCATION_BITS)) >> shift


def old_product_cases(report_paths: list[Path]) -> list[ProductCase]:
    unique: dict[tuple[int, int], ProductCase] = {}
    for report_path in report_paths:
        for setup in load_setups(report_path, 15):
            if setup.displacement == 0:
                continue
            distance = normalized_distance(setup.displacement)
            key = (setup.numerator_index, distance)
            unique[key] = ProductCase(
                *key,
                aggregate_index(*key),
            )
    return list(unique.values())


def analyze(
    report_paths: list[Path],
    *,
    new_numerator: int,
    new_distance: int,
) -> dict[str, object]:
    old = old_product_cases(report_paths)
    new_aggregate = aggregate_index(new_numerator, new_distance)
    results: list[dict[str, object]] = []
    for orientation in ("numerator-distance", "distance-numerator"):
        for width in range(1, 25):
            for phase in range(1, width + 1):
                mismatches = 0
                for case in old:
                    left, right = (
                        (case.multiplicand, case.multiplier)
                        if orientation == "numerator-distance"
                        else (case.multiplier, case.multiplicand)
                    )
                    if segmented_index(
                        left,
                        right,
                        width=width,
                        phase=phase,
                    ) != case.expected_index:
                        mismatches += 1
                left, right = (
                    (new_numerator, new_distance)
                    if orientation == "numerator-distance"
                    else (new_distance, new_numerator)
                )
                new_index = segmented_index(
                    left,
                    right,
                    width=width,
                    phase=phase,
                )
                results.append(
                    {
                        "orientation": orientation,
                        "width": width,
                        "phase": phase,
                        "oldMismatchCount": mismatches,
                        "newOffsetFromAggregate": new_index - new_aggregate,
                    }
                )
    results.sort(
        key=lambda result: (
            result["newOffsetFromAggregate"] != -1,
            result["oldMismatchCount"],
            result["orientation"],
            result["width"],
            result["phase"],
        )
    )
    return {
        "oldUniqueProductCount": len(old),
        "newAggregateIndex": new_aggregate,
        "candidateCount": len(results),
        "exactOldAndNewLower": [
            result
            for result in results
            if result["oldMismatchCount"] == 0
            and result["newOffsetFromAggregate"] == -1
        ],
        "bestNewLower": [
            result
            for result in results
            if result["newOffsetFromAggregate"] == -1
        ][:32],
        "exactOld": [
            result for result in results if result["oldMismatchCount"] == 0
        ][:64],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--new-numerator", type=int, required=True)
    parser.add_argument("--new-distance", type=int, required=True)
    arguments = parser.parse_args()
    print(
        json.dumps(
            analyze(
                arguments.reports,
                new_numerator=arguments.new_numerator,
                new_distance=arguments.new_distance,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
