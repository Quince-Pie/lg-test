#!/usr/bin/env python3
"""Validate the preregistered standalone Metal reciprocal discovery sweep."""

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 1
RIG_VERSION = "metal-raster-reciprocal-sweep-1.0.0"
WIDTH_LOWER = 128
WIDTH_UPPER = 16_384
TARGET_WIDTH = 160
TARGET_HEIGHT = 160
ORIGIN_X = 17
ORIGIN_Y = 19
GEOMETRY_HEIGHT = 64
EDGE_AREA_MARGIN = 512
PRIMITIVE_COUNT = 2
TILE_COUNT = 5
PULL_COUNT = 2
RECORD_BYTES = 8
SENTINEL = (0xFFFF_FFFF, 0xFFFF_FFFF)
CANDIDATE_RADIUS = 8
PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_reciprocal_sweep_preregistration.json"
)
DISCOVERY_WIDTH_COUNT = 14_181
DISCOVERY_WIDTHS_SHA256 = (
    "865bff07b8ca4e440f7d1cc20bb6ec98f1bacee2ee780d85c53e54efcaccabff"
)
HOLDOUT_WIDTH_COUNT = 2_076
HOLDOUT_WIDTHS_SHA256 = (
    "ddda2c54ca06291eb8cbfeacacab3767c1358ed4d1cf0b14bfec805ad93c30ea"
)
SIGNIFICAND_SHA256 = "2220ec200ebb378e3d315839e2ef59e4192a41d76d08fffebe84c5a03ad8258a"
DELTA_BITS_SHA256 = "4af6fce64ad188beb784cbea16c1d09ca2713825f8becee8ee64cabfd68caf8a"
SOURCE_TRUTH_SHA256 = (
    "069c044c3b38d0535656c0a6e4d12c07a80a2b9b528ae4eb80c4735381c2469a"
)
PRODUCTION_HOLDOUT_WIDTHS = (
    640,
    800,
    976,
    1_280,
    1_440,
    1_600,
    1_920,
    2_160,
    2_560,
    2_880,
    3_200,
    3_440,
    3_840,
    4_096,
    4_320,
    5_120,
    5_760,
    7_680,
    8_192,
    10_240,
    11_520,
    15_360,
    16_384,
)
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


def normalization_class(width: int) -> int:
    if not WIDTH_LOWER <= width <= WIDTH_UPPER:
        raise ValueError("reciprocal-sweep width lies outside its domain")
    return width << (15 - width.bit_length())


PRODUCTION_HOLDOUT_CLASSES = frozenset(
    normalization_class(width) for width in PRODUCTION_HOLDOUT_WIDTHS
)


def is_holdout_width(width: int) -> bool:
    normalized = normalization_class(width)
    hashed = (normalized * 0x9E37_79B1) & 0xFFFF_FFFF
    return (hashed >> 29) == 0 or normalized in PRODUCTION_HOLDOUT_CLASSES


def selected_widths(*, holdout: bool) -> list[int]:
    return [
        width
        for width in range(WIDTH_LOWER, WIDTH_UPPER + 1)
        if is_holdout_width(width) is holdout
    ]


def witness_delta_bits() -> tuple[int, ...]:
    return tuple(
        0x3F00_0000 | (significand & 0x7F_FFFF)
        for significand in WITNESS_SIGNIFICANDS
    )


def round_integer_nearest_even(numerator: int, denominator: int) -> int:
    quotient, remainder = divmod(numerator, denominator)
    doubled = 2 * remainder
    return quotient + (
        doubled > denominator or (doubled == denominator and quotient & 1)
    )


def nearest_even_reciprocal_index(width: int) -> int:
    exponent = -(width - 1).bit_length()
    return round_integer_nearest_even(1 << (24 - exponent), width)


def physical_product_bits(width: int, reciprocal: int, significand: int) -> int:
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
    return struct.unpack("<I", struct.pack("<f", value))[0]


def candidate_signatures(width: int) -> list[tuple[int, ...]]:
    nearest = nearest_even_reciprocal_index(width)
    return [
        tuple(
            physical_product_bits(width, nearest + offset, significand)
            for significand in WITNESS_SIGNIFICANDS
        )
        for offset in range(-CANDIDATE_RADIUS, CANDIDATE_RADIUS + 1)
    ]


def expected_positions(width: int) -> list[JsonObject]:
    last_visible_tile = min(
        (ORIGIN_X + width - 1) // 32,
        (TARGET_WIDTH - 1) // 32,
    )
    positions: list[JsonObject] = []
    for primitive in range(PRIMITIVE_COUNT):
        for tile in range(ORIGIN_X // 32, last_visible_tile + 1):
            lower = max(ORIGIN_X, tile * 32) - ORIGIN_X
            upper = min(ORIGIN_X + width - 1, tile * 32 + 31) - ORIGIN_X
            local_x = upper if primitive == 0 else lower
            signed_interior = (
                GEOMETRY_HEIGHT * (2 * local_x + 1) - width
                if primitive == 0
                else (2 * GEOMETRY_HEIGHT - 1) * width
                - GEOMETRY_HEIGHT * (2 * local_x + 1)
            )
            if signed_interior > EDGE_AREA_MARGIN:
                positions.append(
                    {
                        "primitive": primitive,
                        "tile": tile,
                        "x": ORIGIN_X + local_x,
                        "y": (
                            ORIGIN_Y + GEOMETRY_HEIGHT - 1
                            if primitive == 0
                            else ORIGIN_Y
                        ),
                    }
                )
    slots = {
        int(position["primitive"]) * TILE_COUNT + int(position["tile"])
        for position in positions
    }
    if (
        not 4 <= len(positions) <= PRIMITIVE_COUNT * TILE_COUNT
        or len(slots) != len(positions)
        or any(
            not (
                0 <= int(position["x"]) < TARGET_WIDTH
                and 0 <= int(position["y"]) < TARGET_HEIGHT
            )
            for position in positions
        )
    ):
        raise ValueError(f"invalid reciprocal-sweep position map for width {width}")
    return positions


def load_preregistration() -> JsonObject:
    preregistration: JsonObject = json.loads(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    domain = preregistration.get("domain", {})
    envelope = preregistration.get("candidateEnvelope", {})
    witnesses = preregistration.get("witnesses", {})
    product_model = preregistration.get("physicalProductModel", {})
    discovery = selected_widths(holdout=False)
    holdout = selected_widths(holdout=True)
    if (
        preregistration.get("schemaVersion") != 1
        or preregistration.get("role") != "reciprocal-index-discovery"
        or preregistration.get("discoveryObservedAtPreregistration") is not False
        or preregistration.get("holdoutObservedAtPreregistration") is not False
        or product_model
        != {
            "name": "physicalTruncatedRadix2PartialProducts16Bias0x140000",
            "operandPrecisionBits": 24,
            "reciprocalPrecisionBits": 25,
            "productPrecisionBits": 27,
            "partialProductRadix": 2,
            "partialProductTruncationBits": 16,
            "roundingBias": 1_310_720,
            "roundingBiasHex": "0x140000",
            "finalConversion": "round-to-nearest-even binary32",
        }
        or domain.get("widthLowerInclusive") != WIDTH_LOWER
        or domain.get("widthUpperInclusive") != WIDTH_UPPER
        or domain.get("normalizationClass")
        != "width << (15 - bit_length(width))"
        or domain.get("holdoutHash")
        != "high3((normalizationClass * 0x9e3779b1) mod 2^32) == 0"
        or domain.get("productionHoldoutWidths")
        != list(PRODUCTION_HOLDOUT_WIDTHS)
        or domain.get("holdoutClosedUnderPowerOfTwoScaleEquivalence") is not True
        or domain.get("discoveryWidthCount") != DISCOVERY_WIDTH_COUNT
        or domain.get("discoveryWidthsSha256") != DISCOVERY_WIDTHS_SHA256
        or domain.get("holdoutWidthCount") != HOLDOUT_WIDTH_COUNT
        or domain.get("holdoutWidthsSha256") != HOLDOUT_WIDTHS_SHA256
        or len(discovery) != DISCOVERY_WIDTH_COUNT
        or uint32_sha256(discovery) != DISCOVERY_WIDTHS_SHA256
        or len(holdout) != HOLDOUT_WIDTH_COUNT
        or uint32_sha256(holdout) != HOLDOUT_WIDTHS_SHA256
        or set(discovery) & set(holdout)
        or len(discovery) + len(holdout) != WIDTH_UPPER - WIDTH_LOWER + 1
        or envelope
        != {
            "center": "round-to-nearest-even 25-bit reciprocal",
            "radiusInternalUlps": CANDIDATE_RADIUS,
            "offsetLowerInclusive": -CANDIDATE_RADIUS,
            "offsetUpperInclusive": CANDIDATE_RADIUS,
            "candidateCount": 2 * CANDIDATE_RADIUS + 1,
        }
        or witnesses.get("significands") != list(WITNESS_SIGNIFICANDS)
        or witnesses.get("count") != len(WITNESS_SIGNIFICANDS)
        or witnesses.get("significandsSha256") != SIGNIFICAND_SHA256
        or witnesses.get("deltaFloatBitsSha256") != DELTA_BITS_SHA256
        or witnesses.get("candidateSignatureCountPerWidth")
        != 2 * CANDIDATE_RADIUS + 1
        or witnesses.get("candidateCollisionCount") != 0
        or uint32_sha256(WITNESS_SIGNIFICANDS) != SIGNIFICAND_SHA256
        or uint32_sha256(witness_delta_bits()) != DELTA_BITS_SHA256
    ):
        raise ValueError("reciprocal-sweep preregistration differs")
    for width in range(WIDTH_LOWER, WIDTH_UPPER + 1):
        signatures = candidate_signatures(width)
        if len(set(signatures)) != 2 * CANDIDATE_RADIUS + 1:
            raise ValueError(
                f"reciprocal witnesses collide inside the envelope at width {width}"
            )
    return preregistration


def expected_file_bytes() -> int:
    return (
        DISCOVERY_WIDTH_COUNT
        * len(WITNESS_SIGNIFICANDS)
        * PRIMITIVE_COUNT
        * TILE_COUNT
        * RECORD_BYTES
    )


def validate_record_layout(path: Path, widths: list[int]) -> str:
    data = path.read_bytes()
    if len(data) != expected_file_bytes():
        raise ValueError("reciprocal-sweep file size differs")
    records = iter(struct.iter_unpack("<II", data))
    for width in widths:
        expected_slots = {
            int(position["primitive"]) * TILE_COUNT + int(position["tile"])
            for position in expected_positions(width)
        }
        for _witness in WITNESS_SIGNIFICANDS:
            for slot in range(PRIMITIVE_COUNT * TILE_COUNT):
                record = next(records)
                absent = record == SENTINEL
                if absent == (slot in expected_slots):
                    state = "absent" if absent else "present"
                    raise ValueError(
                        f"width {width} slot {slot} is unexpectedly {state}"
                    )
    try:
        next(records)
    except StopIteration:
        pass
    else:
        raise ValueError("reciprocal-sweep file has trailing records")
    return hashlib.sha256(data).hexdigest()


def validate(root: Path) -> None:
    preregistration = load_preregistration()
    manifest: JsonObject = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    evidence = manifest.get("reciprocalSweep", {})
    widths = selected_widths(holdout=False)
    output_path = root / str(evidence.get("file", ""))
    expected_bytes = expected_file_bytes()
    if (
        manifest.get("schemaVersion") != SCHEMA_VERSION
        or manifest.get("rigVersion") != RIG_VERSION
        or not isinstance(manifest.get("ciCommit"), str)
        or len(manifest.get("ciCommit", "")) != 40
        or evidence.get("role") != "discovery"
        or evidence.get("widths") != widths
        or evidence.get("widthCount") != DISCOVERY_WIDTH_COUNT
        or evidence.get("widthsSha256") != DISCOVERY_WIDTHS_SHA256
        or evidence.get("holdoutWidthCount") != HOLDOUT_WIDTH_COUNT
        or evidence.get("holdoutWidthsSha256") != HOLDOUT_WIDTHS_SHA256
        or evidence.get("witnessSignificands") != list(WITNESS_SIGNIFICANDS)
        or evidence.get("witnessCount") != len(WITNESS_SIGNIFICANDS)
        or evidence.get("witnessSignificandsSha256") != SIGNIFICAND_SHA256
        or evidence.get("deltaFloatBitsSha256") != DELTA_BITS_SHA256
        or evidence.get("candidateRadiusInternalUlps") != CANDIDATE_RADIUS
        or evidence.get("candidateCount") != 2 * CANDIDATE_RADIUS + 1
        or evidence.get("targetWidth") != TARGET_WIDTH
        or evidence.get("targetHeight") != TARGET_HEIGHT
        or evidence.get("originX") != ORIGIN_X
        or evidence.get("originY") != ORIGIN_Y
        or evidence.get("geometryHeight") != GEOMETRY_HEIGHT
        or evidence.get("edgeAreaMargin") != EDGE_AREA_MARGIN
        or evidence.get("primitiveCount") != PRIMITIVE_COUNT
        or evidence.get("tileCount") != TILE_COUNT
        or evidence.get("pullOffsets")
        != [{"x": 0.0, "y": 0.5}, {"x": 0.9375, "y": 0.5}]
        or evidence.get("components") != ["xAt0", "xAt15Over16"]
        or evidence.get("positionRule")
        != "clamped-visible-32x32-interior-area-margin-v2"
        or evidence.get("ordering")
        != (
            "width-major,witness-major,primitive-major,"
            "tile-major,pull-offset-major"
        )
        or evidence.get("uncoveredRecordSentinel") != "0xffffffffffffffff"
        or evidence.get("sourcePhysicalTruthTableSha256") != SOURCE_TRUTH_SHA256
        or evidence.get("preregistrationFile")
        != "Analysis/raster_reciprocal_sweep_preregistration.json"
        or evidence.get("preregistrationSha256")
        != sha256_path(PREREGISTRATION_PATH)
        or preregistration.get("discoveryObservedAtPreregistration") is not False
        or evidence.get("bytes") != expected_bytes
        or not output_path.is_file()
        or output_path.stat().st_size != expected_bytes
    ):
        raise ValueError("reciprocal-sweep manifest differs")
    if validate_record_layout(output_path, widths) != evidence.get("sha256"):
        raise ValueError("reciprocal-sweep file hash differs")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    arguments = parser.parse_args()
    validate(arguments.root)


if __name__ == "__main__":
    main()
