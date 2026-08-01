#!/usr/bin/env python3
"""Validate the schema-6 tile double-rounding and center-path holdout."""

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

import validate_raster_tile_numerator as base


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 6
RIG_VERSION = "metal-raster-tile-selector-6.0.0"
ROLE = "prospective-tile-double-rounding-center-path-holdout"
TARGET_WIDTH = base.TARGET_WIDTH
TARGET_HEIGHT = base.TARGET_HEIGHT
VIEWPORT_WIDTH = base.VIEWPORT_WIDTH
VIEWPORT_HEIGHT = base.VIEWPORT_HEIGHT
TILE_SIZE = base.TILE_SIZE
TILE_COUNT = base.TILE_COUNT
AXIS_COUNT = base.AXIS_COUNT
PRIMITIVE_COUNT = base.PRIMITIVE_COUNT
EDGE_COUNT = base.EDGE_COUNT
SLOT_COUNT = base.SLOT_COUNT
PULL_NUMERATORS = base.PULL_NUMERATORS
PULL_COUNT = base.PULL_COUNT
RECORD_COMPONENT_COUNT = base.RECORD_COMPONENT_COUNT
RECORD = base.RECORD
SENTINEL = base.SENTINEL
CaptureCase = base.CaptureCase
EndpointCase = base.EndpointCase
SamplePosition = base.SamplePosition
PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_tile_double_rounding_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "0058337191daccdb565e4004f2b519096095b0694f37aa8e4f108f1b77ae7dbe"
)


CASES = (
    CaptureCase("control-square-256", "prospective-control", 256, 256, 384, 384),
    CaptureCase("sealed-center198-x", "sealed-holdout", 198, 607, 16, 208),
    CaptureCase("sealed-center198-y", "sealed-holdout", 607, 198, 208, 16),
    CaptureCase("sealed-center204-x", "sealed-holdout", 204, 613, 25, 205),
    CaptureCase("sealed-center204-y", "sealed-holdout", 613, 204, 205, 25),
    CaptureCase("sealed-center231-x", "sealed-holdout", 231, 683, 16, 170),
    CaptureCase("sealed-center231-y", "sealed-holdout", 683, 231, 170, 16),
    CaptureCase("sealed-center255-x", "sealed-holdout", 255, 647, 25, 188),
    CaptureCase("sealed-center255-y", "sealed-holdout", 647, 255, 188, 25),
    CaptureCase("sealed-center315-x", "sealed-holdout", 315, 673, 31, 175),
    CaptureCase("sealed-center315-y", "sealed-holdout", 673, 315, 175, 31),
    CaptureCase("sealed-center378-x", "sealed-holdout", 378, 719, 31, 152),
    CaptureCase("sealed-center378-y", "sealed-holdout", 719, 378, 152, 31),
    CaptureCase("sealed-center441-x", "sealed-holdout", 441, 661, 31, 181),
    CaptureCase("sealed-center441-y", "sealed-holdout", 661, 441, 181, 31),
    CaptureCase("sealed-reverse220-x", "sealed-holdout", 220, 193, 31, 415),
    CaptureCase("sealed-reverse220-y", "sealed-holdout", 193, 220, 415, 31),
    CaptureCase("sealed-reverse350-x", "sealed-holdout", 350, 701, 83, 161),
    CaptureCase("sealed-reverse350-y", "sealed-holdout", 701, 350, 161, 83),
    CaptureCase("sealed-reverse351-x", "sealed-holdout", 351, 719, 31, 152),
    CaptureCase("sealed-reverse351-y", "sealed-holdout", 719, 351, 152, 31),
)

ZERO_DELTA_UNITS = (5, 8, 12, 16, 23, 24, 30, 31)
PRIMARY_TRANSLATED_BASE = ("b2", 0x3F00_0000)
PRIMARY_TRANSLATED_RESIDUES = (0, 1, 7, 31)
PRIMARY_NATIVE_SPANS = (3, 4, 5, 6, 7, 8, 29, 30, 31)
TRANSFER_TRANSLATED_BASES = (
    ("b0", 0x3E00_0000),
    ("b1", 0x3E80_0000),
    ("b3", 0x3F80_0000),
)
TRANSFER_TRANSLATED_RESIDUES = (0, 7)
TRANSFER_NATIVE_SPANS = (4, 7, 8, 30)


def translated_endpoint_pair(
    base_name: str,
    base_bits: int,
    residue: int,
    span: int,
) -> tuple[EndpointCase, EndpointCase]:
    low = base_bits + residue
    high = low + span
    stem = f"translated-{base_name}-r{residue:02d}-s{span:02d}"
    return (
        EndpointCase(f"{stem}-forward", "arithmetic-holdout", low, high),
        EndpointCase(f"{stem}-reverse", "arithmetic-holdout", high, low),
    )


def holdout_endpoints() -> tuple[EndpointCase, ...]:
    result = [
        EndpointCase("zero-to-one", "prospective-control", 0, 0x3F80_0000),
        EndpointCase("one-to-zero", "prospective-control", 0x3F80_0000, 0),
    ]
    for units in ZERO_DELTA_UNITS:
        delta_bits = base.float32_bits(units * 2.0**-25)
        result.extend(
            (
                EndpointCase(
                    f"zero-u{units:02d}-forward",
                    "arithmetic-holdout",
                    0,
                    delta_bits,
                ),
                EndpointCase(
                    f"zero-u{units:02d}-reverse",
                    "arithmetic-holdout",
                    delta_bits,
                    0,
                ),
            )
        )
    primary_name, primary_bits = PRIMARY_TRANSLATED_BASE
    for residue in PRIMARY_TRANSLATED_RESIDUES:
        for span in PRIMARY_NATIVE_SPANS:
            result.extend(
                translated_endpoint_pair(
                    primary_name,
                    primary_bits,
                    residue,
                    span,
                )
            )
    for base_name, base_bits in TRANSFER_TRANSLATED_BASES:
        for residue in TRANSFER_TRANSLATED_RESIDUES:
            for span in TRANSFER_NATIVE_SPANS:
                result.extend(
                    translated_endpoint_pair(base_name, base_bits, residue, span)
                )
    return tuple(result)


ENDPOINTS = holdout_endpoints()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def sample_positions(capture_case: CaptureCase) -> tuple[SamplePosition, ...]:
    return base.sample_positions(capture_case)


def uint32_sha256(values: list[int] | tuple[int, ...]) -> str:
    return base.uint32_sha256(values)


def case_words() -> list[int]:
    return [
        value
        for capture_case in CASES
        for value in (
            capture_case.width,
            capture_case.height,
            capture_case.originX,
            capture_case.originY,
        )
    ]


def endpoint_words() -> list[int]:
    return [
        value
        for endpoint in ENDPOINTS
        for value in (endpoint.lowBits, endpoint.highBits)
    ]


def sample_words() -> list[int]:
    return [
        value
        for case_index, capture_case in enumerate(CASES)
        for sample in sample_positions(capture_case)
        for value in (
            case_index,
            sample.axis,
            sample.primitive,
            sample.tile,
            sample.edge,
            sample.x,
            sample.y,
            sample.slot,
        )
    ]


def raw_bytes() -> int:
    return len(CASES) * len(ENDPOINTS) * SLOT_COUNT * RECORD.size


def layout_metadata() -> JsonObject:
    positions = [sample_positions(capture_case) for capture_case in CASES]
    return {
        "caseCount": len(CASES),
        "endpointCount": len(ENDPOINTS),
        "axisCount": AXIS_COUNT,
        "primitiveCount": PRIMITIVE_COUNT,
        "edgeCount": EDGE_COUNT,
        "tileCount": TILE_COUNT,
        "slotCount": SLOT_COUNT,
        "pullCount": PULL_COUNT,
        "recordComponentCount": RECORD_COMPONENT_COUNT,
        "recordBytes": RECORD.size,
        "recordCount": len(CASES) * len(ENDPOINTS) * SLOT_COUNT,
        "rawBytes": raw_bytes(),
        "expectedRecordCount": sum(len(value) for value in positions) * len(ENDPOINTS),
        "caseWordsSha256": uint32_sha256(case_words()),
        "endpointWordsSha256": uint32_sha256(endpoint_words()),
        "sampleWordsSha256": uint32_sha256(sample_words()),
        "samplesPerCase": [len(value) for value in positions],
    }


def endpoint_metadata() -> list[JsonObject]:
    return [
        {
            "name": endpoint.name,
            "role": endpoint.role,
            "lowBits": f"0x{endpoint.lowBits:08x}",
            "highBits": f"0x{endpoint.highBits:08x}",
        }
        for endpoint in ENDPOINTS
    ]


def record_components() -> list[str]:
    return [
        *(f"axis-pull@{value}/16" for value in PULL_NUMERATORS),
        "center",
        "axis-derivative(center)",
    ]


def pull_offsets() -> JsonObject:
    return {
        "x": [[value / 16, 0.5] for value in PULL_NUMERATORS],
        "y": [[0.5, value / 16] for value in PULL_NUMERATORS],
    }


def capture_metadata() -> JsonObject:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "rigVersion": RIG_VERSION,
        "role": ROLE,
        "caseCount": len(CASES),
        "endpointCount": len(ENDPOINTS),
        "caseWordsSha256": uint32_sha256(case_words()),
        "endpointWordsSha256": uint32_sha256(endpoint_words()),
        "sampleWordsSha256": uint32_sha256(sample_words()),
        "sealedCases": [
            value.name for value in CASES if value.role == "sealed-holdout"
        ],
        "zeroDeltaUnitsAtBinary32ExponentMinus25": list(ZERO_DELTA_UNITS),
        "primaryTranslatedBase": {
            "name": PRIMARY_TRANSLATED_BASE[0],
            "bits": f"0x{PRIMARY_TRANSLATED_BASE[1]:08x}",
            "residues": list(PRIMARY_TRANSLATED_RESIDUES),
            "nativeSpans": list(PRIMARY_NATIVE_SPANS),
        },
        "transferTranslatedBases": [
            {"name": name, "bits": f"0x{bits:08x}"}
            for name, bits in TRANSFER_TRANSLATED_BASES
        ],
        "transferTranslatedResidues": list(TRANSFER_TRANSLATED_RESIDUES),
        "transferNativeSpans": list(TRANSFER_NATIVE_SPANS),
        "recordComponents": record_components(),
        "pullOffsetsByAxis": pull_offsets(),
        "layout": layout_metadata(),
    }


def load_preregistration() -> JsonObject:
    preregistration: JsonObject = json.loads(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    if (
        sha256_path(PREREGISTRATION_PATH) != PREREGISTRATION_SHA256
        or preregistration.get("schemaVersion") != 1
        or preregistration.get("role")
        != "prospective-double-rounding-and-center-path-holdout"
        or preregistration.get("sealedHoldoutOpenedAtPreregistration") is not False
        or preregistration.get("capture") != capture_metadata()
    ):
        raise ValueError("tile double-rounding preregistration differs")
    return preregistration


def validate(root: Path) -> JsonObject:
    preregistration = load_preregistration()
    manifest: JsonObject = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    evidence = manifest.get("rasterTileNumerator", {})
    raw_path = root / str(evidence.get("file", ""))
    if (
        manifest.get("schemaVersion") != SCHEMA_VERSION
        or manifest.get("rigVersion") != RIG_VERSION
        or not isinstance(manifest.get("ciCommit"), str)
        or len(str(manifest.get("ciCommit"))) != 40
        or evidence.get("role") != ROLE
        or evidence.get("preregistrationFile")
        != "Analysis/raster_tile_double_rounding_preregistration.json"
        or evidence.get("preregistrationSha256") != PREREGISTRATION_SHA256
        or evidence.get("layout") != layout_metadata()
        or evidence.get("cases") != [asdict(value) for value in CASES]
        or evidence.get("endpoints") != endpoint_metadata()
        or evidence.get("recordComponents") != record_components()
        or evidence.get("pullOffsetsByAxis") != pull_offsets()
        or evidence.get("ordering")
        != "case-major,endpoint-major,axis-primitive-tile-edge-slot-major,component-minor"
        or evidence.get("bytes") != raw_bytes()
        or not raw_path.is_file()
        or raw_path.stat().st_size != raw_bytes()
        or evidence.get("sha256") != sha256_path(raw_path)
    ):
        raise ValueError("tile double-rounding manifest differs")

    raw = raw_path.read_bytes()
    expected_records = 0
    finite_words = 0
    control_records = 0
    control_pull_mismatches = 0
    records_by_role: Counter[str] = Counter()
    for case_index, capture_case in enumerate(CASES):
        expected_by_slot = {
            sample.slot: sample for sample in sample_positions(capture_case)
        }
        for endpoint_index, endpoint in enumerate(ENDPOINTS):
            for slot in range(SLOT_COUNT):
                record_index = (
                    case_index * len(ENDPOINTS) + endpoint_index
                ) * SLOT_COUNT + slot
                record = RECORD.unpack_from(raw, record_index * RECORD.size)
                sample = expected_by_slot.get(slot)
                if sample is None:
                    if record != SENTINEL:
                        raise ValueError(
                            f"undeclared double-rounding record {record_index} was written"
                        )
                    continue
                expected_records += 1
                records_by_role[capture_case.role] += 1
                if record == SENTINEL or not all(base.finite(bits) for bits in record):
                    raise ValueError(
                        f"double-rounding record {record_index} is absent or nonfinite"
                    )
                finite_words += len(record)
                if capture_case.name == "control-square-256" and endpoint.name in {
                    "zero-to-one",
                    "one-to-zero",
                }:
                    control_records += 1
                    control_pull_mismatches += record[:PULL_COUNT] != (
                        base.control_pull_prediction(capture_case, endpoint, sample)
                    )

    if (
        expected_records != layout_metadata()["expectedRecordCount"]
        or control_records == 0
        or control_pull_mismatches != 0
    ):
        raise ValueError("tile double-rounding prospective control differs")
    return {
        "rasterTileDoubleRoundingValidationSchemaVersion": 1,
        "manifestSha256": sha256_path(root / "manifest.json"),
        "rawSha256": sha256_path(raw_path),
        "expectedRecords": expected_records,
        "finiteWords": finite_words,
        "recordsByCaseRole": dict(sorted(records_by_role.items())),
        "prospectiveControlRecords": control_records,
        "prospectiveControlPullMismatches": control_pull_mismatches,
        "prospectiveControlExact": True,
        "sealedHoldoutOpened": False,
        "productionShaderAuthorized": False,
        "preregistrationSha256": sha256_path(PREREGISTRATION_PATH),
        "nextGate": preregistration["nextGate"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = validate(arguments.root)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(rendered, end="")
    else:
        arguments.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
