#!/usr/bin/env python3
"""Compose schema-4 broad endpoints from the measured P36 control weight."""

import argparse
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

import explore_raster_tile_center_p36 as p36
import raster_tile_selector_model as v1
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


def quantize(value: Fraction, precision_bits: int, rounding: str) -> Fraction:
    if value == 0:
        return value
    magnitude = v1.quantize_binary_significand(
        abs(value),
        precision_bits,
        rounding=rounding,
    )
    return -magnitude if value < 0 else magnitude


def control_pair(
    capture_case: object,
    control: object,
    sample: object,
    selector_table: tuple[int, ...],
) -> tuple[Fraction, Fraction]:
    slope_float = v8.determinant_slope(
        capture_case,
        control,
        axis=sample.axis,
        selector_table=selector_table,
    )
    slope = v1.float32_bits_fraction(v1.float32_bits(slope_float))
    constant_bits = v8.physical_constant_bits(
        capture_case,
        control,
        sample,
        selector_table=selector_table,
    )
    constant = v1.float32_bits_fraction(constant_bits)
    step = p36.significand_step(constant, p36.endpoint_step(control))
    coordinate = sample.x if sample.axis == 0 else sample.y
    local_pixel = coordinate - sample.tile * capture.TILE_SIZE
    quad_local = local_pixel & ~1
    exact_base = constant + Fraction(2 * quad_local + 1, 2) * slope
    base_index, _ = divmod(exact_base, step)
    left = base_index * step
    return left, left + slope


def composed_pair(
    low: Fraction,
    high: Fraction,
    left_weight: Fraction,
    right_weight: Fraction,
    policy: str,
) -> tuple[int, int]:
    def compose(weight: Fraction) -> int:
        if policy == "affine-exact":
            value = low + weight * (high - low)
        elif policy == "weight-f32-nearest":
            bits = v1.round_fraction_to_float32_bits(weight)
            value = low + v1.float32_bits_fraction(bits) * (high - low)
        elif policy == "weight-f32-toward-zero":
            bits = p36.toward_zero_float32_bits(weight)
            value = low + v1.float32_bits_fraction(bits) * (high - low)
        else:
            stem, precision_text, rounding = policy.split(":", maxsplit=2)
            precision_bits = int(precision_text)
            if stem == "separate":
                value = quantize(
                    (1 - weight) * low,
                    precision_bits,
                    rounding,
                ) + quantize(
                    weight * high,
                    precision_bits,
                    rounding,
                )
            elif stem == "affine-product":
                value = low + quantize(
                    weight * (high - low),
                    precision_bits,
                    rounding,
                )
            elif stem == "affine-final":
                value = quantize(
                    low + weight * (high - low),
                    precision_bits,
                    rounding,
                )
            else:
                raise ValueError(policy)
        return p36.toward_zero_float32_bits(value)

    return compose(left_weight), compose(right_weight)


def analyze(root: Path) -> dict[str, object]:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    raw = (root / manifest["rasterTileNumerator"]["file"]).read_bytes()
    selector_table = v1.load_selector_table()
    control = next(
        endpoint for endpoint in capture.ENDPOINTS if endpoint.name == "zero-to-one"
    )
    policies = [
        "affine-exact",
        "weight-f32-nearest",
        "weight-f32-toward-zero",
    ]
    for precision_bits in range(24, 41):
        for rounding in ("down", "nearest-even", "up"):
            policies.extend(
                (
                    f"separate:{precision_bits}:{rounding}",
                    f"affine-product:{precision_bits}:{rounding}",
                    f"affine-final:{precision_bits}:{rounding}",
                )
            )
    counters = {policy: Counter() for policy in policies}
    records = 0

    for case_index, capture_case in enumerate(capture.CASES):
        samples = capture.sample_positions(capture_case)
        weights = {
            (sample.axis, sample.primitive, sample.tile, sample.edge): control_pair(
                capture_case,
                control,
                sample,
                selector_table,
            )
            for sample in samples
        }
        for endpoint_index, endpoint in enumerate(capture.ENDPOINTS):
            if endpoint.name not in TARGET_ENDPOINTS:
                continue
            low = v1.float32_bits_fraction(endpoint.lowBits)
            high = v1.float32_bits_fraction(endpoint.highBits)
            for sample in samples:
                actual = record_at(raw, case_index, endpoint_index, sample)
                if actual == capture.SENTINEL:
                    continue
                records += 1
                key = (sample.axis, sample.primitive, sample.tile, sample.edge)
                left_weight, right_weight = weights[key]
                coordinate = sample.x if sample.axis == 0 else sample.y
                local_pixel = coordinate - sample.tile * capture.TILE_SIZE
                for policy in policies:
                    left, right = composed_pair(
                        low,
                        high,
                        left_weight,
                        right_weight,
                        policy,
                    )
                    predicted_center = right if local_pixel & 1 else left
                    predicted_derivative = p36.derivative_bits(left, right)
                    counter = counters[policy]
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
            policy: {
                "centerMismatchCount": counter["center"],
                "derivativeMismatchCount": counter["derivative"],
                "totalMismatchCount": counter["center"] + counter["derivative"],
            }
            for policy, counter in sorted(
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
