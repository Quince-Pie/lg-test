#!/usr/bin/env python3
"""Validate the schema-7 tile-center origin/quotient holdout structure."""

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

import validate_raster_tile_numerator as base


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 7
RIG_VERSION = "metal-raster-tile-selector-7.0.0"
ROLE = "prospective-tile-center-origin-quotient-holdout"
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
    "raster_tile_center_origin_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "41d7dff79323b880e687e182d85d6d548f83847c903ae5fa874f8bc6c659fa96"
)


def transposed_pair(
    stem: str,
    extent: int,
    opposite: int,
    origin: int,
    opposite_origin: int,
) -> tuple[CaptureCase, CaptureCase]:
    return (
        CaptureCase(
            f"sealed-{stem}-x",
            "sealed-holdout",
            extent,
            opposite,
            origin,
            opposite_origin,
        ),
        CaptureCase(
            f"sealed-{stem}-y",
            "sealed-holdout",
            opposite,
            extent,
            opposite_origin,
            origin,
        ),
    )


CASES = (
    CaptureCase("control-square-256", "prospective-control", 256, 256, 384, 384),
    *transposed_pair("d33-e198-o15", 198, 607, 15, 208),
    *transposed_pair("d33-e198-o17", 198, 619, 17, 197),
    *transposed_pair("d33-e198-o48", 198, 631, 48, 181),
    *transposed_pair("d33-e198-o80", 198, 643, 80, 167),
    *transposed_pair("d33-e231-o15", 231, 653, 15, 190),
    *transposed_pair("d33-e231-o17", 231, 661, 17, 178),
    *transposed_pair("d33-e231-o48", 231, 673, 48, 164),
    *transposed_pair("non33-e204-o15", 204, 683, 15, 161),
    *transposed_pair("non33-e204-o16", 204, 691, 16, 153),
    *transposed_pair("non33-e204-o17", 204, 701, 17, 145),
    *transposed_pair("non33-e204-o48", 204, 709, 48, 137),
    *transposed_pair("non33-e252-o16", 252, 719, 16, 129),
    *transposed_pair("non33-e252-o48", 252, 727, 48, 121),
    *transposed_pair("non33-e255-o16", 255, 733, 16, 113),
    *transposed_pair("non33-e315-o16", 315, 691, 16, 101),
)

PRIMARY_TRANSLATED_BASE = ("b2", 0x3F00_0000)
PRIMARY_TRANSLATED_RESIDUES = (0, 1, 7, 31)
PRIMARY_NATIVE_SPANS = (4, 5, 6, 7, 8, 30)
TRANSFER_TRANSLATED_BASES = (
    ("b0", 0x3E00_0000),
    ("b1", 0x3E80_0000),
    ("b3", 0x3F80_0000),
)
TRANSFER_NATIVE_SPANS = (6, 7, 30)


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
        for span in TRANSFER_NATIVE_SPANS:
            result.extend(translated_endpoint_pair(base_name, base_bits, 0, span))
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
        "sealedCases": [
            value.name for value in CASES if value.role == "sealed-holdout"
        ],
        "originResiduesUnderTest": [15, 16, 17],
        "repeatedHalfTileOrigins": [48, 80],
        "denominator33Extents": [198, 231],
        "nonDenominator33Extents": [204, 252, 255, 315],
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
        != "prospective-center-origin-versus-quotient-holdout"
        or preregistration.get("sealedHoldoutOpenedAtPreregistration") is not False
        or preregistration.get("capture") != capture_metadata()
    ):
        raise ValueError("tile-center origin preregistration differs")
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
        != "Analysis/raster_tile_center_origin_preregistration.json"
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
        raise ValueError("tile-center origin manifest differs")

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
                            f"undeclared center-origin record {record_index} was written"
                        )
                    continue
                expected_records += 1
                records_by_role[capture_case.role] += 1
                if record == SENTINEL or not all(base.finite(bits) for bits in record):
                    raise ValueError(
                        f"center-origin record {record_index} is absent or nonfinite"
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
        raise ValueError("tile-center origin prospective control differs")
    return {
        "rasterTileCenterOriginValidationSchemaVersion": 1,
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
