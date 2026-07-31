#!/usr/bin/env python3
"""Test numerator precision laws against general-height raster evidence."""

import argparse
import json
import math
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

import analyze_raster_general_height_diagnostic as analyzer
import explore_general_height as arithmetic
import recover_raster_general_height_slopes as recovery
import validate_raster_general_height_diagnostic as diagnostic


type JsonObject = dict[str, Any]
type ProductPredictor = Callable[[int, int, int], int]


def rounded_shift(value: int, shift: int, mode: str) -> int:
    if shift <= 0:
        return value
    quotient, remainder = divmod(value, 1 << shift)
    if mode == "nearest":
        half = 1 << (shift - 1)
        quotient += remainder > half or (remainder == half and quotient & 1)
    elif mode == "ceil":
        quotient += remainder != 0
    elif mode != "floor":
        raise ValueError(f"unknown rounding mode: {mode}")
    return quotient


def numerator_model(
    significand: int,
    lsb_exponent: int,
    height: int,
    precision: int | None,
    rounding: str,
) -> tuple[int, int]:
    product = significand * height
    if precision is None:
        return product, lsb_exponent
    shift = max(0, product.bit_length() - precision)
    return rounded_shift(product, shift, rounding), lsb_exponent + shift


def physical_numerator_model(
    significand: int,
    lsb_exponent: int,
    height: int,
    *,
    swapped: bool,
) -> tuple[int, int]:
    height_bits = diagnostic.arithmetic.float32_bits(float(height))
    height_significand, height_lsb = arithmetic.float_significand_and_lsb_exponent(
        height_bits
    )
    if swapped:
        bits = arithmetic.physical_product_with_exponent(
            height_significand,
            height_lsb,
            significand,
            lsb_exponent + 24,
        )
    else:
        bits = arithmetic.physical_product_with_exponent(
            significand,
            lsb_exponent,
            height_significand,
            height_lsb + 24,
        )
    return arithmetic.float_significand_and_lsb_exponent(bits)


def clip_numerator_model(
    significand: int,
    lsb_exponent: int,
    height: int,
    origin_y: int,
    *,
    operation: str,
) -> tuple[int, int]:
    def f32(value: float) -> float:
        return diagnostic.arithmetic.float32_value(
            diagnostic.arithmetic.float32_bits(value)
        )

    delta = math.ldexp(significand, lsb_exponent)
    scale = f32(-2.0 / diagnostic.TARGET_HEIGHT)
    top = f32(math.fma(float(origin_y), scale, 1.0))
    bottom = f32(math.fma(float(origin_y + height), scale, 1.0))
    top_product = f32(delta * top)
    bottom_product = f32(delta * bottom)
    if operation == "separate":
        difference = f32(top_product - bottom_product)
    elif operation == "fmaTop":
        difference = f32(math.fma(delta, top, -bottom_product))
    elif operation == "fmaBottom":
        difference = f32(math.fma(-delta, bottom, top_product))
    else:
        raise ValueError(f"unknown clip numerator operation: {operation}")
    scaled = f32(abs(difference) * (diagnostic.TARGET_HEIGHT / 2))
    return arithmetic.float_significand_and_lsb_exponent(
        diagnostic.arithmetic.float32_bits(scaled)
    )


def edge_factorized_product_bits(
    significand: int,
    lsb_exponent: int,
    height: int,
    area: int,
    reciprocal: int,
    *,
    precision: int | None,
    rounding: str,
) -> int:
    edge_product = height * reciprocal
    shift = 0 if precision is None else max(0, edge_product.bit_length() - precision)
    effective_reciprocal = rounded_shift(edge_product, shift, rounding)
    reciprocal_exponent = -(area - 1).bit_length() + shift
    return arithmetic.physical_product_with_exponent(
        significand,
        lsb_exponent,
        effective_reciprocal,
        reciprocal_exponent,
    )


def inverse_reciprocal_candidates(
    numerators: list[tuple[int, int]],
    accepted_slopes: list[set[int]],
    predictor: ProductPredictor,
) -> list[int]:
    def first_at_least(
        target: int,
        significand: int,
        lsb_exponent: int,
    ) -> int:
        lower = 1 << 24
        upper = 1 << 25
        while lower < upper:
            middle = (lower + upper) // 2
            if predictor(significand, lsb_exponent, middle) < target:
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
            predictor(significand, lsb_exponent, reciprocal) in slopes
            for (significand, lsb_exponent), slopes in zip(
                numerators,
                accepted_slopes,
                strict=True,
            )
        )
    ]


def accepted_slopes(
    records: np.ndarray,
    *,
    width: int,
    width_index: int,
    witness_index: int,
    geometry_index: int,
    direct_bits: int,
    radius: int,
    require_derivative: bool,
) -> set[int]:
    positions = [
        float(
            diagnostic.sample_position(
                width,
                diagnostic.failed_general.GEOMETRY_CASES[geometry_index],
                side,
            )["tileLocalX"]
        )
        for side in range(diagnostic.SAMPLE_SIDE_COUNT)
    ]
    selected = records[width_index, witness_index, geometry_index]
    pulls = [
        observation
        for side, position in enumerate(positions)
        for observation in (
            (position, int(selected[side, 0])),
            (position + 0.9375, int(selected[side, 1])),
        )
    ]
    centers = [
        (position + 0.5, int(selected[side, 2]))
        for side, position in enumerate(positions)
    ]
    derivatives = [
        (position + 0.5, int(selected[side, 3]))
        for side, position in enumerate(positions)
    ]
    accepted: set[int] = set()
    for offset in range(-radius, radius + 1):
        slope_bits = direct_bits + offset
        constants = analyzer.shared_iterator_constant_bits(
            slope_bits,
            pull_observations=pulls,
            center_observations=centers,
        )
        if constants and not require_derivative:
            accepted.add(slope_bits)
            continue
        slope = diagnostic.arithmetic.float32_value(slope_bits)
        if any(
            all(
                analyzer.derivative_bits(position, slope, constant) == expected
                for position, expected in derivatives
            )
            for constant in map(diagnostic.arithmetic.float32_value, constants)
        ):
            accepted.add(slope_bits)
    return accepted


def explore(
    root: Path,
    *,
    width_stride: int,
    slope_radius: int,
    selector_radius: int,
    require_derivative: bool,
) -> JsonObject:
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
    width_indices = sorted(
        {
            *range(0, len(widths), width_stride),
            len(widths) - 1,
        }
    )
    models: dict[str, tuple[str, int | None, str]] = {
        "exact": ("quantized", None, "exact"),
        "physicalDeltaHeight": ("physical", None, "ordered"),
        "physicalHeightDelta": ("physical", None, "swapped"),
        "clipSeparate": ("clip", None, "separate"),
        "clipFmaTop": ("clip", None, "fmaTop"),
        "clipFmaBottom": ("clip", None, "fmaBottom"),
    }
    for precision in range(24, 33):
        for rounding in ("floor", "nearest", "ceil"):
            models[f"p{precision}_{rounding}"] = (
                "quantized",
                precision,
                rounding,
            )
    models["edgeExact"] = ("edge", None, "exact")
    for precision in range(24, 33):
        for rounding in ("floor", "nearest", "ceil"):
            models[f"edgeP{precision}_{rounding}"] = (
                "edge",
                precision,
                rounding,
            )
    multiplicity = {
        name: [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)] for name in models
    }
    offsets = {
        name: [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)] for name in models
    }
    model_signatures = [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)]
    determinant_records: list[JsonObject] = []
    inverse_multiplicity = {
        name: [Counter() for _ in range(diagnostic.GEOMETRY_COUNT)]
        for name in (
            "exact",
            "p27_ceil",
            "p28_ceil",
            "p29_ceil",
            "edgeP27_ceil",
            "edgeP28_ceil",
            "edgeP29_ceil",
        )
    }

    for width_index in width_indices:
        width = widths[width_index]
        inputs: list[tuple[int, int]] = []
        accepted_by_geometry: list[list[set[int]]] = [
            [] for _ in range(diagnostic.GEOMETRY_COUNT)
        ]
        for witness_index, original_bits in enumerate(delta_bits):
            scaled_bits = original_bits - shifts[width_index]
            inputs.append(arithmetic.float_significand_and_lsb_exponent(scaled_bits))
            scaled_value = diagnostic.arithmetic.float32_value(scaled_bits)
            direct_bits = diagnostic.arithmetic.float32_bits(scaled_value / width)
            for geometry_index in range(diagnostic.GEOMETRY_COUNT):
                accepted_by_geometry[geometry_index].append(
                    accepted_slopes(
                        records,
                        width=width,
                        width_index=width_index,
                        witness_index=witness_index,
                        geometry_index=geometry_index,
                        direct_bits=direct_bits,
                        radius=slope_radius,
                        require_derivative=require_derivative,
                    )
                )

        for geometry_index, geometry in enumerate(
            diagnostic.failed_general.GEOMETRY_CASES
        ):
            height = int(geometry["height"])
            area = width * height
            nearest = diagnostic.arithmetic.nearest_even_reciprocal_index(area)
            matching_models: list[str] = []
            for name, (kind, precision, rounding) in models.items():
                if kind == "physical":
                    numerators = [
                        physical_numerator_model(
                            significand,
                            lsb_exponent,
                            height,
                            swapped=rounding == "swapped",
                        )
                        for significand, lsb_exponent in inputs
                    ]
                elif kind == "clip":
                    numerators = [
                        clip_numerator_model(
                            significand,
                            lsb_exponent,
                            height,
                            int(geometry["originY"]),
                            operation=rounding,
                        )
                        for significand, lsb_exponent in inputs
                    ]
                elif kind == "edge":
                    numerators = inputs
                else:
                    numerators = [
                        numerator_model(
                            significand,
                            lsb_exponent,
                            height,
                            precision,
                            rounding,
                        )
                        for significand, lsb_exponent in inputs
                    ]
                matching: list[int] = []
                for offset in range(-selector_radius, selector_radius + 1):
                    reciprocal = nearest + offset
                    if all(
                        (
                            edge_factorized_product_bits(
                                significand,
                                lsb_exponent,
                                height,
                                area,
                                reciprocal,
                                precision=precision,
                                rounding=rounding,
                            )
                            if kind == "edge"
                            else arithmetic.generalized_physical_product_bits(
                                significand,
                                lsb_exponent,
                                area,
                                reciprocal,
                            )
                        )
                        in accepted
                        for (significand, lsb_exponent), accepted in zip(
                            numerators,
                            accepted_by_geometry[geometry_index],
                            strict=True,
                        )
                    ):
                        matching.append(offset)
                multiplicity[name][geometry_index][len(matching)] += 1
                for offset in matching:
                    offsets[name][geometry_index][offset] += 1
                if matching:
                    matching_models.append(name)
                if name in inverse_multiplicity:
                    if kind == "edge":
                        inverse = inverse_reciprocal_candidates(
                            numerators,
                            accepted_by_geometry[geometry_index],
                            lambda significand, lsb_exponent, reciprocal: (
                                edge_factorized_product_bits(
                                    significand,
                                    lsb_exponent,
                                    height,
                                    area,
                                    reciprocal,
                                    precision=precision,
                                    rounding=rounding,
                                )
                            ),
                        )
                    else:
                        inverse = recovery.reciprocal_candidates(
                            numerators=numerators,
                            denominator=area,
                            accepted_slopes=accepted_by_geometry[geometry_index],
                            exact_height=None,
                        )
                    inverse_multiplicity[name][geometry_index][len(inverse)] += 1
            model_signatures[geometry_index][tuple(matching_models)] += 1
            determinant_records.append(
                {
                    "width": width,
                    "height": height,
                    "area": area,
                    "areaBitLength": area.bit_length(),
                    "areaLow16": area & 0xFFFF,
                    "matchingModels": matching_models,
                }
            )

    return {
        "liquidGlassRasterGeneralHeightNumeratorPrecisionSchemaVersion": 1,
        "probe": str(root),
        "ciCommit": manifest.get("ciCommit"),
        "manifestSha256": diagnostic.sha256_path(root / "manifest.json"),
        "rawSha256": diagnostic.sha256_path(raw_path),
        "measurement": {
            "widthStride": width_stride,
            "widthCount": len(width_indices),
            "widths": [widths[index] for index in width_indices],
            "slopeCandidateRadiusFloatUlps": slope_radius,
            "selectorRadiusInternalUlps": selector_radius,
            "derivativeConstraintRequired": require_derivative,
            "selectorMultiplicityByHeight": {
                name: [
                    {str(key): value for key, value in sorted(counter.items())}
                    for counter in counters
                ]
                for name, counters in multiplicity.items()
            },
            "selectorAcceptedOffsetsByHeight": {
                name: [
                    {str(key): value for key, value in sorted(counter.items())}
                    for counter in counters
                ]
                for name, counters in offsets.items()
            },
            "modelSignatureByHeight": [
                [
                    {
                        "models": list(signature),
                        "count": count,
                    }
                    for signature, count in sorted(
                        counter.items(),
                        key=lambda item: (-item[1], item[0]),
                    )
                ]
                for counter in model_signatures
            ],
            "inverseSelectorMultiplicityByHeight": {
                name: [
                    {str(key): value for key, value in sorted(counter.items())}
                    for counter in counters
                ]
                for name, counters in inverse_multiplicity.items()
            },
            "determinants": determinant_records,
        },
        "conclusions": {
            "numeratorLawEstablished": False,
            "selectorLawEstablished": False,
            "endToEndLiquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--width-stride", type=int, default=32)
    parser.add_argument("--slope-radius", type=int, default=2)
    parser.add_argument("--selector-radius", type=int, default=8)
    parser.add_argument("--ignore-derivative", action="store_true")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = explore(
        arguments.root,
        width_stride=arguments.width_stride,
        slope_radius=arguments.slope_radius,
        selector_radius=arguments.selector_radius,
        require_derivative=not arguments.ignore_derivative,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(rendered, end="")
    else:
        arguments.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
