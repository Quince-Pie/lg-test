#!/usr/bin/env python3
"""Explore coefficient constraints in the general-height transfer corpus."""

import argparse
import json
import math
import struct
from collections import Counter
from pathlib import Path

import validate_reciprocal_general_height_transfer as general


def nearby_bits(center: int, radius: int) -> list[int]:
    values = [center]
    lower = center
    upper = center
    for _ in range(radius):
        lower = general.arithmetic.next_float32_bits(lower, upward=False)
        upper = general.arithmetic.next_float32_bits(upper, upward=True)
        values.extend((lower, upper))
    return sorted(values)


def signed_ulp_delta(bits: int, center: int) -> int:
    return bits - center


def normalized_class(value: int, *, rounding: str) -> int:
    shift = value.bit_length() - 14
    if shift <= 0:
        scaled = value << -shift
        remainder = 0
        denominator = 1
    else:
        scaled, remainder = divmod(value, 1 << shift)
        denominator = 1 << shift
    if rounding == "nearest":
        doubled = 2 * remainder
        scaled += doubled > denominator or (doubled == denominator and scaled & 1)
    elif rounding == "ceil":
        scaled += remainder != 0
    elif rounding != "floor":
        raise ValueError(f"unknown class rounding: {rounding}")
    return min(16_383, max(8_192, scaled))


def float_significand_and_lsb_exponent(bits: int) -> tuple[int, int]:
    exponent = (bits >> 23) & 0xFF
    fraction = bits & 0x7F_FFFF
    if bits >> 31 or not 0 < exponent < 0xFF:
        raise ValueError("positive normal binary32 required")
    return (1 << 23) | fraction, exponent - 127 - 23


def generalized_physical_product_bits(
    multiplicand: int,
    multiplicand_lsb_exponent: int,
    denominator: int,
    reciprocal: int,
) -> int:
    reciprocal_exponent = -(denominator - 1).bit_length()
    return physical_product_with_exponent(
        multiplicand,
        multiplicand_lsb_exponent,
        reciprocal,
        reciprocal_exponent,
    )


def physical_product_with_exponent(
    multiplicand: int,
    multiplicand_lsb_exponent: int,
    reciprocal: int,
    reciprocal_exponent: int,
) -> int:
    exact_product = multiplicand * reciprocal
    product_shift = exact_product.bit_length() - 27
    truncated_product = sum(
        ((multiplicand << bit) >> 16) << 16
        for bit in range(reciprocal.bit_length())
        if reciprocal & (1 << bit)
    )
    product_index = (truncated_product + 0x14_0000) >> product_shift
    return general.arithmetic.float32_bits(
        math.ldexp(
            product_index,
            multiplicand_lsb_exponent + reciprocal_exponent - 24 + product_shift,
        )
    )


def nearest_reciprocal_for_float(bits: int) -> tuple[int, int, int]:
    significand, lsb_exponent = float_significand_and_lsb_exponent(bits)
    floor_exponent = ((bits >> 23) & 0xFF) - 127
    is_power_of_two = significand == 1 << 23
    reciprocal_exponent = -floor_exponent - (not is_power_of_two)
    numerator_power = 24 - reciprocal_exponent - lsb_exponent
    if numerator_power < 0:
        raise ValueError("reciprocal numerator power is negative")
    reciprocal = general.arithmetic.round_integer_nearest_even(
        1 << numerator_power,
        significand,
    )
    normalized_class = significand >> 10
    return reciprocal, reciprocal_exponent, normalized_class


def transformed_opposite_edges(origin_y: int, height: int) -> dict[str, float]:
    target_height = 192
    scale = general.arithmetic.float32_value(
        general.arithmetic.float32_bits(-2.0 / target_height)
    )

    def f32(value: float) -> float:
        return general.arithmetic.float32_value(general.arithmetic.float32_bits(value))

    top_fma = f32(math.fma(float(origin_y), scale, 1.0))
    bottom_fma = f32(math.fma(float(origin_y + height), scale, 1.0))
    top_separate = f32(f32(float(origin_y) * scale) + 1.0)
    bottom_separate = f32(f32(float(origin_y + height) * scale) + 1.0)
    return {
        "clipFmaDifference": f32(abs(f32(bottom_fma - top_fma)) * 128.0),
        "clipSeparateDifference": f32(abs(f32(bottom_separate - top_separate)) * 128.0),
        "clipDirectHeightProduct": f32(abs(f32(float(height) * scale)) * 128.0),
    }


def rounded_shift(value: int, shift: int, mode: str) -> int:
    if shift <= 0:
        return value << -shift
    quotient, remainder = divmod(value, 1 << shift)
    if mode == "nearest":
        half = 1 << (shift - 1)
        quotient += remainder > half or (remainder == half and quotient & 1)
    elif mode == "ceil":
        quotient += remainder != 0
    elif mode != "floor":
        raise ValueError(f"unknown shift rounding: {mode}")
    return quotient


def model_predictions(
    *,
    width: int,
    height: int,
    original_delta_bits: int,
    delta_exponent_shift: int,
    canonical: list[int],
    origin_y: int | None = None,
) -> dict[str, int]:
    scaled_bits = original_delta_bits - delta_exponent_shift
    scaled_value = general.arithmetic.float32_value(scaled_bits)
    direct = general.arithmetic.float32_bits(scaled_value / width)
    delta_significand, delta_lsb = float_significand_and_lsb_exponent(scaled_bits)
    numerator_bits = general.arithmetic.float32_bits(scaled_value * height)
    numerator_significand, numerator_lsb = float_significand_and_lsb_exponent(
        numerator_bits
    )
    exact_multiplicand = delta_significand * height
    area = width * height
    nearest_area = general.arithmetic.nearest_even_reciprocal_index(area)
    result = {"directDivide": direct}
    for class_rounding in ("floor", "nearest", "ceil"):
        index = normalized_class(area, rounding=class_rounding)
        offset = canonical[
            index - general.factorized.NORMALIZED_DENOMINATOR_LOWER
        ] - general.arithmetic.nearest_even_reciprocal_index(index)
        reciprocal = nearest_area + offset
        result[f"areaF32Numerator_{class_rounding}ClassOffset"] = (
            generalized_physical_product_bits(
                numerator_significand,
                numerator_lsb,
                area,
                reciprocal,
            )
        )
        result[f"areaExactNumerator_{class_rounding}ClassOffset"] = (
            generalized_physical_product_bits(
                exact_multiplicand,
                delta_lsb,
                area,
                reciprocal,
            )
        )
    result["areaF32Numerator_nearestReciprocal"] = generalized_physical_product_bits(
        numerator_significand,
        numerator_lsb,
        area,
        nearest_area,
    )
    result["areaExactNumerator_nearestReciprocal"] = generalized_physical_product_bits(
        exact_multiplicand,
        delta_lsb,
        area,
        nearest_area,
    )
    selector_variants = {
        "nearestArea": nearest_area,
        "floorClassOffset": (
            nearest_area
            + canonical[
                normalized_class(area, rounding="floor")
                - general.factorized.NORMALIZED_DENOMINATOR_LOWER
            ]
            - general.arithmetic.nearest_even_reciprocal_index(
                normalized_class(area, rounding="floor")
            )
        ),
    }
    for selector_name, area_reciprocal in selector_variants.items():
        edge_product = height * area_reciprocal
        result[f"edgeExactMultiplier_{selector_name}"] = (
            generalized_physical_product_bits(
                delta_significand,
                delta_lsb,
                area,
                edge_product,
            )
        )
        edge_shift = edge_product.bit_length() - 25
        for edge_rounding in ("floor", "nearest", "ceil"):
            effective_reciprocal = rounded_shift(
                edge_product,
                edge_shift,
                edge_rounding,
            )
            result[f"edge25_{selector_name}_{edge_rounding}"] = (
                generalized_physical_product_bits(
                    delta_significand,
                    delta_lsb,
                    width,
                    effective_reciprocal,
                )
            )
    if origin_y is not None:
        for edge_name, edge_value in transformed_opposite_edges(
            origin_y,
            height,
        ).items():
            denominator_bits = general.arithmetic.float32_bits(edge_value * width)
            numerator_bits = general.arithmetic.float32_bits(edge_value * scaled_value)
            numerator_significand, transformed_numerator_lsb = (
                float_significand_and_lsb_exponent(numerator_bits)
            )
            (
                transformed_reciprocal,
                transformed_reciprocal_exponent,
                transformed_class,
            ) = nearest_reciprocal_for_float(denominator_bits)
            transformed_offset = canonical[
                transformed_class - general.factorized.NORMALIZED_DENOMINATOR_LOWER
            ] - general.arithmetic.nearest_even_reciprocal_index(transformed_class)
            for selector_name, reciprocal in (
                ("nearestReciprocal", transformed_reciprocal),
                (
                    "floorClassOffset",
                    transformed_reciprocal + transformed_offset,
                ),
            ):
                result[f"{edge_name}_{selector_name}"] = physical_product_with_exponent(
                    numerator_significand,
                    transformed_numerator_lsb,
                    reciprocal,
                    transformed_reciprocal_exponent,
                )
    return result


def analyze(
    root: Path,
    radius: int,
    *,
    models_only: bool,
) -> dict[str, object]:
    _, raw_path = general.validate_manifest(root)
    data = raw_path.read_bytes()
    widths = general.factorized.geometry_widths()
    shifts = general.factorized.delta_exponent_shift_bits()
    delta_bits = general.arithmetic.witness_delta_bits()

    def pulls_at(
        width_index: int,
        witness_index: int,
        geometry_index: int,
        sample_side: int,
    ) -> tuple[int, int]:
        record_index = (
            (width_index * len(general.arithmetic.WITNESS_SIGNIFICANDS) + witness_index)
            * general.GEOMETRY_COUNT
            * general.SAMPLE_SIDE_COUNT
            + geometry_index * general.SAMPLE_SIDE_COUNT
            + sample_side
        )
        return struct.unpack_from("<II", data, record_index * general.RECORD_BYTES)

    per_height_nearest: list[Counter[int]] = [Counter() for _ in general.GEOMETRY_CASES]
    per_height_multiplicity: list[Counter[int]] = [
        Counter() for _ in general.GEOMETRY_CASES
    ]
    intersection_multiplicity: Counter[int] = Counter()
    intersection_nearest: Counter[int] = Counter()
    union_span: Counter[tuple[int, int]] = Counter()
    empty_examples: list[dict[str, object]] = []
    canonical = general.factorized.canonical_reciprocals()
    model_acceptance: dict[str, list[int]] = {}
    model_ulp_error: dict[str, list[Counter[int]]] = {}

    for width_index, width in enumerate(widths):
        for witness_index, original_bits in enumerate(delta_bits):
            scaled_bits = original_bits - shifts[width_index]
            scaled_delta = general.arithmetic.float32_value(scaled_bits)
            direct_bits = general.arithmetic.float32_bits(scaled_delta / width)
            candidates = [] if models_only else nearby_bits(direct_bits, radius)
            accepted_by_height: list[set[int]] = []
            observations_by_height: list[list[tuple[float, int]]] = []
            for geometry_index, geometry in enumerate(general.GEOMETRY_CASES):
                observations: list[tuple[float, int]] = []
                for sample_side in range(general.SAMPLE_SIDE_COUNT):
                    pulls = pulls_at(
                        width_index,
                        witness_index,
                        geometry_index,
                        sample_side,
                    )
                    position = float(
                        general.sample_position(width, geometry, sample_side)[
                            "tileLocalX"
                        ]
                    )
                    observations.extend(
                        ((position, pulls[0]), (position + 0.9375, pulls[1]))
                    )
                accepted = {
                    bits
                    for bits in candidates
                    if general.factorized.shared_plane_accepts_slope(
                        bits,
                        observations=observations,
                    )
                }
                accepted_by_height.append(accepted)
                observations_by_height.append(observations)
                per_height_multiplicity[geometry_index][len(accepted)] += 1
                if accepted:
                    nearest = min(
                        accepted,
                        key=lambda bits: (abs(bits - direct_bits), bits),
                    )
                    per_height_nearest[geometry_index][
                        signed_ulp_delta(nearest, direct_bits)
                    ] += 1

            for geometry_index, geometry in enumerate(general.GEOMETRY_CASES):
                predictions = model_predictions(
                    width=width,
                    height=int(geometry["height"]),
                    original_delta_bits=original_bits,
                    delta_exponent_shift=shifts[width_index],
                    canonical=canonical,
                    origin_y=int(geometry["originY"]),
                )
                accepted_prediction_bits = {
                    bits
                    for bits in set(predictions.values())
                    if general.factorized.shared_plane_accepts_slope(
                        bits,
                        observations=observations_by_height[geometry_index],
                    )
                }
                for name, predicted_bits in predictions.items():
                    model_acceptance.setdefault(name, [0] * len(general.GEOMETRY_CASES))
                    model_ulp_error.setdefault(
                        name,
                        [Counter() for _ in general.GEOMETRY_CASES],
                    )
                    if predicted_bits in accepted_prediction_bits:
                        model_acceptance[name][geometry_index] += 1
                    accepted = accepted_by_height[geometry_index]
                    if accepted and not models_only:
                        nearest_observed = min(
                            accepted,
                            key=lambda bits: (
                                abs(bits - predicted_bits),
                                bits,
                            ),
                        )
                        model_ulp_error[name][geometry_index][
                            nearest_observed - predicted_bits
                        ] += 1

            if models_only:
                continue
            intersection = set.intersection(*accepted_by_height)
            intersection_multiplicity[len(intersection)] += 1
            if intersection:
                nearest = min(
                    intersection,
                    key=lambda bits: (abs(bits - direct_bits), bits),
                )
                intersection_nearest[nearest - direct_bits] += 1
            elif len(empty_examples) < 32:
                empty_examples.append(
                    {
                        "width": width,
                        "witnessIndex": witness_index,
                        "directBits": f"0x{direct_bits:08x}",
                        "acceptedDeltasByHeight": [
                            sorted(bits - direct_bits for bits in accepted)
                            for accepted in accepted_by_height
                        ],
                    }
                )
            all_accepted = set.union(*accepted_by_height)
            if all_accepted:
                union_span[
                    (
                        min(all_accepted) - direct_bits,
                        max(all_accepted) - direct_bits,
                    )
                ] += 1

    return {
        "radius": radius,
        "modelsOnly": models_only,
        "coefficientCount": len(widths) * len(delta_bits),
        "heightNames": [item["name"] for item in general.GEOMETRY_CASES],
        "perHeightAcceptedMultiplicity": [
            dict(sorted(counter.items())) for counter in per_height_multiplicity
        ],
        "perHeightNearestAcceptedDelta": [
            dict(sorted(counter.items())) for counter in per_height_nearest
        ],
        "allHeightIntersectionMultiplicity": dict(
            sorted(intersection_multiplicity.items())
        ),
        "allHeightIntersectionNearestDelta": dict(sorted(intersection_nearest.items())),
        "unionDeltaSpan": {
            f"{lower}:{upper}": count
            for (lower, upper), count in sorted(union_span.items())
        },
        "emptyIntersectionExamples": empty_examples,
        "modelAcceptanceByHeight": model_acceptance,
        "modelNearestAcceptedUlpErrorByHeight": {
            name: [dict(sorted(counter.items())) for counter in counters]
            for name, counters in model_ulp_error.items()
        },
    }


def scan_area_selectors(root: Path, radius: int) -> dict[str, object]:
    _, raw_path = general.validate_manifest(root)
    data = raw_path.read_bytes()
    widths = general.factorized.geometry_widths()
    shifts = general.factorized.delta_exponent_shift_bits()
    delta_bits = general.arithmetic.witness_delta_bits()
    canonical = general.factorized.canonical_reciprocals()

    def pulls_at(
        width_index: int,
        witness_index: int,
        geometry_index: int,
        sample_side: int,
    ) -> tuple[int, int]:
        record_index = (
            (width_index * len(delta_bits) + witness_index)
            * general.GEOMETRY_COUNT
            * general.SAMPLE_SIDE_COUNT
            + geometry_index * general.SAMPLE_SIDE_COUNT
            + sample_side
        )
        return struct.unpack_from("<II", data, record_index * general.RECORD_BYTES)

    multiplicity = [Counter() for _ in general.GEOMETRY_CASES]
    accepted_offset = [Counter() for _ in general.GEOMETRY_CASES]
    top_class_offset_accepted = [0] * len(general.GEOMETRY_CASES)
    failures: list[dict[str, object]] = []
    for width_index, width in enumerate(widths):
        for geometry_index, geometry in enumerate(general.GEOMETRY_CASES):
            height = int(geometry["height"])
            area = width * height
            nearest = general.arithmetic.nearest_even_reciprocal_index(area)
            class_index = normalized_class(area, rounding="floor")
            frozen_offset = canonical[
                class_index - general.factorized.NORMALIZED_DENOMINATOR_LOWER
            ] - general.arithmetic.nearest_even_reciprocal_index(class_index)
            observations_by_witness: list[list[tuple[float, int]]] = []
            for witness_index in range(len(delta_bits)):
                observations: list[tuple[float, int]] = []
                for sample_side in range(general.SAMPLE_SIDE_COUNT):
                    pulls = pulls_at(
                        width_index,
                        witness_index,
                        geometry_index,
                        sample_side,
                    )
                    position = float(
                        general.sample_position(width, geometry, sample_side)[
                            "tileLocalX"
                        ]
                    )
                    observations.extend(
                        ((position, pulls[0]), (position + 0.9375, pulls[1]))
                    )
                observations_by_witness.append(observations)

            matching: list[int] = []
            for offset in range(-radius, radius + 1):
                reciprocal = nearest + offset
                edge_multiplier = height * reciprocal
                accepted = True
                for witness_index, original_bits in enumerate(delta_bits):
                    scaled_bits = original_bits - shifts[width_index]
                    significand, lsb_exponent = float_significand_and_lsb_exponent(
                        scaled_bits
                    )
                    predicted = generalized_physical_product_bits(
                        significand,
                        lsb_exponent,
                        area,
                        edge_multiplier,
                    )
                    if not general.factorized.shared_plane_accepts_slope(
                        predicted,
                        observations=observations_by_witness[witness_index],
                    ):
                        accepted = False
                        break
                if accepted:
                    matching.append(offset)
            multiplicity[geometry_index][len(matching)] += 1
            for offset in matching:
                accepted_offset[geometry_index][offset] += 1
            top_class_offset_accepted[geometry_index] += frozen_offset in matching
            if not matching and len(failures) < 32:
                failures.append(
                    {
                        "width": width,
                        "height": height,
                        "area": area,
                        "normalizedClassFloor": class_index,
                        "topClassOffset": frozen_offset,
                    }
                )

    return {
        "selectorModel": (
            "exact-height-times-25-bit-area-reciprocal then measured "
            "physical partial-product law"
        ),
        "candidateRadius": radius,
        "widthCount": len(widths),
        "witnessCount": len(delta_bits),
        "heightNames": [item["name"] for item in general.GEOMETRY_CASES],
        "matchMultiplicityByHeight": [
            dict(sorted(counter.items())) for counter in multiplicity
        ],
        "acceptedOffsetCountsByHeight": [
            dict(sorted(counter.items())) for counter in accepted_offset
        ],
        "topIntegerClassOffsetAcceptedCountByHeight": (top_class_offset_accepted),
        "failureExamples": failures,
    }


def evaluate_legacy_report(path: Path) -> dict[str, object]:
    source = json.loads(path.read_text(encoding="utf-8"))
    canonical = general.factorized.canonical_reciprocals()
    counts: dict[str, Counter[str]] = {}
    totals: Counter[str] = Counter()
    errors: dict[str, dict[str, Counter[int]]] = {}
    for sample in source.get("samples", []):
        base = str(sample["baseCase"])
        category = (
            "power2-opposite-edge"
            if "factor-h064" in base
            else "nonpower-opposite-edge"
        )
        axis = str(sample["axis"])
        group = f"{category}/{axis}"
        numerator = int(sample["deltaNumerator"])
        denominator = int(sample["deltaDenominator"])
        delta_bits = general.arithmetic.float32_bits(numerator / denominator)
        predictions = model_predictions(
            width=int(sample["axisDimension"]),
            height=int(sample["otherDimension"]),
            original_delta_bits=delta_bits,
            delta_exponent_shift=0,
            canonical=canonical,
        )
        observed = int(str(sample["observedBits"]), 16)
        totals[group] += 1
        for name, predicted in predictions.items():
            counts.setdefault(name, Counter())[group] += predicted == observed
            errors.setdefault(name, {}).setdefault(group, Counter())[
                observed - predicted
            ] += 1
    return {
        "source": str(path),
        "groupTotals": dict(sorted(totals.items())),
        "modelExactMatches": {
            name: dict(sorted(counter.items())) for name, counter in counts.items()
        },
        "modelFloatUlpErrors": {
            name: {
                group: dict(sorted(counter.items()))
                for group, counter in sorted(groups.items())
            }
            for name, groups in errors.items()
        },
    }


def evaluate_calibrated_area_subset(root: Path) -> dict[str, object]:
    _, raw_path = general.validate_manifest(root)
    data = raw_path.read_bytes()
    widths = general.factorized.geometry_widths()
    shifts = general.factorized.delta_exponent_shift_bits()
    delta_bits = general.arithmetic.witness_delta_bits()
    canonical = general.factorized.canonical_reciprocals()
    selected_models = (
        "directDivide",
        "areaF32Numerator_floorClassOffset",
        "areaExactNumerator_floorClassOffset",
        "edgeExactMultiplier_floorClassOffset",
    )
    coefficient_matches = {
        name: [0] * len(general.GEOMETRY_CASES) for name in selected_models
    }
    signature_matches = {
        name: [0] * len(general.GEOMETRY_CASES) for name in selected_models
    }
    width_counts = [0] * len(general.GEOMETRY_CASES)

    def pulls_at(
        width_index: int,
        witness_index: int,
        geometry_index: int,
        sample_side: int,
    ) -> tuple[int, int]:
        record_index = (
            (width_index * len(delta_bits) + witness_index)
            * general.GEOMETRY_COUNT
            * general.SAMPLE_SIDE_COUNT
            + geometry_index * general.SAMPLE_SIDE_COUNT
            + sample_side
        )
        return struct.unpack_from("<II", data, record_index * general.RECORD_BYTES)

    for width_index, width in enumerate(widths):
        for geometry_index, geometry in enumerate(general.GEOMETRY_CASES):
            height = int(geometry["height"])
            area = width * height
            normalization_shift = area.bit_length() - 14
            if normalization_shift > 0 and area % (1 << normalization_shift):
                continue
            width_counts[geometry_index] += 1
            whole = {name: True for name in selected_models}
            for witness_index, original_bits in enumerate(delta_bits):
                observations: list[tuple[float, int]] = []
                for sample_side in range(general.SAMPLE_SIDE_COUNT):
                    pulls = pulls_at(
                        width_index,
                        witness_index,
                        geometry_index,
                        sample_side,
                    )
                    position = float(
                        general.sample_position(width, geometry, sample_side)[
                            "tileLocalX"
                        ]
                    )
                    observations.extend(
                        ((position, pulls[0]), (position + 0.9375, pulls[1]))
                    )
                predictions = model_predictions(
                    width=width,
                    height=height,
                    original_delta_bits=original_bits,
                    delta_exponent_shift=shifts[width_index],
                    canonical=canonical,
                    origin_y=int(geometry["originY"]),
                )
                for name in selected_models:
                    accepted = general.factorized.shared_plane_accepts_slope(
                        predictions[name],
                        observations=observations,
                    )
                    coefficient_matches[name][geometry_index] += accepted
                    whole[name] &= accepted
            for name in selected_models:
                signature_matches[name][geometry_index] += whole[name]
    return {
        "heightNames": [item["name"] for item in general.GEOMETRY_CASES],
        "calibratedAreaWidthCountByHeight": width_counts,
        "expectedCoefficientCountByHeight": [
            count * len(delta_bits) for count in width_counts
        ],
        "coefficientMatchesByHeight": coefficient_matches,
        "wholeSignatureMatchesByHeight": signature_matches,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--radius", type=int, default=8)
    parser.add_argument("--models-only", action="store_true")
    parser.add_argument("--selector-scan", action="store_true")
    parser.add_argument("--legacy-report", type=Path)
    parser.add_argument("--calibrated-subset", action="store_true")
    arguments = parser.parse_args()
    if arguments.calibrated_subset:
        print(json.dumps(evaluate_calibrated_area_subset(arguments.root), indent=2))
        return
    if arguments.legacy_report is not None:
        print(json.dumps(evaluate_legacy_report(arguments.legacy_report), indent=2))
        return
    if arguments.selector_scan:
        print(
            json.dumps(scan_area_selectors(arguments.root, arguments.radius), indent=2)
        )
        return
    print(
        json.dumps(
            analyze(
                arguments.root,
                arguments.radius,
                models_only=arguments.models_only,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
