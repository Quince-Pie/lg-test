#!/usr/bin/env python3
"""Validate live-read-back single-path producer-allocation interventions."""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_dynamic_allocation_fixed_state as fixed
import validate_dynamic_allocation_holdout as holdout


EXPECTED_GEOMETRY = "circle-640-center"
EXPECTED_SAMPLE_INDICES = tuple(range(1, 33))
EXPECTED_SOURCE_SAMPLE_INDICES = (25, 31)
BOUNDS_PATHS = (
    (1, 0, 1),
    (1, 0, 1, 0),
    (1, 0, 1, 0, 0),
    (1, 0, 1, 1),
    (1, 0, 1, 1, 0),
    (1, 0, 1, 1, 0, 0),
    (1, 0, 1, 2),
)
POSITION_PATH = (1, 0, 1, 0, 0, 0, 0)
STRONG_DELTAS = (
    ("x-negative-90", (-90, 0)),
    ("x-positive-90", (90, 0)),
    ("y-negative-134", (0, -134)),
    ("y-positive-134", (0, 134)),
)
DENSE_X_VALUES = (
    -128,
    -96,
    -92,
    -91,
    -90,
    -89,
    -88,
    -64,
    -32,
    -16,
    -8,
    -4,
    -2,
    -1,
    1,
    2,
    4,
    8,
    16,
    32,
    64,
    80,
    88,
    89,
    90,
    91,
    92,
    96,
    128,
)
DENSE_Y_VALUES = (
    -160,
    -144,
    -136,
    -135,
    -134,
    -133,
    -132,
    -128,
    -96,
    -64,
    -32,
    -16,
    -8,
    -4,
    -2,
    -1,
    1,
    2,
    4,
    8,
    16,
    32,
    64,
    96,
    120,
    128,
    132,
    133,
    134,
    135,
    136,
    144,
    160,
)
MUTATIONS = ("bounds-origin", "position", "bounds-origin-and-position")
CLASSIFICATION = (
    "preregistered-live-read-back-single-path-producer-allocation-calibration"
)
BUFFER_RETENTION_POLICY = "index-all-compute-0-vertex-1-or-2"


def path_name(path: Sequence[int]) -> str:
    return "-".join(str(value) for value in path)


def signed_name(value: int) -> str:
    return ("negative" if value < 0 else "positive") + f"-{abs(value)}"


def expected_interventions(sample_index: int) -> list[dict[str, Any]]:
    if sample_index not in EXPECTED_SOURCE_SAMPLE_INDICES:
        raise ValueError(f"unexpected path-isolation sample: {sample_index}")
    result: list[dict[str, Any]] = [
        {
            "name": "base",
            "phase": "control",
            "path": (),
            "mutation": "base",
            "delta": (0, 0),
        }
    ]
    for path in BOUNDS_PATHS:
        identifier = path_name(path)
        for mutation in MUTATIONS:
            for delta_name, delta in STRONG_DELTAS:
                result.append(
                    {
                        "name": f"strong-{identifier}-{mutation}-{delta_name}",
                        "phase": "path-isolation",
                        "path": path,
                        "mutation": mutation,
                        "delta": delta,
                    }
                )
    identifier = path_name(POSITION_PATH)
    for delta_name, delta in STRONG_DELTAS:
        result.append(
            {
                "name": f"strong-{identifier}-position-{delta_name}",
                "phase": "path-isolation",
                "path": POSITION_PATH,
                "mutation": "position",
                "delta": delta,
            }
        )
    if sample_index != 25:
        return result

    dense_targets = (
        ((1, 0, 1, 0), MUTATIONS),
        (POSITION_PATH, ("position",)),
    )
    for path, mutations in dense_targets:
        identifier = path_name(path)
        for mutation in mutations:
            for value in DENSE_X_VALUES:
                result.append(
                    {
                        "name": (
                            f"dense-{identifier}-{mutation}-x-{signed_name(value)}"
                        ),
                        "phase": "dense-threshold",
                        "path": path,
                        "mutation": mutation,
                        "delta": (value, 0),
                    }
                )
            for value in DENSE_Y_VALUES:
                result.append(
                    {
                        "name": (
                            f"dense-{identifier}-{mutation}-y-{signed_name(value)}"
                        ),
                        "phase": "dense-threshold",
                        "path": path,
                        "mutation": mutation,
                        "delta": (0, value),
                    }
                )
    return result


def requested_layer_states(
    states: Sequence[Any],
    intervention: Mapping[str, Any],
) -> list[dict[str, Any]]:
    path = tuple(int(value) for value in intervention["path"])
    mutation = intervention["mutation"]
    delta = tuple(int(value) for value in intervention["delta"])
    if mutation not in {*MUTATIONS, "base"} or len(delta) != 2:
        raise ValueError("path-isolation mutation differs")
    result: list[dict[str, Any]] = []
    for untyped_state in states:
        state = copy.deepcopy(dict(holdout.mapping(untyped_state, "layer state")))
        state_path = tuple(
            int(value) for value in fixed.sequence(state.get("path"), "layer path")
        )
        if state_path != path or mutation == "base":
            result.append(state)
            continue
        if mutation in {"bounds-origin", "bounds-origin-and-position"}:
            bounds = list(fixed.sequence(state.get("bounds"), "layer bounds"))
            if len(bounds) != 4:
                raise ValueError("path-isolation bounds are not a rectangle")
            bounds[0] = holdout.numeric(bounds[0], "bounds X") + delta[0]
            bounds[1] = holdout.numeric(bounds[1], "bounds Y") + delta[1]
            state["bounds"] = bounds
        if mutation in {"position", "bounds-origin-and-position"}:
            position = list(fixed.sequence(state.get("position"), "layer position"))
            if len(position) != 2:
                raise ValueError("path-isolation position is not a point")
            position[0] = holdout.numeric(position[0], "position X") + delta[0]
            position[1] = holdout.numeric(position[1], "position Y") + delta[1]
            state["position"] = position
        result.append(state)
    return result


def validate_attempts(record: Mapping[str, Any]) -> None:
    attempts = fixed.sequence(record.get("renderAttempts"), "render attempts")
    selected = int(record.get("selectedRenderAttemptIndex", -1))
    if not 1 <= len(attempts) <= 3 or selected != len(attempts) - 1:
        raise ValueError("path-isolation render attempt ledger differs")
    for index, untyped_attempt in enumerate(attempts):
        attempt = holdout.mapping(untyped_attempt, "render attempt")
        if (
            attempt.get("attemptIndex") != index
            or attempt.get("executed") is not True
            or not isinstance(attempt.get("capture"), str)
            or not isinstance(attempt.get("metalRecordCount"), int)
            or int(attempt.get("metalRecordCount", 0)) <= 0
            or (
                index == selected
                and attempt.get("producerCopyBaseObserved") is not True
            )
            or (
                index < selected
                and attempt.get("producerCopyBaseObserved") is not False
            )
        ):
            raise ValueError("path-isolation render attempt differs")


def validate_retained_buffers(render: Mapping[str, Any]) -> int:
    buffers = holdout.mapping(
        render.get("metalBufferSnapshots"), "retained Metal buffers"
    )
    if buffers.get("retentionPolicy") != BUFFER_RETENTION_POLICY:
        raise ValueError("path-isolation buffer retention policy differs")
    snapshots = fixed.sequence(buffers.get("snapshots"), "retained snapshots")
    if buffers.get("retainedSnapshotCount") != len(snapshots):
        raise ValueError("retained snapshot count differs")
    for untyped_snapshot in snapshots:
        snapshot = holdout.mapping(untyped_snapshot, "retained snapshot")
        stage = snapshot.get("stage")
        index = snapshot.get("index")
        if not (
            stage == "index"
            or (stage == "compute" and index == 0)
            or (stage == "vertex" and index in {1, 2})
        ):
            raise ValueError("unrequested buffer survived retention")
    return len(snapshots)


def validate(path: Path) -> dict[str, Any]:
    base = holdout.validate(
        path,
        expected_geometry=EXPECTED_GEOMETRY,
        expected_sample_indices=EXPECTED_SAMPLE_INDICES,
        classification=CLASSIFICATION,
        allowed_geometries=frozenset({EXPECTED_GEOMETRY}),
        require_primary_source_q_exact=False,
    )
    report = holdout.mapping(
        json.loads(path.read_text(encoding="utf-8")), "transition report"
    )
    uniforms = holdout.mapping(
        report.get("dynamicBackgroundUniforms"), "dynamic background uniforms"
    )
    evidence = holdout.mapping(
        uniforms.get("pathIsolationInterventions"), "path-isolation evidence"
    )
    expected_by_sample = {
        sample_index: expected_interventions(sample_index)
        for sample_index in EXPECTED_SOURCE_SAMPLE_INDICES
    }
    expected_counts = {
        str(sample_index): len(interventions)
        for sample_index, interventions in expected_by_sample.items()
    }
    expected_record_count = sum(expected_counts.values())
    expected_strong_paths = [list(value) for value in BOUNDS_PATHS] + [
        list(POSITION_PATH)
    ]
    expected_strong_deltas = [
        {"name": name, "delta": list(delta)} for name, delta in STRONG_DELTAS
    ]
    if (
        evidence.get("schemaVersion") != 1
        or evidence.get("requested") is not True
        or evidence.get("executed") is not True
        or evidence.get("sourceSampleIndices") != list(EXPECTED_SOURCE_SAMPLE_INDICES)
        or evidence.get("sourceInterventionCounts") != expected_counts
        or evidence.get("expectedRecordCount") != expected_record_count
        or evidence.get("executedRecordCount") != expected_record_count
        or evidence.get("strongPaths") != expected_strong_paths
        or evidence.get("strongDeltas") != expected_strong_deltas
        or evidence.get("denseSampleIndex") != 25
        or evidence.get("denseXValues") != list(DENSE_X_VALUES)
        or evidence.get("denseYValues") != list(DENSE_Y_VALUES)
        or evidence.get("liveRenderBoundaryReadback") is not True
        or evidence.get("maximumRenderAttemptCount") != 3
        or evidence.get("renderBufferRetentionPolicy") != BUFFER_RETENTION_POLICY
        or not holdout.no_raw_stage_dumps(evidence)
    ):
        raise ValueError("path-isolation evidence header differs")
    records = fixed.sequence(evidence.get("records"), "path-isolation records")
    if len(records) != expected_record_count:
        raise ValueError("path-isolation record count differs")

    normal_records = {
        int(holdout.mapping(value, "normal record")["sampleIndex"]): holdout.mapping(
            value, "normal record"
        )
        for value in fixed.sequence(uniforms.get("records"), "normal records")
    }
    normal_states = {
        int(holdout.mapping(value, "normal state")["sampleIndex"]): holdout.mapping(
            value, "normal state"
        )
        for value in fixed.sequence(base.get("states"), "normal states")
    }
    expected_order = [
        (sample_index, intervention_index, intervention)
        for sample_index in EXPECTED_SOURCE_SAMPLE_INDICES
        for intervention_index, intervention in enumerate(
            expected_by_sample[sample_index]
        )
    ]

    source_layer_hashes: dict[int, str] = {}
    source_filter_hashes: dict[int, str] = {}
    topology_counts: Counter[int] = Counter()
    phase_counts: Counter[str] = Counter()
    selected_attempt_counts: Counter[int] = Counter()
    q_components = 0
    q_mismatches = 0
    zero_semantic_exact = 0
    zero_draw_hash_exact = 0
    retained_buffer_count = 0
    validated_records: list[dict[str, Any]] = []

    for record_index, (untyped_record, expected) in enumerate(
        zip(records, expected_order, strict=True)
    ):
        sample_index, intervention_index, intervention = expected
        record = holdout.mapping(untyped_record, "path-isolation record")
        translation = tuple(
            int(value)
            for value in fixed.sequence(record.get("translation"), "translation")
        )
        mutation_path = tuple(
            int(value)
            for value in fixed.sequence(record.get("mutationPath"), "mutation path")
        )
        if (
            record.get("recordIndex") != record_index
            or record.get("sampleIndex") != sample_index
            or record.get("interventionIndex") != intervention_index
            or record.get("interventionName") != intervention["name"]
            or record.get("phase") != intervention["phase"]
            or record.get("mutation") != intervention["mutation"]
            or mutation_path != intervention["path"]
            or translation != intervention["delta"]
            or record.get("mutationPathOccurrenceCount") != 1
            or record.get("executed") is not True
            or record.get("originalProducerInput") is not True
            or record.get("producerCopyBaseObserved") is not True
            or record.get("filterInputValuesUnchanged") is not True
            or record.get("liveLayerStatesBeforeMatchRequested") is not True
            or record.get("liveLayerStatesAfterMatchRequested") is not True
            or record.get("liveFilterInputsBeforeUnchanged") is not True
            or record.get("liveFilterInputsAfterUnchanged") is not True
            or record.get("missingCriticalCarrierPaths") != []
        ):
            raise ValueError(
                f"path-isolation record differs at {sample_index}/{intervention_index}"
            )

        normal = normal_records[sample_index]
        remaining = holdout.numeric(record.get("remaining"), "remaining")
        if remaining != holdout.numeric(normal.get("remaining"), "normal remaining"):
            raise ValueError("path-isolation and normal remaining differ")
        source_layer_hash = record.get("sourceLayerStatesSHA256")
        source_filter_hash = record.get("sourceFilterInputValuesSHA256")
        requested_layer_hash = record.get("requestedLayerStatesSHA256")
        if (
            not isinstance(source_layer_hash, str)
            or len(source_layer_hash) != 64
            or not isinstance(source_filter_hash, str)
            or len(source_filter_hash) != 64
            or not isinstance(requested_layer_hash, str)
            or len(requested_layer_hash) != 64
            or record.get("replayedFilterInputValuesSHA256") != source_filter_hash
        ):
            raise ValueError("path-isolation source identity differs")
        if (
            source_layer_hashes.setdefault(sample_index, source_layer_hash)
            != source_layer_hash
            or source_filter_hashes.setdefault(sample_index, source_filter_hash)
            != source_filter_hash
        ):
            raise ValueError("path-isolation source changed within one state")

        expected_states = requested_layer_states(
            fixed.sequence(normal.get("capturedLayerStates"), "normal captured states"),
            intervention,
        )
        requested_states = list(
            fixed.sequence(record.get("requestedLayerStates"), "requested states")
        )
        before = holdout.mapping(
            record.get("liveRenderBoundaryBefore"), "live boundary before"
        )
        after = holdout.mapping(
            record.get("liveRenderBoundaryAfter"), "live boundary after"
        )
        before_states = list(
            fixed.sequence(before.get("layerStates"), "live before states")
        )
        after_states = list(
            fixed.sequence(after.get("layerStates"), "live after states")
        )
        captured_states = list(
            fixed.sequence(record.get("capturedLayerStates"), "captured states")
        )
        if (
            requested_states != expected_states
            or before_states != expected_states
            or after_states != expected_states
            or captured_states != before_states
            or before.get("schemaVersion") != 1
            or before.get("executed") is not True
            or after.get("schemaVersion") != 1
            or after.get("executed") is not True
            or before.get("layerStatesSHA256") != requested_layer_hash
            or after.get("layerStatesSHA256") != requested_layer_hash
            or before.get("backgroundFilterPath") != list(holdout.BACKDROP_LAYER_PATH)
            or after.get("backgroundFilterPath") != list(holdout.BACKDROP_LAYER_PATH)
            or before.get("backgroundFilterInputValuesSHA256") != source_filter_hash
            or after.get("backgroundFilterInputValuesSHA256") != source_filter_hash
        ):
            raise ValueError("path-isolation live state differs")

        validate_attempts(record)
        selected_attempt = int(record["selectedRenderAttemptIndex"])
        selected_attempt_counts[selected_attempt] += 1
        scale, layer_state_count = holdout.captured_scale(record)
        if scale != 1.0 - remaining / 2.0:
            raise ValueError("path-isolation backdrop scale differs")
        render = holdout.mapping(record.get("render"), "path-isolation render")
        retained_buffer_count += validate_retained_buffers(render)
        observed = holdout.observed_policy(record, scale=scale)
        mesh = holdout.mapping(observed.get("producerMesh"), "producer mesh")
        record_q_components = int(mesh["sourceScaleComponentCount"])
        record_q_mismatches = int(mesh["sourceScaleMismatchedComponents"])
        q_components += record_q_components
        q_mismatches += record_q_mismatches
        topology_counts[int(mesh["vertexCount"])] += 1
        phase_counts[str(intervention["phase"])] += 1

        if intervention["mutation"] == "base":
            normal_observed = holdout.mapping(
                normal_states[sample_index].get("observed"), "normal observed"
            )
            normal_mesh = holdout.mapping(
                normal_observed.get("producerMesh"), "normal producer mesh"
            )
            if int(normal_mesh["sourceScaleMismatchedComponents"]) != 0:
                raise ValueError("path-isolation normal source q law differs")
            zero_semantic_exact += fixed.semantic_policy(
                dict(observed)
            ) == fixed.semantic_policy(dict(normal_observed))
            zero_draw_hash_exact += fixed.draw_consumed_hashes(
                dict(observed)
            ) == fixed.draw_consumed_hashes(dict(normal_observed))

        validated_records.append(
            {
                "recordIndex": record_index,
                "sampleIndex": sample_index,
                "remaining": remaining,
                "runtimeScale": scale,
                "interventionIndex": intervention_index,
                "interventionName": intervention["name"],
                "phase": intervention["phase"],
                "mutationPath": list(intervention["path"]),
                "mutation": intervention["mutation"],
                "translation": list(intervention["delta"]),
                "capturedLayerStateCount": layer_state_count,
                "selectedRenderAttemptIndex": selected_attempt,
                "observed": observed,
            }
        )

    source_count = len(EXPECTED_SOURCE_SAMPLE_INDICES)
    if (
        q_mismatches != 0
        or zero_semantic_exact != source_count
        or zero_draw_hash_exact != source_count
    ):
        raise ValueError("path-isolation exact integrity gate failed")
    return {
        "dynamicAllocationPathIsolationResultSchemaVersion": 1,
        "classification": CLASSIFICATION,
        "timeline": str(path),
        "timelineSHA256": holdout.sha256_file(path),
        "geometry": report.get("geometry"),
        "sourceSampleIndices": list(EXPECTED_SOURCE_SAMPLE_INDICES),
        "aggregate": {
            "recordCount": len(validated_records),
            "sourceStateCount": source_count,
            "sourceInterventionCounts": expected_counts,
            "phaseRecordCounts": {
                name: phase_counts[name] for name in sorted(phase_counts)
            },
            "primaryProducerSourceQ": {
                "componentCount": q_components,
                "mismatchedComponents": q_mismatches,
                "exact": q_mismatches == 0,
            },
            "producerVertexCountStates": {
                str(count): topology_counts[count] for count in sorted(topology_counts)
            },
            "selectedRenderAttemptCounts": {
                str(index): selected_attempt_counts[index]
                for index in sorted(selected_attempt_counts)
            },
            "retainedBufferSnapshotCount": retained_buffer_count,
            "zeroTranslationSemanticPolicyExact": True,
            "zeroTranslationDrawConsumedPayloadExact": True,
            "liveLayerStateBeforeAndAfterExact": True,
            "liveFilterInputsBeforeAndAfterExact": True,
            "sourceFilterHashStableWithinEachState": True,
            "sourceLayerHashStableWithinEachState": True,
            "originalProducerInputEveryState": True,
            "rawStageDumpsAbsent": True,
        },
        "records": validated_records,
        "conclusion": {
            "captureIntegrityPassed": True,
            "causalCalibrationOnly": True,
            "independentProducerMeshPolicyRecovered": False,
            "requiresPostOpeningAnalysis": True,
            "requiresUnseenHoldout": True,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.report)
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
        print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
