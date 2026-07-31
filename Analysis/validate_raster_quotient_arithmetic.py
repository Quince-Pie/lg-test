#!/usr/bin/env python3
"""Validate schema-21 exhaustive Metal quotient arithmetic controls."""

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


JsonObject = dict[str, Any]

SCHEMA_VERSION = 21
RIG_VERSION = "metal-raster-interpolant-probe-21.0.0"
HOLDOUT_WIDTHS = tuple(range(37, 128, 6))
DISCOVERY_WIDTHS = tuple(
    width for width in range(32, 128) if width not in HOLDOUT_WIDTHS
)
NUMERATOR_LOWER = 32_768
NUMERATOR_UPPER = 65_535
NUMERATOR_COUNT = NUMERATOR_UPPER - NUMERATOR_LOWER + 1
VECTORS_PER_SAMPLE = 3
COMPONENTS = (
    "operatorDivide",
    "fastDivide",
    "preciseDivide",
    "fastReciprocalProduct",
    "preciseReciprocalProduct",
    "operatorNormalizedIntegerDivide",
    "fastNormalizedIntegerDivide",
    "preciseNormalizedIntegerDivide",
    "fastReciprocalWidth",
    "preciseReciprocalWidth",
    "operatorReciprocalWidth",
    "deltaControl",
)
RECORD = struct.Struct("<12I")


def expected_file_bytes() -> int:
    return len(DISCOVERY_WIDTHS) * NUMERATOR_COUNT * RECORD.size


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def float32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def finite_positive(bits: int) -> bool:
    return bits >> 31 == 0 and bits & 0x7F800000 != 0x7F800000


def validate_record(
    record: tuple[int, ...],
    *,
    expected_delta_bits: int,
    reciprocal_bits: tuple[int, int, int] | None,
) -> tuple[int, int, int]:
    if len(record) != len(COMPONENTS):
        raise ValueError("quotient-arithmetic record width differs")
    if not all(finite_positive(bits) and bits != 0 for bits in record):
        raise ValueError("quotient-arithmetic record is not finite and positive")
    if record[-1] != expected_delta_bits:
        raise ValueError("quotient-arithmetic delta ordering differs")
    observed_reciprocals = record[8:11]
    if reciprocal_bits is not None and observed_reciprocals != reciprocal_bits:
        raise ValueError("quotient-arithmetic reciprocal changed within a width")
    return observed_reciprocals


def validate(root: Path) -> None:
    manifest_path = root / "manifest.json"
    manifest: JsonObject = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("schemaVersion") != SCHEMA_VERSION
        or manifest.get("rigVersion") != RIG_VERSION
    ):
        raise ValueError("raster quotient arithmetic schema 21 is required")

    probe = manifest.get("quotientArithmeticProbe", {})
    path = root / str(probe.get("file", ""))
    if (
        probe.get("role") != "discovery"
        or probe.get("widths") != list(DISCOVERY_WIDTHS)
        or probe.get("holdoutWidthsExcluded") != list(HOLDOUT_WIDTHS)
        or probe.get("numeratorLowerInclusive") != NUMERATOR_LOWER
        or probe.get("numeratorUpperInclusive") != NUMERATOR_UPPER
        or probe.get("deltaDenominator") != 65_536
        or probe.get("vectorsPerSample") != VECTORS_PER_SAMPLE
        or probe.get("components") != list(COMPONENTS)
        or probe.get("ordering") != "width-major,numerator-major,component-major"
        or probe.get("bytes") != expected_file_bytes()
        or not path.is_file()
        or path.stat().st_size != expected_file_bytes()
        or sha256_file(path) != probe.get("sha256")
    ):
        raise ValueError("raster quotient arithmetic metadata differs")

    expected_deltas = tuple(
        float32_bits(numerator * 2.0**-16)
        for numerator in range(NUMERATOR_LOWER, NUMERATOR_UPPER + 1)
    )
    width_bytes = NUMERATOR_COUNT * RECORD.size
    with path.open("rb") as stream:
        for width in DISCOVERY_WIDTHS:
            block = stream.read(width_bytes)
            if len(block) != width_bytes:
                raise ValueError(f"width {width} arithmetic block is truncated")
            reciprocals: tuple[int, int, int] | None = None
            for expected_delta, record in zip(
                expected_deltas,
                RECORD.iter_unpack(block),
                strict=True,
            ):
                reciprocals = validate_record(
                    record,
                    expected_delta_bits=expected_delta,
                    reciprocal_bits=reciprocals,
                )
        if stream.read(1):
            raise ValueError("quotient-arithmetic file has trailing bytes")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    arguments = parser.parse_args()
    validate(arguments.root)


if __name__ == "__main__":
    main()
