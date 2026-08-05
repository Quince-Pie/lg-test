#!/usr/bin/env python3
"""Ablate coefficient and constant inputs for schema-4 P36 residuals."""

import argparse
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

import explore_raster_tile_center_p36 as p36
import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v8 as v8
import validate_raster_tile_phase_holdout as capture


TARGET_ENDPOINTS = {
    "opened-512-x",
    "opened-512-y",
    "opened-640-x",
    "opened-640-y",
    "opened-896-x",
    "opened-896-y",
}


def fixed_product_fraction(
    capture_case: object,
    endpoint: object,
    axis: int,
    selector_table: tuple[int, ...],
    *,
    first_output_bits: int,
    second_output_bits: int,
) -> Fraction:
    delta = v1.bits_float32(endpoint.highBits) - v1.bits_float32(endpoint.lowBits)
    sign = -1 if delta < 0 else 1
    opposite = capture_case.height if axis == 0 else capture_case.width
    determinant = capture_case.width * capture_case.height
    delta_significand, delta_exponent = v1.float_significand_and_lsb_exponent(
        v1.float32_bits(v1.float32(abs(delta)))
    )
    edge_significand, edge_exponent = v1.float_significand_and_lsb_exponent(
        v1.float32_bits(float(opposite))
    )
    numerator_index, numerator_exponent = v1.product_stage(
        delta_significand,
        delta_exponent,
        edge_significand,
        edge_exponent,
        output_bits=first_output_bits,
        truncation_bits=v1.FIRST_STAGE_TRUNCATION_BITS,
        bias_units=v1.FIRST_STAGE_BIAS_UNITS,
    )
    coefficient_index, coefficient_exponent = v1.product_stage(
        numerator_index,
        numerator_exponent,
        v1.reciprocal_selector(determinant, selector_table),
        -(determinant - 1).bit_length() - 24,
        output_bits=second_output_bits,
        truncation_bits=v1.SECOND_STAGE_TRUNCATION_BITS,
        bias_units=v1.SECOND_STAGE_BIAS_UNITS,
    )
    return sign * coefficient_index * v1.power_of_two(coefficient_exponent)


def output_pair(
    sample: object,
    slope: Fraction,
    constant: Fraction,
    fallback_step: Fraction,
    *,
    precision_bits: int = p36.CENTER_PRECISION_BITS,
) -> tuple[int, int]:
    step = (
        v1.power_of_two(
            v1.floor_binary_exponent(abs(constant)) - precision_bits + 1
        )
        if constant
        else fallback_step
    )
    coordinate = sample.x if sample.axis == 0 else sample.y
    local_pixel = coordinate - sample.tile * capture.TILE_SIZE
    left, right = p36.quad_center_pair(
        local_pixel,
        slope,
        constant,
        step,
        base_rounding="floor",
    )
    return (
        right if local_pixel & 1 else left,
        p36.derivative_bits(left, right),
    )


def analyze(root: Path) -> dict[str, object]:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    raw = (root / manifest["rasterTileNumerator"]["file"]).read_bytes()
    selector_table = v1.load_selector_table()
    counters: dict[str, Counter[str]] = {}
    records = 0

    for case_index, capture_case in enumerate(capture.CASES):
        for endpoint_index, endpoint in enumerate(capture.ENDPOINTS):
            if endpoint.name not in TARGET_ENDPOINTS:
                continue
            for sample in capture.sample_positions(capture_case):
                record_index = (
                    case_index * len(capture.ENDPOINTS) + endpoint_index
                ) * capture.SLOT_COUNT + sample.slot
                actual = capture.RECORD.unpack_from(
                    raw,
                    record_index * capture.RECORD.size,
                )
                if actual == capture.SENTINEL:
                    continue
                records += 1
                axis = sample.axis
                determinant_float = v8.determinant_slope(
                    capture_case,
                    endpoint,
                    axis=axis,
                    selector_table=selector_table,
                )
                _, _, determinant_internal_float = v4.determinant_slope(
                    capture_case,
                    endpoint,
                    axis=axis,
                    selector_table=selector_table,
                )
                phase_float = v2.selected_slope(
                    capture_case,
                    endpoint,
                    axis=axis,
                    selector_table=selector_table,
                )[1]
                legacy_float = v1.selected_slope(
                    capture_case,
                    endpoint,
                    axis=axis,
                    selector_table=selector_table,
                )[1]
                extent = capture_case.width if axis == 0 else capture_case.height
                exact = (
                    v1.float32_bits_fraction(endpoint.highBits)
                    - v1.float32_bits_fraction(endpoint.lowBits)
                ) / extent
                slopes = {
                    "determinant-f32": v1.float32_bits_fraction(
                        v1.float32_bits(determinant_float)
                    ),
                    "determinant-internal": Fraction.from_float(
                        determinant_internal_float
                    ),
                    "phase-p27": Fraction.from_float(phase_float),
                    "phase-p27-f32": v1.float32_bits_fraction(
                        v1.float32_bits(phase_float)
                    ),
                    "legacy-p27": Fraction.from_float(legacy_float),
                    "legacy-p27-f32": v1.float32_bits_fraction(
                        v1.float32_bits(legacy_float)
                    ),
                    "exact-quotient": exact,
                    "exact-quotient-f32-nearest": v1.float32_bits_fraction(
                        v1.round_fraction_to_float32_bits(exact)
                    ),
                }
                physical_bits = v8.physical_constant_bits(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table=selector_table,
                )
                exact_tile_bits = v1.tile_constant_bits(
                    capture_case,
                    endpoint,
                    axis=axis,
                    tile=sample.tile,
                )
                raw_physical = v4.zero_physical_composite(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table=selector_table,
                )
                raw_p28_magnitude = v1.quantize_binary_significand(
                    abs(raw_physical),
                    v4.CONSTANT_INTERNAL_PRECISION_BITS,
                    rounding="nearest-even",
                )
                raw_p28 = (
                    -raw_p28_magnitude if raw_physical < 0 else raw_p28_magnitude
                )
                origin = (
                    capture_case.originX if axis == 0 else capture_case.originY
                )
                translated_exact = (
                    v1.float32_bits_fraction(endpoint.lowBits)
                    + (
                        v1.float32_bits_fraction(endpoint.highBits)
                        - v1.float32_bits_fraction(endpoint.lowBits)
                    )
                    * Fraction(
                        sample.tile * capture.TILE_SIZE - origin,
                        extent,
                    )
                )
                constants = {
                    "physical": v1.float32_bits_fraction(physical_bits),
                    "raw-physical": raw_physical,
                    "raw-p28": raw_p28,
                    "translated-exact": translated_exact,
                    "exact-tile": v1.float32_bits_fraction(exact_tile_bits),
                }
                fallback_step = p36.endpoint_step(endpoint)
                for slope_name, slope in slopes.items():
                    for constant_name, constant in constants.items():
                        name = f"{slope_name}+{constant_name}"
                        predicted_center, predicted_derivative = output_pair(
                            sample,
                            slope,
                            constant,
                            fallback_step,
                        )
                        counter = counters.setdefault(name, Counter())
                        counter["center"] += (
                            predicted_center != actual[capture.PULL_COUNT]
                        )
                        counter["derivative"] += (
                            predicted_derivative
                            != actual[capture.PULL_COUNT + 1]
                        )
                for precision_bits in range(24, 49):
                    name = f"determinant-f32+physical+p{precision_bits}"
                    predicted_center, predicted_derivative = output_pair(
                        sample,
                        slopes["determinant-f32"],
                        constants["physical"],
                        v1.power_of_two(
                            v1.floor_binary_exponent(
                                max(
                                    abs(v1.float32_bits_fraction(endpoint.lowBits)),
                                    abs(v1.float32_bits_fraction(endpoint.highBits)),
                                )
                            )
                            - precision_bits
                            + 1
                        ),
                        precision_bits=precision_bits,
                    )
                    counter = counters.setdefault(name, Counter())
                    counter["center"] += (
                        predicted_center != actual[capture.PULL_COUNT]
                    )
                    counter["derivative"] += (
                        predicted_derivative
                        != actual[capture.PULL_COUNT + 1]
                    )
                for slope_precision_bits in range(24, 49):
                    for slope_rounding in ("down", "nearest-even", "up"):
                        quantized_slope = v1.quantize_binary_significand(
                            abs(exact),
                            slope_precision_bits,
                            rounding=slope_rounding,
                        )
                        if exact < 0:
                            quantized_slope = -quantized_slope
                        name = (
                            f"exact-p{slope_precision_bits}-{slope_rounding}"
                            "+physical"
                        )
                        predicted_center, predicted_derivative = output_pair(
                            sample,
                            quantized_slope,
                            constants["physical"],
                            fallback_step,
                        )
                        counter = counters.setdefault(name, Counter())
                        counter["center"] += (
                            predicted_center != actual[capture.PULL_COUNT]
                        )
                        counter["derivative"] += (
                            predicted_derivative
                            != actual[capture.PULL_COUNT + 1]
                        )
                for second_output_bits in range(24, 45):
                    fixed_slope = fixed_product_fraction(
                        capture_case,
                        endpoint,
                        axis,
                        selector_table,
                        first_output_bits=v1.FIRST_STAGE_OUTPUT_BITS,
                        second_output_bits=second_output_bits,
                    )
                    name = f"fixed-p27-p{second_output_bits}+physical"
                    predicted_center, predicted_derivative = output_pair(
                        sample,
                        fixed_slope,
                        constants["physical"],
                        fallback_step,
                    )
                    counter = counters.setdefault(name, Counter())
                    counter["center"] += (
                        predicted_center != actual[capture.PULL_COUNT]
                    )
                    counter["derivative"] += (
                        predicted_derivative
                        != actual[capture.PULL_COUNT + 1]
                    )
                for first_output_bits in range(24, 37):
                    fixed_slope = fixed_product_fraction(
                        capture_case,
                        endpoint,
                        axis,
                        selector_table,
                        first_output_bits=first_output_bits,
                        second_output_bits=36,
                    )
                    name = f"fixed-p{first_output_bits}-p36+physical"
                    predicted_center, predicted_derivative = output_pair(
                        sample,
                        fixed_slope,
                        constants["physical"],
                        fallback_step,
                    )
                    counter = counters.setdefault(name, Counter())
                    counter["center"] += (
                        predicted_center != actual[capture.PULL_COUNT]
                    )
                    counter["derivative"] += (
                        predicted_derivative
                        != actual[capture.PULL_COUNT + 1]
                    )

    return {
        "recordCount": records,
        "targetEndpoints": sorted(TARGET_ENDPOINTS),
        "candidates": {
            name: {
                "centerMismatchCount": counter["center"],
                "derivativeMismatchCount": counter["derivative"],
                "totalMismatchCount": counter["center"] + counter["derivative"],
            }
            for name, counter in sorted(
                counters.items(),
                key=lambda item: (
                    item[1]["center"] + item[1]["derivative"],
                    item[0],
                ),
            )
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(analyze(arguments.root), indent=2))


if __name__ == "__main__":
    main()
