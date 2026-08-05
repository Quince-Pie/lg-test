#!/usr/bin/env python3
"""Explore the schema-12 36-bit quad-center evaluator without fitting outputs."""

import argparse
import json
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any

import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v8 as v8
import validate_raster_tile_center_extent_tomography as capture


type JsonObject = dict[str, Any]

CENTER_PRECISION_BITS = 36


def toward_zero_float32_bits(value: Fraction) -> int:
    """Round one normal rational toward zero to binary32."""

    if value == 0:
        return 0
    bits = v1.round_fraction_to_float32_bits(value)
    rounded = v1.float32_bits_fraction(bits)
    if (value > 0 and rounded > value) or (value < 0 and rounded < value):
        bits -= 1
    return bits


def endpoint_step(endpoint: object) -> Fraction:
    low = abs(v1.float32_bits_fraction(endpoint.lowBits))
    high = abs(v1.float32_bits_fraction(endpoint.highBits))
    scale = max(low, high)
    return v1.power_of_two(
        v1.floor_binary_exponent(scale) - CENTER_PRECISION_BITS + 1
    )


def significand_step(value: Fraction, fallback: Fraction) -> Fraction:
    """Return the 36-significand-bit step for a tile-start constant."""

    if value == 0:
        return fallback
    return v1.power_of_two(
        v1.floor_binary_exponent(abs(value)) - CENTER_PRECISION_BITS + 1
    )


def quad_center_pair(
    local_pixel: int,
    slope: Fraction,
    constant: Fraction,
    step: Fraction,
    *,
    base_rounding: str = "floor",
) -> tuple[int, int]:
    quad_local = local_pixel & ~1
    exact_base = constant + Fraction(2 * quad_local + 1, 2) * slope
    floor_index, remainder = divmod(exact_base, step)
    if base_rounding == "ceil":
        index = floor_index + bool(remainder)
    elif base_rounding == "floor":
        index = floor_index
    else:
        raise ValueError(f"unknown base rounding: {base_rounding}")
    left = index * step
    right = left + slope
    return toward_zero_float32_bits(left), toward_zero_float32_bits(right)


def derivative_bits(left_bits: int, right_bits: int) -> int:
    return v1.float32_bits(
        v1.float32(v1.bits_float32(right_bits) - v1.bits_float32(left_bits))
    )


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


def analyze(root: Path) -> JsonObject:
    capture.validate(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    raw_path = root / manifest["rasterTileNumerator"]["file"]
    raw = raw_path.read_bytes()
    selector_table = v1.load_selector_table()

    pull_word_mismatches = 0
    pull_record_mismatches = 0
    center_floor_mismatches = 0
    center_ceil_mismatches = 0
    derivative_floor_mismatches = 0
    center_normalized_mismatches = 0
    derivative_normalized_mismatches = 0
    actual_derivative_from_actual_centers_mismatches = 0
    center_actual_equals_pull8 = 0
    center_actual_equals_pull8_minus_one = 0
    center_actual_other = 0
    records = 0
    mismatch_examples: list[JsonObject] = []
    discriminating_rows: list[JsonObject] = []
    action_counts: Counter[str] = Counter()
    action_by_extent: Counter[str] = Counter()
    setup_actions: dict[tuple[str, str, int, int], Counter[str]] = defaultdict(Counter)

    for case_index, capture_case in enumerate(capture.CASES):
        samples = capture.sample_positions(capture_case)
        axis, extent, origin, _ = capture.effective_geometry(capture_case)
        for endpoint_index, endpoint in enumerate(capture.ENDPOINTS):
            slope_float = v8.determinant_slope(
                capture_case,
                endpoint,
                axis=axis,
                selector_table=selector_table,
            )
            slope_bits = v1.float32_bits(slope_float)
            slope = v1.float32_bits_fraction(slope_bits)
            step = endpoint_step(endpoint)
            constants: dict[tuple[int, int], tuple[int, Fraction, Fraction]] = {}
            for sample in samples:
                records += 1
                actual = record_at(raw, case_index, endpoint_index, sample)
                constant_key = (sample.primitive, sample.tile)
                if constant_key not in constants:
                    constant_bits = v8.physical_constant_bits(
                        capture_case,
                        endpoint,
                        sample,
                        selector_table=selector_table,
                    )
                    constant = v1.float32_bits_fraction(constant_bits)
                    raw_constant = v4.zero_physical_composite(
                        capture_case,
                        endpoint,
                        sample,
                        selector_table=selector_table,
                    )
                    constants[constant_key] = (
                        constant_bits,
                        constant,
                        raw_constant,
                    )
                constant_bits, constant, raw_constant = constants[constant_key]
                constant_float = v1.bits_float32(constant_bits)
                pull_prediction = v2.predict_record_with_setup(
                    sample,
                    slope=slope_float,
                    constant=constant_float,
                )[: capture.PULL_COUNT]
                pull_differing = sum(
                    left != right
                    for left, right in zip(
                        actual[: capture.PULL_COUNT],
                        pull_prediction,
                        strict=True,
                    )
                )
                pull_word_mismatches += pull_differing
                pull_record_mismatches += bool(pull_differing)

                center_bits = actual[capture.PULL_COUNT]
                pull8_bits = actual[capture.PULL_NUMERATORS.index(8)]
                if center_bits == pull8_bits:
                    center_actual_equals_pull8 += 1
                elif center_bits + 1 == pull8_bits:
                    center_actual_equals_pull8_minus_one += 1
                else:
                    center_actual_other += 1

                coordinate = sample.x if axis == 0 else sample.y
                local_pixel = coordinate - sample.tile * capture.TILE_SIZE
                floor_left, floor_right = quad_center_pair(
                    local_pixel,
                    slope,
                    constant,
                    step,
                    base_rounding="floor",
                )
                ceil_left, ceil_right = quad_center_pair(
                    local_pixel,
                    slope,
                    constant,
                    step,
                    base_rounding="ceil",
                )
                normalized_step = significand_step(constant, step)
                normalized_left, normalized_right = quad_center_pair(
                    local_pixel,
                    slope,
                    constant,
                    normalized_step,
                    base_rounding="floor",
                )
                floor_center = floor_right if local_pixel & 1 else floor_left
                ceil_center = ceil_right if local_pixel & 1 else ceil_left
                normalized_center = (
                    normalized_right if local_pixel & 1 else normalized_left
                )
                floor_derivative = derivative_bits(floor_left, floor_right)
                normalized_derivative = derivative_bits(
                    normalized_left, normalized_right
                )
                center_floor_mismatches += floor_center != center_bits
                center_ceil_mismatches += ceil_center != center_bits
                center_normalized_mismatches += normalized_center != center_bits
                derivative_floor_mismatches += (
                    floor_derivative != actual[capture.PULL_COUNT + 1]
                )
                derivative_normalized_mismatches += (
                    normalized_derivative != actual[capture.PULL_COUNT + 1]
                )

                actual_pair_edge = sample.edge - (local_pixel & 1)
                if 0 <= actual_pair_edge and actual_pair_edge + 1 < extent:
                    paired_sample = samples[
                        sample.primitive * extent + actual_pair_edge + 1
                    ]
                    left_sample = samples[
                        sample.primitive * extent + actual_pair_edge
                    ]
                    left_actual = record_at(
                        raw, case_index, endpoint_index, left_sample
                    )[capture.PULL_COUNT]
                    right_actual = record_at(
                        raw, case_index, endpoint_index, paired_sample
                    )[capture.PULL_COUNT]
                    actual_derivative_from_actual_centers_mismatches += (
                        derivative_bits(left_actual, right_actual)
                        != actual[capture.PULL_COUNT + 1]
                    )

                floor_matches = floor_center == center_bits
                ceil_matches = ceil_center == center_bits
                action = (
                    "both"
                    if floor_matches and ceil_matches
                    else "floor-only"
                    if floor_matches
                    else "ceil-only"
                    if ceil_matches
                    else "neither"
                )
                action_counts[action] += 1
                action_by_extent[f"{extent}:{action}"] += 1
                setup_actions[
                    (capture_case.name, endpoint.name, sample.primitive, sample.tile)
                ][action] += 1

                if action != "both":
                    quad_local = local_pixel & ~1
                    exact_base = constant + Fraction(2 * quad_local + 1, 2) * slope
                    base_index, base_remainder = divmod(exact_base, step)
                    raw_base = raw_constant + Fraction(2 * quad_local + 1, 2) * slope
                    raw_index, raw_remainder = divmod(raw_base, step)
                    exact_translated = (
                        v1.float32_bits_fraction(endpoint.lowBits)
                        + (
                            v1.float32_bits_fraction(endpoint.highBits)
                            - v1.float32_bits_fraction(endpoint.lowBits)
                        )
                        * Fraction(sample.tile * capture.TILE_SIZE - origin, extent)
                    )
                    translated_base = (
                        exact_translated
                        + Fraction(2 * quad_local + 1, 2) * slope
                    )
                    translated_index, translated_remainder = divmod(
                        translated_base, step
                    )
                    slope_index, slope_remainder = divmod(slope, step)
                    row = {
                        "case": capture_case.name,
                        "endpoint": endpoint.name,
                        "role": endpoint.role,
                        "axis": axis,
                        "primitive": sample.primitive,
                        "extent": extent,
                        "oppositeExtent": (
                            capture_case.height if axis == 0 else capture_case.width
                        ),
                        "origin": origin,
                        "tile": sample.tile,
                        "geometryTile": sample.tile - origin // capture.TILE_SIZE,
                        "edge": sample.edge,
                        "coordinate": coordinate,
                        "localPixel": local_pixel,
                        "quadLocal": quad_local,
                        "quadMultiplier": 2 * quad_local + 1,
                        "firstGeometryTile": (
                            sample.tile == origin // capture.TILE_SIZE
                        ),
                        "lowBits": f"0x{endpoint.lowBits:08x}",
                        "highBits": f"0x{endpoint.highBits:08x}",
                        "cancellationDepth": v8.cancellation_depth(endpoint),
                        "slopeBits": f"0x{slope_bits:08x}",
                        "slopeIndex": slope_index,
                        "slopePhase": str(slope_remainder / step),
                        "constantBits": f"0x{constant_bits:08x}",
                        "step": str(step),
                        "baseIndex": base_index,
                        "basePhase": str(base_remainder / step),
                        "rawConstantResidualSteps": str(
                            (raw_constant - constant) / step
                        ),
                        "rawBaseIndexDelta": raw_index - base_index,
                        "rawBasePhase": str(raw_remainder / step),
                        "translatedConstantResidualSteps": str(
                            (exact_translated - constant) / step
                        ),
                        "translatedBaseIndexDelta": translated_index - base_index,
                        "translatedBasePhase": str(translated_remainder / step),
                        "actual": f"0x{center_bits:08x}",
                        "floor": f"0x{floor_center:08x}",
                        "ceil": f"0x{ceil_center:08x}",
                        "action": action,
                    }
                    discriminating_rows.append(row)
                    if action in {"ceil-only", "neither"}:
                        mismatch_examples.append(row)

    return {
        "records": records,
        "pullRecordMismatches": pull_record_mismatches,
        "pullWordMismatches": pull_word_mismatches,
        "centerActualVersusPull8": {
            "equal": center_actual_equals_pull8,
            "onePositiveUlpBelow": center_actual_equals_pull8_minus_one,
            "other": center_actual_other,
        },
        "p36": {
            "centerFloorMismatches": center_floor_mismatches,
            "centerCeilMismatches": center_ceil_mismatches,
            "centerNormalizedMismatches": center_normalized_mismatches,
            "derivativeFloorMismatches": derivative_floor_mismatches,
            "derivativeNormalizedMismatches": (
                derivative_normalized_mismatches
            ),
            "actualDerivativeFromActualCentersMismatches": (
                actual_derivative_from_actual_centers_mismatches
            ),
            "actions": dict(sorted(action_counts.items())),
            "actionsByExtent": dict(sorted(action_by_extent.items())),
            "discriminatingRows": discriminating_rows,
            "mismatchExamples": mismatch_examples,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(analyze(arguments.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
