#!/usr/bin/env python3
"""Analyze direct derivative evidence in the general-height diagnostic."""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

import explore_general_height as explore
import validate_raster_general_height_diagnostic as diagnostic


type JsonObject = dict[str, Any]


def counter_json(counter: Counter[int]) -> dict[str, int]:
    return {str(key): value for key, value in sorted(counter.items())}


def toward_zero_bits(value: float) -> int:
    bits = diagnostic.arithmetic.float32_bits(value)
    rounded = diagnostic.arithmetic.float32_value(bits)
    if value > 0.0 and rounded > value:
        return bits - 1
    if value < 0.0 and rounded < value:
        return bits - 1
    return bits


def center_iterator_bits(position: float, slope: float, constant: float) -> int:
    return toward_zero_bits(position * slope + constant)


def shared_center_plane_accepts_slope(
    slope_bits: int,
    *,
    observations: list[tuple[float, int]],
) -> bool:
    slope = diagnostic.arithmetic.float32_value(slope_bits)
    if any(bits == 0 or bits >> 31 for _, bits in observations):
        raise ValueError("positive nonzero center values are required")
    lower = max(
        diagnostic.arithmetic.float32_value(bits) - position * slope
        for position, bits in observations
    )
    upper = min(
        diagnostic.arithmetic.float32_value(
            diagnostic.arithmetic.next_float32_bits(bits, upward=True)
        )
        - position * slope
        for position, bits in observations
    )
    if lower >= upper:
        return False
    constant_bits = diagnostic.arithmetic.float32_bits(lower)
    if diagnostic.arithmetic.float32_value(constant_bits) < lower:
        constant_bits = diagnostic.arithmetic.next_float32_bits(
            constant_bits,
            upward=True,
        )
    for _ in range(128):
        constant = diagnostic.arithmetic.float32_value(constant_bits)
        if constant >= upper:
            return False
        if all(
            center_iterator_bits(position, slope, constant) == expected
            for position, expected in observations
        ):
            return True
        constant_bits = diagnostic.arithmetic.next_float32_bits(
            constant_bits,
            upward=True,
        )
    raise ValueError("center-plane constant interval is too wide")


def shared_iterator_constant_bits(
    slope_bits: int,
    *,
    pull_observations: list[tuple[float, int]],
    center_observations: list[tuple[float, int]],
) -> tuple[int, ...]:
    slope = diagnostic.arithmetic.float32_value(slope_bits)
    if any(bits == 0 or bits >> 31 for _, bits in center_observations):
        raise ValueError("positive nonzero center values are required")
    lower = max(
        *(
            diagnostic.arithmetic.float32_rounding_bounds(bits)[0] - position * slope
            for position, bits in pull_observations
        ),
        *(
            diagnostic.arithmetic.float32_value(bits) - position * slope
            for position, bits in center_observations
        ),
    )
    upper = min(
        *(
            diagnostic.arithmetic.float32_rounding_bounds(bits)[1] - position * slope
            for position, bits in pull_observations
        ),
        *(
            diagnostic.arithmetic.float32_value(
                diagnostic.arithmetic.next_float32_bits(bits, upward=True)
            )
            - position * slope
            for position, bits in center_observations
        ),
    )
    if lower > upper:
        return ()
    constant_bits = diagnostic.arithmetic.float32_bits(lower)
    if diagnostic.arithmetic.float32_value(constant_bits) < lower:
        constant_bits = diagnostic.arithmetic.next_float32_bits(
            constant_bits,
            upward=True,
        )
    accepted: list[int] = []
    for _ in range(128):
        constant = diagnostic.arithmetic.float32_value(constant_bits)
        if constant > upper:
            return tuple(accepted)
        if all(
            diagnostic.arithmetic.float32_bits(position * slope + constant) == expected
            for position, expected in pull_observations
        ) and all(
            center_iterator_bits(position, slope, constant) == expected
            for position, expected in center_observations
        ):
            accepted.append(constant_bits)
        constant_bits = diagnostic.arithmetic.next_float32_bits(
            constant_bits,
            upward=True,
        )
    raise ValueError("shared iterator constant interval is too wide")


def derivative_bits(
    position: float,
    slope: float,
    constant: float,
) -> int:
    right = diagnostic.arithmetic.float32_value(
        center_iterator_bits(position, slope, constant)
    )
    left = diagnostic.arithmetic.float32_value(
        center_iterator_bits(position - 1.0, slope, constant)
    )
    return diagnostic.arithmetic.float32_bits(right - left)


def shared_iterator_accepts_slope(
    slope_bits: int,
    *,
    pull_observations: list[tuple[float, int]],
    center_observations: list[tuple[float, int]],
    derivative_observations: list[tuple[float, int]] | None = None,
) -> bool:
    constants = shared_iterator_constant_bits(
        slope_bits,
        pull_observations=pull_observations,
        center_observations=center_observations,
    )
    if derivative_observations is None:
        return bool(constants)
    slope = diagnostic.arithmetic.float32_value(slope_bits)
    return any(
        all(
            derivative_bits(position, slope, constant) == expected
            for position, expected in derivative_observations
        )
        for constant in map(diagnostic.arithmetic.float32_value, constants)
    )


def analyze(root: Path, *, selector_radius: int) -> JsonObject:
    manifest, raw_path = diagnostic.validate_manifest(root)
    shape = (
        diagnostic.factorized.WIDTH_COUNT,
        len(diagnostic.arithmetic.WITNESS_SIGNIFICANDS),
        diagnostic.GEOMETRY_COUNT,
        diagnostic.SAMPLE_SIDE_COUNT,
        4,
    )
    records = np.fromfile(raw_path, dtype="<u4").reshape(shape)
    pulls0 = records[..., 0]
    centers = records[..., 2]
    derivatives = records[..., 3]
    same_derivative = derivatives[..., 0] == derivatives[..., 1]
    center_matches_pull = centers == pulls0
    finite_derivatives = (derivatives & 0x7F80_0000) != 0x7F80_0000
    positive_derivatives = (derivatives & 0x8000_0000) == 0

    widths = diagnostic.factorized.geometry_widths()
    shifts = diagnostic.factorized.delta_exponent_shift_bits()
    delta_bits = diagnostic.arithmetic.witness_delta_bits()
    canonical = diagnostic.factorized.canonical_reciprocals()
    model_matches: dict[str, list[int]] = {}
    model_errors: dict[str, list[Counter[int]]] = {}
    model_joint_plane_acceptance: dict[str, list[int]] = {}
    model_shared_plane_acceptance: dict[str, list[int]] = {}
    model_derivative_acceptance: dict[str, list[int]] = {}
    derivative_accepts_pulls = [0] * diagnostic.GEOMETRY_COUNT
    derivative_pair_equal_by_height = [0] * diagnostic.GEOMETRY_COUNT
    selector_multiplicity = {
        "roundedNumerator": [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)],
        "exactNumerator": [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)],
    }
    selector_offsets = {
        "roundedNumerator": [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)],
        "exactNumerator": [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)],
    }

    def observations(
        width_index: int,
        witness_index: int,
        geometry_index: int,
    ) -> list[tuple[float, int]]:
        result: list[tuple[float, int]] = []
        width = widths[width_index]
        geometry = diagnostic.failed_general.GEOMETRY_CASES[geometry_index]
        for side in range(diagnostic.SAMPLE_SIDE_COUNT):
            position = float(
                diagnostic.sample_position(width, geometry, side)["tileLocalX"]
            )
            record = records[width_index, witness_index, geometry_index, side]
            result.extend(
                ((position, int(record[0])), (position + 0.9375, int(record[1])))
            )
        return result

    def center_observations(
        width_index: int,
        witness_index: int,
        geometry_index: int,
    ) -> list[tuple[float, int]]:
        width = widths[width_index]
        geometry = diagnostic.failed_general.GEOMETRY_CASES[geometry_index]
        return [
            (
                float(diagnostic.sample_position(width, geometry, side)["tileLocalX"])
                + 0.5,
                int(records[width_index, witness_index, geometry_index, side, 2]),
            )
            for side in range(diagnostic.SAMPLE_SIDE_COUNT)
        ]

    def derivative_observations(
        width_index: int,
        witness_index: int,
        geometry_index: int,
    ) -> list[tuple[float, int]]:
        width = widths[width_index]
        geometry = diagnostic.failed_general.GEOMETRY_CASES[geometry_index]
        return [
            (
                float(diagnostic.sample_position(width, geometry, side)["tileLocalX"])
                + 0.5,
                int(records[width_index, witness_index, geometry_index, side, 3]),
            )
            for side in range(diagnostic.SAMPLE_SIDE_COUNT)
        ]

    for width_index, width in enumerate(widths):
        for geometry_index, geometry in enumerate(
            diagnostic.failed_general.GEOMETRY_CASES
        ):
            height = int(geometry["height"])
            area = width * height
            nearest_area = diagnostic.arithmetic.nearest_even_reciprocal_index(area)
            class_index = explore.normalized_class(area, rounding="floor")
            class_offset = canonical[
                class_index - diagnostic.factorized.NORMALIZED_DENOMINATOR_LOWER
            ] - diagnostic.arithmetic.nearest_even_reciprocal_index(class_index)
            rounded_numerators: list[tuple[int, int]] = []
            exact_numerators: list[tuple[int, int]] = []
            for witness_index, original_bits in enumerate(delta_bits):
                derivative_pair = derivatives[
                    width_index, witness_index, geometry_index
                ]
                equal = bool(derivative_pair[0] == derivative_pair[1])
                derivative_pair_equal_by_height[geometry_index] += equal
                derivative_bits = int(derivative_pair[0])
                if diagnostic.factorized.shared_plane_accepts_slope(
                    derivative_bits,
                    observations=observations(
                        width_index,
                        witness_index,
                        geometry_index,
                    ),
                ):
                    derivative_accepts_pulls[geometry_index] += 1

                scaled_bits = original_bits - shifts[width_index]
                scaled_value = diagnostic.arithmetic.float32_value(scaled_bits)
                scaled_significand, scaled_lsb = (
                    explore.float_significand_and_lsb_exponent(scaled_bits)
                )
                rounded_bits = diagnostic.arithmetic.float32_bits(scaled_value * height)
                rounded_significand, rounded_lsb = (
                    explore.float_significand_and_lsb_exponent(rounded_bits)
                )
                rounded_numerators.append((rounded_significand, rounded_lsb))
                exact_numerators.append((scaled_significand * height, scaled_lsb))

                predictions = {
                    "directDivide": diagnostic.arithmetic.float32_bits(
                        scaled_value / width
                    ),
                    "roundedNumeratorNearestArea": (
                        explore.generalized_physical_product_bits(
                            rounded_significand,
                            rounded_lsb,
                            area,
                            nearest_area,
                        )
                    ),
                    "roundedNumeratorClassOffset": (
                        explore.generalized_physical_product_bits(
                            rounded_significand,
                            rounded_lsb,
                            area,
                            nearest_area + class_offset,
                        )
                    ),
                    "exactNumeratorNearestArea": (
                        explore.generalized_physical_product_bits(
                            scaled_significand * height,
                            scaled_lsb,
                            area,
                            nearest_area,
                        )
                    ),
                    "exactNumeratorClassOffset": (
                        explore.generalized_physical_product_bits(
                            scaled_significand * height,
                            scaled_lsb,
                            area,
                            nearest_area + class_offset,
                        )
                    ),
                }
                for name, predicted in predictions.items():
                    model_matches.setdefault(
                        name,
                        [0] * diagnostic.GEOMETRY_COUNT,
                    )[geometry_index] += predicted == derivative_bits
                    model_errors.setdefault(
                        name,
                        [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)],
                    )[geometry_index][derivative_bits - predicted] += 1
                    joint_accepted = diagnostic.factorized.shared_plane_accepts_slope(
                        predicted,
                        observations=observations(
                            width_index,
                            witness_index,
                            geometry_index,
                        ),
                    ) and shared_center_plane_accepts_slope(
                        predicted,
                        observations=center_observations(
                            width_index,
                            witness_index,
                            geometry_index,
                        ),
                    )
                    model_joint_plane_acceptance.setdefault(
                        name,
                        [0] * diagnostic.GEOMETRY_COUNT,
                    )[geometry_index] += joint_accepted
                    shared_accepted = shared_iterator_accepts_slope(
                        predicted,
                        pull_observations=observations(
                            width_index,
                            witness_index,
                            geometry_index,
                        ),
                        center_observations=center_observations(
                            width_index,
                            witness_index,
                            geometry_index,
                        ),
                    )
                    model_shared_plane_acceptance.setdefault(
                        name,
                        [0] * diagnostic.GEOMETRY_COUNT,
                    )[geometry_index] += shared_accepted
                    derivative_accepted = shared_iterator_accepts_slope(
                        predicted,
                        pull_observations=observations(
                            width_index,
                            witness_index,
                            geometry_index,
                        ),
                        center_observations=center_observations(
                            width_index,
                            witness_index,
                            geometry_index,
                        ),
                        derivative_observations=derivative_observations(
                            width_index,
                            witness_index,
                            geometry_index,
                        ),
                    )
                    model_derivative_acceptance.setdefault(
                        name,
                        [0] * diagnostic.GEOMETRY_COUNT,
                    )[geometry_index] += derivative_accepted

            for model_name, numerators in (
                ("roundedNumerator", rounded_numerators),
                ("exactNumerator", exact_numerators),
            ):
                matching: list[int] = []
                for offset in range(-selector_radius, selector_radius + 1):
                    reciprocal = nearest_area + offset
                    accepted = True
                    for witness_index, (significand, lsb_exponent) in enumerate(
                        numerators
                    ):
                        predicted = explore.generalized_physical_product_bits(
                            significand,
                            lsb_exponent,
                            area,
                            reciprocal,
                        )
                        if not (
                            diagnostic.factorized.shared_plane_accepts_slope(
                                predicted,
                                observations=observations(
                                    width_index,
                                    witness_index,
                                    geometry_index,
                                ),
                            )
                            and shared_center_plane_accepts_slope(
                                predicted,
                                observations=center_observations(
                                    width_index,
                                    witness_index,
                                    geometry_index,
                                ),
                            )
                        ):
                            accepted = False
                            break
                    if accepted:
                        matching.append(offset)
                selector_multiplicity[model_name][geometry_index][len(matching)] += 1
                for offset in matching:
                    selector_offsets[model_name][geometry_index][offset] += 1

    coefficient_count_per_height = diagnostic.factorized.WIDTH_COUNT * len(delta_bits)
    return {
        "liquidGlassRasterGeneralHeightDerivativeAnalysisSchemaVersion": 1,
        "probe": str(root),
        "ciCommit": manifest.get("ciCommit"),
        "manifestSha256": diagnostic.sha256_path(root / "manifest.json"),
        "rawSha256": diagnostic.sha256_path(raw_path),
        "measurement": {
            "recordCount": int(records.shape[0] * np.prod(records.shape[1:-1])),
            "finiteDerivativeRecordCount": int(np.count_nonzero(finite_derivatives)),
            "positiveDerivativeRecordCount": int(
                np.count_nonzero(positive_derivatives)
            ),
            "centerEqualsZeroXPullCount": int(np.count_nonzero(center_matches_pull)),
            "sameTileDerivativePairEqualCount": int(np.count_nonzero(same_derivative)),
            "sameTileDerivativePairCount": int(same_derivative.size),
            "derivativePairEqualByHeight": derivative_pair_equal_by_height,
            "derivativeAcceptsPullsByHeight": derivative_accepts_pulls,
            "coefficientCountPerHeight": coefficient_count_per_height,
            "modelExactMatchesByHeight": model_matches,
            "modelJointCenterAndPullAcceptanceByHeight": (model_joint_plane_acceptance),
            "modelSharedCenterAndPullAcceptanceByHeight": (
                model_shared_plane_acceptance
            ),
            "modelSharedCenterPullAndDerivativeAcceptanceByHeight": (
                model_derivative_acceptance
            ),
            "modelDerivativeMinusPredictionUlpByHeight": {
                name: [counter_json(counter) for counter in counters]
                for name, counters in model_errors.items()
            },
            "selectorCandidateRadius": selector_radius,
            "selectorMatchMultiplicityByHeight": {
                name: [counter_json(counter) for counter in counters]
                for name, counters in selector_multiplicity.items()
            },
            "selectorAcceptedOffsetsByHeight": {
                name: [counter_json(counter) for counter in counters]
                for name, counters in selector_offsets.items()
            },
        },
        "conclusions": {
            "derivativeIsDirectCoefficient": (
                all(
                    count == coefficient_count_per_height
                    for count in derivative_accepts_pulls
                )
                and all(
                    count == coefficient_count_per_height
                    for count in derivative_pair_equal_by_height
                )
            ),
            "selectorLawEstablished": False,
            "endToEndLiquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--selector-radius", type=int, default=16)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = analyze(arguments.root, selector_radius=arguments.selector_radius)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(rendered, end="")
    else:
        arguments.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
