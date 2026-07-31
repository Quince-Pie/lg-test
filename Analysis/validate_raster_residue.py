#!/usr/bin/env python3
"""Validate inherited raster product-lattice residue evidence."""

import argparse
import hashlib
import json
import struct
from pathlib import Path


SCHEMA_VERSION = 21
RIG_VERSION = "metal-raster-interpolant-probe-21.0.0"
HOLDOUT_WIDTHS = frozenset(range(37, 128, 6))
TARGET_NUMERATORS_BY_SHIFT = {
    0: (0, 40, 42, 44, 46, 48, 50, 63),
    1: (0, 20, 22, 24, 26, 28, 30, 63),
}
TARGET_DENOMINATOR = 64


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


def product_floor_residue(numerator, dimension):
    reciprocal_binary_exponent = reciprocal_exponent(dimension)
    reciprocal_significand = rounded_quotient_nearest_even(
        1 << (24 - reciprocal_binary_exponent),
        dimension,
    )
    product = numerator * reciprocal_significand
    product_shift = product.bit_length() - 27
    if product_shift <= 0:
        raise ValueError("residue product shift is not positive")
    return (product >> product_shift) & 7


def residue_candidate_groups(dimension, normalization_shift):
    reciprocal_binary_exponent = reciprocal_exponent(dimension)
    quotient_binary_exponent = reciprocal_binary_exponent - normalization_shift
    reciprocal_significand = rounded_quotient_nearest_even(
        1 << (24 - reciprocal_binary_exponent),
        dimension,
    )
    candidates = [[] for _ in range(8)]
    for numerator in range(1, 65_536):
        if not ratio_has_binary_exponent(
            numerator,
            dimension,
            quotient_binary_exponent,
        ):
            continue
        product = numerator * reciprocal_significand
        product_shift = product.bit_length() - 27
        if product_shift <= 0:
            raise ValueError("residue product shift is not positive")
        modulus = 1 << product_shift
        remainder = product & (modulus - 1)
        floor_index = product >> product_shift
        candidates[floor_index & 7].append(
            (numerator, remainder, modulus)
        )
    return candidates


def residue_numerator_banks(dimension, normalization_shift):
    candidates = residue_candidate_groups(dimension, normalization_shift)
    reachable_residues = [
        residue for residue, group in enumerate(candidates) if group
    ]
    if not reachable_residues:
        return None

    used_numerators = set()
    banks = []
    for target_numerator in TARGET_NUMERATORS_BY_SHIFT[normalization_shift]:
        available = [
            sorted(
                (
                    candidate
                    for candidate in group
                    if candidate[0] not in used_numerators
                ),
                key=lambda candidate: (
                    abs(
                        TARGET_DENOMINATOR * candidate[1]
                        - target_numerator * candidate[2]
                    ),
                    candidate[0],
                ),
            )
            for group in candidates
        ]
        if any(not available[residue] for residue in reachable_residues):
            raise ValueError("a reachable residue has no unused numerator")
        selected_count = [0] * 8
        selected = []
        while len(selected) < 8:
            minimum_count = min(
                selected_count[residue]
                for residue in reachable_residues
            )
            eligible = [
                residue
                for residue in reachable_residues
                if selected_count[residue] == minimum_count
            ]
            residue = min(
                eligible,
                key=lambda item: (
                    abs(
                        TARGET_DENOMINATOR
                        * available[item][selected_count[item]][1]
                        - target_numerator
                        * available[item][selected_count[item]][2]
                    ),
                    available[item][selected_count[item]][0],
                    item,
                ),
            )
            selected.append(
                available[residue][selected_count[residue]][0]
            )
            selected_count[residue] += 1

        selected_residues = {
            product_floor_residue(numerator, dimension)
            for numerator in selected
        }
        if (
            len(set(selected)) != 8
            or selected_residues != set(reachable_residues)
        ):
            raise ValueError(
                "residue selection does not cover its reachable lattice"
            )
        used_numerators.update(selected)
        banks.append(selected)
    if len(used_numerators) != 64:
        raise ValueError("residue matrix numerators are not unique")
    return banks


def expected_residue_records():
    records = []
    for dimension in range(32, 128):
        role = "holdout" if dimension in HOLDOUT_WIDTHS else "discovery"
        base_case = f"tomography-discovery-factor-h064-w{dimension:03d}"
        for normalization_shift in range(2):
            banks = residue_numerator_banks(
                dimension,
                normalization_shift,
            )
            if banks is None:
                if normalization_shift != 0 or dimension.bit_count() != 1:
                    raise ValueError("an unexpected residue branch is empty")
                continue
            targets = TARGET_NUMERATORS_BY_SHIFT[normalization_shift]
            for target_numerator, numerators in zip(
                targets,
                banks,
                strict=True,
            ):
                records.append(
                    {
                        "name": (
                            f"numerator-residue-{role}-"
                            f"factor-h064-w{dimension:03d}-"
                            f"shift-{normalization_shift}-"
                            f"phase-{target_numerator:02d}"
                        ),
                        "role": role,
                        "baseCase": base_case,
                        "normalizationShift": normalization_shift,
                        "thresholdTargetNumerator": target_numerator,
                        "thresholdTargetDenominator": TARGET_DENOMINATOR,
                        "productFloorResiduesModulo8": [
                            product_floor_residue(numerator, dimension)
                            for numerator in numerators
                        ],
                        "numerators": numerators,
                        "deltaBits": [
                            float32_bits(numerator / 65_536)
                            for numerator in numerators
                        ],
                    }
                )
    if len(records) != 1_520:
        raise ValueError("residue case count differs")
    if (
        sum(record["role"] == "discovery" for record in records) != 1_264
        or sum(record["role"] == "holdout" for record in records) != 256
    ):
        raise ValueError("residue role counts differ")
    if len({record["name"] for record in records}) != len(records):
        raise ValueError("residue case names are not unique")
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

    expected_records = expected_residue_records()
    records = manifest.get("numeratorResidueCases", [])
    projection = [
        {
            "name": record.get("name"),
            "role": record.get("role"),
            "baseCase": record.get("baseCase"),
            "normalizationShift": record.get("normalizationShift"),
            "thresholdTargetNumerator": record.get(
                "thresholdTargetNumerator"
            ),
            "thresholdTargetDenominator": record.get(
                "thresholdTargetDenominator"
            ),
            "productFloorResiduesModulo8": record.get(
                "productFloorResiduesModulo8"
            ),
            "numerators": record.get("deltaNumerators"),
            "deltaBits": record.get("deltaBits"),
        }
        for record in records
    ]
    if projection != expected_records:
        raise ValueError("numerator residue case set differs")

    for record in records:
        name = record["name"]
        base_name = record["baseCase"]
        base = tomography_by_name.get(base_name)
        if base is None:
            raise ValueError(f"{name} residue base is absent")
        crop = record.get("crop")
        if (
            record.get("role") not in {"discovery", "holdout"}
            or record.get("primitiveMaskCase") != base_name
            or crop != base.get("crop")
            or record.get("target") != base.get("target")
            or record.get("deltaDenominator") != 65_536
        ):
            raise ValueError(f"{name} residue metadata differs")

        outputs = record.get("outputs", [])
        if (
            len(outputs) != 8
            or {output.get("deltaIndex") for output in outputs} != set(range(8))
        ):
            raise ValueError(f"{name} residue outputs differ")
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
                raise ValueError(f"{name} residue surface {index} differs")


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
