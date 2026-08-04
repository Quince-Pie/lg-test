#!/usr/bin/env python3
"""Validate the sealed full-code/path/aggregate-writer trace."""

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_capture_backdrop_writer_trace as writer_base
import validate_layer_shapes_construction_trace as construction_base
import validate_layer_shapes_merge_trace as merge_base


EXPECTED_TRACE_SCHEMA_VERSION = 1
VALIDATION_SCHEMA_VERSION = 1
EXPECTED_CLASSIFICATION = (
    "preregistered-complete-prepare-layer-code-path-marker-and-selected-"
    "aggregate-origin-watchpoint-trace; writer-semantics-public-crop-law-"
    "unseen-transfer-and-product-parity-remain-sealed"
)
EXPECTED_VALIDATION_CLASSIFICATION = (
    "prospective-integrity-gate-for-complete-prepare-layer-code-path-markers-"
    "and-selected-aggregate-writer; semantics-remain-sealed"
)
CAPTURE_BACKDROP_CODE_BYTE_COUNT = 0x4000
CAPTURE_BACKDROP_LATE_OFFSET = 0x2B58
PREPARE_LAYER_SYMBOL_BYTE_COUNT = 40128
KNOWN_PREPARE_LAYER_WINDOWS = (
    (12764, 0x1000, "91fbe43da3533d7cd4578195b77c5a1aa0844105493c70635687e76adb7af768"),
    (14064, 0x1000, "9f67889b8a095f620d078f0c5c61eb0dca92e76916301a4ada40cf3b63eff9df"),
    (17944, 0x1000, "6472a0a0dbbb1fcdcbc75dcea63f28f2645cb58770ab0dc00ea17464db597c7f"),
    (19212, 0x1000, "756da544c0ac96badc07fc651b127e7eb8dcb244f98801335748e27feed2b5fa"),
    (19216, 0x1000, "e28e801599441f3aaf171ccc7ca5df86a0dc4c32a0d18062ab9a8c4627e9bc37"),
)
UNION_HELPER_RELATIVE_TO_PREPARE_LAYER = -0xAA0
UNION_HELPER_SYMBOL_NAME = (
    "CA::Render::Updater::LayerShapes::union_bounds(CA::Rect const&, bool)"
)
UNION_HELPER_SYMBOL_BYTE_COUNT = 404
UNION_HELPER_SYMBOL_SHA256 = (
    "246257a9bc1a608f59dbc07345397a8851b49528c59407eb775e9b9895a2c4b7"
)
PATH_MARKERS = (
    ("constructionWindowEntry", 0x31DC, False),
    ("preSelectorCall", 0x327C, False),
    ("postSelectorBranch", 0x3284, False),
    ("directLabel", 0x32B4, False),
    ("directUnionCall", 0x32C0, False),
    ("alternateLabel", 0x32C8, False),
    ("alternateSourceLoad", 0x33E8, False),
    ("alternateAggregateStore", 0x33F0, False),
    ("constructionJoin", 0x3458, False),
    ("sourceLaterHandle", 0x3EF0, True),
    ("sourceLaterOwnerRectangle", 0x4E18, True),
    ("sourceLaterIntegerOrigin", 0x530C, True),
    ("sourceLaterIntegerTail", 0x5310, True),
)
MARKER_BY_NAME = {
    name: {"offset": offset, "watchArmCandidate": watch_arm}
    for name, offset, watch_arm in PATH_MARKERS
}
LATER_SELECTED_MARKER_NAMES = tuple(
    name for name, _offset, watch_arm in PATH_MARKERS if watch_arm
)
ROLE_STATE_BYTE_COUNT = 0x800
AGGREGATE_OFFSET = 656
AGGREGATE_BYTE_COUNT = 32
ALTERNATE_SOURCE_OFFSET = 1312
RECURSIVE_CHILD_OFFSET = 1568
MAXIMUM_LATE_CANDIDATE_COUNT = 512
MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT = 16
MAXIMUM_MARKER_HIT_COUNT = 4096
MAXIMUM_RECORD_COUNT_PER_MARKER = 128
MAXIMUM_BACKTRACE_FRAME_COUNT = 24
WATCHPOINT_BYTE_COUNT = 8
MAXIMUM_WATCHPOINT_HIT_COUNT = 24
PC_CENTERED_CODE_WINDOW_BYTE_COUNT = 0x1000
PC_CENTERED_CODE_WINDOW_BACKTRACK = 0x800
STACK_SNAPSHOT_BYTE_COUNT = 0x800
REGISTER_POINTER_SNAPSHOT_BYTE_COUNT = 0x100
REGISTER_POINTER_SNAPSHOT_BACKTRACK = 0x40
MINIMUM_POINTER_PROBE_ADDRESS = 0x1_0000_0000
MAXIMUM_POINTER_PROBE_ADDRESS = 0x0000_FFFF_FFFF_FFFF
MARKER_REGISTER_NAMES = (
    "x0",
    "x1",
    "x2",
    "x3",
    "x4",
    "x19",
    "x23",
    "x24",
    "x27",
    "x28",
    "x29",
    "x30",
    "sp",
    "pc",
)
GENERAL_REGISTER_NAMES = tuple(f"x{index}" for index in range(31)) + (
    "sp",
    "pc",
    "cpsr",
)
SIMD_REGISTER_NAMES = tuple(f"v{index}" for index in range(32)) + (
    "fpsr",
    "fpcr",
)
POINTER_PROBE_REGISTER_NAMES = tuple(f"x{index}" for index in range(29))
PREPARE_LAYER_ROLE_REGISTER_NAMES = tuple(f"x{index}" for index in range(19, 29))
OBJECT_SNAPSHOT_SPECS = (
    ("source", 0x180),
    ("owner", 0x300),
    ("layer", 0x200),
    ("layerState", 0x180),
)
EXPECTED_CONFIGURATION = {
    "captureBackdropSymbol": merge_base.CAPTURE_BACKDROP_SYMBOL,
    "captureBackdropCodeByteCount": CAPTURE_BACKDROP_CODE_BYTE_COUNT,
    "captureBackdropCodeSHA256": merge_base.CAPTURE_BACKDROP_CODE_SHA256,
    "captureBackdropLateOffset": CAPTURE_BACKDROP_LATE_OFFSET,
    "prepareLayerFunction": merge_base.PREPARE_LAYER_FUNCTION,
    "prepareLayerSymbolByteCount": PREPARE_LAYER_SYMBOL_BYTE_COUNT,
    "knownPrepareLayerWindows": [
        {"offset": offset, "byteCount": count, "sha256": digest}
        for offset, count, digest in KNOWN_PREPARE_LAYER_WINDOWS
    ],
    "unionHelperRelativeToPrepareLayer": UNION_HELPER_RELATIVE_TO_PREPARE_LAYER,
    "unionHelperSymbolName": UNION_HELPER_SYMBOL_NAME,
    "unionHelperSymbolByteCount": UNION_HELPER_SYMBOL_BYTE_COUNT,
    "unionHelperSymbolSHA256": UNION_HELPER_SYMBOL_SHA256,
    "pathMarkers": [
        {"name": name, "offset": offset, "watchArmCandidate": watch_arm}
        for name, offset, watch_arm in PATH_MARKERS
    ],
    "laterSelectedMarkerNames": list(LATER_SELECTED_MARKER_NAMES),
    "roleStateByteCount": ROLE_STATE_BYTE_COUNT,
    "aggregateOffset": AGGREGATE_OFFSET,
    "aggregateByteCount": AGGREGATE_BYTE_COUNT,
    "alternateSourceOffset": ALTERNATE_SOURCE_OFFSET,
    "recursiveChildOffset": RECURSIVE_CHILD_OFFSET,
    "maximumLateCandidateCount": MAXIMUM_LATE_CANDIDATE_COUNT,
    "maximumLateCandidateDiagnosticCount": (
        MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT
    ),
    "maximumMarkerHitCount": MAXIMUM_MARKER_HIT_COUNT,
    "maximumRecordCountPerMarker": MAXIMUM_RECORD_COUNT_PER_MARKER,
    "maximumBacktraceFrameCount": MAXIMUM_BACKTRACE_FRAME_COUNT,
    "watchpointByteCount": WATCHPOINT_BYTE_COUNT,
    "maximumWatchpointHitCount": MAXIMUM_WATCHPOINT_HIT_COUNT,
    "pcCenteredCodeWindowByteCount": PC_CENTERED_CODE_WINDOW_BYTE_COUNT,
    "pcCenteredCodeWindowBacktrack": PC_CENTERED_CODE_WINDOW_BACKTRACK,
    "stackSnapshotByteCount": STACK_SNAPSHOT_BYTE_COUNT,
    "registerPointerSnapshotByteCount": REGISTER_POINTER_SNAPSHOT_BYTE_COUNT,
    "registerPointerSnapshotBacktrack": REGISTER_POINTER_SNAPSHOT_BACKTRACK,
    "pointerProbeAddressRange": [
        MINIMUM_POINTER_PROBE_ADDRESS,
        MAXIMUM_POINTER_PROBE_ADDRESS,
    ],
    "markerRegisterNames": list(MARKER_REGISTER_NAMES),
    "generalRegisterNames": list(GENERAL_REGISTER_NAMES),
    "simdRegisterNames": list(SIMD_REGISTER_NAMES),
    "pointerProbeRegisterNames": list(POINTER_PROBE_REGISTER_NAMES),
    "prepareLayerRoleRegisterNames": list(PREPARE_LAYER_ROLE_REGISTER_NAMES),
    "objectSnapshotSpecs": [
        {"base": base, "byteCount": byte_count}
        for base, byte_count in OBJECT_SNAPSHOT_SPECS
    ],
    "markerRecordRule": (
        "retain every bounded preselection marker; after source selection "
        "retain only exact x28 source matches"
    ),
    "watchpointArmRule": (
        "after source selection arm from the most recent retained watch-arm "
        "marker retrospectively classified as the exact x28 source; if none "
        "exists, arm at the first later live exact-x28 watch-arm marker; target "
        "x19+656 for eight bytes"
    ),
}
MINIMUM_SELECTED_LATER_MARKER_RECORD_COUNT = 4
MINIMUM_DISTINCT_SELECTED_AGGREGATE_COUNT = 3
MINIMUM_CHANGED_WATCHPOINT_EVENT_COUNT = 1


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    return writer_base.mapping(value, label)


def sequence(value: Any, label: str) -> Sequence[Any]:
    return writer_base.sequence(value, label)


def integer(value: Any, label: str) -> int:
    return writer_base.integer(value, label)


def _payload(value: Any, byte_count: int, label: str) -> bytes:
    return writer_base.hexadecimal_payload(value, byte_count, label)


def _memory_payload(
    value: Any,
    label: str,
    *,
    expected_address: int,
    expected_byte_count: int,
) -> bytes:
    snapshot = writer_base.memory_snapshot(
        value,
        label,
        expected_address=expected_address,
        expected_byte_count=expected_byte_count,
    )
    return bytes.fromhex(snapshot["hex"])


def _callback_order(trace: Mapping[str, Any]) -> dict[int, str]:
    items = list(sequence(trace.get("callbackOrder"), "callback order"))
    final = integer(trace.get("finalCallbackSequence"), "final callback sequence")
    if final != len(items) or not items:
        raise ValueError("callback sequence bounds differ")
    result = {}
    for expected, value_item in enumerate(items, start=1):
        item = mapping(value_item, f"callback order {expected}")
        sequence_number = integer(item.get("sequence"), "callback sequence")
        kind = item.get("kind")
        if sequence_number != expected or not isinstance(kind, str) or not kind:
            raise ValueError("callback sequence identity differs")
        result[sequence_number] = kind
    return result


def _require_callback(
    order: Mapping[int, str], value: Any, expected_kind: str, label: str
) -> int:
    sequence_number = integer(value, label)
    if order.get(sequence_number) != expected_kind:
        raise ValueError(f"{label} identity differs")
    return sequence_number


def _marker_registers(value: Any, label: str) -> dict[str, int]:
    records = list(sequence(value, label))
    if len(records) != len(MARKER_REGISTER_NAMES):
        raise ValueError(f"{label} inventory differs")
    result = {}
    for name, value_record in zip(MARKER_REGISTER_NAMES, records, strict=True):
        record = writer_base.register_record(value_record, name, 8, f"{label} {name}")
        result[name] = integer(record.get("unsignedValue"), f"{label} {name}")
    return result


def _static_gates(trace: Mapping[str, Any], order: Mapping[int, str]):
    capture = mapping(trace.get("captureBackdrop"), "capture_backdrop")
    capture_sequence = _require_callback(
        order,
        capture.get("callbackSequence"),
        "capture-backdrop-entry",
        "capture_backdrop callback",
    )
    capture_module = merge_base.module_record(
        capture.get("module"), "capture_backdrop module"
    )
    if (
        integer(capture.get("symbolAddress"), "capture_backdrop address") <= 0
        or capture.get("codeByteCount") != CAPTURE_BACKDROP_CODE_BYTE_COUNT
        or capture.get("codeSHA256") != merge_base.CAPTURE_BACKDROP_CODE_SHA256
        or integer(capture.get("lateBreakpointID"), "late breakpoint ID") <= 0
    ):
        raise ValueError("capture_backdrop gate differs")

    prepare = mapping(trace.get("prepareLayer"), "prepare_layer")
    prepare_sequence = _require_callback(
        order,
        prepare.get("callbackSequence"),
        "prepare-layer-entry",
        "prepare_layer callback",
    )
    start = integer(prepare.get("symbolStart"), "prepare_layer start")
    end = integer(prepare.get("symbolEnd"), "prepare_layer end")
    prepare_module = merge_base.module_record(
        prepare.get("module"), "prepare_layer module"
    )
    entry_id = integer(prepare.get("entryBreakpointID"), "entry breakpoint ID")
    entry_locations = list(
        sequence(
            prepare.get("entryBreakpointLocationAddresses"),
            "entry breakpoint locations",
        )
    )
    if (
        prepare.get("function") != merge_base.PREPARE_LAYER_FUNCTION
        or end - start != PREPARE_LAYER_SYMBOL_BYTE_COUNT
        or prepare.get("symbolByteCount") != PREPARE_LAYER_SYMBOL_BYTE_COUNT
        or prepare_module != capture_module
        or prepare.get("callbackPC") != start
        or prepare.get("callbackLocationAddress") != start
        or entry_locations != [start]
        or entry_id <= 0
        or prepare_sequence >= capture_sequence
    ):
        raise ValueError("prepare_layer exact entry differs")
    full_code = _memory_payload(
        prepare.get("fullCode"),
        "full prepare_layer code",
        expected_address=start,
        expected_byte_count=PREPARE_LAYER_SYMBOL_BYTE_COUNT,
    )
    known_values = list(sequence(prepare.get("knownWindows"), "known windows"))
    if len(known_values) != len(KNOWN_PREPARE_LAYER_WINDOWS):
        raise ValueError("known window inventory differs")
    for value_item, expected in zip(
        known_values, KNOWN_PREPARE_LAYER_WINDOWS, strict=True
    ):
        item = mapping(value_item, "known window")
        offset, byte_count, digest = expected
        if (
            item
            != {"offset": offset, "byteCount": byte_count, "sha256": digest}
            or hashlib.sha256(full_code[offset : offset + byte_count]).hexdigest()
            != digest
        ):
            raise ValueError("known prepare_layer window differs")

    helper = mapping(prepare.get("unionHelper"), "union helper")
    helper_address = start + UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
    helper_symbol = mapping(helper.get("symbol"), "union helper symbol")
    if (
        helper.get("address") != helper_address
        or helper.get("relativeToPrepareLayer")
        != UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
        or merge_base.module_record(helper.get("module"), "union helper module")
        != prepare_module
        or helper_symbol.get("valid") is not True
        or helper_symbol.get("name") != UNION_HELPER_SYMBOL_NAME
        or helper_symbol.get("startAddress") != helper_address
        or helper_symbol.get("endAddress")
        != helper_address + UNION_HELPER_SYMBOL_BYTE_COUNT
        or helper.get("symbolCodeSHA256") != UNION_HELPER_SYMBOL_SHA256
    ):
        raise ValueError("union helper gate differs")

    markers = list(sequence(prepare.get("markers"), "static markers"))
    if len(markers) != len(PATH_MARKERS):
        raise ValueError("static marker inventory differs")
    marker_ids = set()
    marker_records = {}
    for value_marker, (name, offset, watch_arm) in zip(
        markers, PATH_MARKERS, strict=True
    ):
        marker = mapping(value_marker, f"static marker {name}")
        breakpoint_id = integer(marker.get("breakpointID"), f"{name} breakpoint")
        expected_raw = full_code[offset : offset + 4].hex()
        if (
            marker.get("name") != name
            or marker.get("offset") != offset
            or marker.get("address") != start + offset
            or marker.get("watchArmCandidate") is not watch_arm
            or marker.get("instructionRawLittleEndianHex") != expected_raw
            or breakpoint_id <= entry_id
            or breakpoint_id in marker_ids
        ):
            raise ValueError(f"static marker {name} differs")
        marker_ids.add(breakpoint_id)
        marker_records[name] = marker
    if marker_ids and capture.get("lateBreakpointID") <= max(marker_ids):
        raise ValueError("construction markers were not armed before source selection")
    return start, prepare_module, full_code, marker_records


def _marker_records(
    trace: Mapping[str, Any],
    order: Mapping[int, str],
    *,
    prepare_start: int,
    prepare_module: Mapping[str, Any],
    selected_source: int,
) -> tuple[Counter[str], Counter[str], int]:
    records = list(sequence(trace.get("markerRecords"), "marker records"))
    if trace.get("finalMarkerRecordCount") != len(records):
        raise ValueError("marker record count differs")
    retained = Counter()
    selected = Counter()
    selected_aggregates = set()
    for index, value_record in enumerate(records):
        label = f"marker record {index}"
        record = mapping(value_record, label)
        name = record.get("markerName")
        if name not in MARKER_BY_NAME:
            raise ValueError(f"{label} marker differs")
        marker = MARKER_BY_NAME[name]
        offset = marker["offset"]
        _require_callback(
            order,
            record.get("callbackSequence"),
            "marker:" + name,
            f"{label} callback",
        )
        addresses = mapping(record.get("addresses"), f"{label} addresses")
        x19 = integer(addresses.get("x19"), f"{label} x19")
        source = integer(addresses.get("source"), f"{label} source")
        is_selected = source == selected_source
        source_known = record.get("sourceKnownAtHit")
        if (
            record.get("recordIndex") != index
            or record.get("markerOffset") != offset
            or record.get("watchArmCandidate")
            is not marker["watchArmCandidate"]
            or record.get("selectedSource") is not is_selected
            or not isinstance(source_known, bool)
            or source_known and not is_selected
            or integer(record.get("threadID"), f"{label} thread") <= 0
            or record.get("pc") != prepare_start + offset
            or addresses.get("aggregate") != x19 + AGGREGATE_OFFSET
            or addresses.get("alternateSource") != x19 + ALTERNATE_SOURCE_OFFSET
            or addresses.get("recursiveChild") != x19 + RECURSIVE_CHILD_OFFSET
        ):
            raise ValueError(f"{label} identity differs")
        merge_base.frame_record(
            record.get("frame"),
            f"{label} frame",
            expected_pc=prepare_start + offset,
            expected_symbol_start=prepare_start,
            expected_module=prepare_module,
        )
        merge_base.backtrace(
            record.get("backtrace"),
            f"{label} backtrace",
            expected_first_pc=prepare_start + offset,
            expected_symbol_start=prepare_start,
            expected_module=prepare_module,
        )
        registers = _marker_registers(record.get("registers"), f"{label} registers")
        if (
            registers["x19"] != x19
            or registers["x28"] != source
            or registers["pc"] != prepare_start + offset
        ):
            raise ValueError(f"{label} register aliases differ")
        role = _memory_payload(
            record.get("roleState"),
            f"{label} role state",
            expected_address=x19,
            expected_byte_count=ROLE_STATE_BYTE_COUNT,
        )
        aggregate = role[AGGREGATE_OFFSET : AGGREGATE_OFFSET + AGGREGATE_BYTE_COUNT]
        alternate = role[
            ALTERNATE_SOURCE_OFFSET : ALTERNATE_SOURCE_OFFSET + AGGREGATE_BYTE_COUNT
        ]
        child = role[
            RECURSIVE_CHILD_OFFSET : RECURSIVE_CHILD_OFFSET + AGGREGATE_BYTE_COUNT
        ]
        if (
            _payload(record.get("aggregateHex"), AGGREGATE_BYTE_COUNT, label)
            != aggregate
            or _payload(
                record.get("alternateSourceHex"), AGGREGATE_BYTE_COUNT, label
            )
            != alternate
            or _payload(
                record.get("recursiveChildHex"), AGGREGATE_BYTE_COUNT, label
            )
            != child
        ):
            raise ValueError(f"{label} role slices differ")
        retained[name] += 1
        if is_selected:
            selected[name] += 1
            if name in LATER_SELECTED_MARKER_NAMES:
                selected_aggregates.add(hashlib.sha256(aggregate).digest())
    if any(count > MAXIMUM_RECORD_COUNT_PER_MARKER for count in retained.values()):
        raise ValueError("marker retained bounds differ")
    if trace.get("finalSelectedMarkerRecordCount") != sum(selected.values()):
        raise ValueError("selected marker count differs")
    selected_later_count = sum(selected[name] for name in LATER_SELECTED_MARKER_NAMES)
    if (
        trace.get("finalSelectedLaterMarkerRecordCount") != selected_later_count
        or selected_later_count < MINIMUM_SELECTED_LATER_MARKER_RECORD_COUNT
        or any(selected[name] == 0 for name in LATER_SELECTED_MARKER_NAMES)
        or len(selected_aggregates) < MINIMUM_DISTINCT_SELECTED_AGGREGATE_COUNT
    ):
        raise ValueError("selected later marker coverage differs")

    hit_counts = mapping(trace.get("markerHitCounts"), "marker hit counts")
    rejected_counts = mapping(
        trace.get("rejectedMarkerCounts"), "rejected marker counts"
    )
    discarded_counts = mapping(
        trace.get("discardedMarkerCounts"), "discarded marker counts"
    )
    expected_names = set(MARKER_BY_NAME)
    if (
        set(hit_counts) != expected_names
        or set(rejected_counts) != expected_names
        or set(discarded_counts) != expected_names
    ):
        raise ValueError("marker accounting inventory differs")
    for name in expected_names:
        hits = integer(hit_counts.get(name), f"{name} hit count")
        rejected = integer(rejected_counts.get(name), f"{name} rejected count")
        discarded = integer(discarded_counts.get(name), f"{name} discarded count")
        if (
            discarded != 0
            or hits != retained[name] + rejected
            or hits > MAXIMUM_MARKER_HIT_COUNT
        ):
            raise ValueError(f"{name} marker accounting differs")
    return retained, selected, len(selected_aggregates)


def _generic_backtrace(value: Any, label: str, first_frame: Mapping[str, Any]) -> None:
    frames = list(sequence(value, label))
    if not frames or len(frames) > MAXIMUM_BACKTRACE_FRAME_COUNT:
        raise ValueError(f"{label} bounds differ")
    if mapping(frames[0], f"{label} first frame") != first_frame:
        raise ValueError(f"{label} first frame differs")
    for index, frame in enumerate(frames):
        writer_base.frame_record(frame, f"{label} frame {index}")


def _watchpoint_evidence(
    trace: Mapping[str, Any],
    order: Mapping[int, str],
    *,
    object_addresses: Mapping[str, Any],
    selected_source: int,
    source_sequence: int,
    marker_records: Sequence[Any],
) -> tuple[int, int, set[int]]:
    watchpoint = mapping(trace.get("aggregateWatchpoint"), "aggregate watchpoint")
    watch_id = integer(watchpoint.get("id"), "aggregate watchpoint ID")
    role_base = integer(watchpoint.get("roleBase"), "aggregate role base")
    address = integer(watchpoint.get("address"), "aggregate watched address")
    marker_name = watchpoint.get("markerName")
    marker_record_index = integer(
        watchpoint.get("markerRecordIndex"), "watchpoint marker record index"
    )
    arm_mode = watchpoint.get("armMode")
    arm_sequence = _require_callback(
        order,
        watchpoint.get("callbackSequence"),
        "aggregate-watchpoint-armed",
        "watchpoint arm callback",
    )
    initial = _payload(
        watchpoint.get("initialHex"), WATCHPOINT_BYTE_COUNT, "watchpoint initial"
    )
    initial_role = _payload(
        watchpoint.get("initialRoleStateHex"),
        ROLE_STATE_BYTE_COUNT,
        "watchpoint initial role state",
    )
    if (
        watch_id <= 0
        or marker_name not in LATER_SELECTED_MARKER_NAMES
        or watchpoint.get("selectedSource") != selected_source
        or address != role_base + AGGREGATE_OFFSET
        or watchpoint.get("byteCount") != WATCHPOINT_BYTE_COUNT
        or not isinstance(watchpoint.get("deprecatedHardwareIndex"), int)
        or watchpoint.get("initialRoleStateSHA256")
        != hashlib.sha256(initial_role).hexdigest()
        or initial_role[AGGREGATE_OFFSET : AGGREGATE_OFFSET + WATCHPOINT_BYTE_COUNT]
        != initial
    ):
        raise ValueError("aggregate watchpoint identity differs")
    if not 0 <= marker_record_index < len(marker_records):
        raise ValueError("aggregate watchpoint arm provenance differs")
    arm_record = mapping(
        marker_records[marker_record_index], "watchpoint arm marker record"
    )
    arm_record_sequence = integer(
        arm_record.get("callbackSequence"), "watchpoint arm marker sequence"
    )
    arm_addresses = mapping(
        arm_record.get("addresses"), "watchpoint arm marker addresses"
    )
    if (
        arm_record.get("recordIndex") != marker_record_index
        or arm_record.get("markerName") != marker_name
        or arm_record.get("watchArmCandidate") is not True
        or arm_record.get("selectedSource") is not True
        or arm_addresses.get("source") != selected_source
        or arm_addresses.get("x19") != role_base
        or arm_record_sequence >= arm_sequence
    ):
        raise ValueError("aggregate watchpoint arm provenance differs")
    if arm_mode == "retrospective-source-selection":
        retrospective_candidates = [
            mapping(record, "retrospective watchpoint candidate")
            for record in marker_records
            if mapping(record, "retrospective watchpoint marker").get(
                "watchArmCandidate"
            )
            is True
            and mapping(record, "retrospective watchpoint source").get(
                "selectedSource"
            )
            is True
            and mapping(record, "retrospective watchpoint timing").get(
                "sourceKnownAtHit"
            )
            is False
        ]
        if (
            arm_record.get("sourceKnownAtHit") is not False
            or arm_sequence <= source_sequence
            or not retrospective_candidates
            or marker_record_index
            != max(
                retrospective_candidates,
                key=lambda record: integer(
                    record.get("callbackSequence"),
                    "retrospective watchpoint candidate sequence",
                ),
            ).get("recordIndex")
        ):
            raise ValueError("retrospective watchpoint arm differs")
    elif arm_mode == "live-selected-marker":
        if (
            arm_record.get("sourceKnownAtHit") is not True
            or arm_record_sequence <= source_sequence
            or arm_sequence != arm_record_sequence + 1
        ):
            raise ValueError("live watchpoint arm differs")
    else:
        raise ValueError("aggregate watchpoint arm mode differs")

    code_windows = list(sequence(trace.get("codeWindows"), "writer code windows"))
    window_payloads = []
    for index, value_window in enumerate(code_windows):
        label = f"writer code window {index}"
        window = mapping(value_window, label)
        start = integer(window.get("startAddress"), f"{label} start")
        if window.get("byteCount") != PC_CENTERED_CODE_WINDOW_BYTE_COUNT:
            raise ValueError(f"{label} bounds differ")
        payload = _payload(
            window.get("hex"), PC_CENTERED_CODE_WINDOW_BYTE_COUNT, label
        )
        if (
            window.get("source") != "pc-centered"
            or window.get("containsStopPC") is not True
            or window.get("sha256") != hashlib.sha256(payload).hexdigest()
            or not 0
            <= integer(window.get("stopPCOffset"), f"{label} stop offset")
            < len(payload)
        ):
            raise ValueError(f"{label} identity differs")
        window_payloads.append((start, payload))

    events = list(sequence(trace.get("watchpointEvents"), "watchpoint events"))
    if (
        not 1 <= len(events) <= MAXIMUM_WATCHPOINT_HIT_COUNT
        or trace.get("finalWatchpointEventCount") != len(events)
        or trace.get("watchpointHitCount") != len(events)
    ):
        raise ValueError("watchpoint event bounds differ")
    before = initial
    changed_count = 0
    writer_pcs = set()
    for index, value_event in enumerate(events):
        label = f"watchpoint event {index}"
        event = mapping(value_event, label)
        _require_callback(
            order,
            event.get("callbackSequence"),
            "aggregate-watchpoint-hit",
            f"{label} callback",
        )
        after = _payload(event.get("afterHex"), WATCHPOINT_BYTE_COUNT, label)
        event_before = _payload(
            event.get("beforeHex"), WATCHPOINT_BYTE_COUNT, label
        )
        changed = event_before != after
        stop_pc = integer(event.get("stopPC"), f"{label} stop PC")
        if (
            event.get("eventIndex") != index
            or event.get("watchpointID") != watch_id
            or event.get("watchpointHitIndex") != index + 1
            or integer(event.get("threadID"), f"{label} thread") <= 0
            or event.get("watchedAddress") != address
            or event_before != before
            or event.get("valueChanged") is not changed
        ):
            raise ValueError(f"{label} identity differs")
        frame = writer_base.frame_record(event.get("frame"), f"{label} frame")
        if frame.get("pc") != stop_pc:
            raise ValueError(f"{label} frame PC differs")
        _generic_backtrace(event.get("backtrace"), f"{label} backtrace", frame)
        window_index = integer(event.get("codeWindowIndex"), f"{label} window")
        if not 0 <= window_index < len(window_payloads):
            raise ValueError(f"{label} code-window index differs")
        window_start, payload = window_payloads[window_index]
        if not window_start <= stop_pc < window_start + len(payload):
            raise ValueError(f"{label} code-window containment differs")
        role_after = _memory_payload(
            event.get("roleStateAfter"),
            f"{label} role state",
            expected_address=role_base,
            expected_byte_count=ROLE_STATE_BYTE_COUNT,
        )
        if (
            role_after[AGGREGATE_OFFSET : AGGREGATE_OFFSET + WATCHPOINT_BYTE_COUNT]
            != after
        ):
            raise ValueError(f"{label} watched role alias differs")
        writer_base.private_fields(
            event.get("privateFieldsAfter"), f"{label} private fields"
        )
        writer_base.operand_snapshot(
            event.get("operandSnapshot"),
            f"{label} operands",
            object_addresses,
            is_prepare_layer=(frame.get("function") == merge_base.PREPARE_LAYER_FUNCTION),
        )
        changed_count += changed
        writer_pcs.add(stop_pc)
        before = after
    if (
        changed_count < MINIMUM_CHANGED_WATCHPOINT_EVENT_COUNT
        or trace.get("finalChangedWatchpointEventCount") != changed_count
    ):
        raise ValueError("changed watchpoint coverage differs")
    return len(events), changed_count, writer_pcs


def validate(trace_path: Path) -> dict[str, Any]:
    trace_bytes = trace_path.read_bytes()
    trace = mapping(json.loads(trace_bytes), "prepare_layer full-path trace")
    if (
        trace.get("prepareLayerFullPathTraceSchemaVersion")
        != EXPECTED_TRACE_SCHEMA_VERSION
        or trace.get("classification") != EXPECTED_CLASSIFICATION
        or trace.get("status") != "finalized"
        or trace.get("statusBeforeFinalization")
        not in {"source-selected-path-trace-active", "watchpoint-hit-limit-reached"}
        or mapping(trace.get("configuration"), "trace configuration")
        != EXPECTED_CONFIGURATION
        or list(sequence(trace.get("failures"), "trace failures"))
        or trace.get("finalFailureCount") != 0
    ):
        raise ValueError("trace envelope differs")
    order = _callback_order(trace)
    prepare_start, prepare_module, full_code, _static_markers = _static_gates(
        trace, order
    )
    chain, selected_source = construction_base._selected_object_chain(trace)
    object_addresses = mapping(chain.get("addresses"), "selected object addresses")
    source_sequence = _require_callback(
        order,
        chain.get("callbackSequence"),
        "source-selected",
        "source-selection callback",
    )
    late_count = integer(trace.get("lateCandidateCount"), "late candidate count")
    if (
        late_count != chain.get("selectedLateCandidateIndex")
        or not 1 <= late_count <= MAXIMUM_LATE_CANDIDATE_COUNT
        or len(sequence(trace.get("lateCandidateDiagnostics"), "late diagnostics"))
        > MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT
        or source_sequence
        <= mapping(trace.get("prepareLayer"), "prepare layer").get(
            "callbackSequence"
        )
    ):
        raise ValueError("source selection accounting differs")
    retained, selected, distinct_aggregates = _marker_records(
        trace,
        order,
        prepare_start=prepare_start,
        prepare_module=prepare_module,
        selected_source=selected_source,
    )
    event_count, changed_count, writer_pcs = _watchpoint_evidence(
        trace,
        order,
        object_addresses=object_addresses,
        selected_source=selected_source,
        source_sequence=source_sequence,
        marker_records=list(sequence(trace.get("markerRecords"), "marker records")),
    )
    return {
        "prepareLayerFullPathTraceValidationSchemaVersion": VALIDATION_SCHEMA_VERSION,
        "classification": EXPECTED_VALIDATION_CLASSIFICATION,
        "inputTrace": trace_path.name,
        "inputTraceSHA256": hashlib.sha256(trace_bytes).hexdigest(),
        "conclusion": "success",
        "prospectiveGatePassed": True,
        "aggregate": {
            "prepareLayerFullCodeByteCount": len(full_code),
            "prepareLayerFullCodeSHA256": hashlib.sha256(full_code).hexdigest(),
            "retainedMarkerCounts": dict(sorted(retained.items())),
            "selectedMarkerCounts": dict(sorted(selected.items())),
            "distinctSelectedLaterAggregateCount": distinct_aggregates,
            "watchpointEventCount": event_count,
            "changedWatchpointEventCount": changed_count,
            "distinctWriterPCCount": len(writer_pcs),
            "writerPCs": sorted(writer_pcs),
        },
        "sealedConclusion": {
            "exactPrepareLayerEntryProved": True,
            "completePrepareLayerCodeCaptured": True,
            "selectedLaterPathMarkersCaptured": True,
            "selectedAggregateWriterEventCaptured": True,
            "writerInstructionSemanticsOpened": False,
            "completePublicCropRuleRecovered": False,
            "unseenGeometryTransferPassed": False,
            "productionShaderAuthorized": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = validate(arguments.trace)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
