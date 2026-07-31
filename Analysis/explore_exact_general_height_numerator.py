#!/usr/bin/env python3
"""Explore odd-height numerator laws where the reciprocal is already known."""

import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import explore_general_height as general
import explore_general_height_numerator_precision as numerator
import validate_raster_low_exponent_power2 as low_exponent


type JsonObject = dict[str, Any]

HEIGHTS = (47, 61, 79, 113)
GEOMETRY_COUNT = len(HEIGHTS)
PRECISIONS = range(24, 37)
ROUNDING_MODES = ("floor", "nearest", "ceil")


def signed_offset(byte: int) -> int:
    return byte if byte < 128 else byte - 256


def exact_normalized_class(area: int) -> tuple[int, int] | None:
    shift = area.bit_length() - 14
    if shift < 0:
        return None
    normalized, remainder = divmod(area, 1 << shift)
    if remainder or not 8_192 <= normalized <= 16_383:
        return None
    return normalized, shift


def recovered_slopes() -> list[int]:
    offsets = low_exponent.load_top_left_slope_offsets()
    widths = low_exponent.factorized.geometry_widths()
    shifts = low_exponent.factorized.delta_exponent_shift_bits()
    witnesses = low_exponent.arithmetic.witness_delta_bits()
    result: list[int] = []
    index = 0
    for width_index, width in enumerate(widths):
        for delta_bits in witnesses:
            scaled_value = low_exponent.arithmetic.float32_value(
                delta_bits - shifts[width_index]
            )
            direct = low_exponent.arithmetic.float32_bits(scaled_value / width)
            for _ in HEIGHTS:
                result.append(direct + signed_offset(offsets[index]))
                index += 1
    if index != len(offsets):
        raise ValueError("top-left slope offset layout differs")
    return result


def physical_index(
    left: int,
    left_lsb_exponent: int,
    right: int,
    right_lsb_exponent: int,
) -> tuple[int, int]:
    exact_product = left * right
    product_shift = exact_product.bit_length() - 27
    truncated_product = sum(
        ((left << bit) >> 16) << 16
        for bit in range(right.bit_length())
        if right & (1 << bit)
    )
    product_index = (truncated_product + 0x14_0000) >> product_shift
    return product_index, left_lsb_exponent + right_lsb_exponent + product_shift


def physical_bits(
    left: int,
    left_lsb_exponent: int,
    right: int,
    right_lsb_exponent: int,
) -> int:
    product_index, product_lsb_exponent = physical_index(
        left,
        left_lsb_exponent,
        right,
        right_lsb_exponent,
    )
    return low_exponent.arithmetic.float32_bits(
        math.ldexp(product_index, product_lsb_exponent)
    )


def expanded_triple_product_bits(
    significand: int,
    significand_lsb_exponent: int,
    edge: int,
    edge_lsb_exponent: int,
    reciprocal: int,
    reciprocal_lsb_exponent: int,
) -> int:
    exact_product = significand * edge * reciprocal
    product_shift = exact_product.bit_length() - 27
    truncated_product = sum(
        ((significand << (edge_bit + reciprocal_bit)) >> 16) << 16
        for edge_bit in range(edge.bit_length())
        if edge & (1 << edge_bit)
        for reciprocal_bit in range(reciprocal.bit_length())
        if reciprocal & (1 << reciprocal_bit)
    )
    product_index = (truncated_product + 0x14_0000) >> product_shift
    return low_exponent.arithmetic.float32_bits(
        math.ldexp(
            product_index,
            significand_lsb_exponent
            + edge_lsb_exponent
            + reciprocal_lsb_exponent
            + product_shift,
        )
    )


def numerator_candidate_interval(
    observations: list[tuple[int, int, int, int]],
    *,
    product_shift: int,
) -> tuple[int, int] | None:
    def first_at_least(
        target: int,
        lsb_exponent: int,
        reciprocal: int,
        reciprocal_exponent: int,
    ) -> int:
        lower = 1
        upper = 1 << 40
        while lower < upper:
            middle = (lower + upper) // 2
            predicted = general.physical_product_with_exponent(
                middle,
                lsb_exponent + product_shift,
                reciprocal,
                reciprocal_exponent,
            )
            if predicted < target:
                lower = middle + 1
            else:
                upper = middle
        return lower

    lower = 1
    upper = (1 << 40) - 1
    for lsb_exponent, reciprocal, reciprocal_exponent, actual in observations:
        lower = max(
            lower,
            first_at_least(
                actual,
                lsb_exponent,
                reciprocal,
                reciprocal_exponent,
            ),
        )
        upper = min(
            upper,
            first_at_least(
                actual + 1,
                lsb_exponent,
                reciprocal,
                reciprocal_exponent,
            )
            - 1,
        )
        if lower > upper:
            return None
    return lower, upper


def analyze() -> JsonObject:
    widths = low_exponent.factorized.geometry_widths()
    shifts = low_exponent.factorized.delta_exponent_shift_bits()
    witness_bits = low_exponent.arithmetic.witness_delta_bits()
    canonical = low_exponent.factorized.canonical_reciprocals()
    slopes = recovered_slopes()
    model_matches: dict[str, int] = Counter()
    model_errors: dict[str, Counter[int]] = defaultdict(Counter)
    exact_pair_count = 0
    coefficient_count = 0
    p28_ceil_mismatches: list[JsonObject] = []
    p28_candidate_offsets: Counter[tuple[int, ...]] = Counter()
    grouped_observations: dict[tuple[int, int], list[tuple[int, int, int, int]]] = (
        defaultdict(list)
    )

    for width_index, width in enumerate(widths):
        for geometry_index, height in enumerate(HEIGHTS):
            area = width * height
            normalized = exact_normalized_class(area)
            if normalized is None:
                continue
            normalized_class, area_shift = normalized
            exact_pair_count += 1
            reciprocal = canonical[normalized_class - 8_192]
            reciprocal_exponent = -(area - 1).bit_length()
            for witness_index, delta_bits in enumerate(witness_bits):
                scaled_bits = delta_bits - shifts[width_index]
                significand, lsb_exponent = general.float_significand_and_lsb_exponent(
                    scaled_bits
                )
                slope_index = (
                    width_index * len(witness_bits) + witness_index
                ) * GEOMETRY_COUNT + geometry_index
                actual = slopes[slope_index]
                coefficient_count += 1
                grouped_observations[height, witness_index].append(
                    (
                        lsb_exponent,
                        reciprocal,
                        reciprocal_exponent,
                        actual,
                    )
                )
                for precision in PRECISIONS:
                    for rounding in ROUNDING_MODES:
                        numerator_significand, numerator_exponent = (
                            numerator.numerator_model(
                                significand,
                                lsb_exponent,
                                height,
                                precision,
                                rounding,
                            )
                        )
                        predicted = general.physical_product_with_exponent(
                            numerator_significand,
                            numerator_exponent,
                            reciprocal,
                            reciprocal_exponent,
                        )
                        name = f"p{precision}_{rounding}"
                        model_matches[name] += predicted == actual
                        model_errors[name][predicted - actual] += 1
                        edge_predicted = numerator.edge_factorized_product_bits(
                            significand,
                            lsb_exponent,
                            height,
                            area,
                            reciprocal,
                            precision=precision,
                            rounding=rounding,
                        )
                        edge_name = f"edge_p{precision}_{rounding}"
                        model_matches[edge_name] += edge_predicted == actual
                        model_errors[edge_name][edge_predicted - actual] += 1
                edge_exact = numerator.edge_factorized_product_bits(
                    significand,
                    lsb_exponent,
                    height,
                    area,
                    reciprocal,
                    precision=None,
                    rounding="exact",
                )
                model_matches["edge_exact"] += edge_exact == actual
                model_errors["edge_exact"][edge_exact - actual] += 1

                height_bits = low_exponent.arithmetic.float32_bits(float(height))
                height_significand, height_lsb_exponent = (
                    general.float_significand_and_lsb_exponent(height_bits)
                )
                reciprocal_lsb_exponent = reciprocal_exponent - 24
                chained_models: dict[str, int] = {}
                for edge_shift in range(17):
                    fixed_edge = height << edge_shift
                    fixed_edge_lsb_exponent = -edge_shift
                    chained_models[f"numeratorConsolidated_edgeShift{edge_shift}"] = (
                        physical_bits(
                            significand * fixed_edge,
                            lsb_exponent + fixed_edge_lsb_exponent,
                            reciprocal,
                            reciprocal_lsb_exponent,
                        )
                    )
                    chained_models[f"edgeConsolidated_edgeShift{edge_shift}"] = (
                        physical_bits(
                            significand,
                            lsb_exponent,
                            fixed_edge * reciprocal,
                            fixed_edge_lsb_exponent + reciprocal_lsb_exponent,
                        )
                    )
                    chained_models[f"tripleExpanded_edgeShift{edge_shift}"] = (
                        expanded_triple_product_bits(
                            significand,
                            lsb_exponent,
                            fixed_edge,
                            fixed_edge_lsb_exponent,
                            reciprocal,
                            reciprocal_lsb_exponent,
                        )
                    )
                for (
                    first_name,
                    first_left,
                    first_left_exponent,
                    first_right,
                    first_right_exponent,
                ) in (
                    (
                        "numeratorDeltaHeight",
                        significand,
                        lsb_exponent,
                        height_significand,
                        height_lsb_exponent,
                    ),
                    (
                        "numeratorHeightDelta",
                        height_significand,
                        height_lsb_exponent,
                        significand,
                        lsb_exponent,
                    ),
                ):
                    intermediate, intermediate_exponent = physical_index(
                        first_left,
                        first_left_exponent,
                        first_right,
                        first_right_exponent,
                    )
                    chained_models[f"{first_name}_thenReciprocal"] = physical_bits(
                        intermediate,
                        intermediate_exponent,
                        reciprocal,
                        reciprocal_lsb_exponent,
                    )
                    chained_models[f"reciprocalThen_{first_name}"] = physical_bits(
                        reciprocal,
                        reciprocal_lsb_exponent,
                        intermediate,
                        intermediate_exponent,
                    )
                for (
                    first_name,
                    first_left,
                    first_left_exponent,
                    first_right,
                    first_right_exponent,
                ) in (
                    (
                        "deltaReciprocal",
                        significand,
                        lsb_exponent,
                        reciprocal,
                        reciprocal_lsb_exponent,
                    ),
                    (
                        "reciprocalDelta",
                        reciprocal,
                        reciprocal_lsb_exponent,
                        significand,
                        lsb_exponent,
                    ),
                ):
                    intermediate, intermediate_exponent = physical_index(
                        first_left,
                        first_left_exponent,
                        first_right,
                        first_right_exponent,
                    )
                    chained_models[f"{first_name}_thenHeight"] = physical_bits(
                        intermediate,
                        intermediate_exponent,
                        height_significand,
                        height_lsb_exponent,
                    )
                    chained_models[f"heightThen_{first_name}"] = physical_bits(
                        height_significand,
                        height_lsb_exponent,
                        intermediate,
                        intermediate_exponent,
                    )
                for (
                    first_name,
                    first_left,
                    first_left_exponent,
                    first_right,
                    first_right_exponent,
                ) in (
                    (
                        "edgeHeightReciprocal",
                        height_significand,
                        height_lsb_exponent,
                        reciprocal,
                        reciprocal_lsb_exponent,
                    ),
                    (
                        "edgeReciprocalHeight",
                        reciprocal,
                        reciprocal_lsb_exponent,
                        height_significand,
                        height_lsb_exponent,
                    ),
                ):
                    intermediate, intermediate_exponent = physical_index(
                        first_left,
                        first_left_exponent,
                        first_right,
                        first_right_exponent,
                    )
                    chained_models[f"deltaThen_{first_name}"] = physical_bits(
                        significand,
                        lsb_exponent,
                        intermediate,
                        intermediate_exponent,
                    )
                    chained_models[f"{first_name}_thenDelta"] = physical_bits(
                        intermediate,
                        intermediate_exponent,
                        significand,
                        lsb_exponent,
                    )
                for name, predicted in chained_models.items():
                    model_matches[name] += predicted == actual
                    model_errors[name][predicted - actual] += 1

                product = significand * height
                product_shift = max(0, product.bit_length() - 28)
                floor_numerator, remainder = divmod(product, 1 << product_shift)
                accepted_offsets = tuple(
                    offset
                    for offset in range(-8, 10)
                    if general.physical_product_with_exponent(
                        floor_numerator + offset,
                        lsb_exponent + product_shift,
                        reciprocal,
                        reciprocal_exponent,
                    )
                    == actual
                )
                p28_candidate_offsets[accepted_offsets] += 1
                ceil_numerator = floor_numerator + bool(remainder)
                ceil_prediction = general.physical_product_with_exponent(
                    ceil_numerator,
                    lsb_exponent + product_shift,
                    reciprocal,
                    reciprocal_exponent,
                )
                if ceil_prediction != actual and len(p28_ceil_mismatches) < 512:
                    p28_ceil_mismatches.append(
                        {
                            "width": width,
                            "height": height,
                            "area": area,
                            "areaShift": area_shift,
                            "normalizedClass": normalized_class,
                            "witnessIndex": witness_index,
                            "significand": significand,
                            "productBitLength": product.bit_length(),
                            "productShift": product_shift,
                            "remainder": remainder,
                            "floorNumeratorLow16": floor_numerator & 0xFFFF,
                            "acceptedNumeratorOffsetsFromFloor": list(accepted_offsets),
                            "predictedMinusActualFloatUlps": ceil_prediction - actual,
                        }
                    )

    grouped_numerator_candidates: dict[str, JsonObject] = {}
    for precision in PRECISIONS:
        multiplicity: Counter[int] = Counter()
        recovered_offsets: Counter[int] = Counter()
        groups: list[JsonObject] = []
        for (height, witness_index), observations in sorted(
            grouped_observations.items()
        ):
            significand = low_exponent.arithmetic.WITNESS_SIGNIFICANDS[witness_index]
            product = significand * height
            product_shift = max(0, product.bit_length() - precision)
            floor_numerator = product >> product_shift
            interval = numerator_candidate_interval(
                observations,
                product_shift=product_shift,
            )
            offsets = (
                []
                if interval is None
                else [
                    interval[0] - floor_numerator,
                    interval[1] - floor_numerator,
                ]
            )
            interval_size = 0 if interval is None else interval[1] - interval[0] + 1
            multiplicity[interval_size] += 1
            if interval_size <= 1_024:
                recovered_offsets.update(
                    range(offsets[0], offsets[1] + 1) if offsets else ()
                )
            groups.append(
                {
                    "height": height,
                    "witnessIndex": witness_index,
                    "observationCount": len(observations),
                    "productShift": product_shift,
                    "candidateIntervalOffsetsFromFloor": offsets,
                    "candidateIntervalSize": interval_size,
                }
            )
        grouped_numerator_candidates[f"p{precision}"] = {
            "multiplicity": {
                str(key): value for key, value in sorted(multiplicity.items())
            },
            "candidateOffsetDistribution": {
                str(key): value for key, value in sorted(recovered_offsets.items())
            },
            "groups": groups,
        }

    return {
        "exactNormalizedPairCount": exact_pair_count,
        "coefficientCount": coefficient_count,
        "modelMatches": dict(
            sorted(model_matches.items(), key=lambda item: (-item[1], item[0]))
        ),
        "modelErrors": {
            name: {str(key): value for key, value in sorted(errors.items())}
            for name, errors in model_errors.items()
        },
        "p28CandidateOffsetsFromFloor": {
            json.dumps(key): value
            for key, value in sorted(
                p28_candidate_offsets.items(),
                key=lambda item: (-item[1], item[0]),
            )
        },
        "p28CeilMismatchCount": len(p28_ceil_mismatches),
        "p28CeilMismatches": p28_ceil_mismatches,
        "groupedNumeratorCandidates": grouped_numerator_candidates,
    }


def main() -> None:
    output = Path("Analysis/exact_general_height_numerator_analysis.json")
    output.write_text(
        json.dumps(analyze(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
