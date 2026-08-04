#!/usr/bin/env python3
"""Validate the sealed live-frame-qualified ``prepare_layer`` writer trace."""

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_capture_backdrop_writer_trace as writer_base
import validate_layer_shapes_construction_trace as construction_base
import validate_layer_shapes_merge_trace as merge_base
import validate_prepare_layer_full_path_trace as full_base


EXPECTED_TRACE_SCHEMA_VERSION = 1
VALIDATION_SCHEMA_VERSION = 1
EXPECTED_CLASSIFICATION = (
    "preregistered-live-selected-prepare-layer-frame-qualified-aggregate-"
    "origin-writer-trace; writer-semantics-public-crop-law-unseen-"
    "transfer-and-product-parity-remain-sealed"
)
EXPECTED_VALIDATION_CLASSIFICATION = (
    "prospective-integrity-gate-for-live-selected-prepare-layer-frame-"
    "qualified-aggregate-writer; semantics-remain-sealed"
)
PREPARE_LAYER_FULL_CODE_SHA256 = (
    "fe58001369708e0276599f26865be03fdf1dd2348524f92a72c1427be8d1817c"
)
LIVE_ARM_MARKER_NAME = "sourceLaterHandle"
LIVE_ARM_MARKER_OFFSET = 0x3EF0
MAXIMUM_PRESELECTION_MARKER_RECORD_COUNT = 32
MAXIMUM_MARKER_HIT_COUNT = 4096
MAXIMUM_RAW_WATCHPOINT_HIT_COUNT = 8192
MAXIMUM_IGNORED_WATCHPOINT_DIAGNOSTIC_COUNT = 64
MAXIMUM_QUALIFIED_WATCHPOINT_EVENT_COUNT = 24
PREPARE_FRAME_REGISTER_NAMES = ("x19", "x28", "x29", "x30", "sp", "pc")
EXPECTED_CONFIGURATION = {
    "captureBackdropSymbol": merge_base.CAPTURE_BACKDROP_SYMBOL,
    "captureBackdropCodeByteCount": full_base.CAPTURE_BACKDROP_CODE_BYTE_COUNT,
    "captureBackdropCodeSHA256": merge_base.CAPTURE_BACKDROP_CODE_SHA256,
    "captureBackdropLateOffset": full_base.CAPTURE_BACKDROP_LATE_OFFSET,
    "prepareLayerFunction": merge_base.PREPARE_LAYER_FUNCTION,
    "prepareLayerSymbolByteCount": full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
    "prepareLayerFullCodeSHA256": PREPARE_LAYER_FULL_CODE_SHA256,
    "knownPrepareLayerWindows": [
        {"offset": offset, "byteCount": count, "sha256": digest}
        for offset, count, digest in full_base.KNOWN_PREPARE_LAYER_WINDOWS
    ],
    "unionHelperRelativeToPrepareLayer": (
        full_base.UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
    ),
    "unionHelperSymbolName": full_base.UNION_HELPER_SYMBOL_NAME,
    "unionHelperSymbolByteCount": full_base.UNION_HELPER_SYMBOL_BYTE_COUNT,
    "unionHelperSymbolSHA256": full_base.UNION_HELPER_SYMBOL_SHA256,
    "liveArmMarkerName": LIVE_ARM_MARKER_NAME,
    "liveArmMarkerOffset": LIVE_ARM_MARKER_OFFSET,
    "maximumPreselectionMarkerRecordCount": (
        MAXIMUM_PRESELECTION_MARKER_RECORD_COUNT
    ),
    "maximumMarkerHitCount": MAXIMUM_MARKER_HIT_COUNT,
    "roleStateByteCount": full_base.ROLE_STATE_BYTE_COUNT,
    "aggregateOffset": full_base.AGGREGATE_OFFSET,
    "aggregateByteCount": full_base.AGGREGATE_BYTE_COUNT,
    "watchpointByteCount": full_base.WATCHPOINT_BYTE_COUNT,
    "maximumRawWatchpointHitCount": MAXIMUM_RAW_WATCHPOINT_HIT_COUNT,
    "maximumIgnoredWatchpointDiagnosticCount": (
        MAXIMUM_IGNORED_WATCHPOINT_DIAGNOSTIC_COUNT
    ),
    "maximumQualifiedWatchpointEventCount": (
        MAXIMUM_QUALIFIED_WATCHPOINT_EVENT_COUNT
    ),
    "prepareFrameRegisterNames": list(PREPARE_FRAME_REGISTER_NAMES),
    "maximumLateCandidateCount": full_base.MAXIMUM_LATE_CANDIDATE_COUNT,
    "maximumLateCandidateDiagnosticCount": (
        full_base.MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT
    ),
    "maximumBacktraceFrameCount": full_base.MAXIMUM_BACKTRACE_FRAME_COUNT,
    "pcCenteredCodeWindowByteCount": (
        full_base.PC_CENTERED_CODE_WINDOW_BYTE_COUNT
    ),
    "pcCenteredCodeWindowBacktrack": (
        full_base.PC_CENTERED_CODE_WINDOW_BACKTRACK
    ),
    "stackSnapshotByteCount": full_base.STACK_SNAPSHOT_BYTE_COUNT,
    "registerPointerSnapshotByteCount": (
        full_base.REGISTER_POINTER_SNAPSHOT_BYTE_COUNT
    ),
    "registerPointerSnapshotBacktrack": (
        full_base.REGISTER_POINTER_SNAPSHOT_BACKTRACK
    ),
    "pointerProbeAddressRange": [
        full_base.MINIMUM_POINTER_PROBE_ADDRESS,
        full_base.MAXIMUM_POINTER_PROBE_ADDRESS,
    ],
    "generalRegisterNames": list(full_base.GENERAL_REGISTER_NAMES),
    "simdRegisterNames": list(full_base.SIMD_REGISTER_NAMES),
    "pointerProbeRegisterNames": list(full_base.POINTER_PROBE_REGISTER_NAMES),
    "prepareLayerRoleRegisterNames": list(
        full_base.PREPARE_LAYER_ROLE_REGISTER_NAMES
    ),
    "objectSnapshotSpecs": [
        {"base": base_name, "byteCount": byte_count}
        for base_name, byte_count in full_base.OBJECT_SNAPSHOT_SPECS
    ],
    "watchpointArmRule": (
        "never arm retrospectively; arm once at the first source-known live "
        "+0x3ef0 marker whose x28 is the exact selected source; require marker "
        "aggregate bytes to equal watchpoint initial bytes"
    ),
    "watchpointQualificationRule": (
        "retain a hardware stop only when an exact prepare_layer frame in its "
        "live backtrace has unwound x19 equal to the watched role base and "
        "unwound x28 equal to the selected source"
    ),
}
MINIMUM_CHANGED_QUALIFIED_EVENT_COUNT = 1


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
    if not items or final != len(items):
        raise ValueError("callback sequence bounds differ")
    result = {}
    for expected, value_item in enumerate(items, start=1):
        item = mapping(value_item, f"callback order {expected}")
        number = integer(item.get("sequence"), "callback sequence")
        kind = item.get("kind")
        if number != expected or not isinstance(kind, str) or not kind:
            raise ValueError("callback sequence identity differs")
        result[number] = kind
    return result


def _require_callback(
    order: Mapping[int, str], value: Any, expected_kind: str, label: str
) -> int:
    number = integer(value, label)
    if order.get(number) != expected_kind:
        raise ValueError(f"{label} identity differs")
    return number


def _registers(value: Any, names: Sequence[str], label: str) -> dict[str, int]:
    records = list(sequence(value, label))
    if len(records) != len(names):
        raise ValueError(f"{label} inventory differs")
    result = {}
    for name, value_record in zip(names, records, strict=True):
        record = writer_base.register_record(
            value_record, name, 8, f"{label} {name}"
        )
        result[name] = integer(
            record.get("unsignedValue"), f"{label} {name} value"
        )
    return result


def _generic_backtrace(
    value: Any, label: str, first_frame: Mapping[str, Any]
) -> list[Mapping[str, Any]]:
    values = list(sequence(value, label))
    if not values or len(values) > full_base.MAXIMUM_BACKTRACE_FRAME_COUNT:
        raise ValueError(f"{label} bounds differ")
    frames = [
        writer_base.frame_record(item, f"{label} frame {index}")
        for index, item in enumerate(values)
    ]
    if frames[0] != first_frame:
        raise ValueError(f"{label} first frame differs")
    return frames


def _generic_module(value: Any, label: str) -> Mapping[str, Any]:
    module = mapping(value, label)
    valid = module.get("valid")
    if valid is False:
        return module
    if valid is not True or not isinstance(module.get("path"), str):
        raise ValueError(f"{label} identity differs")
    load_address = module.get("loadAddress")
    if load_address is not None:
        integer(load_address, f"{label} load address")
    return module


def _static_gates(
    trace: Mapping[str, Any], order: Mapping[int, str]
) -> tuple[int, Mapping[str, Any], bytes, int, int]:
    capture_entry_id = integer(
        trace.get("captureBackdropEntryBreakpointID"),
        "capture_backdrop entry breakpoint ID",
    )
    prepare_entry_id = integer(
        trace.get("prepareLayerEntryBreakpointID"),
        "prepare_layer entry breakpoint ID",
    )
    if (
        capture_entry_id <= 0
        or prepare_entry_id <= 0
        or capture_entry_id == prepare_entry_id
    ):
        raise ValueError("entry breakpoint identity differs")

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
    late_id = integer(capture.get("lateBreakpointID"), "late breakpoint ID")
    if (
        integer(capture.get("symbolAddress"), "capture_backdrop address") <= 0
        or capture.get("codeByteCount")
        != full_base.CAPTURE_BACKDROP_CODE_BYTE_COUNT
        or capture.get("codeSHA256") != merge_base.CAPTURE_BACKDROP_CODE_SHA256
        or late_id <= 0
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
        or end - start != full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        or prepare.get("symbolByteCount")
        != full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        or prepare_module != capture_module
        or prepare.get("callbackPC") != start
        or prepare.get("callbackLocationAddress") != start
        or entry_locations != [start]
        or entry_id != prepare_entry_id
        or prepare_sequence >= capture_sequence
    ):
        raise ValueError("prepare_layer exact entry differs")
    full_code = _memory_payload(
        prepare.get("fullCode"),
        "full prepare_layer code",
        expected_address=start,
        expected_byte_count=full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
    )
    if hashlib.sha256(full_code).hexdigest() != PREPARE_LAYER_FULL_CODE_SHA256:
        raise ValueError("full prepare_layer code differs")
    known_values = list(sequence(prepare.get("knownWindows"), "known windows"))
    if len(known_values) != len(full_base.KNOWN_PREPARE_LAYER_WINDOWS):
        raise ValueError("known window inventory differs")
    for value_item, expected in zip(
        known_values, full_base.KNOWN_PREPARE_LAYER_WINDOWS, strict=True
    ):
        item = mapping(value_item, "known window")
        offset, byte_count, digest = expected
        if (
            item
            != {"offset": offset, "byteCount": byte_count, "sha256": digest}
            or hashlib.sha256(
                full_code[offset : offset + byte_count]
            ).hexdigest()
            != digest
        ):
            raise ValueError("known prepare_layer window differs")

    helper = mapping(prepare.get("unionHelper"), "union helper")
    helper_address = start + full_base.UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
    helper_symbol = mapping(helper.get("symbol"), "union helper symbol")
    if (
        helper.get("address") != helper_address
        or helper.get("relativeToPrepareLayer")
        != full_base.UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
        or merge_base.module_record(helper.get("module"), "union helper module")
        != prepare_module
        or helper_symbol.get("valid") is not True
        or helper_symbol.get("name") != full_base.UNION_HELPER_SYMBOL_NAME
        or helper_symbol.get("startAddress") != helper_address
        or helper_symbol.get("endAddress")
        != helper_address + full_base.UNION_HELPER_SYMBOL_BYTE_COUNT
        or helper.get("symbolCodeSHA256")
        != full_base.UNION_HELPER_SYMBOL_SHA256
    ):
        raise ValueError("union helper gate differs")

    marker = mapping(prepare.get("liveArmMarker"), "live arm marker")
    marker_id = integer(marker.get("breakpointID"), "live marker breakpoint ID")
    if (
        marker.get("name") != LIVE_ARM_MARKER_NAME
        or marker.get("offset") != LIVE_ARM_MARKER_OFFSET
        or marker.get("address") != start + LIVE_ARM_MARKER_OFFSET
        or marker.get("instructionRawLittleEndianHex")
        != full_code[LIVE_ARM_MARKER_OFFSET : LIVE_ARM_MARKER_OFFSET + 4].hex()
        or marker_id <= max(capture_entry_id, prepare_entry_id)
        or late_id <= marker_id
    ):
        raise ValueError("live arm marker gate differs")
    return start, prepare_module, full_code, marker_id, capture_sequence


def _marker_records(
    trace: Mapping[str, Any],
    order: Mapping[int, str],
    *,
    prepare_start: int,
    prepare_module: Mapping[str, Any],
    selected_source: int,
    source_sequence: int,
) -> tuple[list[Mapping[str, Any]], list[bytes], int]:
    values = list(
        sequence(trace.get("liveArmMarkerRecords"), "live arm marker records")
    )
    if trace.get("finalMarkerRecordCount") != len(values) or not values:
        raise ValueError("live marker record count differs")
    records = []
    roles = []
    preselection_count = 0
    selected_count = 0
    source_known_count = 0
    previous_callback = 0
    for index, value_record in enumerate(values):
        label = f"live marker record {index}"
        record = mapping(value_record, label)
        callback = _require_callback(
            order,
            record.get("callbackSequence"),
            "live-arm-marker",
            f"{label} callback",
        )
        role_base = integer(record.get("roleBase"), f"{label} role base")
        source = integer(record.get("source"), f"{label} source")
        source_known = record.get("sourceKnownAtHit")
        is_selected = source == selected_source
        if (
            record.get("recordIndex") != index
            or callback <= previous_callback
            or not isinstance(source_known, bool)
            or record.get("selectedSource") is not is_selected
            or source_known and not is_selected
            or source_known and callback <= source_sequence
            or not source_known and callback >= source_sequence
            or integer(record.get("threadID"), f"{label} thread") <= 0
            or record.get("pc") != prepare_start + LIVE_ARM_MARKER_OFFSET
        ):
            raise ValueError(f"{label} identity differs")
        merge_base.frame_record(
            record.get("frame"),
            f"{label} frame",
            expected_pc=prepare_start + LIVE_ARM_MARKER_OFFSET,
            expected_symbol_start=prepare_start,
            expected_module=prepare_module,
        )
        merge_base.backtrace(
            record.get("backtrace"),
            f"{label} backtrace",
            expected_first_pc=prepare_start + LIVE_ARM_MARKER_OFFSET,
            expected_symbol_start=prepare_start,
            expected_module=prepare_module,
        )
        registers = _registers(
            record.get("registers"), PREPARE_FRAME_REGISTER_NAMES, f"{label} registers"
        )
        if (
            registers["x19"] != role_base
            or registers["x28"] != source
            or registers["pc"] != prepare_start + LIVE_ARM_MARKER_OFFSET
        ):
            raise ValueError(f"{label} register aliases differ")
        role = _memory_payload(
            record.get("roleState"),
            f"{label} role state",
            expected_address=role_base,
            expected_byte_count=full_base.ROLE_STATE_BYTE_COUNT,
        )
        aggregate = role[
            full_base.AGGREGATE_OFFSET : full_base.AGGREGATE_OFFSET
            + full_base.AGGREGATE_BYTE_COUNT
        ]
        if (
            _payload(
                record.get("aggregateHex"),
                full_base.AGGREGATE_BYTE_COUNT,
                f"{label} aggregate",
            )
            != aggregate
        ):
            raise ValueError(f"{label} aggregate alias differs")
        if source_known:
            source_known_count += 1
        else:
            preselection_count += 1
        selected_count += is_selected
        previous_callback = callback
        records.append(record)
        roles.append(role)
    if (
        source_known_count != 1
        or records[-1].get("sourceKnownAtHit") is not True
        or preselection_count > MAXIMUM_PRESELECTION_MARKER_RECORD_COUNT
        or trace.get("finalSelectedMarkerRecordCount") != selected_count
    ):
        raise ValueError("live marker source coverage differs")
    hits = integer(trace.get("markerHitCount"), "marker hit count")
    rejected = integer(
        trace.get("rejectedMarkerHitCount"), "rejected marker hit count"
    )
    discarded = integer(
        trace.get("discardedMarkerHitCount"), "discarded marker hit count"
    )
    if (
        discarded != 0
        or hits != len(records) + rejected + discarded
        or hits > MAXIMUM_MARKER_HIT_COUNT
    ):
        raise ValueError("live marker accounting differs")
    return records, roles, preselection_count


def _watchpoint_arm(
    trace: Mapping[str, Any],
    order: Mapping[int, str],
    *,
    records: Sequence[Mapping[str, Any]],
    roles: Sequence[bytes],
    selected_source: int,
    source_sequence: int,
) -> tuple[int, int, int, bytes, int]:
    watchpoint = mapping(trace.get("aggregateWatchpoint"), "aggregate watchpoint")
    watch_id = integer(watchpoint.get("id"), "aggregate watchpoint ID")
    role_base = integer(watchpoint.get("roleBase"), "aggregate role base")
    address = integer(watchpoint.get("address"), "aggregate watched address")
    record_index = integer(
        watchpoint.get("markerRecordIndex"), "watchpoint marker record index"
    )
    marker_sequence = integer(
        watchpoint.get("markerCallbackSequence"),
        "watchpoint marker callback sequence",
    )
    arm_sequence = _require_callback(
        order,
        watchpoint.get("callbackSequence"),
        "live-aggregate-watchpoint-armed",
        "watchpoint arm callback",
    )
    initial = _payload(
        watchpoint.get("initialHex"),
        full_base.WATCHPOINT_BYTE_COUNT,
        "watchpoint initial",
    )
    initial_role = _payload(
        watchpoint.get("initialRoleStateHex"),
        full_base.ROLE_STATE_BYTE_COUNT,
        "watchpoint initial role state",
    )
    if not 0 <= record_index < len(records):
        raise ValueError("watchpoint arm provenance differs")
    record = records[record_index]
    marker_role = roles[record_index]
    if (
        watch_id <= 0
        or watchpoint.get("selectedSource") != selected_source
        or address != role_base + full_base.AGGREGATE_OFFSET
        or watchpoint.get("byteCount") != full_base.WATCHPOINT_BYTE_COUNT
        or not isinstance(watchpoint.get("deprecatedHardwareIndex"), int)
        or watchpoint.get("initialRoleStateSHA256")
        != hashlib.sha256(initial_role).hexdigest()
        or initial_role != marker_role
        or initial_role[
            full_base.AGGREGATE_OFFSET : full_base.AGGREGATE_OFFSET
            + full_base.WATCHPOINT_BYTE_COUNT
        ]
        != initial
        or record_index != len(records) - 1
        or record.get("sourceKnownAtHit") is not True
        or record.get("selectedSource") is not True
        or record.get("source") != selected_source
        or record.get("roleBase") != role_base
        or record.get("callbackSequence") != marker_sequence
        or marker_sequence <= source_sequence
        or arm_sequence != marker_sequence + 1
    ):
        raise ValueError("watchpoint arm provenance differs")
    return watch_id, role_base, address, initial, arm_sequence


def _code_windows(trace: Mapping[str, Any]) -> list[tuple[int, bytes, int]]:
    values = list(sequence(trace.get("codeWindows"), "writer code windows"))
    result = []
    identities = set()
    for index, value_window in enumerate(values):
        label = f"writer code window {index}"
        window = mapping(value_window, label)
        start = integer(window.get("startAddress"), f"{label} start")
        stop_offset = integer(window.get("stopPCOffset"), f"{label} stop offset")
        payload = _payload(
            window.get("hex"),
            full_base.PC_CENTERED_CODE_WINDOW_BYTE_COUNT,
            label,
        )
        identity = (start, hashlib.sha256(payload).digest())
        if (
            window.get("byteCount")
            != full_base.PC_CENTERED_CODE_WINDOW_BYTE_COUNT
            or window.get("source") != "pc-centered"
            or window.get("containsStopPC") is not True
            or not 0 <= stop_offset < len(payload)
            or window.get("sha256") != hashlib.sha256(payload).hexdigest()
            or identity in identities
        ):
            raise ValueError(f"{label} identity differs")
        identities.add(identity)
        result.append((start, payload, stop_offset))
    return result


def _ignored_evidence(trace: Mapping[str, Any]) -> tuple[int, int, int]:
    values = list(
        sequence(
            trace.get("ignoredWatchpointDiagnostics"),
            "ignored watchpoint diagnostics",
        )
    )
    if len(values) > MAXIMUM_IGNORED_WATCHPOINT_DIAGNOSTIC_COUNT:
        raise ValueError("ignored diagnostic bounds differ")
    grouped_hits = 0
    grouped_prepare_hits = 0
    identities = set()
    for index, value_group in enumerate(values):
        label = f"ignored watchpoint diagnostic {index}"
        group = mapping(value_group, label)
        pc = integer(group.get("stopPC"), f"{label} stop PC")
        function = group.get("function")
        exact_prepare = group.get("exactPrepareFrameSeen")
        module = _generic_module(group.get("module"), f"{label} module")
        hit_count = integer(group.get("hitCount"), f"{label} hit count")
        changed_count = integer(
            group.get("changedCount"), f"{label} changed count"
        )
        _payload(
            group.get("firstBeforeHex"),
            full_base.WATCHPOINT_BYTE_COUNT,
            f"{label} first before",
        )
        _payload(
            group.get("lastAfterHex"),
            full_base.WATCHPOINT_BYTE_COUNT,
            f"{label} last after",
        )
        identity = (pc, function, exact_prepare, module.get("path"))
        if (
            pc <= 0
            or not isinstance(function, str)
            or not isinstance(exact_prepare, bool)
            or hit_count <= 0
            or not 0 <= changed_count <= hit_count
            or identity in identities
        ):
            raise ValueError(f"{label} identity differs")
        identities.add(identity)
        grouped_hits += hit_count
        if exact_prepare:
            grouped_prepare_hits += hit_count
    ignored = integer(
        trace.get("ignoredWatchpointHitCount"), "ignored watchpoint hit count"
    )
    ignored_prepare = integer(
        trace.get("ignoredPrepareFrameSeenCount"),
        "ignored prepare-frame-seen count",
    )
    unretained = integer(
        trace.get("unretainedIgnoredWatchpointHitCount"),
        "unretained ignored watchpoint hit count",
    )
    if (
        ignored != grouped_hits + unretained
        or not grouped_prepare_hits
        <= ignored_prepare
        <= grouped_prepare_hits + unretained
        or ignored_prepare > ignored
        or unretained < 0
        or unretained > 0
        and len(values) != MAXIMUM_IGNORED_WATCHPOINT_DIAGNOSTIC_COUNT
    ):
        raise ValueError("ignored watchpoint accounting differs")
    return ignored, ignored_prepare, unretained


def _qualified_events(
    trace: Mapping[str, Any],
    order: Mapping[int, str],
    *,
    prepare_start: int,
    prepare_module: Mapping[str, Any],
    object_addresses: Mapping[str, Any],
    selected_source: int,
    watch_id: int,
    role_base: int,
    watched_address: int,
    initial: bytes,
    arm_sequence: int,
) -> tuple[int, int, set[int], set[int]]:
    windows = _code_windows(trace)
    values = list(
        sequence(
            trace.get("qualifiedWatchpointEvents"),
            "qualified watchpoint events",
        )
    )
    qualified_count = integer(
        trace.get("qualifiedWatchpointHitCount"),
        "qualified watchpoint hit count",
    )
    if (
        not 1 <= len(values) <= MAXIMUM_QUALIFIED_WATCHPOINT_EVENT_COUNT
        or qualified_count != len(values)
        or trace.get("finalQualifiedWatchpointEventCount") != len(values)
        or not windows
    ):
        raise ValueError("qualified event bounds differ")
    changed_count = 0
    writer_pcs = set()
    prepare_offsets = set()
    previous_raw_index = 0
    previous_after = initial
    previous_callback = arm_sequence
    for index, value_event in enumerate(values):
        label = f"qualified watchpoint event {index}"
        event = mapping(value_event, label)
        callback = _require_callback(
            order,
            event.get("callbackSequence"),
            "qualified-live-aggregate-watchpoint-hit",
            f"{label} callback",
        )
        raw_index = integer(
            event.get("rawWatchpointHitIndex"), f"{label} raw hit index"
        )
        before = _payload(
            event.get("beforeHex"), full_base.WATCHPOINT_BYTE_COUNT, label
        )
        after = _payload(
            event.get("afterHex"), full_base.WATCHPOINT_BYTE_COUNT, label
        )
        changed = before != after
        stop_pc = integer(event.get("stopPC"), f"{label} stop PC")
        if (
            event.get("eventIndex") != index
            or event.get("watchpointID") != watch_id
            or event.get("qualifiedWatchpointHitIndex") != index + 1
            or raw_index <= previous_raw_index
            or callback <= previous_callback
            or integer(event.get("threadID"), f"{label} thread") <= 0
            or event.get("watchedAddress") != watched_address
            or event.get("valueChanged") is not changed
            or raw_index == previous_raw_index + 1
            and before != previous_after
        ):
            raise ValueError(f"{label} identity differs")
        frame = writer_base.frame_record(event.get("frame"), f"{label} frame")
        if frame.get("pc") != stop_pc:
            raise ValueError(f"{label} frame PC differs")
        backtrace = _generic_backtrace(
            event.get("backtrace"), f"{label} backtrace", frame
        )
        prepare_index = integer(
            event.get("prepareFrameIndex"), f"{label} prepare frame index"
        )
        if not 0 <= prepare_index < len(backtrace):
            raise ValueError(f"{label} prepare frame index differs")
        prepare_frame = mapping(event.get("prepareFrame"), f"{label} prepare frame")
        if prepare_frame != backtrace[prepare_index]:
            raise ValueError(f"{label} prepare frame ancestry differs")
        prepare_pc = integer(prepare_frame.get("pc"), f"{label} prepare frame PC")
        merge_base.frame_record(
            prepare_frame,
            f"{label} exact prepare frame",
            expected_pc=prepare_pc,
            expected_symbol_start=prepare_start,
            expected_module=prepare_module,
        )
        prepare_registers = _registers(
            event.get("prepareFrameRegisters"),
            PREPARE_FRAME_REGISTER_NAMES,
            f"{label} prepare frame registers",
        )
        if (
            prepare_registers["x19"] != role_base
            or prepare_registers["x28"] != selected_source
            or prepare_registers["pc"] != prepare_pc
        ):
            raise ValueError(f"{label} live ancestry qualification differs")
        window_index = integer(event.get("codeWindowIndex"), f"{label} window")
        if not 0 <= window_index < len(windows):
            raise ValueError(f"{label} code-window index differs")
        window_start, payload, stop_offset = windows[window_index]
        if stop_pc != window_start + stop_offset or not (
            window_start <= stop_pc < window_start + len(payload)
        ):
            raise ValueError(f"{label} code-window containment differs")
        role_after = _memory_payload(
            event.get("roleStateAfter"),
            f"{label} role state",
            expected_address=role_base,
            expected_byte_count=full_base.ROLE_STATE_BYTE_COUNT,
        )
        if (
            role_after[
                full_base.AGGREGATE_OFFSET : full_base.AGGREGATE_OFFSET
                + full_base.WATCHPOINT_BYTE_COUNT
            ]
            != after
        ):
            raise ValueError(f"{label} watched role alias differs")
        writer_base.private_fields(
            event.get("privateFieldsAfter"), f"{label} private fields"
        )
        operand_snapshot, successful_role_registers = writer_base.operand_snapshot(
            event.get("operandSnapshot"),
            f"{label} operands",
            object_addresses,
            is_prepare_layer=(
                frame.get("function") == merge_base.PREPARE_LAYER_FUNCTION
            ),
        )
        if frame.get("function") == merge_base.PREPARE_LAYER_FUNCTION:
            general_records = sequence(
                mapping(
                    operand_snapshot.get("registers"),
                    f"{label} operand registers",
                ).get("general"),
                f"{label} operand general registers",
            )
            general = {}
            for value_record in general_records:
                record = mapping(value_record, f"{label} general register")
                general[record.get("name")] = record.get("unsignedValue")
            if (
                "x19" not in successful_role_registers
                or general.get("x19") != role_base
                or general.get("x28") != selected_source
                or general.get("pc") != stop_pc
            ):
                raise ValueError(f"{label} direct writer role operands differ")
        changed_count += changed
        writer_pcs.add(stop_pc)
        prepare_offsets.add(prepare_pc - prepare_start)
        previous_raw_index = raw_index
        previous_after = after
        previous_callback = callback
    if (
        changed_count < MINIMUM_CHANGED_QUALIFIED_EVENT_COUNT
        or trace.get("finalChangedQualifiedWatchpointEventCount") != changed_count
    ):
        raise ValueError("changed qualified event coverage differs")
    return len(values), changed_count, writer_pcs, prepare_offsets


def validate(trace_path: Path) -> dict[str, Any]:
    trace_bytes = trace_path.read_bytes()
    trace = mapping(json.loads(trace_bytes), "prepare_layer live-writer trace")
    if (
        trace.get("prepareLayerLiveWriterTraceSchemaVersion")
        != EXPECTED_TRACE_SCHEMA_VERSION
        or trace.get("classification") != EXPECTED_CLASSIFICATION
        or trace.get("status") != "finalized"
        or mapping(trace.get("configuration"), "trace configuration")
        != EXPECTED_CONFIGURATION
        or list(sequence(trace.get("failures"), "trace failures"))
        or trace.get("finalFailureCount") != 0
    ):
        raise ValueError("trace envelope differs")
    order = _callback_order(trace)
    prepare_start, prepare_module, full_code, _marker_id, _capture_sequence = (
        _static_gates(trace, order)
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
        or not 1 <= late_count <= full_base.MAXIMUM_LATE_CANDIDATE_COUNT
        or len(sequence(trace.get("lateCandidateDiagnostics"), "late diagnostics"))
        > full_base.MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT
        or source_sequence
        <= mapping(trace.get("captureBackdrop"), "capture backdrop").get(
            "callbackSequence"
        )
    ):
        raise ValueError("source selection accounting differs")
    marker_records, marker_roles, preselection_count = _marker_records(
        trace,
        order,
        prepare_start=prepare_start,
        prepare_module=prepare_module,
        selected_source=selected_source,
        source_sequence=source_sequence,
    )
    watch_id, role_base, watched_address, initial, arm_sequence = _watchpoint_arm(
        trace,
        order,
        records=marker_records,
        roles=marker_roles,
        selected_source=selected_source,
        source_sequence=source_sequence,
    )
    ignored_count, ignored_prepare_count, unretained_ignored_count = (
        _ignored_evidence(trace)
    )
    event_count, changed_count, writer_pcs, prepare_offsets = _qualified_events(
        trace,
        order,
        prepare_start=prepare_start,
        prepare_module=prepare_module,
        object_addresses=object_addresses,
        selected_source=selected_source,
        watch_id=watch_id,
        role_base=role_base,
        watched_address=watched_address,
        initial=initial,
        arm_sequence=arm_sequence,
    )
    raw_count = integer(
        trace.get("rawWatchpointHitCount"), "raw watchpoint hit count"
    )
    if (
        raw_count != ignored_count + event_count
        or not event_count <= raw_count <= MAXIMUM_RAW_WATCHPOINT_HIT_COUNT
    ):
        raise ValueError("raw watchpoint accounting differs")
    expected_status = (
        "qualified-watchpoint-hit-limit-reached"
        if event_count == MAXIMUM_QUALIFIED_WATCHPOINT_EVENT_COUNT
        else "qualified-live-writer-captured"
    )
    if trace.get("statusBeforeFinalization") != expected_status:
        raise ValueError("qualified writer terminal status differs")
    return {
        "prepareLayerLiveWriterTraceValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": EXPECTED_VALIDATION_CLASSIFICATION,
        "inputTrace": trace_path.name,
        "inputTraceSHA256": hashlib.sha256(trace_bytes).hexdigest(),
        "conclusion": "success",
        "prospectiveGatePassed": True,
        "aggregate": {
            "prepareLayerFullCodeByteCount": len(full_code),
            "prepareLayerFullCodeSHA256": hashlib.sha256(full_code).hexdigest(),
            "preselectionMarkerRecordCount": preselection_count,
            "rejectedMarkerHitCount": trace.get("rejectedMarkerHitCount"),
            "rawWatchpointHitCount": raw_count,
            "ignoredWatchpointHitCount": ignored_count,
            "ignoredPrepareFrameSeenCount": ignored_prepare_count,
            "unretainedIgnoredWatchpointHitCount": unretained_ignored_count,
            "qualifiedWatchpointEventCount": event_count,
            "changedQualifiedWatchpointEventCount": changed_count,
            "distinctWriterPCCount": len(writer_pcs),
            "writerPCs": sorted(writer_pcs),
            "prepareLayerFrameOffsets": sorted(prepare_offsets),
        },
        "sealedConclusion": {
            "exactPrepareLayerEntryProved": True,
            "completePrepareLayerCodeCaptured": True,
            "retrospectiveWatchpointArmRejected": True,
            "liveSelectedWatchpointArmed": True,
            "qualifiedSelectedWriterEventCaptured": True,
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
