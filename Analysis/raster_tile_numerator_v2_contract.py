#!/usr/bin/env python3
"""Frozen schema-2 contract for historical paired tile-numerator evidence."""

import argparse
import hashlib
import json
import math
import struct
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 2
RIG_VERSION = "metal-raster-tile-numerator-2.0.0"
ROLE = "paired-edge-discovery-with-prospective-power-two-controls"
TARGET_WIDTH = 1_024
TARGET_HEIGHT = 1_024
VIEWPORT_WIDTH = 1_024
VIEWPORT_HEIGHT = 1_024
TILE_SIZE = 32
TILE_COUNT = TARGET_WIDTH // TILE_SIZE
AXIS_COUNT = 2
PRIMITIVE_COUNT = 2
EDGE_COUNT = 2
SLOT_COUNT = AXIS_COUNT * PRIMITIVE_COUNT * TILE_COUNT * EDGE_COUNT
RECORD = struct.Struct("<4I")
SENTINEL = (0xFFFF_FFFF,) * 4
PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_tile_numerator_v2_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "150dd157b90ff6798ac087e47d39f78cc4e68dbd016b3aff3a096d1db31dbae1"
)


@dataclass(frozen=True, slots=True)
class CaptureCase:
    name: str
    role: str
    width: int
    height: int
    originX: int
    originY: int


@dataclass(frozen=True, slots=True)
class EndpointCase:
    name: str
    lowBits: int
    highBits: int


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
        return (
            self.axis * PRIMITIVE_COUNT * TILE_COUNT
            + self.primitive * TILE_COUNT
            + self.tile
        ) * EDGE_COUNT + self.edge


CASES = (
    CaptureCase("control-square-256", "prospective-control", 256, 256, 384, 384),
    CaptureCase("opened-square-512", "opened-calibration", 512, 512, 81, 349),
    CaptureCase("opened-square-640", "opened-calibration", 640, 640, 282, 326),
    CaptureCase("opened-square-800", "opened-calibration", 800, 800, 112, 112),
    CaptureCase("opened-square-896", "opened-calibration", 896, 896, 64, 64),
    CaptureCase("opened-rectangle-503x377", "opened-calibration", 503, 377, 37, 73),
    CaptureCase("wide-896x47", "discovery", 896, 47, 64, 211),
    CaptureCase("wide-896x61", "discovery", 896, 61, 64, 227),
    CaptureCase("wide-896x79", "discovery", 896, 79, 64, 239),
    CaptureCase("wide-896x113", "discovery", 896, 113, 64, 251),
    CaptureCase("wide-896x257", "discovery", 896, 257, 64, 293),
    CaptureCase("wide-896x511", "discovery", 896, 511, 64, 129),
    CaptureCase("wide-896x640", "discovery", 896, 640, 64, 192),
    CaptureCase("prime-887x613", "discovery", 887, 613, 73, 107),
    CaptureCase("phase-769x251", "discovery", 769, 251, 127, 311),
    CaptureCase("tall-641x896", "discovery", 641, 896, 191, 64),
    CaptureCase("tall-639x896", "discovery", 639, 896, 193, 64),
    CaptureCase("tall-513x896", "discovery", 513, 896, 255, 64),
    CaptureCase("tall-511x896", "discovery", 511, 896, 257, 64),
    CaptureCase("near-800-plus", "discovery", 801, 896, 111, 64),
    CaptureCase("near-800-minus", "discovery", 799, 896, 113, 64),
    CaptureCase("near-896-plus", "discovery", 897, 895, 63, 65),
    CaptureCase("near-896-minus", "discovery", 895, 897, 65, 63),
    CaptureCase("near-fullscreen-prime", "discovery", 977, 43, 23, 401),
)

ENDPOINTS = (
    EndpointCase("zero-to-one", 0x0000_0000, 0x3F80_0000),
    EndpointCase("one-to-zero", 0x3F80_0000, 0x0000_0000),
    EndpointCase("negative-half-to-half", 0xBF00_0000, 0x3F00_0000),
    EndpointCase("half-to-negative-half", 0x3F00_0000, 0xBF00_0000),
    EndpointCase("opened-256", 0x3EC0_0000, 0x3F20_0000),
    EndpointCase("opened-512-x", 0x3E86_CCCD, 0x3F29_CCCD),
    EndpointCase("opened-512-y", 0x3EC9_AAAB, 0x3F3A_2AAB),
    EndpointCase("opened-640-x", 0x3EB3_5556, 0x3F44_5556),
    EndpointCase("opened-640-y", 0x3EC2_0000, 0x3F4B_AAAB),
    EndpointCase("opened-896-x", 0x3E55_5556, 0x3F4A_AAAB),
    EndpointCase("opened-896-y", 0x3E55_5556, 0x3F4A_AAAC),
    EndpointCase("near-equal-positive", 0x3F00_0001, 0x3F00_0009),
    EndpointCase("negative-to-positive", 0xBF40_0000, 0x3E80_0000),
    EndpointCase("positive-to-negative", 0x3E80_0000, 0xBF40_0000),
    EndpointCase("constant-quarter", 0x3E80_0000, 0x3E80_0000),
    EndpointCase("small-normal-ramp", 0x3980_0000, 0x3A80_0000),
)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def uint32_sha256(values: list[int] | tuple[int, ...]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(struct.pack("<I", value))
    return digest.hexdigest()


def float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def float32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def bits_float32(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def pull_bits(position: float, slope: float, constant: float) -> int:
    return float32_bits(float32(math.fma(position, slope, constant)))


def sample_positions(capture_case: CaptureCase) -> tuple[SamplePosition, ...]:
    result: list[SamplePosition] = []
    for axis in range(AXIS_COUNT):
        origin = capture_case.originX if axis == 0 else capture_case.originY
        extent = capture_case.width if axis == 0 else capture_case.height
        first_tile = origin // TILE_SIZE
        last_tile = (origin + extent - 1) // TILE_SIZE
        for primitive in range(PRIMITIVE_COUNT):
            for tile in range(first_tile, last_tile + 1):
                lower = max(origin, tile * TILE_SIZE)
                upper = min(origin + extent - 1, tile * TILE_SIZE + TILE_SIZE - 1)
                for edge, coordinate in enumerate((lower, upper)):
                    if edge == 1 and upper == lower:
                        continue
                    local = coordinate - origin
                    if axis == 0:
                        covered = (
                            capture_case.height * (2 * local + 1) > capture_case.width
                            if primitive == 0
                            else capture_case.height * (2 * local + 1)
                            < (2 * capture_case.height - 1) * capture_case.width
                        )
                        x = coordinate
                        y = (
                            capture_case.originY + capture_case.height - 1
                            if primitive == 0
                            else capture_case.originY
                        )
                    else:
                        covered = (
                            capture_case.width * (2 * local + 1) > capture_case.height
                            if primitive == 0
                            else capture_case.width * (2 * local + 1)
                            < (2 * capture_case.width - 1) * capture_case.height
                        )
                        x = (
                            capture_case.originX + capture_case.width - 1
                            if primitive == 0
                            else capture_case.originX
                        )
                        y = coordinate
                    if covered:
                        result.append(
                            SamplePosition(
                                axis=axis,
                                primitive=primitive,
                                tile=tile,
                                edge=edge,
                                x=x,
                                y=y,
                            )
                        )
    slots = [sample.slot for sample in result]
    if (
        not result
        or len(slots) != len(set(slots))
        or any(
            not 0 <= sample.x < TARGET_WIDTH
            or not 0 <= sample.y < TARGET_HEIGHT
            or (
                (sample.x if sample.axis == 0 else sample.y) // TILE_SIZE != sample.tile
            )
            for sample in result
        )
    ):
        raise ValueError(f"{capture_case.name} sample layout differs")
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
    positions = [sample_positions(capture_case) for capture_case in CASES]
    return {
        "caseCount": len(CASES),
        "endpointCount": len(ENDPOINTS),
        "axisCount": AXIS_COUNT,
        "primitiveCount": PRIMITIVE_COUNT,
        "edgeCount": EDGE_COUNT,
        "tileCount": TILE_COUNT,
        "slotCount": SLOT_COUNT,
        "recordBytes": RECORD.size,
        "recordCount": len(CASES) * len(ENDPOINTS) * SLOT_COUNT,
        "rawBytes": raw_bytes(),
        "expectedRecordCount": sum(len(value) for value in positions) * len(ENDPOINTS),
        "caseWordsSha256": uint32_sha256(case_words()),
        "endpointWordsSha256": uint32_sha256(endpoint_words()),
        "sampleWordsSha256": uint32_sha256(sample_words()),
        "samplesPerCase": [len(value) for value in positions],
    }


def preregistration_payload() -> JsonObject:
    return {
        "schemaVersion": 2,
        "role": ROLE,
        "observedAtPreregistration": False,
        "purpose": (
            "Identify AGX per-tile slope and centered numerator independently "
            "by observing both covered axis edges of each tile."
        ),
        "sourceEvidence": {
            "sourceTileNumeratorRunId": 30_689_521_255,
            "sourceExpectedRecords": 32_144,
            "sourceCenteredModelMatchedRecords": 32_138,
            "sourceOpenedCalibrationMatchedRecords": 6_816,
            "sourceOpenedCalibrationTotalRecords": 6_816,
            "sourceUnresolvedThinGeometryRecords": 6,
            "sourceBestImageResidualBytesAfterEvidenceCorrection": 0,
            "productionShaderChanged": False,
        },
        "capture": {
            "targetWidth": TARGET_WIDTH,
            "targetHeight": TARGET_HEIGHT,
            "viewportWidth": VIEWPORT_WIDTH,
            "viewportHeight": VIEWPORT_HEIGHT,
            "tileSize": TILE_SIZE,
            "edgeCount": EDGE_COUNT,
            "cases": [asdict(value) for value in CASES],
            "endpoints": [
                {
                    "name": value.name,
                    "lowBits": f"0x{value.lowBits:08x}",
                    "highBits": f"0x{value.highBits:08x}",
                }
                for value in ENDPOINTS
            ],
            "samplePositionLaw": (
                "For each 32-pixel tile, axis, and primitive, retain both "
                "the lower and upper in-geometry axis coordinates whenever "
                "the fixed opposite-edge pixel is covered. Diagonal-edge "
                "pixels are excluded by exact doubled-area inequalities."
            ),
            "recordComponents": [
                "axis-pull@0",
                "axis-pull@15/16",
                "center",
                "axis-derivative(center)",
            ],
            "pullOffsetsByAxis": {
                "x": [[0.0, 0.5], [0.9375, 0.5]],
                "y": [[0.5, 0.0], [0.5, 0.9375]],
            },
            "ordering": (
                "case-major,endpoint-major,axis-primitive-tile-edge-slot-major"
            ),
            "layout": layout_metadata(),
        },
        "prospectiveControl": {
            "case": "control-square-256",
            "endpoints": ["zero-to-one", "one-to-zero"],
            "prediction": (
                "exact power-of-two affine plane at both retained tile "
                "edges; pull samples are fused round-to-nearest"
            ),
            "pullComponentsMustMatchExactly": True,
            "centerAndDerivativeAreDiagnostic": True,
        },
        "acceptance": {
            "allExpectedRecordsWrittenAndFinite": True,
            "allUndeclaredSlotsRemainSentinel": True,
            "layoutHashesMustMatch": True,
            "prospectivePowerTwoPullControlsExact": True,
            "rawDiscoveryRecordsAlwaysRetained": True,
            "noAdaptiveFitOrTolerance": True,
        },
        "nonClaims": [
            "Discovery records do not certify a replacement arithmetic law.",
            "Opened calibration geometries are not a blind image holdout.",
            "A passing control does not establish arbitrary geometry parity.",
            "No result authorizes changing the production shader before a fresh holdout.",
        ],
    }


def load_preregistration() -> JsonObject:
    preregistration: JsonObject = json.loads(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    if (
        sha256_path(PREREGISTRATION_PATH) != PREREGISTRATION_SHA256
        or preregistration != preregistration_payload()
    ):
        raise ValueError("tile-numerator preregistration differs")
    return preregistration


def finite(bits: int) -> bool:
    return bits & 0x7F80_0000 != 0x7F80_0000


def control_pull_prediction(
    capture_case: CaptureCase,
    endpoint: EndpointCase,
    sample: SamplePosition,
) -> tuple[int, int]:
    low = bits_float32(endpoint.lowBits)
    high = bits_float32(endpoint.highBits)
    extent = capture_case.width if sample.axis == 0 else capture_case.height
    origin = capture_case.originX if sample.axis == 0 else capture_case.originY
    coordinate = sample.x if sample.axis == 0 else sample.y
    slope = float32((high - low) / extent)
    tile_origin = sample.tile * TILE_SIZE
    constant = float32(low + (tile_origin - origin) * slope)
    position = float(coordinate % TILE_SIZE)
    return (
        pull_bits(position, slope, constant),
        pull_bits(position + 0.9375, slope, constant),
    )


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
        != "Analysis/raster_tile_numerator_preregistration.json"
        or evidence.get("preregistrationSha256") != PREREGISTRATION_SHA256
        or evidence.get("layout") != layout_metadata()
        or evidence.get("cases") != [asdict(value) for value in CASES]
        or evidence.get("endpoints")
        != [
            {
                "name": value.name,
                "lowBits": f"0x{value.lowBits:08x}",
                "highBits": f"0x{value.highBits:08x}",
            }
            for value in ENDPOINTS
        ]
        or evidence.get("recordComponents")
        != preregistration["capture"]["recordComponents"]
        or evidence.get("pullOffsetsByAxis")
        != preregistration["capture"]["pullOffsetsByAxis"]
        or evidence.get("ordering") != preregistration["capture"]["ordering"]
        or evidence.get("bytes") != raw_bytes()
        or not raw_path.is_file()
        or raw_path.stat().st_size != raw_bytes()
        or evidence.get("sha256") != sha256_path(raw_path)
    ):
        raise ValueError("tile-numerator manifest differs")

    raw = raw_path.read_bytes()
    expected_records = 0
    finite_words = 0
    control_records = 0
    control_pull_mismatches = 0
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
                            f"undeclared tile-numerator record {record_index} was written"
                        )
                    continue
                expected_records += 1
                if record == SENTINEL or not all(finite(bits) for bits in record):
                    raise ValueError(
                        f"tile-numerator record {record_index} is absent or nonfinite"
                    )
                finite_words += len(record)
                if capture_case.name == "control-square-256" and endpoint.name in {
                    "zero-to-one",
                    "one-to-zero",
                }:
                    control_records += 1
                    control_pull_mismatches += record[:2] != control_pull_prediction(
                        capture_case, endpoint, sample
                    )

    if (
        expected_records != layout_metadata()["expectedRecordCount"]
        or control_records == 0
        or control_pull_mismatches != 0
    ):
        raise ValueError("tile-numerator prospective control differs")
    return {
        "rasterTileNumeratorValidationSchemaVersion": 2,
        "manifestSha256": sha256_path(root / "manifest.json"),
        "rawSha256": sha256_path(raw_path),
        "expectedRecords": expected_records,
        "finiteWords": finite_words,
        "prospectiveControlRecords": control_records,
        "prospectiveControlPullMismatches": control_pull_mismatches,
        "prospectiveControlExact": True,
        "discoveryRecords": expected_records - control_records,
        "discoveryOutcomeInterpreted": False,
        "productionShaderAuthorized": False,
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
