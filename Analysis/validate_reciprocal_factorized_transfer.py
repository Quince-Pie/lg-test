#!/usr/bin/env python3
"""Validate prospective factorized raster reciprocal exponent transfer."""

import argparse
import base64
import gzip
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path
from typing import Any

import validate_reciprocal_transfer as arithmetic


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 1
RIG_VERSION = "metal-raster-reciprocal-factorized-transfer-1.0.0"
NORMALIZED_DENOMINATOR_LOWER = 8_192
NORMALIZED_DENOMINATOR_UPPER = 16_383
WIDTH_COUNT = 8_192
TARGET_WIDTH = 96
TARGET_HEIGHT = 8_192
VIEWPORT_WIDTH = 32_768
MINIMUM_SIGNED_INTERIOR_AREA = 1_024
GEOMETRY_COUNT = 4
SAMPLE_SIDE_COUNT = 2
RECORD_BYTES = 8
RAW_BYTES = 7_340_032
SENTINEL = (0xFFFF_FFFF, 0xFFFF_FFFF)
GEOMETRY_WIDTHS_SHA256 = (
    "51543aa53b298402f96f65830302af8f0e4e3aafe49d4ee29c5a6f14f70205d9"
)
EFFECTIVE_WIDTHS_SHA256 = (
    "f22d157b2c0f7f90d4b02997ee78252607edc2991ed75e272c7102519323d2ce"
)
DELTA_EXPONENT_SHIFT_BITS_SHA256 = (
    "e56ee754c91ea5e2eaa945602e0866d96a79dc46018a9ccb9a113828fd88a300"
)
SCALED_DELTA_BITS_SHA256 = (
    "884d0b0f9ea9695965d2ce93ae7e80d318e3e4d0032debf5b83214f03725644e"
)
PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_reciprocal_factorized_transfer_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "1e9de6d0403d0d463ace55daf92b50b99dec1f16b8494041b14f8597c1f775f6"
)
CANONICAL_OFFSET_GZIP_BASE64 = (
    "H4sIAAAAAAAC/72Zi3bjMAhE8f3/j97tSexIMCDkuHVPE0V2EOIxjMjB8fnL"
    "rvSO7c1Tz+YKiAUsXcWCeObBxnVZhf+X1p1jWCB87xonN8O2832VakoDRU"
    "mvCbPKTaYNSWZk5COFtW3h2nR/QiZc8x+zbru58R0W4ctBGmbKdMK4TPoz"
    "3ogzZ1T+DLlmMi1JtoiLXaIf2HNf9mSBLngFz4zRrzNgEMLufOh6O5OUtr"
    "ftJ0XMjseuzMi51WwDCUiEMsENMxC9Qmf8GE2kcOUNLKV2FjzMKJs5XcfI"
    "jwF8hbq0HTmuDgLDHQ4XJ3Lp1Fe2hx2HBuMOGkGvWoJ797sO0T87AbEiEv"
    "pYAS3308QmO+HWnNJnVJOKwuBczKEK9vuDjYpoqJZlmiaN2bUNyOEO8Jak"
    "4xtfnSQjX9k2g32rrtizoScTtsFvPf4QajDct+8++ONe0WmMgsvEeTzoPl"
    "uRaFfV4cgSNtStcwifysdYBCGaiKK4iFSEW1vMps2DXy3T1nLNjWgxBSt"
    "jLatBnCTCUeDNKCGjpkdd228d5L5GhWnwBEX8QjFE8iMBYaR8FyMbcg80P"
    "+aOrlbgmYC1B3n2Up6tk820vy2Bx4wj2MMdEKuDW5My5lIgmRFtB7PM3Qg"
    "ABOxxRWhmoPPZ7XzoCtdJyO5/AS65tVmaQxAzKl6I3L7/RlAc2UuqQL3mk"
    "14FvsIj9CFDInC9krBKZDCSvqw1x3UM7kHvqpVB2n+ROl+0sa1NAV51eEz"
    "6uXnmJglTu6miYHRxahmntlUTrOks3NbB+yLnN0k/wccr8hmfXMzhzbuv9"
    "zqVXt0ZRk0/RZpcg0UfadXolaTSbI8ixuNGq/94L/daDbRGfNgilsgWJTo"
    "edNEbhzgkBCeKY+OQ/+zhrAn/tpvY/DLZeyKYEElaHjr/iuWvehyI9kNIQ"
    "mR6wlRVYc2JtJ9p72XZ0SAU+dC02ApP60Yc6Um0LHpdGmGuaFsLfghMBeX"
    "e0S7MDImG0ei70rKfBnfzoOi0sy+Or4UU+NeExerHN27w9J3fCxDcg08bo"
    "F7xH6r96AsAIAAA"
)
GEOMETRY_CASES = (
    {
        "name": "power2-height-512",
        "height": 512,
        "sampleLocalY": 511,
        "sampleAnchorX": 48,
        "originY": 11,
        "sampleMarginX": 15,
    },
    {
        "name": "power2-height-1024",
        "height": 1_024,
        "sampleLocalY": 1_023,
        "sampleAnchorX": 48,
        "originY": 19,
        "sampleMarginX": 15,
    },
    {
        "name": "power2-height-2048",
        "height": 2_048,
        "sampleLocalY": 2_047,
        "sampleAnchorX": 48,
        "originY": 27,
        "sampleMarginX": 15,
    },
    {
        "name": "power2-height-4096",
        "height": 4_096,
        "sampleLocalY": 4_095,
        "sampleAnchorX": 48,
        "originY": 35,
        "sampleMarginX": 15,
    },
)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def geometry_widths() -> list[int]:
    return list(
        range(
            NORMALIZED_DENOMINATOR_LOWER,
            NORMALIZED_DENOMINATOR_UPPER + 1,
        )
    )


def effective_widths() -> list[int]:
    return [
        32_768 if denominator == NORMALIZED_DENOMINATOR_LOWER
        else 2 * denominator
        for denominator in geometry_widths()
    ]


def canonical_reciprocals() -> list[int]:
    encoded_offsets = gzip.decompress(
        base64.b64decode(CANONICAL_OFFSET_GZIP_BASE64)
    )
    effective = effective_widths()
    if len(encoded_offsets) != WIDTH_COUNT:
        raise ValueError("canonical reciprocal offset table length differs")
    reciprocals = [
        arithmetic.nearest_even_reciprocal_index(width)
        + encoded_offset
        - 1
        for width, encoded_offset in zip(
            effective,
            encoded_offsets,
            strict=True,
        )
    ]
    if (
        arithmetic.uint32_sha256(reciprocals)
        != arithmetic.CANONICAL_RECIPROCAL_SHA256
    ):
        raise ValueError("canonical reciprocal offset table hash differs")
    return reciprocals


def delta_exponent_shift_bits() -> list[int]:
    return [
        0x0100_0000 if denominator == NORMALIZED_DENOMINATOR_LOWER
        else 0x0080_0000
        for denominator in geometry_widths()
    ]


def scaled_delta_bits() -> list[int]:
    return [
        bits - shift
        for shift in delta_exponent_shift_bits()
        for bits in arithmetic.witness_delta_bits()
    ]


def sample_position(
    width: int,
    geometry: JsonObject,
    sample_side: int,
) -> JsonObject:
    x = (
        int(geometry["sampleAnchorX"])
        + int(geometry["sampleMarginX"])
        if sample_side == 0
        else int(geometry["sampleAnchorX"])
        - int(geometry["sampleMarginX"])
    )
    y = int(geometry["originY"]) + int(geometry["sampleLocalY"])
    signed_interior = int(geometry["height"]) * (2 * x + 1) - width
    if (
        sample_side not in range(SAMPLE_SIDE_COUNT)
        or not 0 <= x < TARGET_WIDTH
        or not 0 <= y < TARGET_HEIGHT
        or width > VIEWPORT_WIDTH
        or int(geometry["originY"]) + int(geometry["height"])
        > TARGET_HEIGHT
        or signed_interior <= MINIMUM_SIGNED_INTERIOR_AREA
    ):
        raise ValueError("factorized-transfer sample is not safely interior")
    return {
        "x": x,
        "y": y,
        "tile": x // 32,
        "tileLocalX": x % 32,
        "signedInteriorArea": signed_interior,
    }


def shared_plane_accepts_slope(
    slope_bits: int,
    *,
    observations: list[tuple[float, int]],
) -> bool:
    slope = arithmetic.float32_value(slope_bits)
    lower = max(
        arithmetic.float32_rounding_bounds(pull_bits)[0]
        - position * slope
        for position, pull_bits in observations
    )
    upper = min(
        arithmetic.float32_rounding_bounds(pull_bits)[1]
        - position * slope
        for position, pull_bits in observations
    )
    if lower > upper:
        return False
    constant_bits = arithmetic.float32_bits(lower)
    if arithmetic.float32_value(constant_bits) < lower:
        constant_bits = arithmetic.next_float32_bits(
            constant_bits,
            upward=True,
        )
    candidate_count = 0
    while arithmetic.float32_value(constant_bits) <= upper:
        constant = arithmetic.float32_value(constant_bits)
        if all(
            arithmetic.float32_bits(position * slope + constant)
            == pull_bits
            for position, pull_bits in observations
        ):
            return True
        constant_bits = arithmetic.next_float32_bits(
            constant_bits,
            upward=True,
        )
        candidate_count += 1
        if candidate_count > 64:
            raise ValueError("factorized plane-constant interval is too wide")
    return False


def load_preregistration() -> JsonObject:
    preregistration: JsonObject = json.loads(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    source = preregistration.get("sourceEvidence", {})
    domain = preregistration.get("factorizedDomain", {})
    rule = preregistration.get("geometryRule", {})
    witnesses = preregistration.get("witnesses", {})
    predictions = preregistration.get("frozenPredictions", {})
    layout = preregistration.get("captureLayout", {})
    acceptance = preregistration.get("acceptance", {})
    widths = geometry_widths()
    effective = effective_widths()
    canonical = canonical_reciprocals()
    shifts = delta_exponent_shift_bits()
    scaled = scaled_delta_bits()
    if (
        sha256_path(PREREGISTRATION_PATH) != PREREGISTRATION_SHA256
        or preregistration.get("schemaVersion") != 1
        or preregistration.get("role")
        != "prospective-factorized-reciprocal-exponent-transfer"
        or preregistration.get("observedAtPreregistration") is not False
        or source.get("canonicalReciprocalTableSha256")
        != arithmetic.CANONICAL_RECIPROCAL_SHA256
        or source.get("wideTransferRunId") != 30_656_730_832
        or source.get("wideTransferManifestSha256")
        != "69817ef5279fc2c7e36df6a02bf36d5da67cb65df3ee217c04dd7033c1e85e57"
        or source.get("wideTransferPullsSha256")
        != "f8d66aedcd9041a30256cfe2fcc35d34a4307a922ad85b0fc8f02903f8d89eb2"
        or source.get("unsaturatedPrefixFrozenCandidateRejectedCount") != 0
        or source.get("saturatedRawChunkCount") != 4_096
        or source.get("saturatedRawUniqueChunkCount") != 1
        or domain.get("normalizationClassCount") != WIDTH_COUNT
        or domain.get("geometryWidthsSha256")
        != GEOMETRY_WIDTHS_SHA256
        or domain.get("effectiveWidthsSha256")
        != EFFECTIVE_WIDTHS_SHA256
        or domain.get("deltaExponentShiftBitsSha256")
        != DELTA_EXPONENT_SHIFT_BITS_SHA256
        or domain.get("scaledDeltaFloatBitsSha256")
        != SCALED_DELTA_BITS_SHA256
        or domain.get(
            "allFactorizedGeometryDeltaCombinationsUnobservedAtPreregistration"
        )
        is not True
        or len(widths) != WIDTH_COUNT
        or arithmetic.uint32_sha256(widths) != GEOMETRY_WIDTHS_SHA256
        or arithmetic.uint32_sha256(effective)
        != EFFECTIVE_WIDTHS_SHA256
        or arithmetic.uint32_sha256(canonical)
        != arithmetic.CANONICAL_RECIPROCAL_SHA256
        or arithmetic.uint32_sha256(shifts)
        != DELTA_EXPONENT_SHIFT_BITS_SHA256
        or arithmetic.uint32_sha256(scaled) != SCALED_DELTA_BITS_SHA256
        or preregistration.get("geometryCases") != list(GEOMETRY_CASES)
        or rule.get("targetWidth") != TARGET_WIDTH
        or rule.get("targetHeight") != TARGET_HEIGHT
        or rule.get("viewportWidth") != VIEWPORT_WIDTH
        or rule.get("minimumSignedInteriorArea")
        != MINIMUM_SIGNED_INTERIOR_AREA
        or rule.get("geometryCount") != GEOMETRY_COUNT
        or rule.get("sampleSideCount") != SAMPLE_SIDE_COUNT
        or rule.get("sampleSidesShareTile") is not True
        or rule.get("sampleSideSeparationPixels") != 30
        or rule.get("sharedPlaneConstantRequiredAcrossBothSides")
        is not True
        or witnesses.get("significands")
        != list(arithmetic.WITNESS_SIGNIFICANDS)
        or witnesses.get("significandsSha256")
        != arithmetic.SIGNIFICAND_SHA256
        or witnesses.get("unscaledDeltaFloatBitsSha256")
        != arithmetic.DELTA_BITS_SHA256
        or witnesses.get("candidateRadiusInternalUlps")
        != arithmetic.CANDIDATE_RADIUS
        or predictions.get("selectedReciprocalTableSha256")
        != arithmetic.CANONICAL_RECIPROCAL_SHA256
        or predictions.get("recoveredCoefficientBitsSha256")
        != arithmetic.PREDICTED_COEFFICIENT_SHA256
        or predictions.get(
            "numericalPredictionsChangedFromOriginalWideGate"
        )
        is not False
        or layout.get("rawBytes") != RAW_BYTES
        or layout.get("sameTileSidePositions") != [31, 1]
        or layout.get("uncoveredRecordSentinel")
        != "0xffffffffffffffff"
        or acceptance
        != {
            "frozenCanonicalCandidateMustBeAcceptedEveryWidth": True,
            "candidateMatchMultiplicityMustBeReported": True,
            "frozenSelectedReciprocalTableHashMustMatchPrediction": True,
            "recoveredCoefficientBitsHashMustMatchFrozenPrediction": True,
            "bothSampleSidesMustShareOnePlaneConstantPerGeometry": True,
            "everyGeometryMustAcceptThePredictedCoefficient": True,
            "noAdaptiveFitOrTolerance": True,
        }
    ):
        raise ValueError("factorized-transfer preregistration differs")
    for width in widths:
        for geometry in GEOMETRY_CASES:
            positions = [
                sample_position(width, geometry, side)
                for side in range(SAMPLE_SIDE_COUNT)
            ]
            if (
                positions[0]["tile"] != positions[1]["tile"]
                or positions[0]["tileLocalX"] != 31
                or positions[1]["tileLocalX"] != 1
            ):
                raise ValueError("factorized samples do not share one tile")
    return preregistration


def validate_manifest(root: Path) -> tuple[JsonObject, Path]:
    manifest: JsonObject = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    evidence = manifest.get("reciprocalFactorizedTransfer", {})
    path = root / str(evidence.get("file", ""))
    if (
        manifest.get("schemaVersion") != SCHEMA_VERSION
        or manifest.get("rigVersion") != RIG_VERSION
        or not isinstance(manifest.get("ciCommit"), str)
        or len(manifest.get("ciCommit", "")) != 40
        or evidence.get("role")
        != "prospective-factorized-reciprocal-exponent-transfer"
        or evidence.get("preregistrationFile")
        != (
            "Analysis/"
            "raster_reciprocal_factorized_transfer_preregistration.json"
        )
        or evidence.get("preregistrationSha256")
        != PREREGISTRATION_SHA256
        or evidence.get("geometryWidthFormula")
        != "normalized-denominator"
        or evidence.get("widthMinimum") != NORMALIZED_DENOMINATOR_LOWER
        or evidence.get("widthMaximum") != NORMALIZED_DENOMINATOR_UPPER
        or evidence.get("widthCount") != WIDTH_COUNT
        or evidence.get("geometryWidthsSha256")
        != GEOMETRY_WIDTHS_SHA256
        or evidence.get("effectiveWidthFormula")
        != "32768-for-class-8192-else-2x"
        or evidence.get("effectiveWidthsSha256")
        != EFFECTIVE_WIDTHS_SHA256
        or evidence.get("deltaExponentShiftFormula")
        != "2-for-class-8192-else-1"
        or evidence.get("deltaExponentShiftBitsSha256")
        != DELTA_EXPONENT_SHIFT_BITS_SHA256
        or evidence.get("scaledDeltaFloatBitsSha256")
        != SCALED_DELTA_BITS_SHA256
        or evidence.get("geometryCases") != list(GEOMETRY_CASES)
        or evidence.get("geometryCount") != GEOMETRY_COUNT
        or evidence.get("sampleSideCount") != SAMPLE_SIDE_COUNT
        or evidence.get("witnessSignificands")
        != list(arithmetic.WITNESS_SIGNIFICANDS)
        or evidence.get("witnessSignificandsSha256")
        != arithmetic.SIGNIFICAND_SHA256
        or evidence.get("deltaFloatBitsSha256")
        != arithmetic.DELTA_BITS_SHA256
        or evidence.get("candidateRadiusInternalUlps")
        != arithmetic.CANDIDATE_RADIUS
        or evidence.get("targetWidth") != TARGET_WIDTH
        or evidence.get("targetHeight") != TARGET_HEIGHT
        or evidence.get("viewportWidth") != VIEWPORT_WIDTH
        or evidence.get("minimumSignedInteriorArea")
        != MINIMUM_SIGNED_INTERIOR_AREA
        or evidence.get("ordering")
        != (
            "normalized-denominator-major,witness-major,geometry-major,"
            "sample-side-major,pull-offset-major"
        )
        or evidence.get("pullOffsets")
        != [{"x": 0.0, "y": 0.5}, {"x": 0.9375, "y": 0.5}]
        or evidence.get("uncoveredRecordSentinel")
        != "0xffffffffffffffff"
        or evidence.get("frozenSelectedReciprocalTableSha256")
        != arithmetic.CANONICAL_RECIPROCAL_SHA256
        or evidence.get("frozenRecoveredCoefficientBitsSha256")
        != arithmetic.PREDICTED_COEFFICIENT_SHA256
        or evidence.get("bytes") != RAW_BYTES
        or not path.is_file()
        or path.stat().st_size != RAW_BYTES
        or sha256_path(path) != evidence.get("sha256")
    ):
        raise ValueError("factorized-transfer manifest differs")
    return manifest, path


def validate(root: Path) -> JsonObject:
    load_preregistration()
    manifest, path = validate_manifest(root)
    data = path.read_bytes()
    selected_digest = hashlib.sha256()
    coefficient_digest = hashlib.sha256()
    match_counts: Counter[int] = Counter()
    offset_counts: Counter[int] = Counter()
    acceptance_count = 0
    expected_acceptance_count = (
        WIDTH_COUNT
        * len(arithmetic.WITNESS_SIGNIFICANDS)
        * GEOMETRY_COUNT
    )
    canonical = canonical_reciprocals()

    def pulls_at(
        width_index: int,
        witness_index: int,
        geometry_index: int,
        sample_side: int,
    ) -> tuple[int, int]:
        record_index = (
            (
                width_index * len(arithmetic.WITNESS_SIGNIFICANDS)
                + witness_index
            )
            * GEOMETRY_COUNT
            * SAMPLE_SIDE_COUNT
            + geometry_index * SAMPLE_SIDE_COUNT
            + sample_side
        )
        return struct.unpack_from("<II", data, record_index * RECORD_BYTES)

    for width_index, (geometry_width, effective_width) in enumerate(
        zip(geometry_widths(), effective_widths(), strict=True)
    ):
        nearest = arithmetic.nearest_even_reciprocal_index(effective_width)
        matching: list[tuple[int, tuple[int, ...]]] = []
        for offset in range(
            -arithmetic.CANDIDATE_RADIUS,
            arithmetic.CANDIDATE_RADIUS + 1,
        ):
            reciprocal = nearest + offset
            coefficient_bits = tuple(
                arithmetic.physical_product_bits(
                    effective_width,
                    reciprocal,
                    significand,
                )
                for significand in arithmetic.WITNESS_SIGNIFICANDS
            )
            accepted = True
            for witness_index, slope_bits in enumerate(coefficient_bits):
                for geometry_index, geometry in enumerate(GEOMETRY_CASES):
                    observations: list[tuple[float, int]] = []
                    for sample_side in range(SAMPLE_SIDE_COUNT):
                        pulls = pulls_at(
                            width_index,
                            witness_index,
                            geometry_index,
                            sample_side,
                        )
                        if pulls == SENTINEL:
                            raise ValueError(
                                f"width {geometry_width} has unwritten pulls"
                            )
                        position = float(
                            sample_position(
                                geometry_width,
                                geometry,
                                sample_side,
                            )["tileLocalX"]
                        )
                        observations.extend(
                            (
                                (position, pulls[0]),
                                (position + 0.9375, pulls[1]),
                            )
                        )
                    if not shared_plane_accepts_slope(
                        slope_bits,
                        observations=observations,
                    ):
                        accepted = False
                        break
                if not accepted:
                    break
            if accepted:
                matching.append((reciprocal, coefficient_bits))
        match_counts[len(matching)] += 1
        frozen = canonical[width_index]
        frozen_matches = [
            coefficient_bits
            for reciprocal, coefficient_bits in matching
            if reciprocal == frozen
        ]
        if len(frozen_matches) != 1:
            raise ValueError(
                f"class {geometry_width} rejected its frozen candidate"
            )
        coefficient_bits = frozen_matches[0]
        offset_counts[frozen - nearest] += 1
        selected_digest.update(struct.pack("<I", frozen))
        for slope_bits in coefficient_bits:
            coefficient_digest.update(struct.pack("<I", slope_bits))
            acceptance_count += GEOMETRY_COUNT

    selected_sha256 = selected_digest.hexdigest()
    coefficient_sha256 = coefficient_digest.hexdigest()
    if selected_sha256 != arithmetic.CANONICAL_RECIPROCAL_SHA256:
        raise ValueError("factorized reciprocal-table prediction failed")
    if coefficient_sha256 != arithmetic.PREDICTED_COEFFICIENT_SHA256:
        raise ValueError("factorized coefficient-table prediction failed")
    if acceptance_count != expected_acceptance_count:
        raise ValueError("factorized geometry acceptance count differs")
    return {
        "liquidGlassRasterReciprocalFactorizedValidationSchemaVersion": 1,
        "classification": (
            "prospective-factorized-reciprocal-exponent-transfer"
        ),
        "probe": str(root),
        "manifestSha256": sha256_path(root / "manifest.json"),
        "pullsSha256": sha256_path(path),
        "preregistrationSha256": PREREGISTRATION_SHA256,
        "ciCommit": manifest.get("ciCommit"),
        "measurement": {
            "normalizationClassCount": WIDTH_COUNT,
            "witnessCount": len(arithmetic.WITNESS_SIGNIFICANDS),
            "geometryCount": GEOMETRY_COUNT,
            "sharedPlaneBaselinePixels": 30,
            "candidateMatchCountDistribution": {
                str(count): frequency
                for count, frequency in sorted(match_counts.items())
            },
            "nearestEvenOffsetDistribution": {
                str(offset): frequency
                for offset, frequency in sorted(offset_counts.items())
            },
            "geometryCoefficientAcceptanceCount": acceptance_count,
            "geometryCoefficientExpectedCount": expected_acceptance_count,
            "selectedReciprocalTableSha256": selected_sha256,
            "recoveredCoefficientBitsSha256": coefficient_sha256,
            "exact": True,
        },
        "conclusions": {
            "canonicalReciprocalTableTransfersUnderFactorization": True,
            "physicalProductLawTransfersUnderFactorization": True,
            "all8192NormalizationClassesAcceptedExactly": True,
            "widePrimitiveSaturationAvoided": True,
            "failedClippedGeneralHeightHypothesisRemainsFalsified": True,
            "closedFormSelectorEstablished": False,
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
