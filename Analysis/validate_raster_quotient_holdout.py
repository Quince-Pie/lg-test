#!/usr/bin/env python3
"""Validate schema-23 sealed fixed-function quotient evidence."""

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

import validate_raster_quotient_corpus as corpus


PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_quotient_holdout_preregistration.json"
)
PREDICTED_TRUTH_SHA256 = (
    "0ad8899707021f22bc832724a73efa1bd3f7f3dffff7be182ce15885464b6fbb"
)


def expected_sample_count():
    return len(corpus.HOLDOUT_WIDTHS) * (
        corpus.NUMERATOR_UPPER - corpus.NUMERATOR_LOWER + 1
    )


def expected_file_bytes():
    return (
        expected_sample_count()
        * corpus.PRIMITIVE_COUNT
        * corpus.TILE_COUNT
        * corpus.RECORD_BYTES
    )


def expected_position_records():
    return [
        {
            "width": width,
            "positions": corpus.expected_positions(width),
        }
        for width in corpus.HOLDOUT_WIDTHS
    ]


def nearest_even_reciprocal_index(width):
    exponent = -(width - 1).bit_length()
    numerator = 1 << (24 - exponent)
    quotient, remainder = divmod(numerator, width)
    doubled = 2 * remainder
    return quotient + (doubled > width or (doubled == width and quotient & 1))


def predicted_float_bits(width, reciprocal, numerator):
    exact_product = numerator * reciprocal
    product_shift = exact_product.bit_length() - 27
    truncated_product = numerator * (reciprocal & ~0xFF)
    for bit in range(8):
        if reciprocal & (1 << bit):
            partial = numerator << bit
            truncated_product += (partial >> 8) << 8
    product_index = (truncated_product + 0x1400) >> product_shift
    reciprocal_exponent = -(width - 1).bit_length()
    value = math.ldexp(
        product_index,
        reciprocal_exponent - 24 - 16 + product_shift,
    )
    return struct.unpack("<I", struct.pack("<f", value))[0]


def predicted_truth_sha256(reciprocals):
    digest = hashlib.sha256()
    for record in reciprocals:
        width = int(record["width"])
        reciprocal = int(record["reciprocal25Index"])
        block = bytearray()
        for numerator in range(
            corpus.NUMERATOR_LOWER,
            corpus.NUMERATOR_UPPER + 1,
        ):
            block.extend(
                struct.pack(
                    "<I",
                    predicted_float_bits(width, reciprocal, numerator),
                )
            )
        digest.update(block)
    return digest.hexdigest()


def load_preregistration():
    preregistration = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))
    domain = preregistration.get("domain", {})
    model = preregistration.get("model", {})
    prediction = preregistration.get("predictedTruthTable", {})
    reciprocals = preregistration.get("reciprocalPredictions", [])
    if (
        preregistration.get("schemaVersion") != 1
        or preregistration.get("role") != "sealed-holdout-prediction"
        or preregistration.get("holdoutOpenedAtPreregistration") is not False
        or model
        != {
            "name": "truncatedRadix2PartialProducts8Bias0x1400",
            "partialProductRadix": 2,
            "partialProductTruncationBits": 8,
            "roundingBias": 5120,
            "reciprocalModel": "nearestEven25BitReciprocal",
        }
        or domain.get("widths") != list(corpus.HOLDOUT_WIDTHS)
        or domain.get("numeratorLowerInclusive") != corpus.NUMERATOR_LOWER
        or domain.get("numeratorUpperInclusive") != corpus.NUMERATOR_UPPER
        or domain.get("deltaDenominator") != corpus.DELTA_DENOMINATOR
        or domain.get("ordering") != "width-major,numerator-major"
        or [record.get("width") for record in reciprocals]
        != list(corpus.HOLDOUT_WIDTHS)
        or any(
            record.get("reciprocalExponent") != -(int(record["width"]) - 1).bit_length()
            or record.get("reciprocal25Index")
            != nearest_even_reciprocal_index(int(record["width"]))
            for record in reciprocals
        )
        or prediction
        != {
            "dtype": "little-endian uint32 float bits",
            "shape": [
                len(corpus.HOLDOUT_WIDTHS),
                corpus.NUMERATOR_UPPER - corpus.NUMERATOR_LOWER + 1,
            ],
            "bytes": 2_097_152,
            "sha256": PREDICTED_TRUTH_SHA256,
        }
        or predicted_truth_sha256(reciprocals) != PREDICTED_TRUTH_SHA256
    ):
        raise ValueError("quotient-holdout preregistration differs")
    return preregistration


def validate(root):
    preregistration = load_preregistration()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schemaVersion") != corpus.SCHEMA_VERSION:
        raise ValueError("raster-interpolant schema differs")
    if manifest.get("rigVersion") != corpus.RIG_VERSION:
        raise ValueError("raster-interpolant rig differs")

    holdout = manifest.get("quotientHoldoutCorpus", {})
    path = root / str(holdout.get("file", ""))
    expected_bytes = expected_file_bytes()
    if (
        holdout.get("role") != "holdout"
        or holdout.get("widths") != list(corpus.HOLDOUT_WIDTHS)
        or holdout.get("discoveryWidthsExcluded") != list(corpus.DISCOVERY_WIDTHS)
        or set(holdout.get("widths", []))
        & set(holdout.get("discoveryWidthsExcluded", []))
        or holdout.get("height") != 64
        or holdout.get("originX") != 17
        or holdout.get("originY") != 19
        or holdout.get("targetWidth") != 160
        or holdout.get("targetHeight") != 160
        or holdout.get("instanceCount") != 32_768
        or holdout.get("numeratorLowerInclusive") != corpus.NUMERATOR_LOWER
        or holdout.get("numeratorUpperInclusive") != corpus.NUMERATOR_UPPER
        or holdout.get("deltaDenominator") != corpus.DELTA_DENOMINATOR
        or holdout.get("primitiveCount") != corpus.PRIMITIVE_COUNT
        or holdout.get("tileCount") != corpus.TILE_COUNT
        or holdout.get("uncoveredRecordSentinel") != "0xffffffffffffffff"
        or holdout.get("pullOffsets") != [{"x": 0.0, "y": 0.5}, {"x": 0.9375, "y": 0.5}]
        or holdout.get("components") != list(corpus.COMPONENTS)
        or holdout.get("ordering") != corpus.ORDERING
        or holdout.get("positionsByWidth") != expected_position_records()
        or holdout.get("preregisteredPrediction")
        != {
            "model": "truncatedRadix2PartialProducts8Bias0x1400",
            "reciprocalModel": "nearestEven25BitReciprocal",
            "predictionFile": ("Analysis/raster_quotient_holdout_preregistration.json"),
            "truthTableSha256": PREDICTED_TRUTH_SHA256,
        }
        or holdout.get("bytes") != expected_bytes
        or not path.is_file()
        or path.stat().st_size != expected_bytes
        or preregistration.get("holdoutOpenedAtPreregistration") is not False
    ):
        raise ValueError("quotient-holdout metadata differs")

    digest = corpus.scan_records(
        path,
        expected_sample_count() * corpus.PRIMITIVE_COUNT * corpus.TILE_COUNT,
        expected_slots_by_width=[
            {
                position["primitive"] * corpus.TILE_COUNT + position["tile"]
                for position in corpus.expected_positions(width)
            }
            for width in corpus.HOLDOUT_WIDTHS
        ],
        records_per_width=(
            (corpus.NUMERATOR_UPPER - corpus.NUMERATOR_LOWER + 1)
            * corpus.PRIMITIVE_COUNT
            * corpus.TILE_COUNT
        ),
    )
    if digest != holdout.get("sha256"):
        raise ValueError("quotient-holdout hash differs")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    arguments = parser.parse_args()
    validate(arguments.root)


if __name__ == "__main__":
    main()
