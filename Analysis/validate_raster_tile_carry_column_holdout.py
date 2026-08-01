#!/usr/bin/env python3
"""Validate the schema-15 prospective carry-column coefficient holdout."""

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

import validate_raster_tile_numerator as base


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 15
RIG_VERSION = "metal-raster-tile-selector-15.0.0"
ROLE = "prospective-carry-column-raster-coefficient-holdout"
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
    "raster_tile_carry_column_holdout_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "2d86735e0d6e6bdd4ba88cf766ef8489f1bb6496ad6e27a1e74e37c427d5cc5e"
)
ORDERING = (
    "case-major,endpoint-major,axis-primitive-tile-edge-slot-major,"
    "component-minor"
)


CASES = (
    CaptureCase("sealed-column-a", "sealed-holdout", 659, 907, 157, 53),
    CaptureCase("sealed-column-b", "sealed-holdout", 877, 613, 37, 211),
    CaptureCase("sealed-column-c", "sealed-holdout", 523, 941, 311, 29),
    CaptureCase("sealed-column-d", "sealed-holdout", 967, 449, 17, 503),
    CaptureCase("sealed-column-e", "sealed-holdout", 389, 827, 577, 109),
    CaptureCase("sealed-column-f", "sealed-holdout", 853, 197, 91, 701),
    CaptureCase("sealed-column-g", "sealed-holdout", 617, 769, 227, 143),
    CaptureCase("sealed-column-h", "sealed-holdout", 743, 557, 181, 347),
    CaptureCase("sealed-column-i", "sealed-holdout", 919, 883, 33, 79),
    CaptureCase("sealed-column-j", "sealed-holdout", 467, 983, 421, 5),
    CaptureCase("sealed-column-k", "sealed-holdout", 991, 307, 7, 601),
    CaptureCase("sealed-column-l", "sealed-holdout", 601, 647, 369, 257),
)


ENDPOINT_SPECS = (
    ("tiny-near-one-c", "carry-column-target", 0x3780_001B, 0x3F70_0063),
    ("small-wide-c", "carry-column-target", 0x3981_3579, 0x3F0A_BCDF),
    ("sixteenth-wide-c", "carry-column-target", 0x3D80_0035, 0x3F60_0071),
    ("eighth-half-c", "carry-column-target", 0x3E00_0039, 0x3F00_006B),
    ("three-sixteenths-c", "carry-column-target", 0x3E40_0041, 0x3F30_007D),
    ("quarter-cross-c", "carry-column-target", 0x3E7F_FF91, 0x3F00_0083),
    ("half-cross-c", "carry-column-target", 0x3EFF_FF87, 0x3F40_0089),
    ("same-binade-c", "carry-column-target", 0x3F00_0047, 0x3F70_0095),
    ("tiny-half-c", "carry-column-target", 0x3800_004D, 0x3F00_00A1),
    ("quarter-three-quarter-c", "carry-column-target", 0x3E80_0053, 0x3F40_00AD),
    ("thirdish-wide-c", "carry-column-target", 0x3EAA_AB01, 0x3F55_5637),
    ("near-half-wide-c", "carry-column-target", 0x3EFA_135B, 0x3F66_79C3),
    ("zero-wide-c", "sign-domain", 0x0000_0000, 0x3F20_0097),
    ("negative-positive-c", "sign-domain", 0xBE80_0059, 0x3F10_00B3),
    ("negative-small-c", "sign-domain", 0xBD00_0061, 0x3E80_00BF),
    ("exact-control-c", "arithmetic-control", 0x3E00_0000, 0x3F60_0000),
    ("close-positive-c", "center-control", 0x3F20_0067, 0x3F20_01D1),
    ("one-two-cross-c", "binade-control", 0x3F7F_FF73, 0x4000_00CB),
)


def endpoints() -> tuple[EndpointCase, ...]:
    return tuple(
        endpoint
        for name, role, low_bits, high_bits in ENDPOINT_SPECS
        for endpoint in (
            EndpointCase(f"{name}-forward", role, low_bits, high_bits),
            EndpointCase(f"{name}-reverse", role, high_bits, low_bits),
        )
    )


ENDPOINTS = endpoints()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def uint32_sha256(values: list[int] | tuple[int, ...]) -> str:
    return base.uint32_sha256(values)


def sample_positions(capture_case: CaptureCase) -> tuple[SamplePosition, ...]:
    return base.sample_positions(capture_case)


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
        "expectedRecordCount": sum(map(len, positions)) * len(ENDPOINTS),
        "caseWordsSha256": uint32_sha256(case_words()),
        "endpointWordsSha256": uint32_sha256(endpoint_words()),
        "sampleWordsSha256": uint32_sha256(sample_words()),
        "samplesPerCase": list(map(len, positions)),
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
        "cases": [asdict(value) for value in CASES],
        "endpoints": endpoint_metadata(),
        "recordComponents": record_components(),
        "pullOffsetsByAxis": pull_offsets(),
        "ordering": ORDERING,
        "layout": layout_metadata(),
    }


def load_preregistration() -> JsonObject:
    preregistration: JsonObject = json.loads(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    if (
        sha256_path(PREREGISTRATION_PATH) != PREREGISTRATION_SHA256
        or preregistration.get("schemaVersion") != 1
        or preregistration.get("role") != ROLE
        or preregistration.get("appleOutputsObservedAtPreregistration") is not False
        or preregistration.get("capture") != capture_metadata()
    ):
        raise ValueError("carry-column coefficient preregistration differs")
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
        != "Analysis/raster_tile_carry_column_holdout_preregistration.json"
        or evidence.get("preregistrationSha256") != PREREGISTRATION_SHA256
        or evidence.get("layout") != layout_metadata()
        or evidence.get("cases") != [asdict(value) for value in CASES]
        or evidence.get("endpoints") != endpoint_metadata()
        or evidence.get("recordComponents") != record_components()
        or evidence.get("pullOffsetsByAxis") != pull_offsets()
        or evidence.get("ordering") != ORDERING
        or evidence.get("bytes") != raw_bytes()
        or not raw_path.is_file()
        or raw_path.stat().st_size != raw_bytes()
        or evidence.get("sha256") != sha256_path(raw_path)
    ):
        raise ValueError("carry-column coefficient manifest differs")

    raw = raw_path.read_bytes()
    expected_records = 0
    finite_words = 0
    records_by_endpoint_role: Counter[str] = Counter()
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
                            f"undeclared carry-column record {record_index} was written"
                        )
                    continue
                expected_records += 1
                records_by_endpoint_role[endpoint.role] += 1
                if record == SENTINEL or not all(base.finite(bits) for bits in record):
                    raise ValueError(
                        f"carry-column record {record_index} is absent or nonfinite"
                    )
                finite_words += len(record)

    if expected_records != layout_metadata()["expectedRecordCount"]:
        raise ValueError("carry-column coefficient record count differs")
    return {
        "rasterTileCarryColumnHoldoutValidationSchemaVersion": 1,
        "manifestSha256": sha256_path(root / "manifest.json"),
        "rawSha256": sha256_path(raw_path),
        "expectedRecords": expected_records,
        "finiteWords": finite_words,
        "recordsByEndpointRole": dict(sorted(records_by_endpoint_role.items())),
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
