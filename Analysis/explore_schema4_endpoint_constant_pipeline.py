#!/usr/bin/env python3
"""Test staged endpoint-composition constants against schema-4 raw words."""

import argparse
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import explore_raster_tile_center_p36 as p36
import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v8 as v8
import validate_raster_tile_phase_holdout as capture


type JsonObject = dict[str, Any]

TARGET_ENDPOINTS = {
    "opened-512-x",
    "opened-512-y",
    "opened-640-x",
    "opened-640-y",
    "opened-896-x",
    "opened-896-y",
}


@dataclass(frozen=True, slots=True)
class BinaryTerm:
    index: int
    lsb_exponent: int


@dataclass(frozen=True, slots=True)
class ProductConfiguration:
    output_bits: int
    truncation_bits: int
    bias_units: int

    @property
    def name(self) -> str:
        return f"p{self.output_bits}-t{self.truncation_bits}-b{self.bias_units}"


ENDPOINT_PRODUCT_CONFIGURATIONS = (
    ProductConfiguration(25, 16, 28),
    ProductConfiguration(25, 17, 14),
    ProductConfiguration(25, 17, 15),
    ProductConfiguration(27, 16, 14),
)
RECIPROCAL_PRODUCT_CONFIGURATIONS = (
    ProductConfiguration(27, 19, 20),
    ProductConfiguration(27, 15, 108),
)
ENDPOINT_FACTORIZATIONS = (
    "endpoint-x-float-edge-distance",
    "float-edge-distance-x-endpoint",
    "endpoint-x-edge-distance",
    "endpoint-edge-x-distance",
    "endpoint-distance-x-edge",
    "edge-x-endpoint-distance",
    "distance-x-endpoint-edge",
    "edge-distance-x-endpoint",
)
ENDPOINT_PIPELINES = (
    "stage-edge-exact-distance",
    "stage-distance-exact-edge",
    "stage-edge-stage-distance",
    "stage-distance-stage-edge",
)


def endpoint_term(
    bits: int,
    opposite_edge: int,
    distance: int,
    configuration: ProductConfiguration,
    *,
    factorization: str,
) -> BinaryTerm | None:
    if distance == 0 or bits & 0x7FFF_FFFF == 0:
        return None
    value = v1.bits_float32(bits)
    significand, lsb_exponent = v1.float_significand_and_lsb_exponent(
        bits & 0x7FFF_FFFF
    )
    distance_magnitude = abs(distance)
    if factorization in {
        "endpoint-x-float-edge-distance",
        "float-edge-distance-x-endpoint",
    }:
        weight_significand, weight_exponent = (
            v1.float_significand_and_lsb_exponent(
                v1.float32_bits(float(opposite_edge * distance_magnitude))
            )
        )
        if factorization == "endpoint-x-float-edge-distance":
            multiplicand, multiplicand_exponent = significand, lsb_exponent
            multiplier, multiplier_exponent = weight_significand, weight_exponent
        else:
            multiplicand, multiplicand_exponent = weight_significand, weight_exponent
            multiplier, multiplier_exponent = significand, lsb_exponent
        index, exponent = v1.product_stage(
            multiplicand,
            multiplicand_exponent,
            multiplier,
            multiplier_exponent,
            output_bits=configuration.output_bits,
            truncation_bits=configuration.truncation_bits,
            bias_units=configuration.bias_units,
        )
    else:
        factors = {
            "endpoint-x-edge-distance": (
                significand,
                opposite_edge * distance_magnitude,
            ),
            "endpoint-edge-x-distance": (
                significand * opposite_edge,
                distance_magnitude,
            ),
            "endpoint-distance-x-edge": (
                significand * distance_magnitude,
                opposite_edge,
            ),
            "edge-x-endpoint-distance": (
                opposite_edge,
                significand * distance_magnitude,
            ),
            "distance-x-endpoint-edge": (
                distance_magnitude,
                significand * opposite_edge,
            ),
            "edge-distance-x-endpoint": (
                opposite_edge * distance_magnitude,
                significand,
            ),
        }
        multiplicand, multiplier = factors[factorization]
        index, exponent = v1.product_stage(
            multiplicand,
            lsb_exponent,
            multiplier,
            0,
            output_bits=configuration.output_bits,
            truncation_bits=configuration.truncation_bits,
            bias_units=configuration.bias_units,
        )
    negative = (value < 0.0) != (distance < 0)
    return BinaryTerm(-index if negative else index, exponent)


def add_terms(terms: tuple[BinaryTerm | None, ...]) -> BinaryTerm | None:
    present = tuple(term for term in terms if term is not None)
    if not present:
        return None
    exponent = min(term.lsb_exponent for term in present)
    index = sum(term.index << (term.lsb_exponent - exponent) for term in present)
    return None if index == 0 else BinaryTerm(index, exponent)


def staged_binary_product(
    term: BinaryTerm,
    multiplier: int,
    configuration: ProductConfiguration,
) -> BinaryTerm:
    index, exponent = v1.product_stage(
        abs(term.index),
        term.lsb_exponent,
        multiplier,
        0,
        output_bits=configuration.output_bits,
        truncation_bits=configuration.truncation_bits,
        bias_units=configuration.bias_units,
    )
    return BinaryTerm(-index if term.index < 0 else index, exponent)


def endpoint_pipeline_term(
    bits: int,
    opposite_edge: int,
    distance: int,
    configuration: ProductConfiguration,
    *,
    pipeline: str,
) -> BinaryTerm | None:
    if distance == 0 or bits & 0x7FFF_FFFF == 0:
        return None
    value = v1.bits_float32(bits)
    significand, exponent = v1.float_significand_and_lsb_exponent(
        bits & 0x7FFF_FFFF
    )
    term = BinaryTerm(significand, exponent)
    distance_magnitude = abs(distance)
    if pipeline == "stage-edge-exact-distance":
        term = staged_binary_product(term, opposite_edge, configuration)
        term = BinaryTerm(term.index * distance_magnitude, term.lsb_exponent)
    elif pipeline == "stage-distance-exact-edge":
        term = staged_binary_product(term, distance_magnitude, configuration)
        term = BinaryTerm(term.index * opposite_edge, term.lsb_exponent)
    elif pipeline == "stage-edge-stage-distance":
        term = staged_binary_product(term, opposite_edge, configuration)
        term = staged_binary_product(term, distance_magnitude, configuration)
    elif pipeline == "stage-distance-stage-edge":
        term = staged_binary_product(term, distance_magnitude, configuration)
        term = staged_binary_product(term, opposite_edge, configuration)
    else:
        raise ValueError(f"unknown endpoint pipeline: {pipeline}")
    negative = (value < 0.0) != (distance < 0)
    return BinaryTerm(-term.index if negative else term.index, term.lsb_exponent)


def reciprocal_term(
    numerator: BinaryTerm | None,
    determinant: int,
    reciprocal_index: int,
    configuration: ProductConfiguration,
    *,
    swapped: bool,
) -> int:
    if numerator is None:
        return 0
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
    value = math.ldexp(index, exponent)
    return v1.float32_bits(-value if numerator.index < 0 else value)


def endpoint_weighted_constant(
    low_bits: int,
    high_bits: int,
    *,
    extent: int,
    opposite_edge: int,
    displacement: int,
    determinant: int,
    reciprocal_index: int,
    endpoint_configuration: ProductConfiguration,
    reciprocal_configuration: ProductConfiguration,
    endpoint_factorization: str,
    swap_reciprocal_product: bool,
) -> int:
    numerator = add_terms(
        (
            endpoint_term(
                low_bits,
                opposite_edge,
                extent - displacement,
                endpoint_configuration,
                factorization=endpoint_factorization,
            ),
            endpoint_term(
                high_bits,
                opposite_edge,
                displacement,
                endpoint_configuration,
                factorization=endpoint_factorization,
            ),
        )
    )
    return reciprocal_term(
        numerator,
        determinant,
        reciprocal_index,
        reciprocal_configuration,
        swapped=swap_reciprocal_product,
    )


def endpoint_pipeline_constant(
    low_bits: int,
    high_bits: int,
    *,
    extent: int,
    opposite_edge: int,
    displacement: int,
    determinant: int,
    reciprocal_index: int,
    endpoint_configuration: ProductConfiguration,
    reciprocal_configuration: ProductConfiguration,
    endpoint_pipeline: str,
    swap_reciprocal_product: bool,
) -> int:
    numerator = add_terms(
        (
            endpoint_pipeline_term(
                low_bits,
                opposite_edge,
                extent - displacement,
                endpoint_configuration,
                pipeline=endpoint_pipeline,
            ),
            endpoint_pipeline_term(
                high_bits,
                opposite_edge,
                displacement,
                endpoint_configuration,
                pipeline=endpoint_pipeline,
            ),
        )
    )
    return reciprocal_term(
        numerator,
        determinant,
        reciprocal_index,
        reciprocal_configuration,
        swapped=swap_reciprocal_product,
    )


def endpoint_dot_product_constant(
    low_bits: int,
    high_bits: int,
    *,
    extent: int,
    opposite_edge: int,
    displacement: int,
    determinant: int,
    reciprocal_index: int,
    endpoint_configuration: ProductConfiguration,
    reciprocal_configuration: ProductConfiguration,
    swap_reciprocal_product: bool,
) -> int:
    weighted: list[tuple[int, int, int]] = []
    for bits, weight in (
        (low_bits, opposite_edge * (extent - displacement)),
        (high_bits, opposite_edge * displacement),
    ):
        if weight == 0 or bits & 0x7FFF_FFFF == 0:
            continue
        value = v1.bits_float32(bits)
        significand, exponent = v1.float_significand_and_lsb_exponent(
            bits & 0x7FFF_FFFF
        )
        negative = (value < 0.0) != (weight < 0)
        weighted.append((-significand if negative else significand, exponent, abs(weight)))
    if not weighted:
        return 0
    common_exponent = min(exponent for _, exponent, _ in weighted)
    exact = sum(
        significand * weight << (exponent - common_exponent)
        for significand, exponent, weight in weighted
    )
    if exact <= 0:
        raise ValueError("non-positive fused endpoint dot product is unresolved")
    truncated = sum(
        v1.partial_product_sum(
            significand,
            weight,
            endpoint_configuration.truncation_bits,
        )
        << (exponent - common_exponent)
        for significand, exponent, weight in weighted
    )
    product_shift = exact.bit_length() - endpoint_configuration.output_bits
    if product_shift < 0:
        raise ValueError("endpoint dot product does not fill requested precision")
    numerator = BinaryTerm(
        (
            truncated
            + endpoint_configuration.bias_units
            * (1 << endpoint_configuration.truncation_bits)
        )
        >> product_shift,
        common_exponent + product_shift,
    )
    return reciprocal_term(
        numerator,
        determinant,
        reciprocal_index,
        reciprocal_configuration,
        swapped=swap_reciprocal_product,
    )


def record_at(
    raw: bytes,
    case_index: int,
    endpoint_index: int,
    sample: object,
) -> tuple[int, ...]:
    record_index = (
        case_index * len(capture.ENDPOINTS) + endpoint_index
    ) * capture.SLOT_COUNT + sample.slot
    return capture.RECORD.unpack_from(raw, record_index * capture.RECORD.size)


def predicted_record(
    sample: object,
    endpoint: object,
    *,
    slope_float: float,
    constant_bits: int,
) -> tuple[int, ...]:
    pull_record = v2.predict_record_with_setup(
        sample,
        slope=slope_float,
        constant=v1.bits_float32(constant_bits),
    )
    slope = v1.float32_bits_fraction(v1.float32_bits(slope_float))
    constant = v1.float32_bits_fraction(constant_bits)
    step = p36.significand_step(constant, p36.endpoint_step(endpoint))
    coordinate = sample.x if sample.axis == 0 else sample.y
    local_pixel = coordinate - sample.tile * capture.TILE_SIZE
    left, right = p36.quad_center_pair(
        local_pixel,
        slope,
        constant,
        step,
        base_rounding="floor",
    )
    center = right if local_pixel & 1 else left
    derivative = p36.derivative_bits(left, right)
    return (*pull_record[: capture.PULL_COUNT], center, derivative)


def constant_candidates(
    capture_case: object,
    endpoint: object,
    sample: object,
    selector_table: tuple[int, ...],
) -> dict[str, int]:
    axis = sample.axis
    extent = capture_case.width if axis == 0 else capture_case.height
    opposite = capture_case.height if axis == 0 else capture_case.width
    origin = capture_case.originX if axis == 0 else capture_case.originY
    displacement = sample.tile * capture.TILE_SIZE - origin
    determinant = extent * opposite
    reciprocal_index = v1.reciprocal_selector(determinant, selector_table)
    result = {
        "physical-anchor": v8.physical_constant_bits(
            capture_case,
            endpoint,
            sample,
            selector_table=selector_table,
        ),
        "translated-exact": v4.translated_constant_bits(
            capture_case,
            endpoint,
            sample,
        ),
    }
    for endpoint_configuration in ENDPOINT_PRODUCT_CONFIGURATIONS:
        for reciprocal_configuration in RECIPROCAL_PRODUCT_CONFIGURATIONS:
            for factorization in ENDPOINT_FACTORIZATIONS:
                for swapped in (False, True):
                    name = (
                        f"weighted:{endpoint_configuration.name}:"
                        f"{reciprocal_configuration.name}:"
                        f"{factorization}:{'swap' if swapped else 'ordered'}"
                    )
                    try:
                        result[name] = endpoint_weighted_constant(
                            endpoint.lowBits,
                            endpoint.highBits,
                            extent=extent,
                            opposite_edge=opposite,
                            displacement=displacement,
                            determinant=determinant,
                            reciprocal_index=reciprocal_index,
                            endpoint_configuration=endpoint_configuration,
                            reciprocal_configuration=reciprocal_configuration,
                            endpoint_factorization=factorization,
                            swap_reciprocal_product=swapped,
                        )
                    except ValueError:
                        pass
            for pipeline in ENDPOINT_PIPELINES:
                for swapped in (False, True):
                    name = (
                        f"pipeline:{endpoint_configuration.name}:"
                        f"{reciprocal_configuration.name}:"
                        f"{pipeline}:{'swap' if swapped else 'ordered'}"
                    )
                    try:
                        result[name] = endpoint_pipeline_constant(
                            endpoint.lowBits,
                            endpoint.highBits,
                            extent=extent,
                            opposite_edge=opposite,
                            displacement=displacement,
                            determinant=determinant,
                            reciprocal_index=reciprocal_index,
                            endpoint_configuration=endpoint_configuration,
                            reciprocal_configuration=reciprocal_configuration,
                            endpoint_pipeline=pipeline,
                            swap_reciprocal_product=swapped,
                        )
                    except ValueError:
                        pass
            for swapped in (False, True):
                name = (
                    f"dot:{endpoint_configuration.name}:"
                    f"{reciprocal_configuration.name}:"
                    f"{'swap' if swapped else 'ordered'}"
                )
                try:
                    result[name] = endpoint_dot_product_constant(
                        endpoint.lowBits,
                        endpoint.highBits,
                        extent=extent,
                        opposite_edge=opposite,
                        displacement=displacement,
                        determinant=determinant,
                        reciprocal_index=reciprocal_index,
                        endpoint_configuration=endpoint_configuration,
                        reciprocal_configuration=reciprocal_configuration,
                        swap_reciprocal_product=swapped,
                    )
                except ValueError:
                    pass
    return result


def analyze(root: Path) -> JsonObject:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    raw = (root / manifest["rasterTileNumerator"]["file"]).read_bytes()
    selector_table = v1.load_selector_table()
    scores: dict[str, Counter[str]] = defaultdict(Counter)
    setup_count = 0
    record_count = 0
    union_exact_setups = 0
    union_exact_records = 0
    union_examples: list[JsonObject] = []

    for case_index, capture_case in enumerate(capture.CASES):
        samples = capture.sample_positions(capture_case)
        for endpoint_index, endpoint in enumerate(capture.ENDPOINTS):
            if endpoint.name not in TARGET_ENDPOINTS:
                continue
            groups: dict[tuple[int, int, int], list[object]] = defaultdict(list)
            for sample in samples:
                groups[(sample.axis, sample.primitive, sample.tile)].append(sample)
            for (axis, primitive, tile), group_samples in groups.items():
                actual = tuple(
                    record_at(raw, case_index, endpoint_index, sample)
                    for sample in group_samples
                )
                if not actual or all(record == capture.SENTINEL for record in actual):
                    continue
                setup_count += 1
                record_count += len(actual)
                slope_float = v8.determinant_slope(
                    capture_case,
                    endpoint,
                    axis=axis,
                    selector_table=selector_table,
                )
                candidates = constant_candidates(
                    capture_case,
                    endpoint,
                    group_samples[0],
                    selector_table,
                )
                setup_exact_names: list[str] = []
                exact_record_union = [False] * len(actual)
                for name, constant_bits in candidates.items():
                    score = scores[name]
                    score["availableSetups"] += 1
                    score["availableRecords"] += len(actual)
                    setup_words = 0
                    setup_bad_records = 0
                    for index, (sample, expected) in enumerate(
                        zip(group_samples, actual, strict=True)
                    ):
                        predicted = predicted_record(
                            sample,
                            endpoint,
                            slope_float=slope_float,
                            constant_bits=constant_bits,
                        )
                        bad_words = sum(
                            left != right
                            for left, right in zip(predicted, expected, strict=True)
                        )
                        setup_words += bad_words
                        setup_bad_records += bool(bad_words)
                        if not bad_words:
                            exact_record_union[index] = True
                    score["mismatchedWords"] += setup_words
                    score["mismatchedRecords"] += setup_bad_records
                    score["exactRecords"] += len(actual) - setup_bad_records
                    if setup_words == 0:
                        score["exactSetups"] += 1
                        setup_exact_names.append(name)
                if setup_exact_names:
                    union_exact_setups += 1
                if all(exact_record_union):
                    union_exact_records += len(actual)
                elif len(union_examples) < 64:
                    union_examples.append(
                        {
                            "case": capture_case.name,
                            "endpoint": endpoint.name,
                            "axis": axis,
                            "primitive": primitive,
                            "tile": tile,
                            "recordCount": len(actual),
                            "exactCandidateCount": len(setup_exact_names),
                        }
                    )

    candidates = [
        {
            "name": name,
            **dict(score),
        }
        for name, score in sorted(
            scores.items(),
            key=lambda item: (
                item[1]["mismatchedWords"],
                -item[1]["exactSetups"],
                item[0],
            ),
        )
    ]
    return {
        "schema4EndpointConstantPipelineSchemaVersion": 1,
        "source": str(root),
        "targetEndpoints": sorted(TARGET_ENDPOINTS),
        "setupCount": setup_count,
        "recordCount": record_count,
        "candidateCount": len(candidates),
        "candidateExactSetupUnionCount": union_exact_setups,
        "candidateExactRecordUnionCount": union_exact_records,
        "candidates": candidates,
        "unionFailureExamples": union_examples,
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
