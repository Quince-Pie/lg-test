#!/usr/bin/env python3
"""Validate the schema-12 dense varied-extent center tomography capture."""

import argparse
import hashlib
import json
import struct
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v8 as v8
import validate_raster_tile_numerator as base


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 12
RIG_VERSION = "metal-raster-tile-selector-12.0.0"
ROLE = "preregistered-dense-center-extent-tomography"
TARGET_WIDTH = base.TARGET_WIDTH
TARGET_HEIGHT = base.TARGET_HEIGHT
VIEWPORT_WIDTH = base.VIEWPORT_WIDTH
VIEWPORT_HEIGHT = base.VIEWPORT_HEIGHT
TILE_SIZE = base.TILE_SIZE
TILE_COUNT = base.TILE_COUNT
AXIS_COUNT = base.AXIS_COUNT
PRIMITIVE_COUNT = base.PRIMITIVE_COUNT
MAX_EFFECTIVE_EXTENT = 315
EDGE_COUNT = MAX_EFFECTIVE_EXTENT
SLOT_COUNT = PRIMITIVE_COUNT * EDGE_COUNT
PULL_NUMERATORS = base.PULL_NUMERATORS
PULL_COUNT = base.PULL_COUNT
RECORD_COMPONENT_COUNT = PULL_COUNT + 2
RECORD = struct.Struct(f"<{RECORD_COMPONENT_COUNT}I")
SENTINEL = base.SENTINEL
CaptureCase = base.CaptureCase
EndpointCase = base.EndpointCase
PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_tile_center_extent_tomography_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "b4bf93d43b17d3d1488ca740d30a8c413354537411f541c480fa0026ce2a068b"
)
ORDERING = (
    "case-major,endpoint-major,effective-axis-primitive-coordinate-slot-major,"
    "component-minor"
)


@dataclass(frozen=True, slots=True)
class CaseSpec:
    extent: int
    opposite: int
    origin: int
    opposite_origin: int
    stem: str


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
        return self.primitive * EDGE_COUNT + self.edge


CASE_SPECS = (
    CaseSpec(191, 509, 65, 341, "e191-o65-d509"),
    CaseSpec(193, 647, 78, 290, "e193-o78-d647"),
    CaseSpec(197, 751, 95, 212, "e197-o95-d751"),
    CaseSpec(198, 509, 112, 341, "e198-o112-d509"),
    CaseSpec(198, 751, 145, 212, "e198-o145-d751"),
    CaseSpec(199, 647, 127, 290, "e199-o127-d647"),
    CaseSpec(203, 751, 144, 212, "e203-o144-d751"),
    CaseSpec(204, 509, 161, 341, "e204-o161-d509"),
    CaseSpec(211, 647, 176, 290, "e211-o176-d647"),
    CaseSpec(220, 751, 191, 212, "e220-o191-d751"),
    CaseSpec(231, 509, 208, 341, "e231-o208-d509"),
    CaseSpec(251, 647, 225, 290, "e251-o225-d647"),
    CaseSpec(252, 751, 240, 212, "e252-o240-d751"),
    CaseSpec(252, 509, 271, 341, "e252-o271-d509"),
    CaseSpec(253, 509, 257, 341, "e253-o257-d509"),
    CaseSpec(255, 647, 272, 290, "e255-o272-d647"),
    CaseSpec(256, 751, 287, 212, "e256-o287-d751"),
    CaseSpec(256, 647, 320, 290, "e256-o320-d647"),
    CaseSpec(257, 509, 304, 341, "e257-o304-d509"),
    CaseSpec(315, 647, 321, 290, "e315-o321-d647"),
)
EFFECTIVE_EXTENTS = tuple(sorted({value.extent for value in CASE_SPECS}))


def transposed_pair(specification: CaseSpec) -> tuple[CaptureCase, CaptureCase]:
    return (
        CaptureCase(
            f"extent-{specification.stem}-x",
            "preregistered-discovery",
            specification.extent,
            specification.opposite,
            specification.origin,
            specification.opposite_origin,
        ),
        CaptureCase(
            f"extent-{specification.stem}-y",
            "preregistered-discovery",
            specification.opposite,
            specification.extent,
            specification.opposite_origin,
            specification.origin,
        ),
    )


CASES = tuple(
    capture_case
    for specification in CASE_SPECS
    for capture_case in transposed_pair(specification)
)

TRANSLATED_BASES = (
    ("quarter", 0x3E80_0000),
    ("one", 0x3F80_0000),
)
FAMILY_RESIDUES = {
    "n01": (1, 79),
    "n03": (3, 17),
    "n05": (5, 29),
    "n07": (7, 37),
    "n15": (15, 43),
    "n31": (31, 53),
}
N15_DEPTHS = (17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7)
N01_DEPTHS = (17, 13, 9, 7)
TRANSFER_DEPTHS = (13, 9)


def endpoint_pair(
    base_name: str,
    base_bits: int,
    family_name: str,
    depth: int,
) -> tuple[EndpointCase, EndpointCase]:
    native_significand, residue = FAMILY_RESIDUES[family_name]
    power = 23 - (native_significand.bit_length() - 1) - depth
    low = base_bits + residue
    high = low + (native_significand << power)
    stem = f"extent-{base_name}-{family_name}-d{depth:02d}"
    return (
        EndpointCase(f"{stem}-forward", "tomography-discovery", low, high),
        EndpointCase(f"{stem}-reverse", "tomography-discovery", high, low),
    )


def tomography_endpoints() -> tuple[EndpointCase, ...]:
    result = [
        EndpointCase("zero-to-one", "prospective-control", 0, 0x3F80_0000),
        EndpointCase("one-to-zero", "prospective-control", 0x3F80_0000, 0),
    ]
    for base_name, base_bits in TRANSLATED_BASES:
        for depth in N15_DEPTHS:
            result.extend(endpoint_pair(base_name, base_bits, "n15", depth))
        for depth in N01_DEPTHS:
            result.extend(endpoint_pair(base_name, base_bits, "n01", depth))
    quarter_name, quarter_bits = TRANSLATED_BASES[0]
    for family_name in ("n03", "n05", "n07", "n31"):
        for depth in TRANSFER_DEPTHS:
            result.extend(
                endpoint_pair(
                    quarter_name,
                    quarter_bits,
                    family_name,
                    depth,
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


def effective_geometry(capture_case: CaptureCase) -> tuple[int, int, int, int]:
    if capture_case.width in EFFECTIVE_EXTENTS:
        return (
            0,
            capture_case.width,
            capture_case.originX,
            capture_case.originY,
        )
    if capture_case.height in EFFECTIVE_EXTENTS:
        return (
            1,
            capture_case.height,
            capture_case.originY,
            capture_case.originX,
        )
    raise ValueError(f"{capture_case.name} has no declared effective extent")


def sample_positions(capture_case: CaptureCase) -> tuple[SamplePosition, ...]:
    axis, extent, origin, opposite_origin = effective_geometry(capture_case)
    opposite_extent = capture_case.height if axis == 0 else capture_case.width
    result: list[SamplePosition] = []
    for primitive in range(PRIMITIVE_COUNT):
        for local in range(extent):
            coordinate = origin + local
            covered = (
                opposite_extent * (2 * local + 1) > extent
                if primitive == 0
                else opposite_extent * (2 * local + 1)
                < (2 * opposite_extent - 1) * extent
            )
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
                    x=(
                        coordinate
                        if axis == 0
                        else opposite_origin
                        + (opposite_extent - 1 if primitive == 0 else 0)
                    ),
                    y=(
                        opposite_origin
                        + (opposite_extent - 1 if primitive == 0 else 0)
                        if axis == 0
                        else coordinate
                    ),
                )
            )
    slots = {sample.slot for sample in result}
    if len(result) != 2 * extent or len(slots) != len(result):
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
        "effectiveExtents": list(EFFECTIVE_EXTENTS),
        "caseSpecifications": [asdict(value) for value in CASE_SPECS],
        "translatedBases": [
            {"name": name, "bits": f"0x{bits:08x}"}
            for name, bits in TRANSLATED_BASES
        ],
        "familyResidues": {
            name: {"nativeSignificand": values[0], "baseResidue": values[1]}
            for name, values in FAMILY_RESIDUES.items()
        },
        "n15Depths": list(N15_DEPTHS),
        "n01Depths": list(N01_DEPTHS),
        "transferDepths": list(TRANSFER_DEPTHS),
        "caseWordsSha256": uint32_sha256(case_words()),
        "endpointWordsSha256": uint32_sha256(endpoint_words()),
        "sampleWordsSha256": uint32_sha256(sample_words()),
        "cases": [asdict(value) for value in CASES],
        "samplePolicy": (
            "every integer pixel on each declared effective axis, both triangle "
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
        != "preregistered-center-varied-extent-tomography"
        or preregistration.get("appleOutputsObservedAtPreregistration") is not False
        or preregistration.get("capture") != capture_metadata()
    ):
        raise ValueError("center extent tomography preregistration differs")
    return preregistration


def control_pull_prediction(
    capture_case: CaptureCase,
    endpoint: EndpointCase,
    sample: SamplePosition,
    selector_table: tuple[int, ...],
) -> tuple[int, ...]:
    slope = v8.determinant_slope(
        capture_case,
        endpoint,
        axis=sample.axis,
        selector_table=selector_table,
    )
    constant = v1.bits_float32(
        v8.physical_constant_bits(
            capture_case,
            endpoint,
            sample,
            selector_table=selector_table,
        )
    )
    return v2.predict_record_with_setup(
        sample,
        slope=slope,
        constant=constant,
    )[:PULL_COUNT]


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
        != "Analysis/raster_tile_center_extent_tomography_preregistration.json"
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
        raise ValueError("center extent tomography manifest differs")

    raw = raw_path.read_bytes()
    selector_table = v1.load_selector_table()
    expected_records = 0
    finite_words = 0
    control_records = 0
    control_pull_mismatches = 0
    records_by_extent: Counter[int] = Counter()
    for case_index, capture_case in enumerate(CASES):
        samples = sample_positions(capture_case)
        expected_by_slot = {sample.slot: sample for sample in samples}
        _, extent, _, _ = effective_geometry(capture_case)
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
                            f"undeclared extent record {record_index} was written"
                        )
                    continue
                expected_records += 1
                records_by_extent[extent] += 1
                if record == SENTINEL or not all(base.finite(bits) for bits in record):
                    raise ValueError(
                        f"extent record {record_index} is absent or nonfinite"
                    )
                finite_words += len(record)
                if endpoint.role == "prospective-control":
                    control_records += 1
                    control_pull_mismatches += record[:PULL_COUNT] != (
                        control_pull_prediction(
                            capture_case,
                            endpoint,
                            sample,
                            selector_table,
                        )
                    )

    if (
        expected_records != layout_metadata()["expectedRecordCount"]
        or control_records == 0
        or control_pull_mismatches != 0
    ):
        raise ValueError("center extent tomography prospective control differs")
    return {
        "rasterTileCenterExtentTomographyValidationSchemaVersion": 1,
        "manifestSha256": sha256_path(root / "manifest.json"),
        "rawSha256": sha256_path(raw_path),
        "expectedRecords": expected_records,
        "finiteWords": finite_words,
        "recordsByEffectiveExtent": dict(sorted(records_by_extent.items())),
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
