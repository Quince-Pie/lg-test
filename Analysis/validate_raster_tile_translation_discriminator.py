#!/usr/bin/env python3
"""Validate the schema-5 matched-delta translation discriminator."""

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

import validate_raster_tile_numerator as base


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 5
RIG_VERSION = "metal-raster-tile-selector-5.0.0"
ROLE = "prospective-zero-based-translated-matched-delta-discriminator"
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
    "raster_tile_translation_discriminator_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "5a9a44dd433ad610e01ee48dfac8e63be9f41dfb2ba7aa84a2dd52373263d756"
)
CAPTURE_PREREGISTRATION_SHA256 = (
    "46c4eb90a2aa3bc7630cedf36ab935f5937e3262cdfa408c4b4d904b2fc5eabd"
)

CASES = (
    CaptureCase("control-square-256", "prospective-control", 256, 256, 384, 384),
    CaptureCase("opened-residual-506x859", "discovery", 506, 859, 259, 82),
    CaptureCase("opened-reverse-825x391", "discovery", 825, 391, 99, 316),
    CaptureCase("opened-lower-503x377", "discovery", 503, 377, 37, 73),
    CaptureCase("opened-middle-509x907", "discovery", 509, 907, 309, 49),
    CaptureCase("sealed-ratio253-x", "sealed-holdout", 253, 647, 17, 211),
    CaptureCase("sealed-ratio253-y", "sealed-holdout", 647, 253, 211, 17),
    CaptureCase("sealed-ratio1012-x", "sealed-holdout", 1012, 257, 6, 383),
    CaptureCase("sealed-ratio1012-y", "sealed-holdout", 257, 1012, 383, 6),
    CaptureCase("sealed-ratio55-440-x", "sealed-holdout", 440, 683, 73, 121),
    CaptureCase("sealed-ratio55-440-y", "sealed-holdout", 683, 440, 121, 73),
    CaptureCase("sealed-ratio55-880-x", "sealed-holdout", 880, 347, 79, 251),
    CaptureCase("sealed-ratio55-880-y", "sealed-holdout", 347, 880, 251, 79),
    CaptureCase("sealed-neighbor252-x", "sealed-holdout", 252, 653, 31, 199),
    CaptureCase("sealed-neighbor252-y", "sealed-holdout", 653, 252, 199, 31),
    CaptureCase("sealed-neighbor254-x", "sealed-holdout", 254, 641, 47, 223),
    CaptureCase("sealed-neighbor254-y", "sealed-holdout", 641, 254, 223, 47),
    CaptureCase("sealed-neighbor439-x", "sealed-holdout", 439, 677, 83, 139),
    CaptureCase("sealed-neighbor439-y", "sealed-holdout", 677, 439, 139, 83),
    CaptureCase("sealed-neighbor441-x", "sealed-holdout", 441, 691, 101, 117),
    CaptureCase("sealed-neighbor441-y", "sealed-holdout", 691, 441, 117, 101),
    CaptureCase("sealed-neighbor879-x", "sealed-holdout", 879, 353, 67, 271),
    CaptureCase("sealed-neighbor879-y", "sealed-holdout", 353, 879, 271, 67),
    CaptureCase("sealed-neighbor881-x", "sealed-holdout", 881, 349, 71, 263),
    CaptureCase("sealed-neighbor881-y", "sealed-holdout", 349, 881, 263, 71),
    CaptureCase("sealed-opposite506-x", "sealed-holdout", 506, 853, 259, 91),
    CaptureCase("sealed-opposite506-y", "sealed-holdout", 853, 506, 91, 259),
    CaptureCase("sealed-opposite825-x", "sealed-holdout", 825, 397, 99, 311),
    CaptureCase("sealed-opposite825-y", "sealed-holdout", 397, 825, 311, 99),
)

DELTA_UNITS = (8, 16, 30)
TRANSLATED_BASES = (
    ("b0", 0x3E80_0000, 1),
    ("b2", 0x3F00_0000, 2),
)
TRANSLATED_RESIDUES = (0, 1, 7, 31)


def discriminator_endpoints() -> tuple[EndpointCase, ...]:
    result = [
        EndpointCase("zero-to-one", "prospective-control", 0, 0x3F80_0000),
        EndpointCase("one-to-zero", "prospective-control", 0x3F80_0000, 0),
    ]
    for units in DELTA_UNITS:
        delta_bits = base.float32_bits(units * 2.0**-25)
        result.extend(
            (
                EndpointCase(
                    f"zero-u{units:02d}-forward",
                    "arithmetic-discovery",
                    0,
                    delta_bits,
                ),
                EndpointCase(
                    f"zero-u{units:02d}-reverse",
                    "arithmetic-discovery",
                    delta_bits,
                    0,
                ),
            )
        )
        for base_name, base_bits, unit_scale in TRANSLATED_BASES:
            span = units // unit_scale
            if span * unit_scale != units:
                raise ValueError("translated delta is not exactly representable")
            for residue in TRANSLATED_RESIDUES:
                low = base_bits + residue
                high = low + span
                result.extend(
                    (
                        EndpointCase(
                            f"translated-{base_name}-r{residue:02d}-u{units:02d}-forward",
                            "arithmetic-discovery",
                            low,
                            high,
                        ),
                        EndpointCase(
                            f"translated-{base_name}-r{residue:02d}-u{units:02d}-reverse",
                            "arithmetic-discovery",
                            high,
                            low,
                        ),
                    )
                )
    return tuple(result)


ENDPOINTS = discriminator_endpoints()


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
        "discoveryCases": [
            value.name for value in CASES if value.role == "discovery"
        ],
        "sealedCases": [
            value.name for value in CASES if value.role == "sealed-holdout"
        ],
        "deltaUnitsAtBinary32ExponentMinus25": list(DELTA_UNITS),
        "translatedBaseBits": [
            f"0x{base_bits:08x}"
            for _, base_bits, _ in TRANSLATED_BASES
        ],
        "translatedResidues": list(TRANSLATED_RESIDUES),
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
        != "matched-delta-discovery-with-sealed-geometry-holdout"
        or preregistration.get("sealedHoldoutOpenedAtPreregistration") is not False
        or preregistration.get("capture") != capture_metadata()
    ):
        raise ValueError("tile-translation preregistration differs")
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
        != "Analysis/raster_tile_translation_discriminator_preregistration.json"
        or evidence.get("preregistrationSha256")
        not in {CAPTURE_PREREGISTRATION_SHA256, PREREGISTRATION_SHA256}
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
        raise ValueError("tile-translation manifest differs")

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
                            f"undeclared tile-translation record {record_index} was written"
                        )
                    continue
                expected_records += 1
                records_by_role[capture_case.role] += 1
                if record == SENTINEL or not all(base.finite(bits) for bits in record):
                    raise ValueError(
                        f"tile-translation record {record_index} is absent or nonfinite"
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
        raise ValueError("tile-translation prospective control differs")
    return {
        "rasterTileTranslationValidationSchemaVersion": 1,
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
        "capturePreregistrationSha256": evidence["preregistrationSha256"],
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
