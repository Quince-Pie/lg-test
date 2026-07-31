#!/usr/bin/env python3
"""Validate inherited raster product-threshold evidence."""

import argparse
import hashlib
import json
import struct
from pathlib import Path


SCHEMA_VERSION = 23
RIG_VERSION = "metal-raster-interpolant-probe-23.0.0"
HOLDOUT_WIDTHS = frozenset(range(37, 128, 6))
TARGETS_BY_SHIFT = (
    (0, tuple(range(40, 48))),
    (1, tuple(range(22, 30))),
)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def float32_bits(value):
    return f"0x{struct.unpack('<I', struct.pack('<f', value))[0]:08x}"


def rounded_quotient_nearest_even(numerator, denominator):
    quotient, remainder = divmod(numerator, denominator)
    doubled = 2 * remainder
    return quotient + (
        doubled > denominator or (doubled == denominator and quotient & 1)
    )


def reciprocal_exponent(dimension):
    return -(dimension - 1).bit_length()


def ratio_has_binary_exponent(numerator, dimension, exponent):
    denominator = 65_536 * dimension
    scaled = numerator << -exponent
    return denominator <= scaled < 2 * denominator


def threshold_numerators(dimension, normalization_shift, targets):
    reciprocal_binary_exponent = reciprocal_exponent(dimension)
    quotient_binary_exponent = reciprocal_binary_exponent - normalization_shift
    reciprocal_significand = rounded_quotient_nearest_even(
        1 << (24 - reciprocal_binary_exponent),
        dimension,
    )
    selected = []
    for target in targets:
        best = None
        for numerator in range(1, 65_536):
            if numerator in selected or not ratio_has_binary_exponent(
                numerator,
                dimension,
                quotient_binary_exponent,
            ):
                continue
            product = numerator * reciprocal_significand
            product_shift = product.bit_length() - 27
            if product_shift <= 0:
                raise ValueError("threshold product shift is not positive")
            modulus = 1 << product_shift
            remainder = product & (modulus - 1)
            distance = abs(64 * remainder - target * modulus)
            candidate = (distance, numerator)
            if best is None or candidate < best:
                best = candidate
        if best is None:
            return None
        selected.append(best[1])
    if len(set(selected)) != len(targets):
        raise ValueError("threshold numerators are not unique")
    return selected


def expected_threshold_records():
    records = []
    for dimension in range(32, 128):
        role = "holdout" if dimension in HOLDOUT_WIDTHS else "discovery"
        base_case = f"tomography-discovery-factor-h064-w{dimension:03d}"
        for normalization_shift, targets in TARGETS_BY_SHIFT:
            numerators = threshold_numerators(
                dimension,
                normalization_shift,
                targets,
            )
            if numerators is None:
                if normalization_shift != 0 or dimension.bit_count() != 1:
                    raise ValueError("an unexpected threshold branch is empty")
                continue
            records.append(
                {
                    "name": (
                        f"numerator-threshold-{role}-"
                        f"factor-h064-w{dimension:03d}-"
                        f"shift-{normalization_shift}"
                    ),
                    "role": role,
                    "baseCase": base_case,
                    "normalizationShift": normalization_shift,
                    "numerators": numerators,
                    "deltaBits": [
                        float32_bits(numerator / 65_536) for numerator in numerators
                    ],
                }
            )
    if len(records) != 190:
        raise ValueError("threshold case count differs")
    if (
        sum(record["role"] == "discovery" for record in records) != 158
        or sum(record["role"] == "holdout" for record in records) != 32
    ):
        raise ValueError("threshold role counts differ")
    if len({record["name"] for record in records}) != len(records):
        raise ValueError("threshold case names are not unique")
    return records


def validate(root):
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("raster-interpolant schema differs")
    if manifest.get("rigVersion") != RIG_VERSION:
        raise ValueError("raster-interpolant rig differs")

    tomography = manifest.get("reciprocalTomographyCases", [])
    tomography_by_name = {record["name"]: record for record in tomography}
    if len(tomography_by_name) != len(tomography):
        raise ValueError("reciprocal tomography names are not unique")

    expected_records = expected_threshold_records()
    records = manifest.get("numeratorThresholdCases", [])
    projection = [
        {
            "name": record.get("name"),
            "role": record.get("role"),
            "baseCase": record.get("baseCase"),
            "normalizationShift": record.get("normalizationShift"),
            "numerators": record.get("deltaNumerators"),
            "deltaBits": record.get("deltaBits"),
        }
        for record in records
    ]
    if projection != expected_records:
        raise ValueError("numerator threshold case set differs")

    for record in records:
        name = record["name"]
        base_name = record["baseCase"]
        base = tomography_by_name.get(base_name)
        if base is None:
            raise ValueError(f"{name} threshold base is absent")
        crop = record.get("crop")
        if (
            record.get("role") not in {"discovery", "holdout"}
            or record.get("primitiveMaskCase") != base_name
            or crop != base.get("crop")
            or record.get("target") != base.get("target")
            or record.get("deltaDenominator") != 65_536
        ):
            raise ValueError(f"{name} threshold metadata differs")

        outputs = record.get("outputs", [])
        if len(outputs) != 8 or {output.get("deltaIndex") for output in outputs} != set(
            range(8)
        ):
            raise ValueError(f"{name} threshold outputs differ")
        expected_bytes = crop["width"] * crop["height"] * 16
        for output in outputs:
            index = output["deltaIndex"]
            expected_file = f"{name}-ramp-{index}-rgba32ui.raw"
            path = root / output.get("file", "")
            if (
                output.get("file") != expected_file
                or output.get("bytes") != expected_bytes
                or not path.is_file()
                or path.stat().st_size != expected_bytes
                or output.get("components") != "x@0,x@15/16,y@0,y@15/16"
                or output.get("primitiveIDPacking") != "external-base-case"
                or sha256(path) != output.get("sha256")
            ):
                raise ValueError(f"{name} threshold surface {index} differs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    arguments = parser.parse_args()
    try:
        validate(arguments.root)
    except (KeyError, OSError, TypeError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
