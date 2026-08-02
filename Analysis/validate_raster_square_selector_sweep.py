#!/usr/bin/env python3
"""Resolve every production-range square AGX reciprocal selector exactly."""

import argparse
import hashlib
import json
import math
import struct
import zlib
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

import raster_tile_coefficient_model as coefficient_base
import raster_tile_coefficient_model_v3 as coefficients
import raster_tile_selector_model as arithmetic
import raster_tile_selector_model_v4 as composite


type JsonObject = dict[str, Any]

RIG_VERSION = "metal-raster-square-selector-sweep-1.0.0"
ROLE = "production-square-fixed-grid-reciprocal-selector-calibration"
PREREGISTRATION = Path(__file__).with_name(
    "raster_square_selector_sweep_preregistration.json"
)
WIDTH_FIXED_LOWER = 196_608
WIDTH_FIXED_UPPER = 229_376
FIXED_UNITS_PER_PIXEL = 256
ORIGIN_FIXED = 64 * FIXED_UNITS_PER_PIXEL
SAMPLE_X = 448
SAMPLE_Y = 449
TILE_SIZE = 32
TILE = SAMPLE_X // TILE_SIZE
LOCAL_PIXEL = SAMPLE_X - TILE * TILE_SIZE
PULL_PHASES = (0.0, 15.0 / 16.0)
CASE_COUNT = WIDTH_FIXED_UPPER - WIDTH_FIXED_LOWER + 1
RECORD = struct.Struct("<II")
RAW_BYTES = CASE_COUNT * RECORD.size
RAW_FILE = "raster-square-selector-sweep.raw"
SELECTOR_FILE = "raster-square-selectors-u32le.zlib"
BRANCH_FILE = "raster-square-selector-branches.bin"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def power_of_two(exponent: int) -> Fraction:
    return arithmetic.power_of_two(exponent)


def endpoint_bits(width_fixed: int) -> tuple[int, int]:
    half = Fraction(width_fixed, 2 * FIXED_UNITS_PER_PIXEL)
    return (
        arithmetic.round_fraction_to_float32_bits(-half),
        arithmetic.round_fraction_to_float32_bits(half),
    )


def first_stage_numerator(
    width_fixed: int,
    *,
    bias_units: int,
) -> tuple[int, int]:
    low_bits, high_bits = endpoint_bits(width_fixed)
    delta = arithmetic.float32(
        arithmetic.bits_float32(high_bits)
        - arithmetic.bits_float32(low_bits)
    )
    delta_index, delta_exponent = arithmetic.float_significand_and_lsb_exponent(
        arithmetic.float32_bits(delta)
    )
    opposite_bits = arithmetic.round_fraction_to_float32_bits(
        Fraction(width_fixed, FIXED_UNITS_PER_PIXEL)
    )
    opposite_index, opposite_exponent = (
        arithmetic.float_significand_and_lsb_exponent(opposite_bits)
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


def reciprocal_exponent(width_fixed: int) -> int:
    determinant_fixed = width_fixed * width_fixed
    return (
        -(determinant_fixed - 1).bit_length()
        - 24
        + 2 * FIXED_UNITS_PER_PIXEL.bit_length()
        - 2
    )


def reciprocal_candidates(width_fixed: int) -> tuple[int, ...]:
    determinant_fixed = width_fixed * width_fixed
    exponent = reciprocal_exponent(width_fixed)
    exact = (
        Fraction(FIXED_UNITS_PER_PIXEL * FIXED_UNITS_PER_PIXEL, determinant_fixed)
        / power_of_two(exponent)
    )
    lower, remainder = divmod(exact.numerator, exact.denominator)
    return (lower,) if remainder == 0 else (lower, lower + 1)


def reciprocal_stage(
    index: int,
    exponent: int,
    *,
    reciprocal_index: int,
    reciprocal_lsb_exponent: int,
) -> tuple[int, int]:
    return arithmetic.product_stage(
        index,
        exponent,
        reciprocal_index,
        reciprocal_lsb_exponent,
        output_bits=coefficient_base.RECIPROCAL_STAGE_OUTPUT_BITS,
        truncation_bits=coefficients.MEASURED_POLICY.reciprocal_truncation_bits,
        bias_units=coefficients.MEASURED_POLICY.reciprocal_bias,
    )


def slope(
    width_fixed: int,
    *,
    reciprocal_index: int,
) -> float:
    numerator_index, numerator_exponent = first_stage_numerator(
        width_fixed,
        bias_units=coefficients.MEASURED_POLICY.slope_first_bias,
    )
    index, exponent = reciprocal_stage(
        numerator_index,
        numerator_exponent,
        reciprocal_index=reciprocal_index,
        reciprocal_lsb_exponent=reciprocal_exponent(width_fixed),
    )
    return arithmetic.float32(math.ldexp(index, exponent))


def constant_bits(
    width_fixed: int,
    *,
    reciprocal_index: int,
) -> int:
    numerator_index, numerator_exponent = first_stage_numerator(
        width_fixed,
        bias_units=coefficients.MEASURED_POLICY.constant_first_bias,
    )
    displacement_fixed = (
        TILE * TILE_SIZE * FIXED_UNITS_PER_PIXEL - ORIGIN_FIXED
    )
    distance_bits = arithmetic.round_fraction_to_float32_bits(
        Fraction(displacement_fixed, FIXED_UNITS_PER_PIXEL)
    )
    distance_index, distance_exponent = (
        arithmetic.float_significand_and_lsb_exponent(distance_bits)
    )
    middle_index, middle_exponent = coefficients.column_product_stage(
        numerator_index,
        numerator_exponent,
        distance_index,
        distance_exponent,
        output_bits=coefficient_base.TILE_STAGE_OUTPUT_BITS,
        truncation_bits=coefficients.MEASURED_POLICY.tile_truncation_bits,
        bias_units=coefficients.MEASURED_POLICY.tile_bias,
        carry_mode=coefficients.MEASURED_POLICY.tile_carry_mode,
        propagated_column_count=(
            coefficients.MEASURED_POLICY.tile_propagated_column_count
        ),
        sticky_carry_limit=(
            coefficients.MEASURED_POLICY.tile_sticky_carry_limit
        ),
    )
    index, exponent = reciprocal_stage(
        middle_index,
        middle_exponent,
        reciprocal_index=reciprocal_index,
        reciprocal_lsb_exponent=reciprocal_exponent(width_fixed),
    )
    low_bits, _ = endpoint_bits(width_fixed)
    value = (
        arithmetic.float32_bits_fraction(low_bits)
        + Fraction(index) * power_of_two(exponent)
    )
    return composite.quantize_composite_constant_bits(value)


def prediction(
    width_fixed: int,
    *,
    reciprocal_index: int,
) -> tuple[int, int]:
    setup_slope = slope(width_fixed, reciprocal_index=reciprocal_index)
    constant = arithmetic.bits_float32(
        constant_bits(width_fixed, reciprocal_index=reciprocal_index)
    )
    return tuple(
        arithmetic.float32_bits(
            arithmetic.float32(
                math.fma(LOCAL_PIXEL + phase, setup_slope, constant)
            )
        )
        for phase in PULL_PHASES
    )  # type: ignore[return-value]


def candidate_stream() -> tuple[bytes, int]:
    stream = bytearray()
    distinct = 0
    for width_fixed in range(WIDTH_FIXED_LOWER, WIDTH_FIXED_UPPER + 1):
        candidates = reciprocal_candidates(width_fixed)
        records = [
            prediction(width_fixed, reciprocal_index=selector)
            for selector in candidates
        ]
        for record in records:
            stream.extend(RECORD.pack(*record))
        if len(records) == 1 or records[0] != records[1]:
            distinct += 1
    return bytes(stream), distinct


def validate_manifest(root: Path) -> tuple[JsonObject, Path]:
    preregistration_bytes = PREREGISTRATION.read_bytes()
    preregistration = json.loads(preregistration_bytes)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = manifest.get("rasterSquareSelectorSweep")
    raw_path = root / RAW_FILE
    if (
        manifest.get("schemaVersion") != 1
        or manifest.get("rigVersion") != RIG_VERSION
        or not isinstance(record, dict)
        or record.get("role") != ROLE
        or record.get("preregistrationFile")
        != "Analysis/raster_square_selector_sweep_preregistration.json"
        or record.get("preregistrationSha256")
        != sha256_bytes(preregistration_bytes)
        or preregistration.get("role") != ROLE
        or record.get("widthFixedLower") != WIDTH_FIXED_LOWER
        or record.get("widthFixedUpper") != WIDTH_FIXED_UPPER
        or record.get("fixedUnitsPerPixel") != FIXED_UNITS_PER_PIXEL
        or record.get("caseCount") != CASE_COUNT
        or record.get("origin") != [64, 64]
        or record.get("targetSize") != [1024, 1024]
        or record.get("samplePixel") != [SAMPLE_X, SAMPLE_Y]
        or record.get("pullOffsets") != [[0.0, 0.5], [0.9375, 0.5]]
        or record.get("ordering") != "ascending-width-fixed"
        or record.get("recordBytes") != RECORD.size
        or record.get("coverage") != CASE_COUNT
        or record.get("file") != RAW_FILE
        or record.get("bytes") != RAW_BYTES
        or not raw_path.is_file()
        or raw_path.stat().st_size != RAW_BYTES
        or record.get("sha256") != sha256_path(raw_path)
    ):
        raise ValueError("square selector manifest differs")
    return manifest, raw_path


def validate(root: Path) -> tuple[JsonObject, bytes, bytes]:
    manifest, raw_path = validate_manifest(root)
    raw = raw_path.read_bytes()
    candidate_bytes, distinct_count = candidate_stream()
    preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    preflight = preregistration.get("preflight")
    if (
        not isinstance(preflight, dict)
        or preflight.get("candidateStreamSha256")
        != sha256_bytes(candidate_bytes)
        or preflight.get("candidateDistinctCaseCount") != CASE_COUNT
        or distinct_count != CASE_COUNT
    ):
        raise ValueError("square selector preflight differs")

    selectors: list[int] = []
    branch_bits = bytearray((CASE_COUNT + 7) // 8)
    branch_counts: Counter[str] = Counter()
    failures: list[JsonObject] = []
    for case_index, width_fixed in enumerate(
        range(WIDTH_FIXED_LOWER, WIDTH_FIXED_UPPER + 1)
    ):
        observed = RECORD.unpack_from(raw, case_index * RECORD.size)
        candidates = reciprocal_candidates(width_fixed)
        predictions = [
            prediction(width_fixed, reciprocal_index=selector)
            for selector in candidates
        ]
        matches = [
            index
            for index, predicted in enumerate(predictions)
            if predicted == observed
        ]
        if len(matches) != 1:
            if len(failures) < 32:
                failures.append(
                    {
                        "widthFixed": width_fixed,
                        "observed": [f"0x{word:08x}" for word in observed],
                        "selectors": candidates,
                        "predictions": [
                            [f"0x{word:08x}" for word in record]
                            for record in predictions
                        ],
                        "matchingCandidateIndices": matches,
                    }
                )
            continue
        selected_index = matches[0]
        selector = candidates[selected_index]
        selectors.append(selector)
        branch = "exact" if len(candidates) == 1 else (
            "floor" if selected_index == 0 else "ceil"
        )
        branch_counts[branch] += 1
        if selected_index == 1:
            branch_bits[case_index // 8] |= 1 << (case_index % 8)

    if failures or len(selectors) != CASE_COUNT:
        raise ValueError(
            f"square selector recovery failed: {len(failures)} examples; "
            f"selected={len(selectors)}/{CASE_COUNT}"
        )
    selector_raw = struct.pack(f"<{len(selectors)}I", *selectors)
    selector_archive = zlib.compress(selector_raw, level=9)
    report: JsonObject = {
        "rasterSquareSelectorValidationSchemaVersion": 1,
        "classification": (
            "complete production-range square fixed-grid calibration; "
            "not yet a prospective transfer validation"
        ),
        "manifest": str(root / "manifest.json"),
        "ciCommit": manifest.get("ciCommit"),
        "domain": {
            "widthFixedLower": WIDTH_FIXED_LOWER,
            "widthFixedUpper": WIDTH_FIXED_UPPER,
            "fixedUnitsPerPixel": FIXED_UNITS_PER_PIXEL,
            "caseCount": CASE_COUNT,
            "determinant": "widthFixed squared",
        },
        "input": {
            "raw": str(raw_path),
            "rawBytes": len(raw),
            "rawSha256": sha256_bytes(raw),
        },
        "preflight": {
            "candidateStreamBytes": len(candidate_bytes),
            "candidateStreamSha256": sha256_bytes(candidate_bytes),
            "candidateDistinctCaseCount": distinct_count,
        },
        "selectors": {
            "file": SELECTOR_FILE,
            "rawBytes": len(selector_raw),
            "rawSha256": sha256_bytes(selector_raw),
            "compressedBytes": len(selector_archive),
            "compressedSha256": sha256_bytes(selector_archive),
            "dtype": "little-endian uint32",
            "ordering": "ascending-width-fixed",
            "branchBitsetFile": BRANCH_FILE,
            "branchBitsetBytes": len(branch_bits),
            "branchBitsetSha256": sha256_bytes(branch_bits),
            "branchBitOrdering": "LSB-first; one means ceil",
        },
        "measurement": {
            "caseCount": CASE_COUNT,
            "uniqueSelectorCount": len(set(selectors)),
            "branchCounts": dict(sorted(branch_counts.items())),
            "matchedCaseCount": len(selectors),
            "mismatchedCaseCount": 0,
            "ambiguousCaseCount": 0,
            "exact": True,
        },
        "gate": {
            "calibrationComplete": True,
            "portableClosedFormEstablished": False,
            "prospectiveTransferPassed": False,
            "productionParityAuthorized": False,
        },
    }
    return report, selector_archive, bytes(branch_bits)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report, selectors, branches = validate(arguments.root)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    (arguments.output.parent / SELECTOR_FILE).write_bytes(selectors)
    (arguments.output.parent / BRANCH_FILE).write_bytes(branches)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["measurement"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
