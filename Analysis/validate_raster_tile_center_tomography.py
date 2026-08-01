#!/usr/bin/env python3
"""Validate the schema-11 preregistered dense tile-center tomography capture."""

import argparse
import hashlib
import json
import struct
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import validate_raster_tile_numerator as base


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 11
RIG_VERSION = "metal-raster-tile-selector-11.0.0"
ROLE = "preregistered-dense-tile-center-tomography"
TARGET_WIDTH = base.TARGET_WIDTH
TARGET_HEIGHT = base.TARGET_HEIGHT
VIEWPORT_WIDTH = base.VIEWPORT_WIDTH
VIEWPORT_HEIGHT = base.VIEWPORT_HEIGHT
TILE_SIZE = base.TILE_SIZE
TILE_COUNT = base.TILE_COUNT
AXIS_COUNT = base.AXIS_COUNT
PRIMITIVE_COUNT = base.PRIMITIVE_COUNT
EFFECTIVE_EXTENT = 252
EDGE_COUNT = EFFECTIVE_EXTENT
SLOT_COUNT = PRIMITIVE_COUNT * EFFECTIVE_EXTENT
PULL_NUMERATORS = base.PULL_NUMERATORS
PULL_COUNT = base.PULL_COUNT
RECORD_COMPONENT_COUNT = PULL_COUNT + 2
RECORD = struct.Struct(f"<{RECORD_COMPONENT_COUNT}I")
SENTINEL = base.SENTINEL
CaptureCase = base.CaptureCase
EndpointCase = base.EndpointCase
PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_tile_center_tomography_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "cce4332c8aa1f04faefedf20b327aae2fb78c2aecbe232f3b458c582a757b53d"
)
ORDERING = (
    "case-major,endpoint-major,effective-axis-primitive-coordinate-slot-major,"
    "component-minor"
)


@dataclass(frozen=True, slots=True)
class SamplePosition:
    axis: int
    primitive: int
    tile: int
    edge: int
    x: int
    y: int

    @property
    def slot(self) -> int:
        return self.primitive * EFFECTIVE_EXTENT + self.edge


def transposed_pair(
    stem: str,
    opposite: int,
    origin: int,
    opposite_origin: int,
) -> tuple[CaptureCase, CaptureCase]:
    return (
        CaptureCase(
            f"tomography-{stem}-x",
            "preregistered-discovery",
            EFFECTIVE_EXTENT,
            opposite,
            origin,
            opposite_origin,
        ),
        CaptureCase(
            f"tomography-{stem}-y",
            "preregistered-discovery",
            opposite,
            EFFECTIVE_EXTENT,
            opposite_origin,
            origin,
        ),
    )


CASES = (
    *transposed_pair("e252-d509-o89", 509, 89, 341),
    *transposed_pair("e252-d509-o96", 509, 96, 341),
    *transposed_pair("e252-d647-o143", 647, 143, 290),
    *transposed_pair("e252-d647-o150", 647, 150, 290),
    *transposed_pair("e252-d751-o192", 751, 192, 212),
    *transposed_pair("e252-d751-o199", 751, 199, 212),
)

TRANSLATED_BASES = (
    ("quarter", 0x3E80_0000),
    ("one", 0x3F80_0000),
)
SLOPE_FAMILIES = (
    ("n01", 1, 79),
    ("n15", 15, 43),
)
CANCELLATION_DEPTHS = (20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6)
EXPONENT_TRANSFER_DEPTHS = frozenset((17, 13, 9, 7))


def tomography_endpoints() -> tuple[EndpointCase, ...]:
    result = [
        EndpointCase("zero-to-one", "prospective-control", 0, 0x3F80_0000),
        EndpointCase("one-to-zero", "prospective-control", 0x3F80_0000, 0),
    ]
    for base_name, base_bits in TRANSLATED_BASES:
        for family_name, native_significand, residue in SLOPE_FAMILIES:
            for depth in CANCELLATION_DEPTHS:
                if base_name != "quarter" and depth not in EXPONENT_TRANSFER_DEPTHS:
                    continue
                power = 23 - (native_significand.bit_length() - 1) - depth
                low = base_bits + residue
                high = low + (native_significand << power)
                stem = f"translated-dense-{base_name}-{family_name}-d{depth:02d}"
                result.extend(
                    (
                        EndpointCase(
                            f"{stem}-forward", "tomography-discovery", low, high
                        ),
                        EndpointCase(
                            f"{stem}-reverse", "tomography-discovery", high, low
                        ),
                    )
                )
    return tuple(result)


ENDPOINTS = tomography_endpoints()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def uint32_sha256(values: list[int] | tuple[int, ...]) -> str:
    return base.uint32_sha256(values)


def sample_positions(capture_case: CaptureCase) -> tuple[SamplePosition, ...]:
    if capture_case.width == EFFECTIVE_EXTENT:
        axis = 0
        origin = capture_case.originX
        opposite_origin = capture_case.originY
        opposite_extent = capture_case.height
    elif capture_case.height == EFFECTIVE_EXTENT:
        axis = 1
        origin = capture_case.originY
        opposite_origin = capture_case.originX
        opposite_extent = capture_case.width
    else:
        raise ValueError(f"{capture_case.name} has no {EFFECTIVE_EXTENT}-pixel axis")

    result: list[SamplePosition] = []
    for primitive in range(PRIMITIVE_COUNT):
        for local in range(EFFECTIVE_EXTENT):
            coordinate = origin + local
            if axis == 0:
                covered = (
                    opposite_extent * (2 * local + 1) > EFFECTIVE_EXTENT
                    if primitive == 0
                    else opposite_extent * (2 * local + 1)
                    < (2 * opposite_extent - 1) * EFFECTIVE_EXTENT
                )
                x = coordinate
                y = (
                    opposite_origin + opposite_extent - 1
                    if primitive == 0
                    else opposite_origin
                )
            else:
                covered = (
                    opposite_extent * (2 * local + 1) > EFFECTIVE_EXTENT
                    if primitive == 0
                    else opposite_extent * (2 * local + 1)
                    < (2 * opposite_extent - 1) * EFFECTIVE_EXTENT
                )
                x = (
                    opposite_origin + opposite_extent - 1
                    if primitive == 0
                    else opposite_origin
                )
                y = coordinate
            if not covered:
                raise ValueError(
                    f"{capture_case.name} primitive {primitive} misses local {local}"
                )
            result.append(
                SamplePosition(
                    axis=axis,
                    primitive=primitive,
                    tile=coordinate // TILE_SIZE,
                    edge=local,
                    x=x,
                    y=y,
                )
            )
    if len(result) != SLOT_COUNT or {sample.slot for sample in result} != set(
        range(SLOT_COUNT)
    ):
        raise ValueError(f"{capture_case.name} dense slot layout differs")
    return tuple(result)


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
    samples = [sample_positions(capture_case) for capture_case in CASES]
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
        "expectedRecordCount": sum(map(len, samples)) * len(ENDPOINTS),
        "caseWordsSha256": uint32_sha256(case_words()),
        "endpointWordsSha256": uint32_sha256(endpoint_words()),
        "sampleWordsSha256": uint32_sha256(sample_words()),
        "samplesPerCase": list(map(len, samples)),
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
        "translatedBases": [
            {"name": name, "bits": f"0x{bits:08x}"}
            for name, bits in TRANSLATED_BASES
        ],
        "slopeFamilies": [
            {
                "name": name,
                "nativeSignificand": significand,
                "baseResidue": residue,
            }
            for name, significand, residue in SLOPE_FAMILIES
        ],
        "cancellationDepths": list(CANCELLATION_DEPTHS),
        "exponentTransferDepths": sorted(EXPONENT_TRANSFER_DEPTHS, reverse=True),
        "samplePolicy": (
            "every integer pixel on the 252-pixel effective axis, both triangle "
            "primitives, native and transposed geometry"
        ),
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
        or preregistration.get("role")
        != "preregistered-center-dense-tomography"
        or preregistration.get("appleOutputsObservedAtPreregistration") is not False
        or preregistration.get("capture") != capture_metadata()
    ):
        raise ValueError("tile-center tomography preregistration differs")
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
        != "Analysis/raster_tile_center_tomography_preregistration.json"
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
        raise ValueError("tile-center tomography manifest differs")

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
                            f"undeclared tomography record {record_index} was written"
                        )
                    continue
                expected_records += 1
                records_by_role[capture_case.role] += 1
                if record == SENTINEL or not all(base.finite(bits) for bits in record):
                    raise ValueError(
                        f"tomography record {record_index} is absent or nonfinite"
                    )
                finite_words += len(record)
                if endpoint.name in {"zero-to-one", "one-to-zero"}:
                    control_records += 1
                    control_pull_mismatches += record[:PULL_COUNT] != (
                        base.control_pull_prediction(capture_case, endpoint, sample)
                    )

    if (
        expected_records != layout_metadata()["expectedRecordCount"]
        or control_records == 0
        or control_pull_mismatches != 0
    ):
        raise ValueError("tile-center tomography prospective control differs")
    return {
        "rasterTileCenterTomographyValidationSchemaVersion": 1,
        "manifestSha256": sha256_path(root / "manifest.json"),
        "rawSha256": sha256_path(raw_path),
        "expectedRecords": expected_records,
        "finiteWords": finite_words,
        "recordsByCaseRole": dict(sorted(records_by_role.items())),
        "prospectiveControlRecords": control_records,
        "prospectiveControlPullMismatches": control_pull_mismatches,
        "prospectiveControlExact": True,
        "discoveryRecordsOpened": True,
        "prospectiveParityClaim": False,
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
