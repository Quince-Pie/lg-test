#!/usr/bin/env python3
"""Test separately rounded endpoint products as schema-4 slope generators."""

import argparse
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

import explore_schema4_endpoint_constant_pipeline as arithmetic
import raster_tile_selector_model as v1
import validate_raster_tile_phase_holdout as capture


type JsonObject = dict[str, Any]


def negate(term: arithmetic.BinaryTerm | None) -> arithmetic.BinaryTerm | None:
    if term is None:
        return None
    return arithmetic.BinaryTerm(-term.index, term.lsb_exponent)


def term_fraction(term: arithmetic.BinaryTerm | None) -> Fraction:
    if term is None:
        return Fraction(0)
    return term.index * v1.power_of_two(term.lsb_exponent)


def reciprocal_binary_term(
    numerator: arithmetic.BinaryTerm | None,
    determinant: int,
    reciprocal_index: int,
    configuration: arithmetic.ProductConfiguration,
    *,
    swapped: bool,
) -> arithmetic.BinaryTerm | None:
    if numerator is None:
        return None
    reciprocal_exponent = -(determinant - 1).bit_length() - 24
    magnitude = abs(numerator.index)
    if swapped:
        index, exponent = v1.product_stage(
            reciprocal_index,
            reciprocal_exponent,
            magnitude,
            numerator.lsb_exponent,
            output_bits=configuration.output_bits,
            truncation_bits=configuration.truncation_bits,
            bias_units=configuration.bias_units,
        )
    else:
        index, exponent = v1.product_stage(
            magnitude,
            numerator.lsb_exponent,
            reciprocal_index,
            reciprocal_exponent,
            output_bits=configuration.output_bits,
            truncation_bits=configuration.truncation_bits,
            bias_units=configuration.bias_units,
        )
    return arithmetic.BinaryTerm(
        -index if numerator.index < 0 else index,
        exponent,
    )


def directed_float32_bits(value: Fraction, rounding: str) -> int:
    nearest = v1.round_fraction_to_float32_bits(value)
    nearest_value = v1.float32_bits_fraction(nearest)
    if rounding == "nearest-even" or nearest_value == value:
        return nearest
    if rounding == "down":
        return nearest - 1 if nearest_value > value else nearest
    if rounding == "up":
        return nearest + 1 if nearest_value < value else nearest
    raise ValueError(rounding)


def slope_candidates(
    capture_case: object,
    endpoint: object,
    axis: int,
    selector_table: tuple[int, ...],
) -> dict[str, Fraction]:
    opposite = capture_case.height if axis == 0 else capture_case.width
    determinant = capture_case.width * capture_case.height
    reciprocal_index = v1.reciprocal_selector(determinant, selector_table)
    result: dict[str, Fraction] = {}

    high_value = v1.bits_float32(endpoint.highBits)
    low_value = v1.bits_float32(endpoint.lowBits)
    result["separate-established-fixed-product"] = Fraction.from_float(
        v1.fixed_product_slope(
            high_value,
            opposite_edge=opposite,
            determinant=determinant,
            reciprocal_index=reciprocal_index,
        )
        - v1.fixed_product_slope(
            low_value,
            opposite_edge=opposite,
            determinant=determinant,
            reciprocal_index=reciprocal_index,
        )
    )

    for endpoint_configuration in arithmetic.ENDPOINT_PRODUCT_CONFIGURATIONS:
        for reciprocal_configuration in (
            arithmetic.RECIPROCAL_PRODUCT_CONFIGURATIONS
        ):
            for factorization in arithmetic.ENDPOINT_FACTORIZATIONS:
                high = arithmetic.endpoint_term(
                    endpoint.highBits,
                    opposite,
                    1,
                    endpoint_configuration,
                    factorization=factorization,
                )
                low = arithmetic.endpoint_term(
                    endpoint.lowBits,
                    opposite,
                    1,
                    endpoint_configuration,
                    factorization=factorization,
                )
                for swapped in (False, True):
                    suffix = (
                        f"{endpoint_configuration.name}:"
                        f"{reciprocal_configuration.name}:"
                        f"{factorization}:{'swap' if swapped else 'ordered'}"
                    )
                    combined = arithmetic.add_terms((high, negate(low)))
                    result[f"subtract-before-reciprocal:{suffix}"] = term_fraction(
                        reciprocal_binary_term(
                            combined,
                            determinant,
                            reciprocal_index,
                            reciprocal_configuration,
                            swapped=swapped,
                        )
                    )
                    high_result = reciprocal_binary_term(
                        high,
                        determinant,
                        reciprocal_index,
                        reciprocal_configuration,
                        swapped=swapped,
                    )
                    low_result = reciprocal_binary_term(
                        low,
                        determinant,
                        reciprocal_index,
                        reciprocal_configuration,
                        swapped=swapped,
                    )
                    result[f"subtract-after-reciprocal:{suffix}"] = (
                        term_fraction(high_result) - term_fraction(low_result)
                    )
                    high_bits = arithmetic.reciprocal_term(
                        high,
                        determinant,
                        reciprocal_index,
                        reciprocal_configuration,
                        swapped=swapped,
                    )
                    low_bits = arithmetic.reciprocal_term(
                        low,
                        determinant,
                        reciprocal_index,
                        reciprocal_configuration,
                        swapped=swapped,
                    )
                    result[f"subtract-after-f32:{suffix}"] = (
                        v1.float32_bits_fraction(high_bits)
                        - v1.float32_bits_fraction(low_bits)
                    )
            for endpoint_pipeline in arithmetic.ENDPOINT_PIPELINES:
                try:
                    high = arithmetic.endpoint_pipeline_term(
                        endpoint.highBits,
                        opposite,
                        1,
                        endpoint_configuration,
                        pipeline=endpoint_pipeline,
                    )
                    low = arithmetic.endpoint_pipeline_term(
                        endpoint.lowBits,
                        opposite,
                        1,
                        endpoint_configuration,
                        pipeline=endpoint_pipeline,
                    )
                except ValueError:
                    continue
                for swapped in (False, True):
                    suffix = (
                        f"{endpoint_configuration.name}:"
                        f"{reciprocal_configuration.name}:"
                        f"{endpoint_pipeline}:"
                        f"{'swap' if swapped else 'ordered'}"
                    )
                    combined = arithmetic.add_terms((high, negate(low)))
                    result[f"pipeline-before-reciprocal:{suffix}"] = term_fraction(
                        reciprocal_binary_term(
                            combined,
                            determinant,
                            reciprocal_index,
                            reciprocal_configuration,
                            swapped=swapped,
                        )
                    )
                    high_result = reciprocal_binary_term(
                        high,
                        determinant,
                        reciprocal_index,
                        reciprocal_configuration,
                        swapped=swapped,
                    )
                    low_result = reciprocal_binary_term(
                        low,
                        determinant,
                        reciprocal_index,
                        reciprocal_configuration,
                        swapped=swapped,
                    )
                    result[f"pipeline-after-reciprocal:{suffix}"] = (
                        term_fraction(high_result) - term_fraction(low_result)
                    )
    return result


def analyze(recovery_path: Path) -> JsonObject:
    recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
    cases = {case.name: case for case in capture.CASES}
    endpoints = {endpoint.name: endpoint for endpoint in capture.ENDPOINTS}
    selector_table = v1.load_selector_table()
    scores: dict[str, Counter[str]] = {}
    examples: dict[str, list[JsonObject]] = {}

    for group in recovery["groups"]:
        capture_case = cases[group["case"]]
        endpoint = endpoints[group["endpoint"]]
        axis = int(group["axis"])
        base_bits = int(group["slopeBits"], 16)
        accepted = {int(offset) for offset in group["acceptedSlopeOffsets"]}
        for base_name, value in slope_candidates(
            capture_case,
            endpoint,
            axis,
            selector_table,
        ).items():
            for rounding in ("nearest-even", "down", "up"):
                name = f"{base_name}:{rounding}"
                score = scores.setdefault(name, Counter())
                score["setupCount"] += 1
                try:
                    offset = directed_float32_bits(value, rounding) - base_bits
                except ValueError:
                    score["unavailableCount"] += 1
                    continue
                score["matchCount"] += offset in accepted
                score[f"offset:{offset}"] += 1
                if offset not in accepted:
                    failures = examples.setdefault(name, [])
                    if len(failures) < 32:
                        failures.append(
                            {
                                "case": capture_case.name,
                                "endpoint": endpoint.name,
                                "axis": axis,
                                "predictedOffset": offset,
                                "acceptedOffsets": sorted(accepted),
                            }
                        )

    candidates = []
    for name, score in sorted(
        scores.items(),
        key=lambda item: (-item[1]["matchCount"], item[0]),
    ):
        candidates.append(
            {
                "name": name,
                "setupCount": score["setupCount"],
                "matchCount": score["matchCount"],
                "unavailableCount": score["unavailableCount"],
                "offsetCounts": {
                    key.removeprefix("offset:"): value
                    for key, value in sorted(score.items())
                    if key.startswith("offset:")
                },
                "firstFailures": examples.get(name, []),
            }
        )
    return {
        "schema4SeparateEndpointSlopeAnalysisSchemaVersion": 1,
        "sourceRecovery": str(recovery_path),
        "candidateCount": len(candidates),
        "setupCount": len(recovery["groups"]),
        "candidates": candidates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recovery", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = analyze(arguments.recovery)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(rendered, end="")
    else:
        arguments.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
