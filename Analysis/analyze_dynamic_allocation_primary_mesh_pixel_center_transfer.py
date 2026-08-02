#!/usr/bin/env python3
"""Re-express the sparse and fine mesh scans in live circle-center pixels."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import analyze_dynamic_allocation_holdout as allocation
import analyze_dynamic_allocation_primary_mesh_normalized_response as normalized
import analyze_dynamic_allocation_surviving_path_threshold as threshold
import validate_dynamic_allocation_fixed_state as fixed
import validate_dynamic_allocation_holdout as holdout
import validate_dynamic_allocation_surviving_path_threshold as surviving


CLASSIFICATION = (
    "post-opening-pixel-center-coordinate-transfer-between-preregistered-"
    "sparse-and-fine-scans; not-a-complete-mesh-policy"
)
TARGET_PATH = surviving.POSITION_PATH


def layer_at_path(states: object, path: tuple[int, ...]) -> Mapping[str, Any]:
    rows = [
        holdout.mapping(value, "live layer state")
        for value in fixed.sequence(states, "live layer states")
    ]
    matches = [
        row
        for row in rows
        if tuple(
            int(value)
            for value in fixed.sequence(row.get("path"), "live layer path")
        )
        == path
    ]
    if len(matches) != 1:
        raise ValueError(f"live layer path {path} is not unique")
    return matches[0]


def primary_edges(observed: Mapping[str, Any]) -> tuple[float, ...]:
    mesh = holdout.mapping(observed.get("producerMesh"), "producer mesh")
    return tuple(allocation.primary_position_bounds(mesh.get("primaryVertices")))


def response(reference: Mapping[str, Any], observed: Mapping[str, Any]) -> tuple[float, ...]:
    return tuple(
        actual - base
        for actual, base in zip(
            primary_edges(observed), primary_edges(reference), strict=True
        )
    )


def bracket_pair(bracket: Mapping[str, Any]) -> tuple[int, int]:
    return (
        int(bracket["lowerObservedValue"]),
        int(bracket["upperObservedValue"]),
    )


def bracket_contains(outer: tuple[int, int], inner: tuple[int, int]) -> bool:
    return outer[0] <= inner[0] < inner[1] <= outer[1]


def analyze(
    prior_timeline_path: Path,
    prior_validator_path: Path,
    fine_normalized_result_path: Path,
    *,
    prior_run_id: int,
    fine_run_id: int,
) -> dict[str, Any]:
    if prior_run_id <= 0 or fine_run_id <= 0 or prior_run_id == fine_run_id:
        raise ValueError("run IDs must be distinct and positive")

    prior_result = holdout.mapping(
        json.loads(prior_validator_path.read_text(encoding="utf-8")),
        "prior validator result",
    )
    prior_conclusion = holdout.mapping(
        prior_result.get("conclusion"), "prior validator conclusion"
    )
    if (
        prior_result.get("dynamicAllocationSurvivingPathThresholdResultSchemaVersion")
        != 1
        or prior_result.get("classification") != surviving.CLASSIFICATION
        or prior_conclusion.get("captureIntegrityPassed") is not True
        or prior_result.get("timelineSHA256")
        != holdout.sha256_file(prior_timeline_path)
    ):
        raise ValueError("prior threshold result is not accepted evidence")

    prior_timeline = holdout.mapping(
        json.loads(prior_timeline_path.read_text(encoding="utf-8")),
        "prior timeline",
    )
    prior_uniforms = holdout.mapping(
        prior_timeline.get("dynamicBackgroundUniforms"), "prior uniforms"
    )
    prior_evidence = holdout.mapping(
        prior_uniforms.get("pathIsolationInterventions"), "prior evidence"
    )
    raw_records = [
        holdout.mapping(value, "prior raw record")
        for value in fixed.sequence(prior_evidence.get("records"), "prior records")
    ]
    raw_by_index = {int(record["recordIndex"]): record for record in raw_records}
    validated_records = [
        holdout.mapping(value, "prior validated record")
        for value in fixed.sequence(prior_result.get("records"), "validated records")
    ]
    if len(raw_by_index) != 72 or len(validated_records) != 72:
        raise ValueError("prior record count differs")
    base = next(
        record
        for record in validated_records
        if int(record["sampleIndex"]) == 25 and record.get("phase") == "control"
    )
    base_observed = holdout.mapping(base.get("observed"), "prior base policy")

    prior_values: dict[str, list[tuple[int, tuple[float, ...]]]] = defaultdict(list)
    source_target_center: tuple[float, float] | None = None
    source_pixel_center: tuple[int, int] | None = None
    maximum_prior_center_residual_ulps = 0.0
    for record in validated_records:
        if int(record["sampleIndex"]) != 25:
            continue
        raw = raw_by_index[int(record["recordIndex"])]
        before = holdout.mapping(
            raw.get("liveRenderBoundaryBefore"), "prior live boundary"
        )
        target = layer_at_path(before.get("layerStates"), TARGET_PATH)
        position = tuple(
            holdout.numeric(value, "target position")
            for value in fixed.sequence(target.get("position"), "target position")
        )
        radius = holdout.numeric(target.get("cornerRadius"), "target radius")
        center = tuple(value + radius for value in position)
        pixel_details = tuple(
            normalized.pixel_center(value, maximum_residual_ulps=2.0)
            for value in center
        )
        pixels = tuple(value[0] for value in pixel_details)
        maximum_prior_center_residual_ulps = max(
            maximum_prior_center_residual_ulps,
            *(abs(value[2]) for value in pixel_details),
        )
        if record.get("phase") == "control":
            source_target_center = center
            source_pixel_center = pixels
            continue
        if record.get("phase") != "dense-threshold":
            continue
        translation = tuple(
            int(value)
            for value in fixed.sequence(record.get("translation"), "translation")
        )
        axis = "x" if translation[0] else "y"
        axis_index = 0 if axis == "x" else 1
        prior_values[axis].append(
            (
                pixels[axis_index],
                response(
                    base_observed,
                    holdout.mapping(record.get("observed"), "prior policy"),
                ),
            )
        )
    if source_target_center is None or source_pixel_center is None:
        raise ValueError("prior source state is missing")

    prior_scans: list[dict[str, Any]] = []
    for axis in ("x", "y"):
        runs = threshold.response_runs(prior_values[axis])
        brackets = threshold.transition_brackets(runs)
        if len(brackets) != 1:
            raise ValueError(f"prior {axis} center scan does not have one transition")
        prior_scans.append(
            {
                "axis": axis,
                "targetPixelCenterRuns": runs,
                "targetPixelCenterTransitionBrackets": brackets,
            }
        )

    fine_result = holdout.mapping(
        json.loads(fine_normalized_result_path.read_text(encoding="utf-8")),
        "fine normalized result",
    )
    fine_conclusion = holdout.mapping(
        fine_result.get("conclusion"), "fine normalized conclusion"
    )
    if (
        fine_result.get(
            "dynamicAllocationPrimaryMeshNormalizedResponseAnalysisSchemaVersion"
        )
        != 1
        or fine_result.get("classification") != normalized.CLASSIFICATION
        or int(fine_result.get("runID", -1)) != fine_run_id
        or fine_conclusion.get("sample25AxesShare335To336PixelCenterBracket")
        is not True
        or fine_conclusion.get("productionShaderAuthorized") is not False
    ):
        raise ValueError("fine normalized result differs")
    fine_source = next(
        holdout.mapping(value, "fine source state")
        for value in fixed.sequence(fine_result.get("sourceStates"), "fine sources")
        if int(holdout.mapping(value, "fine source state")["sampleIndex"]) == 25
    )
    fine_scans = [
        holdout.mapping(value, "fine scan group")
        for value in fixed.sequence(fine_result.get("scanGroups"), "fine scans")
        if int(holdout.mapping(value, "fine scan group")["sampleIndex"]) == 25
    ]
    if {str(scan["axis"]) for scan in fine_scans} != {"x", "y"}:
        raise ValueError("fine sample-25 axis set differs")

    transfers: list[dict[str, Any]] = []
    for axis in ("x", "y"):
        prior_scan = next(scan for scan in prior_scans if scan["axis"] == axis)
        fine_scan = next(scan for scan in fine_scans if scan["axis"] == axis)
        prior_bracket = bracket_pair(prior_scan["targetPixelCenterTransitionBrackets"][0])
        fine_brackets = fixed.sequence(
            fine_scan.get("targetPixelCenterTransitionBrackets"),
            "fine center brackets",
        )
        if len(fine_brackets) != 1:
            raise ValueError("fine sample-25 scan does not have one transition")
        fine_bracket = bracket_pair(
            holdout.mapping(fine_brackets[0], "fine center bracket")
        )
        transfers.append(
            {
                "axis": axis,
                "priorSparseBracket": list(prior_bracket),
                "fineUnitStepBracket": list(fine_bracket),
                "fineBracketContainedByPriorBracket": bracket_contains(
                    prior_bracket, fine_bracket
                ),
            }
        )

    fine_bracket_set = {
        tuple(value["fineUnitStepBracket"]) for value in transfers
    }
    transfer_passed = (
        all(value["fineBracketContainedByPriorBracket"] for value in transfers)
        and fine_bracket_set == {(335, 336)}
    )
    return {
        "dynamicAllocationPrimaryMeshPixelCenterTransferAnalysisSchemaVersion": 1,
        "classification": CLASSIFICATION,
        "priorRunID": prior_run_id,
        "fineRunID": fine_run_id,
        "inputs": {
            "priorTimelineArtifact": prior_timeline_path.parent.name
            + "/"
            + prior_timeline_path.name,
            "priorTimelineSHA256": holdout.sha256_file(prior_timeline_path),
            "priorValidatorArtifact": prior_validator_path.parent.name
            + "/"
            + prior_validator_path.name,
            "priorValidatorSHA256": holdout.sha256_file(prior_validator_path),
            "fineNormalizedResult": fine_normalized_result_path.name,
            "fineNormalizedResultSHA256": holdout.sha256_file(
                fine_normalized_result_path
            ),
        },
        "priorSourceState": {
            "sampleIndex": 25,
            "remaining": base["remaining"],
            "runtimeScale": base["runtimeScale"],
            "targetCenter": list(source_target_center),
            "targetPixelCenter": list(source_pixel_center),
            "maximumScanTargetCenterResidualULPs": (
                maximum_prior_center_residual_ulps
            ),
        },
        "fineSourceState": {
            "sampleIndex": 25,
            "remaining": fine_source["remaining"],
            "runtimeScale": fine_source["runtimeScale"],
            "targetCenter": fine_source["targetCenter"],
            "targetPixelCenter": fine_source["targetPixelCenter"],
        },
        "priorScans": prior_scans,
        "transfers": transfers,
        "conclusion": {
            "realizedTemporalStateDiffersAcrossRuns": (
                base["remaining"] != fine_source["remaining"]
            ),
            "rawResponseAnchorComparisonIsExactKConfounded": True,
            "sample25PixelCenterBracketTransferPassed": transfer_passed,
            "transferredUnitStepBracket": [335, 336],
            "independentProducerMeshPolicyRecovered": False,
            "sample31DeterminismEstablished": False,
            "requiresUnseenGeometryTransfer": True,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prior_timeline", type=Path)
    parser.add_argument("prior_validator", type=Path)
    parser.add_argument("fine_normalized_result", type=Path)
    parser.add_argument("--prior-run-id", type=int, required=True)
    parser.add_argument("--fine-run-id", type=int, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = analyze(
        arguments.prior_timeline,
        arguments.prior_validator,
        arguments.fine_normalized_result,
        prior_run_id=arguments.prior_run_id,
        fine_run_id=arguments.fine_run_id,
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
