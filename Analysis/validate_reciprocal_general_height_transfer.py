#!/usr/bin/env python3
"""Validate prospective unclipped general-height reciprocal transfer."""

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path
from typing import Any

import validate_reciprocal_factorized_transfer as factorized


type JsonObject = dict[str, Any]

arithmetic = factorized.arithmetic
SCHEMA_VERSION = 1
RIG_VERSION = "metal-raster-reciprocal-general-height-transfer-1.0.0"
WIDTH_COUNT = factorized.WIDTH_COUNT
TARGET_WIDTH = 288
TARGET_HEIGHT = 192
VIEWPORT_WIDTH = 32_768
MINIMUM_SIGNED_INTERIOR_AREA = 1_024
GEOMETRY_COUNT = 4
SAMPLE_SIDE_COUNT = 2
RECORD_BYTES = 8
RAW_BYTES = 7_340_032
SENTINEL = (0xFFFF_FFFF, 0xFFFF_FFFF)
PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_reciprocal_general_height_transfer_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "144330567722e2336ae6b6024c5d12c8c0bfb2c1e168a68406fcf079b22cb3a3"
)
GEOMETRY_CASES = (
    {
        "name": "general-height-47",
        "height": 47,
        "sampleLocalY": 46,
        "sampleAnchorX": 240,
        "originY": 11,
        "sampleMarginX": 15,
    },
    {
        "name": "general-height-61",
        "height": 61,
        "sampleLocalY": 60,
        "sampleAnchorX": 240,
        "originY": 23,
        "sampleMarginX": 15,
    },
    {
        "name": "general-height-79",
        "height": 79,
        "sampleLocalY": 78,
        "sampleAnchorX": 240,
        "originY": 37,
        "sampleMarginX": 15,
    },
    {
        "name": "general-height-113",
        "height": 113,
        "sampleLocalY": 112,
        "sampleAnchorX": 240,
        "originY": 53,
        "sampleMarginX": 15,
    },
)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


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
    height = int(geometry["height"])
    signed_interior = height * (2 * x + 1) - width
    if (
        sample_side not in range(SAMPLE_SIDE_COUNT)
        or not 0 <= x < TARGET_WIDTH
        or not 0 <= y < TARGET_HEIGHT
        or width > VIEWPORT_WIDTH
        or int(geometry["originY"]) + height > TARGET_HEIGHT
        or signed_interior <= MINIMUM_SIGNED_INTERIOR_AREA
    ):
        raise ValueError(
            "general-height-transfer sample is not safely interior"
        )
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
    source = preregistration.get("sourceEvidence", {})
    domain = preregistration.get("factorizedDomain", {})
    rule = preregistration.get("geometryRule", {})
    witnesses = preregistration.get("witnesses", {})
    predictions = preregistration.get("frozenPredictions", {})
    layout = preregistration.get("captureLayout", {})
    acceptance = preregistration.get("acceptance", {})
    widths = factorized.geometry_widths()
    if (
        sha256_path(PREREGISTRATION_PATH) != PREREGISTRATION_SHA256
        or preregistration.get("schemaVersion") != 1
        or preregistration.get("role")
        != "prospective-unclipped-general-height-reciprocal-transfer"
        or preregistration.get("observedAtPreregistration") is not False
        or source.get("canonicalReciprocalTableSha256")
        != arithmetic.CANONICAL_RECIPROCAL_SHA256
        or source.get("factorizedTransferRunId") != 30_657_632_564
        or source.get("factorizedTransferManifestSha256")
        != "cf695dccda90eea2032649cb1b0ba5227024ec13bc2c960dabaca18f96299c2a"
        or source.get("factorizedTransferPullsSha256")
        != "2de32da043d69e536b5e1b3ad1ed4be2ff7fbf95c894a3a23f0e586a9710cef2"
        or source.get("factorizedTransferValidationSha256")
        != "850f071bbdbb19663b456607e74cc9f792e29bf7df4738063fe61408a2851173"
        or source.get("factorizedTransferExactAcceptanceCount")
        != 458_752
        or source.get("failedCombinedTransferRunId") != 30_654_181_785
        or domain.get("normalizationClassCount") != WIDTH_COUNT
        or domain.get("geometryWidthsSha256")
        != factorized.GEOMETRY_WIDTHS_SHA256
        or domain.get("effectiveWidthsSha256")
        != factorized.EFFECTIVE_WIDTHS_SHA256
        or domain.get("deltaExponentShiftBitsSha256")
        != factorized.DELTA_EXPONENT_SHIFT_BITS_SHA256
        or domain.get("scaledDeltaFloatBitsSha256")
        != factorized.SCALED_DELTA_BITS_SHA256
        or arithmetic.uint32_sha256(widths)
        != factorized.GEOMETRY_WIDTHS_SHA256
        or preregistration.get("geometryCases") != list(GEOMETRY_CASES)
        or rule.get("targetWidth") != TARGET_WIDTH
        or rule.get("targetHeight") != TARGET_HEIGHT
        or rule.get("viewportWidth") != VIEWPORT_WIDTH
        or rule.get("minimumSignedInteriorArea")
        != MINIMUM_SIGNED_INTERIOR_AREA
        or rule.get("geometryCount") != GEOMETRY_COUNT
        or rule.get("sampleSideCount") != SAMPLE_SIDE_COUNT
        or rule.get("allVerticesInsideViewport") is not True
        or rule.get("allGeometryHeightFactorizationsUnobservedAtPreregistration")
        is not True
        or witnesses.get("significands")
        != list(arithmetic.WITNESS_SIGNIFICANDS)
        or witnesses.get("significandsSha256")
        != arithmetic.SIGNIFICAND_SHA256
        or witnesses.get("unscaledDeltaFloatBitsSha256")
        != arithmetic.DELTA_BITS_SHA256
        or predictions.get("selectedReciprocalTableSha256")
        != arithmetic.CANONICAL_RECIPROCAL_SHA256
        or predictions.get("recoveredCoefficientBitsSha256")
        != arithmetic.PREDICTED_COEFFICIENT_SHA256
        or predictions.get(
            "numericalPredictionsChangedFromAcceptedFactorizedGate"
        )
        is not False
        or layout.get("sameTileSidePositions") != [31, 1]
        or layout.get("rawBytes") != RAW_BYTES
        or acceptance
        != {
            "frozenCanonicalCandidateMustBeAcceptedEveryWidth": True,
            "candidateMatchMultiplicityMustBeReported": True,
            "frozenSelectedReciprocalTableHashMustMatchPrediction": True,
            "recoveredCoefficientBitsHashMustMatchFrozenPrediction": True,
            "bothSampleSidesMustShareOnePlaneConstantPerGeometry": True,
            "everyGeneralHeightMustAcceptThePredictedCoefficient": True,
            "noAdaptiveFitOrTolerance": True,
        }
    ):
        raise ValueError("general-height-transfer preregistration differs")
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
                raise ValueError("general-height samples do not share a tile")
    return preregistration


def validate_manifest(root: Path) -> tuple[JsonObject, Path]:
    manifest: JsonObject = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    evidence = manifest.get("reciprocalGeneralHeightTransfer", {})
    path = root / str(evidence.get("file", ""))
    if (
        manifest.get("schemaVersion") != SCHEMA_VERSION
        or manifest.get("rigVersion") != RIG_VERSION
        or not isinstance(manifest.get("ciCommit"), str)
        or len(manifest.get("ciCommit", "")) != 40
        or evidence.get("role")
        != "prospective-unclipped-general-height-reciprocal-transfer"
        or evidence.get("preregistrationFile")
        != (
            "Analysis/"
            "raster_reciprocal_general_height_transfer_preregistration.json"
        )
        or evidence.get("preregistrationSha256")
        != PREREGISTRATION_SHA256
        or evidence.get("geometryWidthFormula")
        != "normalized-denominator"
        or evidence.get("widthMinimum")
        != factorized.NORMALIZED_DENOMINATOR_LOWER
        or evidence.get("widthMaximum")
        != factorized.NORMALIZED_DENOMINATOR_UPPER
        or evidence.get("widthCount") != WIDTH_COUNT
        or evidence.get("geometryWidthsSha256")
        != factorized.GEOMETRY_WIDTHS_SHA256
        or evidence.get("effectiveWidthsSha256")
        != factorized.EFFECTIVE_WIDTHS_SHA256
        or evidence.get("deltaExponentShiftBitsSha256")
        != factorized.DELTA_EXPONENT_SHIFT_BITS_SHA256
        or evidence.get("scaledDeltaFloatBitsSha256")
        != factorized.SCALED_DELTA_BITS_SHA256
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
        raise ValueError("general-height-transfer manifest differs")
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
    canonical = factorized.canonical_reciprocals()

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
        zip(
            factorized.geometry_widths(),
            factorized.effective_widths(),
            strict=True,
        )
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
                                f"class {geometry_width} has unwritten pulls"
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
                    if not factorized.shared_plane_accepts_slope(
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
        raise ValueError("general-height reciprocal prediction failed")
    if coefficient_sha256 != arithmetic.PREDICTED_COEFFICIENT_SHA256:
        raise ValueError("general-height coefficient prediction failed")
    if acceptance_count != expected_acceptance_count:
        raise ValueError("general-height acceptance count differs")
    return {
        "liquidGlassRasterGeneralHeightValidationSchemaVersion": 1,
        "classification": (
            "prospective-unclipped-general-height-reciprocal-transfer"
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
            "generalNonPowerOfTwoHeightsTransferExactly": True,
            "combinedFailureLocalizedToClipGeneratedSetup": True,
            "canonicalReciprocalTableRemainsExact": True,
            "physicalProductLawRemainsExact": True,
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
