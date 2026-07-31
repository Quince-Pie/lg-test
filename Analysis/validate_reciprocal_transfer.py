#!/usr/bin/env python3
"""Validate the prospective raster reciprocal scale/geometry transfer."""

import argparse
import hashlib
import json
import math
import struct
from collections import Counter
from pathlib import Path
from typing import Any


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 1
RIG_VERSION = "metal-raster-reciprocal-transfer-1.0.0"
NORMALIZED_DENOMINATOR_LOWER = 8_192
NORMALIZED_DENOMINATOR_UPPER = 16_383
NORMALIZED_DENOMINATOR_COUNT = 8_192
PREREGISTERED_WIDTH_SCALE = 4
PREREGISTERED_WIDTH_LOWER = 32_768
PREREGISTERED_WIDTH_UPPER = 65_532
PREREGISTERED_WIDTHS_SHA256 = (
    "d1789dd285e63e23375037362e9df017efdc70f5e25163179e7334897d5fc8ed"
)
WIDTH_MINIMUM = 16_386
WIDTH_MAXIMUM = 32_768
WIDTH_COUNT = 8_192
WIDTHS_SHA256 = (
    "f22d157b2c0f7f90d4b02997ee78252607edc2991ed75e272c7102519323d2ce"
)
TARGET_WIDTH = 224
TARGET_HEIGHT = 192
PREREGISTERED_VIEWPORT_WIDTH = 131_072
VIEWPORT_WIDTH = 32_768
MINIMUM_SIGNED_INTERIOR_AREA = 1_024
GEOMETRY_COUNT = 4
SAMPLE_SIDE_COUNT = 2
PULL_COUNT = 2
CANDIDATE_RADIUS = 8
RECORD_BYTES = 8
RAW_BYTES = 7_340_032
SENTINEL = (0xFFFF_FFFF, 0xFFFF_FFFF)
PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_reciprocal_transfer_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "85dd1466c44725eca9cf67d6c48ef0ad691f08c2dcba79b0acfd010e295c8dfa"
)
AMENDMENT_PATH = Path(__file__).with_name(
    "raster_reciprocal_transfer_amendment.json"
)
AMENDMENT_SHA256 = (
    "0e8ad8329c643a6b1393dcb970e3b9a8da042d2c9332e9a3783724fab69fbdbf"
)
ROUTING_AMENDMENT_PATH = Path(__file__).with_name(
    "raster_reciprocal_transfer_routing_amendment.json"
)
ROUTING_AMENDMENT_SHA256 = (
    "7d0f5cee037747a4b883d2c3befa159bafaff1c07cfbf21f402d2ef6a06912c4"
)
DOMAIN_AMENDMENT_PATH = Path(__file__).with_name(
    "raster_reciprocal_transfer_domain_amendment.json"
)
DOMAIN_AMENDMENT_SHA256 = (
    "4892a84da4ec8b21211c95a36507585f6d4667a36a4529207ff8336d4ac79056"
)
CANONICAL_RECIPROCAL_SHA256 = (
    "2c58cdd15e8db020f6a0f22716bf0fbcc4c33edda429724c23094eeb7e87a8fb"
)
PREREGISTERED_COEFFICIENT_SHA256 = (
    "c053c9c4f8f92efa4d93145e627dc16086bf2aebc3133e50f576b696c9eb00bb"
)
PREDICTED_COEFFICIENT_SHA256 = (
    "7f6b228e8932d0aa66715c47f21889aa8982e53558a636df8bfe8572d5bf6cd0"
)
SIGNIFICAND_SHA256 = "2220ec200ebb378e3d315839e2ef59e4192a41d76d08fffebe84c5a03ad8258a"
DELTA_BITS_SHA256 = "4af6fce64ad188beb784cbea16c1d09ca2713825f8becee8ee64cabfd68caf8a"
WITNESS_SIGNIFICANDS = (
    12_310_539,
    10_561_315,
    8_936_464,
    8_393_727,
    16_724_323,
    8_393_489,
    16_276_106,
    8_393_693,
    16_450_452,
    15_671_128,
    9_479_541,
    16_747_356,
    12_063_463,
    8_393_506,
)
GEOMETRY_CASES = (
    {
        "name": "high-threshold-clipped",
        "height": 47,
        "sampleLocalY": 8,
        "sampleAnchorX": 37,
        "originY": 11,
        "sampleMarginX": 13,
    },
    {
        "name": "mid-threshold-translated",
        "height": 61,
        "sampleLocalY": 29,
        "sampleAnchorX": 83,
        "originY": 23,
        "sampleMarginX": 11,
    },
    {
        "name": "low-threshold-clipped",
        "height": 79,
        "sampleLocalY": 63,
        "sampleAnchorX": 131,
        "originY": 37,
        "sampleMarginX": 9,
    },
    {
        "name": "center-threshold-translated",
        "height": 113,
        "sampleLocalY": 56,
        "sampleAnchorX": 181,
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


def uint32_sha256(values: list[int] | tuple[int, ...]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(struct.pack("<I", value))
    return digest.hexdigest()


def prospective_widths() -> list[int]:
    return [
        (
            32_768
            if denominator == NORMALIZED_DENOMINATOR_LOWER
            else 2 * denominator
        )
        for denominator in range(
            NORMALIZED_DENOMINATOR_LOWER,
            NORMALIZED_DENOMINATOR_UPPER + 1,
        )
    ]


def preregistered_widths() -> list[int]:
    return [
        PREREGISTERED_WIDTH_SCALE * denominator
        for denominator in range(
            NORMALIZED_DENOMINATOR_LOWER,
            NORMALIZED_DENOMINATOR_UPPER + 1,
        )
    ]


def witness_delta_bits() -> tuple[int, ...]:
    return tuple(
        0x3F00_0000 | (significand & 0x7F_FFFF)
        for significand in WITNESS_SIGNIFICANDS
    )


def sample_position(
    width: int,
    geometry: JsonObject,
    sample_side: int,
) -> JsonObject:
    height = int(geometry["height"])
    local_y = int(geometry["sampleLocalY"])
    anchor_x = int(geometry["sampleAnchorX"])
    margin_x = int(geometry["sampleMarginX"])
    threshold = width * (2 * (height - local_y) - 1)
    local_at_anchor = (threshold - height) // (2 * height)
    origin_x = anchor_x - local_at_anchor
    x = (
        anchor_x + margin_x
        if sample_side == 0
        else anchor_x - margin_x
    )
    y = int(geometry["originY"]) + local_y
    local_x = x - origin_x
    signed = height * (2 * local_x + 1) - threshold
    interior = signed if sample_side == 0 else -signed
    if (
        sample_side not in range(SAMPLE_SIDE_COUNT)
        or not 0 <= x < TARGET_WIDTH
        or not 0 <= y < TARGET_HEIGHT
        or origin_x >= VIEWPORT_WIDTH
        or origin_x + width <= 0
        or interior <= MINIMUM_SIGNED_INTERIOR_AREA
    ):
        raise ValueError("prospective geometry position is not safely interior")
    return {
        "originX": origin_x,
        "x": x,
        "y": y,
        "tileLocalX": x % 32,
        "signedInteriorArea": interior,
    }


def round_integer_nearest_even(numerator: int, denominator: int) -> int:
    quotient, remainder = divmod(numerator, denominator)
    doubled = 2 * remainder
    return quotient + (
        doubled > denominator or (doubled == denominator and quotient & 1)
    )


def nearest_even_reciprocal_index(width: int) -> int:
    exponent = -(width - 1).bit_length()
    return round_integer_nearest_even(1 << (24 - exponent), width)


def float32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def float32_value(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def next_float32_bits(bits: int, *, upward: bool) -> int:
    value = float32_value(bits)
    if math.isnan(value):
        raise ValueError("NaN has no ordered float32 neighbor")
    if value == 0:
        return 0x0000_0001 if upward else 0x8000_0001
    if value > 0:
        return bits + 1 if upward else bits - 1
    return bits - 1 if upward else bits + 1


def float32_rounding_bounds(bits: int) -> tuple[float, float]:
    value = float32_value(bits)
    previous = float32_value(next_float32_bits(bits, upward=False))
    following = float32_value(next_float32_bits(bits, upward=True))
    return (previous + value) / 2, (value + following) / 2


def pair_accepts_slope(
    slope_bits: int,
    *,
    position: int,
    pulls: tuple[int, int],
) -> bool:
    slope = float32_value(slope_bits)
    lower0, upper0 = float32_rounding_bounds(pulls[0])
    lower1, upper1 = float32_rounding_bounds(pulls[1])
    lower = max(
        lower0 - position * slope,
        lower1 - (position + 0.9375) * slope,
    )
    upper = min(
        upper0 - position * slope,
        upper1 - (position + 0.9375) * slope,
    )
    constant_bits = float32_bits(lower)
    if float32_value(constant_bits) < lower:
        constant_bits = next_float32_bits(constant_bits, upward=True)
    for candidate_bits in (
        constant_bits,
        next_float32_bits(constant_bits, upward=True),
    ):
        constant = float32_value(candidate_bits)
        if (
            constant <= upper
            and float32_bits(position * slope + constant) == pulls[0]
            and float32_bits((position + 0.9375) * slope + constant)
            == pulls[1]
        ):
            return True
    return False


def physical_product_bits(
    width: int,
    reciprocal: int,
    significand: int,
) -> int:
    exact_product = significand * reciprocal
    product_shift = exact_product.bit_length() - 27
    truncated_product = 0
    remaining = reciprocal
    bit = 0
    while remaining:
        if remaining & 1:
            partial = significand << bit
            truncated_product += (partial >> 16) << 16
        remaining >>= 1
        bit += 1
    product_index = (truncated_product + 0x14_0000) >> product_shift
    reciprocal_exponent = -(width - 1).bit_length()
    value = math.ldexp(
        product_index,
        reciprocal_exponent - 24 - 24 + product_shift,
    )
    return float32_bits(value)


def load_preregistration() -> JsonObject:
    preregistration: JsonObject = json.loads(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    source = preregistration.get("sourceCalibration", {})
    model = preregistration.get("physicalProductModel", {})
    domain = preregistration.get("prospectiveDomain", {})
    rule = preregistration.get("geometryRule", {})
    witnesses = preregistration.get("witnesses", {})
    predictions = preregistration.get("frozenPredictions", {})
    layout = preregistration.get("captureLayout", {})
    acceptance = preregistration.get("acceptance", {})
    widths = preregistered_widths()
    if (
        sha256_path(PREREGISTRATION_PATH) != PREREGISTRATION_SHA256
        or preregistration.get("schemaVersion") != 1
        or preregistration.get("role")
        != "prospective-reciprocal-scale-geometry-transfer"
        or preregistration.get("observedAtPreregistration") is not False
        or source.get("canonicalReciprocalTableSha256")
        != CANONICAL_RECIPROCAL_SHA256
        or source.get("canonicalReciprocalTableBytes") != 32_768
        or source.get("canonicalReciprocalTableShape")
        != [NORMALIZED_DENOMINATOR_COUNT]
        or source.get("classification")
        != (
            "complete finite-domain calibration; not prospective model "
            "validation"
        )
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
        != NORMALIZED_DENOMINATOR_LOWER
        or domain.get("normalizedDenominatorUpperInclusive")
        != NORMALIZED_DENOMINATOR_UPPER
        or domain.get("normalizationClassCount")
        != NORMALIZED_DENOMINATOR_COUNT
        or domain.get("widthLowerInclusive")
        != PREREGISTERED_WIDTH_LOWER
        or domain.get("widthUpperInclusive")
        != PREREGISTERED_WIDTH_UPPER
        or domain.get("widthStride") != PREREGISTERED_WIDTH_SCALE
        or domain.get("widthCount") != WIDTH_COUNT
        or domain.get("widthsSha256")
        != PREREGISTERED_WIDTHS_SHA256
        or domain.get("allWidthsAboveCalibrationUpperBound16384") is not True
        or domain.get("allWidthsUnobservedAtPreregistration") is not True
        or len(widths) != WIDTH_COUNT
        or uint32_sha256(widths) != PREREGISTERED_WIDTHS_SHA256
        or preregistration.get("geometryCases") != list(GEOMETRY_CASES)
        or rule.get("minimumSignedInteriorArea")
        != MINIMUM_SIGNED_INTERIOR_AREA
        or rule.get("targetWidth") != TARGET_WIDTH
        or rule.get("targetHeight") != TARGET_HEIGHT
        or rule.get("viewportWidth") != PREREGISTERED_VIEWPORT_WIDTH
        or rule.get("geometryCount") != GEOMETRY_COUNT
        or rule.get("primitiveCount") != SAMPLE_SIDE_COUNT
        or rule.get("allGeometryCasesUnobservedAtPreregistration") is not True
        or witnesses.get("significands") != list(WITNESS_SIGNIFICANDS)
        or witnesses.get("count") != len(WITNESS_SIGNIFICANDS)
        or witnesses.get("significandsSha256") != SIGNIFICAND_SHA256
        or witnesses.get("deltaFloatBitsSha256") != DELTA_BITS_SHA256
        or witnesses.get("candidateRadiusInternalUlps")
        != CANDIDATE_RADIUS
        or witnesses.get("candidateCount") != 2 * CANDIDATE_RADIUS + 1
        or uint32_sha256(WITNESS_SIGNIFICANDS) != SIGNIFICAND_SHA256
        or uint32_sha256(witness_delta_bits()) != DELTA_BITS_SHA256
        or predictions.get("selectedReciprocalTableSha256")
        != CANONICAL_RECIPROCAL_SHA256
        or predictions.get("selectedReciprocalTableBytes") != 32_768
        or predictions.get("selectedReciprocalTableShape")
        != [NORMALIZED_DENOMINATOR_COUNT]
        or predictions.get("recoveredCoefficientBitsSha256")
        != PREREGISTERED_COEFFICIENT_SHA256
        or predictions.get("recoveredCoefficientBitsBytes") != 458_752
        or predictions.get("recoveredCoefficientBitsShape")
        != [WIDTH_COUNT, len(WITNESS_SIGNIFICANDS)]
        or predictions.get(
            "capturedPullBytesAreEvidenceCarrierNotPredictionTarget"
        )
        is not True
        or layout.get("ordering")
        != (
            "normalized-denominator-major,witness-major,geometry-major,"
            "primitive-major,pull-offset-major"
        )
        or layout.get("rawBytes") != RAW_BYTES
        or layout.get("uncoveredRecordSentinel")
        != "0xffffffffffffffff"
        or set(acceptance.values()) != {True}
    ):
        raise ValueError("reciprocal-transfer preregistration differs")
    for width in widths:
        for geometry in GEOMETRY_CASES:
            for sample_side in range(SAMPLE_SIDE_COUNT):
                sample_position(width, geometry, sample_side)
    return preregistration


def load_amendment() -> JsonObject:
    amendment: JsonObject = json.loads(
        AMENDMENT_PATH.read_text(encoding="utf-8")
    )
    failed = amendment.get("failedRun", {})
    change = amendment.get("technicalChange", {})
    unchanged = amendment.get("unchangedFrozenPredictions", {})
    if (
        sha256_path(AMENDMENT_PATH) != AMENDMENT_SHA256
        or amendment.get("schemaVersion") != 1
        or amendment.get("role")
        != "prospective-reciprocal-transfer-technical-amendment"
        or amendment.get("authorized") is not True
        or amendment.get("observedAtAmendment") is not False
        or failed.get("runId") != 30_653_275_362
        or failed.get("ciCommit")
        != "3bcc3cf4a64217088726d7ded360288f654957f2"
        or failed.get("buildSucceeded") is not True
        or failed.get("captureSucceeded") is not False
        or failed.get("validatorRan") is not False
        or failed.get("failure")
        != "reciprocal-transfer record 0 was not written"
        or failed.get("uploadedFiles")
        != [
            {
                "name": "build.log",
                "bytes": 569,
                "sha256": (
                    "dd947ae08ab45218a9d93307c38f7716ff9eafbda1009fc1f"
                    "7fd19259c58bdbd"
                ),
            }
        ]
        or failed.get("manifestUploaded") is not False
        or failed.get("pullCorpusUploaded") is not False
        or failed.get("validationUploaded") is not False
        or failed.get("appleReciprocalOrCoefficientOutputsObserved")
        is not False
        or change.get("field") != "geometryRule.viewportWidth"
        or change.get("previousValue") != PREREGISTERED_VIEWPORT_WIDTH
        or change.get("newValue") != VIEWPORT_WIDTH
        or unchanged.get("selectedReciprocalTableSha256")
        != CANONICAL_RECIPROCAL_SHA256
        or unchanged.get("recoveredCoefficientBitsSha256")
        != PREREGISTERED_COEFFICIENT_SHA256
        or unchanged.get("widthsSha256")
        != PREREGISTERED_WIDTHS_SHA256
        or unchanged.get("witnessSignificandsSha256")
        != SIGNIFICAND_SHA256
        or unchanged.get("geometryCasesChanged") is not False
        or unchanged.get("samplePositionsChanged") is not False
        or unchanged.get("acceptanceCriteriaChanged") is not False
    ):
        raise ValueError("reciprocal-transfer amendment differs")
    return amendment


def load_routing_amendment() -> JsonObject:
    amendment: JsonObject = json.loads(
        ROUTING_AMENDMENT_PATH.read_text(encoding="utf-8")
    )
    correction = amendment.get("correctionToPreviousInference", {})
    failed = amendment.get("failedRuns", [])
    change = amendment.get("technicalChange", {})
    terminology = change.get("layoutTerminology", {})
    unchanged = amendment.get("unchangedFrozenPredictions", {})
    if (
        sha256_path(ROUTING_AMENDMENT_PATH)
        != ROUTING_AMENDMENT_SHA256
        or amendment.get("schemaVersion") != 1
        or amendment.get("role")
        != "prospective-reciprocal-transfer-routing-amendment"
        or amendment.get("authorized") is not True
        or amendment.get("observedAtAmendment") is not False
        or correction.get("scientificImpact")
        != (
            "No manifest, pull corpus, validation result, reciprocal "
            "selector, or coefficient output was uploaded from either run. "
            "The frozen numerical predictions therefore remain unobserved."
        )
        or not isinstance(failed, list)
        or len(failed) != 2
        or [record.get("runId") for record in failed]
        != [30_653_275_362, 30_653_519_301]
        or any(
            record.get("failure")
            != "reciprocal-transfer record 0 was not written"
            or record.get("pullCorpusUploaded") is not False
            for record in failed
        )
        or change.get("field") != "fragment capture routing"
        or terminology
        != {
            "previous": "geometry-major,primitive-major",
            "effective": "geometry-major,sample-side-major",
            "recordOrderOrBytesChanged": False,
        }
        or unchanged.get("selectedReciprocalTableSha256")
        != CANONICAL_RECIPROCAL_SHA256
        or unchanged.get("recoveredCoefficientBitsSha256")
        != PREREGISTERED_COEFFICIENT_SHA256
        or unchanged.get("widthsSha256")
        != PREREGISTERED_WIDTHS_SHA256
        or unchanged.get("witnessSignificandsSha256")
        != SIGNIFICAND_SHA256
        or unchanged.get("geometryCasesChanged") is not False
        or unchanged.get("samplePositionsChanged") is not False
        or unchanged.get("recordOrderOrBytesChanged") is not False
        or unchanged.get("numericAcceptanceCriteriaChanged") is not False
    ):
        raise ValueError("reciprocal-transfer routing amendment differs")
    return amendment


def load_domain_amendment() -> JsonObject:
    amendment: JsonObject = json.loads(
        DOMAIN_AMENDMENT_PATH.read_text(encoding="utf-8")
    )
    failed = amendment.get("failedRun", {})
    change = amendment.get("technicalChange", {})
    predictions = amendment.get("refrozenPredictionsBeforeObservation", {})
    if (
        sha256_path(DOMAIN_AMENDMENT_PATH) != DOMAIN_AMENDMENT_SHA256
        or amendment.get("schemaVersion") != 1
        or amendment.get("role")
        != "prospective-reciprocal-transfer-domain-amendment"
        or amendment.get("authorized") is not True
        or amendment.get("observedAtAmendment") is not False
        or failed.get("runId") != 30_653_858_985
        or failed.get("ciCommit")
        != "61a08ddeb0806e26627339dd42ba67ab23ca5009"
        or failed.get("captureSucceeded") is not False
        or failed.get("validatorRan") is not False
        or failed.get("totalRecordCount") != 917_504
        or failed.get("writtenRecordCount") != 602_476
        or failed.get("missingRecordCount") != 315_028
        or failed.get("firstMissingRecordIndices")
        != [
            76_724,
            76_725,
            76_732,
            76_733,
            76_740,
            76_741,
            76_748,
            76_749,
            76_756,
            76_757,
            76_764,
            76_765,
            76_772,
            76_773,
            76_780,
            76_781,
        ]
        or failed.get("manifestUploaded") is not False
        or failed.get("pullCorpusUploaded") is not False
        or failed.get("validationUploaded") is not False
        or failed.get("appleReciprocalOrCoefficientOutputsObserved")
        is not False
        or change.get("field") != "prospective width mapping"
        or change.get("newFormula")
        != (
            "32768 when normalizedDenominator == 8192; otherwise 2 * "
            "normalizedDenominator"
        )
        or change.get("normalizationClassCount")
        != NORMALIZED_DENOMINATOR_COUNT
        or change.get("widthCount") != WIDTH_COUNT
        or change.get("widthMinimum") != WIDTH_MINIMUM
        or change.get("widthMaximum") != WIDTH_MAXIMUM
        or change.get("widthsAboveCalibrationUpperBoundCount")
        != WIDTH_COUNT
        or change.get("unobservedWidthCount") != WIDTH_COUNT
        or change.get("unseenReciprocalExponent") != -15
        or change.get("previousWidthsSha256")
        != PREREGISTERED_WIDTHS_SHA256
        or change.get("amendedWidthsSha256") != WIDTHS_SHA256
        or predictions.get("selectedReciprocalTableSha256")
        != CANONICAL_RECIPROCAL_SHA256
        or predictions.get("selectedReciprocalTableChanged") is not False
        or predictions.get("previousRecoveredCoefficientBitsSha256")
        != PREREGISTERED_COEFFICIENT_SHA256
        or predictions.get("amendedRecoveredCoefficientBitsSha256")
        != PREDICTED_COEFFICIENT_SHA256
        or predictions.get("recoveredCoefficientBitsBytes") != 458_752
        or predictions.get("recoveredCoefficientBitsShape")
        != [WIDTH_COUNT, len(WITNESS_SIGNIFICANDS)]
        or predictions.get("geometryCasesChanged") is not False
        or predictions.get("samplePositionRuleChanged") is not False
        or predictions.get("recordLayoutChanged") is not False
        or predictions.get("numericAcceptanceCriteriaChanged") is not False
        or len(prospective_widths()) != WIDTH_COUNT
        or min(prospective_widths()) != WIDTH_MINIMUM
        or max(prospective_widths()) != WIDTH_MAXIMUM
        or any(width <= 16_384 for width in prospective_widths())
        or uint32_sha256(prospective_widths()) != WIDTHS_SHA256
    ):
        raise ValueError("reciprocal-transfer domain amendment differs")
    return amendment


def validate_manifest(root: Path) -> tuple[JsonObject, Path]:
    manifest: JsonObject = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    evidence = manifest.get("reciprocalTransfer", {})
    path = root / str(evidence.get("file", ""))
    if (
        manifest.get("schemaVersion") != SCHEMA_VERSION
        or manifest.get("rigVersion") != RIG_VERSION
        or not isinstance(manifest.get("ciCommit"), str)
        or len(manifest.get("ciCommit", "")) != 40
        or evidence.get("role")
        != "prospective-scale-geometry-transfer"
        or evidence.get("preregistrationFile")
        != "Analysis/raster_reciprocal_transfer_preregistration.json"
        or evidence.get("preregistrationSha256")
        != PREREGISTRATION_SHA256
        or evidence.get("amendmentFile")
        != "Analysis/raster_reciprocal_transfer_amendment.json"
        or evidence.get("amendmentSha256") != AMENDMENT_SHA256
        or evidence.get("routingAmendmentFile")
        != "Analysis/raster_reciprocal_transfer_routing_amendment.json"
        or evidence.get("routingAmendmentSha256")
        != ROUTING_AMENDMENT_SHA256
        or evidence.get("domainAmendmentFile")
        != "Analysis/raster_reciprocal_transfer_domain_amendment.json"
        or evidence.get("domainAmendmentSha256")
        != DOMAIN_AMENDMENT_SHA256
        or evidence.get("widthFormula")
        != "32768-if-normalized-denominator-8192-else-2x"
        or evidence.get("widthMinimum") != WIDTH_MINIMUM
        or evidence.get("widthMaximum") != WIDTH_MAXIMUM
        or evidence.get("widthCount") != WIDTH_COUNT
        or evidence.get("widthsSha256") != WIDTHS_SHA256
        or evidence.get("geometryCases") != list(GEOMETRY_CASES)
        or evidence.get("geometryCount") != GEOMETRY_COUNT
        or evidence.get("sampleSideCount") != SAMPLE_SIDE_COUNT
        or evidence.get("witnessSignificands")
        != list(WITNESS_SIGNIFICANDS)
        or evidence.get("witnessCount") != len(WITNESS_SIGNIFICANDS)
        or evidence.get("witnessSignificandsSha256") != SIGNIFICAND_SHA256
        or evidence.get("deltaFloatBitsSha256") != DELTA_BITS_SHA256
        or evidence.get("candidateRadiusInternalUlps")
        != CANDIDATE_RADIUS
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
        != CANONICAL_RECIPROCAL_SHA256
        or evidence.get("frozenRecoveredCoefficientBitsSha256")
        != PREDICTED_COEFFICIENT_SHA256
        or evidence.get("bytes") != RAW_BYTES
        or not path.is_file()
        or path.stat().st_size != RAW_BYTES
        or sha256_path(path) != evidence.get("sha256")
    ):
        raise ValueError("reciprocal-transfer manifest differs")
    return manifest, path


def validate(root: Path) -> JsonObject:
    load_preregistration()
    load_amendment()
    load_routing_amendment()
    load_domain_amendment()
    manifest, path = validate_manifest(root)
    data = path.read_bytes()
    selected_digest = hashlib.sha256()
    coefficient_digest = hashlib.sha256()
    match_counts: Counter[int] = Counter()
    offset_counts: Counter[int] = Counter()
    geometry_acceptance_count = 0
    expected_geometry_acceptance_count = (
        WIDTH_COUNT
        * len(WITNESS_SIGNIFICANDS)
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
                width_index * len(WITNESS_SIGNIFICANDS)
                + witness_index
            )
            * GEOMETRY_COUNT
            * SAMPLE_SIDE_COUNT
            + geometry_index * SAMPLE_SIDE_COUNT
            + sample_side
        )
        return struct.unpack_from("<II", data, record_index * RECORD_BYTES)

    for width_index, width in enumerate(prospective_widths()):
        nearest = nearest_even_reciprocal_index(width)
        matching: list[tuple[int, tuple[int, ...]]] = []
        for offset in range(-CANDIDATE_RADIUS, CANDIDATE_RADIUS + 1):
            reciprocal = nearest + offset
            coefficient_bits = tuple(
                physical_product_bits(width, reciprocal, significand)
                for significand in WITNESS_SIGNIFICANDS
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
                        if not pair_accepts_slope(
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
                    if not pair_accepts_slope(
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
                            "selected coefficient failed geometry transfer"
                        )
                    geometry_acceptance_count += 1

    selected_sha256 = selected_digest.hexdigest()
    coefficient_sha256 = coefficient_digest.hexdigest()
    if selected_sha256 != CANONICAL_RECIPROCAL_SHA256:
        raise ValueError("prospective reciprocal-table prediction failed")
    if coefficient_sha256 != PREDICTED_COEFFICIENT_SHA256:
        raise ValueError("prospective coefficient-table prediction failed")
    if geometry_acceptance_count != expected_geometry_acceptance_count:
        raise ValueError("prospective geometry acceptance count differs")
    return {
        "liquidGlassRasterReciprocalTransferValidationSchemaVersion": 1,
        "classification": "prospective-scale-and-geometry-transfer",
        "probe": str(root),
        "manifestSha256": sha256_path(root / "manifest.json"),
        "pullsSha256": sha256_path(path),
        "preregistrationSha256": PREREGISTRATION_SHA256,
        "amendmentSha256": AMENDMENT_SHA256,
        "routingAmendmentSha256": ROUTING_AMENDMENT_SHA256,
        "domainAmendmentSha256": DOMAIN_AMENDMENT_SHA256,
        "ciCommit": manifest.get("ciCommit"),
        "measurement": {
            "widthCount": WIDTH_COUNT,
            "witnessCount": len(WITNESS_SIGNIFICANDS),
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
            "geometrySampleSideCoefficientAcceptanceCount": (
                geometry_acceptance_count
            ),
            "geometrySampleSideCoefficientExpectedCount": (
                expected_geometry_acceptance_count
            ),
            "selectedReciprocalTableSha256": selected_sha256,
            "recoveredCoefficientBitsSha256": coefficient_sha256,
            "exact": True,
        },
        "conclusions": {
            "canonicalReciprocalTableTransfersToUnseenExponentRange": True,
            "physicalProductLawTransfersToUnseenExponentRange": True,
            "allUnseenGeometrySampleSidesAcceptPredictions": True,
            "prospectiveTransferGatePassed": True,
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
