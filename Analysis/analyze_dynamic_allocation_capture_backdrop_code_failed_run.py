#!/usr/bin/env python3
"""Audit the failed first capture_backdrop code-capture run."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import validate_dynamic_allocation_fixed_state as fixed
import validate_dynamic_allocation_holdout as holdout
import validate_dynamic_allocation_surviving_path_threshold as surviving


CLASSIFICATION = (
    "post-opening-audit-of-failed-preregistered-capture-backdrop-code-"
    "capture; not-an-accepted-code-recovery-or-producer-mesh-policy"
)
EXPECTED_GATE_ERROR = (
    "surviving-path exact integrity gate failed: q=912/912, "
    "allocation=1596/1596, baseDecoded=0/1, baseMVP=1/1, baseIndex=1/1"
)


def pipeline_fragment(snapshot: Mapping[str, Any]) -> str | None:
    pipeline = snapshot.get("pipeline")
    if not isinstance(pipeline, Mapping):
        return None
    descriptor = pipeline.get("creationDescriptor")
    if not isinstance(descriptor, Mapping):
        return None
    fragment = descriptor.get("fragmentFunction")
    return fragment if isinstance(fragment, str) else None


def mesh_difference_fields(
    expected: Mapping[str, Any], observed: Mapping[str, Any]
) -> list[str]:
    return [
        field
        for field in sorted(set(expected) | set(observed))
        if expected.get(field) != observed.get(field)
    ]


def analyze(timeline_path: Path, *, run_id: int, head_sha: str) -> dict[str, Any]:
    if run_id <= 0 or len(head_sha) != 40:
        raise ValueError("run identity differs")
    try:
        surviving.validate(timeline_path)
    except ValueError as error:
        gate_error = str(error)
    else:
        raise ValueError("failed-run timeline unexpectedly passed")
    if gate_error != EXPECTED_GATE_ERROR:
        raise ValueError(f"failed-run rejection differs: {gate_error}")

    base_validation = holdout.validate(
        timeline_path,
        expected_geometry=surviving.EXPECTED_GEOMETRY,
        expected_sample_indices=surviving.EXPECTED_SAMPLE_INDICES,
        classification=surviving.SAMPLE31_REPEAT_CLASSIFICATION,
        allowed_geometries=frozenset({surviving.EXPECTED_GEOMETRY}),
        require_primary_source_q_exact=False,
    )
    timeline = holdout.mapping(
        json.loads(timeline_path.read_text(encoding="utf-8")), "transition timeline"
    )
    uniforms = holdout.mapping(
        timeline.get("dynamicBackgroundUniforms"), "dynamic background uniforms"
    )
    evidence = holdout.mapping(
        uniforms.get("pathIsolationInterventions"), "path-isolation evidence"
    )
    records = [
        holdout.mapping(value, "path-isolation record")
        for value in fixed.sequence(evidence.get("records"), "path-isolation records")
    ]
    if evidence.get("schemaVersion") != 4 or len(records) != 114:
        raise ValueError("failed-run sample-31 matrix differs")
    first = records[0]
    scale, _ = holdout.captured_scale(first)
    observed = holdout.observed_policy(first, scale=scale)
    normal_states = {
        int(holdout.mapping(value, "normal state")["sampleIndex"]): holdout.mapping(
            value, "normal state"
        )
        for value in fixed.sequence(base_validation.get("states"), "normal states")
    }
    normal = holdout.mapping(normal_states[31].get("observed"), "normal observed")
    normal_mesh = holdout.mapping(normal.get("producerMesh"), "normal mesh")
    observed_mesh = holdout.mapping(observed.get("producerMesh"), "observed mesh")

    render = holdout.mapping(first.get("render"), "first intervention render")
    buffers = holdout.mapping(
        render.get("metalBufferSnapshots"), "first intervention buffers"
    )
    call_site_snapshots = [
        snapshot
        for value in fixed.sequence(buffers.get("snapshots"), "buffer snapshots")
        if "producerGeometryCallSite"
        in (snapshot := holdout.mapping(value, "buffer snapshot"))
    ]
    if len(call_site_snapshots) != 1:
        raise ValueError("failed-run call-site snapshot is not unique")
    snapshot = call_site_snapshots[0]
    call_site = holdout.mapping(
        snapshot.get("producerGeometryCallSite"), "producer call site"
    )
    frames = [
        holdout.mapping(value, "producer call-site frame")
        for value in fixed.sequence(call_site.get("frames"), "producer frames")
    ]
    symbols = [frame.get("symbol") for frame in frames]
    contents_symbol = (
        "_ZNK2CA3OGL16ContentsGeometry15fill_and_unbindERNS0_7ContextEPNS0_5ImageE"
    )
    if (
        call_site.get("schemaVersion") != 5
        or call_site.get("captureBackdropCodeCaptureCount") != 0
        or surviving.CAPTURE_BACKDROP_SYMBOL in symbols
        or contents_symbol not in symbols
    ):
        raise ValueError("failed-run wrong-stack diagnosis differs")

    differing_fields = mesh_difference_fields(normal_mesh, observed_mesh)
    expected_difference_fields = [
        "fragmentFunction",
        "mvpPayloadSHA256",
        "vertexDrawConsumedPayloadSHA256",
        "vertexPayloadSHA256",
    ]
    primary_vertices_exact = normal_mesh.get("primaryVertices") == observed_mesh.get(
        "primaryVertices"
    )
    if differing_fields != expected_difference_fields or not primary_vertices_exact:
        raise ValueError("failed-run base mesh differences differ")
    return {
        "dynamicAllocationCaptureBackdropCodeFailedRunAnalysisSchemaVersion": 1,
        "classification": CLASSIFICATION,
        "runID": run_id,
        "headSHA": head_sha,
        "inputTimelineArtifact": timeline_path.parent.name + "/" + timeline_path.name,
        "inputTimelineSHA256": holdout.sha256_file(timeline_path),
        "frozenGateError": gate_error,
        "aggregate": {
            "recordCount": len(records),
            "preIntegrityValidationReached": True,
            "primarySourceQ": {
                "componentCount": 912,
                "mismatchedComponents": 0,
                "exact": True,
            },
            "allocationInvariants": {
                "componentCount": 1596,
                "mismatchedComponents": 0,
                "exact": True,
            },
            "baseDrawConsumedHashes": {
                "mvpExact": True,
                "indexExact": True,
                "vertexExact": False,
            },
            "basePrimaryVerticesExact": primary_vertices_exact,
            "normalFragmentFunction": normal_mesh.get("fragmentFunction"),
            "firstInterventionFragmentFunction": observed_mesh.get("fragmentFunction"),
            "baseMeshDifferenceFields": differing_fields,
            "latchedSnapshotFragmentFunction": pipeline_fragment(snapshot),
            "latchedCallSiteSchemaVersion": call_site.get("schemaVersion"),
            "latchedStackFrameCount": len(frames),
            "latchedStackSymbols": symbols,
            "captureBackdropCodeCaptureCount": call_site.get(
                "captureBackdropCodeCaptureCount"
            ),
            "captureBackdropDecisionDirectCallCount": call_site.get(
                "captureBackdropDecisionDirectCallCount"
            ),
            "captureBackdropDirectCallTargetCodeCaptureCount": call_site.get(
                "captureBackdropDirectCallTargetCodeCaptureCount"
            ),
        },
        "conclusion": {
            "frozenCodeCaptureGatePassed": False,
            "firstMatchingA2XBindingWasBackdropProducer": False,
            "latchedStackWasContentsGeometry": True,
            "captureBackdropBytesRecovered": False,
            "sample31MatrixRemainsExtractable": True,
            "primaryGeometryChangedByFailedDiagnostic": False,
            "requiresLiveStackQualifiedRetry": True,
            "producerMeshPolicyRecovered": False,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = analyze(
        arguments.timeline, run_id=arguments.run_id, head_sha=arguments.head_sha
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
