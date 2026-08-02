#!/usr/bin/env python3
"""Audit failed selected-region run 30765781334 without promoting it."""

from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_dynamic_allocation_surviving_path_threshold as surviving
import validate_transition_input_clamp_probe as input_clamp


EXPECTED_RUN_ID = 30_765_781_334
EXPECTED_HEAD_SHA = "ddbd6dfa13fe5cee468acd378e3cdc3acd94fd12"
EXPECTED_TIMELINE_SHA256 = (
    "9ddd7b312105f97c516cc25707cd633629df964bbf16160301924cff4d5b49fd"
)
EXPECTED_GATE_ERROR = "capture_backdrop operand capture count differs at 31/9"
EXPECTED_MISSING_RECORD_INDEX = 9
EXPECTED_REPEAT_RECORD_INDEX = 94
EXPECTED_HANDLE_COUNTS = {
    0x00C7_00AC_050A_0A31: 14,
    0x00C7_00AD_0508_0A31: 8,
    0x00C7_00AD_050A_0A31: 7,
    0x00C8_00AD_0506_0A29: 1,
    0x00C8_00AD_0506_0A2D: 29,
    0x00C8_00AD_0508_0A31: 14,
    0x00C8_00AE_0504_0A29: 1,
    0x00C8_00AE_0506_0A29: 38,
    0x00C9_00AE_0504_0A29: 1,
}
EXPECTED_RECT_COUNTS = {
    (199, 172, 645, 652): 14,
    (199, 173, 644, 652): 8,
    (199, 173, 645, 652): 7,
    (200, 173, 643, 650): 1,
    (200, 173, 643, 651): 29,
    (200, 173, 644, 652): 14,
    (200, 174, 642, 650): 1,
    (200, 174, 643, 650): 38,
    (201, 174, 642, 650): 1,
}
EXPECTED_OWNER_MISMATCH_RECORDS = (7, 38, 79)
EXPECTED_REPEAT_RAW_DIFFERENCES = {
    "interventionIndex",
    "interventionName",
    "phase",
    "recordIndex",
    "render",
    "renderAttempts",
}
EXPECTED_REPEAT_MESH_DIFFERENCES = {
    "fragmentFunction",
    "mvpPayloadSHA256",
    "vertexPayloadSHA256",
}
CLASSIFICATION = (
    "post-opening-audit-of-failed-preregistered-capture-backdrop-selected-"
    "region-replay; not-a-prospective-pass-public-crop-policy-or-parity-claim"
)


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} differs")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label} differs")
    return value


def differing_keys(left: Mapping[str, Any], right: Mapping[str, Any]) -> set[str]:
    if left.keys() != right.keys():
        raise ValueError("repeat record key inventory differs")
    return {key for key in left if left[key] != right[key]}


def operand_payloads_and_strip(
    report: dict[str, Any],
) -> tuple[list[Mapping[str, Any] | None], list[Mapping[str, Any]]]:
    uniforms = mapping(report.get("dynamicBackgroundUniforms"), "uniform evidence")
    evidence = mapping(
        uniforms.get("pathIsolationInterventions"), "path-isolation evidence"
    )
    if evidence.get("schemaVersion") != 6:
        raise ValueError("selected-region evidence schema differs")
    raw_records = [
        mapping(record, "raw path-isolation record")
        for record in sequence(evidence.get("records"), "raw path-isolation records")
    ]
    payloads: list[Mapping[str, Any] | None] = []
    for raw_record in raw_records:
        render = mapping(raw_record.get("render"), "raw render")
        retained = mapping(render.get("metalBufferSnapshots"), "retained Metal buffers")
        record_payloads = []
        for untyped_snapshot in sequence(
            retained.get("snapshots"), "retained snapshots"
        ):
            snapshot = mapping(untyped_snapshot, "retained snapshot")
            if "captureBackdropOperands" in snapshot:
                record_payloads.append(
                    mapping(
                        snapshot.pop("captureBackdropOperands"),
                        "capture_backdrop operands",
                    )
                )
        if len(record_payloads) > 1:
            raise ValueError("multiple selected-region operands in one record")
        payloads.append(record_payloads[0] if record_payloads else None)
    evidence["schemaVersion"] = 4
    return payloads, raw_records


def observed_primary_bits(mesh: Mapping[str, Any]) -> tuple[list[int], list[int]]:
    vertices = [
        sequence(vertex, "primary vertex")
        for vertex in sequence(mesh.get("primaryVertices"), "primary vertices")
    ]
    if len(vertices) != 4 or any(len(vertex) < 6 for vertex in vertices):
        raise ValueError("primary producer vertices differ")
    position = [
        surviving.holdout.float32_bits(
            surviving.holdout.numeric(component, "primary position component")
        )
        for vertex in vertices
        for component in vertex[:2]
    ]
    source = [
        surviving.holdout.float32_bits(
            surviving.holdout.numeric(component, "primary source component")
        )
        for vertex in vertices
        for component in vertex[4:6]
    ]
    return position, source


def analyze(timeline_path: Path, *, run_id: int, head_sha: str) -> dict[str, Any]:
    if run_id != EXPECTED_RUN_ID or head_sha != EXPECTED_HEAD_SHA:
        raise ValueError("failed-run identity differs")
    timeline_sha = surviving.holdout.sha256_file(timeline_path)
    if timeline_sha != EXPECTED_TIMELINE_SHA256:
        raise ValueError("failed-run timeline digest differs")

    try:
        surviving.validate(timeline_path)
    except ValueError as error:
        if str(error) != EXPECTED_GATE_ERROR:
            raise ValueError("frozen selected-region gate error differs") from error
    else:
        raise ValueError("failed selected-region run unexpectedly passes")

    clamp_result = input_clamp.validate(timeline_path)
    clamp_aggregate = mapping(clamp_result.get("aggregate"), "inputClamp aggregate")
    if (
        clamp_aggregate.get("sampleCount") != 32
        or clamp_aggregate.get("recoveredTransferCandidate")
        != "float-weighted-mix/affine-expanded-base-darwin-powf"
        or clamp_aggregate.get("recoveredTransferCandidateExact") is not True
    ):
        raise ValueError("inputClamp side gate differs")

    report = json.loads(timeline_path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("transition report differs")
    payloads, raw_records = operand_payloads_and_strip(report)
    missing_indices = [
        index for index, payload in enumerate(payloads) if payload is None
    ]
    if missing_indices != [EXPECTED_MISSING_RECORD_INDEX] or len(payloads) != 114:
        raise ValueError("failed-run operand inventory differs")

    missing_record = raw_records[EXPECTED_MISSING_RECORD_INDEX]
    repeat_record = raw_records[EXPECTED_REPEAT_RECORD_INDEX]
    if (
        missing_record.get("recordIndex") != EXPECTED_MISSING_RECORD_INDEX
        or missing_record.get("sampleIndex") != 31
        or missing_record.get("interventionIndex") != 9
        or missing_record.get("interventionName")
        != "sample31-unit-1-0-1-0-0-0-0-position-x-negative-4"
        or missing_record.get("translation") != [-4, 0]
        or repeat_record.get("recordIndex") != EXPECTED_REPEAT_RECORD_INDEX
        or repeat_record.get("translation") != [-4, 0]
        or differing_keys(missing_record, repeat_record)
        != EXPECTED_REPEAT_RAW_DIFFERENCES
    ):
        raise ValueError("missing-record same-state repeat differs")

    with tempfile.TemporaryDirectory() as directory:
        baseline_path = Path(directory) / "transition-timeline-schema4.json"
        baseline_path.write_text(
            json.dumps(report, separators=(",", ":"), allow_nan=False),
            encoding="utf-8",
        )
        baseline = surviving.validate(baseline_path)
    baseline_aggregate = mapping(baseline.get("aggregate"), "baseline aggregate")
    baseline_records = [
        mapping(record, "baseline record")
        for record in sequence(baseline.get("records"), "baseline records")
    ]
    if len(baseline_records) != 114:
        raise ValueError("corrected baseline record count differs")
    baseline_by_index = {
        int(record.get("recordIndex", -1)): record for record in baseline_records
    }
    if len(baseline_by_index) != 114:
        raise ValueError("corrected baseline record identity differs")

    handle_counts: Counter[int] = Counter()
    rect_counts: Counter[tuple[int, ...]] = Counter()
    context_scale_bits: set[int] = set()
    renderer_scale_bits: set[int] = set()
    renderer_control_hex: set[str] = set()
    origin_values: set[tuple[int, ...]] = set()
    origin_bounds_values: set[tuple[int, ...]] = set()
    owner_270_pointer_values: set[int] = set()
    owner_mismatch_records: list[dict[str, Any]] = []
    selected_equals_owner_248 = 0
    selected_equals_owner_270 = 0
    selected_intersection_count = 0
    position_components = 0
    source_components = 0

    for record_index, payload in enumerate(payloads):
        if payload is None:
            continue
        operands = surviving.validate_capture_backdrop_operands(payload)
        baseline_record = baseline_by_index[record_index]
        observed = mapping(baseline_record.get("observed"), "baseline observation")
        mesh = mapping(observed.get("producerMesh"), "baseline producer mesh")
        observed_position, observed_source = observed_primary_bits(mesh)
        predicted_position = list(operands["predictedPrimaryPositionBits"])
        predicted_source = list(operands["predictedPrimarySourceBits"])
        if (
            predicted_position != observed_position
            or predicted_source != observed_source
        ):
            raise ValueError("retained operand primary replay differs")
        position_components += len(predicted_position)
        source_components += len(predicted_source)

        region_handle = int(operands["regionHandle"])
        owner_248 = int(operands["ownerRegion248"])
        owner_270 = int(operands["ownerRegion270"])
        handle_counts[region_handle] += 1
        rect_counts[tuple(operands["selectedRegionRect"])] += 1
        context_scale_bits.add(int(operands["scaleBits"]))
        renderer_scale_bits.add(int(operands["rendererScaleBits"]))
        renderer_control_hex.add(str(operands["rendererRegionControlHex"]))
        origin_values.add(tuple(operands["origin"]))
        origin_bounds_values.add(tuple(operands["originBounds"]))
        selected_intersection_count += bool(operands["selectedRegionWasIntersected"])
        selected_equals_owner_248 += region_handle == owner_248
        selected_equals_owner_270 += region_handle == owner_270
        if owner_248 != owner_270:
            raw_record = raw_records[record_index]
            owner_270_class = "packed" if owner_270 & 1 else "pointer"
            if owner_270_class == "pointer":
                owner_270_pointer_values.add(owner_270)
            owner_mismatch_records.append(
                {
                    "recordIndex": record_index,
                    "interventionIndex": raw_record.get("interventionIndex"),
                    "interventionName": raw_record.get("interventionName"),
                    "translation": raw_record.get("translation"),
                    "selectedAndOwner248": f"0x{region_handle:016x}",
                    "owner270Class": owner_270_class,
                    **(
                        {"owner270": f"0x{owner_270:016x}"}
                        if owner_270_class == "packed"
                        else {"owner270PointerValueRetainedInArtifactOnly": True}
                    ),
                }
            )

    missing_mesh = mapping(
        mapping(
            baseline_by_index[EXPECTED_MISSING_RECORD_INDEX].get("observed"),
            "missing observation",
        ).get("producerMesh"),
        "missing producer mesh",
    )
    repeat_mesh = mapping(
        mapping(
            baseline_by_index[EXPECTED_REPEAT_RECORD_INDEX].get("observed"),
            "repeat observation",
        ).get("producerMesh"),
        "repeat producer mesh",
    )
    repeat_mesh_differences = differing_keys(missing_mesh, repeat_mesh)

    q = mapping(baseline_aggregate.get("primaryProducerSourceQ"), "baseline source-q")
    allocation = mapping(
        baseline_aggregate.get("allocationInvariants"), "baseline allocation"
    )
    if (
        handle_counts != Counter(EXPECTED_HANDLE_COUNTS)
        or rect_counts != Counter(EXPECTED_RECT_COUNTS)
        or context_scale_bits != {0x3F03_E138}
        or renderer_scale_bits != {0x3FF0_0000_0000_0000}
        or renderer_control_hex != {"01000000000000000000000000000000"}
        or origin_values != {(0, 0)}
        or origin_bounds_values != {(0, 0, 1024, 1024)}
        or selected_intersection_count != 0
        or selected_equals_owner_248 != 113
        or selected_equals_owner_270 != 110
        or tuple(item["recordIndex"] for item in owner_mismatch_records)
        != EXPECTED_OWNER_MISMATCH_RECORDS
        or len(owner_270_pointer_values) != 1
        or position_components != 904
        or source_components != 904
        or q != {"componentCount": 912, "exact": True, "mismatchedComponents": 0}
        or allocation
        != {"componentCount": 1596, "exact": True, "mismatchedComponents": 0}
        or repeat_mesh_differences != EXPECTED_REPEAT_MESH_DIFFERENCES
    ):
        raise ValueError("failed-run selected-region audit differs")

    return {
        "dynamicAllocationCaptureBackdropSelectedRegionFailedRunAnalysisSchemaVersion": 1,
        "classification": CLASSIFICATION,
        "runID": run_id,
        "headSHA": head_sha,
        "workflowConclusion": "failure",
        "frozenGateError": EXPECTED_GATE_ERROR,
        "prospectiveGatePassed": False,
        "inputTimelineArtifact": timeline_path.parent.name + "/" + timeline_path.name,
        "inputTimelineSHA256": timeline_sha,
        "aggregate": {
            "recordCount": 114,
            "completeLiveOperandCaptureCount": 113,
            "missingLiveOperandCaptureCount": 1,
            "baselinePrimarySourceQ": dict(q),
            "baselineAllocationInvariants": dict(allocation),
            "retainedOperandReplay": {
                "primaryPositionComponentCount": position_components,
                "primaryPositionMismatchedComponents": 0,
                "primarySourceComponentCount": source_components,
                "primarySourceMismatchedComponents": 0,
                "selectedRegionConsumedRectangleExactCount": 113,
                "selectedRegionIntersectionCount": selected_intersection_count,
                "selectedEqualsOwner248Count": selected_equals_owner_248,
                "selectedEqualsOwner270Count": selected_equals_owner_270,
                "contextScaleBits": [
                    f"0x{value:08x}" for value in sorted(context_scale_bits)
                ],
                "rendererScaleBits": [
                    f"0x{value:016x}" for value in sorted(renderer_scale_bits)
                ],
                "rendererRegionControlHex": sorted(renderer_control_hex),
                "originValues": [list(value) for value in sorted(origin_values)],
                "originBoundsValues": [
                    list(value) for value in sorted(origin_bounds_values)
                ],
                "allowNumericTolerance": False,
            },
            "selectedRegionHandleFrequency": [
                {"handle": f"0x{handle:016x}", "count": count}
                for handle, count in sorted(handle_counts.items())
            ],
            "selectedRegionRectangleFrequency": [
                {"rect": list(rect), "count": count}
                for rect, count in sorted(rect_counts.items())
            ],
            "ownerRegionMismatches": owner_mismatch_records,
            "owner270PointerMismatchCount": 2,
            "owner270DistinctPointerIdentityCount": len(owner_270_pointer_values),
            "inputClampSideGate": {
                "sampleCount": clamp_aggregate.get("sampleCount"),
                "candidateCount": clamp_aggregate.get("candidateCount"),
                "recoveredTransferCandidate": clamp_aggregate.get(
                    "recoveredTransferCandidate"
                ),
                "recoveredTransferCandidateExact": clamp_aggregate.get(
                    "recoveredTransferCandidateExact"
                ),
            },
        },
        "missingCapture": {
            "recordIndex": EXPECTED_MISSING_RECORD_INDEX,
            "sampleIndex": 31,
            "interventionIndex": 9,
            "interventionName": missing_record.get("interventionName"),
            "translation": missing_record.get("translation"),
            "sameStateRepeatRecordIndex": EXPECTED_REPEAT_RECORD_INDEX,
            "allNonRenderStateFieldsExact": True,
            "drawConsumedPrimaryGeometryExact": True,
            "producerMeshDifferingFields": sorted(repeat_mesh_differences),
            "missingFragmentFunction": missing_mesh.get("fragmentFunction"),
            "repeatFragmentFunction": repeat_mesh.get("fragmentFunction"),
            "classification": (
                "observed callback/provenance gap; the same-state repeat is a "
                "diagnostic and is not substituted for the missing live capture"
            ),
            "bufferReuseCauseProven": False,
        },
        "openedFacts": {
            "selectedRegionHandleClass": "packed-immediate in all 113 captures",
            "packedImmediateDecoder": {
                "x": "signed bits 48..63",
                "y": "signed bits 32..47",
                "width": "bits 17..31",
                "height": "bits 2..16",
            },
            "selectedRegionAlwaysOwner248": True,
            "owner270RequiresIndependentPrefixCapture": True,
        },
        "conclusion": {
            "frozenSelectedRegionGatePassed": False,
            "retrospective113Of114SelectedRegionReplayExact": True,
            "missingCapturePromotedFromRepeat": False,
            "selectedPrivateRegionArithmeticRecoveredForRetainedStates": True,
            "publicLayerStateCropRuleRecovered": False,
            "requiresOwnerRegionConstructionCapture": True,
            "requiresUnseenGeometryTransfer": True,
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
        arguments.timeline,
        run_id=arguments.run_id,
        head_sha=arguments.head_sha,
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
