#!/usr/bin/env python3
"""Audit the same-diameter producer-mesh center intervention."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_dynamic_allocation_holdout as allocation


EXPECTED_GEOMETRIES = {
    "circle-640-center": (512.0, 512.0),
    "circle-640-integer": (602.0, 378.0),
    "circle-640-phase-0500-even": (602.5, 378.5),
    "circle-640-phase-0500-signed": (421.5, 646.5),
}
INTEGER_CONTROLS = frozenset({"circle-640-center", "circle-640-integer"})
HALF_PIXEL_CONTROLS = frozenset(
    {
        "circle-640-phase-0500-even",
        "circle-640-phase-0500-signed",
    }
)
EXPECTED_SAMPLE_INDICES = tuple(range(1, 33))


def mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} is not an object")
    return value


def sequence(value: object, name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{name} is not an array")
    return value


def numeric(value: object, name: str) -> float:
    return allocation.numeric(value, name)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def metric(component_count: int, mismatch_count: int) -> dict[str, Any]:
    return {
        "componentCount": component_count,
        "mismatchedComponents": mismatch_count,
        "exact": mismatch_count == 0,
    }


def causal_diagnostics(
    geometry_metrics: Mapping[str, Mapping[str, Any]],
    remaining_by_sample: Mapping[int, Mapping[str, float]],
) -> dict[str, Any]:
    if set(geometry_metrics) != set(EXPECTED_GEOMETRIES):
        raise ValueError("causal geometry metric set differs")
    if set(remaining_by_sample) != set(range(1, 32)):
        raise ValueError("non-endpoint remaining sample set differs")

    integer_mismatches = sum(
        int(geometry_metrics[name]["mismatchedComponents"]) for name in INTEGER_CONTROLS
    )
    half_mismatches = sum(
        int(geometry_metrics[name]["mismatchedComponents"])
        for name in HALF_PIXEL_CONTROLS
    )
    residual_edges = {
        name: sorted(
            {
                str(residual["edge"])
                for residual in sequence(
                    geometry_metrics[name]["residuals"],
                    f"{name} residuals",
                )
            }
        )
        for name in EXPECTED_GEOMETRIES
    }
    half_edge_intersection = sorted(
        set(residual_edges["circle-640-phase-0500-even"])
        & set(residual_edges["circle-640-phase-0500-signed"])
    )

    spreads: list[dict[str, Any]] = []
    exact_k_samples = 0
    for sample_index in range(1, 32):
        values_by_geometry = remaining_by_sample[sample_index]
        if set(values_by_geometry) != set(EXPECTED_GEOMETRIES):
            raise ValueError(f"remaining geometry set differs at {sample_index}")
        values = list(values_by_geometry.values())
        spread = max(values) - min(values)
        exact_k_samples += spread == 0.0
        spreads.append(
            {
                "sampleIndex": sample_index,
                "minimumRemaining": min(values),
                "maximumRemaining": max(values),
                "spread": spread,
            }
        )
    minimum_spread = min(spreads, key=lambda value: value["spread"])
    maximum_spread = max(spreads, key=lambda value: value["spread"])

    return {
        "integerControlMismatchedComponents": integer_mismatches,
        "halfPixelControlMismatchedComponents": half_mismatches,
        "residualEdgesByGeometry": residual_edges,
        "sameFractionalPhaseResidualEdgeIntersection": half_edge_intersection,
        "fractionalPhaseOnlyHypothesisRejected": integer_mismatches > 0,
        "fractionalPhaseInsufficientAcrossTranslations": (
            not half_edge_intersection and half_mismatches > 0
        ),
        "nonEndpointExactRemainingMatchedSampleCount": exact_k_samples,
        "nonEndpointSampleCount": len(spreads),
        "minimumCrossGeometryRemainingSpread": minimum_spread,
        "maximumCrossGeometryRemainingSpread": maximum_spread,
        "meanCrossGeometryRemainingSpread": (
            sum(value["spread"] for value in spreads) / len(spreads)
        ),
        "exactKCenterAttributionPossible": exact_k_samples == len(spreads),
        "predeclaredOutcome": "mixed-and-exact-k-confounded",
    }


def analyze(
    result_paths: Sequence[Path], *, artifact_root: Path, run_id: int
) -> dict[str, Any]:
    if run_id <= 0:
        raise ValueError("run ID must be positive")
    geometry_names: set[str] = set()
    inputs: list[dict[str, Any]] = []
    geometry_metrics: dict[str, dict[str, Any]] = {}
    remaining_by_sample: dict[int, dict[str, float]] = {
        index: {} for index in range(1, 32)
    }
    topology_counts: Counter[int] = Counter()
    state_count = 0
    runtime_components = 0
    runtime_mismatches = 0
    primary_source_components = 0
    primary_source_mismatches = 0

    for result_path in sorted(result_paths):
        result = mapping(
            json.loads(result_path.read_text(encoding="utf-8")),
            "mesh calibration result",
        )
        geometry = mapping(result.get("geometry"), "geometry")
        geometry_name = geometry.get("name")
        if (
            not isinstance(geometry_name, str)
            or geometry_name not in EXPECTED_GEOMETRIES
        ):
            raise ValueError(f"unexpected geometry: {geometry_name!r}")
        if geometry_name in geometry_names:
            raise ValueError(f"duplicate geometry: {geometry_name}")
        geometry_names.add(geometry_name)
        expected_center = EXPECTED_GEOMETRIES[geometry_name]
        observed_shape = (
            numeric(geometry.get("width"), "geometry width"),
            numeric(geometry.get("height"), "geometry height"),
            numeric(geometry.get("centerX"), "geometry center X"),
            numeric(geometry.get("centerY"), "geometry center Y"),
            numeric(geometry.get("windowWidth"), "window width"),
            numeric(geometry.get("windowHeight"), "window height"),
        )
        if observed_shape != (640.0, 640.0, *expected_center, 1024.0, 1024.0):
            raise ValueError(f"geometry specification differs for {geometry_name}")

        calibration = mapping(result.get("meshCalibration"), "mesh calibration")
        if (
            calibration.get("captureIntegrityPassed") is not True
            or calibration.get("stateCount") != 32
            or calibration.get("runtimeScaleLawExactEveryState") is not True
            or calibration.get("primaryProducerSourceQLawExactEveryState") is not True
        ):
            raise ValueError(f"capture integrity failed for {geometry_name}")

        timeline_path = result_path.parent / "transition-timeline.json"
        timeline_hash = result.get("timelineSHA256")
        if (
            not isinstance(timeline_hash, str)
            or sha256_file(timeline_path) != timeline_hash
        ):
            raise ValueError(f"timeline hash differs for {geometry_name}")
        timeline = mapping(
            json.loads(timeline_path.read_text(encoding="utf-8")),
            "transition timeline",
        )
        if mapping(timeline.get("geometry"), "timeline geometry") != geometry:
            raise ValueError(f"timeline geometry differs for {geometry_name}")

        states = sequence(result.get("states"), "validated states")
        sample_indices = tuple(
            int(mapping(state, "validated state")["sampleIndex"]) for state in states
        )
        if sample_indices != EXPECTED_SAMPLE_INDICES:
            raise ValueError(f"sample indices differ for {geometry_name}")

        geometry_topology: Counter[int] = Counter()
        candidate_components = 0
        candidate_mismatches = 0
        residuals: list[dict[str, Any]] = []
        edge_mismatches: Counter[str] = Counter()
        quad4_nonendpoint_states = 0
        for untyped_state in states:
            state = mapping(untyped_state, "validated state")
            sample_index = int(state["sampleIndex"])
            remaining = numeric(state.get("remaining"), "remaining")
            scale = numeric(state.get("runtimeScale"), "runtime scale")
            runtime_components += 1
            runtime_mismatches += scale != 1.0 - remaining / 2.0
            observed = mapping(state.get("observed"), "observed allocation")
            mesh = mapping(observed.get("producerMesh"), "producer mesh")
            vertex_count = int(mesh["vertexCount"])
            geometry_topology[vertex_count] += 1
            topology_counts[vertex_count] += 1
            primary_source_components += int(mesh["sourceScaleComponentCount"])
            primary_source_mismatches += int(mesh["sourceScaleMismatchedComponents"])
            if remaining < 1.0:
                remaining_by_sample[sample_index][geometry_name] = remaining
            if remaining >= 1.0 or vertex_count != 4:
                continue
            quad4_nonendpoint_states += 1
            carrier = allocation.predicted_carrier(geometry, remaining)
            bounds = allocation.allocation_bounds(geometry, carrier["position"])
            predicted = allocation.quad4_primary_bounds_candidate(bounds, scale=scale)
            observed_edges = allocation.primary_position_bounds(
                mesh.get("primaryVertices")
            )
            candidate_components += 4
            for edge, predicted_value, observed_value in zip(
                allocation.EDGE_NAMES, predicted, observed_edges, strict=True
            ):
                if predicted_value == observed_value:
                    continue
                candidate_mismatches += 1
                edge_mismatches[edge] += 1
                residuals.append(
                    {
                        "sampleIndex": sample_index,
                        "edge": edge,
                        "remaining": remaining,
                        "predicted": predicted_value,
                        "observed": observed_value,
                        "difference": predicted_value - observed_value,
                    }
                )

        geometry_metric = {
            "topologyStateCounts": {
                str(count): geometry_topology[count]
                for count in sorted(geometry_topology)
            },
            "quad4NonEndpointStateCount": quad4_nonendpoint_states,
            **metric(candidate_components, candidate_mismatches),
            "mismatchedEdges": {
                edge: edge_mismatches[edge]
                for edge in allocation.EDGE_NAMES
                if edge_mismatches[edge]
            },
            "residuals": residuals,
        }
        geometry_metrics[geometry_name] = geometry_metric
        state_count += len(states)
        inputs.append(
            {
                "geometry": geometry_name,
                "validatorResultArtifact": (
                    result_path.parent.name + "/" + result_path.name
                ),
                "validatorResultSHA256": sha256_file(result_path),
                "timelineArtifact": timeline_path.parent.name
                + "/"
                + timeline_path.name,
                "timelineSHA256": timeline_hash,
            }
        )

    if geometry_names != set(EXPECTED_GEOMETRIES):
        missing = sorted(set(EXPECTED_GEOMETRIES) - geometry_names)
        extra = sorted(geometry_names - set(EXPECTED_GEOMETRIES))
        raise ValueError(f"geometry set differs; missing={missing}, extra={extra}")

    candidate_components = sum(
        int(value["componentCount"]) for value in geometry_metrics.values()
    )
    candidate_mismatches = sum(
        int(value["mismatchedComponents"]) for value in geometry_metrics.values()
    )
    causal = causal_diagnostics(geometry_metrics, remaining_by_sample)
    return {
        "dynamicAllocationMeshCalibrationAnalysisSchemaVersion": 1,
        "classification": (
            "post-opening-causal-calibration-with-unmatched-realized-k; "
            "not-an-unseen-holdout"
        ),
        "runID": run_id,
        "inputs": inputs,
        "aggregate": {
            "geometryCount": len(geometry_names),
            "stateCount": state_count,
            "runtimeScale": metric(runtime_components, runtime_mismatches),
            "primaryProducerSourceQ": metric(
                primary_source_components, primary_source_mismatches
            ),
            "producerVertexCountStates": {
                str(count): topology_counts[count] for count in sorted(topology_counts)
            },
            "existingQuad4PrimaryBoundsCandidate": {
                **metric(candidate_components, candidate_mismatches),
                "byGeometry": geometry_metrics,
            },
            "causalDiagnostics": causal,
        },
        "conclusion": {
            "captureIntegrityPassed": True,
            "existingPrimaryMeshCandidateExact": candidate_mismatches == 0,
            "fractionalCenterPhaseAloneExplainsResiduals": False,
            "exactKCenterAttributionEstablished": causal[
                "exactKCenterAttributionPossible"
            ],
            "independentProducerMeshPolicyRecovered": False,
            "requiresFixedStateIntervention": True,
            "requiresNewUnseenHoldout": True,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result_paths = sorted(
        arguments.artifact_root.glob("*/dynamic-allocation-mesh-calibration.json")
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
