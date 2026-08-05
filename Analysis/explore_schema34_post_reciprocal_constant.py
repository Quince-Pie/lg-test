#!/usr/bin/env python3
"""Test post-reciprocal tile-constant arithmetic on schemas 3 and 4."""

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import raster_tile_selector_model as v1
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v8 as v8
import validate_raster_tile_numerator as schema3
import validate_raster_tile_phase_holdout as schema4


@dataclass(frozen=True, slots=True)
class Setup:
    anchor: Fraction
    displacement: int
    numerator_index: int
    numerator_exponent: int
    reciprocal_index: int
    reciprocal_exponent: int
    gradient_index: int
    gradient_exponent: int
    physical_bits: int
    allowed_bits: frozenset[int]
    label: str


def quantize_signed(value: Fraction, precision: int, rounding: str) -> Fraction:
    if value == 0:
        return value
    magnitude = v1.quantize_binary_significand(
        abs(value),
        precision,
        rounding=rounding,
    )
    return -magnitude if value < 0 else magnitude


def product_term_exact(
    setup: Setup,
    *,
    precision: int,
    rounding: str,
) -> Fraction:
    exact = (
        Fraction(setup.gradient_index * setup.displacement)
        * v1.power_of_two(setup.gradient_exponent)
    )
    return quantize_signed(exact, precision, rounding)


def normalized_dyadic(value: Fraction, precision: int) -> tuple[int, int]:
    exponent = v1.floor_binary_exponent(value) - precision + 1
    index = value / v1.power_of_two(exponent)
    if index.denominator != 1:
        raise ValueError("quantized dyadic did not normalize to an integer")
    return index.numerator, exponent


def product_term_pre_reciprocal(
    setup: Setup,
    *,
    precision: int,
    rounding: str,
    reciprocal_bias: int = 20,
) -> Fraction:
    if setup.displacement == 0:
        return Fraction(0)
    exact = (
        Fraction(setup.numerator_index * abs(setup.displacement))
        * v1.power_of_two(setup.numerator_exponent)
    )
    quantized = quantize_signed(exact, precision, rounding)
    index, exponent = normalized_dyadic(quantized, precision)
    result_index, result_exponent = v1.product_stage(
        index,
        exponent,
        setup.reciprocal_index,
        setup.reciprocal_exponent,
        output_bits=27,
        truncation_bits=19,
        bias_units=reciprocal_bias,
    )
    term = Fraction(result_index) * v1.power_of_two(result_exponent)
    return -term if setup.displacement < 0 else term


def product_term_pre_reciprocal_staged(
    setup: Setup,
    *,
    truncation: int,
    bias: int,
    normalized_distance: bool,
) -> Fraction:
    if setup.displacement == 0:
        return Fraction(0)
    distance = abs(setup.displacement)
    if normalized_distance:
        distance_index, distance_exponent = (
            v1.float_significand_and_lsb_exponent(
                v1.float32_bits(float(distance))
            )
        )
    else:
        distance_index, distance_exponent = distance, 0
    middle_index, middle_exponent = v1.product_stage(
        setup.numerator_index,
        setup.numerator_exponent,
        distance_index,
        distance_exponent,
        output_bits=27,
        truncation_bits=truncation,
        bias_units=bias,
    )
    result_index, result_exponent = v1.product_stage(
        middle_index,
        middle_exponent,
        setup.reciprocal_index,
        setup.reciprocal_exponent,
        output_bits=27,
        truncation_bits=19,
        bias_units=20,
    )
    term = Fraction(result_index) * v1.power_of_two(result_exponent)
    return -term if setup.displacement < 0 else term


def product_term_pre_reciprocal_fractional_bias(
    setup: Setup,
    *,
    bias_numerator: int,
    bias_denominator_bits: int,
) -> Fraction:
    if setup.displacement == 0:
        return Fraction(0)
    distance = abs(setup.displacement)
    distance_index, distance_exponent = (
        v1.float_significand_and_lsb_exponent(v1.float32_bits(float(distance)))
    )
    product = setup.numerator_index * distance_index
    product_shift = product.bit_length() - 27
    truncation = 19
    if bias_denominator_bits > truncation:
        raise ValueError("fractional bias denominator exceeds truncation lattice")
    middle_index = (
        v1.partial_product_sum(
            setup.numerator_index,
            distance_index,
            truncation,
        )
        + (bias_numerator << (truncation - bias_denominator_bits))
    ) >> product_shift
    middle_exponent = (
        setup.numerator_exponent + distance_exponent + product_shift
    )
    result_index, result_exponent = v1.product_stage(
        middle_index,
        middle_exponent,
        setup.reciprocal_index,
        setup.reciprocal_exponent,
        output_bits=27,
        truncation_bits=19,
        bias_units=20,
    )
    term = Fraction(result_index) * v1.power_of_two(result_exponent)
    return -term if setup.displacement < 0 else term


def product_term_pre_reciprocal_aggregate(
    setup: Setup,
    *,
    bias: int,
) -> Fraction:
    if setup.displacement == 0:
        return Fraction(0)
    distance = abs(setup.displacement)
    distance_index, distance_exponent = (
        v1.float_significand_and_lsb_exponent(v1.float32_bits(float(distance)))
    )
    product = setup.numerator_index * distance_index
    product_shift = product.bit_length() - 27
    truncation = 19
    middle_index = (
        ((product >> truncation) << truncation) + (bias << truncation)
    ) >> product_shift
    middle_exponent = (
        setup.numerator_exponent + distance_exponent + product_shift
    )
    result_index, result_exponent = v1.product_stage(
        middle_index,
        middle_exponent,
        setup.reciprocal_index,
        setup.reciprocal_exponent,
        output_bits=27,
        truncation_bits=19,
        bias_units=20,
    )
    term = Fraction(result_index) * v1.power_of_two(result_exponent)
    return -term if setup.displacement < 0 else term


def product_term_staged(
    setup: Setup,
    *,
    precision: int,
    truncation: int,
    bias: int,
    normalized_distance: bool,
) -> Fraction:
    distance = abs(setup.displacement)
    if distance == 0:
        return Fraction(0)
    if normalized_distance:
        distance_bits = v1.float32_bits(float(distance))
        distance_index, distance_exponent = (
            v1.float_significand_and_lsb_exponent(distance_bits)
        )
    else:
        distance_index, distance_exponent = distance, 0
    index, exponent = v1.product_stage(
        setup.gradient_index,
        setup.gradient_exponent,
        distance_index,
        distance_exponent,
        output_bits=precision,
        truncation_bits=truncation,
        bias_units=bias,
    )
    term = Fraction(index) * v1.power_of_two(exponent)
    return -term if setup.displacement < 0 else term


def constant_bits(setup: Setup, term: Fraction) -> int:
    return v4.quantize_composite_constant_bits(setup.anchor + term)


def load_setups(report_path: Path, first_bias: int) -> list[Setup]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    source = Path(report["source"]).resolve()
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    capture = {3: schema3, 4: schema4}[manifest["schemaVersion"]]
    cases = {capture_case.name: capture_case for capture_case in capture.CASES}
    endpoints = {endpoint.name: endpoint for endpoint in capture.ENDPOINTS}
    selector_table = v1.load_selector_table()
    result: list[Setup] = []

    for group in report["groups"]:
        capture_case = cases[group["case"]]
        endpoint = endpoints[group["endpoint"]]
        axis = group["axis"]
        accepted = group["acceptedSlopeOffsets"]
        slope_offset = 0 if "0" in accepted else min(
            (int(value) for value in accepted),
            key=abs,
        )
        constants = accepted[str(slope_offset)]
        extent = capture_case.width if axis == 0 else capture_case.height
        opposite = capture_case.height if axis == 0 else capture_case.width
        origin = capture_case.originX if axis == 0 else capture_case.originY
        determinant = capture_case.width * capture_case.height
        delta = v1.bits_float32(endpoint.highBits) - v1.bits_float32(
            endpoint.lowBits
        )
        delta_bits = v1.float32_bits(v1.float32(abs(delta)))
        delta_index, delta_exponent = v1.float_significand_and_lsb_exponent(
            delta_bits
        )
        opposite_bits = v1.float32_bits(float(opposite))
        opposite_index, opposite_exponent = (
            v1.float_significand_and_lsb_exponent(opposite_bits)
        )
        numerator_index, numerator_exponent = v1.product_stage(
            delta_index,
            delta_exponent,
            opposite_index,
            opposite_exponent,
            output_bits=27,
            truncation_bits=16,
            bias_units=first_bias,
        )
        reciprocal_index = v1.reciprocal_selector(determinant, selector_table)
        reciprocal_exponent = -(determinant - 1).bit_length() - 24
        gradient_index, gradient_exponent = v1.product_stage(
            numerator_index,
            numerator_exponent,
            reciprocal_index,
            reciprocal_exponent,
            output_bits=27,
            truncation_bits=19,
            bias_units=20,
        )
        if delta < 0:
            raise ValueError("negative endpoint deltas are not in the target corpus")

        samples = capture.sample_positions(capture_case)
        sample_by_tile = {
            (sample.axis, sample.primitive, sample.tile): sample
            for sample in samples
        }
        for key, offsets in constants.items():
            primitive_text, tile_text = key.split(":")
            primitive = int(primitive_text[1:])
            tile = int(tile_text[1:])
            sample = sample_by_tile[(axis, primitive, tile)]
            if axis == 0 and primitive == 0:
                anchor_bits = endpoint.highBits
                anchor_position = origin + extent
            else:
                anchor_bits = endpoint.lowBits
                anchor_position = origin
            physical_bits = v8.physical_constant_bits(
                capture_case,
                endpoint,
                sample,
                selector_table=selector_table,
            )
            result.append(
                Setup(
                    anchor=v1.float32_bits_fraction(anchor_bits),
                    displacement=tile * capture.TILE_SIZE - anchor_position,
                    numerator_index=numerator_index,
                    numerator_exponent=numerator_exponent,
                    reciprocal_index=reciprocal_index,
                    reciprocal_exponent=reciprocal_exponent,
                    gradient_index=gradient_index,
                    gradient_exponent=gradient_exponent,
                    physical_bits=physical_bits,
                    allowed_bits=frozenset(physical_bits + offset for offset in offsets),
                    label=(
                        f"s{manifest['schemaVersion']}:{capture_case.name}:"
                        f"{endpoint.name}:a{axis}:p{primitive}:t{tile}"
                    ),
                )
            )
    return result


def score_exact(setups: list[Setup]) -> list[dict[str, object]]:
    scores: list[dict[str, object]] = []
    for precision in range(24, 41):
        for rounding in ("down", "nearest-even", "up"):
            mismatches = [
                setup.label
                for setup in setups
                if constant_bits(
                    setup,
                    product_term_exact(
                        setup,
                        precision=precision,
                        rounding=rounding,
                    ),
                )
                not in setup.allowed_bits
            ]
            scores.append(
                {
                    "name": f"exact-p{precision}-{rounding}",
                    "exact": len(setups) - len(mismatches),
                    "mismatched": len(mismatches),
                    "examples": mismatches[:8],
                }
            )
    return scores


def score_staged_known(setups: list[Setup]) -> list[dict[str, object]]:
    configurations = {
        (27, 16, bias) for bias in range(0, 33)
    } | {
        (27, 19, bias) for bias in range(0, 65)
    }
    scores: list[dict[str, object]] = []
    for normalized_distance in (False, True):
        for precision, truncation, bias in sorted(configurations):
            mismatches: list[str] = []
            try:
                for setup in setups:
                    predicted = constant_bits(
                        setup,
                        product_term_staged(
                            setup,
                            precision=precision,
                            truncation=truncation,
                            bias=bias,
                            normalized_distance=normalized_distance,
                        ),
                    )
                    if predicted not in setup.allowed_bits:
                        mismatches.append(setup.label)
            except ValueError:
                continue
            scores.append(
                {
                    "name": (
                        f"{'normalized' if normalized_distance else 'integer'}-"
                        f"p{precision}-t{truncation}-b{bias}"
                    ),
                    "exact": len(setups) - len(mismatches),
                    "mismatched": len(mismatches),
                    "examples": mismatches[:8],
                }
            )
    return scores


def score_pre_reciprocal(setups: list[Setup]) -> list[dict[str, object]]:
    scores: list[dict[str, object]] = []
    for precision in range(24, 33):
        for rounding in ("down", "nearest-even", "up"):
            mismatches = [
                setup.label
                for setup in setups
                if constant_bits(
                    setup,
                    product_term_pre_reciprocal(
                        setup,
                        precision=precision,
                        rounding=rounding,
                    ),
                )
                not in setup.allowed_bits
            ]
            scores.append(
                {
                    "name": f"pre-reciprocal-p{precision}-{rounding}",
                    "exact": len(setups) - len(mismatches),
                    "mismatched": len(mismatches),
                    "examples": mismatches[:8],
                }
            )
    return scores


def analyze(report_paths: list[Path]) -> dict[str, object]:
    all_scores: list[dict[str, object]] = []
    setup_counts: dict[str, int] = {}
    for first_bias in (14, 15):
        setups = [
            setup
            for report_path in report_paths
            for setup in load_setups(report_path, first_bias)
        ]
        setup_counts[str(first_bias)] = len(setups)
        scores = (
            score_exact(setups)
            + score_pre_reciprocal(setups)
        )
        for score in scores:
            score["firstBias"] = first_bias
        all_scores.extend(scores)
    all_scores.sort(key=lambda score: (score["mismatched"], score["name"]))
    histogram = Counter(score["mismatched"] for score in all_scores)
    return {
        "schema34PostReciprocalConstantSchemaVersion": 1,
        "reports": [str(path) for path in report_paths],
        "setupCountsByFirstBias": setup_counts,
        "candidateCount": len(all_scores),
        "mismatchHistogram": dict(sorted(histogram.items())[:32]),
        "best": all_scores[:64],
    }


def analyze_best(report_paths: list[Path]) -> dict[str, object]:
    setups = [
        setup
        for report_path in report_paths
        for setup in load_setups(report_path, 15)
    ]
    failures: list[dict[str, object]] = []
    dimensions: dict[str, Counter[str]] = {
        name: Counter()
        for name in ("schema", "case", "endpoint", "axis", "primitive")
    }
    for setup in setups:
        term = product_term_pre_reciprocal(
            setup,
            precision=27,
            rounding="nearest-even",
        )
        predicted = constant_bits(setup, term)
        if predicted in setup.allowed_bits:
            continue
        schema, case, endpoint, axis, primitive, tile = setup.label.split(":")
        for name, value in (
            ("schema", schema),
            ("case", case),
            ("endpoint", endpoint),
            ("axis", axis),
            ("primitive", primitive),
        ):
            dimensions[name][value] += 1

        product = setup.numerator_index * abs(setup.displacement)
        shift = product.bit_length() - 27
        floor_index, remainder = divmod(product, 1 << shift)
        nearest_index = floor_index + (
            2 * remainder > 1 << shift
            or (2 * remainder == 1 << shift and bool(floor_index & 1))
        )
        accepted_middle_offsets: list[int] = []
        for offset in range(-16, 17):
            result_index, result_exponent = v1.product_stage(
                nearest_index + offset,
                setup.numerator_exponent + shift,
                setup.reciprocal_index,
                setup.reciprocal_exponent,
                output_bits=27,
                truncation_bits=19,
                bias_units=20,
            )
            candidate_term = (
                Fraction(result_index) * v1.power_of_two(result_exponent)
            )
            if setup.displacement < 0:
                candidate_term = -candidate_term
            if constant_bits(setup, candidate_term) in setup.allowed_bits:
                accepted_middle_offsets.append(offset)
        failures.append(
            {
                "label": setup.label,
                "tile": int(tile[1:]),
                "displacement": setup.displacement,
                "physicalBits": f"0x{setup.physical_bits:08x}",
                "predictedBits": f"0x{predicted:08x}",
                "predictedOffset": predicted - setup.physical_bits,
                "allowedBits": [
                    f"0x{bits:08x}" for bits in sorted(setup.allowed_bits)
                ],
                "allowedOffsets": [
                    bits - setup.physical_bits for bits in sorted(setup.allowed_bits)
                ],
                "middleShift": shift,
                "middleFloorIndex": floor_index,
                "middleRemainder": remainder,
                "middleHalf": 0 if shift == 0 else 1 << (shift - 1),
                "middleNearestIndex": nearest_index,
                "acceptedMiddleOffsets": accepted_middle_offsets,
            }
        )
    middle_offsets = Counter(
        offset
        for failure in failures
        for offset in failure["acceptedMiddleOffsets"]
    )
    return {
        "schema34PreReciprocalFailureSchemaVersion": 1,
        "reports": [str(path) for path in report_paths],
        "model": "first-b15, middle-p27-nearest-even, reciprocal-p27-t19-b20",
        "setupCount": len(setups),
        "exactSetupCount": len(setups) - len(failures),
        "failureCount": len(failures),
        "dimensionCounts": {
            name: dict(counter.most_common())
            for name, counter in dimensions.items()
        },
        "acceptedMiddleOffsetCounts": dict(sorted(middle_offsets.items())),
        "failures": failures,
    }


def analyze_middle_stage(report_paths: list[Path]) -> dict[str, object]:
    setups = [
        setup
        for report_path in report_paths
        for setup in load_setups(report_path, 15)
    ]
    scores: list[dict[str, object]] = []
    for normalized_distance in (False, True):
        for truncation, biases in ((16, range(0, 33)), (19, range(0, 65))):
            for bias in biases:
                failures: list[str] = []
                for setup in setups:
                    predicted = constant_bits(
                        setup,
                        product_term_pre_reciprocal_staged(
                            setup,
                            truncation=truncation,
                            bias=bias,
                            normalized_distance=normalized_distance,
                        ),
                    )
                    if predicted not in setup.allowed_bits:
                        failures.append(setup.label)
                scores.append(
                    {
                        "name": (
                            f"{'normalized' if normalized_distance else 'integer'}-"
                            f"p27-t{truncation}-b{bias}"
                        ),
                        "exact": len(setups) - len(failures),
                        "mismatched": len(failures),
                        "examples": failures[:16],
                    }
                )
    scores.sort(key=lambda score: (score["mismatched"], score["name"]))
    return {
        "schema34MiddleStageSearchSchemaVersion": 1,
        "reports": [str(path) for path in report_paths],
        "setupCount": len(setups),
        "candidateCount": len(scores),
        "best": scores[:64],
    }


def analyze_middle_neighborhood(report_paths: list[Path]) -> dict[str, object]:
    setup_maps = {
        first_bias: {
            setup.label: setup
            for report_path in report_paths
            for setup in load_setups(report_path, first_bias)
        }
        for first_bias in (14, 15)
    }
    labels = sorted(setup_maps[15])
    variants = {
        f"first-b{first_bias}:middle-b{middle_bias}": (
            first_bias,
            middle_bias,
        )
        for first_bias in (14, 15)
        for middle_bias in range(8, 13)
    }
    matches: dict[str, set[str]] = {name: set() for name in variants}
    signatures: Counter[str] = Counter()
    unresolved: list[str] = []
    discriminators: list[dict[str, object]] = []
    for label in labels:
        accepted: list[str] = []
        for name, (first_bias, middle_bias) in variants.items():
            setup = setup_maps[first_bias][label]
            predicted = constant_bits(
                setup,
                product_term_pre_reciprocal_staged(
                    setup,
                    truncation=19,
                    bias=middle_bias,
                    normalized_distance=True,
                ),
            )
            if predicted in setup.allowed_bits:
                accepted.append(name)
                matches[name].add(label)
        signatures[",".join(accepted) or "none"] += 1
        if not accepted:
            unresolved.append(label)
        accepts_10 = "first-b15:middle-b10" in accepted
        accepts_11 = "first-b15:middle-b11" in accepted
        if accepts_10 == accepts_11:
            continue
        setup = setup_maps[15][label]
        distance = abs(setup.displacement)
        distance_index, _ = v1.float_significand_and_lsb_exponent(
            v1.float32_bits(float(distance))
        )
        exact_product = setup.numerator_index * distance_index
        partial = v1.partial_product_sum(
            setup.numerator_index,
            distance_index,
            19,
        )
        loss = exact_product - partial
        product_shift = exact_product.bit_length() - 27
        predictions: dict[str, int] = {}
        for middle_bias in (10, 11):
            predictions[str(middle_bias)] = constant_bits(
                setup,
                product_term_pre_reciprocal_staged(
                    setup,
                    truncation=19,
                    bias=middle_bias,
                    normalized_distance=True,
                ),
            )
        discriminators.append(
            {
                "label": label,
                "requiredBias": 10 if accepts_10 else 11,
                "displacement": setup.displacement,
                "numeratorIndex": setup.numerator_index,
                "numeratorHex": f"0x{setup.numerator_index:07x}",
                "numeratorPopcount": setup.numerator_index.bit_count(),
                "numeratorLow19": setup.numerator_index & ((1 << 19) - 1),
                "distanceIndex": distance_index,
                "distanceHex": f"0x{distance_index:06x}",
                "distancePopcount": distance_index.bit_count(),
                "distanceLow19": distance_index & ((1 << 19) - 1),
                "exactProduct": exact_product,
                "partialProduct": partial,
                "truncationLoss": loss,
                "lossUnitsFloor": loss >> 19,
                "lossLow19": loss & ((1 << 19) - 1),
                "productShift": product_shift,
                "partialOutputResidue": partial & ((1 << product_shift) - 1),
                "physicalBits": f"0x{setup.physical_bits:08x}",
                "allowedBits": [
                    f"0x{bits:08x}" for bits in sorted(setup.allowed_bits)
                ],
                "predictedBits": {
                    bias: f"0x{bits:08x}" for bias, bits in predictions.items()
                },
            }
        )
    return {
        "schema34MiddleNeighborhoodSchemaVersion": 1,
        "reports": [str(path) for path in report_paths],
        "setupCount": len(labels),
        "variants": {
            name: {
                "exact": len(matched),
                "mismatched": len(labels) - len(matched),
            }
            for name, matched in variants.items()
            for matched in (matches[name],)
        },
        "unionExact": len(labels) - len(unresolved),
        "unionMismatched": len(unresolved),
        "unresolved": unresolved,
        "acceptanceSignatures": dict(signatures.most_common()),
        "discriminatorCount": len(discriminators),
        "discriminators": discriminators,
    }


def analyze_fractional_middle_bias(report_paths: list[Path]) -> dict[str, object]:
    setups = [
        setup
        for report_path in report_paths
        for setup in load_setups(report_path, 15)
    ]
    denominator_bits = 6
    scores: list[dict[str, object]] = []
    for bias_numerator in range(9 << denominator_bits, (12 << denominator_bits) + 1):
        failures: list[str] = []
        for setup in setups:
            predicted = constant_bits(
                setup,
                product_term_pre_reciprocal_fractional_bias(
                    setup,
                    bias_numerator=bias_numerator,
                    bias_denominator_bits=denominator_bits,
                ),
            )
            if predicted not in setup.allowed_bits:
                failures.append(setup.label)
        scores.append(
            {
                "biasNumerator": bias_numerator,
                "biasDenominator": 1 << denominator_bits,
                "bias": f"{bias_numerator}/{1 << denominator_bits}",
                "exact": len(setups) - len(failures),
                "mismatched": len(failures),
                "examples": failures[:16],
            }
        )
    scores.sort(key=lambda score: (score["mismatched"], score["biasNumerator"]))
    return {
        "schema34FractionalMiddleBiasSchemaVersion": 1,
        "reports": [str(path) for path in report_paths],
        "setupCount": len(setups),
        "candidateCount": len(scores),
        "best": scores[:64],
    }


def analyze_aggregate_middle(report_paths: list[Path]) -> dict[str, object]:
    setups = [
        setup
        for report_path in report_paths
        for setup in load_setups(report_path, 15)
    ]
    scores: list[dict[str, object]] = []
    for bias in range(0, 33):
        failures: list[str] = []
        for setup in setups:
            predicted = constant_bits(
                setup,
                product_term_pre_reciprocal_aggregate(setup, bias=bias),
            )
            if predicted not in setup.allowed_bits:
                failures.append(setup.label)
        scores.append(
            {
                "bias": bias,
                "exact": len(setups) - len(failures),
                "mismatched": len(failures),
                "examples": failures[:32],
            }
        )
    scores.sort(key=lambda score: (score["mismatched"], score["bias"]))
    return {
        "schema34AggregateMiddleSchemaVersion": 1,
        "reports": [str(path) for path in report_paths],
        "setupCount": len(setups),
        "candidateCount": len(scores),
        "best": scores,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", type=Path, nargs="+")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--classify-best", action="store_true")
    parser.add_argument("--search-middle", action="store_true")
    parser.add_argument("--middle-neighborhood", action="store_true")
    parser.add_argument("--fractional-middle-bias", action="store_true")
    parser.add_argument("--aggregate-middle", action="store_true")
    arguments = parser.parse_args()
    if arguments.classify_best:
        report = analyze_best(arguments.reports)
    elif arguments.search_middle:
        report = analyze_middle_stage(arguments.reports)
    elif arguments.middle_neighborhood:
        report = analyze_middle_neighborhood(arguments.reports)
    elif arguments.fractional_middle_bias:
        report = analyze_fractional_middle_bias(arguments.reports)
    elif arguments.aggregate_middle:
        report = analyze_aggregate_middle(arguments.reports)
    else:
        report = analyze(arguments.reports)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(rendered, end="")
    else:
        arguments.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
