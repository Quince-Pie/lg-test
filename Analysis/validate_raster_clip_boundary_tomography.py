#!/usr/bin/env python3
"""Validate preregistered Metal clip-boundary and topology tomography."""

import argparse
import functools
import hashlib
import json
import struct
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import validate_raster_general_height_factorization as factorization


type JsonObject = dict[str, Any]
type Record = tuple[int, ...]
type RecordSequence = Sequence[Sequence[int]]

SCHEMA_VERSION = 1
RIG_VERSION = "metal-raster-clip-boundary-tomography-1.0.0"
ROLE = "prospective-clip-boundary-and-generated-topology-tomography"
UNITS_PER_PIXEL = 256
RECORD_VECTOR_COUNT = 15
RECORD_WORD_COUNT = RECORD_VECTOR_COUNT * 4
RECORD_BYTES = RECORD_WORD_COUNT * 4
RECORD = struct.Struct(f"<{RECORD_WORD_COUNT}I")
LINE_SAMPLE_COUNT = 4
GRID_STEP = 4
PULL_OFFSET = 0.9375
BOUNDARY_CANDIDATE_NDC = 1.5
DELTA_BITS = (
    0x3E_E2_B8_4A,
    0x3E_89_14_5A,
    0x3E_97_D2_AC,
    0x3E_B0_D4_3F,
    0x3E_C9_D5_D2,
    0x3E_D8_94_24,
    0x3E_EC_8C_50,
    0x3E_FE_2E_BA,
)
WITNESS_COUNT = len(DELTA_BITS)
CANDIDATE_RADIUS_FLOAT_ULPS = 64
SOURCE_RUN_ID = 30_674_647_960
SOURCE_COMMIT = "a9dd81713ffcdaf21f3447d0efd15a44d329447d"
SOURCE_RAW_SHA256 = (
    "c89b0d39d1c022fad863007e996e701ffa3b2e1c128b2b08fe7d28511fa4f590"
)
SOURCE_ANALYSIS_SHA256 = (
    "f1a2e3c6005677d62f654eb7a3dab705462b2facbcdf28a96e9bfe67f7434296"
)
PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_clip_boundary_tomography_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "0e0d03c0ee94aa4a23a84cd104211b3a53c69e2a900c7343d364aca863fa9b48"
)


@dataclass(frozen=True, slots=True)
class ProbeCase:
    name: str
    role: str
    viewport_width: int
    viewport_height: int
    geometry_fixed: tuple[int, int, int, int]
    mode: str
    sample_origin_x: int
    sample_origin_y: int
    sample_step_x: int
    sample_step_y: int
    sample_count_x: int
    sample_count_y: int
    output_record_start: int

    @property
    def record_count(self) -> int:
        return self.sample_count_x * self.sample_count_y

    @property
    def layout_words(self) -> tuple[int, ...]:
        mode = {"horizontal": 0, "vertical": 1, "grid": 2}[self.mode]
        return (
            self.output_record_start,
            mode,
            self.sample_origin_x,
            self.sample_origin_y,
            self.sample_step_x,
            self.sample_step_y,
            self.sample_count_x,
            self.sample_count_y,
        )

    def sample(self, index: int) -> tuple[int, int]:
        if not 0 <= index < self.record_count:
            raise IndexError(index)
        return (
            self.sample_origin_x
            + (index % self.sample_count_x) * self.sample_step_x,
            self.sample_origin_y
            + (index // self.sample_count_x) * self.sample_step_y,
        )


@dataclass(frozen=True, slots=True)
class BoundaryGroup:
    name: str
    viewport: int
    plane: str
    first_case: int
    case_count: int
    safe_case: int
    candidate_edge_fixed: int


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


def int32_sha256(values: list[int] | tuple[int, ...]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(struct.pack("<i", value))
    return digest.hexdigest()


def float32_value(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def float32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def edge_positions(viewport: int, plane: str) -> tuple[int, ...]:
    lower = plane in {"left", "top"}
    coarse_start = -viewport // 2 if lower else viewport
    coarse_stop = 0 if lower else 3 * viewport // 2
    candidate = -viewport // 4 if lower else 5 * viewport // 4
    coarse = range(
        coarse_start * UNITS_PER_PIXEL,
        coarse_stop * UNITS_PER_PIXEL + 1,
        UNITS_PER_PIXEL,
    )
    fine = range(
        (candidate - 1) * UNITS_PER_PIXEL,
        (candidate + 1) * UNITS_PER_PIXEL + 1,
    )
    return tuple(sorted({*coarse, *fine}))


def fixed_rect(
    center_x_fixed: int,
    center_y_fixed: int,
    width_fixed: int,
    height_fixed: int,
) -> tuple[int, int, int, int]:
    if width_fixed % 2 or height_fixed % 2:
        raise ValueError("centered fixed rectangle requires even extents")
    return (
        center_x_fixed - width_fixed // 2,
        center_x_fixed + width_fixed // 2,
        center_y_fixed - height_fixed // 2,
        center_y_fixed + height_fixed // 2,
    )


def fixed_label(value: int) -> str:
    return f"{'n' if value < 0 else 'p'}{abs(value):08d}"


def boundary_geometry(
    *, viewport: int, plane: str, edge_fixed: int
) -> tuple[int, int, int, int]:
    span_fixed = (viewport + viewport // 4) * UNITS_PER_PIXEL
    center_x_fixed = viewport * UNITS_PER_PIXEL // 2
    center_y_fixed = (viewport * UNITS_PER_PIXEL // 2) - 128
    cross_fixed = 47 * UNITS_PER_PIXEL
    if plane == "left":
        return (
            edge_fixed,
            edge_fixed + span_fixed,
            center_y_fixed - cross_fixed // 2,
            center_y_fixed + cross_fixed // 2,
        )
    if plane == "right":
        return (
            edge_fixed - span_fixed,
            edge_fixed,
            center_y_fixed - cross_fixed // 2,
            center_y_fixed + cross_fixed // 2,
        )
    if plane == "top":
        return (
            center_x_fixed - 64 * UNITS_PER_PIXEL,
            center_x_fixed + 64 * UNITS_PER_PIXEL,
            edge_fixed,
            edge_fixed + span_fixed,
        )
    if plane == "bottom":
        return (
            center_x_fixed - 64 * UNITS_PER_PIXEL,
            center_x_fixed + 64 * UNITS_PER_PIXEL,
            edge_fixed - span_fixed,
            edge_fixed,
        )
    raise ValueError(f"unknown plane {plane}")


def boundary_samples(viewport: int, plane: str) -> tuple[int, int, int, int, int, int]:
    center_x = viewport // 2
    center_y = viewport // 2 - 1
    values = (viewport // 2 - 32, viewport // 2 - 2, viewport // 2, viewport // 2 + 30)
    if plane in {"left", "right"}:
        return values[0], center_y, 30, 0, 4, 1
    return center_x - 1, values[0], 0, 30, 1, 4


def topology_specs() -> tuple[tuple[str, int, tuple[int, int, int, int]], ...]:
    result: list[tuple[str, int, tuple[int, int, int, int]]] = []

    def add(
        name: str,
        viewport: int,
        width_fixed: int,
        height_fixed: int,
        *,
        center_x_fixed: int | None = None,
        center_y_fixed: int | None = None,
    ) -> None:
        cx = center_x_fixed or viewport * UNITS_PER_PIXEL // 2
        cy = center_y_fixed or viewport * UNITS_PER_PIXEL // 2 - 128
        result.append(
            (name, viewport, fixed_rect(cx, cy, width_fixed, height_fixed))
        )

    pixel = UNITS_PER_PIXEL
    add("topology-v256-control-160x160", 256, 160 * pixel, 160 * pixel)
    add("topology-v256-y-guard-inside-376", 256, 128 * pixel, 376 * pixel)
    add("topology-v256-y-guard-exact-384", 256, 128 * pixel, 384 * pixel)
    add("topology-v256-y-guard-outside", 256, 128 * pixel, 384 * pixel + 2)
    for width_fixed in (
        384 * pixel + 2,
        512 * pixel,
        1_024 * pixel,
        1_536 * pixel,
        2_048 * pixel - 32,
    ):
        for height in (47, 113):
            add(
                f"topology-v256-x-w{width_fixed:07d}-h{height:03d}",
                256,
                width_fixed,
                height * pixel,
            )
    for width in (128, 192):
        for height_fixed in (
            384 * pixel + 2,
            488 * pixel,
            632 * pixel,
            904 * pixel,
        ):
            add(
                f"topology-v256-y-w{width:03d}-h{height_fixed:07d}",
                256,
                width * pixel,
                height_fixed,
            )
    for width_fixed, height_fixed in (
        (512 * pixel, 488 * pixel),
        (1_024 * pixel, 488 * pixel),
        (1_024 * pixel, 632 * pixel),
        (1_536 * pixel, 632 * pixel),
        (2_048 * pixel - 32, 904 * pixel),
    ):
        add(
            f"topology-v256-xy-w{width_fixed:07d}-h{height_fixed:07d}",
            256,
            width_fixed,
            height_fixed,
        )
    for index, (cx, cy) in enumerate(
        (
            (127.5, 127.5),
            (128.0, 127.5),
            (128.5, 127.5),
            (160.0, 159.5),
            (96.0, 95.5),
        )
    ):
        add(
            f"topology-v256-xy-phase-{index}",
            256,
            1_024 * pixel,
            488 * pixel,
            center_x_fixed=round(cx * pixel),
            center_y_fixed=round(cy * pixel),
        )
    add("topology-v320-control-200x200", 320, 200 * pixel, 200 * pixel)
    add("topology-v320-xy-guard-exact", 320, 480 * pixel, 480 * pixel)
    add("topology-v320-x-1280x61", 320, 1_280 * pixel, 61 * pixel)
    add("topology-v320-y-160x610", 320, 160 * pixel, 610 * pixel)
    add("topology-v320-xy-1280x610", 320, 1_280 * pixel, 610 * pixel)
    return tuple(result)


def grid_axis(lower_fixed: int, upper_fixed: int, viewport: int) -> tuple[int, ...]:
    return tuple(
        pixel
        for pixel in range(2, viewport, GRID_STEP)
        if lower_fixed < pixel * UNITS_PER_PIXEL + 128 < upper_fixed
    )


@functools.cache
def case_catalog() -> tuple[tuple[ProbeCase, ...], tuple[BoundaryGroup, ...]]:
    cases: list[ProbeCase] = []
    groups: list[BoundaryGroup] = []
    output_start = 0
    for viewport in (256, 512):
        for plane in ("left", "right", "top", "bottom"):
            first_case = len(cases)
            edges = edge_positions(viewport, plane)
            safe_edge = (
                -viewport // 8
                if plane in {"left", "top"}
                else viewport + viewport // 8
            ) * UNITS_PER_PIXEL
            if safe_edge not in edges:
                raise ValueError("safe boundary control is absent")
            sample = boundary_samples(viewport, plane)
            for edge_fixed in edges:
                case = ProbeCase(
                    name=(
                        f"boundary-v{viewport}-{plane}-"
                        f"{fixed_label(edge_fixed)}"
                    ),
                    role="discovery-boundary",
                    viewport_width=viewport,
                    viewport_height=viewport,
                    geometry_fixed=boundary_geometry(
                        viewport=viewport,
                        plane=plane,
                        edge_fixed=edge_fixed,
                    ),
                    mode=(
                        "horizontal" if plane in {"left", "right"} else "vertical"
                    ),
                    sample_origin_x=sample[0],
                    sample_origin_y=sample[1],
                    sample_step_x=sample[2],
                    sample_step_y=sample[3],
                    sample_count_x=sample[4],
                    sample_count_y=sample[5],
                    output_record_start=output_start,
                )
                cases.append(case)
                output_start += case.record_count
            candidate = (
                -viewport // 4
                if plane in {"left", "top"}
                else 5 * viewport // 4
            ) * UNITS_PER_PIXEL
            groups.append(
                BoundaryGroup(
                    name=f"v{viewport}-{plane}",
                    viewport=viewport,
                    plane=plane,
                    first_case=first_case,
                    case_count=len(edges),
                    safe_case=first_case + edges.index(safe_edge),
                    candidate_edge_fixed=candidate,
                )
            )
    for name, viewport, geometry in topology_specs():
        xs = grid_axis(geometry[0], geometry[1], viewport)
        ys = grid_axis(geometry[2], geometry[3], viewport)
        if not xs or not ys:
            raise ValueError(f"{name} has no topology samples")
        if any(right - left != GRID_STEP for left, right in zip(xs, xs[1:])):
            raise ValueError(f"{name} X grid is not contiguous")
        if any(bottom - top != GRID_STEP for top, bottom in zip(ys, ys[1:])):
            raise ValueError(f"{name} Y grid is not contiguous")
        case = ProbeCase(
            name=name,
            role="discovery-generated-topology",
            viewport_width=viewport,
            viewport_height=viewport,
            geometry_fixed=geometry,
            mode="grid",
            sample_origin_x=xs[0],
            sample_origin_y=ys[0],
            sample_step_x=GRID_STEP,
            sample_step_y=GRID_STEP,
            sample_count_x=len(xs),
            sample_count_y=len(ys),
            output_record_start=output_start,
        )
        cases.append(case)
        output_start += case.record_count
    return tuple(cases), tuple(groups)


def predicted_layout() -> JsonObject:
    cases, groups = case_catalog()
    catalog_digest = hashlib.sha256()
    geometry_words: list[int] = []
    layout_words: list[int] = []
    role_counts = Counter(case.role for case in cases)
    viewport_counts = Counter(case.viewport_width for case in cases)
    for case in cases:
        encoded = case.name.encode()
        catalog_digest.update(struct.pack("<I", len(encoded)))
        catalog_digest.update(encoded)
        catalog_digest.update(struct.pack("<2I", case.viewport_width, case.viewport_height))
        catalog_digest.update(struct.pack("<4i", *case.geometry_fixed))
        catalog_digest.update(struct.pack("<8I", *case.layout_words))
        geometry_words.extend(case.geometry_fixed)
        layout_words.extend(case.layout_words)
    record_count = sum(case.record_count for case in cases)
    return {
        "caseCount": len(cases),
        "boundaryGroupCount": len(groups),
        "boundaryCaseCount": role_counts["discovery-boundary"],
        "topologyCaseCount": role_counts["discovery-generated-topology"],
        "viewportCaseCounts": {
            str(key): value for key, value in sorted(viewport_counts.items())
        },
        "recordVectorCount": RECORD_VECTOR_COUNT,
        "recordWords": RECORD_WORD_COUNT,
        "recordBytes": RECORD_BYTES,
        "recordCount": record_count,
        "rawBytes": record_count * RECORD_BYTES,
        "deltaBitsSha256": uint32_sha256(DELTA_BITS),
        "caseCatalogSha256": catalog_digest.hexdigest(),
        "fixedGeometrySha256": int32_sha256(geometry_words),
        "caseLayoutSha256": uint32_sha256(layout_words),
        "boundaryCandidateNDC": BOUNDARY_CANDIDATE_NDC,
        "boundaryFineStepPixels": 1 / UNITS_PER_PIXEL,
        "boundaryFineRadiusPixels": 1,
        "topologyGridStepPixels": GRID_STEP,
        "sourceClippedSetupRawSha256": SOURCE_RAW_SHA256,
    }


def load_preregistration() -> JsonObject:
    preregistration: JsonObject = json.loads(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    if (
        sha256_path(PREREGISTRATION_PATH) != PREREGISTRATION_SHA256
        or preregistration.get("schemaVersion") != 1
        or preregistration.get("role") != ROLE
        or preregistration.get("observedAtPreregistration") is not False
        or preregistration.get("frozenLayout") != predicted_layout()
    ):
        raise ValueError("clip-boundary preregistration differs")
    return preregistration


def validate_manifest(root: Path) -> tuple[JsonObject, Path]:
    manifest_path = root / "manifest.json"
    manifest: JsonObject = json.loads(manifest_path.read_text(encoding="utf-8"))
    evidence = manifest.get("rasterClipBoundaryTomography", {})
    raw_path = root / str(evidence.get("file", ""))
    if (
        manifest.get("schemaVersion") != SCHEMA_VERSION
        or manifest.get("rigVersion") != RIG_VERSION
        or not isinstance(manifest.get("ciCommit"), str)
        or len(str(manifest.get("ciCommit"))) != 40
        or evidence.get("role") != ROLE
        or evidence.get("preregistrationSha256") != PREREGISTRATION_SHA256
        or evidence.get("layout") != predicted_layout()
        or evidence.get("deltaBits") != list(DELTA_BITS)
        or evidence.get("recordBytes") != RECORD_BYTES
        or not raw_path.is_file()
        or raw_path.stat().st_size != predicted_layout()["rawBytes"]
        or evidence.get("sha256") != sha256_path(raw_path)
    ):
        raise ValueError("clip-boundary manifest differs")
    return manifest, raw_path


def load_records(raw_path: Path) -> bytes:
    layout = predicted_layout()
    data = raw_path.read_bytes()
    if len(data) != int(layout["rawBytes"]):
        raise ValueError("clip-boundary raw byte count differs")
    return data


def case_records(data: bytes, case: ProbeCase) -> tuple[Record, ...]:
    return tuple(
        RECORD.unpack_from(data, record_index * RECORD_BYTES)
        for record_index in range(
            case.output_record_start,
            case.output_record_start + case.record_count,
        )
    )


def axis_observation_groups(
    records: RecordSequence, *, witness_index: int, axis: str
) -> tuple[list[tuple[float, int]], list[tuple[float, int]]]:
    if len(records) != LINE_SAMPLE_COUNT:
        raise ValueError("boundary record count differs")
    row = (7 + witness_index) * 4
    components = (0, 1) if axis == "x" else (2, 3)
    return tuple(
        [
            (0.0, int(records[first][row + components[0]])),
            (PULL_OFFSET, int(records[first][row + components[1]])),
            (30.0, int(records[first + 1][row + components[0]])),
            (
                30.0 + PULL_OFFSET,
                int(records[first + 1][row + components[1]]),
            ),
        ]
        for first in (0, 2)
    )  # type: ignore[return-value]


def accepted_baseline_slopes(
    records: RecordSequence, *, witness_index: int, span_pixels: int, axis: str
) -> tuple[int, ...]:
    direct = float32_bits(float32_value(DELTA_BITS[witness_index]) / span_pixels)
    groups = axis_observation_groups(records, witness_index=witness_index, axis=axis)
    return tuple(
        candidate
        for candidate in range(
            direct - CANDIDATE_RADIUS_FLOAT_ULPS,
            direct + CANDIDATE_RADIUS_FLOAT_ULPS + 1,
        )
        if all(
            factorization.top_left.factorized.shared_plane_accepts_slope(
                candidate,
                observations=group,
            )
            for group in groups
        )
    )


def slope_matches(
    records: RecordSequence, *, witness_index: int, axis: str, slope_bits: int
) -> bool:
    return all(
        factorization.top_left.factorized.shared_plane_accepts_slope(
            slope_bits,
            observations=group,
        )
        for group in axis_observation_groups(
            records,
            witness_index=witness_index,
            axis=axis,
        )
    )


def validate_record_integrity(data: bytes) -> JsonObject:
    cases, _groups = case_catalog()
    primitive_counts: Counter[int] = Counter()
    basis_sum_exact = 0
    barycentric_sum_exact = 0
    finite_float_word_count = 0
    expected_float_word_count = 0
    for case_index, case in enumerate(cases):
        observed = case_records(data, case)
        for record_index, record in enumerate(observed):
            x, y = case.sample(record_index)
            if (record[0], record[1], record[3]) != (x, y, case_index):
                raise ValueError(f"{case.name} record header differs")
            primitive = record[2]
            if primitive not in (0, 1):
                raise ValueError(f"{case.name} primitive ID differs")
            primitive_counts[primitive] += 1
            float_words = record[4:]
            finite_float_word_count += sum(
                word & 0x7F80_0000 != 0x7F80_0000 for word in float_words
            )
            expected_float_word_count += len(float_words)
            basis_sum_exact += record[11] == 0x3F80_0000
            barycentric_sum_exact += record[7] == 0x3F80_0000
    if finite_float_word_count != expected_float_word_count:
        raise ValueError("clip-boundary capture contains non-finite float words")
    return {
        "primitiveIdCounts": {
            str(key): value for key, value in sorted(primitive_counts.items())
        },
        "finiteFloatWordCount": finite_float_word_count,
        "basisCenterSumExactlyOneCount": basis_sum_exact,
        "builtinBarycentricSumExactlyOneCount": barycentric_sum_exact,
    }


def validate_boundaries(data: bytes) -> tuple[JsonObject, bool]:
    cases, groups = case_catalog()
    reports: JsonObject = {}
    all_groups_match = True
    for group in groups:
        axis = "x" if group.plane in {"left", "right"} else "y"
        span = group.viewport + group.viewport // 4
        safe = cases[group.safe_case]
        baseline_slopes: list[int] = []
        for witness_index in range(WITNESS_COUNT):
            accepted = accepted_baseline_slopes(
                case_records(data, safe),
                witness_index=witness_index,
                span_pixels=span,
                axis=axis,
            )
            if len(accepted) != 1:
                raise ValueError(
                    f"{group.name} witness {witness_index} baseline is not unique"
                )
            baseline_slopes.append(accepted[0])
        match_counts: list[int] = []
        edge_values: list[int] = []
        for case_index in range(
            group.first_case,
            group.first_case + group.case_count,
        ):
            case = cases[case_index]
            edge = case.geometry_fixed[
                {"left": 0, "right": 1, "top": 2, "bottom": 3}[group.plane]
            ]
            edge_values.append(edge)
            observed = case_records(data, case)
            match_counts.append(
                sum(
                    slope_matches(
                        observed,
                        witness_index=witness_index,
                        axis=axis,
                        slope_bits=baseline_slopes[witness_index],
                    )
                    for witness_index in range(WITNESS_COUNT)
                )
            )
        lower_plane = group.plane in {"left", "top"}
        expected_matches = [
            edge >= group.candidate_edge_fixed
            if lower_plane
            else edge <= group.candidate_edge_fixed
            for edge in edge_values
        ]
        observed_matches = [count == WITNESS_COUNT for count in match_counts]
        candidate_gate = observed_matches == expected_matches
        all_groups_match &= candidate_gate
        changed_edges = [
            edge for edge, matches in zip(edge_values, observed_matches) if not matches
        ]
        unchanged_edges = [
            edge for edge, matches in zip(edge_values, observed_matches) if matches
        ]
        reports[group.name] = {
            "axis": axis,
            "plane": group.plane,
            "caseCount": group.case_count,
            "candidateEdgeFixed": group.candidate_edge_fixed,
            "candidateEdgePixels": group.candidate_edge_fixed / UNITS_PER_PIXEL,
            "baselineSlopeBits": baseline_slopes,
            "allWitnessMatchCaseCount": sum(observed_matches),
            "partiallyMatchingCaseCount": sum(
                0 < count < WITNESS_COUNT for count in match_counts
            ),
            "zeroWitnessMatchCaseCount": sum(count == 0 for count in match_counts),
            "nearestChangedEdgeFixed": (
                max(changed_edges) if lower_plane else min(changed_edges)
            ),
            "nearestUnchangedEdgeFixed": (
                min(unchanged_edges) if lower_plane else max(unchanged_edges)
            ),
            "candidateNDCOnePointFiveGate": candidate_gate,
        }
    return reports, all_groups_match


def validate(root: Path) -> JsonObject:
    load_preregistration()
    manifest, raw_path = validate_manifest(root)
    data = load_records(raw_path)
    integrity = validate_record_integrity(data)
    boundary_reports, boundary_gate = validate_boundaries(data)
    return {
        "liquidGlassRasterClipBoundaryTomographyValidationSchemaVersion": 1,
        "classification": ROLE,
        "probe": str(root),
        "ciCommit": manifest.get("ciCommit"),
        "manifestSha256": sha256_path(root / "manifest.json"),
        "rawSha256": sha256_path(raw_path),
        "preregistrationSha256": PREREGISTRATION_SHA256,
        "measurement": {
            "integrity": integrity,
            "boundaryGroups": boundary_reports,
            "candidateNDCOnePointFiveGate": boundary_gate,
            "captureValidForAnalysis": True,
        },
        "conclusions": {
            "normalizedGuardBoundaryEstablished": boundary_gate,
            "generatedTopologyCaptured": True,
            "clipArithmeticEstablished": False,
            "endToEndLiquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.root is None:
        print(json.dumps(predicted_layout(), indent=2, sort_keys=True))
        return
    if arguments.output is None:
        raise SystemExit("--output is required with a capture root")
    report = validate(arguments.root)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    raise SystemExit(
        0 if report["measurement"]["candidateNDCOnePointFiveGate"] else 1
    )


if __name__ == "__main__":
    main()
