#!/usr/bin/env python3
"""Validate schema-19 compact fixed-function quotient evidence."""

import argparse
import hashlib
import json
import struct
from pathlib import Path


SCHEMA_VERSION = 19
RIG_VERSION = "metal-raster-interpolant-probe-19.0.0"
HOLDOUT_WIDTHS = tuple(range(37, 128, 6))
DISCOVERY_WIDTHS = tuple(
    width for width in range(32, 128) if width not in HOLDOUT_WIDTHS
)
NUMERATOR_LOWER = 32_768
NUMERATOR_UPPER = 65_535
DELTA_DENOMINATOR = 65_536
PRIMITIVE_COUNT = 2
RECORD_BYTES = 8
COMPONENTS = (
    "primitive0XAt0",
    "primitive0XAt15Over16",
    "primitive1XAt0",
    "primitive1XAt15Over16",
)
ORDERING = (
    "width-major,numerator-major,primitive-major,pull-offset-major"
)


def expected_sample_count():
    return len(DISCOVERY_WIDTHS) * (
        NUMERATOR_UPPER - NUMERATOR_LOWER + 1
    )


def expected_file_bytes():
    return expected_sample_count() * PRIMITIVE_COUNT * RECORD_BYTES


def scan_records(path, expected_record_count):
    digest = hashlib.sha256()
    record_count = 0
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            if len(block) % RECORD_BYTES:
                raise ValueError("quotient-corpus block is misaligned")
            digest.update(block)
            for first, second in struct.iter_unpack("<II", block):
                if first == 0xFFFFFFFF and second == 0xFFFFFFFF:
                    raise ValueError(
                        f"quotient-corpus record {record_count} is absent"
                    )
                if (
                    first & 0x80000000
                    or second & 0x80000000
                    or (first >> 23) & 0xFF == 0xFF
                    or (second >> 23) & 0xFF == 0xFF
                    or first > second
                ):
                    raise ValueError(
                        f"quotient-corpus record {record_count} "
                        "is not a finite increasing pull pair"
                    )
                record_count += 1
    if record_count != expected_record_count:
        raise ValueError(
            f"quotient-corpus has {record_count} records; "
            f"expected {expected_record_count}"
        )
    return digest.hexdigest()


def validate(root):
    manifest = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("raster-interpolant schema differs")
    if manifest.get("rigVersion") != RIG_VERSION:
        raise ValueError("raster-interpolant rig differs")

    corpus = manifest.get("quotientCorpus", {})
    path = root / str(corpus.get("file", ""))
    expected_bytes = expected_file_bytes()
    if (
        corpus.get("role") != "discovery"
        or corpus.get("widths") != list(DISCOVERY_WIDTHS)
        or corpus.get("holdoutWidthsExcluded") != list(HOLDOUT_WIDTHS)
        or set(corpus.get("widths", []))
        & set(corpus.get("holdoutWidthsExcluded", []))
        or corpus.get("height") != 1
        or corpus.get("originX") != 17
        or corpus.get("targetWidth") != 160
        or corpus.get("batchSize") != 8_192
        or corpus.get("numeratorLowerInclusive") != NUMERATOR_LOWER
        or corpus.get("numeratorUpperInclusive") != NUMERATOR_UPPER
        or corpus.get("deltaDenominator") != DELTA_DENOMINATOR
        or corpus.get("primitiveCount") != PRIMITIVE_COUNT
        or corpus.get("pullOffsets")
        != [{"x": 0.0, "y": 0.5}, {"x": 0.9375, "y": 0.5}]
        or corpus.get("components") != list(COMPONENTS)
        or corpus.get("ordering") != ORDERING
        or corpus.get("bytes") != expected_bytes
        or not path.is_file()
        or path.stat().st_size != expected_bytes
    ):
        raise ValueError("quotient-corpus metadata differs")

    digest = scan_records(
        path,
        expected_sample_count() * PRIMITIVE_COUNT,
    )
    if digest != corpus.get("sha256"):
        raise ValueError("quotient-corpus hash differs")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    arguments = parser.parse_args()
    validate(arguments.root)


if __name__ == "__main__":
    main()
