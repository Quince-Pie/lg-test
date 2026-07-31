#!/usr/bin/env python3
"""Validate the preregistered top-left slope and primitive-equality gate."""

import argparse
import hashlib
import json
import struct
import zlib
from collections import Counter
from pathlib import Path
from typing import Any

import validate_raster_general_height_multitile as multitile


type JsonObject = dict[str, Any]

factorized = multitile.factorized
arithmetic = multitile.arithmetic
SCHEMA_VERSION = 4
RIG_VERSION = "metal-raster-general-height-top-left-4.0.0"
ROLE = "discovery-with-preregistered-top-left-slope-recovery"
TARGET_WIDTH = 288
TARGET_HEIGHT = 256
VIEWPORT_WIDTH = 32_768
MINIMUM_SIGNED_INTERIOR_AREA = 1_024
GEOMETRY_CASES: tuple[JsonObject, ...] = (
    {
        "name": "general-height-47",
        "height": 47,
        "sampleLocalY": 0,
        "originY": 11,
    },
    {
        "name": "general-height-61",
        "height": 61,
        "sampleLocalY": 0,
        "originY": 23,
    },
    {
        "name": "general-height-79",
        "height": 79,
        "sampleLocalY": 0,
        "originY": 37,
    },
    {
        "name": "general-height-113",
        "height": 113,
        "sampleLocalY": 0,
        "originY": 53,
    },
)
GEOMETRY_COUNT = len(GEOMETRY_CASES)
SAMPLE_XS = (0, 31)
SAMPLE_TILES = (0, 0)
SAMPLE_TILE_LOCAL_XS = (0, 31)
SHARED_TILE_GROUPS = ((0, 1),)
SAMPLE_POSITION_COUNT = len(SAMPLE_XS)
CANDIDATE_RADIUS = 8
RECORD = struct.Struct("<4I")
MASK = struct.Struct("<I")
COEFFICIENT_COUNT = (
    factorized.WIDTH_COUNT * len(arithmetic.WITNESS_SIGNIFICANDS) * GEOMETRY_COUNT
)
RAW_BYTES = COEFFICIENT_COUNT * SAMPLE_POSITION_COUNT * RECORD.size
SENTINEL = (0xFFFF_FFFF,) * 4
SAMPLE_XS_SHA256 = "3786b5685d81fe8c584105b439bc5a4dc7a0af4a76548dc49f5b3f47e2984238"
PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_general_height_top_left_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "5d8ae8d8a215ab6615ba2c2e4a2feacd268bec5da6668fdbc92680d2ea85cd3c"
)
BOTTOM_RIGHT_MASK_PATH = Path(__file__).with_name(
    "raster_general_height_multitile_candidate_masks.zlib"
)
BOTTOM_RIGHT_MASK_RAW_BYTES = COEFFICIENT_COUNT * MASK.size
BOTTOM_RIGHT_MASK_RAW_SHA256 = (
    "04a36598ae156769b59d22630d8a7279803bb354a66007cfe4ba8742ce1214f8"
)
BOTTOM_RIGHT_MASK_COMPRESSED_BYTES = 175_503
BOTTOM_RIGHT_MASK_COMPRESSED_SHA256 = (
    "1a9c3bf01109f9c9c3d724215dee623af7275a294536b7618ab7938946c4781c"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def uint32_sha256(values: tuple[int, ...]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(MASK.pack(value))
    return digest.hexdigest()


def sample_position(
    width: int,
    geometry: JsonObject,
    sample_index: int,
) -> JsonObject:
    if sample_index not in range(SAMPLE_POSITION_COUNT):
        raise ValueError("sample index is outside the top-left layout")
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
        raise ValueError("top-left sample is not safely interior")
    return {
        "x": x,
        "y": y,
        "tile": x // 32,
        "tileLocalX": x % 32,
        "signedInteriorArea": signed_interior,
    }


def load_bottom_right_masks() -> bytes:
    compressed = BOTTOM_RIGHT_MASK_PATH.read_bytes()
    if (
        len(compressed) != BOTTOM_RIGHT_MASK_COMPRESSED_BYTES
        or sha256_bytes(compressed) != BOTTOM_RIGHT_MASK_COMPRESSED_SHA256
    ):
        raise ValueError("compressed bottom-right candidate masks differ")
    masks = zlib.decompress(compressed)
    if (
        len(masks) != BOTTOM_RIGHT_MASK_RAW_BYTES
        or sha256_bytes(masks) != BOTTOM_RIGHT_MASK_RAW_SHA256
    ):
        raise ValueError("bottom-right candidate-mask table differs")
    allowed_bits = (1 << (2 * CANDIDATE_RADIUS + 1)) - 1
    for (mask,) in MASK.iter_unpack(masks):
        if mask == 0 or mask & ~allowed_bits:
            raise ValueError("bottom-right candidate mask is invalid")
    return masks


def load_preregistration() -> JsonObject:
    preregistration: JsonObject = json.loads(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    source = preregistration.get("sourceEvidence", {})
    capture = preregistration.get("capture", {})
    ideal = preregistration.get("idealIdentifiabilityControl", {})
    control = preregistration.get("bottomRightControl", {})
    recovery = preregistration.get("slopeRecovery", {})
    acceptance = preregistration.get("acceptance", {})
    if (
        sha256_path(PREREGISTRATION_PATH) != PREREGISTRATION_SHA256
        or preregistration.get("schemaVersion") != 1
        or preregistration.get("role") != ROLE
        or preregistration.get("observedAtPreregistration") is not False
        or source.get("multitileRunId") != 30_662_476_971
        or source.get("multitileCommit") != "5923a6c9269762fe64e49b4a49e8ad42afc91a2f"
        or source.get("multitileManifestSha256")
        != "9045d7c468956e2467f3787ce9c9eca73747f920508a7e0065fc433024f89ae9"
        or source.get("multitileRawSha256")
        != "be36b115fccdbefcc24cee952d295f5e4c9a27d157e23f8b27712359668a0c46"
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
        or ideal.get("widthWitnessCaseCount")
        != factorized.WIDTH_COUNT * len(arithmetic.WITNESS_SIGNIFICANDS)
        or ideal.get("candidateMultiplicity") != {"1": 114_688}
        or ideal.get("zeroCandidateCount") != 0
        or ideal.get("ambiguousCandidateCount") != 0
        or ideal.get("observedAppleDataUsed") is not False
        or control.get("candidateMaskFile")
        != "Analysis/raster_general_height_multitile_candidate_masks.zlib"
        or control.get("candidateMaskCount") != COEFFICIENT_COUNT
        or control.get("candidateMaskRawBytes") != BOTTOM_RIGHT_MASK_RAW_BYTES
        or control.get("candidateMaskRawSha256") != BOTTOM_RIGHT_MASK_RAW_SHA256
        or control.get("candidateMaskCompressedBytes")
        != BOTTOM_RIGHT_MASK_COMPRESSED_BYTES
        or control.get("candidateMaskCompressedSha256")
        != BOTTOM_RIGHT_MASK_COMPRESSED_SHA256
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
            "numeratorOrReciprocalModelUsedForSelection": False,
        }
        or acceptance
        != {
            "allRecordsWrittenAndFinite": True,
            "allSamplesSafelyInsideTopLeftPrimitive": True,
            "samplePositionHashMustMatch": True,
            "everyCoefficientHasExactlyOneTopLeftPullSlope": True,
            "everyRecoveredTopLeftSlopeIsInFrozenBottomRightCandidateMask": True,
            "recoveredSlopeAndCandidateMaskHashesAreDiscoveryOutputs": True,
            "centerAndDerivativeBitsAreDiagnosticNotFitted": True,
            "noAdaptiveFitOrTolerance": True,
        }
    ):
        raise ValueError("top-left preregistration differs")
    return preregistration


def validate_manifest(root: Path) -> tuple[JsonObject, Path]:
    manifest: JsonObject = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    evidence = manifest.get("rasterGeneralHeightTopLeft", {})
    path = root / str(evidence.get("file", ""))
    if (
        manifest.get("schemaVersion") != SCHEMA_VERSION
        or manifest.get("rigVersion") != RIG_VERSION
        or not isinstance(manifest.get("ciCommit"), str)
        or len(manifest.get("ciCommit", "")) != 40
        or evidence.get("role") != ROLE
        or evidence.get("preregistrationFile")
        != "Analysis/raster_general_height_top_left_preregistration.json"
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
        raise ValueError("top-left manifest differs")
    return manifest, path


def finite_float_bits(bits: int) -> bool:
    return bits & 0x7F80_0000 != 0x7F80_0000


def accepted_slopes(
    direct_bits: int,
    records: list[tuple[int, int, int, int]],
) -> tuple[int, ...]:
    accepted: list[int] = []
    for offset in range(-CANDIDATE_RADIUS, CANDIDATE_RADIUS + 1):
        slope_bits = direct_bits + offset
        if all(
            factorized.shared_plane_accepts_slope(
                slope_bits,
                observations=[
                    observation
                    for sample_index in group
                    for observation in (
                        (
                            float(SAMPLE_TILE_LOCAL_XS[sample_index]),
                            records[sample_index][0],
                        ),
                        (
                            float(SAMPLE_TILE_LOCAL_XS[sample_index]) + 0.9375,
                            records[sample_index][1],
                        ),
                    )
                ],
            )
            for group in SHARED_TILE_GROUPS
        ):
            accepted.append(slope_bits)
    return tuple(accepted)


def validate(root: Path) -> JsonObject:
    load_preregistration()
    bottom_right_masks = load_bottom_right_masks()
    manifest, path = validate_manifest(root)
    data = path.read_bytes()
    widths = factorized.geometry_widths()
    shifts = factorized.delta_exponent_shift_bits()
    witnesses = arithmetic.witness_delta_bits()
    top_multiplicity: Counter[int] = Counter()
    bottom_multiplicity: Counter[int] = Counter()
    intersection_multiplicity: Counter[int] = Counter()
    accepted_offsets: Counter[int] = Counter()
    center_equals_zero_x_pull = 0
    same_tile_derivative_pair_equal = 0
    top_unique_bottom_accepted = 0
    first_failures: list[JsonObject] = []
    recovered_digest = hashlib.sha256()
    top_mask_digest = hashlib.sha256()
    coefficient_index = 0

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
                    raise ValueError(
                        f"width {width} has missing or nonfinite top-left records"
                    )
                center_equals_zero_x_pull += sum(
                    record[2] == record[0] for record in records
                )
                same_tile_derivative_pair_equal += records[0][3] == records[1][3]

                accepted = accepted_slopes(direct_bits, records)
                top_mask = 0
                for slope_bits in accepted:
                    offset = slope_bits - direct_bits
                    accepted_offsets[offset] += 1
                    top_mask |= 1 << (offset + CANDIDATE_RADIUS)
                bottom_mask = MASK.unpack_from(
                    bottom_right_masks,
                    coefficient_index * MASK.size,
                )[0]
                intersection_mask = top_mask & bottom_mask
                top_multiplicity[top_mask.bit_count()] += 1
                bottom_multiplicity[bottom_mask.bit_count()] += 1
                intersection_multiplicity[intersection_mask.bit_count()] += 1
                top_mask_digest.update(MASK.pack(top_mask))

                recovered = accepted[0] if len(accepted) == 1 else 0xFFFF_FFFF
                recovered_digest.update(MASK.pack(recovered))
                cross_accepted = len(accepted) == 1 and bool(intersection_mask)
                top_unique_bottom_accepted += cross_accepted
                if (len(accepted) != 1 or not cross_accepted) and len(
                    first_failures
                ) < 32:
                    first_failures.append(
                        {
                            "width": width,
                            "height": int(geometry["height"]),
                            "witnessIndex": witness_index,
                            "directBits": f"0x{direct_bits:08x}",
                            "topLeftAcceptedOffsets": [
                                bits - direct_bits for bits in accepted
                            ],
                            "bottomRightAcceptedOffsets": [
                                offset - CANDIDATE_RADIUS
                                for offset in range(2 * CANDIDATE_RADIUS + 1)
                                if bottom_mask & (1 << offset)
                            ],
                        }
                    )
                coefficient_index += 1

    top_unique_count = top_multiplicity[1]
    top_exact = top_unique_count == COEFFICIENT_COUNT
    primitive_equality = top_exact and top_unique_bottom_accepted == COEFFICIENT_COUNT
    return {
        "liquidGlassRasterGeneralHeightTopLeftValidationSchemaVersion": 1,
        "classification": ROLE,
        "probe": str(root),
        "ciCommit": manifest.get("ciCommit"),
        "manifestSha256": sha256_path(root / "manifest.json"),
        "rawSha256": sha256_path(path),
        "preregistrationSha256": PREREGISTRATION_SHA256,
        "bottomRightCandidateMaskRawSha256": (BOTTOM_RIGHT_MASK_RAW_SHA256),
        "measurement": {
            "recordCount": RAW_BYTES // RECORD.size,
            "coefficientCount": COEFFICIENT_COUNT,
            "candidateRadiusFloatUlps": CANDIDATE_RADIUS,
            "topLeftCandidateMultiplicity": {
                str(key): value for key, value in sorted(top_multiplicity.items())
            },
            "bottomRightCandidateMultiplicity": {
                str(key): value for key, value in sorted(bottom_multiplicity.items())
            },
            "primitiveIntersectionMultiplicity": {
                str(key): value
                for key, value in sorted(intersection_multiplicity.items())
            },
            "acceptedOffsetDistribution": {
                str(key): value for key, value in sorted(accepted_offsets.items())
            },
            "topLeftUniqueCoefficientCount": top_unique_count,
            "topLeftZeroCandidateCount": top_multiplicity[0],
            "topLeftAmbiguousCoefficientCount": (
                COEFFICIENT_COUNT - top_unique_count - top_multiplicity[0]
            ),
            "topLeftUniqueBottomRightAcceptedCount": (top_unique_bottom_accepted),
            "topLeftUniqueBottomRightRejectedCount": (
                top_unique_count - top_unique_bottom_accepted
            ),
            "recoveredSlopeTableSha256": recovered_digest.hexdigest(),
            "topLeftCandidateMaskTableSha256": top_mask_digest.hexdigest(),
            "centerEqualsZeroXPullCount": center_equals_zero_x_pull,
            "sameTileDerivativePairEqualCount": (same_tile_derivative_pair_equal),
            "sameTileDerivativePairCount": COEFFICIENT_COUNT,
            "firstFailures": first_failures,
            "allRecordsFinite": True,
            "allSamplesSafelyInsideTopLeftPrimitive": True,
            "exactTopLeftSlopeRecoveryGate": top_exact,
            "primitiveCoefficientEqualityGate": primitive_equality,
        },
        "conclusions": {
            "allTopLeftDiscoverySlopesUniquelyRecovered": top_exact,
            "topLeftAndBottomRightCoefficientEqualityEstablished": (primitive_equality),
            "centerAndDerivativeBitsExcludedFromSelection": True,
            "numeratorLawEstablished": False,
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
    raise SystemExit(
        0 if report["measurement"]["primitiveCoefficientEqualityGate"] else 1
    )


if __name__ == "__main__":
    main()
