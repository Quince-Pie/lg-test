#!/usr/bin/env python3
"""Open the prospectively passing owner-record capture from run 30771308161."""

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


EXPECTED_RUN_ID = 30_771_308_161
EXPECTED_HEAD_SHA = "a326be3a0887e9fe661ada3a66e5437e954956e4"
EXPECTED_TIMELINE_SHA256 = (
    "38d660532faba98af0e24cab22b5fe7d3e34379d1916b85440dd96d36f83e2d6"
)
EXPECTED_CAPTURE_BACKDROP_SHA256 = (
    "14f25960556bec9e88ba8ade176ee7f1d39b84726226ade3eb1b0f1be00b70d2"
)
EXPECTED_RECORD_COUNT = 114
EXPECTED_OWNER_PREFIX_BYTE_COUNT = 0x300
EXPECTED_RECORD_BYTE_COUNT = 0xD0
EXPECTED_OWNER_INLINE_RECORD_OFFSET = 0x70
EXPECTED_OWNER_INLINE_RECORD_END = 0x140
EXPECTED_HELPER_POINTER_PERIOD = 14
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
    0x034C: 0xA945_229C,  # ldp x28, x8, [x20, #0x50]
    0x0378: 0xF940_0E6C,  # ldr x12, [x19, #0x18]
    0x0388: 0x5280_1A11,  # mov w17, #0xd0
    0x0398: 0xF940_0220,  # ldr x0, [x17]
    0x03D4: 0x9A9B_021B,  # csel x27, x16, x27, eq
    0x03FC: 0xF901_129B,  # str x27, [x20, #0x220]
    0x0408: 0x3DC0_0D20,  # ldr q0, [x9, #0x30]
    0x0414: 0x3DC0_1120,  # ldr q0, [x9, #0x40]
    0x041C: 0xAD42_8921,  # ldp q1, q2, [x9, #0x50]
    0x0420: 0x5280_1519,  # mov w25, #0xa8
    0x044C: 0x3CD8_82A0,  # ldur q0, [x21, #-0x78]
    0x0450: 0x3CD9_82A1,  # ldur q1, [x21, #-0x68]
    0x0454: 0x0E61_6800,  # fcvtn v0.2s, v0.2d
    0x0458: 0x0E61_6821,  # fcvtn v1.2s, v1.2d
    0x045C: 0x0E20_D421,  # fadd v1.2s, v1.2s, v0.2s
    0x0468: 0x6D3E_8AA0,  # stp d0, d2, [x21, #-0x18]
    0x0470: 0x6D3F_82A1,  # stp d1, d0, [x21, #-0x8]
    0x0474: 0xEB17_037F,  # cmp x27, x23
    0x0478: 0x5400_20C0,  # b.eq capture_backdrop+0x890
    0x0500: 0xF858_02A1,  # ldur x1, [x21, #-0x80]
    0x0504: 0x5280_1A09,  # mov w9, #0xd0
    0x0508: 0x9B09_2368,  # madd x8, x27, x9, x8
    0x050C: 0xF940_1502,  # ldr x2, [x8, #0x28]
    0x088C: 0xA945_229C,  # ldp x28, x8, [x20, #0x50]
    0x0890: 0x9100_06F7,  # add x23, x23, #1
    0x08A0: 0x9103_4339,  # add x25, x25, #0xd0
    0x08A8: 0x54FF_DD03,  # b.lo capture_backdrop+0x448
}
CLASSIFICATION = (
    "post-opening-analysis-of-prospectively-passing-capture-backdrop-owner-"
    "record-vector; not-a-public-state-crop-policy-unseen-transfer-or-product-"
    "parity-claim"
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
        raise ValueError("owner-record operand inventory differs")
    return mapping(payloads[0], "owner-record operands")


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
        capture.get("lengthBytes") != 0x4000
        or len(code) != 0x4000
        or capture.get("sha256") != EXPECTED_CAPTURE_BACKDROP_SHA256
        or hashlib.sha256(code).hexdigest() != EXPECTED_CAPTURE_BACKDROP_SHA256
    ):
        raise ValueError("capture_backdrop code differs")
    return code


def state_at_path(record: Mapping[str, Any], path: list[int]) -> Mapping[str, Any]:
    states = [
        mapping(value, "captured layer state")
        for value in sequence(
            record.get("capturedLayerStates"), "captured layer states"
        )
    ]
    matching = [state for state in states if state.get("path") == path]
    if len(matching) != 1:
        raise ValueError(f"captured layer state at {path} differs")
    return matching[0]


def binary32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def generated_corner_bytes(bounds: Sequence[Any]) -> bytes:
    if len(bounds) != 4:
        raise ValueError("public bounds differ")
    x = binary32(float(bounds[0]))
    y = binary32(float(bounds[1]))
    width = binary32(float(bounds[2]))
    height = binary32(float(bounds[3]))
    upper_x = binary32(width + x)
    upper_y = binary32(height + y)
    return struct.pack(
        "<8f",
        x,
        y,
        upper_x,
        y,
        upper_x,
        upper_y,
        x,
        upper_y,
    )


def analyze(timeline_path: Path, *, run_id: int, head_sha: str) -> dict[str, Any]:
    if run_id != EXPECTED_RUN_ID or head_sha != EXPECTED_HEAD_SHA:
        raise ValueError("owner-record run identity differs")
    timeline_sha = surviving.holdout.sha256_file(timeline_path)
    if timeline_sha != EXPECTED_TIMELINE_SHA256:
        raise ValueError("owner-record timeline digest differs")

    validated = surviving.validate(timeline_path)
    aggregate = mapping(validated.get("aggregate"), "validated aggregate")
    owner_record_replay = mapping(
        aggregate.get("captureBackdropOwnerRecordReplay"), "owner-record replay"
    )
    operand_replay = mapping(
        aggregate.get("captureBackdropOperandReplay"), "operand replay"
    )
    region_replay = mapping(
        aggregate.get("captureBackdropConsumedRegionReplay"), "region replay"
    )
    q_replay = mapping(
        aggregate.get("primaryProducerSourceQ"), "source-q replay"
    )
    allocation_replay = mapping(
        aggregate.get("allocationInvariants"), "allocation replay"
    )
    if (
        owner_record_replay.get("ownerRecordCountStates") != {"1": 114}
        or owner_record_replay.get("ownerRecordVectorByteCountStates")
        != {"208": 114}
        or owner_record_replay.get("sourceRecordMatchCountStates") != {"1": 114}
        or owner_record_replay.get("selectedOwnerRecordIndexStates") != {"0": 114}
        or owner_record_replay.get("sourceKeyMatchedRecordEveryState") is not True
        or operand_replay.get("captureCount") != 114
        or operand_replay.get("primaryPositionMismatchedComponents") != 0
        or operand_replay.get("primarySourceMismatchedComponents") != 0
        or region_replay.get("captureCount") != 114
        or region_replay.get("consumedRegionRectExact") is not True
        or q_replay
        != {"componentCount": 912, "exact": True, "mismatchedComponents": 0}
        or allocation_replay
        != {"componentCount": 1596, "exact": True, "mismatchedComponents": 0}
    ):
        raise ValueError("prospective owner-record gate differs")

    report = json.loads(timeline_path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("owner-record report differs")
    evidence = mapping(
        mapping(
            report.get("dynamicBackgroundUniforms"), "uniform evidence"
        ).get("pathIsolationInterventions"),
        "path-isolation evidence",
    )
    raw_records = [
        mapping(value, "path-isolation record")
        for value in sequence(evidence.get("records"), "path-isolation records")
    ]
    if evidence.get("schemaVersion") != 8 or len(raw_records) != EXPECTED_RECORD_COUNT:
        raise ValueError("owner-record evidence inventory differs")

    owner_addresses: set[int] = set()
    owner_prefix_hashes: set[str] = set()
    record_hashes: set[str] = set()
    source_hashes: set[str] = set()
    helper_pointers: list[int] = []
    normalized_records: Counter[str] = Counter()
    normalized_hash_rects: defaultdict[str, set[tuple[int, ...]]] = defaultdict(set)
    repeat_groups: defaultdict[str, list[bytes]] = defaultdict(list)
    rect_counts: Counter[tuple[int, ...]] = Counter()
    inline_storage_exact_count = 0
    public_bounds_exact_count = 0
    public_scale_exact_count = 0
    auxiliary_zero_count = 0
    selected_rect_exact_count = 0
    generated_corners_exact_count = 0
    reserved_zero_count = 0
    generation_exact_count = 0
    reconstructed_record_exact_count = 0
    selected_branch_bypass_count = 0

    for record_index, raw_record in enumerate(raw_records):
        if raw_record.get("recordIndex") != record_index:
            raise ValueError("owner-record order differs")
        payload = record_operand_payload(raw_record)
        operands = surviving.validate_capture_backdrop_operands(payload)
        owner_prefix = surviving.capture_backdrop_operand_bytes(
            payload, "ownerObjectPrefix"
        )
        owner_record = surviving.capture_backdrop_owner_record_vector_bytes(payload)
        source_key = surviving.capture_backdrop_operand_bytes(
            payload, "sourceStateWindow"
        )
        registers = struct.unpack(
            "<11Q",
            surviving.capture_backdrop_operand_bytes(payload, "registers"),
        )
        owner_address = registers[20 - surviving.CAPTURE_BACKDROP_FIRST_REGISTER]
        owner_addresses.add(owner_address)
        owner_prefix_hashes.add(hashlib.sha256(owner_prefix).hexdigest())
        record_hashes.add(hashlib.sha256(owner_record).hexdigest())
        source_hashes.add(hashlib.sha256(source_key).hexdigest())
        if (
            len(owner_prefix) != EXPECTED_OWNER_PREFIX_BYTE_COUNT
            or len(owner_record) != EXPECTED_RECORD_BYTE_COUNT
            or len(source_key) != 40
        ):
            raise ValueError("owner-record payload length differs")

        begin, end, word_60, word_68 = struct.unpack_from("<4Q", owner_prefix, 0x50)
        inline_exact = (
            begin == owner_address + EXPECTED_OWNER_INLINE_RECORD_OFFSET
            and end == owner_address + EXPECTED_OWNER_INLINE_RECORD_END
            and word_60 == begin
            and word_68 == 2
            and owner_prefix[
                EXPECTED_OWNER_INLINE_RECORD_OFFSET:EXPECTED_OWNER_INLINE_RECORD_END
            ]
            == owner_record
        )
        inline_storage_exact_count += inline_exact
        if not inline_exact:
            raise ValueError("owner inline record storage differs")

        if owner_record[:40] != source_key:
            raise ValueError("owner record source key differs")
        helper_pointer = struct.unpack_from("<Q", owner_record, 0x28)[0]
        helper_pointers.append(helper_pointer)
        if helper_pointer == 0 or helper_pointer & 0x7:
            raise ValueError("owner-record helper pointer differs")

        public_bounds = sequence(
            state_at_path(raw_record, [1, 0, 1]).get("bounds"),
            "public owner bounds",
        )
        public_bounds_bytes = struct.pack(
            "<4d", *(float(value) for value in public_bounds)
        )
        bounds_exact = (
            owner_record[0x30:0x50] == public_bounds_bytes
            and owner_prefix[0x228:0x248] == public_bounds_bytes
            and owner_prefix[0x250:0x270] == public_bounds_bytes
        )
        public_bounds_exact_count += bounds_exact
        if not bounds_exact:
            raise ValueError("owner-record public bounds differ")

        backdrop_scale = surviving.holdout.numeric(
            state_at_path(raw_record, [1, 0, 1, 0]).get("backdropScale"),
            "public backdrop scale",
        )
        public_scale_bits = struct.unpack("<I", struct.pack("<f", backdrop_scale))[0]
        scale_exact = (
            int.from_bytes(owner_prefix[0x48:0x4C], "little")
            == public_scale_bits
            and owner_prefix[0x4C:0x50] == bytes(4)
            and operands["scaleBits"] == public_scale_bits
        )
        public_scale_exact_count += scale_exact
        if not scale_exact:
            raise ValueError("owner public backdrop scale differs")

        selected_rect = tuple(int(value) for value in operands["selectedRegionRect"])
        rect_counts[selected_rect] += 1
        selected_rect_bytes = struct.pack(
            "<4d", *(float(value) for value in selected_rect)
        )
        selected_rect_exact = owner_record[0x70:0x90] == selected_rect_bytes
        selected_rect_exact_count += selected_rect_exact
        if not selected_rect_exact:
            raise ValueError("owner-record selected rectangle differs")

        corner_bytes = generated_corner_bytes(public_bounds)
        corners_exact = owner_record[0x90:0xB0] == corner_bytes
        generated_corners_exact_count += corners_exact
        if not corners_exact:
            raise ValueError("owner-record generated corners differ")

        generation = record_index + 33
        generation_exact = (
            int.from_bytes(owner_prefix[0x40:0x48], "little") == generation
            and struct.unpack_from("<II", owner_prefix, 0x210)
            == (generation, generation)
            and int.from_bytes(owner_record[0xC8:0xD0], "little") == generation
        )
        generation_exact_count += generation_exact
        if not generation_exact:
            raise ValueError("owner-record generation differs")

        auxiliary_zero = owner_record[0x50:0x70] == bytes(0x20)
        reserved_zero = owner_record[0xB0:0xC8] == bytes(0x18)
        auxiliary_zero_count += auxiliary_zero
        reserved_zero_count += reserved_zero
        if not auxiliary_zero or not reserved_zero:
            raise ValueError("owner-record zero block differs")

        expected_record = bytearray(EXPECTED_RECORD_BYTE_COUNT)
        expected_record[:40] = source_key
        struct.pack_into("<Q", expected_record, 0x28, helper_pointer)
        expected_record[0x30:0x50] = public_bounds_bytes
        expected_record[0x70:0x90] = selected_rect_bytes
        expected_record[0x90:0xB0] = corner_bytes
        struct.pack_into("<Q", expected_record, 0xC8, generation)
        reconstructed_exact = bytes(expected_record) == owner_record
        reconstructed_record_exact_count += reconstructed_exact
        if not reconstructed_exact:
            raise ValueError("owner record contains an unaccounted byte")

        normalized = bytearray(owner_record)
        normalized[0x28:0x30] = bytes(8)
        normalized[0xC8:0xD0] = bytes(8)
        normalized_bytes = bytes(normalized)
        normalized_sha = hashlib.sha256(normalized_bytes).hexdigest()
        normalized_records[normalized_sha] += 1
        normalized_hash_rects[normalized_sha].add(selected_rect)
        requested_sha = raw_record.get("requestedLayerStatesSHA256")
        if not isinstance(requested_sha, str):
            raise ValueError("requested-state identity differs")
        repeat_groups[requested_sha].append(normalized_bytes)

        # With one record, x27 and x23 are both zero at +0x474, so +0x478
        # branches directly to +0x890 and does not execute the +0x28 helper path.
        selected_branch_bypass_count += operands["selectedOwnerRecordIndex"] == 0

    repeated = [group for group in repeat_groups.values() if len(group) > 1]
    repeat_normalized_exact = all(len(set(group)) == 1 for group in repeated)
    helper_pointer_period_exact = all(
        pointer == helper_pointers[index % EXPECTED_HELPER_POINTER_PERIOD]
        for index, pointer in enumerate(helper_pointers)
    )
    normalized_counts = sorted(normalized_records.values(), reverse=True)
    expected_variant_counts = sorted(EXPECTED_RECT_COUNTS.values(), reverse=True)
    if (
        len(owner_addresses) != 1
        or len(owner_prefix_hashes) != EXPECTED_RECORD_COUNT
        or len(record_hashes) != EXPECTED_RECORD_COUNT
        or len(source_hashes) != 1
        or rect_counts != Counter(EXPECTED_RECT_COUNTS)
        or inline_storage_exact_count != EXPECTED_RECORD_COUNT
        or public_bounds_exact_count != EXPECTED_RECORD_COUNT
        or public_scale_exact_count != EXPECTED_RECORD_COUNT
        or auxiliary_zero_count != EXPECTED_RECORD_COUNT
        or selected_rect_exact_count != EXPECTED_RECORD_COUNT
        or generated_corners_exact_count != EXPECTED_RECORD_COUNT
        or reserved_zero_count != EXPECTED_RECORD_COUNT
        or generation_exact_count != EXPECTED_RECORD_COUNT
        or reconstructed_record_exact_count != EXPECTED_RECORD_COUNT
        or selected_branch_bypass_count != EXPECTED_RECORD_COUNT
        or len(set(helper_pointers)) != EXPECTED_HELPER_POINTER_PERIOD
        or not helper_pointer_period_exact
        or len(normalized_records) != len(EXPECTED_RECT_COUNTS)
        or normalized_counts != expected_variant_counts
        or any(len(rectangles) != 1 for rectangles in normalized_hash_rects.values())
        or len(repeated) != 23
        or not repeat_normalized_exact
    ):
        raise ValueError("opened owner-record audit differs")

    code = capture_backdrop_code(raw_records[0])
    observed_words = {
        offset: int.from_bytes(code[offset : offset + 4], "little")
        for offset in EXPECTED_CODE_WORDS
    }
    if observed_words != EXPECTED_CODE_WORDS:
        raise ValueError("owner-record construction instruction words differ")

    return {
        "dynamicAllocationCaptureBackdropOwnerRecordAnalysisSchemaVersion": 1,
        "classification": CLASSIFICATION,
        "runID": run_id,
        "headSHA": head_sha,
        "workflowConclusion": "success",
        "prospectiveGatePassed": True,
        "inputTimelineArtifact": timeline_path.parent.name + "/" + timeline_path.name,
        "inputTimelineSHA256": timeline_sha,
        "aggregate": {
            "recordCount": EXPECTED_RECORD_COUNT,
            "completeLiveOperandCaptureCount": EXPECTED_RECORD_COUNT,
            "ownerRecordCountEveryState": 1,
            "sourceKeyMatchCountEveryState": 1,
            "selectedRecordIndexEveryState": 0,
            "primaryPositionReplay": {
                "componentCount": operand_replay["primaryPositionComponentCount"],
                "mismatchedComponents": operand_replay[
                    "primaryPositionMismatchedComponents"
                ],
                "allowNumericTolerance": False,
            },
            "primarySourceReplay": {
                "componentCount": operand_replay["primarySourceComponentCount"],
                "mismatchedComponents": operand_replay[
                    "primarySourceMismatchedComponents"
                ],
                "allowNumericTolerance": False,
            },
            "primarySourceQ": dict(q_replay),
            "allocationInvariants": dict(allocation_replay),
            "selectedRegionConsumedRectangleExactCount": region_replay[
                "captureCount"
            ],
            "distinctOwnerPrefixCount": len(owner_prefix_hashes),
            "distinctOwnerRecordCount": len(record_hashes),
            "distinctSourceKeyCount": len(source_hashes),
            "sameStateNormalizedRecordGroupCount": len(repeated),
            "sameStateNormalizedRecordsExact": repeat_normalized_exact,
            "selectedRegionRectangleFrequency": [
                {"rect": list(rectangle), "count": count}
                for rectangle, count in sorted(rect_counts.items())
            ],
        },
        "openedOwnerInlineStorage": {
            "ownerRegister": "x20",
            "distinctOwnerAddressCount": len(owner_addresses),
            "ownerPrefixByteCount": EXPECTED_OWNER_PREFIX_BYTE_COUNT,
            "beginPointerOwnerOffset": 0x50,
            "endPointerOwnerOffset": 0x58,
            "duplicateBeginWordOwnerOffset": 0x60,
            "opaqueConstantWordOwnerOffset": 0x68,
            "opaqueConstantWordValue": 2,
            "inlineRecordOwnerRange": [
                EXPECTED_OWNER_INLINE_RECORD_OFFSET,
                EXPECTED_OWNER_INLINE_RECORD_END,
            ],
            "beginEqualsOwnerPlusInlineOffsetCount": inline_storage_exact_count,
            "endEqualsOwnerPlusInlineEndCount": inline_storage_exact_count,
            "word60EqualsBeginCount": inline_storage_exact_count,
            "inlineBytesEqualIndependentVectorCount": inline_storage_exact_count,
        },
        "openedOwnerRecord": {
            "byteCount": EXPECTED_RECORD_BYTE_COUNT,
            "fullyReconstructedExactCount": reconstructed_record_exact_count,
            "sourceKey": {
                "recordRange": [0x00, 0x28],
                "sourceObjectRange": [0x18, 0x40],
                "exactCount": EXPECTED_RECORD_COUNT,
            },
            "helperPointer": {
                "recordOffset": 0x28,
                "distinctPointerCount": len(set(helper_pointers)),
                "exactSequencePeriod": EXPECTED_HELPER_POINTER_PERIOD,
                "periodExact": helper_pointer_period_exact,
                "helperPathBypassedBySingleSelectedRecordCount": (
                    selected_branch_bypass_count
                ),
                "semanticObjectTypeRecovered": False,
            },
            "initialPublicBounds": {
                "recordRange": [0x30, 0x50],
                "encoding": "four little-endian binary64 words",
                "capturedLayerPath": [1, 0, 1],
                "exactCount": public_bounds_exact_count,
            },
            "auxiliaryBounds": {
                "recordRange": [0x50, 0x70],
                "encoding": "four little-endian binary64 words",
                "allZeroCount": auxiliary_zero_count,
            },
            "selectedRegionRectangle": {
                "recordRange": [0x70, 0x90],
                "encoding": "four little-endian binary64 words",
                "exactCount": selected_rect_exact_count,
            },
            "generatedPublicBoundsCorners": {
                "recordRange": [0x90, 0xB0],
                "encoding": "eight little-endian binary32 words",
                "order": [
                    "lowerX",
                    "lowerY",
                    "upperX",
                    "lowerY",
                    "upperX",
                    "upperY",
                    "lowerX",
                    "upperY",
                ],
                "exactCount": generated_corners_exact_count,
            },
            "zeroReservedRange": [0xB0, 0xC8],
            "zeroReservedExactCount": reserved_zero_count,
            "generation": {
                "recordOffset": 0xC8,
                "exactRule": "recordIndex + 33",
                "exactCount": generation_exact_count,
                "sameValueOwnerOffsets": [0x40, 0x210, 0x214],
            },
            "pointerAndGenerationNormalizedDistinctVariantCount": len(
                normalized_records
            ),
            "normalizedVariantsAreInOneToOneCorrespondenceWithRectangles": True,
        },
        "openedInstructions": {
            "captureBackdropSymbolPrefixSHA256": EXPECTED_CAPTURE_BACKDROP_SHA256,
            "byteGatedWords": [
                {"offset": offset, "word": f"0x{word:08x}"}
                for offset, word in sorted(observed_words.items())
            ],
            "descendingKeyScanSelectsLowestMatchingIndex": True,
            "selectedRecordBoundsCopiedToOwner228": True,
            "generatedCornerArithmetic": (
                "binary64-to-binary32 lower and extent conversion, binary32 "
                "upper=lower+extent, then four-corner stores"
            ),
            "singleRecordSelectedBranch": {
                "compareOffset": 0x474,
                "branchOffset": 0x478,
                "branchTargetOffset": 0x890,
                "bypassesOtherRecordTransformAndUnionPath": True,
            },
            "otherRecordHelperOperands": {
                "currentRecordPointerOffset": 0x28,
                "selectedRecordPointerOffset": 0x28,
                "pathExecutedInThisCorpus": False,
            },
        },
        "conclusion": {
            "frozenOwnerRecordGatePassed": True,
            "ownerRecordVectorCaptured": True,
            "ownerRecordVectorIsInlineOwnerStorage": True,
            "everyOwnerRecordByteAccountedFor": True,
            "singleRecordTransformAndUnionBranchExercised": False,
            "publicLayerStateCropRuleRecovered": False,
            "upstreamPrivateRegionConstructionStillMissing": True,
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
