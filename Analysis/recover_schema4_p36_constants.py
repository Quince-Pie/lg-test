#!/usr/bin/env python3
"""Recover hidden P36 tile-constant offsets for schema-4 broad residuals."""

import argparse
import json
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np

import explore_raster_tile_center_p36 as p36
import raster_tile_selector_model as v1
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v8 as v8
import validate_raster_tile_phase_holdout as capture
from recover_schema4_p36_coefficients import intervals, toward_zero_bits


type JsonObject = dict[str, Any]

TARGET_ENDPOINTS = {
    "opened-512-x",
    "opened-512-y",
    "opened-640-x",
    "opened-640-y",
    "opened-896-x",
    "opened-896-y",
}
OFFSET_RADIUS = 8_192


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


def rounded_candidates(value: Fraction) -> dict[str, int]:
    floor_value, remainder = divmod(value.numerator, value.denominator)
    return {
        "floor": floor_value,
        "ceil": floor_value + bool(remainder),
        "nearestEven": v1.round_fraction_to_integer_nearest_even(value),
        "towardZero": int(value),
    }


def analyze(root: Path) -> JsonObject:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    raw = (root / manifest["rasterTileNumerator"]["file"]).read_bytes()
    selector_table = v1.load_selector_table()
    all_offsets = np.arange(
        -OFFSET_RADIUS,
        OFFSET_RADIUS + 1,
        dtype=np.int64,
    )
    mismatching_groups: list[JsonObject] = []
    group_count = 0

    for case_index, capture_case in enumerate(capture.CASES):
        case_samples = capture.sample_positions(capture_case)
        for endpoint_index, endpoint in enumerate(capture.ENDPOINTS):
            if endpoint.name not in TARGET_ENDPOINTS:
                continue
            groups: dict[tuple[int, int, int], list[object]] = defaultdict(list)
            for sample in case_samples:
                groups[(sample.axis, sample.primitive, sample.tile)].append(sample)
            for (axis, primitive, tile), samples in groups.items():
                actual = [
                    record_at(raw, case_index, endpoint_index, sample)
                    for sample in samples
                ]
                retained = [
                    (sample, record)
                    for sample, record in zip(samples, actual, strict=True)
                    if record != capture.SENTINEL
                ]
                if not retained:
                    continue
                group_count += 1
                samples = [value[0] for value in retained]
                actual = [value[1] for value in retained]
                slope_float = v8.determinant_slope(
                    capture_case,
                    endpoint,
                    axis=axis,
                    selector_table=selector_table,
                )
                slope_bits = v1.float32_bits(slope_float)
                slope = v1.float32_bits_fraction(slope_bits)
                representative = samples[0]
                constant_bits = v8.physical_constant_bits(
                    capture_case,
                    endpoint,
                    representative,
                    selector_table=selector_table,
                )
                constant = v1.float32_bits_fraction(constant_bits)
                step = p36.significand_step(
                    constant,
                    p36.endpoint_step(endpoint),
                )
                local = np.asarray(
                    [
                        (sample.x if axis == 0 else sample.y)
                        - tile * capture.TILE_SIZE
                        for sample in samples
                    ],
                    dtype=np.int64,
                )
                multipliers = (local & ~1).astype(np.float64) + 0.5
                expected_centers = np.asarray(
                    [record[capture.PULL_COUNT] for record in actual],
                    dtype=np.uint32,
                )
                expected_derivatives = np.asarray(
                    [record[capture.PULL_COUNT + 1] for record in actual],
                    dtype=np.uint32,
                )

                candidate_constants = float(constant) + all_offsets * float(step)
                exact_bases = (
                    candidate_constants[:, None]
                    + float(slope) * multipliers[None, :]
                )
                bases = np.floor(exact_bases / float(step)) * float(step)
                left_bits = toward_zero_bits(bases)
                right_bits = toward_zero_bits(bases + float(slope))
                predicted_centers = np.where(
                    (local & 1)[None, :] != 0,
                    right_bits,
                    left_bits,
                )
                center_matches = np.all(
                    predicted_centers == expected_centers[None, :],
                    axis=1,
                )
                left_values = left_bits.view(np.float32)
                right_values = right_bits.view(np.float32)
                predicted_derivatives = (right_values - left_values).astype(
                    np.float32
                ).view(np.uint32)
                derivative_matches = np.all(
                    predicted_derivatives == expected_derivatives[None, :],
                    axis=1,
                )
                complete_matches = center_matches & derivative_matches
                if complete_matches[OFFSET_RADIUS]:
                    continue

                matching_offsets = all_offsets[complete_matches]
                raw_constant = v4.zero_physical_composite(
                    capture_case,
                    endpoint,
                    representative,
                    selector_table=selector_table,
                )
                raw_p28_magnitude = v1.quantize_binary_significand(
                    abs(raw_constant),
                    v4.CONSTANT_INTERNAL_PRECISION_BITS,
                    rounding="nearest-even",
                )
                raw_p28 = (
                    -raw_p28_magnitude if raw_constant < 0 else raw_p28_magnitude
                )
                extent = capture_case.width if axis == 0 else capture_case.height
                origin = capture_case.originX if axis == 0 else capture_case.originY
                translated = (
                    v1.float32_bits_fraction(endpoint.lowBits)
                    + (
                        v1.float32_bits_fraction(endpoint.highBits)
                        - v1.float32_bits_fraction(endpoint.lowBits)
                    )
                    * Fraction(tile * capture.TILE_SIZE - origin, extent)
                )
                residuals = {
                    "rawPhysical": (raw_constant - constant) / step,
                    "rawP28": (raw_p28 - constant) / step,
                    "translatedExact": (translated - constant) / step,
                }
                neighbor_offsets = {
                    "previous": (
                        v1.float32_bits_fraction(constant_bits - 1) - constant
                    )
                    / step,
                    "current": Fraction(0),
                    "next": (
                        v1.float32_bits_fraction(constant_bits + 1) - constant
                    )
                    / step,
                }
                matching_intervals = intervals(matching_offsets)
                mismatching_groups.append(
                    {
                        "case": capture_case.name,
                        "caseRole": capture_case.role,
                        "endpoint": endpoint.name,
                        "axis": axis,
                        "primitive": primitive,
                        "tile": tile,
                        "extent": extent,
                        "oppositeExtent": (
                            capture_case.height if axis == 0 else capture_case.width
                        ),
                        "origin": origin,
                        "localPixels": local.tolist(),
                        "slopeBits": f"0x{slope_bits:08x}",
                        "constantBits": f"0x{constant_bits:08x}",
                        "step": str(step),
                        "matchingOffsetCount": len(matching_offsets),
                        "matchingOffsetIntervals": matching_intervals,
                        "neighborOffsets": {
                            name: str(value)
                            for name, value in neighbor_offsets.items()
                        },
                        "matchingNeighbors": [
                            name
                            for name, value in neighbor_offsets.items()
                            if value.denominator == 1
                            and any(
                                lower <= value <= upper
                                for lower, upper in matching_intervals
                            )
                        ],
                        "candidateResidualSteps": {
                            name: str(value) for name, value in residuals.items()
                        },
                        "candidateRoundedOffsets": {
                            name: rounded_candidates(value)
                            for name, value in residuals.items()
                        },
                    }
                )

    return {
        "schema4P36ConstantRecoverySchemaVersion": 1,
        "source": str(root),
        "targetEndpoints": sorted(TARGET_ENDPOINTS),
        "offsetRadius": OFFSET_RADIUS,
        "groupCount": group_count,
        "roundedF32MismatchingGroupCount": len(mismatching_groups),
        "mismatchingGroups": mismatching_groups,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = analyze(arguments.root)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(rendered, end="")
    else:
        arguments.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
