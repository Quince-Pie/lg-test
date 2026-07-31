#!/usr/bin/env python3
"""Validate schema-20 compact fixed-function quotient evidence."""

import argparse
import hashlib
import json
import struct
from pathlib import Path


SCHEMA_VERSION = 20
RIG_VERSION = "metal-raster-interpolant-probe-20.0.0"
HOLDOUT_WIDTHS = tuple(range(37, 128, 6))
DISCOVERY_WIDTHS = tuple(
    width for width in range(32, 128) if width not in HOLDOUT_WIDTHS
)
NUMERATOR_LOWER = 32_768
NUMERATOR_UPPER = 65_535
DELTA_DENOMINATOR = 65_536
PRIMITIVE_COUNT = 2
TILE_COUNT = 5
RECORD_BYTES = 8
COMPONENTS = (
    "xAt0",
    "xAt15Over16",
)
ORDERING = (
    "width-major,numerator-major,primitive-major,"
    "tile-major,pull-offset-major"
)


def expected_sample_count():
    return len(DISCOVERY_WIDTHS) * (
        NUMERATOR_UPPER - NUMERATOR_LOWER + 1
    )


def expected_file_bytes():
    return (
        expected_sample_count()
        * PRIMITIVE_COUNT
        * TILE_COUNT
        * RECORD_BYTES
    )


def expected_positions(width):
    origin_x = 17
    origin_y = 19
    height = 64
    positions = []
    for primitive in range(PRIMITIVE_COUNT):
        for tile in range(
            origin_x // 32,
            (origin_x + width - 1) // 32 + 1,
        ):
            lower = max(origin_x, tile * 32) - origin_x
            upper = min(
                origin_x + width - 1,
                tile * 32 + 31,
            ) - origin_x
            local_x = upper if primitive == 0 else lower
            covered = (
                height * (2 * local_x + 1) > width
                if primitive == 0
                else height * (2 * local_x + 1)
                < (2 * height - 1) * width
            )
            if covered:
                positions.append(
                    {
                        "primitive": primitive,
                        "tile": tile,
                        "x": origin_x + local_x,
                        "y": (
                            origin_y + height - 1
                            if primitive == 0
                            else origin_y
                        ),
                    }
                )
    if not 4 <= len(positions) <= 10:
        raise ValueError("quotient-corpus position count differs")
    slots = {
        position["primitive"] * TILE_COUNT + position["tile"]
        for position in positions
    }
    if len(slots) != len(positions):
        raise ValueError("quotient-corpus positions alias")
    return positions


def expected_position_records():
    return [
        {
            "width": width,
            "positions": expected_positions(width),
        }
        for width in DISCOVERY_WIDTHS
    ]


def scan_records(
    path,
    expected_record_count,
    *,
    expected_slots_by_width=None,
    records_per_width=None,
):
    digest = hashlib.sha256()
    record_count = 0
    if expected_slots_by_width is not None and records_per_width is None:
        raise ValueError("records-per-width is required with a position map")
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            if len(block) % RECORD_BYTES:
                raise ValueError("quotient-corpus block is misaligned")
            digest.update(block)
            for first, second in struct.iter_unpack("<II", block):
                absent = first == 0xFFFFFFFF and second == 0xFFFFFFFF
                expected = True
                if expected_slots_by_width is not None:
                    width_index = record_count // records_per_width
                    slot = record_count % (
                        PRIMITIVE_COUNT * TILE_COUNT
                    )
                    expected = (
                        slot in expected_slots_by_width[width_index]
                    )
                if absent and expected:
                    raise ValueError(
                        f"quotient-corpus record {record_count} is absent"
                    )
                if not absent and not expected:
                    raise ValueError(
                        f"quotient-corpus record {record_count} "
                        "was written outside the position map"
                    )
                if absent:
                    record_count += 1
                    continue
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
        or corpus.get("height") != 64
        or corpus.get("originX") != 17
        or corpus.get("originY") != 19
        or corpus.get("targetWidth") != 160
        or corpus.get("targetHeight") != 160
        or corpus.get("instanceCount") != 32_768
        or corpus.get("numeratorLowerInclusive") != NUMERATOR_LOWER
        or corpus.get("numeratorUpperInclusive") != NUMERATOR_UPPER
        or corpus.get("deltaDenominator") != DELTA_DENOMINATOR
        or corpus.get("primitiveCount") != PRIMITIVE_COUNT
        or corpus.get("tileCount") != TILE_COUNT
        or corpus.get("uncoveredRecordSentinel")
        != "0xffffffffffffffff"
        or corpus.get("pullOffsets")
        != [{"x": 0.0, "y": 0.5}, {"x": 0.9375, "y": 0.5}]
        or corpus.get("components") != list(COMPONENTS)
        or corpus.get("ordering") != ORDERING
        or corpus.get("positionsByWidth")
        != expected_position_records()
        or corpus.get("bytes") != expected_bytes
        or not path.is_file()
        or path.stat().st_size != expected_bytes
    ):
        raise ValueError("quotient-corpus metadata differs")

    digest = scan_records(
        path,
        expected_sample_count() * PRIMITIVE_COUNT * TILE_COUNT,
        expected_slots_by_width=[
            {
                position["primitive"] * TILE_COUNT
                + position["tile"]
                for position in expected_positions(width)
            }
            for width in DISCOVERY_WIDTHS
        ],
        records_per_width=(
            (NUMERATOR_UPPER - NUMERATOR_LOWER + 1)
            * PRIMITIVE_COUNT
            * TILE_COUNT
        ),
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
