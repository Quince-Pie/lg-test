#!/usr/bin/env python3
"""Analyze preregistered single-path producer-mesh interventions."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_dynamic_allocation_holdout as allocation
import validate_dynamic_allocation_fixed_state as fixed
import validate_dynamic_allocation_holdout as holdout
import validate_dynamic_allocation_path_isolation as path_isolation


CLASSIFICATION = (
    "post-opening-analysis-of-preregistered-live-read-back-path-isolation; "
    "not-an-unseen-geometry-transfer"
)
INVARIANT_FIELDS = (
    "cropOrigin",
    "textureCoordinateClamp",
    "producerExtent",
    "destinationExtent",
    "copyOffset",
    "effectiveOrigin",
)


def primary_edges(observed: Mapping[str, Any]) -> list[float]:
    mesh = holdout.mapping(observed.get("producerMesh"), "producer mesh")
    return allocation.primary_position_bounds(mesh.get("primaryVertices"))


def edge_delta(
    reference: Mapping[str, Any], observed: Mapping[str, Any]
) -> tuple[float, ...]:
    return tuple(
        actual - expected
        for actual, expected in zip(
            primary_edges(observed),
            primary_edges(reference),
            strict=True,
        )
    )


def response_runs(
    values: Sequence[tuple[int, tuple[float, ...]]],
) -> list[dict[str, Any]]:
    if not values:
        raise ValueError("dense response group is empty")
    ordered = sorted(values)
    if len({value for value, _ in ordered}) != len(ordered):
        raise ValueError("dense response values are not unique")
    runs: list[dict[str, Any]] = []
    start = ordered[0][0]
    previous = ordered[0][0]
    response = ordered[0][1]
    for value, current in ordered[1:]:
        if current == response:
            previous = value
            continue
        runs.append(
            {
                "minimumValue": start,
                "maximumValue": previous,
                "response": list(response),
            }
        )
        start = value
        previous = value
        response = current
    runs.append(
        {
            "minimumValue": start,
            "maximumValue": previous,
            "response": list(response),
        }
    )
    return runs


def transition_brackets(runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    brackets: list[dict[str, Any]] = []
    for lower, upper in zip(runs, runs[1:]):
        brackets.append(
            {
                "lowerObservedValue": int(lower["maximumValue"]),
                "upperObservedValue": int(upper["minimumValue"]),
                "lowerResponse": list(lower["response"]),
                "upperResponse": list(upper["response"]),
            }
        )
    return brackets


def analyze(result_path: Path, *, run_id: int) -> dict[str, Any]:
    if run_id <= 0:
        raise ValueError("run ID must be positive")
    result = holdout.mapping(
        json.loads(result_path.read_text(encoding="utf-8")),
        "path-isolation validator result",
    )
    conclusion = holdout.mapping(result.get("conclusion"), "validator conclusion")
    if (
        result.get("dynamicAllocationPathIsolationResultSchemaVersion") != 1
        or result.get("classification") != path_isolation.CLASSIFICATION
        or conclusion.get("captureIntegrityPassed") is not True
        or conclusion.get("causalCalibrationOnly") is not True
        or conclusion.get("productionShaderAuthorized") is not False
    ):
        raise ValueError("path-isolation validator result is not accepted calibration")
    untyped_records = result.get("records")
    if not isinstance(untyped_records, list) or len(untyped_records) != 426:
        raise ValueError("path-isolation validated record count differs")
    records = [
        holdout.mapping(value, "path-isolation validated record")
        for value in untyped_records
    ]
    bases = {
        int(record["sampleIndex"]): holdout.mapping(
            record.get("observed"), "base observed policy"
        )
        for record in records
        if record.get("phase") == "control"
    }
    if set(bases) != set(path_isolation.EXPECTED_SOURCE_SAMPLE_INDICES):
        raise ValueError("path-isolation base states differ")

    invariant_components = 0
    invariant_mismatches = 0
    invariant_residuals: list[dict[str, Any]] = []
    topology_mismatches = 0
    changed_edge_components = 0
    edge_components = 0
    changed_records = 0
    edge_delta_counts: Counter[tuple[str, float]] = Counter()
    strong_effects: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    dense_values: dict[
        tuple[tuple[int, ...], str, str], list[tuple[int, tuple[float, ...]]]
    ] = defaultdict(list)
    record_responses: list[dict[str, Any]] = []

    for record in records:
        sample_index = int(record["sampleIndex"])
        reference = bases[sample_index]
        observed = holdout.mapping(record.get("observed"), "observed policy")
        for field in INVARIANT_FIELDS:
            expected_values = list(
                fixed.sequence(reference.get(field), f"base {field}")
            )
            actual_values = list(
                fixed.sequence(observed.get(field), f"observed {field}")
            )
            if len(expected_values) != len(actual_values):
                raise ValueError(f"path-isolation invariant length differs: {field}")
            invariant_components += len(expected_values)
            for component, (expected, actual) in enumerate(
                zip(expected_values, actual_values, strict=True)
            ):
                if expected == actual:
                    continue
                invariant_mismatches += 1
                invariant_residuals.append(
                    {
                        "recordIndex": record["recordIndex"],
                        "sampleIndex": sample_index,
                        "interventionName": record["interventionName"],
                        "field": field,
                        "component": component,
                        "expected": expected,
                        "observed": actual,
                    }
                )
        reference_mesh = holdout.mapping(
            reference.get("producerMesh"), "reference producer mesh"
        )
        observed_mesh = holdout.mapping(
            observed.get("producerMesh"), "observed producer mesh"
        )
        topology_mismatches += int(reference_mesh["vertexCount"]) != int(
            observed_mesh["vertexCount"]
        )
        response = edge_delta(reference, observed)
        edge_components += len(response)
        changed = sum(value != 0 for value in response)
        changed_edge_components += changed
        changed_records += changed > 0
        for name, difference in zip(allocation.EDGE_NAMES, response, strict=True):
            if difference:
                edge_delta_counts[(name, difference)] += 1
        path = tuple(int(value) for value in record["mutationPath"])
        mutation = str(record["mutation"])
        translation = tuple(int(value) for value in record["translation"])
        phase = str(record["phase"])
        if phase == "path-isolation":
            strong_effects[(sample_index, path, mutation)].append(
                {
                    "interventionName": record["interventionName"],
                    "translation": list(translation),
                    "response": list(response),
                }
            )
        elif phase == "dense-threshold":
            if (translation[0] == 0) == (translation[1] == 0):
                raise ValueError("dense intervention is not one-axis nonzero")
            axis = "x" if translation[0] else "y"
            value = translation[0] if translation[0] else translation[1]
            dense_values[(path, mutation, axis)].append((value, response))
        elif phase != "control":
            raise ValueError(f"unexpected path-isolation phase: {phase}")
        record_responses.append(
            {
                "recordIndex": record["recordIndex"],
                "sampleIndex": sample_index,
                "interventionName": record["interventionName"],
                "phase": phase,
                "mutationPath": list(path),
                "mutation": mutation,
                "translation": list(translation),
                "primaryEdgeResponse": list(response),
            }
        )

    strong_groups: list[dict[str, Any]] = []
    causal_strong_groups: list[dict[str, Any]] = []
    for key in sorted(strong_effects):
        sample_index, path, mutation = key
        responses = strong_effects[key]
        group = {
            "sampleIndex": sample_index,
            "mutationPath": list(path),
            "mutation": mutation,
            "changedInterventionCount": sum(
                any(item["response"]) for item in responses
            ),
            "interventions": responses,
        }
        strong_groups.append(group)
        if group["changedInterventionCount"]:
            causal_strong_groups.append(group)

    dense_groups: list[dict[str, Any]] = []
    for key in sorted(dense_values):
        path, mutation, axis = key
        values = dense_values[key]
        expected_count = (
            len(path_isolation.DENSE_X_VALUES)
            if axis == "x"
            else len(path_isolation.DENSE_Y_VALUES)
        )
        if len(values) != expected_count:
            raise ValueError("dense path-isolation group count differs")
        runs = response_runs(values)
        dense_groups.append(
            {
                "sampleIndex": 25,
                "mutationPath": list(path),
                "mutation": mutation,
                "axis": axis,
                "sampledValueCount": len(values),
                "distinctResponseCount": len({response for _, response in values}),
                "runs": runs,
                "transitionBrackets": transition_brackets(runs),
            }
        )

    return {
        "dynamicAllocationPathIsolationAnalysisSchemaVersion": 1,
        "classification": CLASSIFICATION,
        "runID": run_id,
        "inputValidatorResultArtifact": result_path.parent.name
        + "/"
        + result_path.name,
        "inputValidatorResultSHA256": holdout.sha256_file(result_path),
        "aggregate": {
            "recordCount": len(records),
            "invariantAllocationPolicy": {
                "componentCount": invariant_components,
                "mismatchedComponents": invariant_mismatches,
                "exact": invariant_mismatches == 0,
            },
            "producerTopology": {
                "componentCount": len(records),
                "mismatchedComponents": topology_mismatches,
                "exact": topology_mismatches == 0,
            },
            "primaryEdgeResponse": {
                "componentCount": edge_components,
                "mismatchedComponents": changed_edge_components,
                "exact": changed_edge_components == 0,
            },
            "changedPrimaryEdgeRecordCount": changed_records,
            "primaryEdgeDeltaCounts": [
                {"edge": edge, "difference": difference, "count": count}
                for (edge, difference), count in sorted(edge_delta_counts.items())
            ],
            "strongInterventionGroupCount": len(strong_groups),
            "causalStrongInterventionGroupCount": len(causal_strong_groups),
            "denseInterventionGroupCount": len(dense_groups),
        },
        "invariantPolicyResiduals": invariant_residuals,
        "strongInterventionGroups": strong_groups,
        "causalStrongInterventionGroups": causal_strong_groups,
        "denseResponseGroups": dense_groups,
        "recordResponses": record_responses,
        "conclusion": {
            "singlePathFieldCauseIdentified": bool(causal_strong_groups),
            "sampledThresholdBracketsRecovered": any(
                group["transitionBrackets"] for group in dense_groups
            ),
            "independentProducerMeshPolicyRecovered": False,
            "requiresPostOpeningArithmeticRecovery": True,
            "requiresUnseenHoldout": True,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("validator_result", type=Path)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = analyze(arguments.validator_result, run_id=arguments.run_id)
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
        print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
