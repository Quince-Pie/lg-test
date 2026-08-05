#!/usr/bin/env python3
"""Test explicit constant-rounding pipelines on schema-4 broad centers."""

import argparse
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

import explore_raster_tile_center_p36 as p36
import raster_tile_selector_model as v1
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


def round_to_float32_bits(value: Fraction, mode: str) -> int:
    if value == 0:
        return 0
    if value < 0:
        raise ValueError("this schema-4 target matrix should remain positive")
    exponent = v1.floor_binary_exponent(value)
    step = v1.power_of_two(exponent - 23)
    scaled = value / step
    quotient, remainder = divmod(scaled.numerator, scaled.denominator)
    doubled = 2 * remainder
    if mode == "nearest-even":
        quotient += doubled > scaled.denominator or (
            doubled == scaled.denominator and bool(quotient & 1)
        )
    elif mode == "nearest-odd":
        quotient += doubled > scaled.denominator or (
            doubled == scaled.denominator and not bool(quotient & 1)
        )
    elif mode == "up":
        quotient += bool(remainder)
    elif mode != "down":
        raise ValueError(mode)
    return v1.round_fraction_to_float32_bits(quotient * step)


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


def analyze(root: Path) -> dict[str, object]:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    raw = (root / manifest["rasterTileNumerator"]["file"]).read_bytes()
    selector_table = v1.load_selector_table()
    counters: dict[str, Counter[str]] = {}
    records = 0

    for case_index, capture_case in enumerate(capture.CASES):
        samples = capture.sample_positions(capture_case)
        for endpoint_index, endpoint in enumerate(capture.ENDPOINTS):
            if endpoint.name not in TARGET_ENDPOINTS:
                continue
            slopes = {
                axis: v1.float32_bits_fraction(
                    v1.float32_bits(
                        v8.determinant_slope(
                            capture_case,
                            endpoint,
                            axis=axis,
                            selector_table=selector_table,
                        )
                    )
                )
                for axis in range(capture.AXIS_COUNT)
            }
            anchor_samples: dict[tuple[int, int, str], object] = {}
            for axis in range(capture.AXIS_COUNT):
                for primitive in range(capture.PRIMITIVE_COUNT):
                    candidates = [
                        sample
                        for sample in samples
                        if sample.axis == axis and sample.primitive == primitive
                    ]
                    if not candidates:
                        continue
                    first = min(candidates, key=lambda sample: sample.tile)
                    last = max(candidates, key=lambda sample: sample.tile)
                    anchor_samples[(axis, primitive, "first")] = first
                    anchor_samples[(axis, primitive, "last")] = last
                    anchor_samples[(axis, primitive, "primitive")] = (
                        last if axis == 0 and primitive == 0 else first
                    )
            constants: dict[tuple[int, int, int], dict[str, Fraction]] = {}
            for sample in samples:
                actual = record_at(raw, case_index, endpoint_index, sample)
                if actual == capture.SENTINEL:
                    continue
                records += 1
                key = (sample.axis, sample.primitive, sample.tile)
                if key not in constants:
                    raw_constant = v4.zero_physical_composite(
                        capture_case,
                        endpoint,
                        sample,
                        selector_table=selector_table,
                    )
                    variants: dict[str, Fraction] = {}
                    for internal_mode in ("down", "nearest-even", "up"):
                        magnitude = v1.quantize_binary_significand(
                            abs(raw_constant),
                            v4.CONSTANT_INTERNAL_PRECISION_BITS,
                            rounding=internal_mode,
                        )
                        internal = -magnitude if raw_constant < 0 else magnitude
                        for output_mode in (
                            "down",
                            "nearest-even",
                            "nearest-odd",
                            "up",
                        ):
                            bits = round_to_float32_bits(internal, output_mode)
                            variants[
                                f"p28-{internal_mode}-f32-{output_mode}"
                            ] = v1.float32_bits_fraction(bits)
                    for output_mode in (
                        "down",
                        "nearest-even",
                        "nearest-odd",
                        "up",
                    ):
                        bits = round_to_float32_bits(raw_constant, output_mode)
                        variants[f"raw-f32-{output_mode}"] = (
                            v1.float32_bits_fraction(bits)
                        )
                    p28_magnitude = v1.quantize_binary_significand(
                        abs(raw_constant),
                        v4.CONSTANT_INTERNAL_PRECISION_BITS,
                        rounding="nearest-even",
                    )
                    p28_constant = (
                        -p28_magnitude if raw_constant < 0 else p28_magnitude
                    )
                    physical_bits = v8.physical_constant_bits(
                        capture_case,
                        endpoint,
                        sample,
                        selector_table=selector_table,
                    )
                    physical = v1.float32_bits_fraction(physical_bits)
                    for source_name, source in (
                        ("raw", raw_constant),
                        ("p28", p28_constant),
                    ):
                        residual = source - physical
                        direction = (residual > 0) - (residual < 0)
                        neighbor_bits = physical_bits + direction
                        neighbor = v1.float32_bits_fraction(neighbor_bits)
                        phase = (
                            abs(residual / (neighbor - physical))
                            if direction
                            else Fraction(0)
                        )
                        for threshold_numerator in range(17):
                            threshold = Fraction(threshold_numerator, 16)
                            selected_bits = (
                                neighbor_bits
                                if direction and phase >= threshold
                                else physical_bits
                            )
                            variants[
                                f"physical-neighbor-{source_name}-phase-ge-"
                                f"{threshold_numerator:02d}/16"
                            ] = v1.float32_bits_fraction(selected_bits)
                    axis = sample.axis
                    extent = (
                        capture_case.width if axis == 0 else capture_case.height
                    )
                    origin = (
                        capture_case.originX
                        if axis == 0
                        else capture_case.originY
                    )
                    if axis == 0 and sample.primitive == 0:
                        anchor = v1.float32_bits_fraction(endpoint.highBits)
                        anchor_position = origin + extent
                    else:
                        anchor = v1.float32_bits_fraction(endpoint.lowBits)
                        anchor_position = origin
                    displacement = (
                        sample.tile * capture.TILE_SIZE - anchor_position
                    )
                    coherent = anchor + displacement * slopes[axis]
                    variants["coherent-exact"] = coherent
                    for output_mode in (
                        "down",
                        "nearest-even",
                        "nearest-odd",
                        "up",
                    ):
                        bits = round_to_float32_bits(coherent, output_mode)
                        variants[f"coherent-f32-{output_mode}"] = (
                            v1.float32_bits_fraction(bits)
                        )
                    for precision_bits in (28, 32, 36):
                        for internal_mode in ("down", "nearest-even", "up"):
                            magnitude = v1.quantize_binary_significand(
                                abs(coherent),
                                precision_bits,
                                rounding=internal_mode,
                            )
                            internal = -magnitude if coherent < 0 else magnitude
                            variants[
                                f"coherent-p{precision_bits}-{internal_mode}"
                            ] = internal
                    for anchor_name in ("first", "last", "primitive"):
                        anchor_sample = anchor_samples[
                            (axis, sample.primitive, anchor_name)
                        ]
                        anchor_bits = v8.physical_constant_bits(
                            capture_case,
                            endpoint,
                            anchor_sample,
                            selector_table=selector_table,
                        )
                        anchor_constant = v1.float32_bits_fraction(anchor_bits)
                        propagated = anchor_constant + (
                            sample.tile - anchor_sample.tile
                        ) * capture.TILE_SIZE * slopes[axis]
                        variants[f"propagate-{anchor_name}-exact"] = propagated
                        for output_mode in (
                            "down",
                            "nearest-even",
                            "nearest-odd",
                            "up",
                        ):
                            bits = round_to_float32_bits(propagated, output_mode)
                            variants[
                                f"propagate-{anchor_name}-f32-{output_mode}"
                            ] = v1.float32_bits_fraction(bits)
                        for precision_bits in (28, 32, 36):
                            for internal_mode in (
                                "down",
                                "nearest-even",
                                "up",
                            ):
                                magnitude = v1.quantize_binary_significand(
                                    abs(propagated),
                                    precision_bits,
                                    rounding=internal_mode,
                                )
                                internal = (
                                    -magnitude if propagated < 0 else magnitude
                                )
                                variants[
                                    f"propagate-{anchor_name}-p{precision_bits}-"
                                    f"{internal_mode}"
                                ] = internal
                    constants[key] = variants

                slope = slopes[sample.axis]
                coordinate = sample.x if sample.axis == 0 else sample.y
                local_pixel = coordinate - sample.tile * capture.TILE_SIZE
                fallback_step = p36.endpoint_step(endpoint)
                for name, constant in constants[key].items():
                    step = p36.significand_step(constant, fallback_step)
                    left, right = p36.quad_center_pair(
                        local_pixel,
                        slope,
                        constant,
                        step,
                        base_rounding="floor",
                    )
                    predicted_center = right if local_pixel & 1 else left
                    predicted_derivative = p36.derivative_bits(left, right)
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
