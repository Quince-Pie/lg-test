#!/usr/bin/env python3
"""Audit repeated same-state allocation probes inside one accepted Apple run."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import analyze_dynamic_allocation_holdout as allocation
import validate_dynamic_allocation_holdout as holdout
import validate_dynamic_allocation_surviving_path_threshold as surviving


CLASSIFICATION = (
    "post-opening-within-run-repeat-determinism-audit-of-preregistered-"
    "sample-25-controls; not-an-exact-policy-recovery"
)

EXPECTED_REPEAT_GROUPS = {
    (25, (-90, 0)): (1, 9),
    (25, (90, 0)): (2, 29),
    (25, (0, -134)): (3, 38),
    (25, (0, 134)): (4, 62),
}

ALLOCATION_FIELDS = (
    "cropOrigin",
    "textureCoordinateClamp",
    "producerExtent",
    "destinationExtent",
    "copyOffset",
    "effectiveOrigin",
    "producerCropMaximumIntegralResidual",
)

MESH_POLICY_FIELDS = (
    "fragmentFunction",
    "inputTexture",
    "viewport",
    "scissor",
    "vertexCount",
    "indexCount",
    "primaryVertices",
    "quadBounds",
    "sourceScaleComponentCount",
    "sourceScaleMismatchedComponents",
    "allSourceScaleComponentCount",
    "allSourceScaleMismatchedComponents",
)

DRAW_CONSUMED_FIELDS = (
    "vertexDrawConsumedByteCount",
    "vertexDrawConsumedPayloadSHA256",
    "mvpDrawConsumedByteCount",
    "mvpDrawConsumedPayloadSHA256",
    "indexDrawConsumedByteCount",
    "indexDrawConsumedPayloadSHA256",
)

FULL_SNAPSHOT_HASH_FIELDS = (
    "vertexPayloadSHA256",
    "mvpPayloadSHA256",
)

RAW_REQUEST_FIELDS = (
    "sourceLayerStatesSHA256",
    "requestedLayerStatesSHA256",
    "sourceFilterInputValuesSHA256",
    "replayedFilterInputValuesSHA256",
    "requestedLayerStates",
    "capturedLayerStates",
)

LIVE_BOUNDARY_FIELDS = (
    "schemaVersion",
    "executed",
    "layerStatesSHA256",
    "layerStates",
    "backgroundFilterPath",
    "backgroundFilterIndex",
    "backgroundFilterInputValuesSHA256",
    "backgroundFilterInputValues",
)


def projection(value: Mapping[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    missing = [field for field in fields if field not in value]
    if missing:
        raise ValueError(f"repeat projection fields are missing: {missing}")
    return {field: value[field] for field in fields}


def primary_edges(observed: Mapping[str, Any]) -> list[float]:
    mesh = holdout.mapping(observed.get("producerMesh"), "producer mesh")
    return allocation.primary_position_bounds(mesh.get("primaryVertices"))


def analyze(
    timeline_path: Path, result_path: Path, *, run_id: int
) -> dict[str, Any]:
    if run_id <= 0:
        raise ValueError("run ID must be positive")
    result = holdout.mapping(
        json.loads(result_path.read_text(encoding="utf-8")), "validator result"
    )
    conclusion = holdout.mapping(result.get("conclusion"), "validator conclusion")
    if (
        result.get("dynamicAllocationSurvivingPathThresholdResultSchemaVersion")
        != 1
        or result.get("classification") != surviving.CLASSIFICATION
        or conclusion.get("captureIntegrityPassed") is not True
        or conclusion.get("causalCalibrationOnly") is not True
        or conclusion.get("productionShaderAuthorized") is not False
        or result.get("timelineSHA256") != holdout.sha256_file(timeline_path)
    ):
        raise ValueError("surviving-path validator result is not accepted calibration")

    timeline = holdout.mapping(
        json.loads(timeline_path.read_text(encoding="utf-8")), "transition timeline"
    )
    uniforms = holdout.mapping(
        timeline.get("dynamicBackgroundUniforms"), "dynamic background uniforms"
    )
    evidence = holdout.mapping(
        uniforms.get("pathIsolationInterventions"), "path-isolation evidence"
    )
    raw_values = evidence.get("records")
    if evidence.get("schemaVersion") != 2 or not isinstance(raw_values, list):
        raise ValueError("path-isolation capture evidence differs")
    raw_records = [holdout.mapping(value, "raw record") for value in raw_values]
    raw_by_index = {int(record["recordIndex"]): record for record in raw_records}
    if len(raw_by_index) != 72:
        raise ValueError("raw record indices differ")

    validated_values = result.get("records")
    if not isinstance(validated_values, list) or len(validated_values) != 72:
        raise ValueError("surviving-path validated record count differs")
    records = [holdout.mapping(value, "validated record") for value in validated_values]
    records_by_index = {int(record["recordIndex"]): record for record in records}
    if len(records_by_index) != len(records):
        raise ValueError("validated record indices are not unique")

    groups: list[dict[str, Any]] = []
    for (sample, translation), indices in EXPECTED_REPEAT_GROUPS.items():
        if any(index not in records_by_index for index in indices):
            raise ValueError(f"repeat records are missing for {sample}/{translation}")
        first, second = (records_by_index[index] for index in indices)
        first_raw, second_raw = (raw_by_index[index] for index in indices)
        expected_phases = ("path-isolation", "dense-threshold")
        for record, phase in zip((first, second), expected_phases, strict=True):
            observed_translation = tuple(
                int(value)
                for value in allocation.sequence(
                    record.get("translation"), "translation"
                )
            )
            if (
                int(record["sampleIndex"]) != sample
                or observed_translation != translation
                or record.get("phase") != phase
                or record.get("mutation") != "position"
                or record.get("mutationPath") != list(surviving.POSITION_PATH)
            ):
                raise ValueError(f"repeat identity differs at record {record['recordIndex']}")

        request_state_exact = projection(
            first_raw, RAW_REQUEST_FIELDS
        ) == projection(second_raw, RAW_REQUEST_FIELDS)
        first_before = holdout.mapping(
            first_raw.get("liveRenderBoundaryBefore"), "first live boundary before"
        )
        second_before = holdout.mapping(
            second_raw.get("liveRenderBoundaryBefore"), "second live boundary before"
        )
        first_after = holdout.mapping(
            first_raw.get("liveRenderBoundaryAfter"), "first live boundary after"
        )
        second_after = holdout.mapping(
            second_raw.get("liveRenderBoundaryAfter"), "second live boundary after"
        )
        live_before_exact = projection(
            first_before, LIVE_BOUNDARY_FIELDS
        ) == projection(second_before, LIVE_BOUNDARY_FIELDS)
        live_after_exact = projection(
            first_after, LIVE_BOUNDARY_FIELDS
        ) == projection(second_after, LIVE_BOUNDARY_FIELDS)
        each_render_stable = all(
            raw.get("liveLayerStatesStableAcrossRender") is True
            and raw.get("liveFilterInputsBeforeUnchanged") is True
            and raw.get("liveFilterInputsAfterUnchanged") is True
            and raw.get("filterInputValuesUnchanged") is True
            and raw.get("originalProducerInput") is True
            and raw.get("producerCopyBaseObserved") is True
            for raw in (first_raw, second_raw)
        )

        state_exact = (
            first.get("remaining") == second.get("remaining")
            and first.get("runtimeScale") == second.get("runtimeScale")
        )
        first_observed = holdout.mapping(first.get("observed"), "first policy")
        second_observed = holdout.mapping(second.get("observed"), "second policy")
        first_mesh = holdout.mapping(first_observed.get("producerMesh"), "first mesh")
        second_mesh = holdout.mapping(second_observed.get("producerMesh"), "second mesh")

        allocation_exact = projection(
            first_observed, ALLOCATION_FIELDS
        ) == projection(second_observed, ALLOCATION_FIELDS)
        mesh_policy_exact = projection(first_mesh, MESH_POLICY_FIELDS) == projection(
            second_mesh, MESH_POLICY_FIELDS
        )
        draw_consumed_exact = projection(
            first_mesh, DRAW_CONSUMED_FIELDS
        ) == projection(second_mesh, DRAW_CONSUMED_FIELDS)
        primary_edges_exact = primary_edges(first_observed) == primary_edges(
            second_observed
        )
        full_snapshot_hash_exact = {
            field: first_mesh.get(field) == second_mesh.get(field)
            for field in FULL_SNAPSHOT_HASH_FIELDS
        }
        decoded_policy_exact = (
            state_exact
            and request_state_exact
            and live_before_exact
            and live_after_exact
            and each_render_stable
            and allocation_exact
            and mesh_policy_exact
            and draw_consumed_exact
            and primary_edges_exact
        )
        groups.append(
            {
                "sampleIndex": sample,
                "translation": list(translation),
                "recordIndices": list(indices),
                "recordIndexSeparation": indices[1] - indices[0],
                "phases": list(expected_phases),
                "remaining": first["remaining"],
                "runtimeScale": first["runtimeScale"],
                "sourceStateScalarsExact": state_exact,
                "requestedStateExact": request_state_exact,
                "liveStateBeforeExact": live_before_exact,
                "liveStateAfterExact": live_after_exact,
                "eachRenderStateStable": each_render_stable,
                "allocationPolicyExact": allocation_exact,
                "primaryEdges": primary_edges(first_observed),
                "primaryEdgesExact": primary_edges_exact,
                "decodedMeshPolicyExact": mesh_policy_exact,
                "drawConsumedPayloadsExact": draw_consumed_exact,
                "fullSnapshotHashesExact": full_snapshot_hash_exact,
                "decodedDrawConsumedPolicyExact": decoded_policy_exact,
            }
        )

    exact_group_count = sum(
        group["decodedDrawConsumedPolicyExact"] is True for group in groups
    )
    maximum_separation = max(int(group["recordIndexSeparation"]) for group in groups)
    return {
        "dynamicAllocationWithinRunRepeatDeterminismAnalysisSchemaVersion": 1,
        "classification": CLASSIFICATION,
        "runID": run_id,
        "inputValidatorResultArtifact": result_path.parent.name
        + "/"
        + result_path.name,
        "inputValidatorResultSHA256": holdout.sha256_file(result_path),
        "inputTimelineArtifact": timeline_path.parent.name
        + "/"
        + timeline_path.name,
        "inputTimelineSHA256": holdout.sha256_file(timeline_path),
        "aggregate": {
            "repeatGroupCount": len(groups),
            "exactDecodedDrawConsumedGroupCount": exact_group_count,
            "maximumRecordIndexSeparation": maximum_separation,
            "sampleIndices": sorted({int(group["sampleIndex"]) for group in groups}),
            "fullSnapshotHashFieldsExcludedFromDeterminismGate": list(
                FULL_SNAPSHOT_HASH_FIELDS
            ),
        },
        "repeatGroups": groups,
        "conclusion": {
            "sample25SameStateResponseDeterministicAcrossRecordedOrder": (
                exact_group_count == len(groups)
            ),
            "comparisonRestrictedToDecodedPolicyAndDrawConsumedBytes": True,
            "requestedAndLiveStatesExactWithinEveryRepeatPair": all(
                group["requestedStateExact"] is True
                and group["liveStateBeforeExact"] is True
                and group["liveStateAfterExact"] is True
                for group in groups
            ),
            "unusedSnapshotTailBytesExcluded": True,
            "sample31DeterminismEstablished": False,
            "independentProducerMeshPolicyRecovered": False,
            "requiresExactStateAndUnseenGeometryTransfer": True,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("result", type=Path)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = analyze(
        arguments.timeline, arguments.result, run_id=arguments.run_id
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
