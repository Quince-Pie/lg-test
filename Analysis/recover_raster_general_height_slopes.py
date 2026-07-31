#!/usr/bin/env python3
"""Recover exact slope candidates from the general-height diagnostic."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

import analyze_raster_general_height_diagnostic as analyzer
import explore_general_height as explore
import validate_raster_general_height_diagnostic as diagnostic


type JsonObject = dict[str, Any]


def counter_json(counter: Counter[int]) -> dict[str, int]:
    return {str(key): value for key, value in sorted(counter.items())}


def sha256_uint32(values: np.ndarray) -> str:
    return hashlib.sha256(values.astype("<u4", copy=False).tobytes()).hexdigest()


def reciprocal_candidates(
    *,
    numerators: list[tuple[int, int]],
    denominator: int,
    accepted_slopes: list[set[int]],
    exact_height: int | None,
) -> list[int]:
    def product(
        reciprocal: int,
        significand: int,
        lsb_exponent: int,
    ) -> int:
        multiplicand = (
            significand * exact_height if exact_height is not None else significand
        )
        return explore.generalized_physical_product_bits(
            multiplicand,
            lsb_exponent,
            denominator,
            reciprocal,
        )

    def first_at_least(
        target: int,
        significand: int,
        lsb_exponent: int,
    ) -> int:
        lower = 1 << 24
        upper = 1 << 25
        while lower < upper:
            middle = (lower + upper) // 2
            if product(middle, significand, lsb_exponent) < target:
                lower = middle + 1
            else:
                upper = middle
        return lower

    lower = 1 << 24
    upper = (1 << 25) - 1
    for (significand, lsb_exponent), slopes in zip(
        numerators,
        accepted_slopes,
        strict=True,
    ):
        if not slopes:
            return []
        lower = max(
            lower,
            first_at_least(min(slopes), significand, lsb_exponent),
        )
        upper = min(
            upper,
            first_at_least(
                max(slopes) + 1,
                significand,
                lsb_exponent,
            )
            - 1,
        )
        if lower > upper:
            return []

    return [
        reciprocal
        for reciprocal in range(lower, upper + 1)
        if all(
            product(reciprocal, significand, lsb_exponent) in slopes
            for (significand, lsb_exponent), slopes in zip(
                numerators,
                accepted_slopes,
                strict=True,
            )
        )
    ]


def recover(
    root: Path,
    *,
    radius: int,
    selector_radius: int,
) -> tuple[JsonObject, np.ndarray]:
    manifest, raw_path = diagnostic.validate_manifest(root)
    shape = (
        diagnostic.factorized.WIDTH_COUNT,
        len(diagnostic.arithmetic.WITNESS_SIGNIFICANDS),
        diagnostic.GEOMETRY_COUNT,
        diagnostic.SAMPLE_SIDE_COUNT,
        4,
    )
    records = np.fromfile(raw_path, dtype="<u4").reshape(shape)
    widths = diagnostic.factorized.geometry_widths()
    shifts = diagnostic.factorized.delta_exponent_shift_bits()
    delta_bits = diagnostic.arithmetic.witness_delta_bits()
    canonical = diagnostic.factorized.canonical_reciprocals()
    common_multiplicity = [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)]
    derivative_multiplicity = [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)]
    common_offsets = [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)]
    derivative_offsets = [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)]
    constant_multiplicity = [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)]
    selector_multiplicity = {
        "exactNumerator": [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)],
        "roundedNumerator": [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)],
    }
    selector_offsets = {
        "exactNumerator": [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)],
        "roundedNumerator": [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)],
    }
    class_selector_width_matches = {
        f"{numerator}_{rounding}ClassCanonical": [0] * diagnostic.GEOMETRY_COUNT
        for numerator in ("exactNumerator", "roundedNumerator")
        for rounding in ("floor", "nearest", "ceil")
    }
    class_selector_coefficient_matches = {
        name: [0] * diagnostic.GEOMETRY_COUNT for name in class_selector_width_matches
    }
    inverse_selector_multiplicity = {
        "exactNumerator": [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)],
        "roundedNumerator": [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)],
    }
    inverse_selector_offsets = {
        "exactNumerator": [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)],
        "roundedNumerator": [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)],
    }
    recovered_reciprocals = {
        name: np.full(
            (diagnostic.factorized.WIDTH_COUNT, diagnostic.GEOMETRY_COUNT),
            0xFFFF_FFFF,
            dtype="<u4",
        )
        for name in inverse_selector_multiplicity
    }
    examples: list[JsonObject] = []
    recovered = np.full(
        (
            diagnostic.factorized.WIDTH_COUNT,
            len(delta_bits),
            diagnostic.GEOMETRY_COUNT,
        ),
        0xFFFF_FFFF,
        dtype="<u4",
    )

    for width_index, width in enumerate(widths):
        derivative_bits_by_geometry: list[list[set[int]]] = [
            [set() for _ in delta_bits] for _ in range(diagnostic.GEOMETRY_COUNT)
        ]
        exact_numerators: list[tuple[int, int]] = []
        rounded_numerators: list[list[tuple[int, int]]] = [
            [] for _ in range(diagnostic.GEOMETRY_COUNT)
        ]
        positions = [
            float(
                diagnostic.sample_position(
                    width,
                    diagnostic.failed_general.GEOMETRY_CASES[0],
                    side,
                )["tileLocalX"]
            )
            for side in range(diagnostic.SAMPLE_SIDE_COUNT)
        ]
        for witness_index, original_bits in enumerate(delta_bits):
            scaled_bits = original_bits - shifts[width_index]
            scaled_value = diagnostic.arithmetic.float32_value(scaled_bits)
            direct_bits = diagnostic.arithmetic.float32_bits(scaled_value / width)
            scaled_significand, scaled_lsb = explore.float_significand_and_lsb_exponent(
                scaled_bits
            )
            exact_numerators.append((scaled_significand, scaled_lsb))
            for geometry_index in range(diagnostic.GEOMETRY_COUNT):
                height = int(
                    diagnostic.failed_general.GEOMETRY_CASES[geometry_index]["height"]
                )
                rounded_bits = diagnostic.arithmetic.float32_bits(scaled_value * height)
                rounded_numerators[geometry_index].append(
                    explore.float_significand_and_lsb_exponent(rounded_bits)
                )
                selected = records[width_index, witness_index, geometry_index]
                pull_observations = [
                    observation
                    for side, position in enumerate(positions)
                    for observation in (
                        (position, int(selected[side, 0])),
                        (position + 0.9375, int(selected[side, 1])),
                    )
                ]
                center_observations = [
                    (position + 0.5, int(selected[side, 2]))
                    for side, position in enumerate(positions)
                ]
                derivative_observations = [
                    (position + 0.5, int(selected[side, 3]))
                    for side, position in enumerate(positions)
                ]
                common: list[tuple[int, tuple[int, ...]]] = []
                derivative: list[int] = []
                for offset in range(-radius, radius + 1):
                    slope_bits = direct_bits + offset
                    constants = analyzer.shared_iterator_constant_bits(
                        slope_bits,
                        pull_observations=pull_observations,
                        center_observations=center_observations,
                    )
                    if not constants:
                        continue
                    common.append((offset, constants))
                    slope = diagnostic.arithmetic.float32_value(slope_bits)
                    if any(
                        all(
                            analyzer.derivative_bits(position, slope, constant)
                            == expected
                            for position, expected in derivative_observations
                        )
                        for constant in map(
                            diagnostic.arithmetic.float32_value,
                            constants,
                        )
                    ):
                        derivative.append(offset)

                common_multiplicity[geometry_index][len(common)] += 1
                derivative_multiplicity[geometry_index][len(derivative)] += 1
                for offset, constants in common:
                    common_offsets[geometry_index][offset] += 1
                    constant_multiplicity[geometry_index][len(constants)] += 1
                for offset in derivative:
                    derivative_offsets[geometry_index][offset] += 1
                    derivative_bits_by_geometry[geometry_index][witness_index].add(
                        direct_bits + offset
                    )
                if len(derivative) == 1:
                    recovered[width_index, witness_index, geometry_index] = (
                        direct_bits + derivative[0]
                    )
                elif len(examples) < 32:
                    examples.append(
                        {
                            "width": width,
                            "witnessIndex": witness_index,
                            "height": int(
                                diagnostic.failed_general.GEOMETRY_CASES[
                                    geometry_index
                                ]["height"]
                            ),
                            "directBits": f"0x{direct_bits:08x}",
                            "commonOffsets": [offset for offset, _ in common],
                            "derivativeOffsets": derivative,
                        }
                    )

        for geometry_index, geometry in enumerate(
            diagnostic.failed_general.GEOMETRY_CASES
        ):
            height = int(geometry["height"])
            area = width * height
            nearest_area = diagnostic.arithmetic.nearest_even_reciprocal_index(area)
            accepted_slopes = derivative_bits_by_geometry[geometry_index]
            for model_name, numerators, exact_height in (
                ("exactNumerator", exact_numerators, height),
                (
                    "roundedNumerator",
                    rounded_numerators[geometry_index],
                    None,
                ),
            ):
                matching_reciprocals = reciprocal_candidates(
                    numerators=numerators,
                    denominator=area,
                    accepted_slopes=accepted_slopes,
                    exact_height=exact_height,
                )
                inverse_selector_multiplicity[model_name][geometry_index][
                    len(matching_reciprocals)
                ] += 1
                for reciprocal in matching_reciprocals:
                    inverse_selector_offsets[model_name][geometry_index][
                        reciprocal - nearest_area
                    ] += 1
                if len(matching_reciprocals) == 1:
                    recovered_reciprocals[model_name][
                        width_index,
                        geometry_index,
                    ] = matching_reciprocals[0]
            for class_rounding in ("floor", "nearest", "ceil"):
                class_index = explore.normalized_class(
                    area,
                    rounding=class_rounding,
                )
                reciprocal = canonical[
                    class_index - diagnostic.factorized.NORMALIZED_DENOMINATOR_LOWER
                ]
                for model_name, numerators in (
                    ("exactNumerator", exact_numerators),
                    ("roundedNumerator", rounded_numerators[geometry_index]),
                ):
                    name = f"{model_name}_{class_rounding}ClassCanonical"
                    coefficient_matches = 0
                    for witness_index, (significand, lsb_exponent) in enumerate(
                        numerators
                    ):
                        multiplicand = (
                            significand * height
                            if model_name == "exactNumerator"
                            else significand
                        )
                        predicted = explore.generalized_physical_product_bits(
                            multiplicand,
                            lsb_exponent,
                            area,
                            reciprocal,
                        )
                        coefficient_matches += (
                            predicted
                            in derivative_bits_by_geometry[geometry_index][
                                witness_index
                            ]
                        )
                    class_selector_coefficient_matches[name][geometry_index] += (
                        coefficient_matches
                    )
                    class_selector_width_matches[name][geometry_index] += (
                        coefficient_matches == len(delta_bits)
                    )
            for model_name in selector_multiplicity:
                numerators = (
                    exact_numerators
                    if model_name == "exactNumerator"
                    else rounded_numerators[geometry_index]
                )
                matching: list[int] = []
                for selector_offset in range(
                    -selector_radius,
                    selector_radius + 1,
                ):
                    reciprocal = nearest_area + selector_offset
                    accepted = True
                    for witness_index, (significand, lsb_exponent) in enumerate(
                        numerators
                    ):
                        multiplicand = (
                            significand * height
                            if model_name == "exactNumerator"
                            else significand
                        )
                        predicted = explore.generalized_physical_product_bits(
                            multiplicand,
                            lsb_exponent,
                            area,
                            reciprocal,
                        )
                        if (
                            predicted
                            not in derivative_bits_by_geometry[geometry_index][
                                witness_index
                            ]
                        ):
                            accepted = False
                            break
                    if accepted:
                        matching.append(selector_offset)
                selector_multiplicity[model_name][geometry_index][len(matching)] += 1
                for selector_offset in matching:
                    selector_offsets[model_name][geometry_index][selector_offset] += 1

    coefficient_count = diagnostic.factorized.WIDTH_COUNT * len(delta_bits)
    uniquely_recovered = int(np.count_nonzero(recovered != 0xFFFF_FFFF))
    report: JsonObject = {
        "liquidGlassRasterGeneralHeightSlopeRecoverySchemaVersion": 1,
        "probe": str(root),
        "ciCommit": manifest.get("ciCommit"),
        "manifestSha256": diagnostic.sha256_path(root / "manifest.json"),
        "rawSha256": diagnostic.sha256_path(raw_path),
        "measurement": {
            "candidateRadiusFloatUlps": radius,
            "selectorRadiusInternalUlps": selector_radius,
            "coefficientCountPerHeight": coefficient_count,
            "coefficientCount": coefficient_count * diagnostic.GEOMETRY_COUNT,
            "commonCenterPullMultiplicityByHeight": [
                counter_json(counter) for counter in common_multiplicity
            ],
            "commonCenterPullAcceptedOffsetsByHeight": [
                counter_json(counter) for counter in common_offsets
            ],
            "commonConstantMultiplicityByHeight": [
                counter_json(counter) for counter in constant_multiplicity
            ],
            "centerPullDerivativeMultiplicityByHeight": [
                counter_json(counter) for counter in derivative_multiplicity
            ],
            "centerPullDerivativeAcceptedOffsetsByHeight": [
                counter_json(counter) for counter in derivative_offsets
            ],
            "uniquelyRecoveredCoefficientCount": uniquely_recovered,
            "recoveredCoefficientSha256": sha256_uint32(recovered),
            "selectorMultiplicityByHeight": {
                name: [counter_json(counter) for counter in counters]
                for name, counters in selector_multiplicity.items()
            },
            "selectorAcceptedOffsetsByHeight": {
                name: [counter_json(counter) for counter in counters]
                for name, counters in selector_offsets.items()
            },
            "classCanonicalWidthMatchesByHeight": class_selector_width_matches,
            "classCanonicalCoefficientMatchesByHeight": (
                class_selector_coefficient_matches
            ),
            "inverseSelectorMultiplicityByHeight": {
                name: [counter_json(counter) for counter in counters]
                for name, counters in inverse_selector_multiplicity.items()
            },
            "inverseSelectorAcceptedOffsetsByHeight": {
                name: [counter_json(counter) for counter in counters]
                for name, counters in inverse_selector_offsets.items()
            },
            "uniquelyRecoveredReciprocalSha256": {
                name: sha256_uint32(values)
                for name, values in recovered_reciprocals.items()
            },
            "firstNonUniqueExamples": examples,
        },
        "conclusions": {
            "allCoefficientsUniquelyRecovered": (uniquely_recovered == recovered.size),
            "derivativeSubtractionModelEstablished": (
                uniquely_recovered == recovered.size
            ),
            "selectorLawEstablished": False,
            "endToEndLiquidGlassParityEstablished": False,
        },
    }
    return report, recovered


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--radius", type=int, default=2)
    parser.add_argument("--selector-radius", type=int, default=8)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--recovered-output", type=Path)
    arguments = parser.parse_args()
    report, recovered = recover(
        arguments.root,
        radius=arguments.radius,
        selector_radius=arguments.selector_radius,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(rendered, end="")
    else:
        arguments.output.write_text(rendered, encoding="utf-8")
    if arguments.recovered_output is not None:
        recovered.tofile(arguments.recovered_output)


if __name__ == "__main__":
    main()
