#!/usr/bin/env python3
"""Validate and recover the preregistered multitile slope corpus."""

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path
from typing import Any

import validate_reciprocal_factorized_transfer as factorized
import validate_reciprocal_general_height_transfer as failed_general


type JsonObject = dict[str, Any]

arithmetic = factorized.arithmetic
SCHEMA_VERSION = 3
RIG_VERSION = "metal-raster-general-height-multitile-3.0.0"
ROLE = "discovery-with-preregistered-multitile-slope-recovery"
TARGET_WIDTH = 288
TARGET_HEIGHT = 256
VIEWPORT_WIDTH = 32_768
GEOMETRY_COUNT = 4
SAMPLE_XS = (193, 223, 225, 255, 257, 287)
SAMPLE_TILES = (6, 6, 7, 7, 8, 8)
SAMPLE_TILE_LOCAL_XS = (1, 31, 1, 31, 1, 31)
SHARED_TILE_GROUPS = ((0, 1), (2, 3), (4, 5))
SAMPLE_POSITION_COUNT = len(SAMPLE_XS)
CANDIDATE_RADIUS = 8
RECORD = struct.Struct("<4I")
RAW_BYTES = (
    factorized.WIDTH_COUNT
    * len(arithmetic.WITNESS_SIGNIFICANDS)
    * GEOMETRY_COUNT
    * SAMPLE_POSITION_COUNT
    * RECORD.size
)
SENTINEL = (0xFFFF_FFFF,) * 4
SAMPLE_XS_SHA256 = "4922011fae43558ec8e4fa338f4208e275f32dbc3c80feeb3e2afe6496e90464"
PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_general_height_multitile_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "6e4a7d74c6a92ca00ed683bb64f8446cb0af70983e58afc5480c56b846bf6df0"
)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def uint32_sha256(values: tuple[int, ...]) -> str:
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
        raise ValueError("sample index is outside the multitile layout")
    x = SAMPLE_XS[sample_index]
    y = int(geometry["originY"]) + int(geometry["sampleLocalY"])
    signed_interior = int(geometry["height"]) * (2 * x + 1) - width
    if (
        not 0 <= x < TARGET_WIDTH
        or not 0 <= y < TARGET_HEIGHT
        or int(geometry["originY"]) + int(geometry["height"]) > TARGET_HEIGHT
        or signed_interior <= failed_general.MINIMUM_SIGNED_INTERIOR_AREA
        or x // 32 != SAMPLE_TILES[sample_index]
        or x % 32 != SAMPLE_TILE_LOCAL_XS[sample_index]
    ):
        raise ValueError("multitile sample is not safely interior")
    return {
        "x": x,
        "y": y,
        "tile": x // 32,
        "tileLocalX": x % 32,
        "signedInteriorArea": signed_interior,
    }


def load_preregistration() -> JsonObject:
    preregistration: JsonObject = json.loads(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    capture = preregistration.get("capture", {})
    recovery = preregistration.get("slopeRecovery", {})
    acceptance = preregistration.get("acceptance", {})
    if (
        sha256_path(PREREGISTRATION_PATH) != PREREGISTRATION_SHA256
        or preregistration.get("schemaVersion") != 1
        or preregistration.get("role") != ROLE
        or preregistration.get("observedAtPreregistration") is not False
        or capture.get("targetWidth") != TARGET_WIDTH
        or capture.get("targetHeight") != TARGET_HEIGHT
        or capture.get("viewportWidth") != VIEWPORT_WIDTH
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
                "one independently recovered constant per declared tile group"
            ),
            "centerAndDerivativeUsedForSelection": False,
            "numeratorOrReciprocalModelUsedForSelection": False,
        }
        or acceptance
        != {
            "allRecordsWrittenAndFinite": True,
            "allSamplesSafelyInterior": True,
            "samplePositionHashMustMatch": True,
            "everyCoefficientHasExactlyOneMultitilePullSlope": True,
            "recoveredSlopeHashIsDiscoveryOutput": True,
            "centerAndDerivativeBitsAreDiagnosticNotFitted": True,
            "noAdaptiveFitOrTolerance": True,
        }
    ):
        raise ValueError("multitile preregistration differs")
    return preregistration


def validate_manifest(root: Path) -> tuple[JsonObject, Path]:
    manifest: JsonObject = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    evidence = manifest.get("rasterGeneralHeightMultitile", {})
    path = root / str(evidence.get("file", ""))
    if (
        manifest.get("schemaVersion") != SCHEMA_VERSION
        or manifest.get("rigVersion") != RIG_VERSION
        or not isinstance(manifest.get("ciCommit"), str)
        or len(manifest.get("ciCommit", "")) != 40
        or evidence.get("role") != ROLE
        or evidence.get("preregistrationFile")
        != "Analysis/raster_general_height_multitile_preregistration.json"
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
        or evidence.get("sampleXs") != list(SAMPLE_XS)
        or evidence.get("sampleXsSha256") != SAMPLE_XS_SHA256
        or evidence.get("sampleTiles") != list(SAMPLE_TILES)
        or evidence.get("sampleTileLocalXs") != list(SAMPLE_TILE_LOCAL_XS)
        or evidence.get("samplePositionCount") != SAMPLE_POSITION_COUNT
        or evidence.get("sharedTileGroups")
        != [list(group) for group in SHARED_TILE_GROUPS]
        or evidence.get("candidateRadiusInternalUlps") != CANDIDATE_RADIUS
        or evidence.get("recordBytes") != RECORD.size
        or evidence.get("recordComponents")
        != ["pull@0,0.5", "pull@15/16,0.5", "center", "dfdx(center)"]
        or evidence.get("ordering")
        != (
            "normalized-denominator-major,witness-major,geometry-major,"
            "sample-position-major"
        )
        or evidence.get("bytes") != RAW_BYTES
        or not path.is_file()
        or path.stat().st_size != RAW_BYTES
        or sha256_path(path) != evidence.get("sha256")
    ):
        raise ValueError("multitile manifest differs")
    return manifest, path


def finite_float_bits(bits: int) -> bool:
    return bits & 0x7F80_0000 != 0x7F80_0000


def validate(root: Path) -> JsonObject:
    load_preregistration()
    manifest, path = validate_manifest(root)
    data = path.read_bytes()
    widths = factorized.geometry_widths()
    shifts = factorized.delta_exponent_shift_bits()
    multiplicity: Counter[int] = Counter()
    accepted_offsets: Counter[int] = Counter()
    center_equals_pull = 0
    derivative_pair_equal = 0
    first_nonunique: list[JsonObject] = []
    recovered_digest = hashlib.sha256()

    def record_at(
        width_index: int,
        witness_index: int,
        geometry_index: int,
        sample_index: int,
    ) -> tuple[int, int, int, int]:
        record_index = (
            (width_index * len(arithmetic.WITNESS_SIGNIFICANDS) + witness_index)
            * GEOMETRY_COUNT
            * SAMPLE_POSITION_COUNT
            + geometry_index * SAMPLE_POSITION_COUNT
            + sample_index
        )
        return RECORD.unpack_from(data, record_index * RECORD.size)

    for width_index, width in enumerate(widths):
        for geometry in failed_general.GEOMETRY_CASES:
            for sample_index in range(SAMPLE_POSITION_COUNT):
                sample_position(width, geometry, sample_index)
        for witness_index, delta_bits in enumerate(arithmetic.witness_delta_bits()):
            scaled_bits = delta_bits - shifts[width_index]
            scaled_value = arithmetic.float32_value(scaled_bits)
            direct_bits = arithmetic.float32_bits(scaled_value / width)
            for geometry_index, geometry in enumerate(failed_general.GEOMETRY_CASES):
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
                        f"width {width} has missing or nonfinite multitile records"
                    )
                center_equals_pull += sum(record[2] == record[0] for record in records)
                derivative_pair_equal += sum(
                    records[left][3] == records[right][3]
                    for left, right in SHARED_TILE_GROUPS
                )
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
                                        float(SAMPLE_TILE_LOCAL_XS[sample_index])
                                        + 0.9375,
                                        records[sample_index][1],
                                    ),
                                )
                            ],
                        )
                        for group in SHARED_TILE_GROUPS
                    ):
                        accepted.append(slope_bits)
                multiplicity[len(accepted)] += 1
                for slope_bits in accepted:
                    accepted_offsets[slope_bits - direct_bits] += 1
                recovered = accepted[0] if len(accepted) == 1 else 0xFFFF_FFFF
                recovered_digest.update(struct.pack("<I", recovered))
                if len(accepted) != 1 and len(first_nonunique) < 32:
                    first_nonunique.append(
                        {
                            "width": width,
                            "height": int(geometry["height"]),
                            "witnessIndex": witness_index,
                            "directBits": f"0x{direct_bits:08x}",
                            "acceptedOffsets": [
                                bits - direct_bits for bits in accepted
                            ],
                        }
                    )

    coefficient_count = (
        factorized.WIDTH_COUNT * len(arithmetic.WITNESS_SIGNIFICANDS) * GEOMETRY_COUNT
    )
    unique_count = multiplicity[1]
    exact = unique_count == coefficient_count
    return {
        "liquidGlassRasterGeneralHeightMultitileValidationSchemaVersion": 1,
        "classification": ROLE,
        "probe": str(root),
        "ciCommit": manifest.get("ciCommit"),
        "manifestSha256": sha256_path(root / "manifest.json"),
        "rawSha256": sha256_path(path),
        "preregistrationSha256": PREREGISTRATION_SHA256,
        "measurement": {
            "recordCount": RAW_BYTES // RECORD.size,
            "coefficientCount": coefficient_count,
            "candidateRadiusFloatUlps": CANDIDATE_RADIUS,
            "candidateMultiplicity": {
                str(key): value for key, value in sorted(multiplicity.items())
            },
            "acceptedOffsetDistribution": {
                str(key): value for key, value in sorted(accepted_offsets.items())
            },
            "uniqueCoefficientCount": unique_count,
            "zeroCandidateCount": multiplicity[0],
            "ambiguousCoefficientCount": coefficient_count
            - unique_count
            - multiplicity[0],
            "recoveredSlopeTableSha256": recovered_digest.hexdigest(),
            "centerEqualsZeroXPullCount": center_equals_pull,
            "sameTileDerivativePairEqualCount": derivative_pair_equal,
            "sameTileDerivativePairCount": (
                coefficient_count * len(SHARED_TILE_GROUPS)
            ),
            "firstNonUniqueExamples": first_nonunique,
            "allRecordsFinite": True,
            "allSamplesSafelyInterior": True,
            "exactSlopeRecoveryGate": exact,
        },
        "conclusions": {
            "allDiscoverySlopesUniquelyRecovered": exact,
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
    raise SystemExit(0 if report["measurement"]["exactSlopeRecoveryGate"] else 1)


if __name__ == "__main__":
    main()
