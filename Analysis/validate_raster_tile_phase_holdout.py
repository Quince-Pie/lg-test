#!/usr/bin/env python3
"""Validate the schema-4 dense tile-selector phase holdout."""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import validate_raster_tile_numerator as base


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 4
RIG_VERSION = "metal-raster-tile-selector-4.0.0"
ROLE = "prospective-dense-tile-selector-phase-holdout"
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
ENDPOINTS = base.ENDPOINTS
CaptureCase = base.CaptureCase
EndpointCase = base.EndpointCase
SamplePosition = base.SamplePosition
PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_tile_phase_holdout_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "099ef9c83f6667bb6c89d9fabe560186017b4ed57b10cb1824d7c7c7d7fc07e1"
)

CASES = (
    CaptureCase("control-square-256", "prospective-control", 256, 256, 384, 384),
    CaptureCase("opened-rectangle-503x377", "opened-calibration", 503, 377, 37, 73),
    CaptureCase("opened-wide-896x61", "opened-calibration", 896, 61, 64, 227),
    CaptureCase("opened-wide-896x511", "opened-calibration", 896, 511, 64, 129),
    CaptureCase("opened-phase-769x251", "opened-calibration", 769, 251, 127, 311),
    CaptureCase("opened-tall-511x896", "opened-calibration", 511, 896, 257, 64),
    CaptureCase("opened-prime-677x419", "opened-calibration", 677, 419, 53, 149),
    CaptureCase("opened-prime-823x557", "opened-calibration", 823, 557, 101, 211),
    CaptureCase("opened-tall-509x907", "opened-calibration", 509, 907, 309, 49),
    CaptureCase("opened-wide-911x509", "opened-calibration", 911, 509, 41, 271),
    CaptureCase("sealed-phase-01-31", "sealed-holdout", 514, 809, 255, 107),
    CaptureCase("sealed-phase-02-30", "sealed-holdout", 527, 561, 248, 231),
    CaptureCase("sealed-phase-03-29", "sealed-holdout", 341, 299, 341, 362),
    CaptureCase("sealed-phase-05-29", "sealed-holdout", 275, 423, 374, 300),
    CaptureCase("sealed-phase-07-28", "sealed-holdout", 425, 553, 299, 235),
    CaptureCase("sealed-phase-09-27", "sealed-holdout", 506, 859, 259, 82),
    CaptureCase("sealed-phase-11-26", "sealed-holdout", 563, 458, 230, 283),
    CaptureCase("sealed-boundary-3over8-low", "sealed-holdout", 547, 277, 238, 373),
    CaptureCase("sealed-boundary-3over8-high", "sealed-holdout", 468, 378, 278, 323),
    CaptureCase("sealed-phase-13-23", "sealed-holdout", 432, 287, 296, 368),
    CaptureCase("sealed-phase-14-22", "sealed-holdout", 825, 391, 99, 316),
    CaptureCase("sealed-phase-15-21", "sealed-holdout", 465, 360, 279, 332),
    CaptureCase("sealed-boundary-half-low", "sealed-holdout", 433, 451, 295, 286),
    CaptureCase("sealed-boundary-half-high", "sealed-holdout", 481, 519, 271, 252),
    CaptureCase("sealed-boundary-9over16-low", "sealed-holdout", 272, 521, 376, 251),
    CaptureCase("sealed-boundary-9over16-high", "sealed-holdout", 487, 935, 268, 44),
)


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


def load_preregistration() -> JsonObject:
    preregistration: JsonObject = json.loads(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    capture_metadata = preregistration.get("capture", {})
    if (
        sha256_path(PREREGISTRATION_PATH) != PREREGISTRATION_SHA256
        or preregistration.get("schemaVersion") != 1
        or preregistration.get("role") != "sealed-holdout-prediction"
        or preregistration.get("holdoutOpenedAtPreregistration") is not False
        or capture_metadata.get("schemaVersion") != SCHEMA_VERSION
        or capture_metadata.get("rigVersion") != RIG_VERSION
        or capture_metadata.get("role") != ROLE
        or capture_metadata.get("cases") != [asdict(value) for value in CASES]
        or capture_metadata.get("endpointCount") != len(ENDPOINTS)
        or capture_metadata.get("endpointWordsSha256")
        != uint32_sha256(endpoint_words())
        or capture_metadata.get("layout") != layout_metadata()
        or capture_metadata.get("recordComponents") != record_components()
        or capture_metadata.get("pullOffsetsByAxis") != pull_offsets()
    ):
        raise ValueError("tile-phase preregistration differs")
    return preregistration


def control_pull_prediction(
    capture_case: CaptureCase,
    endpoint: EndpointCase,
    sample: SamplePosition,
) -> tuple[int, ...]:
    return base.control_pull_prediction(capture_case, endpoint, sample)


def finite(bits: int) -> bool:
    return base.finite(bits)


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
        != "Analysis/raster_tile_phase_holdout_preregistration.json"
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
        raise ValueError("tile-phase manifest differs")

    raw = raw_path.read_bytes()
    expected_records = 0
    finite_words = 0
    control_records = 0
    control_pull_mismatches = 0
    records_by_role: dict[str, int] = {}
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
                            f"undeclared tile-phase record {record_index} was written"
                        )
                    continue
                expected_records += 1
                records_by_role[capture_case.role] = (
                    records_by_role.get(capture_case.role, 0) + 1
                )
                if record == SENTINEL or not all(finite(bits) for bits in record):
                    raise ValueError(
                        f"tile-phase record {record_index} is absent or nonfinite"
                    )
                finite_words += len(record)
                if capture_case.name == "control-square-256" and endpoint.name in {
                    "zero-to-one",
                    "one-to-zero",
                }:
                    control_records += 1
                    control_pull_mismatches += record[:PULL_COUNT] != (
                        control_pull_prediction(capture_case, endpoint, sample)
                    )

    if (
        expected_records != layout_metadata()["expectedRecordCount"]
        or control_records == 0
        or control_pull_mismatches != 0
    ):
        raise ValueError("tile-phase prospective control differs")
    return {
        "rasterTilePhaseValidationSchemaVersion": 1,
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
        "predictionSha256": preregistration["predictedTruthStream"]["sha256"],
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
