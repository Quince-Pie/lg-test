#!/usr/bin/env python3
"""Freeze input-only witnesses for the natural shadow selector sweep."""

import argparse
import hashlib
import json
import math
import struct
import sys
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import numpy as np

import build_raster_fractional_selector_witness_map as fractional_witnesses
import raster_tile_coefficient_model as coefficient_base
import raster_tile_coefficient_model_v3 as coefficients
import raster_tile_selector_model as arithmetic
import raster_tile_selector_model_v4 as composite
import validate_raster_near_square_selector_sweep as near_square


type JsonObject = dict[str, object]

FIXED_UNITS_PER_PIXEL = 256
SAMPLE_XS = (512, 527, 543)
SAMPLE_Y = 512
SAMPLE_CENTER_Y_FIXED = SAMPLE_Y * FIXED_UNITS_PER_PIXEL + 128
TILE_SIZE = 32
PULL_PHASES = (0.0, 15.0 / 16.0)
RECOVERY_OFFSETS = tuple(range(-16, 17))
WITNESS_SLOT_COUNT = 8
UNASSIGNED_WITNESS = 0xFF
RECORD = struct.Struct("<2I")
MULTIPLIER_FILENAME = "raster_natural_shadow_selector_multiplier_bits_u32le.bin"


@dataclass(frozen=True, slots=True)
class PredictionContext:
    slopeNumeratorIndex: int
    slopeNumeratorExponent: int
    constantNumeratorIndex: int
    constantNumeratorExponent: int
    reciprocalExponent: int
    anchor: Fraction
    displacementSign: int
    localPixel: int


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_cases(path: Path) -> np.ndarray:
    raw = path.read_bytes()
    if len(raw) % 8:
        raise ValueError("natural shadow case stream is not uint32 pairs")
    values = np.frombuffer(raw, dtype="<u4").reshape(-1, 2)
    encoded = (values[:, 0].astype(np.uint64) << np.uint64(32)) | values[:, 1].astype(
        np.uint64
    )
    if len(values) == 0 or np.any(values == 0) or np.any(encoded[1:] <= encoded[:-1]):
        raise ValueError("natural shadow case stream differs")
    return values


def multiplier_bits() -> tuple[int, ...]:
    """Return one exact half-width multiplier per deterministic witness."""

    # The first entry is the natural symmetric ramp [-width/2,+width/2].
    # The remaining entries multiply width by deterministic values in
    # [1/4,1/2), preserving a broad significand bank without changing scale.
    result = [0x3F00_0000]
    result.extend(
        0x3E80_0000 | (significand & 0x007F_FFFF)
        for significand in fractional_witnesses.witness_significands()
    )
    if len(result) != 65 or len(set(result)) != len(result):
        raise ValueError("natural shadow witness multiplier pool differs")
    return tuple(result)


def endpoint_bits(width_fixed: int, multiplier: int) -> tuple[int, int]:
    width = arithmetic.float32(width_fixed / FIXED_UNITS_PER_PIXEL)
    high = arithmetic.float32(width * arithmetic.bits_float32(multiplier))
    return arithmetic.float32_bits(-high), arithmetic.float32_bits(high)


def first_stage_numerator(
    width_fixed: int,
    height_fixed: int,
    multiplier: int,
    *,
    bias_units: int,
) -> tuple[int, int]:
    low_bits, high_bits = endpoint_bits(width_fixed, multiplier)
    delta = arithmetic.float32(
        arithmetic.bits_float32(high_bits) - arithmetic.bits_float32(low_bits)
    )
    delta_index, delta_exponent = arithmetic.float_significand_and_lsb_exponent(
        arithmetic.float32_bits(delta)
    )
    opposite_bits = arithmetic.round_fraction_to_float32_bits(
        Fraction(height_fixed, FIXED_UNITS_PER_PIXEL)
    )
    opposite_index, opposite_exponent = arithmetic.float_significand_and_lsb_exponent(
        opposite_bits
    )
    return arithmetic.product_stage(
        delta_index,
        delta_exponent,
        opposite_index,
        opposite_exponent,
        output_bits=coefficient_base.FIRST_STAGE_OUTPUT_BITS,
        truncation_bits=coefficient_base.FIRST_STAGE_TRUNCATION_BITS,
        bias_units=bias_units,
    )


def prediction_context(
    width_fixed: int,
    height_fixed: int,
    multiplier: int,
    sample_x: int,
) -> PredictionContext:
    sample_center_x_fixed = sample_x * FIXED_UNITS_PER_PIXEL + 128
    origin_x_fixed = sample_center_x_fixed - width_fixed // 2
    origin_y_fixed = SAMPLE_CENTER_Y_FIXED - height_fixed // 2
    relative_x = sample_center_x_fixed - origin_x_fixed
    relative_y = SAMPLE_CENTER_Y_FIXED - origin_y_fixed
    primitive = int(
        relative_x * height_fixed + relative_y * width_fixed
        < width_fixed * height_fixed
    )
    use_high_anchor = primitive == 0
    anchor_fixed = origin_x_fixed + (width_fixed if use_high_anchor else 0)
    displacement_fixed = (
        sample_x // TILE_SIZE * TILE_SIZE * FIXED_UNITS_PER_PIXEL - anchor_fixed
    )
    slope_index, slope_exponent = first_stage_numerator(
        width_fixed,
        height_fixed,
        multiplier,
        bias_units=coefficients.MEASURED_POLICY.slope_first_bias,
    )
    constant_index, constant_exponent = first_stage_numerator(
        width_fixed,
        height_fixed,
        multiplier,
        bias_units=coefficients.MEASURED_POLICY.constant_first_bias,
    )
    if displacement_fixed:
        distance_bits = arithmetic.round_fraction_to_float32_bits(
            Fraction(abs(displacement_fixed), FIXED_UNITS_PER_PIXEL)
        )
        distance_index, distance_exponent = (
            arithmetic.float_significand_and_lsb_exponent(distance_bits)
        )
        constant_index, constant_exponent = coefficients.column_product_stage(
            constant_index,
            constant_exponent,
            distance_index,
            distance_exponent,
            output_bits=coefficient_base.TILE_STAGE_OUTPUT_BITS,
            truncation_bits=coefficients.MEASURED_POLICY.tile_truncation_bits,
            bias_units=coefficients.MEASURED_POLICY.tile_bias,
            carry_mode=coefficients.MEASURED_POLICY.tile_carry_mode,
            propagated_column_count=(
                coefficients.MEASURED_POLICY.tile_propagated_column_count
            ),
            sticky_carry_limit=(coefficients.MEASURED_POLICY.tile_sticky_carry_limit),
        )
    else:
        constant_index = 0
        constant_exponent = 0
    low_bits, high_bits = endpoint_bits(width_fixed, multiplier)
    return PredictionContext(
        slopeNumeratorIndex=slope_index,
        slopeNumeratorExponent=slope_exponent,
        constantNumeratorIndex=constant_index,
        constantNumeratorExponent=constant_exponent,
        reciprocalExponent=near_square.reciprocal_exponent(
            width_fixed,
            height_fixed,
        ),
        anchor=arithmetic.float32_bits_fraction(
            high_bits if use_high_anchor else low_bits
        ),
        displacementSign=-1 if displacement_fixed < 0 else 1,
        localPixel=sample_x % TILE_SIZE,
    )


def prediction(
    context: PredictionContext,
    *,
    reciprocal_index: int,
) -> tuple[int, int]:
    slope_index, slope_exponent = near_square.reciprocal_stage(
        context.slopeNumeratorIndex,
        context.slopeNumeratorExponent,
        reciprocal_index=reciprocal_index,
        reciprocal_lsb_exponent=context.reciprocalExponent,
    )
    slope = arithmetic.float32(math.ldexp(slope_index, slope_exponent))
    tile_term = Fraction(0)
    if context.constantNumeratorIndex:
        constant_index, constant_exponent = near_square.reciprocal_stage(
            context.constantNumeratorIndex,
            context.constantNumeratorExponent,
            reciprocal_index=reciprocal_index,
            reciprocal_lsb_exponent=context.reciprocalExponent,
        )
        tile_term = (
            context.displacementSign
            * Fraction(constant_index)
            * arithmetic.power_of_two(constant_exponent)
        )
    constant = arithmetic.bits_float32(
        composite.quantize_composite_constant_bits(context.anchor + tile_term)
    )
    return tuple(
        arithmetic.float32_bits(
            arithmetic.float32(math.fma(context.localPixel + phase, slope, constant))
        )
        for phase in PULL_PHASES
    )  # type: ignore[return-value]


def candidate_records(
    width_fixed: int,
    height_fixed: int,
    multiplier: int,
) -> tuple[tuple[int, ...], ...]:
    contexts = tuple(
        prediction_context(width_fixed, height_fixed, multiplier, sample_x)
        for sample_x in SAMPLE_XS
    )
    floor = near_square.exact_floor_selector(width_fixed, height_fixed)
    return tuple(
        tuple(
            word
            for context in contexts
            for word in prediction(
                context,
                reciprocal_index=floor + offset,
            )
        )
        for offset in RECOVERY_OFFSETS
    )


def select_witnesses(
    width_fixed: int,
    height_fixed: int,
    pool: tuple[int, ...],
) -> tuple[tuple[int, ...], tuple[tuple[tuple[int, ...], ...], ...]]:
    signatures: list[tuple[tuple[int, ...], ...]] = []
    combined: tuple[tuple[int, ...], ...] = tuple(() for _ in RECOVERY_OFFSETS)
    selected: list[int] = []
    record_cache: dict[int, tuple[tuple[int, ...], ...]] = {}
    for _ in range(WITNESS_SLOT_COUNT):
        best_index = -1
        best_signatures: tuple[tuple[int, ...], ...] | None = None
        best_distinct = -1
        for witness_index, multiplier in enumerate(pool):
            if witness_index in selected:
                continue
            records = record_cache.get(witness_index)
            if records is None:
                records = candidate_records(width_fixed, height_fixed, multiplier)
                record_cache[witness_index] = records
            trial = tuple(
                prefix + record
                for prefix, record in zip(combined, records, strict=True)
            )
            distinct = len(set(trial))
            if distinct > best_distinct:
                best_index = witness_index
                best_signatures = records
                best_distinct = distinct
            if distinct == len(RECOVERY_OFFSETS):
                break
        if best_index < 0 or best_signatures is None:
            raise ValueError("natural shadow witness search exhausted")
        selected.append(best_index)
        signatures.append(best_signatures)
        combined = tuple(
            prefix + record
            for prefix, record in zip(combined, best_signatures, strict=True)
        )
        if len(set(combined)) == len(RECOVERY_OFFSETS):
            break
    if len(set(combined)) != len(RECOVERY_OFFSETS):
        raise ValueError(f"no unique selector witness for {width_fixed}x{height_fixed}")
    selected.extend([selected[-1]] * (WITNESS_SLOT_COUNT - len(selected)))
    while len(signatures) < WITNESS_SLOT_COUNT:
        signatures.append(signatures[-1])
    return tuple(selected), tuple(signatures)


def build(cases: np.ndarray) -> tuple[bytes, bytes, JsonObject]:
    pool = multiplier_bits()
    assignments = bytearray(len(cases) * WITNESS_SLOT_COUNT)
    selected_count_distribution: Counter[int] = Counter()
    witness_distribution: Counter[int] = Counter()
    candidate_digest = hashlib.sha256()
    for case_index, (width_value, height_value) in enumerate(cases):
        if case_index and case_index % 10_000 == 0:
            print(
                f"preflight: {case_index}/{len(cases)} cases",
                file=sys.stderr,
                flush=True,
            )
        width_fixed = int(width_value)
        height_fixed = int(height_value)
        selected, signatures = select_witnesses(
            width_fixed,
            height_fixed,
            pool,
        )
        used_count = 1
        while (
            used_count < WITNESS_SLOT_COUNT
            and selected[used_count] != selected[used_count - 1]
        ):
            used_count += 1
        selected_count_distribution[used_count] += 1
        for slot, witness_index in enumerate(selected):
            assignments[case_index * WITNESS_SLOT_COUNT + slot] = witness_index
            witness_distribution[witness_index] += 1
            for record in signatures[slot]:
                for position in range(len(SAMPLE_XS)):
                    start = position * 2
                    candidate_digest.update(RECORD.pack(*record[start : start + 2]))
    assignment_bytes = bytes(assignments)
    pool_bytes = struct.pack(f"<{len(pool)}I", *pool)
    report: JsonObject = {
        "schemaVersion": 1,
        "classification": (
            "input-only witness selection for finite natural shadow selector "
            "calibration; no Apple output observed"
        ),
        "cases": {
            "count": len(cases),
            "sha256": sha256_bytes(cases.astype("<u4", copy=False).tobytes()),
        },
        "recovery": {
            "selectorOffsetsFromExactFloor": list(RECOVERY_OFFSETS),
            "candidateCount": len(RECOVERY_OFFSETS),
            "everyCaseCandidateMultiplicity": 1,
        },
        "witnessPool": {
            "count": len(pool),
            "dtype": "little-endian uint32 binary32 multiplier bits",
            "valuesSha256": sha256_bytes(pool_bytes),
        },
        "assignment": {
            "slotCount": WITNESS_SLOT_COUNT,
            "bytes": len(assignment_bytes),
            "dtype": "uint8 witness-pool index",
            "ordering": "case-major,witness-slot-minor",
            "sha256": sha256_bytes(assignment_bytes),
            "selectedWitnessCountDistribution": {
                str(key): value
                for key, value in sorted(selected_count_distribution.items())
            },
            "witnessSlotDistribution": {
                str(key): value for key, value in sorted(witness_distribution.items())
            },
        },
        "prediction": {
            "samplePixels": [[sample_x, SAMPLE_Y] for sample_x in SAMPLE_XS],
            "pullOffsets": [[0.0, 0.5], [0.9375, 0.5]],
            "candidateRecordBytes": RECORD.size,
            "candidateStreamBytes": (
                len(cases)
                * WITNESS_SLOT_COUNT
                * len(SAMPLE_XS)
                * len(RECOVERY_OFFSETS)
                * RECORD.size
            ),
            "candidateStreamSha256": candidate_digest.hexdigest(),
        },
    }
    return assignment_bytes, pool_bytes, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--multipliers-only", action="store_true")
    arguments = parser.parse_args()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    multiplier_output = arguments.output.parent / MULTIPLIER_FILENAME
    if arguments.multipliers_only:
        multiplier_payload = struct.pack(
            f"<{len(multiplier_bits())}I",
            *multiplier_bits(),
        )
        multiplier_output.write_bytes(multiplier_payload)
        print(
            json.dumps(
                {
                    "bytes": len(multiplier_payload),
                    "path": str(multiplier_output),
                    "sha256": sha256_bytes(multiplier_payload),
                },
                sort_keys=True,
            )
        )
        return 0
    cases = load_cases(arguments.cases)
    assignments, multipliers, metadata = build(cases)
    arguments.output.write_bytes(assignments)
    multiplier_output.write_bytes(multipliers)
    encoded = json.dumps(metadata, indent=2, sort_keys=True) + "\n"
    if arguments.report is not None:
        arguments.report.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
