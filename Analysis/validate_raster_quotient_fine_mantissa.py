#!/usr/bin/env python3
"""Validate schema-23 prospective full-mantissa quotient evidence."""

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

import validate_raster_quotient_corpus as corpus


WIDTHS = (
    33,
    37,
    43,
    44,
    49,
    52,
    55,
    59,
    61,
    67,
    73,
    79,
    85,
    90,
    91,
    96,
    97,
    100,
    101,
    103,
    109,
    115,
    121,
    127,
)
SAMPLE_COUNT = 8_192
PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_quotient_fine_mantissa_preregistration.json"
)
SIGNIFICAND_SHA256 = "c55831b5269944773952e478ed7f6f0c7ec7c6f9d7b1a54f230ca34a3c8ad0ac"
DELTA_BITS_SHA256 = "9111298595dd270f0c2142382920a3d0d196044e67ab75054bdcb899736742ab"
PREDICTED_TRUTH_SHA256 = (
    "069c044c3b38d0535656c0a6e4d12c07a80a2b9b528ae4eb80c4735381c2469a"
)
RECIPROCAL_UPWARD_EXCEPTIONS = {45, 48, 50, 90, 96, 100, 101}


def generate_significands():
    result = []
    seen = set()
    for bank in range(16):
        numerator = 32_768 + 2_048 * bank + ((73 * bank + 19) & 255)
        for phase in range(256):
            significand = (numerator << 8) | phase
            if significand in seen:
                raise ValueError("structured fine-mantissa sample repeats")
            seen.add(significand)
            result.append(significand)
    state = 0x31_41_59
    while len(result) < SAMPLE_COUNT:
        state = (state * 0x5B_D1_E9_95 + 0x6C_8E_9C_F5) & 0x7F_FF_FF
        significand = 0x80_00_00 | state
        if significand not in seen:
            seen.add(significand)
            result.append(significand)
    if (
        len(result) != SAMPLE_COUNT
        or len(seen) != SAMPLE_COUNT
        or not all(0x80_00_00 <= value <= 0xFF_FF_FF for value in result)
    ):
        raise ValueError("fine-mantissa sample generator differs")
    return result


def uint32_sha256(values):
    digest = hashlib.sha256()
    for value in values:
        digest.update(struct.pack("<I", value))
    return digest.hexdigest()


def delta_bits(significands):
    return [0x3F_00_00_00 | (significand & 0x7F_FF_FF) for significand in significands]


def nearest_even_reciprocal_index(width):
    exponent = -(width - 1).bit_length()
    numerator = 1 << (24 - exponent)
    quotient, remainder = divmod(numerator, width)
    doubled = 2 * remainder
    return quotient + (doubled > width or (doubled == width and quotient & 1))


def predicted_reciprocal_index(width):
    return nearest_even_reciprocal_index(width) + (
        width in RECIPROCAL_UPWARD_EXCEPTIONS
    )


def predicted_float_bits(width, reciprocal, significand):
    exact_product = significand * reciprocal
    product_shift = exact_product.bit_length() - 27
    truncated_product = significand * (reciprocal & ~0xFFFF)
    for bit in range(16):
        if reciprocal & (1 << bit):
            partial = significand << bit
            truncated_product += (partial >> 16) << 16
    product_index = (truncated_product + 0x14_00_00) >> product_shift
    reciprocal_exponent = -(width - 1).bit_length()
    value = math.ldexp(
        product_index,
        reciprocal_exponent - 24 - 24 + product_shift,
    )
    return struct.unpack("<I", struct.pack("<f", value))[0]


def predicted_truth_sha256(reciprocals, significands):
    digest = hashlib.sha256()
    for record in reciprocals:
        width = int(record["width"])
        reciprocal = int(record["reciprocal25Index"])
        block = bytearray()
        for significand in significands:
            block.extend(
                struct.pack(
                    "<I",
                    predicted_float_bits(
                        width,
                        reciprocal,
                        significand,
                    ),
                )
            )
        digest.update(block)
    return digest.hexdigest()


def load_preregistration():
    preregistration = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))
    model = preregistration.get("model", {})
    generator = preregistration.get("sampleGenerator", {})
    domain = preregistration.get("domain", {})
    reciprocals = preregistration.get("reciprocalPredictions", [])
    prediction = preregistration.get("predictedTruthTable", {})
    significands = generate_significands()
    generated_delta_bits = delta_bits(significands)
    if (
        preregistration.get("schemaVersion") != 1
        or preregistration.get("role") != "prospective-full-mantissa-prediction"
        or preregistration.get("fineMantissaObservedAtPreregistration") is not False
        or model
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
        or generator
        != {
            "sampleCount": SAMPLE_COUNT,
            "structuredSampleCount": 4_096,
            "structuredBankCount": 16,
            "structuredPhaseCount": 256,
            "structuredBankNumerator": ("32768 + 2048*bank + ((73*bank+19)&255)"),
            "permutedSampleCount": 4_096,
            "lcgInitialState": 0x31_41_59,
            "lcgMultiplier": 0x5B_D1_E9_95,
            "lcgIncrement": 0x6C_8E_9C_F5,
            "lcgMask": 0x7F_FF_FF,
            "significandSha256": SIGNIFICAND_SHA256,
            "deltaBitsSha256": DELTA_BITS_SHA256,
        }
        or uint32_sha256(significands) != SIGNIFICAND_SHA256
        or uint32_sha256(generated_delta_bits) != DELTA_BITS_SHA256
        or domain
        != {
            "widths": list(WIDTHS),
            "ordering": "width-major,sample-major",
        }
        or [record.get("width") for record in reciprocals] != list(WIDTHS)
        or any(
            record.get("reciprocalExponent") != -(int(record["width"]) - 1).bit_length()
            or record.get("reciprocal25Index")
            != predicted_reciprocal_index(int(record["width"]))
            for record in reciprocals
        )
        or prediction
        != {
            "dtype": "little-endian uint32 float bits",
            "shape": [len(WIDTHS), SAMPLE_COUNT],
            "bytes": 786_432,
            "sha256": PREDICTED_TRUTH_SHA256,
        }
        or predicted_truth_sha256(
            reciprocals,
            significands,
        )
        != PREDICTED_TRUTH_SHA256
    ):
        raise ValueError("fine-mantissa preregistration differs")
    return preregistration


def expected_file_bytes():
    return (
        len(WIDTHS)
        * SAMPLE_COUNT
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
        for width in WIDTHS
    ]


def validate(root):
    preregistration = load_preregistration()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schemaVersion") != corpus.SCHEMA_VERSION:
        raise ValueError("raster-interpolant schema differs")
    if manifest.get("rigVersion") != corpus.RIG_VERSION:
        raise ValueError("raster-interpolant rig differs")
    evidence = manifest.get("quotientFineMantissaCorpus", {})
    path = root / str(evidence.get("file", ""))
    if (
        evidence.get("role") != "prospective-holdout"
        or evidence.get("widths") != list(WIDTHS)
        or evidence.get("sampleCountPerWidth") != SAMPLE_COUNT
        or evidence.get("operandPrecisionBits") != 24
        or evidence.get("structuredSampleCount") != 4_096
        or evidence.get("permutedSampleCount") != 4_096
        or evidence.get("significandGenerator")
        != "16 banks x 256 low-byte phases, then masked LCG"
        or evidence.get("structuredBankNumerator")
        != "32768 + 2048*bank + ((73*bank+19)&255)"
        or evidence.get("lcgInitialState") != 0x31_41_59
        or evidence.get("lcgMultiplier") != 0x5B_D1_E9_95
        or evidence.get("lcgIncrement") != 0x6C_8E_9C_F5
        or evidence.get("lcgMask") != 0x7F_FF_FF
        or evidence.get("significandSha256") != SIGNIFICAND_SHA256
        or evidence.get("deltaBitsSha256") != DELTA_BITS_SHA256
        or evidence.get("height") != 64
        or evidence.get("originX") != 17
        or evidence.get("originY") != 19
        or evidence.get("targetWidth") != 160
        or evidence.get("targetHeight") != 160
        or evidence.get("primitiveCount") != corpus.PRIMITIVE_COUNT
        or evidence.get("tileCount") != corpus.TILE_COUNT
        or evidence.get("uncoveredRecordSentinel") != "0xffffffffffffffff"
        or evidence.get("pullOffsets")
        != [{"x": 0.0, "y": 0.5}, {"x": 0.9375, "y": 0.5}]
        or evidence.get("components") != list(corpus.COMPONENTS)
        or evidence.get("ordering")
        != ("width-major,sample-major,primitive-major,tile-major,pull-offset-major")
        or evidence.get("positionsByWidth") != expected_position_records()
        or evidence.get("preregisteredPrediction")
        != {
            "model": "physicalTruncatedRadix2PartialProducts16Bias0x140000",
            "predictionFile": (
                "Analysis/raster_quotient_fine_mantissa_preregistration.json"
            ),
            "truthTableSha256": PREDICTED_TRUTH_SHA256,
        }
        or evidence.get("bytes") != expected_file_bytes()
        or not path.is_file()
        or path.stat().st_size != expected_file_bytes()
        or preregistration.get("fineMantissaObservedAtPreregistration") is not False
    ):
        raise ValueError("fine-mantissa quotient metadata differs")
    digest = corpus.scan_records(
        path,
        (len(WIDTHS) * SAMPLE_COUNT * corpus.PRIMITIVE_COUNT * corpus.TILE_COUNT),
        expected_slots_by_width=[
            {
                position["primitive"] * corpus.TILE_COUNT + position["tile"]
                for position in corpus.expected_positions(width)
            }
            for width in WIDTHS
        ],
        records_per_width=(SAMPLE_COUNT * corpus.PRIMITIVE_COUNT * corpus.TILE_COUNT),
    )
    if digest != evidence.get("sha256"):
        raise ValueError("fine-mantissa quotient hash differs")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    arguments = parser.parse_args()
    validate(arguments.root)


if __name__ == "__main__":
    main()
