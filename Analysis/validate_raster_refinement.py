#!/usr/bin/env python3
"""Validate inherited residual-refinement raster evidence."""

import argparse
import hashlib
import json
import struct
from pathlib import Path


RESIDUAL_ANCHORS = (
    (47, (74, 131, 178, 216)),
    (58, (190,)),
    (62, (103, 163, 197)),
    (76, (89, 108, 127, 146, 165, 184)),
    (78, (30, 31, 88, 90, 212, 214, 251)),
    (81, (9, 37, 68, 140, 196)),
    (83, (50, 76, 158, 159, 233, 241)),
    (84, (39, 54, 136, 157, 178, 187, 208)),
    (86, (40, 45, 100, 110, 143, 153, 186, 196, 239)),
    (88, (62, 73)),
    (89, (4, 89, 117, 139, 206, 224)),
    (93, (56, 137, 189, 230)),
    (98, (2, 173, 187)),
    (119, (31, 91, 158, 218)),
    (124, (103, 163, 197)),
)
REFINEMENT_OFFSETS = tuple(range(-3, 5))
SCHEMA_VERSION = 21
RIG_VERSION = "metal-raster-interpolant-probe-21.0.0"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def float32_bits(value):
    return f"0x{struct.unpack('<I', struct.pack('<f', value))[0]:08x}"


def expected_refinement_records():
    records = []
    for dimension, indices in RESIDUAL_ANCHORS:
        base_name = f"tomography-discovery-factor-h064-w{dimension:03d}"
        for anchor_index in indices:
            anchor = 32_832 + 128 * anchor_index
            numerators = [anchor + offset for offset in REFINEMENT_OFFSETS]
            records.append(
                {
                    "name": (
                        "numerator-refinement-discovery-"
                        f"factor-h064-w{dimension:03d}-"
                        f"anchor-{anchor_index:03d}"
                    ),
                    "baseCase": base_name,
                    "anchorNumeratorIndex": anchor_index,
                    "numerators": numerators,
                    "deltaBits": [
                        float32_bits(numerator / 65_536) for numerator in numerators
                    ],
                }
            )
    if len(records) != 70:
        raise ValueError("numerator refinement anchor count differs")
    if len({record["name"] for record in records}) != len(records):
        raise ValueError("numerator refinement names are not unique")
    return records


def validate(root):
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("raster-interpolant schema differs")
    if manifest.get("rigVersion") != RIG_VERSION:
        raise ValueError("raster-interpolant rig differs")

    tomography = manifest.get("reciprocalTomographyCases", [])
    tomography_by_name = {record["name"]: record for record in tomography}
    if len(tomography_by_name) != len(tomography):
        raise ValueError("reciprocal tomography names are not unique")

    expected_records = expected_refinement_records()
    records = manifest.get("numeratorRefinementCases", [])
    projection = [
        {
            "name": record.get("name"),
            "baseCase": record.get("baseCase"),
            "anchorNumeratorIndex": record.get("anchorNumeratorIndex"),
            "numerators": record.get("deltaNumerators"),
            "deltaBits": record.get("deltaBits"),
        }
        for record in records
    ]
    if projection != expected_records:
        raise ValueError("numerator refinement case set differs")

    for record in records:
        name = record["name"]
        base_name = record["baseCase"]
        base = tomography_by_name.get(base_name)
        if base is None:
            raise ValueError(f"{name} refinement base is absent")
        crop = record.get("crop")
        if (
            record.get("role") != "discovery"
            or "holdout" in name
            or record.get("primitiveMaskCase") != base_name
            or crop != base.get("crop")
            or record.get("target") != base.get("target")
            or record.get("deltaDenominator") != 65_536
        ):
            raise ValueError(f"{name} refinement metadata differs")

        outputs = record.get("outputs", [])
        if len(outputs) != 8 or {output.get("deltaIndex") for output in outputs} != set(
            range(8)
        ):
            raise ValueError(f"{name} refinement outputs differ")
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
                raise ValueError(f"{name} refinement surface {index} differs")


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
