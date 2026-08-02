#!/usr/bin/env python3
"""Audit post-opening laws recovered from the failed allocation holdout."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


EXPECTED_GEOMETRIES = frozenset(
    {
        "circle-256-center",
        "circle-512-offset",
        "circle-640-fractional",
        "circle-1536-center",
    }
)
CARRIER_PATH = [1]
ALLOCATION_QUANTUM = 64
ORIGIN_QUANTUM = 4
EDGE_NAMES = ("xLower", "yLower", "xUpper", "yUpper")


def mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} is not an object")
    return value


def sequence(value: object, name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{name} is not an array")
    return value


def numeric(value: object, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} is not finite")
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def float32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def round_nearest_away(value: float) -> int:
    return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)


def align_up(value: float, alignment: int = ALLOCATION_QUANTUM) -> int:
    if not math.isfinite(value) or value <= 0 or alignment <= 0:
        raise ValueError("allocation extent must be finite and positive")
    return alignment * math.ceil(value / alignment)


def align_down(value: float, alignment: int = ORIGIN_QUANTUM) -> int:
    if not math.isfinite(value) or alignment <= 0:
        raise ValueError("origin coordinate and alignment must be valid")
    return alignment * math.floor(value / alignment)


def predicted_carrier(
    geometry: Mapping[str, Any], remaining: float
) -> dict[str, list[float | int]]:
    if not 0.0 < remaining <= 1.0:
        raise ValueError("holdout remaining value is outside (0, 1]")
    width = numeric(geometry.get("width"), "geometry width")
    height = numeric(geometry.get("height"), "geometry height")
    window_width = numeric(geometry.get("windowWidth"), "window width")
    window_height = numeric(geometry.get("windowHeight"), "window height")
    if remaining < 1.0:
        return {
            "position": [
                (window_width - width * remaining) / 2.0,
                (window_height - height * remaining) / 2.0,
            ],
            "extent": [width * remaining, height * remaining],
        }
    center_x = numeric(geometry.get("centerX"), "geometry centerX")
    center_y = numeric(geometry.get("centerY"), "geometry centerY")
    return {
        "position": [
            round_nearest_away(center_x - width / 2.0),
            round_nearest_away(center_y - height / 2.0),
        ],
        "extent": [width, height],
    }


def allocation_bounds(
    geometry: Mapping[str, Any], carrier_position: Sequence[float | int]
) -> dict[str, list[float]]:
    if len(carrier_position) != 2:
        raise ValueError("carrier position is not two-dimensional")
    x = numeric(carrier_position[0], "carrier X")
    y = numeric(carrier_position[1], "carrier Y")
    width = numeric(geometry.get("width"), "geometry width")
    height = numeric(geometry.get("height"), "geometry height")
    window_width = numeric(geometry.get("windowWidth"), "window width")
    window_height = numeric(geometry.get("windowHeight"), "window height")
    return {
        "x": [max(0.0, x), min(window_width, x + width)],
        "y": [
            max(0.0, window_height - (y + height)),
            min(window_height, window_height - y),
        ],
    }


def clipped_sides(
    geometry: Mapping[str, Any], carrier_position: Sequence[float | int]
) -> dict[str, bool]:
    if len(carrier_position) != 2:
        raise ValueError("carrier position is not two-dimensional")
    x = numeric(carrier_position[0], "carrier X")
    y = numeric(carrier_position[1], "carrier Y")
    width = numeric(geometry.get("width"), "geometry width")
    height = numeric(geometry.get("height"), "geometry height")
    window_width = numeric(geometry.get("windowWidth"), "window width")
    window_height = numeric(geometry.get("windowHeight"), "window height")
    metal_y_lower = window_height - (y + height)
    metal_y_upper = window_height - y
    return {
        "xLower": x < 0.0,
        "xUpper": x + width > window_width,
        "yLower": metal_y_lower < 0.0,
        "yUpper": metal_y_upper > window_height,
    }


def nonendpoint_allocation_metadata(
    bounds: Mapping[str, Sequence[float]], *, scale: float
) -> dict[str, list[int]]:
    x_bounds = sequence(bounds.get("x"), "X allocation bounds")
    y_bounds = sequence(bounds.get("y"), "Y allocation bounds")
    if len(x_bounds) != 2 or len(y_bounds) != 2:
        raise ValueError("allocation bounds are not two-dimensional intervals")
    crop: list[int] = []
    clamp: list[int] = []
    extent: list[int] = []
    for axis, interval in enumerate((x_bounds, y_bounds)):
        lower = numeric(interval[0], "allocation lower bound")
        upper = numeric(interval[1], "allocation upper bound")
        scaled_lower = scale * lower
        crop_value = (
            0
            if lower == 0.0
            else math.floor(scaled_lower) + 1
            if axis == 0
            else math.ceil(scaled_lower)
        )
        clamp_value = math.floor(scale * upper) - crop_value - 1
        if clamp_value < 0:
            raise ValueError("predicted copy-base clamp is empty")
        crop.append(crop_value)
        clamp.append(clamp_value)
        extent.append(align_up(clamp_value + 1))
    return {
        "cropOrigin": crop,
        "clampMaximum": clamp,
        "producerExtent": extent,
        "scissorExtent": [
            min(producer_extent, clamp_maximum + 18)
            for producer_extent, clamp_maximum in zip(extent, clamp, strict=True)
        ],
    }


def expected_nonendpoint_vertex_count(sides: Mapping[str, bool]) -> int:
    required = {"xLower", "xUpper", "yLower", "yUpper"}
    if set(sides) != required or any(
        not isinstance(value, bool) for value in sides.values()
    ):
        raise ValueError("clipped-side flags differ")
    x_segments = 1 + int(sides["xLower"]) + int(sides["xUpper"])
    y_segments = 1 + int(sides["yLower"]) + int(sides["yUpper"])
    return 4 * x_segments * y_segments


def expected_auxiliary_quad_bounds(
    primary: Mapping[str, Any], sides: Mapping[str, bool]
) -> list[dict[str, list[float]]]:
    position = sequence(primary.get("position"), "primary position bounds")
    source = sequence(primary.get("source"), "primary source bounds")
    if len(position) != 4 or len(source) != 4:
        raise ValueError("primary producer bounds are incomplete")
    x0, y0, x1, y1 = (numeric(value, "primary position") for value in position)
    u0, v0, u1, v1 = (numeric(value, "primary source") for value in source)

    def quad(
        quad_position: list[float], quad_source: list[float]
    ) -> dict[str, list[float]]:
        return {"position": quad_position, "source": quad_source}

    if not any(sides.values()):
        return []
    if sides == {
        "xLower": False,
        "xUpper": True,
        "yLower": True,
        "yUpper": False,
    }:
        return [
            quad([x0, y0 - 1, x1, y0], [u0, v0 + 0.5, u1, v0 + 0.5]),
            quad(
                [x1, y0 - 1, x1 + 1, y0],
                [u1 - 0.5, v0 + 0.5, u1 - 0.5, v0 + 0.5],
            ),
            quad([x1, y0, x1 + 1, y1], [u1 - 0.5, v0, u1 - 0.5, v1]),
        ]
    if all(sides.values()):
        return [
            quad([x0 - 1, y0, x0, y1], [u0 + 0.5, v0, u0 + 0.5, v1]),
            quad(
                [x0 - 1, y0 - 1, x0, y0],
                [u0 + 0.5, v0 + 0.5, u0 + 0.5, v0 + 0.5],
            ),
            quad([x0, y0 - 1, x1, y0], [u0, v0 + 0.5, u1, v0 + 0.5]),
            quad(
                [x1, y0 - 1, x1 + 1, y0],
                [u1 - 0.5, v0 + 0.5, u1 - 0.5, v0 + 0.5],
            ),
            quad([x1, y0, x1 + 1, y1], [u1 - 0.5, v0, u1 - 0.5, v1]),
            quad(
                [x1, y1, x1 + 1, y1 + 1],
                [u1 - 0.5, v1 - 0.5, u1 - 0.5, v1 - 0.5],
            ),
            quad([x0, y1, x1, y1 + 1], [u0, v1 - 0.5, u1, v1 - 0.5]),
            quad(
                [x0 - 1, y1, x0, y1 + 1],
                [u0 + 0.5, v1 - 0.5, u0 + 0.5, v1 - 0.5],
            ),
        ]
    raise ValueError(f"unmeasured non-endpoint clipping combination: {dict(sides)}")


def origin_candidate(
    bounds: Mapping[str, Sequence[float]], *, remaining: float, scale: float
) -> list[int]:
    x_bounds = sequence(bounds.get("x"), "X allocation bounds")
    y_bounds = sequence(bounds.get("y"), "Y allocation bounds")
    if len(x_bounds) != 2 or len(y_bounds) != 2:
        raise ValueError("allocation bounds are not two-dimensional intervals")
    return [
        align_down(
            scale * numeric(x_bounds[0], "X lower bound")
            - round_nearest_away(remaining)
        ),
        align_down(scale * numeric(y_bounds[0], "Y lower bound") - 1.0),
    ]


def destination_extent(
    bounds: Mapping[str, Sequence[float]],
    *,
    scale: float,
    effective_origin: Sequence[Any],
) -> list[int]:
    if len(effective_origin) != 2:
        raise ValueError("effective origin is not two-dimensional")
    result: list[int] = []
    for axis, origin in zip(("x", "y"), effective_origin, strict=True):
        interval = sequence(bounds.get(axis), f"{axis.upper()} allocation bounds")
        if len(interval) != 2:
            raise ValueError(f"{axis.upper()} allocation bounds are not an interval")
        upper = numeric(interval[1], f"{axis.upper()} upper bound")
        result.append(align_up(scale * upper - numeric(origin, "effective origin")))
    return result


def quad4_primary_bounds_candidate(
    bounds: Mapping[str, Sequence[float]], *, scale: float
) -> list[int]:
    x_bounds = sequence(bounds.get("x"), "X allocation bounds")
    y_bounds = sequence(bounds.get("y"), "Y allocation bounds")
    if len(x_bounds) != 2 or len(y_bounds) != 2:
        raise ValueError("allocation bounds are not two-dimensional intervals")
    x_lower, x_upper = (numeric(value, "X allocation bound") for value in x_bounds)
    y_lower, y_upper = (numeric(value, "Y allocation bound") for value in y_bounds)
    return [
        math.floor(scale * (math.floor(x_lower) - 2)),
        max(0, math.floor(scale * (math.ceil(y_lower) - 10))),
        math.ceil(scale * (math.ceil(x_upper) + 1)),
        math.ceil(scale * (math.ceil(y_upper) + 2)),
    ]


def primary_position_bounds(vertices: object) -> list[float]:
    rows = sequence(vertices, "primary vertices")
    if len(rows) != 4:
        raise ValueError("primary producer quad does not have four vertices")
    parsed = [sequence(row, "primary vertex") for row in rows]
    if any(len(row) < 6 for row in parsed):
        raise ValueError("primary producer vertex is incomplete")
    return [
        min(numeric(row[0], "vertex X") for row in parsed),
        min(numeric(row[1], "vertex Y") for row in parsed),
        max(numeric(row[0], "vertex X") for row in parsed),
        max(numeric(row[1], "vertex Y") for row in parsed),
    ]


def carrier_state(record: Mapping[str, Any]) -> Mapping[str, Any]:
    states = sequence(record.get("capturedLayerStates"), "captured layer states")
    matching = [
        mapping(state, "captured layer state")
        for state in states
        if isinstance(state, Mapping) and state.get("path") == CARRIER_PATH
    ]
    if len(matching) != 1:
        raise ValueError(f"expected one presentation carrier; found {len(matching)}")
    return matching[0]


def metric(*, component_count: int, mismatch_count: int) -> dict[str, Any]:
    return {
        "componentCount": component_count,
        "mismatchedComponents": mismatch_count,
        "exact": mismatch_count == 0,
    }


def load_json(path: Path, name: str) -> Mapping[str, Any]:
    return mapping(json.loads(path.read_text(encoding="utf-8")), name)


def analyze(
    result_paths: Sequence[Path], *, artifact_root: Path, run_id: int
) -> dict[str, Any]:
    if run_id <= 0:
        raise ValueError("run ID must be positive")
    input_records: list[dict[str, Any]] = []
    prospective_passes: list[bool] = []
    geometry_names: set[str] = set()
    state_count = 0
    runtime_scale_components = 0
    runtime_scale_mismatches = 0
    primary_source_components = 0
    primary_source_mismatches = 0
    all_source_components = 0
    all_source_mismatches = 0
    carrier_components = 0
    carrier_mismatches = 0
    destination_components = 0
    destination_mismatches = 0
    origin_components = 0
    origin_mismatches = 0
    origin_residuals: list[dict[str, Any]] = []
    quad4_state_count = 0
    quad4_components = 0
    quad4_mismatches = 0
    quad4_residuals: list[dict[str, Any]] = []
    topology_counts: Counter[int] = Counter()
    nonendpoint_crop_clamp_components = 0
    nonendpoint_crop_clamp_mismatches = 0
    nonendpoint_producer_extent_components = 0
    nonendpoint_producer_extent_mismatches = 0
    nonendpoint_scissor_components = 0
    nonendpoint_scissor_mismatches = 0
    nonendpoint_topology_states = 0
    nonendpoint_topology_mismatches = 0
    nonendpoint_auxiliary_components = 0
    nonendpoint_auxiliary_mismatches = 0
    nonendpoint_side_patterns: Counter[str] = Counter()

    for result_path in sorted(result_paths):
        result = load_json(result_path, "holdout validator result")
        geometry = mapping(result.get("geometry"), "holdout geometry")
        geometry_name = geometry.get("name")
        if (
            not isinstance(geometry_name, str)
            or geometry_name not in EXPECTED_GEOMETRIES
        ):
            raise ValueError(f"unexpected holdout geometry: {geometry_name!r}")
        if geometry_name in geometry_names:
            raise ValueError(f"duplicate holdout geometry: {geometry_name}")
        geometry_names.add(geometry_name)
        acceptance = mapping(result.get("acceptance"), "prospective acceptance")
        prospective_passed = acceptance.get("passed") is True
        prospective_passes.append(prospective_passed)
        timeline_description = result.get("timeline")
        timeline_hash = result.get("timelineSHA256")
        if not isinstance(timeline_description, str) or not isinstance(
            timeline_hash, str
        ):
            raise ValueError("validator result has no timeline identity")
        timeline_relative = (
            Path(Path(timeline_description).parent.name)
            / Path(timeline_description).name
        )
        timeline_path = artifact_root / timeline_relative
        actual_timeline_hash = sha256_file(timeline_path)
        if actual_timeline_hash != timeline_hash:
            raise ValueError(f"timeline hash differs for {geometry_name}")
        timeline = load_json(timeline_path, "transition timeline")
        if mapping(timeline.get("geometry"), "timeline geometry") != geometry:
            raise ValueError(f"timeline geometry differs for {geometry_name}")
        uniforms = mapping(
            timeline.get("dynamicBackgroundUniforms"),
            "dynamic background uniforms",
        )
        raw_records = sequence(uniforms.get("records"), "dynamic background records")
        raw_by_sample = {
            int(mapping(record, "dynamic background record")["sampleIndex"]): mapping(
                record, "dynamic background record"
            )
            for record in raw_records
        }
        validated_states = sequence(result.get("states"), "validated states")
        prospective_aggregate = mapping(
            result.get("aggregate"), "prospective aggregate"
        )
        prospective_mismatches = {
            field: int(
                mapping(prospective_aggregate.get(field), field)["mismatchedComponents"]
            )
            for field in (
                "cropOrigin",
                "textureCoordinateClamp",
                "producerExtent",
                "destinationExtent",
                "effectiveOrigin",
            )
        }

        for untyped_state in validated_states:
            state = mapping(untyped_state, "validated state")
            sample_index = int(state["sampleIndex"])
            raw_record = raw_by_sample.get(sample_index)
            if raw_record is None:
                raise ValueError(
                    f"timeline lacks {geometry_name} sample {sample_index}"
                )
            remaining = numeric(state.get("remaining"), "remaining")
            if numeric(raw_record.get("remaining"), "raw remaining") != remaining:
                raise ValueError("raw and validated remaining values differ")
            scale = numeric(state.get("runtimeScale"), "runtime scale")
            expected_scale = 1.0 - remaining / 2.0
            runtime_scale_components += 1
            runtime_scale_mismatches += scale != expected_scale
            carrier_prediction = predicted_carrier(geometry, remaining)
            raw_carrier = carrier_state(raw_record)
            position = sequence(raw_carrier.get("position"), "carrier position")
            bounds = sequence(raw_carrier.get("bounds"), "carrier bounds")
            if len(position) != 2 or len(bounds) != 4 or list(bounds[:2]) != [0, 0]:
                raise ValueError("presentation carrier shape differs")
            observed_carrier = [*position, *bounds[2:]]
            expected_carrier = [
                *carrier_prediction["position"],
                *carrier_prediction["extent"],
            ]
            carrier_components += 4
            carrier_mismatches += sum(
                observed != expected
                for observed, expected in zip(
                    observed_carrier, expected_carrier, strict=True
                )
            )
            policy_bounds = allocation_bounds(geometry, carrier_prediction["position"])
            observed = mapping(state.get("observed"), "observed allocation policy")
            observed_origin = sequence(
                observed.get("effectiveOrigin"), "observed effective origin"
            )
            observed_destination = sequence(
                observed.get("destinationExtent"), "observed destination extent"
            )
            predicted_destination = destination_extent(
                policy_bounds,
                scale=scale,
                effective_origin=observed_origin,
            )
            if len(observed_destination) != 2:
                raise ValueError("observed destination extent is not two-dimensional")
            destination_components += 2
            destination_mismatches += sum(
                predicted != observed_value
                for predicted, observed_value in zip(
                    predicted_destination, observed_destination, strict=True
                )
            )
            predicted_origin = origin_candidate(
                policy_bounds,
                remaining=remaining,
                scale=scale,
            )
            if len(observed_origin) != 2:
                raise ValueError("observed effective origin is not two-dimensional")
            origin_components += 2
            for axis, predicted, observed_value in zip(
                ("x", "y"), predicted_origin, observed_origin, strict=True
            ):
                if predicted == observed_value:
                    continue
                origin_mismatches += 1
                lower = numeric(policy_bounds[axis][0], "allocation lower bound")
                origin_residuals.append(
                    {
                        "geometry": geometry_name,
                        "sampleIndex": sample_index,
                        "axis": axis,
                        "remaining": remaining,
                        "scaledLower": scale * lower,
                        "predicted": predicted,
                        "observed": observed_value,
                        "difference": predicted
                        - numeric(observed_value, "observed effective origin"),
                    }
                )

            mesh = mapping(observed.get("producerMesh"), "producer mesh")
            vertex_count = int(mesh["vertexCount"])
            topology_counts[vertex_count] += 1
            quad_bounds = sequence(mesh.get("quadBounds"), "producer quad bounds")
            if remaining < 1.0:
                allocation_prediction = nonendpoint_allocation_metadata(
                    policy_bounds, scale=scale
                )
                observed_crop = sequence(
                    observed.get("cropOrigin"), "observed crop origin"
                )
                observed_clamp = sequence(
                    observed.get("textureCoordinateClamp"),
                    "observed texture-coordinate clamp",
                )
                observed_extent = sequence(
                    observed.get("producerExtent"), "observed producer extent"
                )
                observed_scissor = sequence(mesh.get("scissor"), "producer scissor")
                predicted_crop_clamp = [
                    *allocation_prediction["cropOrigin"],
                    *allocation_prediction["clampMaximum"],
                ]
                observed_crop_clamp = [*observed_crop, *observed_clamp[2:]]
                nonendpoint_crop_clamp_components += 4
                nonendpoint_crop_clamp_mismatches += sum(
                    predicted != observed_value
                    for predicted, observed_value in zip(
                        predicted_crop_clamp, observed_crop_clamp, strict=True
                    )
                )
                nonendpoint_producer_extent_components += 2
                nonendpoint_producer_extent_mismatches += sum(
                    predicted != observed_value
                    for predicted, observed_value in zip(
                        allocation_prediction["producerExtent"],
                        observed_extent,
                        strict=True,
                    )
                )
                nonendpoint_scissor_components += 2
                nonendpoint_scissor_mismatches += sum(
                    predicted != observed_value
                    for predicted, observed_value in zip(
                        allocation_prediction["scissorExtent"],
                        observed_scissor[2:],
                        strict=True,
                    )
                )
                sides = clipped_sides(geometry, carrier_prediction["position"])
                pattern = ",".join(name for name, clipped in sides.items() if clipped)
                nonendpoint_side_patterns[pattern or "none"] += 1
                expected_vertex_count = expected_nonendpoint_vertex_count(sides)
                nonendpoint_topology_states += 1
                nonendpoint_topology_mismatches += expected_vertex_count != vertex_count
                if not quad_bounds:
                    raise ValueError("producer mesh has no primary quad")
                expected_auxiliary = expected_auxiliary_quad_bounds(
                    mapping(quad_bounds[0], "primary quad bounds"), sides
                )
                observed_auxiliary = [
                    mapping(value, "auxiliary quad bounds") for value in quad_bounds[1:]
                ]
                nonendpoint_auxiliary_components += 8 * len(expected_auxiliary)
                nonendpoint_auxiliary_mismatches += 8 * abs(
                    len(expected_auxiliary) - len(observed_auxiliary)
                )
                for predicted_quad, observed_quad in zip(
                    expected_auxiliary, observed_auxiliary
                ):
                    for field in ("position", "source"):
                        predicted_values = predicted_quad[field]
                        observed_values = sequence(
                            observed_quad.get(field), f"auxiliary {field} bounds"
                        )
                        if len(observed_values) != 4:
                            raise ValueError(f"auxiliary {field} bounds are incomplete")
                        nonendpoint_auxiliary_mismatches += sum(
                            predicted != observed_value
                            for predicted, observed_value in zip(
                                predicted_values, observed_values, strict=True
                            )
                        )
            vertices = sequence(mesh.get("primaryVertices"), "primary vertices")
            for row in vertices:
                vertex = sequence(row, "primary vertex")
                if len(vertex) < 6:
                    raise ValueError("primary producer vertex is incomplete")
                for axis in range(2):
                    predicted_source = float32(
                        numeric(vertex[axis], "primary position") / scale
                    )
                    observed_source = numeric(
                        vertex[4 + axis], "primary source coordinate"
                    )
                    primary_source_components += 1
                    primary_source_mismatches += float32_bits(
                        predicted_source
                    ) != float32_bits(observed_source)
            all_source_components += int(mesh["allSourceScaleComponentCount"])
            all_source_mismatches += int(mesh["allSourceScaleMismatchedComponents"])
            if vertex_count == 4:
                quad4_state_count += 1
                predicted_edges = quad4_primary_bounds_candidate(
                    policy_bounds, scale=scale
                )
                observed_edges = primary_position_bounds(vertices)
                quad4_components += 4
                for edge_name, predicted, observed_value in zip(
                    EDGE_NAMES, predicted_edges, observed_edges, strict=True
                ):
                    if predicted == observed_value:
                        continue
                    quad4_mismatches += 1
                    quad4_residuals.append(
                        {
                            "geometry": geometry_name,
                            "sampleIndex": sample_index,
                            "edge": edge_name,
                            "remaining": remaining,
                            "predicted": predicted,
                            "observed": observed_value,
                            "difference": predicted - observed_value,
                        }
                    )
        state_count += len(validated_states)
        input_records.append(
            {
                "geometry": geometry_name,
                "validatorResult": result_path.name,
                "validatorResultSHA256": sha256_file(result_path),
                "timelineArtifact": str(timeline_relative),
                "timelineSHA256": timeline_hash,
                "prospectiveAcceptancePassed": prospective_passed,
                "prospectiveMismatchedComponents": prospective_mismatches,
            }
        )

    if geometry_names != EXPECTED_GEOMETRIES:
        missing = sorted(EXPECTED_GEOMETRIES - geometry_names)
        extra = sorted(geometry_names - EXPECTED_GEOMETRIES)
        raise ValueError(
            f"holdout geometry set differs; missing={missing}, extra={extra}"
        )
    prospective_frozen_gate_passed = all(prospective_passes)
    carrier_metric = metric(
        component_count=carrier_components, mismatch_count=carrier_mismatches
    )
    destination_metric = metric(
        component_count=destination_components,
        mismatch_count=destination_mismatches,
    )
    origin_metric = {
        **metric(component_count=origin_components, mismatch_count=origin_mismatches),
        "residuals": origin_residuals,
    }
    quad4_metric = {
        "stateCount": quad4_state_count,
        **metric(component_count=quad4_components, mismatch_count=quad4_mismatches),
        "residuals": quad4_residuals,
    }
    nonendpoint_topology_metric = {
        "stateCount": nonendpoint_topology_states,
        "mismatchedStates": nonendpoint_topology_mismatches,
        "exact": nonendpoint_topology_mismatches == 0,
        "clippedSidePatternStates": {
            pattern: nonendpoint_side_patterns[pattern]
            for pattern in sorted(nonendpoint_side_patterns)
        },
    }
    nonendpoint_auxiliary_metric = metric(
        component_count=nonendpoint_auxiliary_components,
        mismatch_count=nonendpoint_auxiliary_mismatches,
    )
    return {
        "dynamicAllocationGeometryHoldoutAnalysisSchemaVersion": 1,
        "classification": (
            "post-opening-retrospective-analysis-of-failed-prospective-holdout"
        ),
        "runID": run_id,
        "inputs": input_records,
        "aggregate": {
            "geometryCount": len(geometry_names),
            "stateCount": state_count,
            "prospectiveFrozenGatePassed": prospective_frozen_gate_passed,
            "runtimeScale": metric(
                component_count=runtime_scale_components,
                mismatch_count=runtime_scale_mismatches,
            ),
            "primaryProducerSourceQ": metric(
                component_count=primary_source_components,
                mismatch_count=primary_source_mismatches,
            ),
            "allProducerQuadSourceQDiagnostic": metric(
                component_count=all_source_components,
                mismatch_count=all_source_mismatches,
            ),
            "presentationCarrier": carrier_metric,
            "destinationExtentGivenObservedEffectiveOrigin": destination_metric,
            "narrowEffectiveOriginCandidate": origin_metric,
            "quad4PrimaryPositionBoundsCandidate": quad4_metric,
            "nonEndpointCropAndClamp": metric(
                component_count=nonendpoint_crop_clamp_components,
                mismatch_count=nonendpoint_crop_clamp_mismatches,
            ),
            "nonEndpointProducerExtent": metric(
                component_count=nonendpoint_producer_extent_components,
                mismatch_count=nonendpoint_producer_extent_mismatches,
            ),
            "producerScissorFromClamp": metric(
                component_count=nonendpoint_scissor_components,
                mismatch_count=nonendpoint_scissor_mismatches,
            ),
            "nonEndpointTopology": nonendpoint_topology_metric,
            "nonEndpointAuxiliaryBoundsGivenPrimary": (nonendpoint_auxiliary_metric),
            "producerVertexCountStates": {
                str(count): topology_counts[count] for count in sorted(topology_counts)
            },
        },
        "conclusion": {
            "prospectiveFrozenGatePassed": prospective_frozen_gate_passed,
            "retrospectiveCarrierLawExact": carrier_metric["exact"],
            "retrospectiveDestinationLawExactGivenObservedOrigin": (
                destination_metric["exact"]
            ),
            "retrospectiveNonEndpointTopologyExact": (
                nonendpoint_topology_metric["exact"]
            ),
            "retrospectiveNonEndpointAuxiliaryBoundsExactGivenPrimary": (
                nonendpoint_auxiliary_metric["exact"]
            ),
            "independentEffectiveOriginPolicyRecovered": origin_metric["exact"],
            "independentProducerMeshPolicyRecovered": (
                quad4_metric["exact"] and set(topology_counts) == {4}
            ),
            "requiresNewUnseenHoldout": True,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--validator-result-dir", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result_paths = sorted(
        arguments.validator_result_dir.glob(
            f"dynamic-allocation-holdout-circle-*-{arguments.run_id}.json"
        )
    )
    result = analyze(
        result_paths,
        artifact_root=arguments.artifact_root,
        run_id=arguments.run_id,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
        print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
