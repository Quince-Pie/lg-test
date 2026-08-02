#!/usr/bin/env python3
"""Normalize the opened fine scan against each run's live-carrier candidate."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_dynamic_allocation_holdout as allocation
import analyze_dynamic_allocation_surviving_path_threshold as prior
import validate_dynamic_allocation_fixed_state as fixed
import validate_dynamic_allocation_holdout as holdout
import validate_dynamic_allocation_surviving_path_threshold as surviving


CLASSIFICATION = (
    "post-opening-live-carrier-normalization-of-preregistered-primary-mesh-"
    "fine-scan; not-an-unseen-geometry-transfer"
)
CARRIER_PATH = (1,)
TARGET_PATH = surviving.POSITION_PATH


def layer_at_path(states: Sequence[Any], path: tuple[int, ...]) -> Mapping[str, Any]:
    matches = [
        holdout.mapping(value, "live layer state")
        for value in states
        if tuple(
            int(component)
            for component in fixed.sequence(
                holdout.mapping(value, "live layer state").get("path"),
                "live layer path",
            )
        )
        == path
    ]
    if len(matches) != 1:
        raise ValueError(f"live layer path {path} is not unique")
    return matches[0]


def primary_edges(observed: Mapping[str, Any]) -> tuple[float, ...]:
    mesh = holdout.mapping(observed.get("producerMesh"), "producer mesh")
    return tuple(allocation.primary_position_bounds(mesh.get("primaryVertices")))


def pixel_center(
    value: float, *, maximum_residual_ulps: float = 1.0
) -> tuple[int, float, float]:
    nearest = round(value)
    residual = value - nearest
    residual_ulps = residual / math.ulp(float(nearest))
    if abs(residual_ulps) > maximum_residual_ulps:
        raise ValueError(
            "target center exceeds the permitted binary64-ULP distance from a pixel"
        )
    return nearest, residual, residual_ulps


def response_runs(
    values: Sequence[tuple[int, tuple[float, ...]]],
) -> list[dict[str, Any]]:
    return prior.response_runs(values)


def transition_brackets(runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return prior.transition_brackets(runs)


def analyze(
    timeline_path: Path, validator_result_path: Path, *, run_id: int
) -> dict[str, Any]:
    if run_id <= 0:
        raise ValueError("run ID must be positive")
    result = holdout.mapping(
        json.loads(validator_result_path.read_text(encoding="utf-8")),
        "fine-scan validator result",
    )
    conclusion = holdout.mapping(result.get("conclusion"), "validator conclusion")
    if (
        result.get("dynamicAllocationSurvivingPathThresholdResultSchemaVersion")
        != 2
        or result.get("captureEvidenceSchemaVersion") != 3
        or result.get("classification") != surviving.FINE_SCAN_CLASSIFICATION
        or conclusion.get("captureIntegrityPassed") is not True
        or conclusion.get("productionShaderAuthorized") is not False
        or result.get("timelineSHA256") != holdout.sha256_file(timeline_path)
    ):
        raise ValueError("fine-scan validator result or timeline differs")
    timeline = holdout.mapping(
        json.loads(timeline_path.read_text(encoding="utf-8")), "transition timeline"
    )
    geometry = holdout.mapping(timeline.get("geometry"), "geometry")
    uniforms = holdout.mapping(
        timeline.get("dynamicBackgroundUniforms"), "dynamic background uniforms"
    )
    evidence = holdout.mapping(
        uniforms.get("pathIsolationInterventions"), "fine-scan evidence"
    )
    if evidence.get("schemaVersion") != 3:
        raise ValueError("fine-scan evidence schema differs")
    raw_records = [
        holdout.mapping(value, "raw fine-scan record")
        for value in fixed.sequence(evidence.get("records"), "raw fine-scan records")
    ]
    validated_records = [
        holdout.mapping(value, "validated fine-scan record")
        for value in fixed.sequence(result.get("records"), "validated records")
    ]
    if len(raw_records) != 106 or len(validated_records) != 106:
        raise ValueError("fine-scan record count differs")

    raw_by_index = {int(record["recordIndex"]): record for record in raw_records}
    validated_by_index = {
        int(record["recordIndex"]): record for record in validated_records
    }
    if set(raw_by_index) != set(validated_by_index) or len(raw_by_index) != 106:
        raise ValueError("fine-scan record indices differ")

    source_states: dict[int, dict[str, Any]] = {}
    candidate_edges: dict[int, tuple[float, ...]] = {}
    for sample in surviving.EXPECTED_SOURCE_SAMPLE_INDICES:
        base = next(
            record
            for record in validated_records
            if int(record["sampleIndex"]) == sample
            and record.get("phase") == "control"
        )
        raw_base = raw_by_index[int(base["recordIndex"])]
        before = holdout.mapping(
            raw_base.get("liveRenderBoundaryBefore"), "base live boundary"
        )
        states = fixed.sequence(before.get("layerStates"), "base live states")
        carrier = layer_at_path(states, CARRIER_PATH)
        target = layer_at_path(states, TARGET_PATH)
        carrier_position = tuple(
            holdout.numeric(value, "carrier position")
            for value in fixed.sequence(carrier.get("position"), "carrier position")
        )
        carrier_bounds = tuple(
            holdout.numeric(value, "carrier bounds")
            for value in fixed.sequence(carrier.get("bounds"), "carrier bounds")
        )
        target_position = tuple(
            holdout.numeric(value, "target position")
            for value in fixed.sequence(target.get("position"), "target position")
        )
        target_bounds = tuple(
            holdout.numeric(value, "target bounds")
            for value in fixed.sequence(target.get("bounds"), "target bounds")
        )
        if (
            len(carrier_position) != 2
            or len(carrier_bounds) != 4
            or len(target_position) != 2
            or len(target_bounds) != 4
        ):
            raise ValueError("fine-scan source geometry is malformed")
        target_radius = holdout.numeric(
            target.get("cornerRadius"), "target corner radius"
        )
        target_center = tuple(value + target_radius for value in target_position)
        target_pixel_details = tuple(pixel_center(value) for value in target_center)
        target_pixel_center = tuple(value[0] for value in target_pixel_details)
        scale = holdout.numeric(base.get("runtimeScale"), "runtime scale")
        bounds = allocation.allocation_bounds(geometry, carrier_position)
        candidate = tuple(
            float(value)
            for value in allocation.quad4_primary_bounds_candidate(
                bounds, scale=scale
            )
        )
        observed_base = primary_edges(
            holdout.mapping(base.get("observed"), "base observed policy")
        )
        correction = tuple(
            observed - predicted
            for observed, predicted in zip(observed_base, candidate, strict=True)
        )
        candidate_edges[sample] = candidate
        source_states[sample] = {
            "sampleIndex": sample,
            "remaining": base["remaining"],
            "runtimeScale": scale,
            "carrierBounds": list(carrier_bounds),
            "carrierPosition": list(carrier_position),
            "targetBounds": list(target_bounds),
            "targetPosition": list(target_position),
            "targetCornerRadius": target_radius,
            "targetCenter": list(target_center),
            "targetPixelCenter": list(target_pixel_center),
            "targetCenterResidual": [value[1] for value in target_pixel_details],
            "targetCenterResidualULPs": [value[2] for value in target_pixel_details],
            "candidateEdges": list(candidate),
            "observedBaseEdges": list(observed_base),
            "baseCorrection": list(correction),
        }

    corrections: dict[tuple[int, str], list[tuple[int, tuple[float, ...]]]] = (
        defaultdict(list)
    )
    center_corrections: dict[
        tuple[int, str], list[tuple[int, tuple[float, ...]]]
    ] = defaultdict(list)
    signed_corrections: Counter[tuple[str, float]] = Counter()
    corrected_components = 0
    corrected_records = 0
    maximum_target_center_residual_ulps = 0.0
    record_corrections: list[dict[str, Any]] = []
    for record_index in sorted(validated_by_index):
        record = validated_by_index[record_index]
        raw = raw_by_index[record_index]
        sample = int(record["sampleIndex"])
        observed = holdout.mapping(record.get("observed"), "observed policy")
        edges = primary_edges(observed)
        correction = tuple(
            actual - predicted
            for actual, predicted in zip(
                edges, candidate_edges[sample], strict=True
            )
        )
        changed = sum(value != 0 for value in correction)
        corrected_components += changed
        corrected_records += changed > 0
        for name, value in zip(allocation.EDGE_NAMES, correction, strict=True):
            if value:
                signed_corrections[(name, value)] += 1
        translation = tuple(
            int(value)
            for value in fixed.sequence(record.get("translation"), "translation")
        )
        before = holdout.mapping(
            raw.get("liveRenderBoundaryBefore"), "record live boundary"
        )
        target = layer_at_path(
            fixed.sequence(before.get("layerStates"), "record live states"),
            TARGET_PATH,
        )
        target_position = tuple(
            holdout.numeric(value, "target position")
            for value in fixed.sequence(target.get("position"), "target position")
        )
        target_bounds = tuple(
            holdout.numeric(value, "target bounds")
            for value in fixed.sequence(target.get("bounds"), "target bounds")
        )
        target_radius = holdout.numeric(
            target.get("cornerRadius"), "target corner radius"
        )
        target_center = tuple(value + target_radius for value in target_position)
        target_pixel_details = tuple(pixel_center(value) for value in target_center)
        target_pixel_center = tuple(value[0] for value in target_pixel_details)
        maximum_target_center_residual_ulps = max(
            maximum_target_center_residual_ulps,
            *(abs(value[2]) for value in target_pixel_details),
        )
        carrier_bounds = source_states[sample]["carrierBounds"]
        overhang = {
            "xLower": -target_position[0],
            "yLower": -target_position[1],
            "xUpper": target_position[0]
            + target_bounds[2]
            - carrier_bounds[2],
            "yUpper": target_position[1]
            + target_bounds[3]
            - carrier_bounds[3],
        }
        phase = str(record["phase"])
        if phase != "control":
            if (translation[0] == 0) == (translation[1] == 0):
                raise ValueError("fine-scan translation is not one-axis nonzero")
            axis = "x" if translation[0] else "y"
            axis_index = 0 if axis == "x" else 1
            value = translation[0] if translation[0] else translation[1]
            corrections[(sample, axis)].append((value, correction))
            center_value = target_pixel_center[axis_index]
            source_center = source_states[sample]["targetPixelCenter"][axis_index]
            if center_value != source_center + value:
                raise ValueError("target center does not equal base plus translation")
            center_corrections[(sample, axis)].append((center_value, correction))
        record_corrections.append(
            {
                "recordIndex": record_index,
                "sampleIndex": sample,
                "phase": phase,
                "translation": list(translation),
                "targetPosition": list(target_position),
                "targetCenter": list(target_center),
                "targetPixelCenter": list(target_pixel_center),
                "targetCenterResidual": [
                    value[1] for value in target_pixel_details
                ],
                "targetCenterResidualULPs": [
                    value[2] for value in target_pixel_details
                ],
                "targetOverhang": overhang,
                "observedEdges": list(edges),
                "candidateEdges": list(candidate_edges[sample]),
                "candidateCorrection": list(correction),
            }
        )

    scan_groups: list[dict[str, Any]] = []
    for sample in surviving.EXPECTED_SOURCE_SAMPLE_INDICES:
        for axis_index, axis in enumerate(("x", "y")):
            values = corrections[(sample, axis)]
            expected_values = surviving.SCAN_VALUES_BY_SAMPLE[sample][axis_index]
            if tuple(sorted(value for value, _ in values)) != tuple(expected_values):
                raise ValueError(f"normalized scan {sample}/{axis} values differ")
            runs = response_runs(values)
            center_runs = response_runs(center_corrections[(sample, axis)])
            scan_groups.append(
                {
                    "sampleIndex": sample,
                    "axis": axis,
                    "sampledValueCount": len(values),
                    "distinctCorrectionCount": len(
                        {correction for _, correction in values}
                    ),
                    "runs": runs,
                    "transitionBrackets": transition_brackets(runs),
                    "targetPixelCenterRuns": center_runs,
                    "targetPixelCenterTransitionBrackets": transition_brackets(
                        center_runs
                    ),
                }
            )

    base_exact_count = sum(
        not any(state["baseCorrection"]) for state in source_states.values()
    )
    state25_center_bracket_pairs = [
        [
            (
                int(bracket["lowerObservedValue"]),
                int(bracket["upperObservedValue"]),
            )
            for bracket in group["targetPixelCenterTransitionBrackets"]
        ]
        for group in scan_groups
        if group["sampleIndex"] == 25
    ]
    shared_state25_center_bracket = (
        {
            "lowerObservedValue": state25_center_bracket_pairs[0][0][0],
            "upperObservedValue": state25_center_bracket_pairs[0][0][1],
        }
        if len(state25_center_bracket_pairs) == 2
        and len(state25_center_bracket_pairs[0]) == 1
        and state25_center_bracket_pairs[0] == state25_center_bracket_pairs[1]
        else None
    )
    return {
        "dynamicAllocationPrimaryMeshNormalizedResponseAnalysisSchemaVersion": 1,
        "classification": CLASSIFICATION,
        "runID": run_id,
        "inputTimelineArtifact": timeline_path.parent.name
        + "/"
        + timeline_path.name,
        "inputTimelineSHA256": holdout.sha256_file(timeline_path),
        "inputValidatorResultArtifact": validator_result_path.parent.name
        + "/"
        + validator_result_path.name,
        "inputValidatorResultSHA256": holdout.sha256_file(validator_result_path),
        "aggregate": {
            "recordCount": len(record_corrections),
            "edgeComponentCount": len(record_corrections) * len(allocation.EDGE_NAMES),
            "nonzeroCandidateCorrectionComponentCount": corrected_components,
            "nonzeroCandidateCorrectionRecordCount": corrected_records,
            "signedCandidateCorrectionCounts": {
                f"{name}:{value:+g}": count
                for (name, value), count in sorted(signed_corrections.items())
            },
            "sourceStateCount": len(source_states),
            "naturalBaseCandidateExactCount": base_exact_count,
            "scanGroupCount": len(scan_groups),
            "maximumTargetCenterResidualULPs": (
                maximum_target_center_residual_ulps
            ),
            "sample25SharedTargetPixelCenterTransitionBracket": (
                shared_state25_center_bracket
            ),
        },
        "sourceStates": [source_states[sample] for sample in sorted(source_states)],
        "scanGroups": scan_groups,
        "recordCorrections": record_corrections,
        "conclusion": {
            "liveCarrierNormalizationApplied": True,
            "everyCapturedTargetCenterWithinOneBinary64ULPOfInteger": (
                maximum_target_center_residual_ulps <= 1.0
            ),
            "sample25AxesShare335To336PixelCenterBracket": (
                shared_state25_center_bracket is not None
                and shared_state25_center_bracket["lowerObservedValue"] == 335
                and shared_state25_center_bracket["upperObservedValue"] == 336
            ),
            "independentProducerMeshPolicyRecovered": False,
            "requiresExactKAndGeometryTransfer": True,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("validator_result", type=Path)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = analyze(
        arguments.timeline, arguments.validator_result, run_id=arguments.run_id
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
