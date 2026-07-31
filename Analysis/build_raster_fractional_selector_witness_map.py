#!/usr/bin/env python3
"""Build witnesses for an exhaustive fractional-width selector sweep."""

import argparse
import hashlib
import json
import sys
import zlib
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

import explore_general_height as general
import model_raster_general_height_arithmetic as two_stage
import validate_raster_general_height_selector_transfer as selector


type JsonObject = dict[str, Any]

MANTISSA_COUNT = 1 << 23
NORMALIZED_INPUT_LOWER = 1 << 23
RECIPROCAL_NUMERATOR = 1 << 48
OPPOSITE_EDGE = 64
RECIPROCAL_LSB_EXPONENT = -44
SAMPLE_XS = (0, 15, 31)
SAMPLE_OFFSETS = tuple(
    position
    for x in SAMPLE_XS
    for position in (float(x), float(x) + 0.9375)
)
UNASSIGNED_WITNESS = 0xFF
WITNESS_LIMIT = 64
LCG_INITIAL_STATE = 0x5B_D1_E9
LCG_MULTIPLIER = 0x1E_35_A7
LCG_INCREMENT = 0x6C_8E_9D
LCG_MASK = 0x7F_FF_FF
LOW_PRODUCT_MASK = (1 << two_stage.SECOND_STAGE_TRUNCATION_BITS) - 1


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def uint32_sha256(values: np.ndarray | tuple[int, ...]) -> str:
    array = np.asarray(values, dtype="<u4")
    return sha256_bytes(array.tobytes())


def witness_significands() -> tuple[int, ...]:
    result = list(selector.WITNESS_SIGNIFICANDS)
    seen = set(result)
    state = LCG_INITIAL_STATE
    while len(result) < WITNESS_LIMIT:
        state = (state * LCG_MULTIPLIER + LCG_INCREMENT) & LCG_MASK
        significand = 0x80_00_00 | state
        if significand not in seen:
            seen.add(significand)
            result.append(significand)
    return tuple(result)


def delta_bits(significand: int) -> int:
    return (0x3F_00_00_00 | (significand & 0x7F_FF_FF)) - 0x0080_0000


def first_stage(significand: int) -> tuple[int, int]:
    varying_significand, varying_exponent = (
        general.float_significand_and_lsb_exponent(delta_bits(significand))
    )
    edge_bits = selector.factorization.top_left.arithmetic.float32_bits(
        float(OPPOSITE_EDGE)
    )
    edge_significand, edge_exponent = (
        general.float_significand_and_lsb_exponent(edge_bits)
    )
    return two_stage.product_stage(
        varying_significand,
        varying_exponent,
        edge_significand,
        edge_exponent,
        output_bits=two_stage.FIRST_STAGE_OUTPUT_BITS,
        truncation_bits=two_stage.FIRST_STAGE_TRUNCATION_BITS,
        bias_units=two_stage.FIRST_STAGE_BIAS_UNITS[0],
    )


def correction_table(multiplicand: int) -> np.ndarray:
    size = 1 << two_stage.SECOND_STAGE_TRUNCATION_BITS
    indices = np.arange(size, dtype=np.uint32)
    corrections = np.zeros(size, dtype=np.uint64)
    for bit in range(two_stage.SECOND_STAGE_TRUNCATION_BITS):
        penalty = (multiplicand << bit) & LOW_PRODUCT_MASK
        corrections += ((indices >> bit) & 1).astype(np.uint64) * penalty
    return corrections


def vector_slope_bits(
    reciprocals: np.ndarray,
    *,
    numerator_index: int,
    numerator_lsb_exponent: int,
) -> np.ndarray:
    reciprocal_values = np.asarray(reciprocals, dtype=np.uint64)
    exact_products = np.uint64(numerator_index) * reciprocal_values
    corrections = correction_table(numerator_index)
    partial_products = (
        exact_products
        - corrections[(reciprocal_values & LOW_PRODUCT_MASK).astype(np.uint32)]
        + np.uint64(
            two_stage.SECOND_STAGE_BIAS_UNITS
            << two_stage.SECOND_STAGE_TRUNCATION_BITS
        )
    )
    product_shifts = np.where(exact_products >= (1 << 51), 25, 24).astype(
        np.int32
    )
    coefficient_indices = partial_products >> product_shifts.astype(np.uint64)
    coefficient_exponents = (
        numerator_lsb_exponent + RECIPROCAL_LSB_EXPONENT + product_shifts
    )
    return np.ldexp(
        coefficient_indices.astype(np.float64),
        coefficient_exponents,
    ).astype(np.float32).view(np.uint32)


def observationally_distinct(
    lower_slope_bits: np.ndarray,
    upper_slope_bits: np.ndarray,
) -> np.ndarray:
    lower = lower_slope_bits.view(np.float32).astype(np.float64)
    upper = upper_slope_bits.view(np.float32).astype(np.float64)
    distinct = np.zeros(len(lower_slope_bits), dtype=np.bool_)
    for position in SAMPLE_OFFSETS:
        lower_pull = (position * lower).astype(np.float32).view(np.uint32)
        upper_pull = (position * upper).astype(np.float32).view(np.uint32)
        distinct |= lower_pull != upper_pull
    return distinct


def build() -> tuple[bytes, JsonObject]:
    if sys.byteorder != "little":
        raise RuntimeError("the frozen witness map requires little-endian NumPy")
    normalized_inputs = np.arange(
        NORMALIZED_INPUT_LOWER,
        1 << 24,
        dtype=np.uint64,
    )
    lower_reciprocals = np.uint64(RECIPROCAL_NUMERATOR) // normalized_inputs
    remainders = np.uint64(RECIPROCAL_NUMERATOR) % normalized_inputs
    lower_reciprocals[0] = 1 << 24
    remainders[0] = 0
    upper_reciprocals = lower_reciprocals + (remainders != 0)
    witnesses = witness_significands()
    witness_indices = np.full(
        MANTISSA_COUNT,
        UNASSIGNED_WITNESS,
        dtype=np.uint8,
    )
    lower_slopes = np.zeros(MANTISSA_COUNT, dtype=np.uint32)
    upper_slopes = np.zeros(MANTISSA_COUNT, dtype=np.uint32)
    witness_indices[0] = 0
    numerator_index, numerator_exponent = first_stage(witnesses[0])
    lower_slopes[0] = vector_slope_bits(
        lower_reciprocals[:1],
        numerator_index=numerator_index,
        numerator_lsb_exponent=numerator_exponent,
    )[0]
    upper_slopes[0] = lower_slopes[0]
    assignment_counts: Counter[int] = Counter({0: 1})

    for witness_index, significand in enumerate(witnesses):
        unresolved = np.flatnonzero(witness_indices == UNASSIGNED_WITNESS)
        if len(unresolved) == 0:
            break
        numerator_index, numerator_exponent = first_stage(significand)
        candidate_lower = vector_slope_bits(
            lower_reciprocals[unresolved],
            numerator_index=numerator_index,
            numerator_lsb_exponent=numerator_exponent,
        )
        candidate_upper = vector_slope_bits(
            upper_reciprocals[unresolved],
            numerator_index=numerator_index,
            numerator_lsb_exponent=numerator_exponent,
        )
        accepted = observationally_distinct(candidate_lower, candidate_upper)
        selected = unresolved[accepted]
        witness_indices[selected] = witness_index
        lower_slopes[selected] = candidate_lower[accepted]
        upper_slopes[selected] = candidate_upper[accepted]
        if len(selected) != 0:
            assignment_counts[witness_index] += len(selected)

    unresolved_count = int(
        np.count_nonzero(witness_indices == UNASSIGNED_WITNESS)
    )
    if unresolved_count != 0:
        raise ValueError(f"{unresolved_count} reciprocal pairs lack a witness")
    distinct_count = int(np.count_nonzero(lower_slopes != upper_slopes))
    if distinct_count != MANTISSA_COUNT - 1:
        raise ValueError("candidate slope pairs are not uniquely observable")

    witness_bytes = witness_indices.tobytes()
    selected_delta_bits = np.asarray(
        [delta_bits(significand) for significand in witnesses],
        dtype=np.uint32,
    )[witness_indices]
    width_bits = np.arange(
        0x4600_0000,
        0x4680_0000,
        dtype=np.uint32,
    )
    reciprocal_pairs = np.column_stack(
        (lower_reciprocals.astype(np.uint32), upper_reciprocals.astype(np.uint32))
    )
    slope_pairs = np.column_stack((lower_slopes, upper_slopes))
    used_witness_count = max(assignment_counts) + 1
    report: JsonObject = {
        "mantissaCount": MANTISSA_COUNT,
        "widthBitsSha256": uint32_sha256(width_bits),
        "selectedDeltaBitsSha256": uint32_sha256(selected_delta_bits),
        "candidateReciprocalPairSha256": sha256_bytes(
            reciprocal_pairs.astype("<u4", copy=False).tobytes()
        ),
        "candidateSlopePairSha256": sha256_bytes(
            slope_pairs.astype("<u4", copy=False).tobytes()
        ),
        "candidateSlopeDistinctCount": distinct_count,
        "exactPowerBoundaryCount": MANTISSA_COUNT - distinct_count,
        "witnessPoolCount": len(witnesses),
        "usedWitnessCount": used_witness_count,
        "witnessSignificands": list(witnesses),
        "witnessSignificandsSha256": uint32_sha256(witnesses),
        "witnessAssignmentDistribution": {
            str(key): value for key, value in sorted(assignment_counts.items())
        },
        "witnessIndexBytes": len(witness_bytes),
        "witnessIndexSha256": sha256_bytes(witness_bytes),
        "sampleXs": list(SAMPLE_XS),
        "samplePositionCount": len(SAMPLE_XS),
        "recordBytes": 8,
        "rawBytes": MANTISSA_COUNT * len(SAMPLE_XS) * 8,
    }
    return witness_bytes, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map-output", type=Path)
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args()
    witness_map, report = build()
    compressed = zlib.compress(witness_map, level=9)
    report["compressedWitnessIndexBytes"] = len(compressed)
    report["compressedWitnessIndexSha256"] = sha256_bytes(compressed)
    if arguments.map_output is not None:
        arguments.map_output.write_bytes(witness_map)
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.report is not None:
        arguments.report.write_text(serialized, encoding="utf-8")
    print(serialized, end="")


if __name__ == "__main__":
    main()
