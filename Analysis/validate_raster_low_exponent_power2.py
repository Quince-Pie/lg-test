#!/usr/bin/env python3
"""Validate prospective low-determinant-exponent raster transfer."""

import argparse
import hashlib
import json
import struct
import zlib
from collections import Counter
from pathlib import Path
from typing import Any

import validate_raster_general_height_top_left as top_left


type JsonObject = dict[str, Any]

factorized = top_left.factorized
arithmetic = top_left.arithmetic
SCHEMA_VERSION = 5
RIG_VERSION = "metal-raster-low-exponent-power2-5.0.0"
ROLE = "prospective-low-determinant-exponent-transfer"
TARGET_WIDTH = 288
TARGET_HEIGHT = 256
VIEWPORT_WIDTH = 32_768
MINIMUM_SIGNED_INTERIOR_AREA = 1_024
GEOMETRY_CASES: tuple[JsonObject, ...] = (
    {
        "name": "low-exponent-power2-height-16",
        "height": 16,
        "sampleLocalY": 0,
        "originY": 11,
    },
    {
        "name": "low-exponent-power2-height-32",
        "height": 32,
        "sampleLocalY": 0,
        "originY": 23,
    },
    {
        "name": "low-exponent-power2-height-64",
        "height": 64,
        "sampleLocalY": 0,
        "originY": 37,
    },
    {
        "name": "low-exponent-power2-height-128",
        "height": 128,
        "sampleLocalY": 0,
        "originY": 53,
    },
)
GEOMETRY_COUNT = len(GEOMETRY_CASES)
SAMPLE_XS = top_left.SAMPLE_XS
SAMPLE_TILES = top_left.SAMPLE_TILES
SAMPLE_TILE_LOCAL_XS = top_left.SAMPLE_TILE_LOCAL_XS
SHARED_TILE_GROUPS = top_left.SHARED_TILE_GROUPS
SAMPLE_POSITION_COUNT = len(SAMPLE_XS)
CANDIDATE_RADIUS = 8
RECORD = struct.Struct("<4I")
COEFFICIENT_COUNT = (
    factorized.WIDTH_COUNT * len(arithmetic.WITNESS_SIGNIFICANDS) * GEOMETRY_COUNT
)
RAW_BYTES = COEFFICIENT_COUNT * SAMPLE_POSITION_COUNT * RECORD.size
SENTINEL = (0xFFFF_FFFF,) * 4
SAMPLE_XS_SHA256 = top_left.SAMPLE_XS_SHA256
CANONICAL_RECIPROCAL_SHA256 = arithmetic.CANONICAL_RECIPROCAL_SHA256
ONE_GEOMETRY_COEFFICIENT_SHA256 = arithmetic.PREDICTED_COEFFICIENT_SHA256
FOUR_GEOMETRY_COEFFICIENT_SHA256 = (
    "35540ba73b2636d2d8e6b147f099d9178d3b86ca99963c9c56f000c2b57e338e"
)
PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_low_exponent_power2_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "27b61c89cb25c953a48c4ff06e176633c21fb27f35451d63e6bc69246d6e27b2"
)
TOP_LEFT_SLOPE_OFFSETS_PATH = Path(__file__).with_name(
    "raster_general_height_top_left_slope_offsets.zlib"
)
TOP_LEFT_SLOPE_OFFSET_COUNT = 458_752
TOP_LEFT_SLOPE_OFFSETS_COMPRESSED_BYTES = 50_115
TOP_LEFT_SLOPE_OFFSETS_COMPRESSED_SHA256 = (
    "bd022b0b87c7f485092d28877231880f4d359057216418ee8e018cb30189bf42"
)
TOP_LEFT_SLOPE_OFFSETS_RAW_SHA256 = (
    "e4cf23c08f3c080fa61a1ae56067ae4ad318c442a27712032a9314202e409e70"
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


def sample_position(
    width: int,
    geometry: JsonObject,
    sample_index: int,
) -> JsonObject:
    if sample_index not in range(SAMPLE_POSITION_COUNT):
        raise ValueError("sample index is outside the low-exponent layout")
    x = SAMPLE_XS[sample_index]
    local_y = int(geometry["sampleLocalY"])
    height = int(geometry["height"])
    y = int(geometry["originY"]) + local_y
    diagonal_threshold = width * (2 * (height - local_y) - 1)
    signed_edge = height * (2 * x + 1) - diagonal_threshold
    signed_interior = -signed_edge
    if (
        not 0 <= x < TARGET_WIDTH
        or not 0 <= y < TARGET_HEIGHT
        or width > VIEWPORT_WIDTH
        or int(geometry["originY"]) + height > TARGET_HEIGHT
        or signed_interior <= MINIMUM_SIGNED_INTERIOR_AREA
        or x // 32 != SAMPLE_TILES[sample_index]
        or x % 32 != SAMPLE_TILE_LOCAL_XS[sample_index]
    ):
        raise ValueError("low-exponent sample is not safely interior")
    return {
        "x": x,
        "y": y,
        "tile": x // 32,
        "tileLocalX": x % 32,
        "signedInteriorArea": signed_interior,
    }


def predicted_coefficients() -> list[int]:
    result: list[int] = []
    for effective_width, reciprocal in zip(
        factorized.effective_widths(),
        factorized.canonical_reciprocals(),
        strict=True,
    ):
        for significand in arithmetic.WITNESS_SIGNIFICANDS:
            result.append(
                arithmetic.physical_product_bits(
                    effective_width,
                    reciprocal,
                    significand,
                )
            )
    if uint32_sha256(result) != ONE_GEOMETRY_COEFFICIENT_SHA256:
        raise ValueError("one-geometry coefficient prediction differs")
    return result


def repeated_prediction_metadata() -> JsonObject:
    coefficients = predicted_coefficients()
    repeated = [
        coefficient for coefficient in coefficients for _ in range(GEOMETRY_COUNT)
    ]
    widths = factorized.geometry_widths()
    shifts = factorized.delta_exponent_shift_bits()
    offsets: Counter[int] = Counter()
    coefficient_index = 0
    for width_index, width in enumerate(widths):
        for delta_bits in arithmetic.witness_delta_bits():
            scaled_value = arithmetic.float32_value(delta_bits - shifts[width_index])
            direct_bits = arithmetic.float32_bits(scaled_value / width)
            offsets[coefficients[coefficient_index] - direct_bits] += GEOMETRY_COUNT
            coefficient_index += 1
    metadata = {
        "coefficientCount": len(repeated),
        "sha256": uint32_sha256(repeated),
        "directDivisionOffsetDistribution": {
            str(key): value for key, value in sorted(offsets.items())
        },
    }
    if metadata != {
        "coefficientCount": COEFFICIENT_COUNT,
        "sha256": FOUR_GEOMETRY_COEFFICIENT_SHA256,
        "directDivisionOffsetDistribution": {
            "-1": 27_680,
            "0": 392_552,
            "1": 38_520,
        },
    }:
        raise ValueError("four-geometry coefficient prediction differs")
    return metadata


def load_top_left_slope_offsets() -> bytes:
    compressed = TOP_LEFT_SLOPE_OFFSETS_PATH.read_bytes()
    if (
        len(compressed) != TOP_LEFT_SLOPE_OFFSETS_COMPRESSED_BYTES
        or hashlib.sha256(compressed).hexdigest()
        != TOP_LEFT_SLOPE_OFFSETS_COMPRESSED_SHA256
    ):
        raise ValueError("compressed top-left slope offsets differ")
    offsets = zlib.decompress(compressed)
    distribution = Counter(value if value < 128 else value - 256 for value in offsets)
    if (
        len(offsets) != TOP_LEFT_SLOPE_OFFSET_COUNT
        or hashlib.sha256(offsets).hexdigest() != TOP_LEFT_SLOPE_OFFSETS_RAW_SHA256
        or distribution != {-1: 31_570, 0: 391_258, 1: 35_924}
    ):
        raise ValueError("top-left slope offsets differ")
    return offsets


def load_preregistration() -> JsonObject:
    preregistration: JsonObject = json.loads(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    source = preregistration.get("sourceEvidence", {})
    capture = preregistration.get("capture", {})
    prediction = preregistration.get("frozenPrediction", {})
    recovery = preregistration.get("slopeRecovery", {})
    acceptance = preregistration.get("acceptance", {})
    if (
        sha256_path(PREREGISTRATION_PATH) != PREREGISTRATION_SHA256
        or preregistration.get("schemaVersion") != 1
        or preregistration.get("role") != ROLE
        or preregistration.get("observedAtPreregistration") is not False
        or source.get("factorizedRunId") != 30_657_632_564
        or source.get("topLeftRunId") != 30_663_719_233
        or source.get("topLeftRawSha256")
        != "ccb76da172eceba1e9681b6fbcedb47767262964c7d7e423ec86e84fe213d6e0"
        or source.get("topLeftSlopeOffsetRawSha256")
        != TOP_LEFT_SLOPE_OFFSETS_RAW_SHA256
        or source.get("topLeftSlopeOffsetCompressedSha256")
        != TOP_LEFT_SLOPE_OFFSETS_COMPRESSED_SHA256
        or source.get("topLeftUniqueCoefficientCount") != COEFFICIENT_COUNT
        or source.get("bestTestedKnownSelectorModelMatchCount") != 6_450
        or source.get("bestTestedKnownSelectorModelMismatchCount") != 326
        or capture.get("targetWidth") != TARGET_WIDTH
        or capture.get("targetHeight") != TARGET_HEIGHT
        or capture.get("viewportWidth") != VIEWPORT_WIDTH
        or capture.get("geometryCases") != list(GEOMETRY_CASES)
        or capture.get("sampleXs") != list(SAMPLE_XS)
        or capture.get("sampleXsSha256") != SAMPLE_XS_SHA256
        or capture.get("sampleTiles") != list(SAMPLE_TILES)
        or capture.get("sampleTileLocalXs") != list(SAMPLE_TILE_LOCAL_XS)
        or capture.get("sharedTileGroups")
        != [list(group) for group in SHARED_TILE_GROUPS]
        or capture.get("recordComponents")
        != ["pull@0,0.5", "pull@15/16,0.5", "center", "dfdx(center)"]
        or capture.get("recordBytes") != RECORD.size
        or capture.get("rawBytes") != RAW_BYTES
        or prediction
        != {
            "canonicalReciprocalTableSha256": CANONICAL_RECIPROCAL_SHA256,
            "coefficientTableOneGeometrySha256": (ONE_GEOMETRY_COEFFICIENT_SHA256),
            "coefficientTableFourGeometrySha256": (FOUR_GEOMETRY_COEFFICIENT_SHA256),
            "coefficientCount": COEFFICIENT_COUNT,
            "directDivisionOffsetDistribution": {
                "-1": 27_680,
                "0": 392_552,
                "1": 38_520,
            },
            "heightIndependent": True,
            "predictionChangedAfterObservingCapture": False,
        }
        or recovery
        != {
            "candidateCenter": (
                "roundBinary32(scaledVertexDelta / integerGeometryWidth)"
            ),
            "candidateRadiusFloatUlps": CANDIDATE_RADIUS,
            "pullEvaluation": (
                "roundNearestEvenBinary32(fma(tileLocalXPlusOffset, "
                "candidateSlope, sharedTileConstant))"
            ),
            "constantDomain": "binary32",
            "constantSharing": (
                "one recovered constant shared by both tile-zero sample positions"
            ),
            "centerAndDerivativeUsedForSelection": False,
        }
        or acceptance
        != {
            "allRecordsWrittenAndFinite": True,
            "allSamplesSafelyInsideTopLeftPrimitive": True,
            "samplePositionHashMustMatch": True,
            "everyCoefficientHasExactlyOneRecoveredSlope": True,
            "everyRecoveredSlopeEqualsFrozenCanonicalPrediction": True,
            "recoveredSlopeHashEqualsFrozenFourGeometryPrediction": True,
            "centerAndDerivativeBitsAreDiagnosticNotFitted": True,
            "noAdaptiveFitOrTolerance": True,
        }
    ):
        raise ValueError("low-exponent preregistration differs")
    load_top_left_slope_offsets()
    repeated_prediction_metadata()
    return preregistration


def validate_manifest(root: Path) -> tuple[JsonObject, Path]:
    manifest: JsonObject = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    evidence = manifest.get("rasterLowExponentPower2", {})
    path = root / str(evidence.get("file", ""))
    if (
        manifest.get("schemaVersion") != SCHEMA_VERSION
        or manifest.get("rigVersion") != RIG_VERSION
        or not isinstance(manifest.get("ciCommit"), str)
        or len(manifest.get("ciCommit", "")) != 40
        or evidence.get("role") != ROLE
        or evidence.get("preregistrationFile")
        != "Analysis/raster_low_exponent_power2_preregistration.json"
        or evidence.get("preregistrationSha256") != PREREGISTRATION_SHA256
        or evidence.get("geometryWidthFormula") != "normalized-denominator"
        or evidence.get("widthMinimum") != factorized.NORMALIZED_DENOMINATOR_LOWER
        or evidence.get("widthMaximum") != factorized.NORMALIZED_DENOMINATOR_UPPER
        or evidence.get("widthCount") != factorized.WIDTH_COUNT
        or evidence.get("geometryWidthsSha256") != factorized.GEOMETRY_WIDTHS_SHA256
        or evidence.get("effectiveWidthsSha256") != factorized.EFFECTIVE_WIDTHS_SHA256
        or evidence.get("deltaExponentShiftBitsSha256")
        != factorized.DELTA_EXPONENT_SHIFT_BITS_SHA256
        or evidence.get("scaledDeltaFloatBitsSha256")
        != factorized.SCALED_DELTA_BITS_SHA256
        or evidence.get("geometryCases") != list(GEOMETRY_CASES)
        or evidence.get("geometryCount") != GEOMETRY_COUNT
        or evidence.get("sampleXs") != list(SAMPLE_XS)
        or evidence.get("sampleXsSha256") != SAMPLE_XS_SHA256
        or evidence.get("sampleTiles") != list(SAMPLE_TILES)
        or evidence.get("sampleTileLocalXs") != list(SAMPLE_TILE_LOCAL_XS)
        or evidence.get("samplePositionCount") != SAMPLE_POSITION_COUNT
        or evidence.get("sharedTileGroups")
        != [list(group) for group in SHARED_TILE_GROUPS]
        or evidence.get("witnessSignificands") != list(arithmetic.WITNESS_SIGNIFICANDS)
        or evidence.get("witnessCount") != len(arithmetic.WITNESS_SIGNIFICANDS)
        or evidence.get("witnessSignificandsSha256") != arithmetic.SIGNIFICAND_SHA256
        or evidence.get("deltaFloatBitsSha256") != arithmetic.DELTA_BITS_SHA256
        or evidence.get("candidateRadiusInternalUlps") != CANDIDATE_RADIUS
        or evidence.get("targetWidth") != TARGET_WIDTH
        or evidence.get("targetHeight") != TARGET_HEIGHT
        or evidence.get("viewportWidth") != VIEWPORT_WIDTH
        or evidence.get("minimumSignedInteriorArea") != MINIMUM_SIGNED_INTERIOR_AREA
        or evidence.get("frozenCanonicalReciprocalTableSha256")
        != CANONICAL_RECIPROCAL_SHA256
        or evidence.get("frozenCoefficientTableOneGeometrySha256")
        != ONE_GEOMETRY_COEFFICIENT_SHA256
        or evidence.get("frozenCoefficientTableFourGeometrySha256")
        != FOUR_GEOMETRY_COEFFICIENT_SHA256
        or evidence.get("ordering")
        != (
            "normalized-denominator-major,witness-major,geometry-major,"
            "sample-position-major"
        )
        or evidence.get("recordBytes") != RECORD.size
        or evidence.get("recordComponents")
        != ["pull@0,0.5", "pull@15/16,0.5", "center", "dfdx(center)"]
        or evidence.get("uncoveredRecordSentinel")
        != "0xffffffffffffffffffffffffffffffff"
        or evidence.get("bytes") != RAW_BYTES
        or not path.is_file()
        or path.stat().st_size != RAW_BYTES
        or sha256_path(path) != evidence.get("sha256")
    ):
        raise ValueError("low-exponent manifest differs")
    return manifest, path


def finite_float_bits(bits: int) -> bool:
    return bits & 0x7F80_0000 != 0x7F80_0000


def validate(root: Path) -> JsonObject:
    load_preregistration()
    manifest, path = validate_manifest(root)
    data = path.read_bytes()
    widths = factorized.geometry_widths()
    shifts = factorized.delta_exponent_shift_bits()
    witnesses = arithmetic.witness_delta_bits()
    predictions = predicted_coefficients()
    multiplicity: Counter[int] = Counter()
    recovered_offsets: Counter[int] = Counter()
    mismatch_offsets: Counter[int] = Counter()
    unique_count = 0
    predicted_match_count = 0
    predicted_accepted_count = 0
    center_equals_zero_x_pull = 0
    same_tile_derivative_pair_equal = 0
    first_failures: list[JsonObject] = []
    recovered_digest = hashlib.sha256()

    def record_at(
        width_index: int,
        witness_index: int,
        geometry_index: int,
        sample_index: int,
    ) -> tuple[int, int, int, int]:
        record_index = (
            (width_index * len(witnesses) + witness_index)
            * GEOMETRY_COUNT
            * SAMPLE_POSITION_COUNT
            + geometry_index * SAMPLE_POSITION_COUNT
            + sample_index
        )
        return RECORD.unpack_from(data, record_index * RECORD.size)

    for width_index, width in enumerate(widths):
        for geometry in GEOMETRY_CASES:
            for sample_index in range(SAMPLE_POSITION_COUNT):
                sample_position(width, geometry, sample_index)
        for witness_index, delta_bits in enumerate(witnesses):
            scaled_value = arithmetic.float32_value(delta_bits - shifts[width_index])
            direct_bits = arithmetic.float32_bits(scaled_value / width)
            predicted = predictions[width_index * len(witnesses) + witness_index]
            for geometry_index, geometry in enumerate(GEOMETRY_CASES):
                records = [
                    record_at(
                        width_index,
                        witness_index,
                        geometry_index,
                        sample_index,
                    )
                    for sample_index in range(SAMPLE_POSITION_COUNT)
                ]
                if any(
                    record == SENTINEL
                    or not all(finite_float_bits(bits) for bits in record)
                    for record in records
                ):
                    raise ValueError(f"width {width} has missing low-exponent records")
                center_equals_zero_x_pull += sum(
                    record[2] == record[0] for record in records
                )
                same_tile_derivative_pair_equal += records[0][3] == records[1][3]
                accepted = top_left.accepted_slopes(direct_bits, records)
                multiplicity[len(accepted)] += 1
                predicted_accepted = predicted in accepted
                predicted_accepted_count += predicted_accepted
                recovered = accepted[0] if len(accepted) == 1 else 0xFFFF_FFFF
                recovered_digest.update(struct.pack("<I", recovered))
                if len(accepted) == 1:
                    unique_count += 1
                    recovered_offsets[recovered - direct_bits] += 1
                    predicted_match_count += recovered == predicted
                    mismatch_offsets[recovered - predicted] += 1
                if (len(accepted) != 1 or recovered != predicted) and len(
                    first_failures
                ) < 32:
                    first_failures.append(
                        {
                            "width": width,
                            "height": int(geometry["height"]),
                            "witnessIndex": witness_index,
                            "directBits": f"0x{direct_bits:08x}",
                            "predictedBits": f"0x{predicted:08x}",
                            "acceptedOffsets": [
                                bits - direct_bits for bits in accepted
                            ],
                        }
                    )

    recovered_sha256 = recovered_digest.hexdigest()
    exact = (
        unique_count == COEFFICIENT_COUNT
        and predicted_match_count == COEFFICIENT_COUNT
        and predicted_accepted_count == COEFFICIENT_COUNT
        and recovered_sha256 == FOUR_GEOMETRY_COEFFICIENT_SHA256
    )
    return {
        "liquidGlassRasterLowExponentPower2ValidationSchemaVersion": 1,
        "classification": ROLE,
        "probe": str(root),
        "ciCommit": manifest.get("ciCommit"),
        "manifestSha256": sha256_path(root / "manifest.json"),
        "rawSha256": sha256_path(path),
        "preregistrationSha256": PREREGISTRATION_SHA256,
        "measurement": {
            "recordCount": RAW_BYTES // RECORD.size,
            "coefficientCount": COEFFICIENT_COUNT,
            "candidateRadiusFloatUlps": CANDIDATE_RADIUS,
            "candidateMultiplicity": {
                str(key): value for key, value in sorted(multiplicity.items())
            },
            "recoveredDirectDivisionOffsetDistribution": {
                str(key): value for key, value in sorted(recovered_offsets.items())
            },
            "recoveredMinusPredictionOffsetDistribution": {
                str(key): value for key, value in sorted(mismatch_offsets.items())
            },
            "uniqueCoefficientCount": unique_count,
            "predictedAcceptedCount": predicted_accepted_count,
            "predictedExactMatchCount": predicted_match_count,
            "recoveredSlopeTableSha256": recovered_sha256,
            "frozenSlopeTableSha256": FOUR_GEOMETRY_COEFFICIENT_SHA256,
            "centerEqualsZeroXPullCount": center_equals_zero_x_pull,
            "sameTileDerivativePairEqualCount": (same_tile_derivative_pair_equal),
            "sameTileDerivativePairCount": COEFFICIENT_COUNT,
            "firstFailures": first_failures,
            "allRecordsFinite": True,
            "allSamplesSafelyInsideTopLeftPrimitive": True,
            "exactLowDeterminantExponentTransferGate": exact,
        },
        "conclusions": {
            "canonicalReciprocalTransfersToLowDeterminantExponents": exact,
            "physicalProductTransfersToLowDeterminantExponents": exact,
            "oddHeightNumeratorLawEstablished": False,
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
    raise SystemExit(
        0 if report["measurement"]["exactLowDeterminantExponentTransferGate"] else 1
    )


if __name__ == "__main__":
    main()
