#!/usr/bin/env python3
"""Recover AGX reciprocal selectors for preregistered near-square quads."""

import argparse
import hashlib
import json
import math
import struct
import zlib
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import raster_tile_coefficient_model as coefficient_base
import raster_tile_coefficient_model_v3 as coefficients
import raster_tile_selector_model as arithmetic
import raster_tile_selector_model_v4 as composite


type JsonObject = dict[str, Any]

RIG_VERSION = "metal-raster-near-square-selector-sweep-1.0.0"
ROLE = "production-near-square-fixed-grid-reciprocal-selector-calibration"
PREREGISTRATION = Path(__file__).with_name(
    "raster_near_square_selector_sweep_preregistration.json"
)
WIDTH_FIXED_LOWER = 196_608
WIDTH_FIXED_UPPER = 229_376
HEIGHT_DELTAS = (
    -256,
    -128,
    -64,
    -32,
    -16,
    -8,
    -4,
    -2,
    -1,
    1,
    2,
    4,
    8,
    16,
    32,
    64,
    128,
    256,
)
RECOVERY_OFFSETS = (-2, -1, 0, 1, 2, 3)
FIXED_UNITS_PER_PIXEL = 256
ORIGIN_FIXED = 64 * FIXED_UNITS_PER_PIXEL
SAMPLE_X = 448
SAMPLE_Y = 449
TILE_SIZE = 32
TILE = SAMPLE_X // TILE_SIZE
LOCAL_PIXEL = SAMPLE_X - TILE * TILE_SIZE
PULL_PHASES = (0.0, 15.0 / 16.0)
WIDTH_COUNT = WIDTH_FIXED_UPPER - WIDTH_FIXED_LOWER + 1
CASE_COUNT = WIDTH_COUNT * len(HEIGHT_DELTAS)
RECORD = struct.Struct("<II")
RAW_BYTES = CASE_COUNT * RECORD.size
RAW_FILE = "raster-near-square-selector-sweep.raw"
SELECTOR_FILE = "raster-near-square-selectors-u32le.zlib"
OFFSET_FILE = "raster-near-square-selector-offsets-i8.bin"


@dataclass(frozen=True, slots=True)
class PredictionContext:
    slopeNumeratorIndex: int
    slopeNumeratorExponent: int
    constantNumeratorIndex: int
    constantNumeratorExponent: int
    reciprocalExponent: int
    anchor: Fraction
    displacementSign: int


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
    height_fixed: int,
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
        Fraction(height_fixed, FIXED_UNITS_PER_PIXEL)
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


def reciprocal_exponent(width_fixed: int, height_fixed: int) -> int:
    determinant_fixed = width_fixed * height_fixed
    return (
        -(determinant_fixed - 1).bit_length()
        - 24
        + 2 * FIXED_UNITS_PER_PIXEL.bit_length()
        - 2
    )


def exact_floor_selector(width_fixed: int, height_fixed: int) -> int:
    determinant_fixed = width_fixed * height_fixed
    exponent = reciprocal_exponent(width_fixed, height_fixed)
    exact = (
        Fraction(FIXED_UNITS_PER_PIXEL * FIXED_UNITS_PER_PIXEL, determinant_fixed)
        / power_of_two(exponent)
    )
    return exact.numerator // exact.denominator


def selector_candidates(width_fixed: int, height_fixed: int) -> tuple[int, ...]:
    floor = exact_floor_selector(width_fixed, height_fixed)
    return tuple(floor + offset for offset in RECOVERY_OFFSETS)


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


def prediction_context(
    width_fixed: int,
    height_fixed: int,
) -> PredictionContext:
    slope_index, slope_exponent = first_stage_numerator(
        width_fixed,
        height_fixed,
        bias_units=coefficients.MEASURED_POLICY.slope_first_bias,
    )
    constant_index, constant_exponent = first_stage_numerator(
        width_fixed,
        height_fixed,
        bias_units=coefficients.MEASURED_POLICY.constant_first_bias,
    )
    use_high_anchor = anchor_high(width_fixed, height_fixed)
    anchor_fixed = ORIGIN_FIXED + (width_fixed if use_high_anchor else 0)
    displacement_fixed = TILE * TILE_SIZE * FIXED_UNITS_PER_PIXEL - anchor_fixed
    distance_bits = arithmetic.round_fraction_to_float32_bits(
        Fraction(abs(displacement_fixed), FIXED_UNITS_PER_PIXEL)
    )
    distance_index, distance_exponent = (
        arithmetic.float_significand_and_lsb_exponent(distance_bits)
    )
    middle_index, middle_exponent = coefficients.column_product_stage(
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
        sticky_carry_limit=coefficients.MEASURED_POLICY.tile_sticky_carry_limit,
    )
    low_bits, high_bits = endpoint_bits(width_fixed)
    return PredictionContext(
        slopeNumeratorIndex=slope_index,
        slopeNumeratorExponent=slope_exponent,
        constantNumeratorIndex=middle_index,
        constantNumeratorExponent=middle_exponent,
        reciprocalExponent=reciprocal_exponent(width_fixed, height_fixed),
        anchor=arithmetic.float32_bits_fraction(
            high_bits if use_high_anchor else low_bits
        ),
        displacementSign=-1 if displacement_fixed < 0 else 1,
    )


def anchor_high(width_fixed: int, height_fixed: int) -> bool:
    """Return the X anchor selected by the captured descending diagonal."""

    half = FIXED_UNITS_PER_PIXEL // 2
    relative_x = SAMPLE_X * FIXED_UNITS_PER_PIXEL + half - ORIGIN_FIXED
    relative_y = SAMPLE_Y * FIXED_UNITS_PER_PIXEL + half - ORIGIN_FIXED
    primitive = int(
        relative_x * height_fixed + relative_y * width_fixed
        < width_fixed * height_fixed
    )
    return primitive == 0


def prediction(
    context: PredictionContext,
    *,
    reciprocal_index: int,
) -> tuple[int, int]:
    slope_index, slope_exponent = reciprocal_stage(
        context.slopeNumeratorIndex,
        context.slopeNumeratorExponent,
        reciprocal_index=reciprocal_index,
        reciprocal_lsb_exponent=context.reciprocalExponent,
    )
    setup_slope = arithmetic.float32(math.ldexp(slope_index, slope_exponent))
    constant_index, constant_exponent = reciprocal_stage(
        context.constantNumeratorIndex,
        context.constantNumeratorExponent,
        reciprocal_index=reciprocal_index,
        reciprocal_lsb_exponent=context.reciprocalExponent,
    )
    constant = arithmetic.bits_float32(
        composite.quantize_composite_constant_bits(
            context.anchor
            + context.displacementSign
            * Fraction(constant_index)
            * power_of_two(constant_exponent)
        )
    )
    return tuple(
        arithmetic.float32_bits(
            arithmetic.float32(
                math.fma(LOCAL_PIXEL + phase, setup_slope, constant)
            )
        )
        for phase in PULL_PHASES
    )  # type: ignore[return-value]


def cases():
    for height_delta in HEIGHT_DELTAS:
        for width_fixed in range(WIDTH_FIXED_LOWER, WIDTH_FIXED_UPPER + 1):
            yield width_fixed, width_fixed + height_delta, height_delta


def preflight_metadata() -> JsonObject:
    digest = hashlib.sha256()
    distinct = 0
    for width_fixed, height_fixed, _ in cases():
        context = prediction_context(width_fixed, height_fixed)
        records = []
        for selector in selector_candidates(width_fixed, height_fixed):
            record = prediction(
                context,
                reciprocal_index=selector,
            )
            records.append(record)
            digest.update(RECORD.pack(*record))
        distinct += len(set(records)) == len(records)
    return {
        "candidateStreamBytes": (
            CASE_COUNT * len(RECOVERY_OFFSETS) * RECORD.size
        ),
        "candidateStreamSha256": digest.hexdigest(),
        "candidateDistinctCaseCount": distinct,
        "candidateMultiplicityPerCase": len(RECOVERY_OFFSETS),
        "allCasesDistinguishable": distinct == CASE_COUNT,
    }


def validate_manifest(root: Path) -> tuple[JsonObject, Path]:
    preregistration_bytes = PREREGISTRATION.read_bytes()
    preregistration = json.loads(preregistration_bytes)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = manifest.get("rasterNearSquareSelectorSweep")
    raw_path = root / RAW_FILE
    if (
        manifest.get("schemaVersion") != 1
        or manifest.get("rigVersion") != RIG_VERSION
        or not isinstance(record, dict)
        or record.get("role") != ROLE
        or record.get("preregistrationFile")
        != "Analysis/raster_near_square_selector_sweep_preregistration.json"
        or record.get("preregistrationSha256")
        != sha256_bytes(preregistration_bytes)
        or preregistration.get("role") != ROLE
        or record.get("widthFixedLower") != WIDTH_FIXED_LOWER
        or record.get("widthFixedUpper") != WIDTH_FIXED_UPPER
        or record.get("heightFixedDeltas") != list(HEIGHT_DELTAS)
        or record.get("fixedUnitsPerPixel") != FIXED_UNITS_PER_PIXEL
        or record.get("widthCount") != WIDTH_COUNT
        or record.get("caseCount") != CASE_COUNT
        or record.get("origin") != [64, 64]
        or record.get("targetSize") != [1024, 1024]
        or record.get("samplePixel") != [SAMPLE_X, SAMPLE_Y]
        or record.get("pullOffsets") != [[0.0, 0.5], [0.9375, 0.5]]
        or record.get("ordering") != "height-delta-major,width-fixed-minor"
        or record.get("recordBytes") != RECORD.size
        or record.get("coverage") != CASE_COUNT
        or record.get("file") != RAW_FILE
        or record.get("bytes") != RAW_BYTES
        or not raw_path.is_file()
        or raw_path.stat().st_size != RAW_BYTES
        or record.get("sha256") != sha256_path(raw_path)
    ):
        raise ValueError("near-square selector manifest differs")
    return manifest, raw_path


def validate(root: Path) -> tuple[JsonObject, bytes | None, bytes | None]:
    manifest, raw_path = validate_manifest(root)
    raw = raw_path.read_bytes()
    preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    floor_matched = 0
    candidate_digest = hashlib.sha256()
    candidate_distinct = 0
    selectors: list[int] = []
    selector_offsets: list[int] = []
    offset_counts: Counter[int] = Counter()
    delta_offset_counts: dict[int, Counter[int]] = {
        delta: Counter() for delta in HEIGHT_DELTAS
    }
    failures: list[JsonObject] = []
    ambiguous = 0
    for case_index, (width_fixed, height_fixed, height_delta) in enumerate(cases()):
        observed = RECORD.unpack_from(raw, case_index * RECORD.size)
        floor = exact_floor_selector(width_fixed, height_fixed)
        context = prediction_context(width_fixed, height_fixed)
        candidates = selector_candidates(width_fixed, height_fixed)
        predictions = [
            prediction(
                context,
                reciprocal_index=selector,
            )
            for selector in candidates
        ]
        for candidate in predictions:
            candidate_digest.update(RECORD.pack(*candidate))
        candidate_distinct += len(set(predictions)) == len(predictions)
        floor_matched += predictions[RECOVERY_OFFSETS.index(0)] == observed
        matches = [
            index
            for index, predicted in enumerate(predictions)
            if predicted == observed
        ]
        if len(matches) != 1:
            ambiguous += len(matches) > 1
            if len(failures) < 32:
                failures.append(
                    {
                        "widthFixed": width_fixed,
                        "heightFixed": height_fixed,
                        "heightDelta": height_delta,
                        "observed": [f"0x{word:08x}" for word in observed],
                        "selectors": list(candidates),
                        "matchingCandidateIndices": matches,
                    }
                )
            continue
        selector = candidates[matches[0]]
        offset = selector - floor
        selectors.append(selector)
        selector_offsets.append(offset)
        offset_counts[offset] += 1
        delta_offset_counts[height_delta][offset] += 1

    measured_preflight = {
        "candidateStreamBytes": (
            CASE_COUNT * len(RECOVERY_OFFSETS) * RECORD.size
        ),
        "candidateStreamSha256": candidate_digest.hexdigest(),
        "candidateDistinctCaseCount": candidate_distinct,
        "candidateMultiplicityPerCase": len(RECOVERY_OFFSETS),
        "allCasesDistinguishable": candidate_distinct == CASE_COUNT,
    }
    if preregistration.get("preflight") != measured_preflight:
        raise ValueError("near-square selector preflight differs")

    complete = len(selectors) == CASE_COUNT and not failures and ambiguous == 0
    selector_raw = (
        struct.pack(f"<{len(selectors)}I", *selectors) if complete else None
    )
    offset_raw = (
        struct.pack(f"<{len(selector_offsets)}b", *selector_offsets)
        if complete
        else None
    )
    selector_archive = (
        zlib.compress(selector_raw, level=9) if selector_raw is not None else None
    )
    report: JsonObject = {
        "rasterNearSquareSelectorValidationSchemaVersion": 1,
        "classification": (
            "preregistered finite-domain near-square calibration; "
            "not a universal reciprocal closed form"
        ),
        "manifest": str(root / "manifest.json"),
        "ciCommit": manifest.get("ciCommit"),
        "domain": {
            "widthFixedLower": WIDTH_FIXED_LOWER,
            "widthFixedUpper": WIDTH_FIXED_UPPER,
            "heightFixedDeltas": list(HEIGHT_DELTAS),
            "fixedUnitsPerPixel": FIXED_UNITS_PER_PIXEL,
            "caseCount": CASE_COUNT,
            "determinant": "widthFixed * heightFixed",
        },
        "input": {
            "raw": str(raw_path),
            "rawBytes": len(raw),
            "rawSha256": sha256_bytes(raw),
        },
        "frozenExactFloorHypothesis": {
            "matchedCaseCount": floor_matched,
            "mismatchedCaseCount": CASE_COUNT - floor_matched,
            "exact": floor_matched == CASE_COUNT,
        },
        "predeclaredRecovery": {
            "selectorOffsetsFromExactFloor": list(RECOVERY_OFFSETS),
            "matchedCaseCount": len(selectors),
            "mismatchedCaseCount": CASE_COUNT - len(selectors),
            "ambiguousCaseCount": ambiguous,
            "exact": complete,
            "selectorOffsetCounts": {
                str(offset): count for offset, count in sorted(offset_counts.items())
            },
            "selectorOffsetCountsByHeightDelta": {
                str(delta): {
                    str(offset): count
                    for offset, count in sorted(counts.items())
                }
                for delta, counts in delta_offset_counts.items()
            },
            "failureExamples": failures,
        },
        "selectors": (
            {
                "file": SELECTOR_FILE,
                "rawBytes": len(selector_raw),
                "rawSha256": sha256_bytes(selector_raw),
                "compressedBytes": len(selector_archive),
                "compressedSha256": sha256_bytes(selector_archive),
                "dtype": "little-endian uint32",
                "ordering": "height-delta-major,width-fixed-minor",
                "offsetFile": OFFSET_FILE,
                "offsetBytes": len(offset_raw),
                "offsetSha256": sha256_bytes(offset_raw),
                "offsetDtype": "signed int8 relative to exact floor",
            }
            if selector_raw is not None
            and selector_archive is not None
            and offset_raw is not None
            else None
        ),
        "measurement": {
            "caseCount": CASE_COUNT,
            "matchedCaseCount": len(selectors),
            "mismatchedCaseCount": CASE_COUNT - len(selectors),
            "ambiguousCaseCount": ambiguous,
            "calibrationComplete": complete,
        },
        "gate": {
            "calibrationComplete": complete,
            "frozenExactFloorHypothesisPassed": floor_matched == CASE_COUNT,
            "portableClosedFormEstablished": False,
            "prospectiveTransferPassed": False,
            "productionParityAuthorized": False,
        },
    }
    return report, selector_archive, offset_raw


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report, selectors, offsets = validate(arguments.root)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    if selectors is not None and offsets is not None:
        (arguments.output.parent / SELECTOR_FILE).write_bytes(selectors)
        (arguments.output.parent / OFFSET_FILE).write_bytes(offsets)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["measurement"], sort_keys=True))
    return 0 if report["gate"]["calibrationComplete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
