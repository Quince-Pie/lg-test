#!/usr/bin/env python3
"""Audit failed path-isolation run 30754929850 without promoting it."""

from __future__ import annotations

import argparse
import copy
import json
import struct
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import analyze_dynamic_allocation_holdout as allocation
import validate_dynamic_allocation_fixed_state as fixed
import validate_dynamic_allocation_holdout as holdout
import validate_dynamic_allocation_path_isolation as isolation
import validate_transition_input_clamp_probe as clamp


EXPECTED_RUN_ID = 30_754_929_850
CLASSIFICATION = (
    "post-opening-audit-of-failed-preregistered-live-read-back-path-isolation; "
    "not-an-accepted-calibration-or-unseen-transfer"
)
INVARIANT_FIELDS = (
    "cropOrigin",
    "textureCoordinateClamp",
    "producerExtent",
    "destinationExtent",
    "copyOffset",
    "effectiveOrigin",
)
BEST_CLAMP_CANDIDATE = "float-weighted-mix/mixed-base-darwin-powf"
RECOVERED_CLAMP_ENCODING = "float-weighted-mix"


def float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def float32_bits(value: float) -> str:
    return struct.pack(">f", float32(value)).hex()


def affine_expanded_base(encoded: float) -> float:
    divisor = float32(1.055)
    inverse = float32(float32(1.0) / divisor)
    offset = float32(float32(0.055) / divisor)
    product = float32(float32(encoded) * inverse)
    return float32(product + offset)


def float_base(encoded: float) -> float:
    return float32(float32(float32(encoded) + float32(0.055)) / float32(1.055))


def mixed_base(encoded: float) -> float:
    return float32((float(float32(encoded)) + 0.055) / float(float32(1.055)))


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


def layer_states_by_path(record: Mapping[str, Any]) -> dict[tuple[int, ...], dict[str, Any]]:
    boundary = holdout.mapping(
        record.get("liveRenderBoundaryBefore"), "live boundary before"
    )
    result: dict[tuple[int, ...], dict[str, Any]] = {}
    for value in fixed.sequence(boundary.get("layerStates"), "live layer states"):
        state = dict(holdout.mapping(value, "live layer state"))
        path = tuple(
            int(component)
            for component in fixed.sequence(state.get("path"), "live layer path")
        )
        if path in result:
            raise ValueError(f"duplicate live layer path: {path}")
        result[path] = state
    return result


def live_target_delta(
    base: Mapping[tuple[int, ...], Mapping[str, Any]],
    observed: Mapping[tuple[int, ...], Mapping[str, Any]],
    path: tuple[int, ...],
) -> dict[str, Any]:
    if path not in base or path not in observed:
        return {
            "targetPresentInBaseAndObserved": False,
            "boundsOrigin": None,
            "position": None,
        }
    base_state = base[path]
    observed_state = observed[path]
    base_bounds = fixed.sequence(base_state.get("bounds"), "base bounds")
    observed_bounds = fixed.sequence(observed_state.get("bounds"), "observed bounds")
    base_position = fixed.sequence(base_state.get("position"), "base position")
    observed_position = fixed.sequence(
        observed_state.get("position"), "observed position"
    )
    return {
        "targetPresentInBaseAndObserved": True,
        "boundsOrigin": [
            holdout.numeric(observed_bounds[index], "observed bounds")
            - holdout.numeric(base_bounds[index], "base bounds")
            for index in (0, 1)
        ],
        "position": [
            holdout.numeric(observed_position[index], "observed position")
            - holdout.numeric(base_position[index], "base position")
            for index in (0, 1)
        ],
    }


def requested_delta_survived(
    mutation: str,
    requested: tuple[int, int],
    observed: Mapping[str, Any],
) -> bool:
    if observed.get("targetPresentInBaseAndObserved") is not True:
        return False
    expected_bounds = (
        list(requested)
        if mutation in {"bounds-origin", "bounds-origin-and-position"}
        else [0, 0]
    )
    expected_position = (
        list(requested)
        if mutation in {"position", "bounds-origin-and-position"}
        else [0, 0]
    )
    return (
        observed.get("boundsOrigin") == expected_bounds
        and observed.get("position") == expected_position
    )


def decoded_policy(value: Mapping[str, Any]) -> dict[str, Any]:
    """Retain decoded policy while removing snapshot and raw-payload identity."""
    result = copy.deepcopy(dict(value))
    mesh = dict(holdout.mapping(result.get("producerMesh"), "producer mesh"))
    for name in tuple(mesh):
        if name.endswith("SHA256") or name.endswith("PayloadByteCount"):
            mesh.pop(name)
    result["producerMesh"] = mesh
    return result


def _expected_order() -> list[tuple[int, int, dict[str, Any]]]:
    return [
        (sample_index, intervention_index, intervention)
        for sample_index in isolation.EXPECTED_SOURCE_SAMPLE_INDICES
        for intervention_index, intervention in enumerate(
            isolation.expected_interventions(sample_index)
        )
    ]


def _attempts_are_exhausted(record: Mapping[str, Any]) -> bool:
    attempts = fixed.sequence(record.get("renderAttempts"), "render attempts")
    return len(attempts) == 3 and all(
        holdout.mapping(value, "render attempt").get("executed") is True
        and holdout.mapping(value, "render attempt").get("producerCopyBaseObserved")
        is False
        for value in attempts
    )


def analyze(timeline_path: Path, *, run_id: int) -> dict[str, Any]:
    if run_id != EXPECTED_RUN_ID:
        raise ValueError(f"this audit is frozen for run {EXPECTED_RUN_ID}")
    report = holdout.mapping(
        json.loads(timeline_path.read_text(encoding="utf-8")), "transition report"
    )
    uniforms = holdout.mapping(
        report.get("dynamicBackgroundUniforms"), "dynamic background uniforms"
    )
    evidence = holdout.mapping(
        uniforms.get("pathIsolationInterventions"), "path-isolation evidence"
    )
    records = [
        holdout.mapping(value, "path-isolation record")
        for value in fixed.sequence(evidence.get("records"), "path-isolation records")
    ]
    expected_order = _expected_order()
    expected_counts = {
        str(sample_index): len(isolation.expected_interventions(sample_index))
        for sample_index in isolation.EXPECTED_SOURCE_SAMPLE_INDICES
    }
    if (
        evidence.get("schemaVersion") != 1
        or evidence.get("requested") is not True
        or evidence.get("executed") is not False
        or evidence.get("sourceSampleIndices")
        != list(isolation.EXPECTED_SOURCE_SAMPLE_INDICES)
        or evidence.get("sourceInterventionCounts") != expected_counts
        or evidence.get("expectedRecordCount") != len(expected_order)
        or len(records) != len(expected_order)
        or evidence.get("executedRecordCount") != 114
    ):
        raise ValueError("failed path-isolation header differs")

    for record_index, (record, expected_item) in enumerate(
        zip(records, expected_order, strict=True)
    ):
        sample_index, intervention_index, intervention = expected_item
        path = tuple(
            int(value)
            for value in fixed.sequence(record.get("mutationPath"), "mutation path")
        )
        translation = tuple(
            int(value)
            for value in fixed.sequence(record.get("translation"), "translation")
        )
        if (
            record.get("recordIndex") != record_index
            or record.get("sampleIndex") != sample_index
            or record.get("interventionIndex") != intervention_index
            or record.get("interventionName") != intervention["name"]
            or record.get("phase") != intervention["phase"]
            or record.get("mutation") != intervention["mutation"]
            or path != intervention["path"]
            or translation != intervention["delta"]
        ):
            raise ValueError(f"path-isolation ordering differs at {record_index}")

    success_indices = [
        index
        for index, record in enumerate(records)
        if record.get("executed") is True
        and record.get("producerCopyBaseObserved") is True
    ]
    failure_indices = [
        index
        for index, record in enumerate(records)
        if record.get("executed") is not True
        or record.get("producerCopyBaseObserved") is not True
    ]
    if success_indices != list(range(114)) or failure_indices != list(
        range(114, len(records))
    ):
        raise ValueError("producer-copy failure is not the observed prefix boundary")
    if not all(_attempts_are_exhausted(records[index]) for index in failure_indices):
        raise ValueError("post-boundary render attempts differ")

    normal_records = {
        int(holdout.mapping(value, "normal record")["sampleIndex"]): holdout.mapping(
            value, "normal record"
        )
        for value in fixed.sequence(uniforms.get("records"), "normal records")
    }
    usable = records[:114]
    bases = {
        int(record["sampleIndex"]): record
        for record in usable
        if record.get("phase") == "control"
    }
    if set(bases) != {25}:
        raise ValueError("usable base-state set differs")
    base_live = {sample: layer_states_by_path(record) for sample, record in bases.items()}
    base_observed: dict[int, Mapping[str, Any]] = {}
    for sample, record in bases.items():
        scale, _ = holdout.captured_scale(record)
        base_observed[sample] = holdout.observed_policy(record, scale=scale)

    invariant_components = 0
    invariant_mismatches = 0
    q_components = 0
    q_mismatches = 0
    topology_mismatches = 0
    edge_components = 0
    edge_mismatches = 0
    edge_delta_counts: Counter[tuple[str, float]] = Counter()
    pre_post_state_exact = 0
    requested_state_exact = 0
    filter_exact = 0
    strong: dict[tuple[tuple[int, ...], str], list[dict[str, Any]]] = defaultdict(list)
    dense_records: list[dict[str, Any]] = []

    for record in usable:
        sample = int(record["sampleIndex"])
        scale, _ = holdout.captured_scale(record)
        observed = holdout.observed_policy(record, scale=scale)
        reference = base_observed[sample]
        for field in INVARIANT_FIELDS:
            expected_values = fixed.sequence(reference.get(field), f"base {field}")
            actual_values = fixed.sequence(observed.get(field), f"observed {field}")
            if len(expected_values) != len(actual_values):
                raise ValueError(f"allocation invariant length differs: {field}")
            invariant_components += len(expected_values)
            invariant_mismatches += sum(
                expected != actual
                for expected, actual in zip(
                    expected_values, actual_values, strict=True
                )
            )
        mesh = holdout.mapping(observed.get("producerMesh"), "producer mesh")
        reference_mesh = holdout.mapping(
            reference.get("producerMesh"), "base producer mesh"
        )
        q_components += int(mesh["sourceScaleComponentCount"])
        q_mismatches += int(mesh["sourceScaleMismatchedComponents"])
        topology_mismatches += int(mesh["vertexCount"]) != int(
            reference_mesh["vertexCount"]
        )
        response = edge_delta(reference, observed)
        edge_components += len(response)
        edge_mismatches += sum(value != 0 for value in response)
        for name, value in zip(allocation.EDGE_NAMES, response, strict=True):
            if value:
                edge_delta_counts[(name, value)] += 1

        before = holdout.mapping(
            record.get("liveRenderBoundaryBefore"), "live boundary before"
        )
        after = holdout.mapping(
            record.get("liveRenderBoundaryAfter"), "live boundary after"
        )
        pre_post_state_exact += before.get("layerStatesSHA256") == after.get(
            "layerStatesSHA256"
        )
        requested_state_exact += record.get(
            "liveLayerStatesBeforeMatchRequested"
        ) is True and record.get("liveLayerStatesAfterMatchRequested") is True
        filter_exact += record.get("liveFilterInputsBeforeUnchanged") is True and record.get(
            "liveFilterInputsAfterUnchanged"
        ) is True

        path = tuple(int(value) for value in record["mutationPath"])
        mutation = str(record["mutation"])
        translation = tuple(int(value) for value in record["translation"])
        live_delta = live_target_delta(
            base_live[sample], layer_states_by_path(record), path
        )
        survived = requested_delta_survived(mutation, translation, live_delta)
        item = {
            "recordIndex": record["recordIndex"],
            "interventionName": record["interventionName"],
            "translation": list(translation),
            "liveTargetDelta": live_delta,
            "requestedMutationSurvivedLayout": survived,
            "primaryEdgeResponse": list(response),
        }
        if record.get("phase") == "path-isolation":
            strong[(path, mutation)].append(item)
        elif record.get("phase") == "dense-threshold":
            dense_records.append(
                {
                    **item,
                    "mutationPath": list(path),
                    "mutation": mutation,
                }
            )

    strong_groups: list[dict[str, Any]] = []
    surviving_groups: list[dict[str, Any]] = []
    for (path, mutation), items in sorted(strong.items()):
        group = {
            "sampleIndex": 25,
            "mutationPath": list(path),
            "mutation": mutation,
            "recordCount": len(items),
            "liveSurvivingRecordCount": sum(
                item["requestedMutationSurvivedLayout"] for item in items
            ),
            "changedPrimaryEdgeRecordCount": sum(
                any(item["primaryEdgeResponse"]) for item in items
            ),
            "records": items,
        }
        strong_groups.append(group)
        if group["liveSurvivingRecordCount"]:
            surviving_groups.append(group)

    normal = normal_records[25]
    normal_scale, _ = holdout.captured_scale(normal)
    normal_observed = holdout.observed_policy(normal, scale=normal_scale)
    replay_mesh = holdout.mapping(
        base_observed[25].get("producerMesh"), "replay producer mesh"
    )
    normal_mesh = holdout.mapping(
        normal_observed.get("producerMesh"), "normal producer mesh"
    )

    clamp_result = clamp.validate(timeline_path)
    clamp_aggregate = holdout.mapping(
        clamp_result.get("aggregate"), "inputClamp aggregate"
    )
    clamp_records = [
        holdout.mapping(value, "inputClamp record")
        for value in fixed.sequence(clamp_result.get("records"), "inputClamp records")
    ]
    best_counterexamples = [
        {
            "sampleIndex": record["sampleIndex"],
            "remaining": record["remaining"],
            "remainingBits": record["remainingBits"],
            "observedBits": record["observedInputClampBits"],
            "candidateBits": holdout.mapping(
                record.get("candidateDecodedBits"), "candidate bits"
            )[BEST_CLAMP_CANDIDATE],
            "signedBitPatternDelta": int(
                holdout.mapping(record.get("candidateDecodedBits"), "candidate bits")[
                    BEST_CLAMP_CANDIDATE
                ],
                16,
            )
            - int(record["observedInputClampBits"], 16),
        }
        for record in clamp_records
        if holdout.mapping(record.get("candidateDecodedBits"), "candidate bits")[
            BEST_CLAMP_CANDIDATE
        ]
        != record["observedInputClampBits"]
    ]
    raw_probe = holdout.mapping(
        uniforms.get("inputClampArithmeticProbe"), "raw inputClamp probe"
    )
    raw_clamp_records = {
        int(holdout.mapping(value, "raw inputClamp record")["sampleIndex"]): holdout.mapping(
            value, "raw inputClamp record"
        )
        for value in fixed.sequence(raw_probe.get("records"), "raw clamp records")
    }
    recovered_candidates: dict[str, dict[str, Any]] = {}
    for encoded_name in clamp.ENCODED_CANDIDATES:
        recovered_records: list[dict[str, Any]] = []
        for validated in clamp_records:
            sample_index = int(validated["sampleIndex"])
            raw_record = raw_clamp_records[sample_index]
            raw_candidates = holdout.mapping(
                raw_record.get("candidates"), "raw clamp candidates"
            )
            float_candidate = holdout.mapping(
                raw_candidates.get(f"{encoded_name}/float-base-darwin-powf"),
                "float-base candidate",
            )
            mixed_candidate = holdout.mapping(
                raw_candidates.get(f"{encoded_name}/mixed-base-darwin-powf"),
                "mixed-base candidate",
            )
            encoded, encoded_bits = clamp.float_evidence(
                float_candidate.get("encoded"), "encoded clamp input"
            )
            mixed_encoded, mixed_encoded_bits = clamp.float_evidence(
                mixed_candidate.get("encoded"), "mixed candidate encoded input"
            )
            if (encoded, encoded_bits) != (mixed_encoded, mixed_encoded_bits):
                raise ValueError("decoder candidates did not share encoded input")
            recovered_base = affine_expanded_base(encoded)
            recovered_base_bits = float32_bits(recovered_base)
            float_base_bits = float32_bits(float_base(encoded))
            mixed_base_bits = float32_bits(mixed_base(encoded))
            if recovered_base_bits == float_base_bits:
                source_decoder = "float-base-darwin-powf"
                source_candidate = float_candidate
            elif recovered_base_bits == mixed_base_bits:
                source_decoder = "mixed-base-darwin-powf"
                source_candidate = mixed_candidate
            else:
                raise ValueError("recovered affine base was not measured by the probe")
            _, predicted_bits = clamp.float_evidence(
                holdout.mapping(source_candidate, "source candidate").get("decoded"),
                "source decoded candidate",
            )
            observed_bits = str(validated["observedInputClampBits"])
            recovered_records.append(
                {
                    "sampleIndex": sample_index,
                    "encodedBits": encoded_bits,
                    "affineExpandedBaseBits": recovered_base_bits,
                    "measuredDarwinPowfSourceDecoder": source_decoder,
                    "predictedBits": predicted_bits,
                    "observedBits": observed_bits,
                    "exact": predicted_bits == observed_bits,
                }
            )
        recovered_candidates[encoded_name] = {
            "exactMatchCount": sum(record["exact"] for record in recovered_records),
            "records": recovered_records,
        }

    return {
        "dynamicAllocationPathIsolationFailedRunAuditSchemaVersion": 1,
        "classification": CLASSIFICATION,
        "runID": run_id,
        "timelineArtifact": timeline_path.parent.name + "/" + timeline_path.name,
        "timelineSHA256": holdout.sha256_file(timeline_path),
        "aggregate": {
            "requestedInterventionCount": len(records),
            "extractableInterventionCount": len(usable),
            "extractableRecordPrefix": [0, 113],
            "firstMissingProducerCopyRecordIndex": 114,
            "missingProducerCopyCount": len(failure_indices),
            "allMissingCopyRecordsExhaustedThreeExecutedAttempts": True,
            "livePrePostStateExactCount": pre_post_state_exact,
            "requestedStateExactCount": requested_state_exact,
            "liveFilterExactCount": filter_exact,
            "allocationInvariants": {
                "componentCount": invariant_components,
                "mismatchedComponents": invariant_mismatches,
                "exact": invariant_mismatches == 0,
            },
            "primarySourceQ": {
                "componentCount": q_components,
                "mismatchedComponents": q_mismatches,
                "exact": q_mismatches == 0,
            },
            "topologyMismatchCount": topology_mismatches,
            "primaryEdges": {
                "componentCount": edge_components,
                "changedComponents": edge_mismatches,
                "signedDeltaCounts": {
                    f"{name}:{value:+g}": count
                    for (name, value), count in sorted(edge_delta_counts.items())
                },
            },
            "strongGroupCount": len(strong_groups),
            "strongGroupsWithAnyLiveMutation": len(surviving_groups),
            "denseExtractableRecordCount": len(dense_records),
            "baseDecodedPolicyMatchesNormal": decoded_policy(base_observed[25])
            == decoded_policy(normal_observed),
            "baseDrawConsumedHashes": {
                "vertexExact": replay_mesh.get("vertexDrawConsumedPayloadSHA256")
                == normal_mesh.get("vertexDrawConsumedPayloadSHA256"),
                "mvpExact": replay_mesh.get("mvpDrawConsumedPayloadSHA256")
                == normal_mesh.get("mvpDrawConsumedPayloadSHA256"),
                "indexExact": replay_mesh.get("indexDrawConsumedPayloadSHA256")
                == normal_mesh.get("indexDrawConsumedPayloadSHA256"),
            },
        },
        "strongGroups": strong_groups,
        "liveSurvivingStrongGroups": surviving_groups,
        "extractableDenseRecords": dense_records,
        "inputClamp": {
            "captureIntegrityPassed": True,
            "candidateCount": clamp_aggregate["candidateCount"],
            "sampleCount": clamp_aggregate["sampleCount"],
            "exactEveryStateCandidateNames": clamp_aggregate[
                "exactEveryStateCandidateNames"
            ],
            "exactMatchCounts": clamp_aggregate["exactMatchCounts"],
            "bestCandidateName": BEST_CLAMP_CANDIDATE,
            "bestCandidateExactMatchCount": clamp_aggregate["exactMatchCounts"][
                BEST_CLAMP_CANDIDATE
            ],
            "bestCandidateCounterexamples": best_counterexamples,
            "postOpeningAffineExpandedFormula": (
                "powf(float32(float32(encoded * float32(1/1.055f)) + "
                "float32(0.055f/1.055f)), 2.4f)"
            ),
            "postOpeningAffineConstants": {
                "inverseOnePointZeroFiveFiveBits": float32_bits(
                    float32(float32(1.0) / float32(1.055))
                ),
                "offsetBits": float32_bits(
                    float32(float32(0.055) / float32(1.055))
                ),
            },
            "postOpeningAffineExpandedCandidates": recovered_candidates,
            "postOpeningExactEncodingName": RECOVERED_CLAMP_ENCODING,
            "postOpeningExactMatchCount": recovered_candidates[
                RECOVERED_CLAMP_ENCODING
            ]["exactMatchCount"],
        },
        "conclusion": {
            "frozenPathIsolationGatePassed": False,
            "captureCeilingObservedAfterRecord114": True,
            "requestedPresentationStateSurvivedLayout": False,
            "onlyDeepestSDFPositionSurvivedStrongControls": True,
            "deepestSDFPositionChangedPrimaryEdges": True,
            "denseThresholdRecovered": False,
            "inputClampCandidateRecovered": False,
            "inputClampPostOpeningAffineExpandedCalibrationExact": True,
            "inputClampRequiresUnseenTemporalTransfer": True,
            "requiresReducedLiveBaselineThresholdCapture": True,
            "requiresUnseenGeometryTransfer": True,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = analyze(arguments.timeline, run_id=arguments.run_id)
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
        print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
