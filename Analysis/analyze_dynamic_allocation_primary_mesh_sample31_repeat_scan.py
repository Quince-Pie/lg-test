#!/usr/bin/env python3
"""Open the preregistered sample-31 unit scan and same-process repeats."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_dynamic_allocation_holdout as allocation
import analyze_dynamic_allocation_primary_mesh_normalized_response as normalized
import analyze_dynamic_allocation_surviving_path_threshold as response_analysis
import analyze_dynamic_allocation_within_run_repeat_determinism as repeat_audit
import validate_dynamic_allocation_fixed_state as fixed
import validate_dynamic_allocation_holdout as holdout
import validate_dynamic_allocation_surviving_path_threshold as surviving


CLASSIFICATION = (
    "post-opening-analysis-of-preregistered-sample31-unit-threshold-and-"
    "same-process-repeat-scan; not-a-complete-producer-mesh-policy"
)


def all_equal(values: Sequence[Any]) -> bool:
    if not values:
        raise ValueError("exact equivalence group is empty")
    return all(value == values[0] for value in values[1:])


def intervention_axis(record: Mapping[str, Any]) -> str:
    name = record.get("interventionName")
    if not isinstance(name, str):
        raise ValueError("sample-31 intervention name is missing")
    has_x = "-position-x-" in name
    has_y = "-position-y-" in name
    if has_x == has_y:
        raise ValueError("sample-31 intervention axis is ambiguous")
    return "x" if has_x else "y"


def layer_at_path(states: Any, path: tuple[int, ...]) -> Mapping[str, Any]:
    matches = []
    for value in fixed.sequence(states, "live layer states"):
        state = holdout.mapping(value, "live layer state")
        state_path = tuple(
            int(component)
            for component in fixed.sequence(state.get("path"), "live layer path")
        )
        if state_path == path:
            matches.append(state)
    if len(matches) != 1:
        raise ValueError(f"live layer path {path} is not unique")
    return matches[0]


def target_center(raw_record: Mapping[str, Any]) -> tuple[float, float]:
    before = holdout.mapping(
        raw_record.get("liveRenderBoundaryBefore"), "live boundary before"
    )
    target = layer_at_path(before.get("layerStates"), surviving.POSITION_PATH)
    position = tuple(
        holdout.numeric(value, "target position")
        for value in fixed.sequence(target.get("position"), "target position")
    )
    if len(position) != 2:
        raise ValueError("deepest SDF position is not a point")
    radius = holdout.numeric(target.get("cornerRadius"), "target radius")
    return (position[0] + radius, position[1] + radius)


def primary_edges(observed: Mapping[str, Any]) -> tuple[float, ...]:
    mesh = holdout.mapping(observed.get("producerMesh"), "producer mesh")
    return tuple(allocation.primary_position_bounds(mesh.get("primaryVertices")))


def edge_delta(
    reference: Mapping[str, Any], observed: Mapping[str, Any]
) -> tuple[float, ...]:
    return tuple(
        actual - expected
        for actual, expected in zip(
            primary_edges(observed), primary_edges(reference), strict=True
        )
    )


def response_runs(
    values: Sequence[tuple[int, tuple[float, ...]]],
) -> list[dict[str, Any]]:
    return response_analysis.response_runs(values)


def transition_brackets(runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return response_analysis.transition_brackets(runs)


def repeat_keys() -> tuple[tuple[str, int], ...]:
    return tuple(
        [("base", 0)]
        + [("x", value) for value in surviving.SAMPLE31_REPEAT_X_VALUES]
        + [("y", value) for value in surviving.SAMPLE31_REPEAT_Y_VALUES]
    )


def analyze(timeline_path: Path, result_path: Path, *, run_id: int) -> dict[str, Any]:
    if run_id <= 0:
        raise ValueError("run ID must be positive")
    result = holdout.mapping(
        json.loads(result_path.read_text(encoding="utf-8")), "validator result"
    )
    conclusion = holdout.mapping(result.get("conclusion"), "validator conclusion")
    if (
        result.get("dynamicAllocationSurvivingPathThresholdResultSchemaVersion") != 3
        or result.get("captureEvidenceSchemaVersion") != 4
        or result.get("classification") != surviving.SAMPLE31_REPEAT_CLASSIFICATION
        or result.get("timelineSHA256") != holdout.sha256_file(timeline_path)
        or conclusion.get("captureIntegrityPassed") is not True
        or conclusion.get("causalCalibrationOnly") is not True
        or conclusion.get("productionShaderAuthorized") is not False
    ):
        raise ValueError("sample-31 validator result is not accepted calibration")

    timeline = holdout.mapping(
        json.loads(timeline_path.read_text(encoding="utf-8")), "transition timeline"
    )
    uniforms = holdout.mapping(
        timeline.get("dynamicBackgroundUniforms"), "dynamic background uniforms"
    )
    evidence = holdout.mapping(
        uniforms.get("pathIsolationInterventions"), "sample-31 repeat evidence"
    )
    raw_records = [
        holdout.mapping(value, "raw sample-31 record")
        for value in fixed.sequence(evidence.get("records"), "raw sample-31 records")
    ]
    validated_records = [
        holdout.mapping(value, "validated sample-31 record")
        for value in fixed.sequence(result.get("records"), "validated records")
    ]
    expected_count = len(surviving.sample31_repeat_interventions(31))
    if (
        evidence.get("schemaVersion") != 4
        or len(raw_records) != expected_count
        or len(validated_records) != expected_count
    ):
        raise ValueError("sample-31 repeat record count differs")
    raw_by_index = {int(record["recordIndex"]): record for record in raw_records}
    validated_by_index = {
        int(record["recordIndex"]): record for record in validated_records
    }
    expected_indices = set(range(expected_count))
    if (
        set(raw_by_index) != expected_indices
        or set(validated_by_index) != expected_indices
    ):
        raise ValueError("sample-31 repeat record indices differ")

    controls = [
        record for record in validated_records if record.get("phase") == "control"
    ]
    if len(controls) != 1:
        raise ValueError("sample-31 initial control is not unique")
    base = controls[0]
    base_observed = holdout.mapping(base.get("observed"), "base observed policy")
    base_raw = raw_by_index[int(base["recordIndex"])]
    base_center = target_center(base_raw)
    base_pixel_details = tuple(
        normalized.pixel_center(value, maximum_residual_ulps=1.0)
        for value in base_center
    )
    base_pixel_center = tuple(value[0] for value in base_pixel_details)

    scans: dict[str, list[tuple[int, tuple[float, ...]]]] = {"x": [], "y": []}
    pixel_scans: dict[str, list[tuple[int, tuple[float, ...]]]] = {
        "x": [],
        "y": [],
    }
    unit_by_key: dict[tuple[str, int], Mapping[str, Any]] = {}
    repeat_by_key: dict[tuple[str, int], Mapping[str, Any]] = {}
    repeat_base: Mapping[str, Any] | None = None
    record_responses: list[dict[str, Any]] = []
    edge_components = 0
    changed_components = 0
    changed_records = 0
    signed_counts: Counter[tuple[str, float]] = Counter()
    maximum_center_residual_ulps = max(abs(value[2]) for value in base_pixel_details)

    for record in validated_records:
        record_index = int(record["recordIndex"])
        raw = raw_by_index[record_index]
        observed = holdout.mapping(record.get("observed"), "observed policy")
        response = edge_delta(base_observed, observed)
        edge_components += len(response)
        changed = sum(value != 0 for value in response)
        changed_components += changed
        changed_records += changed > 0
        for name, value in zip(allocation.EDGE_NAMES, response, strict=True):
            if value:
                signed_counts[(name, value)] += 1

        translation = tuple(
            int(value)
            for value in fixed.sequence(record.get("translation"), "translation")
        )
        if len(translation) != 2:
            raise ValueError("sample-31 translation is not a point")
        center = target_center(raw)
        pixel_details = tuple(
            normalized.pixel_center(value, maximum_residual_ulps=1.0)
            for value in center
        )
        pixel_center = tuple(value[0] for value in pixel_details)
        maximum_center_residual_ulps = max(
            maximum_center_residual_ulps,
            *(abs(value[2]) for value in pixel_details),
        )
        expected_pixel_center = (
            base_pixel_center[0] + translation[0],
            base_pixel_center[1] + translation[1],
        )
        if pixel_center != expected_pixel_center:
            raise ValueError("sample-31 target pixel-center translation differs")

        phase = str(record["phase"])
        item: dict[str, Any] = {
            "recordIndex": record_index,
            "interventionName": record["interventionName"],
            "phase": phase,
            "translation": list(translation),
            "targetCenter": list(center),
            "targetPixelCenter": list(pixel_center),
            "primaryEdgeResponse": list(response),
        }
        if (
            phase in {"sample31-unit-scan", "repeat-control"}
            and record.get("mutation") == "position"
        ):
            axis = intervention_axis(record)
            axis_index = 0 if axis == "x" else 1
            other_index = 1 - axis_index
            value = translation[axis_index]
            if translation[other_index] != 0:
                raise ValueError("sample-31 intervention is not one-axis")
            item["axis"] = axis
            if phase == "sample31-unit-scan":
                scans[axis].append((value, response))
                pixel_scans[axis].append((pixel_center[axis_index], response))
                if (axis, value) in unit_by_key:
                    raise ValueError("sample-31 unit-scan key is duplicated")
                unit_by_key[(axis, value)] = record
            else:
                if (axis, value) in repeat_by_key:
                    raise ValueError("sample-31 repeat key is duplicated")
                repeat_by_key[(axis, value)] = record
        elif phase == "repeat-control" and record.get("mutation") == "base":
            if repeat_base is not None:
                raise ValueError("sample-31 repeat base is duplicated")
            repeat_base = record
        elif phase != "control":
            raise ValueError(f"unexpected sample-31 phase: {phase}")
        record_responses.append(item)

    scan_groups: list[dict[str, Any]] = []
    for axis_index, axis in enumerate(("x", "y")):
        expected_values = (
            surviving.SAMPLE31_UNIT_X_VALUES
            if axis == "x"
            else surviving.SAMPLE31_UNIT_Y_VALUES
        )
        if tuple(value for value, _ in scans[axis]) != expected_values:
            raise ValueError(f"sample-31 {axis} unit-scan values differ")
        translation_runs = response_runs(scans[axis])
        pixel_runs = response_runs(pixel_scans[axis])
        translation_brackets = transition_brackets(translation_runs)
        pixel_brackets = transition_brackets(pixel_runs)
        if not all(
            int(bracket["upperObservedValue"]) - int(bracket["lowerObservedValue"]) == 1
            for bracket in translation_brackets
        ):
            raise ValueError("sample-31 response transition is not unit-bracketed")
        scan_groups.append(
            {
                "sampleIndex": 31,
                "mutationPath": list(surviving.POSITION_PATH),
                "mutation": "position",
                "phase": "sample31-unit-scan",
                "axis": axis,
                "sampledValueCount": len(scans[axis]),
                "translationMinimum": min(expected_values),
                "translationMaximum": max(expected_values),
                "targetPixelCenterMinimum": min(
                    value for value, _ in pixel_scans[axis]
                ),
                "targetPixelCenterMaximum": max(
                    value for value, _ in pixel_scans[axis]
                ),
                "fixedOtherAxisPixelCenter": base_pixel_center[1 - axis_index],
                "unitStepCoverage": True,
                "distinctResponseCount": len({response for _, response in scans[axis]}),
                "translationRuns": translation_runs,
                "translationTransitionBrackets": translation_brackets,
                "targetPixelCenterRuns": pixel_runs,
                "targetPixelCenterTransitionBrackets": pixel_brackets,
            }
        )

    if repeat_base is None:
        raise ValueError("sample-31 repeat base is missing")
    base_members = [
        base,
        unit_by_key[("x", 0)],
        unit_by_key[("y", 0)],
        repeat_base,
    ]
    repeat_members: dict[tuple[str, int], list[Mapping[str, Any]]] = {
        ("base", 0): base_members
    }
    for axis, value in repeat_keys()[1:]:
        repeat_members[(axis, value)] = [
            unit_by_key[(axis, value)],
            repeat_by_key[(axis, value)],
        ]

    repeat_groups: list[dict[str, Any]] = []
    for key in repeat_keys():
        members = repeat_members[key]
        raw_members = [raw_by_index[int(member["recordIndex"])] for member in members]
        observed_members = [
            holdout.mapping(member.get("observed"), "repeat observed policy")
            for member in members
        ]
        mesh_members = [
            holdout.mapping(observed.get("producerMesh"), "repeat producer mesh")
            for observed in observed_members
        ]
        before_members = [
            holdout.mapping(
                raw.get("liveRenderBoundaryBefore"), "repeat live boundary before"
            )
            for raw in raw_members
        ]
        after_members = [
            holdout.mapping(
                raw.get("liveRenderBoundaryAfter"), "repeat live boundary after"
            )
            for raw in raw_members
        ]
        scalar_exact = all_equal(
            [
                (member.get("remaining"), member.get("runtimeScale"))
                for member in members
            ]
        )
        requested_exact = all_equal(
            [
                repeat_audit.projection(raw, repeat_audit.RAW_REQUEST_FIELDS)
                for raw in raw_members
            ]
        )
        live_before_exact = all_equal(
            [
                repeat_audit.projection(boundary, repeat_audit.LIVE_BOUNDARY_FIELDS)
                for boundary in before_members
            ]
        )
        live_after_exact = all_equal(
            [
                repeat_audit.projection(boundary, repeat_audit.LIVE_BOUNDARY_FIELDS)
                for boundary in after_members
            ]
        )
        each_render_stable = all(
            raw.get("liveLayerStatesStableAcrossRender") is True
            and raw.get("liveFilterInputsBeforeUnchanged") is True
            and raw.get("liveFilterInputsAfterUnchanged") is True
            and raw.get("filterInputValuesUnchanged") is True
            and raw.get("originalProducerInput") is True
            and raw.get("producerCopyBaseObserved") is True
            for raw in raw_members
        )
        allocation_exact = all_equal(
            [
                repeat_audit.projection(observed, repeat_audit.ALLOCATION_FIELDS)
                for observed in observed_members
            ]
        )
        mesh_policy_exact = all_equal(
            [
                repeat_audit.projection(mesh, repeat_audit.MESH_POLICY_FIELDS)
                for mesh in mesh_members
            ]
        )
        draw_consumed_exact = all_equal(
            [
                repeat_audit.projection(mesh, repeat_audit.DRAW_CONSUMED_FIELDS)
                for mesh in mesh_members
            ]
        )
        primary_edges_exact = all_equal(
            [primary_edges(observed) for observed in observed_members]
        )
        full_snapshot_hash_exact = {
            field: all_equal([mesh.get(field) for mesh in mesh_members])
            for field in repeat_audit.FULL_SNAPSHOT_HASH_FIELDS
        }
        exact = (
            scalar_exact
            and requested_exact
            and live_before_exact
            and live_after_exact
            and each_render_stable
            and allocation_exact
            and mesh_policy_exact
            and draw_consumed_exact
            and primary_edges_exact
        )
        indices = [int(member["recordIndex"]) for member in members]
        repeat_groups.append(
            {
                "key": {"axis": key[0], "translation": key[1]},
                "recordIndices": indices,
                "recordIndexSeparation": max(indices) - min(indices),
                "phases": [str(member["phase"]) for member in members],
                "sourceStateScalarsExact": scalar_exact,
                "requestedStateExact": requested_exact,
                "liveStateBeforeExact": live_before_exact,
                "liveStateAfterExact": live_after_exact,
                "eachRenderStateStable": each_render_stable,
                "allocationPolicyExact": allocation_exact,
                "primaryEdges": list(primary_edges(observed_members[0])),
                "primaryEdgesExact": primary_edges_exact,
                "decodedMeshPolicyExact": mesh_policy_exact,
                "drawConsumedPayloadsExact": draw_consumed_exact,
                "fullSnapshotHashesExact": full_snapshot_hash_exact,
                "decodedDrawConsumedPolicyExact": exact,
            }
        )

    exact_repeat_count = sum(
        group["decodedDrawConsumedPolicyExact"] is True for group in repeat_groups
    )
    result_aggregate = holdout.mapping(result.get("aggregate"), "result aggregate")
    call_site = holdout.mapping(
        result_aggregate.get("producerGeometryCallSite"),
        "producer geometry call-site summary",
    )
    return {
        "dynamicAllocationPrimaryMeshSample31RepeatScanAnalysisSchemaVersion": 1,
        "classification": CLASSIFICATION,
        "runID": run_id,
        "inputValidatorResultArtifact": result_path.parent.name
        + "/"
        + result_path.name,
        "inputValidatorResultSHA256": holdout.sha256_file(result_path),
        "inputTimelineArtifact": timeline_path.parent.name + "/" + timeline_path.name,
        "inputTimelineSHA256": holdout.sha256_file(timeline_path),
        "sourceTargetCenter": list(base_center),
        "sourceTargetPixelCenter": list(base_pixel_center),
        "sourceTargetCenterResidual": [value[1] for value in base_pixel_details],
        "sourceTargetCenterResidualULPs": [value[2] for value in base_pixel_details],
        "aggregate": {
            "recordCount": len(validated_records),
            "edgeComponentCount": edge_components,
            "changedEdgeComponentCount": changed_components,
            "changedRecordCount": changed_records,
            "signedEdgeDeltaCounts": {
                f"{name}:{value:+g}": count
                for (name, value), count in sorted(signed_counts.items())
            },
            "scanGroupCount": len(scan_groups),
            "unitScanRecordCount": sum(len(values) for values in scans.values()),
            "repeatEquivalenceGroupCount": len(repeat_groups),
            "exactDecodedDrawConsumedRepeatGroupCount": exact_repeat_count,
            "maximumRepeatRecordIndexSeparation": max(
                int(group["recordIndexSeparation"]) for group in repeat_groups
            ),
            "maximumTargetCenterResidualULPs": maximum_center_residual_ulps,
            "producerGeometryCallSite": dict(call_site),
            "fullSnapshotHashFieldsExcludedFromDeterminismGate": list(
                repeat_audit.FULL_SNAPSHOT_HASH_FIELDS
            ),
        },
        "scanGroups": scan_groups,
        "repeatEquivalenceGroups": repeat_groups,
        "recordResponses": record_responses,
        "conclusion": {
            "sample31UnitThresholdsOpened": True,
            "everyReportedTransitionBracketHasUnitWidth": True,
            "sample31SameStateResponseDeterministicAcrossRecordedOrder": (
                exact_repeat_count == len(repeat_groups)
            ),
            "comparisonRestrictedToDecodedPolicyAndDrawConsumedBytes": True,
            "unusedSnapshotTailBytesExcluded": True,
            "independentProducerMeshPolicyRecovered": False,
            "requiresUnseenGeometryTransfer": True,
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
    result = analyze(arguments.timeline, arguments.result, run_id=arguments.run_id)
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
        print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
