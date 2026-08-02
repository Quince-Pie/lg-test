#!/usr/bin/env python3
"""Open the prospectively passing dual-owner capture from run 30767931920."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_dynamic_allocation_surviving_path_threshold as surviving


EXPECTED_RUN_ID = 30_767_931_920
EXPECTED_HEAD_SHA = "cab92e1411947cf6dc96313e6a343a7019994b0e"
EXPECTED_TIMELINE_SHA256 = (
    "7cf61e1fdb009d00d8cd7446d407193779f3431dc148551e984541064198dc0d"
)
EXPECTED_CAPTURE_BACKDROP_SHA256 = (
    "14f25960556bec9e88ba8ade176ee7f1d39b84726226ade3eb1b0f1be00b70d2"
)
EXPECTED_MISMATCH_RECORDS = (7, 38, 79)
EXPECTED_POINTER_RECORDS = (7, 38)
EXPECTED_POINTER_RECTANGLES = {
    7: ((200, 173, 642, 8), (200, 181, 643, 643)),
    38: ((201, 173, 642, 8), (200, 181, 643, 643)),
}
EXPECTED_HANDLE_COUNTS = {
    0x00C7_00AC_0508_0A35: 8,
    0x00C7_00AC_050A_0A31: 14,
    0x00C7_00AD_050A_0A31: 5,
    0x00C8_00AC_0508_0A35: 14,
    0x00C8_00AD_0504_0A2D: 1,
    0x00C8_00AD_0506_0A29: 1,
    0x00C8_00AD_0506_0A2D: 68,
    0x00C8_00AE_0506_0A29: 2,
    0x00C9_00AD_0504_0A2D: 1,
}
EXPECTED_RECT_COUNTS = {
    (199, 172, 644, 653): 8,
    (199, 172, 645, 652): 14,
    (199, 173, 645, 652): 5,
    (200, 172, 644, 653): 14,
    (200, 173, 642, 651): 1,
    (200, 173, 643, 650): 1,
    (200, 173, 643, 651): 68,
    (200, 174, 643, 650): 2,
    (201, 173, 642, 651): 1,
}
EXPECTED_CODE_WORDS = {
    0x0358: 0x9108_A28C,  # add x12, x20, #0x228
    0x0378: 0xF940_0E6C,  # ldr x12, [x19, #0x18]
    0x0388: 0x5280_1A11,  # mov w17, #0xd0
    0x03F4: 0xB902_1689,  # str w9, [x20, #0x214]
    0x03F8: 0xB902_1A8A,  # str w10, [x20, #0x218]
    0x03FC: 0xF901_129B,  # str x27, [x20, #0x220]
    0x0408: 0x3DC0_0D20,  # ldr q0, [x9, #0x30]
    0x0410: 0x3D80_0140,  # str q0, [x10]
    0x0414: 0x3DC0_1120,  # ldr q0, [x9, #0x40]
    0x0418: 0x3D80_0540,  # str q0, [x10, #0x10]
    0x17A4: 0x5280_4E08,  # mov w8, #0x270
    0x17A8: 0x5280_4909,  # mov w9, #0x248
    0x17AC: 0x9A88_1128,  # csel x8, x9, x8, ne
    0x17BC: 0xF868_6A80,  # ldr x0, [x20, x8]
    0x17C0: 0xF901_53E0,  # str x0, [sp, #0x2a0]
}
CLASSIFICATION = (
    "post-opening-analysis-of-prospectively-passing-capture-backdrop-owner-"
    "region-construction; not-a-public-state-crop-policy-unseen-transfer-or-"
    "product-parity-claim"
)


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} differs")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label} differs")
    return value


def record_operand_payload(record: Mapping[str, Any]) -> Mapping[str, Any]:
    render = mapping(record.get("render"), "path-isolation render")
    retained = mapping(render.get("metalBufferSnapshots"), "retained Metal buffers")
    payloads = [
        mapping(snapshot, "retained snapshot")["captureBackdropOperands"]
        for snapshot in sequence(retained.get("snapshots"), "retained snapshots")
        if "captureBackdropOperands" in mapping(snapshot, "retained snapshot")
    ]
    if len(payloads) != 1:
        raise ValueError("owner-region operand inventory differs")
    return mapping(payloads[0], "owner-region operands")


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
    code = surviving.hexadecimal_bytes(capture, "capture_backdrop code")
    if (
        capture.get("lengthBytes") != 16_384
        or len(code) != 16_384
        or capture.get("sha256") != EXPECTED_CAPTURE_BACKDROP_SHA256
        or hashlib.sha256(code).hexdigest() != EXPECTED_CAPTURE_BACKDROP_SHA256
    ):
        raise ValueError("capture_backdrop code differs")
    return code


def all_region_rectangles(handle: int, prefix: bytes) -> list[list[int]]:
    iterator = [handle, 0, 0]
    rectangles: list[list[int]] = []
    for _ in range(len(prefix) // 4):
        result = surviving.capture_backdrop_pointer_region_iterate(
            handle, prefix, iterator
        )
        if result is None:
            return rectangles
        rectangle, iterator = result
        rectangles.append(rectangle)
    raise ValueError("owner region iterator is unbounded")


def state_at_path(record: Mapping[str, Any], path: list[int]) -> Mapping[str, Any]:
    states = [
        mapping(value, "captured layer state")
        for value in sequence(
            record.get("capturedLayerStates"), "captured layer states"
        )
    ]
    matching = [state for state in states if state.get("path") == path]
    if len(matching) != 1:
        raise ValueError("captured owner-bounds layer state differs")
    return matching[0]


def analyze(timeline_path: Path, *, run_id: int, head_sha: str) -> dict[str, Any]:
    if run_id != EXPECTED_RUN_ID or head_sha != EXPECTED_HEAD_SHA:
        raise ValueError("owner-region run identity differs")
    timeline_sha = surviving.holdout.sha256_file(timeline_path)
    if timeline_sha != EXPECTED_TIMELINE_SHA256:
        raise ValueError("owner-region timeline digest differs")

    validated = surviving.validate(timeline_path)
    aggregate = mapping(validated.get("aggregate"), "validated aggregate")
    owner_replay = mapping(
        aggregate.get("captureBackdropOwnerRegionReplay"), "owner replay"
    )
    operand_replay = mapping(
        aggregate.get("captureBackdropOperandReplay"), "operand replay"
    )
    region_replay = mapping(
        aggregate.get("captureBackdropConsumedRegionReplay"), "region replay"
    )
    q = mapping(aggregate.get("primaryProducerSourceQ"), "source-q replay")
    allocation = mapping(aggregate.get("allocationInvariants"), "allocation replay")
    callbacks = mapping(
        aggregate.get("captureBackdropCallbackProvenance"), "callback provenance"
    )
    expected_owner_replay = {
        "owner248HandleClassCounts": {"packed": 114},
        "owner270HandleClassCounts": {"packed": 112, "pointer": 2},
        "owner248PrefixByteCountStates": {"0": 114},
        "owner270PrefixByteCountStates": {"0": 112, "4096": 2},
        "ownerRegionWindowByteCount": 256,
        "distinctOwnerRegionWindowCount": 114,
        "embeddedOwnerHandlesExact": True,
        "selectedEqualsOwner248Count": 114,
        "selectedEqualsOwner270Count": 111,
        "independentOwnerPrefixesCaptured": True,
        "allowNumericTolerance": False,
    }
    if (
        owner_replay != expected_owner_replay
        or operand_replay.get("captureCount") != 114
        or operand_replay.get("primaryPositionComponentCount") != 912
        or operand_replay.get("primaryPositionMismatchedComponents") != 0
        or operand_replay.get("primarySourceComponentCount") != 912
        or operand_replay.get("primarySourceMismatchedComponents") != 0
        or region_replay.get("captureCount") != 114
        or region_replay.get("consumedRegionRectExact") is not True
        or q != {"componentCount": 912, "exact": True, "mismatchedComponents": 0}
        or allocation
        != {"componentCount": 1596, "exact": True, "mismatchedComponents": 0}
        or callbacks.get("attemptCount") != 0
    ):
        raise ValueError("prospective owner-region gate differs")

    report = json.loads(timeline_path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("owner-region report differs")
    uniforms = mapping(report.get("dynamicBackgroundUniforms"), "uniform evidence")
    evidence = mapping(
        uniforms.get("pathIsolationInterventions"), "path-isolation evidence"
    )
    raw_records = [
        mapping(value, "path-isolation record")
        for value in sequence(evidence.get("records"), "path-isolation records")
    ]
    if evidence.get("schemaVersion") != 7 or len(raw_records) != 114:
        raise ValueError("owner-region record inventory differs")

    handle_counts: Counter[int] = Counter()
    rect_counts: Counter[tuple[int, ...]] = Counter()
    mismatches: list[dict[str, Any]] = []
    pointer_identities: set[int] = set()
    normalized_windows: Counter[str] = Counter()
    repeat_groups: defaultdict[str, list[bytes]] = defaultdict(list)
    owner_window_public_bounds_matches = 0
    owner_window_remaining_matches = 0
    owner_window_generation_matches = 0

    for record_index, raw_record in enumerate(raw_records):
        if raw_record.get("recordIndex") != record_index:
            raise ValueError("owner-region record order differs")
        payload = record_operand_payload(raw_record)
        operands = surviving.validate_capture_backdrop_operands(payload)
        selected = int(operands["regionHandle"])
        owner_248 = int(operands["ownerRegion248"])
        owner_270 = int(operands["ownerRegion270"])
        handle_counts[selected] += 1
        rect_counts[tuple(operands["selectedRegionRect"])] += 1

        window = surviving.capture_backdrop_operand_bytes(payload, "ownerRegionWindow")
        generation_a, generation_b = struct.unpack_from("<II", window, 0x10)
        owner_window_generation_matches += (
            generation_a == record_index + 33 and generation_b == record_index + 33
        )
        public_bounds = sequence(
            state_at_path(raw_record, [1, 0, 1]).get("bounds"),
            "public owner bounds",
        )
        packed_bounds = struct.pack("<4d", *(float(value) for value in public_bounds))
        owner_window_public_bounds_matches += (
            window[0x28:0x48] == packed_bounds and window[0x50:0x70] == packed_bounds
        )
        remaining_bits = surviving.holdout.float32_bits(
            surviving.holdout.numeric(raw_record.get("remaining"), "remaining")
        )
        owner_window_remaining_matches += (
            int.from_bytes(window[0xD0:0xD4], "little") == remaining_bits
        )

        expected_window = bytearray(256)
        struct.pack_into("<II", expected_window, 0x10, generation_a, generation_b)
        expected_window[0x28:0x48] = packed_bounds
        struct.pack_into("<Q", expected_window, 0x48, owner_248)
        expected_window[0x50:0x70] = packed_bounds
        struct.pack_into("<Q", expected_window, 0x70, owner_270)
        struct.pack_into("<I", expected_window, 0xD0, remaining_bits)
        if window != expected_window:
            raise ValueError("owner-region object window contains an unknown field")
        normalized = bytearray(window)
        normalized[0x10:0x18] = bytes(8)
        normalized_sha = hashlib.sha256(normalized).hexdigest()
        normalized_windows[normalized_sha] += 1
        requested_sha = raw_record.get("requestedLayerStatesSHA256")
        if not isinstance(requested_sha, str):
            raise ValueError("requested-state identity differs")
        repeat_groups[requested_sha].append(bytes(normalized))

        if selected != owner_248:
            raise ValueError("selected owner +0x248 identity differs")
        if selected == owner_270:
            continue
        owner_270_prefix = surviving.capture_backdrop_region_prefix_bytes(
            payload,
            field="ownerRegion270Prefix",
            class_name="bounded owner +0x270 region prefix bytes",
            region_handle=owner_270,
            prefix_byte_count=4096,
            minimum_prefix_byte_count=256,
        )
        if owner_270 & 1:
            rectangles = [surviving.capture_backdrop_packed_region_rect(owner_270)]
            owner_class = "packed"
        else:
            pointer_identities.add(owner_270)
            rectangles = all_region_rectangles(owner_270, owner_270_prefix)
            owner_class = "pointer"
        mismatch = {
            "recordIndex": record_index,
            "interventionName": raw_record.get("interventionName"),
            "translation": raw_record.get("translation"),
            "selectedOwner248Rect": list(operands["selectedRegionRect"]),
            "owner270Class": owner_class,
            "owner270Rectangles": rectangles,
        }
        mismatches.append(mismatch)

    repeated = [group for group in repeat_groups.values() if len(group) > 1]
    repeat_normalized_exact = all(len(set(group)) == 1 for group in repeated)
    if (
        handle_counts != Counter(EXPECTED_HANDLE_COUNTS)
        or rect_counts != Counter(EXPECTED_RECT_COUNTS)
        or tuple(item["recordIndex"] for item in mismatches)
        != EXPECTED_MISMATCH_RECORDS
        or tuple(
            item["recordIndex"]
            for item in mismatches
            if item["owner270Class"] == "pointer"
        )
        != EXPECTED_POINTER_RECORDS
        or {
            item["recordIndex"]: tuple(
                tuple(rectangle) for rectangle in item["owner270Rectangles"]
            )
            for item in mismatches
            if item["owner270Class"] == "pointer"
        }
        != EXPECTED_POINTER_RECTANGLES
        or len(pointer_identities) != 1
        or owner_window_generation_matches != 114
        or owner_window_public_bounds_matches != 114
        or owner_window_remaining_matches != 114
        or len(normalized_windows) != 9
        or sorted(normalized_windows.values(), reverse=True)
        != [68, 14, 14, 8, 5, 2, 1, 1, 1]
        or len(repeated) != 23
        or not repeat_normalized_exact
    ):
        raise ValueError("opened owner-region construction audit differs")

    code = capture_backdrop_code(raw_records[0])
    observed_words = {
        offset: int.from_bytes(code[offset : offset + 4], "little")
        for offset in EXPECTED_CODE_WORDS
    }
    if observed_words != EXPECTED_CODE_WORDS:
        raise ValueError("owner-region construction instruction words differ")

    return {
        "dynamicAllocationCaptureBackdropOwnerRegionAnalysisSchemaVersion": 1,
        "classification": CLASSIFICATION,
        "runID": run_id,
        "headSHA": head_sha,
        "workflowConclusion": "success",
        "prospectiveGatePassed": True,
        "inputTimelineArtifact": timeline_path.parent.name + "/" + timeline_path.name,
        "inputTimelineSHA256": timeline_sha,
        "aggregate": {
            "recordCount": 114,
            "completeLiveOperandCaptureCount": 114,
            "primaryPositionReplay": {
                "componentCount": 912,
                "mismatchedComponents": 0,
                "allowNumericTolerance": False,
            },
            "primarySourceReplay": {
                "componentCount": 912,
                "mismatchedComponents": 0,
                "allowNumericTolerance": False,
            },
            "primarySourceQ": dict(q),
            "allocationInvariants": dict(allocation),
            "selectedRegionConsumedRectangleExactCount": 114,
            "selectedEqualsOwner248Count": 114,
            "selectedEqualsOwner270Count": 111,
            "owner248HandleClassCounts": {"packed": 114},
            "owner270HandleClassCounts": {"packed": 112, "pointer": 2},
            "owner270PointerPrefixByteCount": 4096,
            "callbackAttemptCount": 0,
            "sameStateNormalizedOwnerWindowGroupCount": len(repeated),
            "sameStateNormalizedOwnerWindowsExact": repeat_normalized_exact,
            "selectedRegionHandleFrequency": [
                {"handle": f"0x{handle:016x}", "count": count}
                for handle, count in sorted(handle_counts.items())
            ],
            "selectedRegionRectangleFrequency": [
                {"rect": list(rectangle), "count": count}
                for rectangle, count in sorted(rect_counts.items())
            ],
            "ownerRegionMismatches": mismatches,
        },
        "openedOwnerWindow": {
            "byteCount": 256,
            "generationCounters": {
                "ownerOffsets": [0x210, 0x214],
                "exactRule": "recordIndex + 33",
                "exactCount": owner_window_generation_matches,
            },
            "publicBounds": {
                "layerPath": [1, 0, 1],
                "ownerOffsets": [0x228, 0x250],
                "encoding": "four little-endian binary64 words",
                "exactCount": owner_window_public_bounds_matches,
            },
            "regionHandles": {
                "owner248Offset": 0x248,
                "owner270Offset": 0x270,
            },
            "remaining": {
                "ownerOffset": 0x2D0,
                "encoding": "one little-endian binary32 word",
                "exactCount": owner_window_remaining_matches,
            },
            "allOtherBytesZero": True,
            "generationNormalizedDistinctWindowCount": len(normalized_windows),
        },
        "openedInstructions": {
            "captureBackdropSymbolPrefixSHA256": EXPECTED_CAPTURE_BACKDROP_SHA256,
            "byteGatedWords": [
                {"offset": offset, "word": f"0x{word:08x}"}
                for offset, word in sorted(observed_words.items())
            ],
            "recordVector": {
                "ownerBeginEndOffsets": [0x50, 0x58],
                "recordStrideBytes": 0xD0,
                "sourceKeyOffset": 0x18,
                "sourceKeyByteCount": 40,
                "recordKeyOffset": 0,
                "recordKeyByteCount": 40,
                "selectedRecordBoundsOffset": 0x30,
                "selectedRecordBoundsByteCount": 32,
                "ownerBoundsDestinationOffset": 0x228,
            },
            "regionSelector": {
                "candidateOwnerOffsets": [0x248, 0x270],
                "selectedHandleStackOffset": 0x2A0,
                "observedSelectedOwnerOffset": 0x248,
            },
        },
        "conclusion": {
            "frozenOwnerRegionGatePassed": True,
            "missingAlternateProducerCaptureClosed": True,
            "pointerBackedOwnerRegionsDecoded": True,
            "ownerObjectWindowMappedToPublicBoundsAndRemaining": True,
            "publicLayerStateCropRuleRecovered": False,
            "requiresBoundedOwnerRecordVectorCapture": True,
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
