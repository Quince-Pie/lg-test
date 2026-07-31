#!/usr/bin/env python3
"""Validate the isolated prospective reciprocal exponent transfer."""

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path
from typing import Any

import validate_reciprocal_transfer as arithmetic


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 1
RIG_VERSION = "metal-raster-reciprocal-scale-transfer-1.0.0"
TARGET_WIDTH = 224
TARGET_HEIGHT = 4_096
VIEWPORT_WIDTH = 32_768
MINIMUM_SIGNED_INTERIOR_AREA = 1_024
GEOMETRY_COUNT = 4
SAMPLE_SIDE_COUNT = 2
RECORD_BYTES = 8
RAW_BYTES = 7_340_032
SENTINEL = (0xFFFF_FFFF, 0xFFFF_FFFF)
PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_reciprocal_scale_transfer_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "bdf385f37e7c4b6c183e2fd550e1abf150ddcc93758855b6ffd8277970b94fd7"
)
GEOMETRY_CASES = (
    {
        "name": "power2-height-256",
        "height": 256,
        "sampleLocalY": 255,
        "sampleAnchorX": 83,
        "originY": 11,
        "sampleMarginX": 11,
    },
    {
        "name": "power2-height-512",
        "height": 512,
        "sampleLocalY": 511,
        "sampleAnchorX": 43,
        "originY": 19,
        "sampleMarginX": 7,
    },
    {
        "name": "power2-height-1024",
        "height": 1_024,
        "sampleLocalY": 1_023,
        "sampleAnchorX": 127,
        "originY": 27,
        "sampleMarginX": 13,
    },
    {
        "name": "power2-height-2048",
        "height": 2_048,
        "sampleLocalY": 2_047,
        "sampleAnchorX": 189,
        "originY": 35,
        "sampleMarginX": 17,
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
    height = int(geometry["height"])
    anchor_x = int(geometry["sampleAnchorX"])
    margin_x = int(geometry["sampleMarginX"])
    x = (
        anchor_x + margin_x
        if sample_side == 0
        else anchor_x - margin_x
    )
    y = int(geometry["originY"]) + int(geometry["sampleLocalY"])
    signed_interior = height * (2 * x + 1) - width
    if (
        sample_side not in range(SAMPLE_SIDE_COUNT)
        or not 0 <= x < TARGET_WIDTH
        or not 0 <= y < TARGET_HEIGHT
        or width > VIEWPORT_WIDTH
        or int(geometry["originY"]) + height > TARGET_HEIGHT
        or signed_interior <= MINIMUM_SIGNED_INTERIOR_AREA
    ):
        raise ValueError("scale-transfer sample is not safely interior")
    return {
        "x": x,
        "y": y,
        "tileLocalX": x % 32,
        "signedInteriorArea": signed_interior,
    }


def load_preregistration() -> JsonObject:
    preregistration: JsonObject = json.loads(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    source = preregistration.get("sourceEvidence", {})
    model = preregistration.get("physicalProductModel", {})
    domain = preregistration.get("prospectiveDomain", {})
    rule = preregistration.get("geometryRule", {})
    witnesses = preregistration.get("witnesses", {})
    predictions = preregistration.get("frozenPredictions", {})
    layout = preregistration.get("captureLayout", {})
    acceptance = preregistration.get("acceptance", {})
    widths = arithmetic.prospective_widths()
    if (
        sha256_path(PREREGISTRATION_PATH) != PREREGISTRATION_SHA256
        or preregistration.get("schemaVersion") != 1
        or preregistration.get("role")
        != (
            "prospective-unclipped-power2-geometry-reciprocal-"
            "scale-transfer"
        )
        or preregistration.get("observedAtPreregistration") is not False
        or source.get("canonicalReciprocalTableSha256")
        != arithmetic.CANONICAL_RECIPROCAL_SHA256
        or source.get("failedCombinedTransferRunId") != 30_654_181_785
        or source.get("failedCombinedTransferCiCommit")
        != "95b6e69322ba07f513917364be33f1636752ba0f"
        or source.get("failedCombinedTransferManifestSha256")
        != "7389c218362ceddc5bf8c39ee008a691b88ba2e9b2cc961548ae7febe0733977"
        or source.get("failedCombinedTransferPullsSha256")
        != "c0e5a5e139170775042079cf3689411750db52791cc650e4d3839d80ceb4415c"
        or source.get("failedCombinedTransferResult")
        != "width 32768 accepted 0 of 17 frozen width-only candidates"
        or model
        != {
            "name": (
                "physicalTruncatedRadix2PartialProducts16Bias0x140000"
            ),
            "operandPrecisionBits": 24,
            "reciprocalPrecisionBits": 25,
            "productPrecisionBits": 27,
            "partialProductRadix": 2,
            "partialProductTruncationBits": 16,
            "roundingBias": 1_310_720,
            "roundingBiasHex": "0x140000",
            "finalConversion": "round-to-nearest-even binary32",
        }
        or domain.get("normalizedDenominatorLowerInclusive")
        != arithmetic.NORMALIZED_DENOMINATOR_LOWER
        or domain.get("normalizedDenominatorUpperInclusive")
        != arithmetic.NORMALIZED_DENOMINATOR_UPPER
        or domain.get("normalizationClassCount")
        != arithmetic.NORMALIZED_DENOMINATOR_COUNT
        or domain.get("widthMinimum") != arithmetic.WIDTH_MINIMUM
        or domain.get("widthMaximum") != arithmetic.WIDTH_MAXIMUM
        or domain.get("widthCount") != arithmetic.WIDTH_COUNT
        or domain.get("widthsSha256") != arithmetic.WIDTHS_SHA256
        or domain.get("widthsAboveCalibrationUpperBoundCount")
        != arithmetic.WIDTH_COUNT
        or domain.get("unobservedWidthCount") != arithmetic.WIDTH_COUNT
        or domain.get("unseenReciprocalExponent") != -15
        or len(widths) != arithmetic.WIDTH_COUNT
        or arithmetic.uint32_sha256(widths) != arithmetic.WIDTHS_SHA256
        or preregistration.get("geometryCases") != list(GEOMETRY_CASES)
        or rule.get("originX") != 0
        or rule.get("minimumSignedInteriorArea")
        != MINIMUM_SIGNED_INTERIOR_AREA
        or rule.get("targetWidth") != TARGET_WIDTH
        or rule.get("targetHeight") != TARGET_HEIGHT
        or rule.get("viewportWidth") != VIEWPORT_WIDTH
        or rule.get("geometryCount") != GEOMETRY_COUNT
        or rule.get("sampleSideCount") != SAMPLE_SIDE_COUNT
        or rule.get("allVerticesInsideViewport") is not True
        or rule.get("allGeometryCasesUnobservedAtPreregistration")
        is not True
        or witnesses.get("significands")
        != list(arithmetic.WITNESS_SIGNIFICANDS)
        or witnesses.get("count") != len(arithmetic.WITNESS_SIGNIFICANDS)
        or witnesses.get("significandsSha256")
        != arithmetic.SIGNIFICAND_SHA256
        or witnesses.get("deltaFloatBitsSha256")
        != arithmetic.DELTA_BITS_SHA256
        or witnesses.get("candidateRadiusInternalUlps")
        != arithmetic.CANDIDATE_RADIUS
        or witnesses.get("candidateCount")
        != 2 * arithmetic.CANDIDATE_RADIUS + 1
        or predictions.get("selectedReciprocalTableSha256")
        != arithmetic.CANONICAL_RECIPROCAL_SHA256
        or predictions.get("recoveredCoefficientBitsSha256")
        != arithmetic.PREDICTED_COEFFICIENT_SHA256
        or predictions.get(
            "numericalPredictionsChangedFromFailedCombinedGate"
        )
        is not False
        or predictions.get(
            "capturedPullBytesAreEvidenceCarrierNotPredictionTarget"
        )
        is not True
        or layout.get("ordering")
        != (
            "normalized-denominator-major,witness-major,geometry-major,"
            "sample-side-major,pull-offset-major"
        )
        or layout.get("rawBytes") != RAW_BYTES
        or layout.get("uncoveredRecordSentinel")
        != "0xffffffffffffffff"
        or set(acceptance.values()) != {True}
    ):
        raise ValueError("reciprocal-scale-transfer preregistration differs")
    for width in widths:
        for geometry in GEOMETRY_CASES:
            for sample_side in range(SAMPLE_SIDE_COUNT):
                sample_position(width, geometry, sample_side)
    return preregistration


def validate_manifest(root: Path) -> tuple[JsonObject, Path]:
    manifest: JsonObject = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    evidence = manifest.get("reciprocalScaleTransfer", {})
    path = root / str(evidence.get("file", ""))
    if (
        manifest.get("schemaVersion") != SCHEMA_VERSION
        or manifest.get("rigVersion") != RIG_VERSION
        or not isinstance(manifest.get("ciCommit"), str)
        or len(manifest.get("ciCommit", "")) != 40
        or evidence.get("role")
        != "prospective-unclipped-power2-geometry-scale-transfer"
        or evidence.get("preregistrationFile")
        != "Analysis/raster_reciprocal_scale_transfer_preregistration.json"
        or evidence.get("preregistrationSha256")
        != PREREGISTRATION_SHA256
        or evidence.get("widthFormula")
        != "32768-if-normalized-denominator-8192-else-2x"
        or evidence.get("widthMinimum") != arithmetic.WIDTH_MINIMUM
        or evidence.get("widthMaximum") != arithmetic.WIDTH_MAXIMUM
        or evidence.get("widthCount") != arithmetic.WIDTH_COUNT
        or evidence.get("widthsSha256") != arithmetic.WIDTHS_SHA256
        or evidence.get("geometryCases") != list(GEOMETRY_CASES)
        or evidence.get("geometryCount") != GEOMETRY_COUNT
        or evidence.get("sampleSideCount") != SAMPLE_SIDE_COUNT
        or evidence.get("witnessSignificands")
        != list(arithmetic.WITNESS_SIGNIFICANDS)
        or evidence.get("witnessCount")
        != len(arithmetic.WITNESS_SIGNIFICANDS)
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
        raise ValueError("reciprocal-scale-transfer manifest differs")
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
        arithmetic.WIDTH_COUNT
        * len(arithmetic.WITNESS_SIGNIFICANDS)
        * GEOMETRY_COUNT
        * SAMPLE_SIDE_COUNT
    )

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

    for width_index, width in enumerate(arithmetic.prospective_widths()):
        nearest = arithmetic.nearest_even_reciprocal_index(width)
        matching: list[tuple[int, tuple[int, ...]]] = []
        for offset in range(
            -arithmetic.CANDIDATE_RADIUS,
            arithmetic.CANDIDATE_RADIUS + 1,
        ):
            reciprocal = nearest + offset
            coefficient_bits = tuple(
                arithmetic.physical_product_bits(
                    width,
                    reciprocal,
                    significand,
                )
                for significand in arithmetic.WITNESS_SIGNIFICANDS
            )
            accepted = True
            for witness_index, slope_bits in enumerate(coefficient_bits):
                for geometry_index, geometry in enumerate(GEOMETRY_CASES):
                    for sample_side in range(SAMPLE_SIDE_COUNT):
                        pulls = pulls_at(
                            width_index,
                            witness_index,
                            geometry_index,
                            sample_side,
                        )
                        if pulls == SENTINEL:
                            raise ValueError(
                                f"width {width} has an unwritten pull record"
                            )
                        position = sample_position(
                            width,
                            geometry,
                            sample_side,
                        )
                        if not arithmetic.pair_accepts_slope(
                            slope_bits,
                            position=int(position["tileLocalX"]),
                            pulls=pulls,
                        ):
                            accepted = False
                            break
                    if not accepted:
                        break
                if not accepted:
                    break
            if accepted:
                matching.append((reciprocal, coefficient_bits))
        match_counts[len(matching)] += 1
        if len(matching) != 1:
            raise ValueError(
                f"width {width} accepted {len(matching)} candidates"
            )
        selected, coefficient_bits = matching[0]
        offset_counts[selected - nearest] += 1
        selected_digest.update(struct.pack("<I", selected))
        for witness_index, slope_bits in enumerate(coefficient_bits):
            coefficient_digest.update(struct.pack("<I", slope_bits))
            for geometry_index, geometry in enumerate(GEOMETRY_CASES):
                for sample_side in range(SAMPLE_SIDE_COUNT):
                    position = sample_position(
                        width,
                        geometry,
                        sample_side,
                    )
                    if not arithmetic.pair_accepts_slope(
                        slope_bits,
                        position=int(position["tileLocalX"]),
                        pulls=pulls_at(
                            width_index,
                            witness_index,
                            geometry_index,
                            sample_side,
                        ),
                    ):
                        raise ValueError(
                            "selected coefficient failed isolated transfer"
                        )
                    acceptance_count += 1

    selected_sha256 = selected_digest.hexdigest()
    coefficient_sha256 = coefficient_digest.hexdigest()
    if selected_sha256 != arithmetic.CANONICAL_RECIPROCAL_SHA256:
        raise ValueError("prospective reciprocal-table prediction failed")
    if coefficient_sha256 != arithmetic.PREDICTED_COEFFICIENT_SHA256:
        raise ValueError("prospective coefficient-table prediction failed")
    if acceptance_count != expected_acceptance_count:
        raise ValueError("prospective geometry acceptance count differs")
    return {
        "liquidGlassRasterReciprocalScaleTransferValidationSchemaVersion": 1,
        "classification": (
            "prospective-unclipped-power2-geometry-scale-transfer"
        ),
        "probe": str(root),
        "manifestSha256": sha256_path(root / "manifest.json"),
        "pullsSha256": sha256_path(path),
        "preregistrationSha256": PREREGISTRATION_SHA256,
        "ciCommit": manifest.get("ciCommit"),
        "measurement": {
            "widthCount": arithmetic.WIDTH_COUNT,
            "witnessCount": len(arithmetic.WITNESS_SIGNIFICANDS),
            "geometryCount": GEOMETRY_COUNT,
            "sampleSideCount": SAMPLE_SIDE_COUNT,
            "candidateMatchCountDistribution": {
                str(count): frequency
                for count, frequency in sorted(match_counts.items())
            },
            "nearestEvenOffsetDistribution": {
                str(offset): frequency
                for offset, frequency in sorted(offset_counts.items())
            },
            "geometrySampleSideCoefficientAcceptanceCount": acceptance_count,
            "geometrySampleSideCoefficientExpectedCount": (
                expected_acceptance_count
            ),
            "selectedReciprocalTableSha256": selected_sha256,
            "recoveredCoefficientBitsSha256": coefficient_sha256,
            "exact": True,
        },
        "conclusions": {
            "canonicalReciprocalTableTransfersToUnseenExponentRange": True,
            "physicalProductLawTransfersToUnseenExponentRange": True,
            "powerOfTwoHeightScaleEquivalenceTransfers": True,
            "prospectiveIsolatedScaleTransferGatePassed": True,
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
