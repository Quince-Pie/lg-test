#!/usr/bin/env python3
"""Audit the preregistered dense dynamic-allocation calibration."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_dynamic_allocation_holdout as allocation


EXPECTED_GEOMETRIES = frozenset(
    {
        "circle-256-center",
        "circle-512-offset",
        "circle-640-fractional",
        "circle-1536-center",
    }
)
EXPECTED_SAMPLE_INDICES = tuple(range(1, 33))
CALIBRATION_CLASSIFICATION = "post-opening-dense-temporal-allocation-calibration"
RATIO_PHASE = "resampling-ratio-five-fourths"
PADDING_PHASE = "rounded-eight-pixel-transition-padding"
PHASE_CANDIDATES = (RATIO_PHASE, PADDING_PHASE)


def metric(*, component_count: int, mismatch_count: int) -> dict[str, Any]:
    return {
        "componentCount": component_count,
        "mismatchedComponents": mismatch_count,
        "exact": mismatch_count == 0,
    }


def phase_halo(remaining: float, candidate: str) -> int:
    if not 0.0 < remaining <= 1.0:
        raise ValueError("remaining value is outside (0, 1]")
    if candidate == RATIO_PHASE:
        return 2 if remaining >= 2.0 / 5.0 else 1
    if candidate == PADDING_PHASE:
        transition_padding = allocation.round_nearest_away(8.0 * (1.0 - remaining))
        return 2 if transition_padding <= 4 else 1
    raise ValueError(f"unknown phase candidate: {candidate}")


def phase_origin(
    *, crop: int, clipped_lower: float, remaining: float, candidate: str
) -> int:
    if clipped_lower < 0.0:
        raise ValueError("clipped lower bound is negative")
    if clipped_lower == 0.0:
        return -allocation.ORIGIN_QUANTUM
    return allocation.align_down(crop - phase_halo(remaining, candidate))


def primary_position_candidate(
    geometry: Mapping[str, Any],
    bounds: Mapping[str, Sequence[float]],
    *,
    scale: float,
    vertex_count: int,
) -> list[int]:
    if vertex_count == 4:
        return allocation.quad4_primary_bounds_candidate(bounds, scale=scale)
    x_bounds = allocation.sequence(bounds.get("x"), "X allocation bounds")
    y_bounds = allocation.sequence(bounds.get("y"), "Y allocation bounds")
    if len(x_bounds) != 2 or len(y_bounds) != 2:
        raise ValueError("allocation bounds are not two-dimensional intervals")
    if vertex_count == 16:
        return [
            math.floor(
                scale
                * (
                    math.floor(
                        allocation.numeric(x_bounds[0], "X lower allocation bound")
                    )
                    - 2
                )
            ),
            0,
            math.ceil(
                scale * allocation.numeric(geometry.get("windowWidth"), "window width")
            ),
            math.ceil(
                scale
                * (
                    math.ceil(
                        allocation.numeric(y_bounds[1], "Y upper allocation bound")
                    )
                    + 2
                )
            ),
        ]
    if vertex_count == 36:
        return [
            0,
            0,
            math.ceil(
                scale * allocation.numeric(geometry.get("windowWidth"), "window width")
            ),
            math.ceil(
                scale
                * allocation.numeric(geometry.get("windowHeight"), "window height")
            ),
        ]
    raise ValueError(f"no non-endpoint primary candidate for {vertex_count} vertices")


def compare_values(
    predicted: Sequence[Any], observed: Sequence[Any]
) -> tuple[int, int]:
    if len(predicted) != len(observed):
        raise ValueError("predicted and observed component counts differ")
    return len(predicted), sum(
        predicted_value != observed_value
        for predicted_value, observed_value in zip(predicted, observed, strict=True)
    )


def analyze(
    result_paths: Sequence[Path],
    *,
    artifact_root: Path,
    run_id: int,
) -> dict[str, Any]:
    if run_id <= 0:
        raise ValueError("run ID must be positive")
    geometry_names: set[str] = set()
    inputs: list[dict[str, Any]] = []
    state_count = 0
    nonendpoint_state_count = 0
    runtime_scale_components = 0
    runtime_scale_mismatches = 0
    primary_source_components = 0
    primary_source_mismatches = 0
    all_source_components = 0
    all_source_mismatches = 0
    phase_components = Counter[str]()
    phase_mismatches = Counter[str]()
    all_state_phase_components = Counter[str]()
    all_state_phase_mismatches = Counter[str]()
    phase_discriminators: list[dict[str, Any]] = []
    crop_clamp_components = 0
    crop_clamp_mismatches = 0
    producer_extent_components = 0
    producer_extent_mismatches = 0
    destination_components = 0
    destination_mismatches = 0
    scissor_components = 0
    scissor_mismatches = 0
    topology_states = 0
    topology_mismatches = 0
    auxiliary_components = 0
    auxiliary_mismatches = 0
    side_patterns: Counter[str] = Counter()
    topology_counts: Counter[int] = Counter()
    primary_metrics: dict[int, Counter[str]] = {}
    primary_residuals: list[dict[str, Any]] = []

    for result_path in sorted(result_paths):
        result = allocation.load_json(result_path, "calibration validator result")
        if result.get("classification") != CALIBRATION_CLASSIFICATION:
            raise ValueError("calibration classification differs")
        geometry = allocation.mapping(result.get("geometry"), "calibration geometry")
        geometry_name = geometry.get("name")
        if (
            not isinstance(geometry_name, str)
            or geometry_name not in EXPECTED_GEOMETRIES
        ):
            raise ValueError(f"unexpected calibration geometry: {geometry_name!r}")
        if geometry_name in geometry_names:
            raise ValueError(f"duplicate calibration geometry: {geometry_name}")
        geometry_names.add(geometry_name)
        calibration = allocation.mapping(result.get("calibration"), "calibration")
        if (
            calibration.get("captureIntegrityPassed") is not True
            or calibration.get("stateCount") != len(EXPECTED_SAMPLE_INDICES)
            or calibration.get("runtimeScaleLawExactEveryState") is not True
            or calibration.get("primaryProducerSourceQLawExactEveryState") is not True
        ):
            raise ValueError(f"calibration integrity differs for {geometry_name}")
        timeline_hash = result.get("timelineSHA256")
        timeline_description = result.get("timeline")
        if not isinstance(timeline_hash, str) or not isinstance(
            timeline_description, str
        ):
            raise ValueError("calibration timeline identity is incomplete")
        timeline_path = result_path.parent / Path(timeline_description).name
        if not timeline_path.is_relative_to(artifact_root):
            raise ValueError("calibration timeline is outside the artifact root")
        if allocation.sha256_file(timeline_path) != timeline_hash:
            raise ValueError(f"timeline hash differs for {geometry_name}")
        timeline = allocation.load_json(timeline_path, "calibration timeline")
        if (
            allocation.mapping(timeline.get("geometry"), "timeline geometry")
            != geometry
        ):
            raise ValueError(f"timeline geometry differs for {geometry_name}")
        states = allocation.sequence(result.get("states"), "calibration states")
        sample_indices = tuple(
            int(allocation.mapping(state, "calibration state")["sampleIndex"])
            for state in states
        )
        if sample_indices != EXPECTED_SAMPLE_INDICES:
            raise ValueError(f"sample indices differ for {geometry_name}")

        for untyped_state in states:
            state = allocation.mapping(untyped_state, "calibration state")
            sample_index = int(state["sampleIndex"])
            remaining = allocation.numeric(state.get("remaining"), "remaining")
            scale = allocation.numeric(state.get("runtimeScale"), "runtime scale")
            runtime_scale_components += 1
            runtime_scale_mismatches += scale != 1.0 - remaining / 2.0
            carrier = allocation.predicted_carrier(geometry, remaining)
            bounds = allocation.allocation_bounds(geometry, carrier["position"])
            observed = allocation.mapping(state.get("observed"), "observed policy")
            observed_crop = allocation.sequence(
                observed.get("cropOrigin"), "observed crop origin"
            )
            observed_origin = allocation.sequence(
                observed.get("effectiveOrigin"), "observed effective origin"
            )
            mesh = allocation.mapping(observed.get("producerMesh"), "producer mesh")
            vertex_count = int(mesh["vertexCount"])
            topology_counts[vertex_count] += 1
            primary_source_components += int(mesh["sourceScaleComponentCount"])
            primary_source_mismatches += int(mesh["sourceScaleMismatchedComponents"])
            all_source_components += int(mesh["allSourceScaleComponentCount"])
            all_source_mismatches += int(mesh["allSourceScaleMismatchedComponents"])

            for candidate in PHASE_CANDIDATES:
                for axis_index, axis in enumerate(("x", "y")):
                    predicted_origin = phase_origin(
                        crop=int(observed_crop[axis_index]),
                        clipped_lower=allocation.numeric(
                            bounds[axis][0], f"{axis.upper()} clipped lower bound"
                        ),
                        remaining=remaining,
                        candidate=candidate,
                    )
                    all_state_phase_components[candidate] += 1
                    all_state_phase_mismatches[candidate] += (
                        predicted_origin != observed_origin[axis_index]
                    )

            if remaining == 1.0:
                continue
            nonendpoint_state_count += 1
            prediction = allocation.nonendpoint_allocation_metadata(bounds, scale=scale)
            observed_clamp = allocation.sequence(
                observed.get("textureCoordinateClamp"), "observed clamp"
            )
            observed_extent = allocation.sequence(
                observed.get("producerExtent"), "observed producer extent"
            )
            observed_scissor = allocation.sequence(
                mesh.get("scissor"), "observed producer scissor"
            )
            count, mismatches = compare_values(
                [*prediction["cropOrigin"], *prediction["clampMaximum"]],
                [*observed_crop, *observed_clamp[2:]],
            )
            crop_clamp_components += count
            crop_clamp_mismatches += mismatches
            count, mismatches = compare_values(
                prediction["producerExtent"], observed_extent
            )
            producer_extent_components += count
            producer_extent_mismatches += mismatches
            count, mismatches = compare_values(
                prediction["scissorExtent"], observed_scissor[2:]
            )
            scissor_components += count
            scissor_mismatches += mismatches

            candidate_origins: dict[str, list[int]] = {}
            for candidate in PHASE_CANDIDATES:
                candidate_origins[candidate] = [
                    phase_origin(
                        crop=prediction["cropOrigin"][axis_index],
                        clipped_lower=allocation.numeric(
                            bounds[axis][0], f"{axis.upper()} clipped lower bound"
                        ),
                        remaining=remaining,
                        candidate=candidate,
                    )
                    for axis_index, axis in enumerate(("x", "y"))
                ]
                count, mismatches = compare_values(
                    candidate_origins[candidate], observed_origin
                )
                phase_components[candidate] += count
                phase_mismatches[candidate] += mismatches
            for axis_index, axis in enumerate(("x", "y")):
                ratio_value = candidate_origins[RATIO_PHASE][axis_index]
                padding_value = candidate_origins[PADDING_PHASE][axis_index]
                if ratio_value == padding_value:
                    continue
                phase_discriminators.append(
                    {
                        "geometry": geometry_name,
                        "sampleIndex": sample_index,
                        "axis": axis,
                        "remaining": remaining,
                        "cropOrigin": prediction["cropOrigin"][axis_index],
                        "observedEffectiveOrigin": observed_origin[axis_index],
                        "candidateOrigins": {
                            RATIO_PHASE: ratio_value,
                            PADDING_PHASE: padding_value,
                        },
                    }
                )
            predicted_destination = allocation.destination_extent(
                bounds,
                scale=scale,
                effective_origin=candidate_origins[PADDING_PHASE],
            )
            observed_destination = allocation.sequence(
                observed.get("destinationExtent"), "observed destination extent"
            )
            count, mismatches = compare_values(
                predicted_destination, observed_destination
            )
            destination_components += count
            destination_mismatches += mismatches

            sides = allocation.clipped_sides(geometry, carrier["position"])
            pattern = ",".join(name for name, clipped in sides.items() if clipped)
            side_patterns[pattern or "none"] += 1
            topology_states += 1
            topology_mismatches += (
                allocation.expected_nonendpoint_vertex_count(sides) != vertex_count
            )
            quads = allocation.sequence(mesh.get("quadBounds"), "producer quads")
            if not quads:
                raise ValueError("producer mesh has no primary quad")
            expected_auxiliary = allocation.expected_auxiliary_quad_bounds(
                allocation.mapping(quads[0], "primary producer quad"), sides
            )
            observed_auxiliary = [
                allocation.mapping(value, "auxiliary producer quad")
                for value in quads[1:]
            ]
            auxiliary_components += 8 * len(expected_auxiliary)
            auxiliary_mismatches += 8 * abs(
                len(expected_auxiliary) - len(observed_auxiliary)
            )
            for predicted_quad, observed_quad in zip(
                expected_auxiliary, observed_auxiliary
            ):
                for field in ("position", "source"):
                    _, mismatches = compare_values(
                        predicted_quad[field],
                        allocation.sequence(
                            observed_quad.get(field), f"auxiliary {field}"
                        ),
                    )
                    auxiliary_mismatches += mismatches

            predicted_primary = primary_position_candidate(
                geometry,
                bounds,
                scale=scale,
                vertex_count=vertex_count,
            )
            observed_primary = allocation.primary_position_bounds(
                mesh.get("primaryVertices")
            )
            counters = primary_metrics.setdefault(vertex_count, Counter())
            counters["stateCount"] += 1
            counters["componentCount"] += 4
            for edge, predicted_value, observed_value in zip(
                allocation.EDGE_NAMES,
                predicted_primary,
                observed_primary,
                strict=True,
            ):
                if predicted_value == observed_value:
                    continue
                counters["mismatchedComponents"] += 1
                primary_residuals.append(
                    {
                        "geometry": geometry_name,
                        "sampleIndex": sample_index,
                        "remaining": remaining,
                        "vertexCount": vertex_count,
                        "edge": edge,
                        "predicted": predicted_value,
                        "observed": observed_value,
                        "difference": predicted_value - observed_value,
                    }
                )
        state_count += len(states)
        inputs.append(
            {
                "geometry": geometry_name,
                "validatorResult": str(result_path.relative_to(artifact_root)),
                "validatorResultSHA256": allocation.sha256_file(result_path),
                "timelineArtifact": str(timeline_path.relative_to(artifact_root)),
                "timelineSHA256": timeline_hash,
            }
        )

    if geometry_names != EXPECTED_GEOMETRIES:
        missing = sorted(EXPECTED_GEOMETRIES - geometry_names)
        extra = sorted(geometry_names - EXPECTED_GEOMETRIES)
        raise ValueError(
            f"calibration geometry set differs; missing={missing}, extra={extra}"
        )
    selected_phase = (
        PADDING_PHASE
        if phase_mismatches[PADDING_PHASE] == 0
        and phase_mismatches[RATIO_PHASE] > 0
        and phase_discriminators
        else None
    )
    primary_by_topology = {
        str(vertex_count): {
            "stateCount": counters["stateCount"],
            **metric(
                component_count=counters["componentCount"],
                mismatch_count=counters["mismatchedComponents"],
            ),
        }
        for vertex_count, counters in sorted(primary_metrics.items())
    }
    primary_component_count = sum(
        value["componentCount"] for value in primary_by_topology.values()
    )
    primary_mismatch_count = sum(
        value["mismatchedComponents"] for value in primary_by_topology.values()
    )
    return {
        "dynamicAllocationPhaseCalibrationAnalysisSchemaVersion": 1,
        "classification": (
            "post-opening-analysis-of-preregistered-dense-temporal-calibration"
        ),
        "runID": run_id,
        "inputs": inputs,
        "aggregate": {
            "geometryCount": len(geometry_names),
            "stateCount": state_count,
            "nonEndpointStateCount": nonendpoint_state_count,
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
            "nonEndpointCropAndClamp": metric(
                component_count=crop_clamp_components,
                mismatch_count=crop_clamp_mismatches,
            ),
            "nonEndpointProducerExtent": metric(
                component_count=producer_extent_components,
                mismatch_count=producer_extent_mismatches,
            ),
            "nonEndpointDestinationExtentWithSelectedOrigin": metric(
                component_count=destination_components,
                mismatch_count=destination_mismatches,
            ),
            "producerScissorFromClamp": metric(
                component_count=scissor_components,
                mismatch_count=scissor_mismatches,
            ),
            "phaseCandidatesFromPredictedNonEndpointCrop": {
                candidate: metric(
                    component_count=phase_components[candidate],
                    mismatch_count=phase_mismatches[candidate],
                )
                for candidate in PHASE_CANDIDATES
            },
            "phaseCandidatesAllStatesGivenObservedCrop": {
                candidate: metric(
                    component_count=all_state_phase_components[candidate],
                    mismatch_count=all_state_phase_mismatches[candidate],
                )
                for candidate in PHASE_CANDIDATES
            },
            "phaseDiscriminatingComponents": phase_discriminators,
            "nonEndpointTopology": {
                "stateCount": topology_states,
                "mismatchedStates": topology_mismatches,
                "exact": topology_mismatches == 0,
                "clippedSidePatternStates": {
                    pattern: side_patterns[pattern] for pattern in sorted(side_patterns)
                },
            },
            "nonEndpointAuxiliaryBoundsGivenPrimary": metric(
                component_count=auxiliary_components,
                mismatch_count=auxiliary_mismatches,
            ),
            "nonEndpointPrimaryPositionCandidates": {
                "overall": {
                    **metric(
                        component_count=primary_component_count,
                        mismatch_count=primary_mismatch_count,
                    ),
                    "residuals": primary_residuals,
                },
                "byVertexCount": primary_by_topology,
            },
            "producerVertexCountStatesIncludingEndpoints": {
                str(count): topology_counts[count] for count in sorted(topology_counts)
            },
        },
        "conclusion": {
            "selectedFinitePhaseCandidate": selected_phase,
            "phaseCandidateSelectedByDiscriminator": selected_phase is not None,
            "nonEndpointAllocationMetadataRecoveredOnCalibration": all(
                mismatch_count == 0
                for mismatch_count in (
                    crop_clamp_mismatches,
                    producer_extent_mismatches,
                    destination_mismatches,
                    scissor_mismatches,
                    topology_mismatches,
                    auxiliary_mismatches,
                )
            ),
            "independentProducerMeshPolicyRecovered": primary_mismatch_count == 0,
            "requiresNewUnseenGeometryHoldout": True,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    artifact_root = arguments.artifact_root.resolve()
    result_paths = sorted(artifact_root.glob("*/dynamic-allocation-calibration.json"))
    result = analyze(
        result_paths,
        artifact_root=artifact_root,
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
