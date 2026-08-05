#!/usr/bin/env python3
"""Compare input-only first-tile constant paths for schema-12 centers."""

import argparse
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

import explore_raster_tile_center_p36 as p36
import raster_tile_selector_model as v1
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v8 as v8
import validate_raster_tile_center_extent_tomography as capture


def quantize_to_step(value: Fraction, step: Fraction, mode: str) -> Fraction:
    scaled = value / step
    floor_index, remainder = divmod(scaled.numerator, scaled.denominator)
    if mode == "floor":
        index = floor_index
    elif mode == "nearest-even":
        index = v1.round_fraction_to_integer_nearest_even(scaled)
    elif mode == "ceil":
        index = floor_index + bool(remainder)
    else:
        raise ValueError(mode)
    return index * step


def center(
    local_pixel: int,
    slope: Fraction,
    constant: Fraction,
    step: Fraction,
    *,
    rounding: str = "floor",
) -> int:
    left, right = p36.quad_center_pair(
        local_pixel,
        slope,
        constant,
        step,
        base_rounding=rounding,
    )
    return right if local_pixel & 1 else left


def significand_step(value: Fraction) -> Fraction:
    if value == 0:
        raise ValueError("a nonzero value is required for a significand step")
    return v1.power_of_two(
        v1.floor_binary_exponent(abs(value)) - p36.CENTER_PRECISION_BITS + 1
    )


def analyze(root: Path) -> dict[str, object]:
    capture.validate(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    raw = (root / manifest["rasterTileNumerator"]["file"]).read_bytes()
    selector_table = v1.load_selector_table()
    mismatches: Counter[str] = Counter()
    records = 0
    local31_records = 0

    for case_index, capture_case in enumerate(capture.CASES):
        samples = capture.sample_positions(capture_case)
        axis, extent, origin, _ = capture.effective_geometry(capture_case)
        first_tile = origin // capture.TILE_SIZE
        for endpoint_index, endpoint in enumerate(capture.ENDPOINTS):
            slope_float = v8.determinant_slope(
                capture_case,
                endpoint,
                axis=axis,
                selector_table=selector_table,
            )
            slope = v1.float32_bits_fraction(v1.float32_bits(slope_float))
            _, _, internal_slope_float = v4.determinant_slope(
                capture_case,
                endpoint,
                axis=axis,
                selector_table=selector_table,
            )
            internal_slope = Fraction.from_float(internal_slope_float)
            step = p36.endpoint_step(endpoint)
            low = v1.float32_bits_fraction(endpoint.lowBits)
            high = v1.float32_bits_fraction(endpoint.highBits)
            exact_slope = (high - low) / extent
            translated = low + (high - low) * Fraction(
                first_tile * capture.TILE_SIZE - origin,
                extent,
            )
            for sample in samples:
                if sample.tile != first_tile:
                    continue
                records += 1
                coordinate = sample.x if axis == 0 else sample.y
                local_pixel = coordinate - first_tile * capture.TILE_SIZE
                local31_records += local_pixel == 31
                actual = p36.record_at(
                    raw,
                    case_index,
                    endpoint_index,
                    sample,
                )[capture.PULL_COUNT]
                f32_bits = v8.physical_constant_bits(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table=selector_table,
                )
                f32_constant = v1.float32_bits_fraction(f32_bits)
                raw_constant = v4.zero_physical_composite(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table=selector_table,
                )
                variants = {
                    "f32-floor": center(
                        local_pixel, slope, f32_constant, step
                    ),
                    "f32-ceil": center(
                        local_pixel,
                        slope,
                        f32_constant,
                        step,
                        rounding="ceil",
                    ),
                    "internal-slope-f32-constant": center(
                        local_pixel,
                        internal_slope,
                        f32_constant,
                        step,
                    ),
                    "exact-slope-f32-constant": center(
                        local_pixel,
                        exact_slope,
                        f32_constant,
                        step,
                    ),
                    "f32-floor-step-from-constant-binade": center(
                        local_pixel,
                        slope,
                        f32_constant,
                        (
                            significand_step(f32_constant)
                            if f32_constant
                            else step
                        ),
                    ),
                    "f32-floor-step-from-even-base-binade": center(
                        local_pixel,
                        slope,
                        f32_constant,
                        significand_step(
                            f32_constant
                            + Fraction(2 * (local_pixel & ~1) + 1, 2) * slope
                        ),
                    ),
                    "raw-exact-floor": center(
                        local_pixel, slope, raw_constant, step
                    ),
                    "raw-p36-floor": center(
                        local_pixel,
                        slope,
                        quantize_to_step(raw_constant, step, "floor"),
                        step,
                    ),
                    "raw-p36-nearest": center(
                        local_pixel,
                        slope,
                        quantize_to_step(raw_constant, step, "nearest-even"),
                        step,
                    ),
                    "translated-exact-floor": center(
                        local_pixel, slope, translated, step
                    ),
                    "translated-p36-floor": center(
                        local_pixel,
                        slope,
                        quantize_to_step(translated, step, "floor"),
                        step,
                    ),
                    "translated-p36-nearest": center(
                        local_pixel,
                        slope,
                        quantize_to_step(translated, step, "nearest-even"),
                        step,
                    ),
                    "f32-plus-one-if-raw-positive": center(
                        local_pixel,
                        slope,
                        f32_constant
                        + (step if raw_constant > f32_constant else 0),
                        step,
                    ),
                    "f32-plus-one-if-translated-positive": center(
                        local_pixel,
                        slope,
                        f32_constant + (step if translated > f32_constant else 0),
                        step,
                    ),
                    "raw-exact-local31-otherwise-f32": center(
                        local_pixel,
                        slope,
                        raw_constant if local_pixel == 31 else f32_constant,
                        step,
                    ),
                    "translated-exact-local31-otherwise-f32": center(
                        local_pixel,
                        slope,
                        translated if local_pixel == 31 else f32_constant,
                        step,
                    ),
                }
                for name, predicted in variants.items():
                    mismatches[name] += predicted != actual

    return {
        "firstTileRecords": records,
        "firstTileLocal31Records": local31_records,
        "centerMismatchCounts": dict(sorted(mismatches.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(analyze(arguments.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
