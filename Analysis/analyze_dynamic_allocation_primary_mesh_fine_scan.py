#!/usr/bin/env python3
"""Open the preregistered primary-mesh fine and cross-axis scan."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_dynamic_allocation_holdout as allocation
import analyze_dynamic_allocation_surviving_path_threshold as prior
import validate_dynamic_allocation_holdout as holdout
import validate_dynamic_allocation_surviving_path_threshold as surviving


CLASSIFICATION = (
    "post-opening-analysis-of-preregistered-deepest-sdf-position-fine-"
    "threshold-and-cross-axis-scan; not-an-unseen-geometry-transfer"
)
PRIOR_RESPONSE_ANCHORS = {
    (25, (80, 0)): (0.0, 0.0, 0.0, 0.0),
    (25, (88, 0)): (1.0, 0.0, 0.0, 0.0),
    (25, (0, 64)): (0.0, 0.0, 0.0, 0.0),
    (25, (0, 96)): (0.0, 0.0, 0.0, -1.0),
    (31, (-90, 0)): (0.0, 0.0, 0.0, 1.0),
    (31, (90, 0)): (0.0, 0.0, 1.0, 1.0),
    (31, (0, -134)): (0.0, 0.0, 1.0, 1.0),
    (31, (0, 134)): (0.0, 0.0, 1.0, 0.0),
}


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
    return prior.response_runs(values)


def transition_brackets(runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return prior.transition_brackets(runs)


def analyze(result_path: Path, *, run_id: int) -> dict[str, Any]:
    if run_id <= 0:
        raise ValueError("run ID must be positive")
    result = holdout.mapping(
        json.loads(result_path.read_text(encoding="utf-8")), "validator result"
    )
    conclusion = holdout.mapping(result.get("conclusion"), "validator conclusion")
    if (
        result.get("dynamicAllocationSurvivingPathThresholdResultSchemaVersion")
        != 2
        or result.get("captureEvidenceSchemaVersion") != 3
        or result.get("classification") != surviving.FINE_SCAN_CLASSIFICATION
        or conclusion.get("captureIntegrityPassed") is not True
        or conclusion.get("causalCalibrationOnly") is not True
        or conclusion.get("productionShaderAuthorized") is not False
    ):
        raise ValueError("fine-scan validator result is not accepted calibration")
    raw_records = result.get("records")
    expected_record_count = sum(
        len(surviving.fine_scan_interventions(sample))
        for sample in surviving.EXPECTED_SOURCE_SAMPLE_INDICES
    )
    if not isinstance(raw_records, list) or len(raw_records) != expected_record_count:
        raise ValueError("fine-scan validated record count differs")
    records = [holdout.mapping(value, "validated record") for value in raw_records]
    bases = {
        int(record["sampleIndex"]): holdout.mapping(
            record.get("observed"), "base observed policy"
        )
        for record in records
        if record.get("phase") == "control"
    }
    if set(bases) != set(surviving.EXPECTED_SOURCE_SAMPLE_INDICES):
        raise ValueError("fine-scan base state set differs")

    edge_components = 0
    changed_components = 0
    changed_records = 0
    signed_counts: Counter[tuple[str, float]] = Counter()
    scans: dict[tuple[int, str], list[tuple[int, tuple[float, ...]]]] = defaultdict(
        list
    )
    responses_by_key: dict[tuple[int, tuple[int, int]], tuple[float, ...]] = {}
    record_responses: list[dict[str, Any]] = []

    for record in records:
        sample = int(record["sampleIndex"])
        observed = holdout.mapping(record.get("observed"), "observed policy")
        response = edge_delta(bases[sample], observed)
        edge_components += len(response)
        changed = sum(value != 0 for value in response)
        changed_components += changed
        changed_records += changed > 0
        for name, value in zip(allocation.EDGE_NAMES, response, strict=True):
            if value:
                signed_counts[(name, value)] += 1
        phase = str(record["phase"])
        translation = tuple(int(value) for value in record["translation"])
        if len(translation) != 2:
            raise ValueError("fine-scan translation is not a point")
        item = {
            "recordIndex": record["recordIndex"],
            "sampleIndex": sample,
            "interventionName": record["interventionName"],
            "phase": phase,
            "translation": list(translation),
            "primaryEdgeResponse": list(response),
        }
        if phase != "control":
            if (translation[0] == 0) == (translation[1] == 0):
                raise ValueError("fine-scan intervention is not one-axis nonzero")
            axis = "x" if translation[0] else "y"
            value = translation[0] if translation[0] else translation[1]
            scans[(sample, axis)].append((value, response))
            responses_by_key[(sample, translation)] = response
        record_responses.append(item)

    scan_groups: list[dict[str, Any]] = []
    for sample in surviving.EXPECTED_SOURCE_SAMPLE_INDICES:
        for axis_index, axis in enumerate(("x", "y")):
            values = scans[(sample, axis)]
            expected_values = surviving.SCAN_VALUES_BY_SAMPLE[sample][axis_index]
            if tuple(sorted(value for value, _ in values)) != tuple(expected_values):
                raise ValueError(f"fine-scan {sample}/{axis} values differ")
            runs = response_runs(values)
            ordered_values = tuple(sorted(expected_values))
            scan_groups.append(
                {
                    "sampleIndex": sample,
                    "mutationPath": list(surviving.POSITION_PATH),
                    "mutation": "position",
                    "phase": surviving.SCAN_PHASES_BY_SAMPLE[sample],
                    "axis": axis,
                    "sampledValueCount": len(values),
                    "unitStepCoverage": all(
                        upper - lower == 1
                        for lower, upper in zip(
                            ordered_values, ordered_values[1:]
                        )
                    ),
                    "distinctResponseCount": len(
                        {response for _, response in values}
                    ),
                    "runs": runs,
                    "transitionBrackets": transition_brackets(runs),
                }
            )

    anchor_records = []
    for (sample, translation), expected_response in PRIOR_RESPONSE_ANCHORS.items():
        observed_response = responses_by_key.get((sample, translation))
        if observed_response is None:
            raise ValueError("fine-scan prior-response anchor is missing")
        anchor_records.append(
            {
                "sampleIndex": sample,
                "translation": list(translation),
                "priorResponse": list(expected_response),
                "observedResponse": list(observed_response),
                "exact": observed_response == expected_response,
            }
        )
    anchor_exact_count = sum(bool(record["exact"]) for record in anchor_records)

    return {
        "dynamicAllocationPrimaryMeshFineScanAnalysisSchemaVersion": 1,
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
            "signedEdgeDeltaCounts": {
                f"{name}:{value:+g}": count
                for (name, value), count in sorted(signed_counts.items())
            },
            "scanGroupCount": len(scan_groups),
            "priorResponseAnchorCount": len(anchor_records),
            "priorResponseAnchorExactCount": anchor_exact_count,
            "priorResponseAnchorTransferPassed": (
                anchor_exact_count == len(anchor_records)
            ),
        },
        "scanGroups": scan_groups,
        "priorResponseAnchors": anchor_records,
        "recordResponses": record_responses,
        "conclusion": {
            "causalCalibrationAnalyzed": True,
            "state25BracketsExhaustivelySampledAtIntegerSteps": True,
            "crossAxisScanIsCoarseOutsidePriorAnchors": True,
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
