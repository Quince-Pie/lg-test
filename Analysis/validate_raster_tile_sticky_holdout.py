#!/usr/bin/env python3
"""Validate the schema-14 prospective sticky-carry coefficient holdout."""

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

import validate_raster_tile_numerator as base


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 14
RIG_VERSION = "metal-raster-tile-selector-14.0.0"
ROLE = "prospective-sticky-carry-raster-coefficient-holdout"
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
    "raster_tile_sticky_holdout_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "9e083792501da88dae838ee3d1d69b163b7adfe38e96cf78477afd34754af4a1"
)
ORDERING = (
    "case-major,endpoint-major,axis-primitive-tile-edge-slot-major,"
    "component-minor"
)


CASES = (
    CaptureCase("sealed-sticky-a", "sealed-holdout", 680, 871, 69, 129),
    CaptureCase("sealed-sticky-b", "sealed-holdout", 703, 676, 308, 293),
    CaptureCase("sealed-sticky-c", "sealed-holdout", 811, 718, 113, 279),
    CaptureCase("sealed-sticky-d", "sealed-holdout", 714, 952, 301, 1),
    CaptureCase("sealed-sticky-e", "sealed-holdout", 755, 918, 76, 41),
    CaptureCase("sealed-sticky-f", "sealed-holdout", 431, 495, 143, 289),
    CaptureCase("sealed-sticky-g", "sealed-holdout", 728, 185, 193, 615),
    CaptureCase("sealed-sticky-h", "sealed-holdout", 934, 889, 34, 57),
    CaptureCase("sealed-sticky-i", "sealed-holdout", 814, 857, 64, 137),
    CaptureCase("sealed-sticky-j", "sealed-holdout", 571, 883, 339, 41),
    CaptureCase("sealed-sticky-k", "sealed-holdout", 944, 580, 45, 288),
    CaptureCase("sealed-sticky-l", "sealed-holdout", 947, 747, 8, 129),
)


ENDPOINT_SPECS = (
    ("tiny-near-one-b", "sticky-carry-target", 0x3780_0005, 0x3F70_000D),
    ("small-wide", "sticky-carry-target", 0x3901_2345, 0x3F12_3457),
    ("sixteenth-seven-eighths", "sticky-carry-target", 0x3D80_0011, 0x3F60_001D),
    ("eighth-half", "sticky-carry-target", 0x3E00_0013, 0x3F00_0025),
    ("three-sixteenths-eleven", "sticky-carry-target", 0x3E40_0017, 0x3F30_002B),
    ("quarter-half-cross", "sticky-carry-target", 0x3E7F_FFDD, 0x3F00_0031),
    ("half-three-quarter-cross", "sticky-carry-target", 0x3EFF_FFCD, 0x3F40_003B),
    ("zero-five-eighths", "sign-domain", 0x0000_0000, 0x3F20_002D),
    ("negative-quarter-positive", "sign-domain", 0xBE80_0019, 0x3F10_0033),
    ("exact-eighth-seven-eighths", "arithmetic-control", 0x3E00_0000, 0x3F60_0000),
    ("same-binade-wide", "sticky-carry-target", 0x3F00_0015, 0x3F70_002F),
    ("close-positive", "center-control", 0x3F20_0011, 0x3F20_00B7),
    ("negative-small-positive", "sign-domain", 0xBD00_001B, 0x3E80_0037),
    ("one-two-cross", "binade-control", 0x3F7F_FFC1, 0x4000_0029),
    ("tiny-half-b", "sticky-carry-target", 0x3800_000F, 0x3F00_0043),
    ("quarter-three-quarter-b", "sticky-carry-target", 0x3E80_0029, 0x3F40_004D),
    ("slope-bias-wide", "slope-bias-target", 0x3E1D_681A, 0x3FAD_CF98),
    ("slope-bias-small", "slope-bias-target", 0x3B78_8C19, 0x3CDC_11BD),
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
        raise ValueError("sticky-carry coefficient preregistration differs")
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
        != "Analysis/raster_tile_sticky_holdout_preregistration.json"
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
        raise ValueError("sticky-carry coefficient manifest differs")

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
                            f"undeclared sticky record {record_index} was written"
                        )
                    continue
                expected_records += 1
                records_by_endpoint_role[endpoint.role] += 1
                if record == SENTINEL or not all(base.finite(bits) for bits in record):
                    raise ValueError(
                        f"sticky record {record_index} is absent or nonfinite"
                    )
                finite_words += len(record)

    if expected_records != layout_metadata()["expectedRecordCount"]:
        raise ValueError("sticky-carry coefficient record count differs")
    return {
        "rasterTileStickyHoldoutValidationSchemaVersion": 1,
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
