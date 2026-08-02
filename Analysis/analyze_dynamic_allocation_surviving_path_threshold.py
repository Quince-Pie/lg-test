#!/usr/bin/env python3
"""Analyze the accepted deepest-SDF live-baseline threshold calibration."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_dynamic_allocation_holdout as allocation
import validate_dynamic_allocation_holdout as holdout
import validate_dynamic_allocation_surviving_path_threshold as surviving


CLASSIFICATION = (
    "post-opening-analysis-of-preregistered-live-baseline-deepest-sdf-"
    "position-threshold; not-an-unseen-geometry-transfer"
)


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
    if not values:
        raise ValueError("dense response group is empty")
    ordered = sorted(values)
    if len({value for value, _ in ordered}) != len(ordered):
        raise ValueError("dense response values are not unique")
    runs: list[dict[str, Any]] = []
    start = previous = ordered[0][0]
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
        start = previous = value
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
    return [
        {
            "lowerObservedValue": int(lower["maximumValue"]),
            "upperObservedValue": int(upper["minimumValue"]),
            "lowerResponse": list(lower["response"]),
            "upperResponse": list(upper["response"]),
        }
        for lower, upper in zip(runs, runs[1:])
    ]


def analyze(result_path: Path, *, run_id: int) -> dict[str, Any]:
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
    ):
        raise ValueError("surviving-path validator result is not accepted calibration")
    raw_records = result.get("records")
    if not isinstance(raw_records, list) or len(raw_records) != 72:
        raise ValueError("surviving-path validated record count differs")
    records = [holdout.mapping(value, "validated record") for value in raw_records]
    bases = {
        int(record["sampleIndex"]): holdout.mapping(
            record.get("observed"), "base observed policy"
        )
        for record in records
        if record.get("phase") == "control"
    }
    if set(bases) != set(surviving.EXPECTED_SOURCE_SAMPLE_INDICES):
        raise ValueError("surviving-path base state set differs")

    edge_components = 0
    changed_components = 0
    changed_records = 0
    topology_mismatches = 0
    signed_counts: Counter[tuple[str, float]] = Counter()
    strong: dict[int, list[dict[str, Any]]] = defaultdict(list)
    dense: dict[str, list[tuple[int, tuple[float, ...]]]] = defaultdict(list)
    record_responses: list[dict[str, Any]] = []

    for record in records:
        sample = int(record["sampleIndex"])
        observed = holdout.mapping(record.get("observed"), "observed policy")
        reference = bases[sample]
        response = edge_delta(reference, observed)
        edge_components += len(response)
        changed = sum(value != 0 for value in response)
        changed_components += changed
        changed_records += changed > 0
        reference_mesh = holdout.mapping(
            reference.get("producerMesh"), "reference mesh"
        )
        observed_mesh = holdout.mapping(observed.get("producerMesh"), "observed mesh")
        topology_mismatches += int(reference_mesh["vertexCount"]) != int(
            observed_mesh["vertexCount"]
        )
        for name, value in zip(allocation.EDGE_NAMES, response, strict=True):
            if value:
                signed_counts[(name, value)] += 1
        phase = str(record["phase"])
        translation = tuple(int(value) for value in record["translation"])
        item = {
            "recordIndex": record["recordIndex"],
            "sampleIndex": sample,
            "interventionName": record["interventionName"],
            "phase": phase,
            "translation": list(translation),
            "primaryEdgeResponse": list(response),
        }
        if phase == "path-isolation":
            strong[sample].append(item)
        elif phase == "dense-threshold":
            if (translation[0] == 0) == (translation[1] == 0):
                raise ValueError("dense intervention is not one-axis nonzero")
            axis = "x" if translation[0] else "y"
            value = translation[0] if translation[0] else translation[1]
            dense[axis].append((value, response))
        elif phase != "control":
            raise ValueError(f"unexpected phase: {phase}")
        record_responses.append(item)

    strong_groups = []
    for sample in sorted(strong):
        items = strong[sample]
        if len(items) != len(surviving.STRONG_DELTAS):
            raise ValueError("strong control count differs")
        strong_groups.append(
            {
                "sampleIndex": sample,
                "mutationPath": list(surviving.POSITION_PATH),
                "mutation": "position",
                "changedInterventionCount": sum(
                    any(item["primaryEdgeResponse"]) for item in items
                ),
                "interventions": items,
            }
        )

    dense_groups = []
    for axis in ("x", "y"):
        values = dense[axis]
        expected_count = (
            len(surviving.DENSE_X_VALUES)
            if axis == "x"
            else len(surviving.DENSE_Y_VALUES)
        )
        if len(values) != expected_count:
            raise ValueError(f"dense {axis} count differs")
        runs = response_runs(values)
        dense_groups.append(
            {
                "sampleIndex": 25,
                "mutationPath": list(surviving.POSITION_PATH),
                "mutation": "position",
                "axis": axis,
                "sampledValueCount": len(values),
                "distinctResponseCount": len({response for _, response in values}),
                "runs": runs,
                "transitionBrackets": transition_brackets(runs),
            }
        )

    return {
        "dynamicAllocationSurvivingPathThresholdAnalysisSchemaVersion": 1,
        "classification": CLASSIFICATION,
        "runID": run_id,
        "inputValidatorResultArtifact": result_path.parent.name
        + "/"
        + result_path.name,
        "inputValidatorResultSHA256": holdout.sha256_file(result_path),
        "aggregate": {
            "recordCount": len(records),
            "edgeComponentCount": edge_components,
            "changedEdgeComponentCount": changed_components,
            "changedRecordCount": changed_records,
            "topologyMismatchCount": topology_mismatches,
            "signedEdgeDeltaCounts": {
                f"{name}:{value:+g}": count
                for (name, value), count in sorted(signed_counts.items())
            },
            "strongGroupCount": len(strong_groups),
            "denseGroupCount": len(dense_groups),
        },
        "strongGroups": strong_groups,
        "denseGroups": dense_groups,
        "recordResponses": record_responses,
        "conclusion": {
            "causalCalibrationAnalyzed": True,
            "thresholdsReportedOnlyAsAdjacentObservedBrackets": True,
            "independentProducerMeshPolicyRecovered": False,
            "requiresUnseenGeometryTransfer": True,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = analyze(arguments.result, run_id=arguments.run_id)
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
        print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
