#!/usr/bin/env python3
"""Recover schema-4 center coefficients on a 36-bit lattice."""

import argparse
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

import explore_raster_tile_center_p36 as p36
import raster_tile_selector_model as v1
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v8 as v8
import validate_raster_tile_phase_holdout as capture


type JsonObject = dict[str, Any]
type FloatArray = npt.NDArray[np.float64]
type Uint32Array = npt.NDArray[np.uint32]

TARGET_ENDPOINTS = {
    "opened-512-x",
    "opened-512-y",
    "opened-640-x",
    "opened-640-y",
    "opened-896-x",
    "opened-896-y",
}
OFFSET_RADIUS = 8_192
CHUNK_SIZE = 512


def toward_zero_bits(values: FloatArray) -> Uint32Array:
    nearest = values.astype(np.float32)
    nearest64 = nearest.astype(np.float64)
    bits = nearest.view(np.uint32).copy()
    overshoot = ((values > 0) & (nearest64 > values)) | (
        (values < 0) & (nearest64 < values)
    )
    bits[overshoot] -= np.uint32(1)
    return bits


def intervals(values: npt.NDArray[np.int64]) -> list[list[int]]:
    if len(values) == 0:
        return []
    result: list[list[int]] = []
    start = previous = int(values[0])
    for raw_value in values[1:]:
        value = int(raw_value)
        if value != previous + 1:
            result.append([start, previous])
            start = value
        previous = value
    result.append([start, previous])
    return result


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
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    raw = (root / manifest["rasterTileNumerator"]["file"]).read_bytes()
    selector_table = v1.load_selector_table()
    setups: list[JsonObject] = []
    center_exact_setups = 0
    derivative_exact_setups = 0

    all_offsets = np.arange(
        -OFFSET_RADIUS,
        OFFSET_RADIUS + 1,
        dtype=np.int64,
    )
    for case_index, capture_case in enumerate(capture.CASES):
        case_samples = capture.sample_positions(capture_case)
        for endpoint_index, endpoint in enumerate(capture.ENDPOINTS):
            if endpoint.name not in TARGET_ENDPOINTS:
                continue
            for axis in range(capture.AXIS_COUNT):
                samples = [sample for sample in case_samples if sample.axis == axis]
                if not samples:
                    continue
                determinant_float = v8.determinant_slope(
                    capture_case,
                    endpoint,
                    axis=axis,
                    selector_table=selector_table,
                )
                determinant_bits = v1.float32_bits(determinant_float)
                determinant = float(v1.bits_float32(determinant_bits))
                determinant_fraction = v1.float32_bits_fraction(determinant_bits)
                coefficient_step_fraction = v1.power_of_two(
                    v1.floor_binary_exponent(abs(determinant_fraction))
                    - p36.CENTER_PRECISION_BITS
                    + 1
                )
                coefficient_step = float(coefficient_step_fraction)
                fallback_step = p36.endpoint_step(endpoint)

                local_pixels: list[int] = []
                constants: list[float] = []
                accumulator_steps: list[float] = []
                actual_centers: list[int] = []
                actual_derivatives: list[int] = []
                for sample in samples:
                    actual = record_at(raw, case_index, endpoint_index, sample)
                    if actual == capture.SENTINEL:
                        continue
                    coordinate = sample.x if axis == 0 else sample.y
                    local_pixels.append(
                        coordinate - sample.tile * capture.TILE_SIZE
                    )
                    constant_bits = v8.physical_constant_bits(
                        capture_case,
                        endpoint,
                        sample,
                        selector_table=selector_table,
                    )
                    constant = v1.float32_bits_fraction(constant_bits)
                    constants.append(float(constant))
                    accumulator_steps.append(
                        float(p36.significand_step(constant, fallback_step))
                    )
                    actual_centers.append(actual[capture.PULL_COUNT])
                    actual_derivatives.append(actual[capture.PULL_COUNT + 1])

                local = np.asarray(local_pixels, dtype=np.int64)
                quad_local = local & ~1
                multipliers = quad_local.astype(np.float64) + 0.5
                constant_values = np.asarray(constants, dtype=np.float64)
                steps = np.asarray(accumulator_steps, dtype=np.float64)
                expected_centers = np.asarray(actual_centers, dtype=np.uint32)
                expected_derivatives = np.asarray(
                    actual_derivatives,
                    dtype=np.uint32,
                )
                center_offsets: list[npt.NDArray[np.int64]] = []
                derivative_offsets: list[npt.NDArray[np.int64]] = []

                for start in range(0, len(all_offsets), CHUNK_SIZE):
                    offsets = all_offsets[start : start + CHUNK_SIZE]
                    slopes = determinant + offsets.astype(np.float64) * coefficient_step
                    exact_bases = (
                        constant_values[None, :]
                        + slopes[:, None] * multipliers[None, :]
                    )
                    bases = np.floor(exact_bases / steps[None, :]) * steps[None, :]
                    left_bits = toward_zero_bits(bases)
                    right_bits = toward_zero_bits(bases + slopes[:, None])
                    predicted_centers = np.where(
                        (local & 1)[None, :] != 0,
                        right_bits,
                        left_bits,
                    )
                    center_matches = np.all(
                        predicted_centers == expected_centers[None, :],
                        axis=1,
                    )
                    if not np.any(center_matches):
                        continue
                    matching_offsets = offsets[center_matches]
                    center_offsets.append(matching_offsets)
                    matching_left = left_bits[center_matches]
                    matching_right = right_bits[center_matches]
                    left_values = matching_left.view(np.float32)
                    right_values = matching_right.view(np.float32)
                    predicted_derivatives = (right_values - left_values).astype(
                        np.float32
                    ).view(np.uint32)
                    derivative_matches = np.all(
                        predicted_derivatives == expected_derivatives[None, :],
                        axis=1,
                    )
                    if np.any(derivative_matches):
                        derivative_offsets.append(
                            matching_offsets[derivative_matches]
                        )

                center_values = (
                    np.concatenate(center_offsets)
                    if center_offsets
                    else np.empty(0, dtype=np.int64)
                )
                derivative_values = (
                    np.concatenate(derivative_offsets)
                    if derivative_offsets
                    else np.empty(0, dtype=np.int64)
                )
                center_exact_setups += bool(len(center_values))
                derivative_exact_setups += bool(len(derivative_values))
                _, quotient_phase, internal_float = v4.determinant_slope(
                    capture_case,
                    endpoint,
                    axis=axis,
                    selector_table=selector_table,
                )
                setups.append(
                    {
                        "case": capture_case.name,
                        "caseRole": capture_case.role,
                        "endpoint": endpoint.name,
                        "axis": axis,
                        "extent": (
                            capture_case.width if axis == 0 else capture_case.height
                        ),
                        "oppositeExtent": (
                            capture_case.height if axis == 0 else capture_case.width
                        ),
                        "origin": (
                            capture_case.originX if axis == 0 else capture_case.originY
                        ),
                        "recordCount": len(local),
                        "determinantBits": f"0x{determinant_bits:08x}",
                        "coefficientStep": str(coefficient_step_fraction),
                        "quotientP27Phase": str(quotient_phase),
                        "internalOffsetSteps": str(
                            (Fraction.from_float(internal_float) - determinant_fraction)
                            / coefficient_step_fraction
                        ),
                        "centerOffsetCount": len(center_values),
                        "centerOffsetIntervals": intervals(center_values),
                        "centerIncludesRoundedF32": bool(
                            np.any(center_values == 0)
                        ),
                        "derivativeOffsetCount": len(derivative_values),
                        "derivativeOffsetIntervals": intervals(derivative_values),
                        "derivativeIncludesRoundedF32": bool(
                            np.any(derivative_values == 0)
                        ),
                    }
                )

    return {
        "schema4P36CoefficientRecoverySchemaVersion": 1,
        "source": str(root),
        "targetEndpoints": sorted(TARGET_ENDPOINTS),
        "coefficientPrecisionBits": p36.CENTER_PRECISION_BITS,
        "offsetRadius": OFFSET_RADIUS,
        "setupCount": len(setups),
        "centerExactSetupCount": center_exact_setups,
        "centerAndDerivativeExactSetupCount": derivative_exact_setups,
        "setups": setups,
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
