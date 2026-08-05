#!/usr/bin/env python3
"""Recover one coherent plane gradient from schema-4 tile constants."""

import argparse
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np

import raster_tile_selector_model as v1
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v8 as v8
import validate_raster_tile_phase_holdout as capture


type JsonObject = dict[str, Any]

OFFSET_RADIUS = 32_768


def intervals(values: np.ndarray) -> list[list[int]]:
    if not len(values):
        return []
    result: list[list[int]] = []
    lower = previous = int(values[0])
    for raw_value in values[1:]:
        value = int(raw_value)
        if value != previous + 1:
            result.append([lower, previous])
            lower = value
        previous = value
    result.append([lower, previous])
    return result


def analyze(recovery_path: Path) -> JsonObject:
    recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
    cases = {case.name: case for case in capture.CASES}
    endpoints = {endpoint.name: endpoint for endpoint in capture.ENDPOINTS}
    selector_table = v1.load_selector_table()
    offsets = np.arange(-OFFSET_RADIUS, OFFSET_RADIUS + 1, dtype=np.int64)
    nonempty = 0
    fixed_internal_inside = 0
    exact_inside = 0
    width_counts: Counter[int] = Counter()
    groups: list[JsonObject] = []

    for recovered in recovery["groups"]:
        capture_case = cases[recovered["case"]]
        endpoint = endpoints[recovered["endpoint"]]
        axis = int(recovered["axis"])
        base_bits = int(recovered["slopeBits"], 16)
        base = v1.float32_bits_fraction(base_bits)
        step = v1.power_of_two(v1.floor_binary_exponent(abs(base)) - 35)
        candidates = float(base) + offsets * float(step)
        accepted_slopes = {
            int(offset): constants
            for offset, constants in recovered["acceptedSlopeOffsets"].items()
        }
        evaluator_offset = 1 if set(accepted_slopes) == {1} else 0
        accepted_constants = accepted_slopes[evaluator_offset]
        matching = np.ones(len(offsets), dtype=np.bool_)
        extent = capture_case.width if axis == 0 else capture_case.height
        origin = capture_case.originX if axis == 0 else capture_case.originY
        samples = capture.sample_positions(capture_case)

        for key, allowed_offsets in accepted_constants.items():
            primitive_text, tile_text = key.split(":")
            primitive = int(primitive_text.removeprefix("p"))
            tile = int(tile_text.removeprefix("t"))
            sample = next(
                sample
                for sample in samples
                if sample.axis == axis
                and sample.primitive == primitive
                and sample.tile == tile
            )
            physical_bits = v8.physical_constant_bits(
                capture_case,
                endpoint,
                sample,
                selector_table=selector_table,
            )
            if axis == 0 and primitive == 0:
                anchor = v1.bits_float32(endpoint.highBits)
                anchor_position = origin + extent
            else:
                anchor = v1.bits_float32(endpoint.lowBits)
                anchor_position = origin
            displacement = tile * capture.TILE_SIZE - anchor_position
            values = anchor + displacement * candidates
            _, binary_exponents = np.frexp(np.abs(values))
            p28_steps = np.exp2(binary_exponents.astype(np.float64) - 28.0)
            p28_values = np.rint(values / p28_steps) * p28_steps
            bits = p28_values.astype(np.float32).view(np.uint32)
            allowed = np.zeros(len(offsets), dtype=np.bool_)
            for constant_offset in allowed_offsets:
                allowed |= bits == physical_bits + constant_offset
            matching &= allowed
            if not matching.any():
                break

        matching_offsets = offsets[matching]
        if len(matching_offsets):
            nonempty += 1
            width_counts[len(matching_offsets)] += 1
        _, _, internal_float = v4.determinant_slope(
            capture_case,
            endpoint,
            axis=axis,
            selector_table=selector_table,
        )
        internal_offset = (Fraction.from_float(internal_float) - base) / step
        delta = (
            v1.float32_bits_fraction(endpoint.highBits)
            - v1.float32_bits_fraction(endpoint.lowBits)
        )
        exact = delta / extent
        exact_offset = (exact - base) / step

        def inside(value: Fraction) -> bool:
            return value.denominator == 1 and bool(
                matching[int(value) + OFFSET_RADIUS]
            )

        fixed_internal_inside += inside(internal_offset)
        exact_inside += inside(exact_offset)
        groups.append(
            {
                "case": capture_case.name,
                "caseRole": capture_case.role,
                "endpoint": endpoint.name,
                "axis": axis,
                "extent": extent,
                "origin": origin,
                "baseSlopeBits": f"0x{base_bits:08x}",
                "p36Step": str(step),
                "matchingOffsetCount": len(matching_offsets),
                "matchingOffsetIntervals": intervals(matching_offsets),
                "fixedInternalOffset": str(internal_offset),
                "fixedInternalInside": inside(internal_offset),
                "exactOffset": str(exact_offset),
                "exactInside": inside(exact_offset),
            }
        )

    return {
        "schema4ConstantGradientRecoverySchemaVersion": 1,
        "sourceRecovery": str(recovery_path),
        "offsetRadius": OFFSET_RADIUS,
        "setupCount": len(groups),
        "nonemptySetupCount": nonempty,
        "emptySetupCount": len(groups) - nonempty,
        "fixedInternalInsideCount": fixed_internal_inside,
        "exactInsideCount": exact_inside,
        "matchingWidthCounts": {
            str(width): count for width, count in sorted(width_counts.items())
        },
        "groups": groups,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recovery", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = analyze(arguments.recovery)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(rendered, end="")
    else:
        arguments.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
