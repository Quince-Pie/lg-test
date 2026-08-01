#!/usr/bin/env python3
"""Validate the preregistered fixed-post-clip Metal arithmetic capture."""

import argparse
import hashlib
import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 1
RIG_VERSION = "metal-raster-clip-arithmetic-discriminator-1.0.0"
ROLE = "prospective-fixed-post-clip-arithmetic-discriminator"
UNITS_PER_PIXEL = 256
VIEWPORTS = (256, 512)
PLANES = ("left", "right", "top", "bottom")
CROSS_SPANS = (47, 61)
DISTANCE_FIXED_MAX = 8_192
DISTANCE_COUNT = DISTANCE_FIXED_MAX + 1
SAMPLE_COUNT = 3
RECORD_VECTOR_COUNT = 18
RECORD_WORD_COUNT = RECORD_VECTOR_COUNT * 4
RECORD_BYTES = RECORD_WORD_COUNT * 4
RECORD = struct.Struct(f"<{RECORD_WORD_COUNT}I")
DELTA_BITS = (
    0x3E_E2_B8_4A,
    0x3E_88_E3_E7,
    0x3E_89_14_5A,
    0x3E_90_73_83,
    0x3E_97_D2_AC,
    0x3E_A9_75_16,
    0x3E_B0_D4_3F,
    0x3E_B8_33_68,
    0x3E_C9_D5_D2,
    0x3E_CC_2B_94,
    0x3E_D8_94_24,
    0x3E_E5_2D_27,
    0x3E_EC_8C_50,
    0x3E_F1_74_93,
    0x3E_F7_91_A5,
    0x3E_FE_2E_BA,
)
WITNESS_COUNT = len(DELTA_BITS)
GROUP_COUNT = len(VIEWPORTS) * len(PLANES) * len(CROSS_SPANS)
CASE_COUNT = GROUP_COUNT * DISTANCE_COUNT
RECORD_COUNT = CASE_COUNT * SAMPLE_COUNT
RAW_BYTES = RECORD_COUNT * RECORD_BYTES
SOURCE_RUN_ID = 30_676_628_218
SOURCE_COMMIT = "51636e834750e1346e3fb044e6874a89afb1dc16"
SOURCE_RAW_SHA256 = "486d227a49ab90a5744cf2dff827253b9e25effcaf3b7adaf5b0176d1e0527c8"
SOURCE_ANALYSIS_SHA256 = (
    "780d17c0faa01e996129429d30a58bc9ed46fc6c8a3a2d7bedda5448468eb751"
)
PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_clip_arithmetic_discriminator_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "505d589c969e142e81bed76982fc81ab7a01b2b2b84ddf4d46ed78650c8ff718"
)


@dataclass(frozen=True, slots=True)
class ProbeGroup:
    name: str
    viewport: int
    plane: str
    cross_span: int
    first_case: int
    case_count: int
    samples: tuple[tuple[int, int], ...]

    @property
    def axis(self) -> str:
        return "x" if self.plane in {"left", "right"} else "y"

    @property
    def lower_plane(self) -> bool:
        return self.plane in {"left", "top"}

    @property
    def guard_fixed(self) -> int:
        if self.lower_plane:
            return -(self.viewport // 4) * UNITS_PER_PIXEL
        return (5 * self.viewport // 4) * UNITS_PER_PIXEL

    @property
    def post_clip_span_fixed(self) -> int:
        return (5 * self.viewport // 4) * UNITS_PER_PIXEL

    def manifest(self) -> JsonObject:
        return {
            "name": self.name,
            "viewport": self.viewport,
            "plane": self.plane,
            "axis": self.axis,
            "crossSpanPixels": self.cross_span,
            "firstCase": self.first_case,
            "caseCount": self.case_count,
            "guardFixed": self.guard_fixed,
            "postClipSpanFixed": self.post_clip_span_fixed,
            "samples": [list(sample) for sample in self.samples],
        }


@dataclass(frozen=True, slots=True)
class ProbeCase:
    name: str
    group_index: int
    viewport: int
    plane: str
    cross_span: int
    distance_fixed: int
    geometry_fixed: tuple[int, int, int, int]
    output_record_start: int


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def words_sha256(values: tuple[int, ...] | list[int], *, signed: bool) -> str:
    code = "i" if signed else "I"
    digest = hashlib.sha256()
    for value in values:
        digest.update(struct.pack(f"<{code}", value))
    return digest.hexdigest()


def sample_coordinates(viewport: int, plane: str) -> tuple[tuple[int, int], ...]:
    lower = plane in {"left", "top"}
    first = 5 * viewport // 8 if lower else viewport // 4
    along = (first, first + 15, first + 31)
    cross = viewport // 2 - 1
    if plane in {"left", "right"}:
        return tuple((coordinate, cross) for coordinate in along)
    return tuple((cross, coordinate) for coordinate in along)


def geometry_fixed(
    *,
    viewport: int,
    plane: str,
    cross_span: int,
    distance_fixed: int,
) -> tuple[int, int, int, int]:
    center = viewport * UNITS_PER_PIXEL // 2 - 128
    cross_half = cross_span * UNITS_PER_PIXEL // 2
    cross_lower = center - cross_half
    cross_upper = center + cross_half
    lower_plane = plane in {"left", "top"}
    guard = (
        -(viewport // 4) * UNITS_PER_PIXEL
        if lower_plane
        else (5 * viewport // 4) * UNITS_PER_PIXEL
    )
    outer = guard - distance_fixed if lower_plane else guard + distance_fixed
    viewport_fixed = viewport * UNITS_PER_PIXEL
    if plane == "left":
        return (outer, viewport_fixed, cross_lower, cross_upper)
    if plane == "right":
        return (0, outer, cross_lower, cross_upper)
    if plane == "top":
        return (cross_lower, cross_upper, outer, viewport_fixed)
    if plane == "bottom":
        return (cross_lower, cross_upper, 0, outer)
    raise ValueError(f"unknown plane {plane}")


def case_catalog() -> tuple[tuple[ProbeCase, ...], tuple[ProbeGroup, ...]]:
    cases: list[ProbeCase] = []
    groups: list[ProbeGroup] = []
    for viewport in VIEWPORTS:
        for plane in PLANES:
            for cross_span in CROSS_SPANS:
                first_case = len(cases)
                group = ProbeGroup(
                    name=f"v{viewport}-{plane}-h{cross_span}",
                    viewport=viewport,
                    plane=plane,
                    cross_span=cross_span,
                    first_case=first_case,
                    case_count=DISTANCE_COUNT,
                    samples=sample_coordinates(viewport, plane),
                )
                groups.append(group)
                for distance_fixed in range(DISTANCE_COUNT):
                    case_index = len(cases)
                    cases.append(
                        ProbeCase(
                            name=(f"{group.name}-d{distance_fixed:05d}"),
                            group_index=len(groups) - 1,
                            viewport=viewport,
                            plane=plane,
                            cross_span=cross_span,
                            distance_fixed=distance_fixed,
                            geometry_fixed=geometry_fixed(
                                viewport=viewport,
                                plane=plane,
                                cross_span=cross_span,
                                distance_fixed=distance_fixed,
                            ),
                            output_record_start=case_index * SAMPLE_COUNT,
                        )
                    )
    return tuple(cases), tuple(groups)


def case_catalog_bytes(cases: tuple[ProbeCase, ...]) -> bytes:
    result = bytearray()
    plane_codes = {"left": 0, "right": 1, "top": 2, "bottom": 3}
    for case in cases:
        name = case.name.encode()
        result.extend(struct.pack("<I", len(name)))
        result.extend(name)
        result.extend(
            struct.pack(
                "<5I4iI",
                case.group_index,
                case.viewport,
                plane_codes[case.plane],
                case.cross_span,
                case.distance_fixed,
                *case.geometry_fixed,
                case.output_record_start,
            )
        )
    return bytes(result)


def predicted_layout() -> JsonObject:
    cases, groups = case_catalog()
    geometry_words = [value for case in cases for value in case.geometry_fixed]
    sample_words = [
        value for group in groups for sample in group.samples for value in sample
    ]
    distance_words = list(range(DISTANCE_COUNT))
    return {
        "viewportCount": len(VIEWPORTS),
        "planeCount": len(PLANES),
        "crossSpanCount": len(CROSS_SPANS),
        "groupCount": len(groups),
        "caseCount": len(cases),
        "casesPerGroup": DISTANCE_COUNT,
        "distanceFixedMaximum": DISTANCE_FIXED_MAX,
        "distanceStepPixels": 1 / UNITS_PER_PIXEL,
        "sampleCountPerCase": SAMPLE_COUNT,
        "witnessCount": WITNESS_COUNT,
        "recordVectorCount": RECORD_VECTOR_COUNT,
        "recordWords": RECORD_WORD_COUNT,
        "recordBytes": RECORD_BYTES,
        "recordCount": RECORD_COUNT,
        "rawBytes": RAW_BYTES,
        "caseCatalogSha256": hashlib.sha256(case_catalog_bytes(cases)).hexdigest(),
        "fixedGeometrySha256": words_sha256(geometry_words, signed=True),
        "sampleCoordinatesSha256": words_sha256(sample_words, signed=False),
        "distanceFixedSha256": words_sha256(distance_words, signed=False),
        "deltaBitsSha256": words_sha256(list(DELTA_BITS), signed=False),
    }


def load_preregistration() -> JsonObject:
    if sha256_path(PREREGISTRATION_PATH) != PREREGISTRATION_SHA256:
        raise ValueError("clip arithmetic preregistration digest differs")
    document = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))
    if (
        document.get("schemaVersion") != SCHEMA_VERSION
        or document.get("role") != ROLE
        or document.get("observedAtPreregistration") is not False
        or document.get("frozenLayout") != predicted_layout()
    ):
        raise ValueError("clip arithmetic preregistration differs")
    return document


def validate_manifest(root: Path) -> tuple[JsonObject, Path]:
    preregistration = load_preregistration()
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    section = manifest.get("rasterClipArithmeticDiscriminator")
    if not isinstance(section, dict):
        raise ValueError("clip arithmetic manifest section is absent")
    if (
        manifest.get("schemaVersion") != SCHEMA_VERSION
        or manifest.get("rigVersion") != RIG_VERSION
        or section.get("role") != ROLE
        or section.get("preregistrationSha256") != PREREGISTRATION_SHA256
        or section.get("layout") != preregistration["frozenLayout"]
        or section.get("deltaBits") != list(DELTA_BITS)
    ):
        raise ValueError("clip arithmetic manifest differs")
    _cases, groups = case_catalog()
    if section.get("groups") != [group.manifest() for group in groups]:
        raise ValueError("clip arithmetic group manifest differs")
    raw_path = root / str(section.get("file", ""))
    if (
        section.get("bytes") != RAW_BYTES
        or raw_path.stat().st_size != RAW_BYTES
        or section.get("sha256") != sha256_path(raw_path)
    ):
        raise ValueError("clip arithmetic raw identity differs")
    return manifest, raw_path


def validate_records(raw_path: Path) -> JsonObject:
    cases, groups = case_catalog()
    primitive_counts: dict[int, int] = {}
    finite_word_count = 0
    with raw_path.open("rb") as stream:
        for case_index, case in enumerate(cases):
            group = groups[case.group_index]
            for sample_index, (expected_x, expected_y) in enumerate(group.samples):
                payload = stream.read(RECORD_BYTES)
                if len(payload) != RECORD_BYTES:
                    raise ValueError("clip arithmetic record stream ended early")
                record = RECORD.unpack(payload)
                if record[:2] != (expected_x, expected_y):
                    raise ValueError(f"{case.name} sample {sample_index} pixel differs")
                primitive = record[2]
                if primitive > 1 or record[3] != case_index:
                    raise ValueError(
                        f"{case.name} sample {sample_index} header differs"
                    )
                primitive_counts[primitive] = primitive_counts.get(primitive, 0) + 1
                for bits in record[4:]:
                    if not math.isfinite(
                        struct.unpack("<f", struct.pack("<I", bits))[0]
                    ):
                        raise ValueError(
                            f"{case.name} sample {sample_index} has nonfinite data"
                        )
                    finite_word_count += 1
        if stream.read(1):
            raise ValueError("clip arithmetic record stream has trailing bytes")
    return {
        "recordCount": RECORD_COUNT,
        "finiteFloatingPointWordCount": finite_word_count,
        "primitiveIdCounts": {
            str(key): value for key, value in sorted(primitive_counts.items())
        },
        "allExpectedRecordsPresent": True,
    }


def validate(root: Path) -> JsonObject:
    manifest, raw_path = validate_manifest(root)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "rigVersion": RIG_VERSION,
        "ciCommit": manifest.get("ciCommit", ""),
        "measurement": {
            "rawSha256": sha256_path(raw_path),
            "integrity": validate_records(raw_path),
        },
        "conclusions": {
            "captureIntegrityEstablished": True,
            "postClipGeometryHeldFixedByConstruction": True,
            "clipArithmeticModelSelected": False,
            "endToEndLiquidGlassParityEstablished": False,
            "productionShaderChangeAuthorized": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
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
