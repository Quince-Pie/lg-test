#!/usr/bin/env python3
"""Validate the power-of-two-viewport general-height diagnostic corpus."""

import argparse
import hashlib
import json
import math
import struct
from collections import Counter
from pathlib import Path
from typing import Any

import validate_reciprocal_factorized_transfer as factorized
import validate_reciprocal_general_height_transfer as failed_general


type JsonObject = dict[str, Any]

arithmetic = factorized.arithmetic
SCHEMA_VERSION = 2
RIG_VERSION = "metal-raster-general-height-diagnostic-2.0.0"
ROLE = "discovery-with-preregistered-calibrated-determinant-controls"
TARGET_WIDTH = 288
TARGET_HEIGHT = 256
VIEWPORT_WIDTH = 32_768
GEOMETRY_COUNT = 4
SAMPLE_SIDE_COUNT = 2
RECORD = struct.Struct("<4I")
RAW_BYTES = (
    factorized.WIDTH_COUNT
    * len(arithmetic.WITNESS_SIGNIFICANDS)
    * GEOMETRY_COUNT
    * SAMPLE_SIDE_COUNT
    * RECORD.size
)
SENTINEL = (0xFFFF_FFFF,) * 4
PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_general_height_diagnostic_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "2e9db3b82a74b0da3761cd19125e1228cc60af9cc08902ddba32a8213aa19002"
)
CONTROL_PAIR_COUNT = 484
CONTROL_COEFFICIENT_COUNT = CONTROL_PAIR_COUNT * len(arithmetic.WITNESS_SIGNIFICANDS)
CONTROL_PAIRS_SHA256 = (
    "5009c0ef63b8c7ea107727537bab3c633d685b2474b0e91d957e3fffe93d9af9"
)
CONTROL_RECIPROCALS_SHA256 = (
    "4de707bf7d8e9469537e648d35b6c0f75c843207c91f387d023e16812be2c971"
)
CONTROL_COEFFICIENTS_SHA256 = (
    "6ac1220a2e7884df9655689f84e064ccabef206f3c7135329cfea8820d7db434"
)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def uint32_sha256(values: list[int]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(struct.pack("<I", value))
    return digest.hexdigest()


def float_significand_and_lsb_exponent(bits: int) -> tuple[int, int]:
    exponent = (bits >> 23) & 0xFF
    if bits >> 31 or not 0 < exponent < 0xFF:
        raise ValueError("positive normal binary32 required")
    return (1 << 23) | (bits & 0x7F_FFFF), exponent - 127 - 23


def generalized_physical_product_bits(
    *,
    numerator_bits: int,
    denominator: int,
    reciprocal: int,
) -> int:
    significand, lsb_exponent = float_significand_and_lsb_exponent(numerator_bits)
    exact_product = significand * reciprocal
    product_shift = exact_product.bit_length() - 27
    truncated_product = sum(
        ((significand << bit) >> 16) << 16
        for bit in range(reciprocal.bit_length())
        if reciprocal & (1 << bit)
    )
    product_index = (truncated_product + 0x14_0000) >> product_shift
    reciprocal_exponent = -(denominator - 1).bit_length()
    return arithmetic.float32_bits(
        math.ldexp(
            product_index,
            lsb_exponent + reciprocal_exponent - 24 + product_shift,
        )
    )


def calibrated_normalized_class(area: int) -> int | None:
    shift = area.bit_length() - 14
    if shift <= 0:
        normalized = area << -shift
    else:
        normalized, remainder = divmod(area, 1 << shift)
        if remainder:
            return None
    if (
        not factorized.NORMALIZED_DENOMINATOR_LOWER
        <= normalized
        <= (factorized.NORMALIZED_DENOMINATOR_UPPER)
    ):
        raise ValueError("normalized determinant class is outside calibration")
    return normalized


def sample_position(
    width: int,
    geometry: JsonObject,
    sample_side: int,
) -> JsonObject:
    x = (
        int(geometry["sampleAnchorX"]) + int(geometry["sampleMarginX"])
        if sample_side == 0
        else int(geometry["sampleAnchorX"]) - int(geometry["sampleMarginX"])
    )
    y = int(geometry["originY"]) + int(geometry["sampleLocalY"])
    signed_interior = int(geometry["height"]) * (2 * x + 1) - width
    if (
        sample_side not in range(SAMPLE_SIDE_COUNT)
        or not 0 <= x < TARGET_WIDTH
        or not 0 <= y < TARGET_HEIGHT
        or int(geometry["originY"]) + int(geometry["height"]) > TARGET_HEIGHT
        or signed_interior <= failed_general.MINIMUM_SIGNED_INTERIOR_AREA
    ):
        raise ValueError("diagnostic sample is not safely interior")
    return {
        "x": x,
        "y": y,
        "tile": x // 32,
        "tileLocalX": x % 32,
        "signedInteriorArea": signed_interior,
    }


def control_tables() -> tuple[list[int], list[int], list[int]]:
    canonical = factorized.canonical_reciprocals()
    pair_words: list[int] = []
    reciprocals: list[int] = []
    coefficients: list[int] = []
    widths = factorized.geometry_widths()
    shifts = factorized.delta_exponent_shift_bits()
    for width_index, width in enumerate(widths):
        controls_for_width: list[tuple[int, int, int] | None] = []
        for geometry in failed_general.GEOMETRY_CASES:
            height = int(geometry["height"])
            area = width * height
            normalized = calibrated_normalized_class(area)
            if normalized is None:
                controls_for_width.append(None)
                continue
            reciprocal = canonical[normalized - factorized.NORMALIZED_DENOMINATOR_LOWER]
            pair_words.extend((width, height))
            reciprocals.append(reciprocal)
            controls_for_width.append((height, area, reciprocal))
        for delta_bits in arithmetic.witness_delta_bits():
            for control in controls_for_width:
                if control is None:
                    continue
                height, area, reciprocal = control
                scaled_bits = delta_bits - shifts[width_index]
                scaled_value = arithmetic.float32_value(scaled_bits)
                numerator_bits = arithmetic.float32_bits(scaled_value * height)
                coefficients.append(
                    generalized_physical_product_bits(
                        numerator_bits=numerator_bits,
                        denominator=area,
                        reciprocal=reciprocal,
                    )
                )
    return pair_words, reciprocals, coefficients


def computed_control_metadata() -> JsonObject:
    pair_words, reciprocals, coefficients = control_tables()
    return {
        "pairCount": len(reciprocals),
        "coefficientCount": len(coefficients),
        "pairsSha256": uint32_sha256(pair_words),
        "selectedReciprocalsSha256": uint32_sha256(reciprocals),
        "predictedCoefficientsSha256": uint32_sha256(coefficients),
    }


def load_preregistration() -> JsonObject:
    preregistration: JsonObject = json.loads(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    controls = preregistration.get("calibratedDeterminantControls", {})
    capture = preregistration.get("capture", {})
    acceptance = preregistration.get("acceptance", {})
    expected_controls = computed_control_metadata()
    if (
        sha256_path(PREREGISTRATION_PATH) != PREREGISTRATION_SHA256
        or preregistration.get("schemaVersion") != 1
        or preregistration.get("role") != ROLE
        or preregistration.get("observedAtPreregistration") is not False
        or controls != expected_controls
        or expected_controls.get("pairCount") != CONTROL_PAIR_COUNT
        or expected_controls.get("coefficientCount") != CONTROL_COEFFICIENT_COUNT
        or expected_controls.get("pairsSha256") != CONTROL_PAIRS_SHA256
        or expected_controls.get("selectedReciprocalsSha256")
        != CONTROL_RECIPROCALS_SHA256
        or expected_controls.get("predictedCoefficientsSha256")
        != CONTROL_COEFFICIENTS_SHA256
        or capture.get("targetWidth") != TARGET_WIDTH
        or capture.get("targetHeight") != TARGET_HEIGHT
        or capture.get("viewportWidth") != VIEWPORT_WIDTH
        or capture.get("recordComponents")
        != ["pull@0,0.5", "pull@15/16,0.5", "center", "dfdx(center)"]
        or capture.get("rawBytes") != RAW_BYTES
        or acceptance
        != {
            "allRecordsWrittenAndFinite": True,
            "allCalibratedDeterminantControlSlopesAcceptedExactly": True,
            "controlPairHashMustMatch": True,
            "controlReciprocalHashMustMatch": True,
            "controlCoefficientHashMustMatch": True,
            "derivativeBitsAreDiagnosticNotFitted": True,
            "noAdaptiveFitOrTolerance": True,
        }
    ):
        raise ValueError("general-height diagnostic preregistration differs")
    return preregistration


def validate_manifest(root: Path) -> tuple[JsonObject, Path]:
    manifest: JsonObject = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    evidence = manifest.get("rasterGeneralHeightDiagnostic", {})
    path = root / str(evidence.get("file", ""))
    if (
        manifest.get("schemaVersion") != SCHEMA_VERSION
        or manifest.get("rigVersion") != RIG_VERSION
        or not isinstance(manifest.get("ciCommit"), str)
        or len(manifest.get("ciCommit", "")) != 40
        or evidence.get("role") != ROLE
        or evidence.get("preregistrationFile")
        != "Analysis/raster_general_height_diagnostic_preregistration.json"
        or evidence.get("preregistrationSha256") != PREREGISTRATION_SHA256
        or evidence.get("geometryCases") != list(failed_general.GEOMETRY_CASES)
        or evidence.get("widthMinimum") != factorized.NORMALIZED_DENOMINATOR_LOWER
        or evidence.get("widthMaximum") != factorized.NORMALIZED_DENOMINATOR_UPPER
        or evidence.get("widthCount") != factorized.WIDTH_COUNT
        or evidence.get("geometryWidthsSha256") != factorized.GEOMETRY_WIDTHS_SHA256
        or evidence.get("effectiveWidthsSha256") != factorized.EFFECTIVE_WIDTHS_SHA256
        or evidence.get("deltaExponentShiftBitsSha256")
        != factorized.DELTA_EXPONENT_SHIFT_BITS_SHA256
        or evidence.get("scaledDeltaFloatBitsSha256")
        != factorized.SCALED_DELTA_BITS_SHA256
        or evidence.get("witnessSignificands") != list(arithmetic.WITNESS_SIGNIFICANDS)
        or evidence.get("targetWidth") != TARGET_WIDTH
        or evidence.get("targetHeight") != TARGET_HEIGHT
        or evidence.get("viewportWidth") != VIEWPORT_WIDTH
        or evidence.get("recordBytes") != RECORD.size
        or evidence.get("recordComponents")
        != ["pull@0,0.5", "pull@15/16,0.5", "center", "dfdx(center)"]
        or evidence.get("ordering")
        != (
            "normalized-denominator-major,witness-major,geometry-major,"
            "sample-side-major"
        )
        or evidence.get("calibratedDeterminantControls") != computed_control_metadata()
        or evidence.get("bytes") != RAW_BYTES
        or not path.is_file()
        or path.stat().st_size != RAW_BYTES
        or sha256_path(path) != evidence.get("sha256")
    ):
        raise ValueError("general-height diagnostic manifest differs")
    return manifest, path


def finite_float_bits(bits: int) -> bool:
    return bits & 0x7F80_0000 != 0x7F80_0000


def validate(root: Path) -> JsonObject:
    load_preregistration()
    manifest, path = validate_manifest(root)
    data = path.read_bytes()
    widths = factorized.geometry_widths()
    shifts = factorized.delta_exponent_shift_bits()
    canonical = factorized.canonical_reciprocals()
    coefficient_acceptance = 0
    expected_acceptance = CONTROL_COEFFICIENT_COUNT
    derivative_equals_prediction = 0
    derivative_pair_equal = 0
    center_equals_pull0 = 0
    derivative_ulp_errors: Counter[int] = Counter()
    derivative_comparison_count = 0

    def record_at(
        width_index: int,
        witness_index: int,
        geometry_index: int,
        sample_side: int,
    ) -> tuple[int, int, int, int]:
        record_index = (
            (width_index * len(arithmetic.WITNESS_SIGNIFICANDS) + witness_index)
            * GEOMETRY_COUNT
            * SAMPLE_SIDE_COUNT
            + geometry_index * SAMPLE_SIDE_COUNT
            + sample_side
        )
        return RECORD.unpack_from(data, record_index * RECORD.size)

    for width_index, width in enumerate(widths):
        for witness_index, delta_bits in enumerate(arithmetic.witness_delta_bits()):
            for geometry_index, geometry in enumerate(failed_general.GEOMETRY_CASES):
                records = [
                    record_at(
                        width_index,
                        witness_index,
                        geometry_index,
                        side,
                    )
                    for side in range(SAMPLE_SIDE_COUNT)
                ]
                if any(
                    record == SENTINEL
                    or not all(finite_float_bits(bits) for bits in record)
                    for record in records
                ):
                    raise ValueError(f"width {width} has missing or nonfinite records")
                center_equals_pull0 += sum(record[2] == record[0] for record in records)
                derivative_pair_equal += records[0][3] == records[1][3]
                height = int(geometry["height"])
                area = width * height
                normalized = calibrated_normalized_class(area)
                if normalized is None:
                    continue
                reciprocal = canonical[
                    normalized - factorized.NORMALIZED_DENOMINATOR_LOWER
                ]
                scaled_bits = delta_bits - shifts[width_index]
                numerator_bits = arithmetic.float32_bits(
                    arithmetic.float32_value(scaled_bits) * height
                )
                predicted = generalized_physical_product_bits(
                    numerator_bits=numerator_bits,
                    denominator=area,
                    reciprocal=reciprocal,
                )
                observations: list[tuple[float, int]] = []
                for side, record in enumerate(records):
                    position = float(
                        sample_position(width, geometry, side)["tileLocalX"]
                    )
                    observations.extend(
                        ((position, record[0]), (position + 0.9375, record[1]))
                    )
                    derivative_equals_prediction += record[3] == predicted
                    derivative_ulp_errors[record[3] - predicted] += 1
                    derivative_comparison_count += 1
                if not factorized.shared_plane_accepts_slope(
                    predicted,
                    observations=observations,
                ):
                    raise ValueError(
                        f"calibrated determinant control rejected at "
                        f"width {width}, height {height}, witness {witness_index}"
                    )
                coefficient_acceptance += 1

    if coefficient_acceptance != expected_acceptance:
        raise ValueError("calibrated determinant acceptance count differs")
    record_count = RAW_BYTES // RECORD.size
    pair_count = (
        factorized.WIDTH_COUNT * len(arithmetic.WITNESS_SIGNIFICANDS) * GEOMETRY_COUNT
    )
    return {
        "liquidGlassRasterGeneralHeightDiagnosticValidationSchemaVersion": 1,
        "classification": ROLE,
        "probe": str(root),
        "ciCommit": manifest.get("ciCommit"),
        "manifestSha256": sha256_path(root / "manifest.json"),
        "rawSha256": sha256_path(path),
        "preregistrationSha256": PREREGISTRATION_SHA256,
        "measurement": {
            "recordCount": record_count,
            "allRecordsFinite": True,
            "calibratedDeterminantControlPairCount": CONTROL_PAIR_COUNT,
            "calibratedDeterminantCoefficientAcceptanceCount": (coefficient_acceptance),
            "calibratedDeterminantCoefficientExpectedCount": (expected_acceptance),
            "centerEqualsZeroXPullCount": center_equals_pull0,
            "centerEqualsZeroXPullExpectedCount": record_count,
            "sameTileDerivativePairEqualCount": derivative_pair_equal,
            "sameTileDerivativePairCount": pair_count,
            "controlDerivativeEqualsPredictedCount": (derivative_equals_prediction),
            "controlDerivativeComparisonCount": derivative_comparison_count,
            "controlDerivativeMinusPredictedUlpDistribution": {
                str(error): count
                for error, count in sorted(derivative_ulp_errors.items())
            },
            "exactControlGate": True,
        },
        "conclusions": {
            "powerOfTwoViewportControlPassed": True,
            "lowDeterminantMantissaCorpusCaptured": True,
            "derivativeBitsCapturedWithoutFitting": True,
            "lowDeterminantMantissaLawEstablished": False,
            "clippedSetupEstablished": False,
            "endToEndLiquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report = validate(arguments.root)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
