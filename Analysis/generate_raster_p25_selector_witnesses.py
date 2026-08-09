#!/usr/bin/env python3
"""Freeze the input-only witness for the exhaustive normalized-P25 sweep.

Each non-boundary P25 key has exactly two reciprocal candidates: the floor and
ceiling of ``2**49 / key``.  A centered, symmetric ramp exposes the candidate
through AGX's measured factorized tile constant.  This module exhaustively
proves that the predeclared fragment pull distinguishes every candidate pair.
It consumes no Apple output.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

import raster_tile_coefficient_model as coefficients


type JsonObject = dict[str, Any]

KEY_LOWER = 1 << 24
KEY_UPPER = 1 << 25
KEY_COUNT = KEY_UPPER - KEY_LOWER
RECIPROCAL_NUMERATOR = 1 << 49
FIXED_UNITS_PER_PIXEL = 256
CASE_RECORD_BYTES = 8
BATCH_CASE_COUNT = 65_536
SAMPLE_X = 512
SAMPLE_Y = 512
SAMPLE_CENTER_X_FIXED = SAMPLE_X * FIXED_UNITS_PER_PIXEL + 128
SAMPLE_CENTER_Y_FIXED = SAMPLE_Y * FIXED_UNITS_PER_PIXEL + 128
TILE_SIZE = 32
TILE_ORIGIN_X_FIXED = (
    SAMPLE_X // TILE_SIZE * TILE_SIZE * FIXED_UNITS_PER_PIXEL
)
ENDPOINT_MULTIPLIER_BITS = 0x3F00_0000
PULL_OFFSET = (0.0, 0.5)
CASE_SHA256 = "836faf360db6a9bcdf2beb2f994507afe2ce0276eab3c2d45ae64e6facf8da3e"


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def load_cases(path: Path) -> np.memmap:
    expected_bytes = KEY_COUNT * CASE_RECORD_BYTES
    if path.stat().st_size != expected_bytes or sha256_path(path) != CASE_SHA256:
        raise ValueError("normalized-P25 representative case stream differs")
    cases = np.memmap(path, mode="r", dtype="<u4").reshape(KEY_COUNT, 2)
    if (
        np.any(cases == 0)
        or int(cases[:, 0].min()) != 130_048
        or int(cases[:, 0].max()) != 185_344
        or int(cases[:, 1].min()) != 131_072
        or int(cases[:, 1].max()) != 186_382
    ):
        raise ValueError("normalized-P25 representative bounds differ")
    return cases


def reciprocal_candidates(keys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    key_values = np.asarray(keys, dtype=np.uint64)
    lower = np.uint64(RECIPROCAL_NUMERATOR) // key_values
    remainder = np.uint64(RECIPROCAL_NUMERATOR) % key_values
    upper = lower + (remainder != 0)
    exact_power = key_values == KEY_LOWER
    lower[exact_power] = 1 << 24
    upper[exact_power] = 1 << 24
    return lower, upper


def product_shifts(products: np.ndarray, output_bits: int) -> np.ndarray:
    """Return exact integer bit lengths minus the output precision."""

    values = np.asarray(products, dtype=np.uint64)
    if np.any(values == 0) or np.any(values >= (1 << 53)):
        raise ValueError("vector product is outside exact binary64 integers")
    return np.frexp(values.astype(np.float64))[1].astype(np.int32) - output_bits


def fixed_float_parts(
    values_fixed: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Decode positive 24.8 fixed values into exact binary32 parts."""

    values = np.asarray(values_fixed, dtype=np.uint64)
    if np.any(values == 0) or np.any(values >= (1 << 24)):
        raise ValueError("fixed value is outside exact normal binary32 input")
    bit_lengths = np.frexp(values.astype(np.float64))[1].astype(np.int32)
    shifts = 24 - bit_lengths
    indices = values << shifts.astype(np.uint64)
    exponents = bit_lengths - 32
    return indices, exponents


def vector_product_stage(
    multiplicands: np.ndarray,
    multiplicand_exponents: np.ndarray,
    multipliers: np.ndarray,
    multiplier_exponents: np.ndarray | int,
    *,
    output_bits: int,
    truncation_bits: int,
    bias_units: int,
    propagate_top_discarded_column: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply the measured truncated-partial-product integer stage."""

    left = np.asarray(multiplicands, dtype=np.uint64)
    right = np.asarray(multipliers, dtype=np.uint64)
    exact_products = left * right
    low_mask = np.uint64((1 << truncation_bits) - 1)
    corrections = np.zeros(len(exact_products), dtype=np.uint64)
    top_column_count = np.zeros(len(exact_products), dtype=np.uint64)
    for bit in range(int(right.max()).bit_length()):
        selected = (right >> np.uint64(bit)) & np.uint64(1)
        remainder = (left << np.uint64(bit)) & low_mask
        corrections += remainder * selected
        if propagate_top_discarded_column:
            top_column_count += (
                (remainder >> np.uint64(truncation_bits - 1)) & np.uint64(1)
            ) * selected
    retained_carry = (
        top_column_count >> np.uint64(1)
        if propagate_top_discarded_column
        else np.zeros(len(exact_products), dtype=np.uint64)
    )
    adjusted = (
        exact_products
        - corrections
        + ((retained_carry + np.uint64(bias_units)) << np.uint64(truncation_bits))
    )
    shifts = product_shifts(exact_products, output_bits)
    indices = adjusted >> shifts.astype(np.uint64)
    exponents = (
        np.asarray(multiplicand_exponents, dtype=np.int32)
        + np.asarray(multiplier_exponents, dtype=np.int32)
        + shifts
    )
    return indices, exponents


def first_stage_numerator(
    widths_fixed: np.ndarray,
    heights_fixed: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    delta_indices, delta_exponents = fixed_float_parts(widths_fixed)
    height_indices, height_exponents = fixed_float_parts(heights_fixed)
    return vector_product_stage(
        delta_indices,
        delta_exponents,
        height_indices,
        height_exponents,
        output_bits=coefficients.FIRST_STAGE_OUTPUT_BITS,
        truncation_bits=coefficients.FIRST_STAGE_TRUNCATION_BITS,
        bias_units=coefficients.CONSTANT_FIRST_STAGE_BIAS_UNITS,
    )


def reciprocal_stage(
    numerator_indices: np.ndarray,
    numerator_exponents: np.ndarray,
    reciprocals: np.ndarray,
    reciprocal_exponents: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    return vector_product_stage(
        numerator_indices,
        numerator_exponents,
        reciprocals,
        reciprocal_exponents,
        output_bits=coefficients.RECIPROCAL_STAGE_OUTPUT_BITS,
        truncation_bits=coefficients.RECIPROCAL_STAGE_TRUNCATION_BITS,
        bias_units=coefficients.RECIPROCAL_STAGE_BIAS_UNITS,
    )


def quantize_composite_constant_bits(values: np.ndarray) -> np.ndarray:
    """Apply exact P28-nearest followed by binary32-nearest rounding."""

    source = np.asarray(values, dtype=np.float64)
    magnitudes = np.abs(source)
    nonzero = magnitudes != 0
    binary_exponents = np.zeros(len(source), dtype=np.int32)
    binary_exponents[nonzero] = (
        np.frexp(magnitudes[nonzero])[1].astype(np.int32) - 1
    )
    steps = np.ldexp(
        np.ones(len(source), dtype=np.float64),
        binary_exponents - 27,
    )
    scaled = np.zeros(len(source), dtype=np.float64)
    scaled[nonzero] = magnitudes[nonzero] / steps[nonzero]
    internal = np.rint(scaled) * steps
    internal = np.copysign(internal, source)
    internal[~nonzero] = 0.0
    return internal.astype(np.float32).view(np.uint32)


def candidate_constant_bits(
    widths_fixed: np.ndarray,
    heights_fixed: np.ndarray,
    reciprocals: np.ndarray,
) -> np.ndarray:
    """Predict the centered pull at offset (0, 0.5) for one candidate."""

    widths = np.asarray(widths_fixed, dtype=np.uint64)
    heights = np.asarray(heights_fixed, dtype=np.uint64)
    numerator_indices, numerator_exponents = first_stage_numerator(
        widths,
        heights,
    )
    determinants = widths * heights
    determinant_bit_lengths = np.frexp(
        (determinants - np.uint64(1)).astype(np.float64)
    )[1].astype(np.int32)
    reciprocal_exponents = -determinant_bit_lengths - 8
    use_high_anchor = ((widths & 1) == 0) & ((heights & 1) == 0)
    origins_fixed = np.int64(SAMPLE_CENTER_X_FIXED) - (
        widths.astype(np.int64) // 2
    )
    anchors_fixed = origins_fixed + np.where(
        use_high_anchor,
        widths.astype(np.int64),
        0,
    )
    displacements_fixed = np.int64(TILE_ORIGIN_X_FIXED) - anchors_fixed
    distances_fixed = np.abs(displacements_fixed).astype(np.uint64)
    distance_indices, distance_exponents = fixed_float_parts(distances_fixed)
    middle_indices, middle_exponents = vector_product_stage(
        numerator_indices,
        numerator_exponents,
        distance_indices,
        distance_exponents,
        output_bits=coefficients.TILE_STAGE_OUTPUT_BITS,
        truncation_bits=coefficients.TILE_STAGE_TRUNCATION_BITS,
        bias_units=coefficients.TILE_STAGE_BIAS_UNITS,
        propagate_top_discarded_column=True,
    )
    term_indices, term_exponents = reciprocal_stage(
        middle_indices,
        middle_exponents,
        reciprocals,
        reciprocal_exponents,
    )
    anchors = np.where(
        use_high_anchor,
        widths.astype(np.float64),
        -widths.astype(np.float64),
    ) / 512.0
    terms = np.ldexp(
        term_indices.astype(np.float64),
        term_exponents,
    )
    terms = np.copysign(terms, displacements_fixed.astype(np.float64))
    return quantize_composite_constant_bits(anchors + terms)


def build(cases: np.memmap) -> JsonObject:
    if sys.byteorder != "little":
        raise RuntimeError("the frozen P25 preflight requires little endian")
    reciprocal_pair_digest = hashlib.sha256()
    constant_pair_digest = hashlib.sha256()
    lower_constant_digest = hashlib.sha256()
    upper_constant_digest = hashlib.sha256()
    distinct_count = 0
    failure_examples: list[JsonObject] = []

    for start in range(0, KEY_COUNT, BATCH_CASE_COUNT):
        stop = min(start + BATCH_CASE_COUNT, KEY_COUNT)
        keys = np.arange(KEY_LOWER + start, KEY_LOWER + stop, dtype=np.uint64)
        widths = np.asarray(cases[start:stop, 0], dtype=np.uint64)
        heights = np.asarray(cases[start:stop, 1], dtype=np.uint64)
        lower, upper = reciprocal_candidates(keys)
        lower_bits = candidate_constant_bits(widths, heights, lower)
        upper_bits = candidate_constant_bits(widths, heights, upper)
        exact_boundary = lower == upper
        distinct = lower_bits != upper_bits
        invalid = (~exact_boundary) & (~distinct)
        distinct_count += int(np.count_nonzero(distinct))
        if np.any(invalid) and len(failure_examples) < 32:
            for local_index in np.flatnonzero(invalid)[
                : 32 - len(failure_examples)
            ]:
                failure_examples.append(
                    {
                        "key": int(keys[local_index]),
                        "widthFixed": int(widths[local_index]),
                        "heightFixed": int(heights[local_index]),
                        "candidateReciprocals": [
                            int(lower[local_index]),
                            int(upper[local_index]),
                        ],
                        "candidateConstantBits": [
                            f"0x{int(lower_bits[local_index]):08x}",
                            f"0x{int(upper_bits[local_index]):08x}",
                        ],
                    }
                )
        reciprocal_pair_digest.update(
            np.column_stack((lower, upper)).astype("<u4", copy=False).tobytes()
        )
        constant_pair_digest.update(
            np.column_stack((lower_bits, upper_bits))
            .astype("<u4", copy=False)
            .tobytes()
        )
        lower_constant_digest.update(lower_bits.astype("<u4", copy=False).tobytes())
        upper_constant_digest.update(upper_bits.astype("<u4", copy=False).tobytes())
        if (stop // BATCH_CASE_COUNT) % 16 == 0 or stop == KEY_COUNT:
            print(f"p25-witness: {stop}/{KEY_COUNT}", flush=True)

    if failure_examples or distinct_count != KEY_COUNT - 1:
        raise ValueError(
            f"P25 centered witness failed: distinct={distinct_count}; "
            f"examples={failure_examples}"
        )
    return {
        "rasterP25SelectorWitnessSchemaVersion": 1,
        "classification": (
            "input-only exhaustive centered-witness preflight; no Apple output "
            "observed"
        ),
        "domain": {
            "keyLowerInclusive": KEY_LOWER,
            "keyUpperExclusive": KEY_UPPER,
            "keyCount": KEY_COUNT,
            "caseFileSha256": CASE_SHA256,
            "reciprocalCandidates": (
                "floor and ceil of 2^49/key, with the exact power boundary "
                "represented as 2^24 at the next reciprocal exponent"
            ),
            "candidateReciprocalPairSha256": reciprocal_pair_digest.hexdigest(),
        },
        "witness": {
            "endpointRamp": "[-width/2,+width/2] in exact binary32",
            "endpointMultiplierBits": f"0x{ENDPOINT_MULTIPLIER_BITS:08x}",
            "samplePixel": [SAMPLE_X, SAMPLE_Y],
            "pullOffset": list(PULL_OFFSET),
            "candidateConstantPairSha256": constant_pair_digest.hexdigest(),
            "lowerCandidateConstantSha256": lower_constant_digest.hexdigest(),
            "upperCandidateConstantSha256": upper_constant_digest.hexdigest(),
            "candidateConstantDistinctCount": distinct_count,
            "exactPowerBoundaryCount": KEY_COUNT - distinct_count,
            "everyNonBoundaryCandidateMultiplicity": 1,
        },
        "capture": {
            "batchCaseCount": BATCH_CASE_COUNT,
            "recordBytes": 4,
            "recordCount": KEY_COUNT,
            "rawBytes": KEY_COUNT * 4,
            "ordering": "ascending normalized-P25 key",
        },
        "capturedAppleOutputUsed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args()
    report = build(load_cases(arguments.cases))
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.report is not None:
        arguments.report.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
