#!/usr/bin/env python3
"""Audit failed owner-record run 30770107772 without promoting it."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import struct
import tempfile
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_dynamic_allocation_surviving_path_threshold as surviving


EXPECTED_RUN_ID = 30_770_107_772
EXPECTED_HEAD_SHA = "8998bd56f34a749afa599197c153e58600a20d8f"
EXPECTED_TIMELINE_SHA256 = (
    "eb45b13ebbcfd234b76d7d3940ca08df2ee4d2e8e6feb73fde92c916f602f39a"
)
EXPECTED_GATE_ERROR = "capture_backdrop operand capture count differs at 31/0"
EXPECTED_RECORD_COUNT = 114
EXPECTED_CALLBACK_ATTEMPT_COUNT = 342
EXPECTED_PARTIAL_READ_MASK = "0x005fffff"
EXPECTED_REQUIRED_READ_MASK = "0x007fffff"
PREVIOUS_REQUIRED_READ_MASK = "0x000fffff"
OWNER_RECORD_BEGIN_OFFSET = 0x50
OWNER_RECORD_END_OFFSET = 0x58
FALSIFIED_CAPACITY_OFFSET = 0x60
OWNER_RECORD_BYTE_COUNT = 0xD0
CAPTURE_BACKDROP_BEGIN_END_LOAD_OFFSET = 0x34C
CAPTURE_BACKDROP_BEGIN_END_LOAD_WORD = 0xA945_229C
CLASSIFICATION = (
    "post-opening-audit-of-failed-preregistered-capture-backdrop-owner-record-"
    "vector-replay; not-a-prospective-pass-public-crop-policy-or-parity-claim"
)


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} differs")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label} differs")
    return value


def serialized_empty_vector(partial: Mapping[str, Any]) -> None:
    record = mapping(
        partial.get("ownerRecordVector"),
        "failed owner-record vector",
    )
    payload = surviving.hexadecimal_bytes(record, "failed owner-record vector")
    if (
        record.get("class") != "bounded owner 0xd0-byte record vector"
        or record.get("lengthBytes") != 0
        or payload
        or record.get("sha256") != hashlib.sha256(b"").hexdigest()
    ):
        raise ValueError("failed owner-record vector metadata differs")


def capture_backdrop_code(record: Mapping[str, Any]) -> bytes:
    render = mapping(record.get("render"), "code render")
    retained = mapping(render.get("metalBufferSnapshots"), "code buffers")
    call_sites = [
        mapping(snapshot, "code snapshot")["producerGeometryCallSite"]
        for snapshot in sequence(retained.get("snapshots"), "code snapshots")
        if "producerGeometryCallSite" in mapping(snapshot, "code snapshot")
    ]
    if len(call_sites) != 1:
        raise ValueError("producer call-site inventory differs")
    frames = sequence(
        mapping(call_sites[0], "producer call site").get("frames"),
        "producer call-site frames",
    )
    matching = [
        mapping(frame, "producer frame")
        for frame in frames
        if mapping(frame, "producer frame").get("symbol")
        == surviving.CAPTURE_BACKDROP_SYMBOL
    ]
    if len(matching) != 1:
        raise ValueError("capture_backdrop frame inventory differs")
    capture = mapping(matching[0].get("captureBackdropCode"), "capture_backdrop code")
    return surviving.hexadecimal_bytes(capture, "capture_backdrop code")


def schema_three_copy(partial: Mapping[str, Any]) -> dict[str, Any]:
    operands = copy.deepcopy(dict(partial))
    operands.update(
        {
            "schemaVersion": 3,
            "completeRead": True,
            "readMask": PREVIOUS_REQUIRED_READ_MASK,
            "requiredReadMask": PREVIOUS_REQUIRED_READ_MASK,
        }
    )
    return operands


def analyze(timeline_path: Path, *, run_id: int, head_sha: str) -> dict[str, Any]:
    if run_id != EXPECTED_RUN_ID or head_sha != EXPECTED_HEAD_SHA:
        raise ValueError("failed owner-record run identity differs")
    timeline_sha = surviving.holdout.sha256_file(timeline_path)
    if timeline_sha != EXPECTED_TIMELINE_SHA256:
        raise ValueError("failed owner-record timeline digest differs")

    try:
        surviving.validate(timeline_path)
    except ValueError as error:
        if str(error) != EXPECTED_GATE_ERROR:
            raise ValueError("frozen owner-record gate error differs") from error
    else:
        raise ValueError("failed owner-record run unexpectedly passes")

    report = json.loads(timeline_path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("transition report differs")
    uniforms = mapping(report.get("dynamicBackgroundUniforms"), "uniform evidence")
    evidence = mapping(
        uniforms.get("pathIsolationInterventions"),
        "path-isolation evidence",
    )
    records = [
        mapping(value, "path-isolation record")
        for value in sequence(evidence.get("records"), "path-isolation records")
    ]
    if evidence.get("schemaVersion") != 8 or len(records) != EXPECTED_RECORD_COUNT:
        raise ValueError("failed owner-record evidence inventory differs")

    callback_attempt_count = 0
    partial_attempt_count = 0
    partial_mask_counts: Counter[str] = Counter()
    begin_end_span_counts: Counter[int] = Counter()
    owner_prefix_hashes: set[str] = set()
    source_window_hashes: set[str] = set()
    word_60_equals_begin_count = 0
    embedded_window_count = 0

    for record_index, record in enumerate(records):
        if record.get("recordIndex") != record_index:
            raise ValueError("failed owner-record order differs")
        render = mapping(record.get("render"), "path-isolation render")
        retained = mapping(render.get("metalBufferSnapshots"), "retained buffers")
        snapshots = [
            mapping(value, "retained snapshot")
            for value in sequence(retained.get("snapshots"), "retained snapshots")
        ]
        if any("captureBackdropOperands" in snapshot for snapshot in snapshots):
            raise ValueError("failed run unexpectedly retained complete operands")
        attempts = [
            mapping(snapshot["captureBackdropOperandAttempt"], "callback attempt")
            for snapshot in snapshots
            if "captureBackdropOperandAttempt" in snapshot
        ]
        summaries = [
            surviving.validate_capture_backdrop_operand_attempt(attempt)
            for attempt in attempts
        ]
        if [summary["attemptIndex"] for summary in summaries] != [0, 1, 2]:
            raise ValueError("failed owner-record callback inventory differs")
        callback_attempt_count += len(summaries)
        partials = [
            mapping(attempt["partialOperands"], "partial operands")
            for attempt in attempts
            if "partialOperands" in attempt
        ]
        if len(partials) != 1 or "partialReadMask" not in summaries[0]:
            raise ValueError("failed owner-record partial inventory differs")
        partial_attempt_count += 1
        partial = partials[0]
        partial_mask = str(partial.get("readMask"))
        partial_mask_counts[partial_mask] += 1
        if (
            partial.get("schemaVersion") != 4
            or partial.get("completeRead") is not False
            or partial_mask != EXPECTED_PARTIAL_READ_MASK
            or partial.get("requiredReadMask") != EXPECTED_REQUIRED_READ_MASK
            or partial.get("ownerRecordOffsets")
            != {
                "begin": OWNER_RECORD_BEGIN_OFFSET,
                "end": OWNER_RECORD_END_OFFSET,
                "capacity": FALSIFIED_CAPACITY_OFFSET,
                "recordByteCount": OWNER_RECORD_BYTE_COUNT,
            }
        ):
            raise ValueError("failed owner-record partial metadata differs")

        owner_prefix = surviving.capture_backdrop_operand_bytes(
            partial,
            "ownerObjectPrefix",
        )
        source_window = surviving.capture_backdrop_operand_bytes(
            partial,
            "sourceStateWindow",
        )
        owner_window = surviving.capture_backdrop_operand_bytes(
            partial,
            "ownerRegionWindow",
        )
        serialized_empty_vector(partial)
        begin, end = struct.unpack_from("<2Q", owner_prefix, OWNER_RECORD_BEGIN_OFFSET)
        word_60 = struct.unpack_from("<Q", owner_prefix, FALSIFIED_CAPACITY_OFFSET)[0]
        if begin == 0 or end <= begin:
            raise ValueError("failed owner-record begin/end differs")
        span = end - begin
        begin_end_span_counts[span] += 1
        word_60_equals_begin_count += word_60 == begin
        embedded_window_count += (
            owner_prefix[
                surviving.CAPTURE_BACKDROP_OWNER_REGION_WINDOW_OFFSET : surviving.CAPTURE_BACKDROP_OWNER_REGION_WINDOW_OFFSET
                + surviving.CAPTURE_BACKDROP_REGION_PREFIX_BYTE_COUNT
            ]
            == owner_window
        )
        owner_prefix_hashes.add(hashlib.sha256(owner_prefix).hexdigest())
        source_window_hashes.add(hashlib.sha256(source_window).hexdigest())
        if span != OWNER_RECORD_BYTE_COUNT or len(source_window) != 40:
            raise ValueError("failed owner-record bounded payload differs")

        partial_snapshot = next(
            snapshot
            for snapshot in snapshots
            if mapping(
                snapshot.get("captureBackdropOperandAttempt", {}),
                "candidate callback attempt",
            ).get("partialOperands")
            is partial
        )
        partial_snapshot["captureBackdropOperands"] = schema_three_copy(partial)

    if (
        callback_attempt_count != EXPECTED_CALLBACK_ATTEMPT_COUNT
        or partial_attempt_count != EXPECTED_RECORD_COUNT
        or partial_mask_counts != Counter({EXPECTED_PARTIAL_READ_MASK: 114})
        or begin_end_span_counts != Counter({OWNER_RECORD_BYTE_COUNT: 114})
        or word_60_equals_begin_count != EXPECTED_RECORD_COUNT
        or embedded_window_count != EXPECTED_RECORD_COUNT
    ):
        raise ValueError("failed owner-record aggregate differs")

    code = capture_backdrop_code(records[0])
    instruction = struct.unpack_from(
        "<I",
        code,
        CAPTURE_BACKDROP_BEGIN_END_LOAD_OFFSET,
    )[0]
    if instruction != CAPTURE_BACKDROP_BEGIN_END_LOAD_WORD:
        raise ValueError("capture_backdrop begin/end instruction differs")

    evidence["schemaVersion"] = 7
    evidence["captureBackdropRequiredReadMask"] = PREVIOUS_REQUIRED_READ_MASK
    evidence["method"] = surviving.CAPTURE_BACKDROP_OWNER_REGION_METHOD
    with tempfile.TemporaryDirectory() as directory:
        downgraded_path = Path(directory) / "transition-timeline-schema7.json"
        downgraded_path.write_text(
            json.dumps(report, separators=(",", ":"), allow_nan=False),
            encoding="utf-8",
        )
        downgraded = surviving.validate(downgraded_path)
    baseline = mapping(downgraded.get("aggregate"), "downgraded aggregate")
    operand_replay = mapping(
        baseline.get("captureBackdropOperandReplay"),
        "downgraded operand replay",
    )
    region_replay = mapping(
        baseline.get("captureBackdropConsumedRegionReplay"),
        "downgraded region replay",
    )
    owner_replay = mapping(
        baseline.get("captureBackdropOwnerRegionReplay"),
        "downgraded owner replay",
    )
    if (
        operand_replay.get("captureCount") != EXPECTED_RECORD_COUNT
        or operand_replay.get("primaryPositionMismatchedComponents") != 0
        or operand_replay.get("primarySourceMismatchedComponents") != 0
        or region_replay.get("captureCount") != EXPECTED_RECORD_COUNT
        or region_replay.get("consumedRegionRectExact") is not True
        or owner_replay.get("selectedEqualsOwner248Count") != 114
        or owner_replay.get("selectedEqualsOwner270Count") != 111
        or baseline.get("primaryProducerSourceQ", {}).get("mismatchedComponents") != 0
        or baseline.get("allocationInvariants", {}).get("mismatchedComponents") != 0
    ):
        raise ValueError("downgraded owner-region gate differs")

    return {
        "dynamicAllocationCaptureBackdropOwnerRecordFailedRunAnalysisSchemaVersion": 1,
        "classification": CLASSIFICATION,
        "runID": run_id,
        "headSHA": head_sha,
        "workflowConclusion": "failure",
        "frozenGateError": EXPECTED_GATE_ERROR,
        "prospectiveGatePassed": False,
        "inputTimelineArtifact": timeline_path.parent.name + "/" + timeline_path.name,
        "inputTimelineSHA256": timeline_sha,
        "aggregate": {
            "recordCount": len(records),
            "completeLiveOperandCaptureCount": 0,
            "partialOperandCaptureCount": partial_attempt_count,
            "callbackAttemptCount": callback_attempt_count,
            "partialReadMaskCounts": dict(sorted(partial_mask_counts.items())),
            "ownerObjectPrefixExactCount": len(records),
            "ownerObjectPrefixByteCount": 768,
            "distinctOwnerObjectPrefixCount": len(owner_prefix_hashes),
            "sourceStateWindowExactCount": len(records),
            "sourceStateWindowByteCount": 40,
            "distinctSourceStateWindowCount": len(source_window_hashes),
            "retainedOwnerRecordVectorCount": 0,
            "beginEndSpanByteCounts": {
                str(key): value for key, value in sorted(begin_end_span_counts.items())
            },
            "ownerWord60EqualsBeginCount": word_60_equals_begin_count,
            "ownerRegionWindowEmbeddedInPrefixCount": embedded_window_count,
            "downgradedOwnerRegionGate": {
                "primaryPositionComponentCount": operand_replay[
                    "primaryPositionComponentCount"
                ],
                "primaryPositionMismatchedComponents": operand_replay[
                    "primaryPositionMismatchedComponents"
                ],
                "primarySourceComponentCount": operand_replay[
                    "primarySourceComponentCount"
                ],
                "primarySourceMismatchedComponents": operand_replay[
                    "primarySourceMismatchedComponents"
                ],
                "selectedRegionConsumedRectangleExactCount": region_replay[
                    "captureCount"
                ],
                "owner248HandleClassCounts": owner_replay["owner248HandleClassCounts"],
                "owner270HandleClassCounts": owner_replay["owner270HandleClassCounts"],
                "selectedEqualsOwner248Count": owner_replay[
                    "selectedEqualsOwner248Count"
                ],
                "selectedEqualsOwner270Count": owner_replay[
                    "selectedEqualsOwner270Count"
                ],
                "primarySourceQ": baseline["primaryProducerSourceQ"],
                "allocationInvariants": baseline["allocationInvariants"],
                "allowNumericTolerance": False,
            },
        },
        "openedFacts": {
            "captureBackdropSymbolPrefixSHA256": (
                surviving.CAPTURE_BACKDROP_EXPECTED_SYMBOL_PREFIX_SHA256
            ),
            "beginEndLoadInstructionOffset": (CAPTURE_BACKDROP_BEGIN_END_LOAD_OFFSET),
            "beginEndLoadInstructionWord": (
                f"0x{CAPTURE_BACKDROP_BEGIN_END_LOAD_WORD:08x}"
            ),
            "beginEndLoadInstruction": "ldp x28, x8, [x20, #0x50]",
            "instructionProvenOwnerRecordOffsets": [
                OWNER_RECORD_BEGIN_OFFSET,
                OWNER_RECORD_END_OFFSET,
            ],
            "falsifiedCapacityOffset": FALSIFIED_CAPACITY_OFFSET,
            "falsifiedGuard": "owner[+0x60] >= owner[+0x58]",
            "observedOwnerWord60EqualsBeginEveryState": True,
            "observedRecordCountEveryState": 1,
        },
        "conclusion": {
            "frozenOwnerRecordGatePassed": False,
            "failureIsolatedToUnprovenCapacityGuard": True,
            "previousOwnerRegionGateReplaysExactly": True,
            "ownerRecordVectorCaptured": False,
            "requiresInstructionProvenBeginEndRetry": True,
            "publicLayerStateCropRuleRecovered": False,
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
    rendered = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(rendered, end="")
    else:
        arguments.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
