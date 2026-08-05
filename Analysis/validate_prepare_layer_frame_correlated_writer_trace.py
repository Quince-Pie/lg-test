#!/usr/bin/env python3
"""Validate the sealed same-frame ``prepare_layer`` writer correlation."""

import argparse
import hashlib
import json
from collections import defaultdict
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
    "preregistered-still-live-frame-correlated-prepare-layer-writer-trace; "
    "writer-semantics-public-crop-law-unseen-transfer-and-product-parity-"
    "remain-sealed"
)
EXPECTED_VALIDATION_CLASSIFICATION = (
    "prospective-integrity-gate-for-still-live-frame-correlated-prepare-"
    "layer-writer-suffix; semantics-remain-sealed"
)
PREPARE_LAYER_FULL_CODE_SHA256 = (
    "fe58001369708e0276599f26865be03fdf1dd2348524f92a72c1427be8d1817c"
)
LIVE_SELECTION_MARKER_NAME = "sourceLaterHandle"
LIVE_SELECTION_MARKER_OFFSET = 0x3EF0
PREPARE_FRAME_REGISTER_NAMES = ("x19", "x28", "x29", "x30", "sp", "pc")
MAXIMUM_WRITER_SITE_HIT_COUNT = 4096
MAXIMUM_RECORD_COUNT_PER_WRITER_SITE = 512
MAXIMUM_LIVE_SELECTION_MARKER_HIT_COUNT = 4096
MAXIMUM_PRESELECTION_MARKER_DIAGNOSTIC_COUNT = 32
MAXIMUM_REJECTED_WRITER_DIAGNOSTIC_COUNT = 64
MINIMUM_SELECTED_DISTINCT_AGGREGATE_COUNT = 2
MINIMUM_SELECTED_CHANGING_TRANSITION_COUNT = 1

WRITER_SITES = (
    {
        "name": "rectApplyTransformAfter",
        "relativeToPrepareLayer": -1207012,
        "function": "CA::Rect::apply_transform(CA::SimpleTransform const&)",
        "epochStart": False,
        "openedByHardwareWatchpoint": True,
    },
    {
        "name": "rectUnapplyTransformAfter",
        "relativeToPrepareLayer": -1202604,
        "function": "CA::Rect::unapply_transform(CA::SimpleTransform const&)",
        "epochStart": False,
        "openedByHardwareWatchpoint": True,
    },
    {
        "name": "glassDODAfter0",
        "relativeToPrepareLayer": -90080,
        "function": (
            "CA::OGL::GlassBackgroundFilter::DOD(CA::Render::Filter const*, "
            "CA::Render::Layer const*, CA::Rect&) const"
        ),
        "epochStart": False,
        "openedByHardwareWatchpoint": True,
    },
    {
        "name": "glassDODAfter1",
        "relativeToPrepareLayer": -89720,
        "function": (
            "CA::OGL::GlassBackgroundFilter::DOD(CA::Render::Filter const*, "
            "CA::Render::Layer const*, CA::Rect&) const"
        ),
        "epochStart": False,
        "openedByHardwareWatchpoint": True,
    },
    {
        "name": "glassDODAfter2",
        "relativeToPrepareLayer": -89512,
        "function": (
            "CA::OGL::GlassBackgroundFilter::DOD(CA::Render::Filter const*, "
            "CA::Render::Layer const*, CA::Rect&) const"
        ),
        "epochStart": False,
        "openedByHardwareWatchpoint": True,
    },
    {
        "name": "unionBoundsStoreAfter",
        "relativeToPrepareLayer": -2588,
        "function": full_base.UNION_HELPER_SYMBOL_NAME,
        "epochStart": False,
        "openedByHardwareWatchpoint": True,
        "precedingInstructionRelativeToPrepareLayer": -2592,
        "precedingInstructionRawLittleEndianHex": "800600ad",
    },
    {
        "name": "zeroInitializationAfter",
        "relativeToPrepareLayer": 0xB60,
        "function": merge_base.PREPARE_LAYER_FUNCTION,
        "epochStart": True,
        "openedByHardwareWatchpoint": True,
        "precedingInstructionRelativeToPrepareLayer": 0xB5C,
        "precedingInstructionRawLittleEndianHex": "60a6803d",
    },
    {
        "name": "alternateAggregateCopyAfter",
        "relativeToPrepareLayer": 0x33F4,
        "function": merge_base.PREPARE_LAYER_FUNCTION,
        "epochStart": False,
        "openedByHardwareWatchpoint": False,
        "precedingInstructionRelativeToPrepareLayer": 0x33F0,
        "precedingInstructionRawLittleEndianHex": "608614ad",
    },
    {
        "name": "rangeClampStoreAfter",
        "relativeToPrepareLayer": 0x3974,
        "function": merge_base.PREPARE_LAYER_FUNCTION,
        "epochStart": False,
        "openedByHardwareWatchpoint": True,
        "precedingInstructionRelativeToPrepareLayer": 0x3970,
        "precedingInstructionRawLittleEndianHex": "608614ad",
    },
)
WRITER_SITE_BY_NAME = {site["name"]: site for site in WRITER_SITES}

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
    "liveSelectionMarkerName": LIVE_SELECTION_MARKER_NAME,
    "liveSelectionMarkerOffset": LIVE_SELECTION_MARKER_OFFSET,
    "writerSites": [dict(site) for site in WRITER_SITES],
    "maximumWriterSiteHitCount": MAXIMUM_WRITER_SITE_HIT_COUNT,
    "maximumRecordCountPerWriterSite": MAXIMUM_RECORD_COUNT_PER_WRITER_SITE,
    "maximumLiveSelectionMarkerHitCount": MAXIMUM_LIVE_SELECTION_MARKER_HIT_COUNT,
    "maximumPreselectionMarkerDiagnosticCount": (
        MAXIMUM_PRESELECTION_MARKER_DIAGNOSTIC_COUNT
    ),
    "maximumRejectedWriterDiagnosticCount": (
        MAXIMUM_REJECTED_WRITER_DIAGNOSTIC_COUNT
    ),
    "roleStateByteCount": full_base.ROLE_STATE_BYTE_COUNT,
    "aggregateOffset": full_base.AGGREGATE_OFFSET,
    "aggregateByteCount": full_base.AGGREGATE_BYTE_COUNT,
    "prepareFrameRegisterNames": list(PREPARE_FRAME_REGISTER_NAMES),
    "maximumLateCandidateCount": full_base.MAXIMUM_LATE_CANDIDATE_COUNT,
    "maximumLateCandidateDiagnosticCount": (
        full_base.MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT
    ),
    "maximumBacktraceFrameCount": full_base.MAXIMUM_BACKTRACE_FRAME_COUNT,
    "pcCenteredCodeWindowByteCount": full_base.PC_CENTERED_CODE_WINDOW_BYTE_COUNT,
    "pcCenteredCodeWindowBacktrack": full_base.PC_CENTERED_CODE_WINDOW_BACKTRACK,
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
    "objectSnapshotSpecs": [
        {"base": base, "byteCount": byte_count}
        for base, byte_count in full_base.OBJECT_SNAPSHOT_SPECS
    ],
    "frameCorrelationRule": (
        "at the first source-known +0x3ef0 marker whose x28 is the selected "
        "source, select only the writer suffix with identical thread ID, x19 "
        "role base, and x29 frame pointer, beginning at that frame identity's "
        "latest +0xb60 epoch-start record"
    ),
}


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
    values = list(sequence(trace.get("callbackOrder"), "callback order"))
    final = integer(trace.get("finalCallbackSequence"), "final callback sequence")
    if not values or final != len(values):
        raise ValueError("callback sequence bounds differ")
    result = {}
    for expected, value in enumerate(values, start=1):
        item = mapping(value, f"callback order {expected}")
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
    values = list(sequence(value, label))
    if len(values) != len(names):
        raise ValueError(f"{label} inventory differs")
    result = {}
    for name, record_value in zip(names, values, strict=True):
        record = writer_base.register_record(
            record_value, name, 8, f"{label} {name}"
        )
        result[name] = integer(
            record.get("unsignedValue"), f"{label} {name} value"
        )
    return result


def _module(value: Any, label: str) -> Mapping[str, Any]:
    return merge_base.module_record(value, label)


def _backtrace(value: Any, label: str) -> list[Mapping[str, Any]]:
    values = list(sequence(value, label))
    if not values or len(values) > full_base.MAXIMUM_BACKTRACE_FRAME_COUNT:
        raise ValueError(f"{label} bounds differ")
    return [
        writer_base.frame_record(item, f"{label} frame {index}")
        for index, item in enumerate(values)
    ]


def _static_gates(
    trace: Mapping[str, Any], order: Mapping[int, str]
) -> tuple[int, Mapping[str, Any], bytes, dict[str, Mapping[str, Any]], int]:
    capture_entry_id = integer(
        trace.get("captureBackdropEntryBreakpointID"), "capture entry breakpoint"
    )
    prepare_entry_id = integer(
        trace.get("prepareLayerEntryBreakpointID"), "prepare entry breakpoint"
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
        "capture callback",
    )
    capture_module = _module(capture.get("module"), "capture module")
    late_id = integer(capture.get("lateBreakpointID"), "late breakpoint")
    if (
        integer(capture.get("symbolAddress"), "capture address") <= 0
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
        "prepare callback",
    )
    start = integer(prepare.get("symbolStart"), "prepare start")
    end = integer(prepare.get("symbolEnd"), "prepare end")
    prepare_module = _module(prepare.get("module"), "prepare module")
    entry_id = integer(prepare.get("entryBreakpointID"), "prepare entry ID")
    locations = list(
        sequence(
            prepare.get("entryBreakpointLocationAddresses"),
            "prepare entry locations",
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
        or locations != [start]
        or entry_id != prepare_entry_id
        or prepare_sequence >= capture_sequence
    ):
        raise ValueError("prepare_layer exact entry differs")
    full_code = _memory_payload(
        prepare.get("fullCode"),
        "full prepare code",
        expected_address=start,
        expected_byte_count=full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
    )
    if hashlib.sha256(full_code).hexdigest() != PREPARE_LAYER_FULL_CODE_SHA256:
        raise ValueError("full prepare_layer code differs")
    known = list(sequence(prepare.get("knownWindows"), "known windows"))
    if len(known) != len(full_base.KNOWN_PREPARE_LAYER_WINDOWS):
        raise ValueError("known window inventory differs")
    for value, expected in zip(
        known, full_base.KNOWN_PREPARE_LAYER_WINDOWS, strict=True
    ):
        item = mapping(value, "known window")
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
        or _module(helper.get("module"), "union helper module") != prepare_module
        or helper_symbol.get("valid") is not True
        or helper_symbol.get("name") != full_base.UNION_HELPER_SYMBOL_NAME
        or helper_symbol.get("startAddress") != helper_address
        or helper_symbol.get("endAddress")
        != helper_address + full_base.UNION_HELPER_SYMBOL_BYTE_COUNT
        or helper.get("symbolCodeSHA256")
        != full_base.UNION_HELPER_SYMBOL_SHA256
    ):
        raise ValueError("union helper gate differs")
    values = list(sequence(prepare.get("writerSites"), "writer sites"))
    if len(values) != len(WRITER_SITES):
        raise ValueError("writer site inventory differs")
    site_records = {}
    breakpoint_ids = []
    for expected, value in zip(WRITER_SITES, values, strict=True):
        label = f"writer site {expected['name']}"
        item = mapping(value, label)
        for key, expected_value in expected.items():
            if item.get(key) != expected_value:
                raise ValueError(f"{label} configuration differs")
        address = start + expected["relativeToPrepareLayer"]
        breakpoint_id = integer(item.get("breakpointID"), f"{label} breakpoint")
        symbol = mapping(item.get("symbol"), f"{label} symbol")
        raw = _payload(
            item.get("precedingInstructionRawLittleEndianHex"), 4, label
        )
        symbol_start = integer(symbol.get("startAddress"), f"{label} start")
        symbol_end = integer(symbol.get("endAddress"), f"{label} end")
        if (
            item.get("address") != address
            or breakpoint_id <= max(capture_entry_id, prepare_entry_id)
            or _module(item.get("module"), f"{label} module") != prepare_module
            or symbol.get("valid") is not True
            or symbol.get("name") != expected["function"]
            or not symbol_start <= address < symbol_end
        ):
            raise ValueError(f"{label} identity differs")
        expected_raw = expected.get("precedingInstructionRawLittleEndianHex")
        if expected_raw is not None and raw.hex() != expected_raw:
            raise ValueError(f"{label} preceding instruction differs")
        relative = expected["relativeToPrepareLayer"]
        if relative >= 4 and raw != full_code[relative - 4 : relative]:
            raise ValueError(f"{label} embedded instruction differs")
        breakpoint_ids.append(breakpoint_id)
        site_records[expected["name"]] = item
    if (
        len(set(breakpoint_ids)) != len(breakpoint_ids)
        or breakpoint_ids != sorted(breakpoint_ids)
    ):
        raise ValueError("writer breakpoint identities differ")
    marker = mapping(prepare.get("liveSelectionMarker"), "selection marker")
    marker_id = integer(marker.get("breakpointID"), "selection marker breakpoint")
    if (
        marker.get("name") != LIVE_SELECTION_MARKER_NAME
        or marker.get("offset") != LIVE_SELECTION_MARKER_OFFSET
        or marker.get("address") != start + LIVE_SELECTION_MARKER_OFFSET
        or marker.get("instructionRawLittleEndianHex")
        != full_code[
            LIVE_SELECTION_MARKER_OFFSET : LIVE_SELECTION_MARKER_OFFSET + 4
        ].hex()
        or marker_id <= max(breakpoint_ids)
        or late_id <= marker_id
    ):
        raise ValueError("selection marker gate differs")
    return start, prepare_module, full_code, site_records, capture_sequence


def _code_windows(trace: Mapping[str, Any]) -> list[tuple[int, bytes, int]]:
    values = list(sequence(trace.get("codeWindows"), "code windows"))
    result = []
    identities = set()
    for index, value in enumerate(values):
        label = f"code window {index}"
        item = mapping(value, label)
        start = integer(item.get("startAddress"), f"{label} start")
        stop_offset = integer(item.get("stopPCOffset"), f"{label} stop offset")
        payload = _payload(
            item.get("hex"), full_base.PC_CENTERED_CODE_WINDOW_BYTE_COUNT, label
        )
        identity = (start, hashlib.sha256(payload).digest())
        if (
            item.get("byteCount") != full_base.PC_CENTERED_CODE_WINDOW_BYTE_COUNT
            or item.get("source") != "pc-centered"
            or item.get("containsStopPC") is not True
            or stop_offset != full_base.PC_CENTERED_CODE_WINDOW_BACKTRACK
            or item.get("sha256") != hashlib.sha256(payload).hexdigest()
            or identity in identities
        ):
            raise ValueError(f"{label} identity differs")
        identities.add(identity)
        result.append((start, payload, stop_offset))
    return result


def _top_operands(value: Any, label: str, *, expected_pc: int) -> dict[str, int]:
    snapshot = mapping(value, label)
    registers = mapping(snapshot.get("registers"), f"{label} registers")
    general_values = list(sequence(registers.get("general"), f"{label} general"))
    simd_values = list(sequence(registers.get("simd"), f"{label} SIMD"))
    if (
        len(general_values) != len(full_base.GENERAL_REGISTER_NAMES)
        or len(simd_values) != len(full_base.SIMD_REGISTER_NAMES)
    ):
        raise ValueError(f"{label} register inventory differs")
    general = {}
    for name, record_value in zip(
        full_base.GENERAL_REGISTER_NAMES, general_values, strict=True
    ):
        byte_count = 4 if name == "cpsr" else 8
        record = writer_base.register_record(
            record_value, name, byte_count, f"{label} register {name}"
        )
        general[name] = integer(
            record.get("unsignedValue"), f"{label} register {name} value"
        )
    for name, record_value in zip(
        full_base.SIMD_REGISTER_NAMES, simd_values, strict=True
    ):
        writer_base.register_record(
            record_value,
            name,
            4 if name in {"fpsr", "fpcr"} else 16,
            f"{label} register {name}",
        )
    if general["pc"] != expected_pc:
        raise ValueError(f"{label} PC alias differs")
    writer_base.memory_snapshot(
        snapshot.get("stack"),
        f"{label} stack",
        expected_address=general["sp"],
        expected_byte_count=full_base.STACK_SNAPSHOT_BYTE_COUNT,
    )
    probes = [
        mapping(item, f"{label} pointer probe")
        for item in sequence(
            snapshot.get("registerPointerProbes"), f"{label} pointer probes"
        )
    ]
    failures = [
        mapping(item, f"{label} pointer failure")
        for item in sequence(
            snapshot.get("registerPointerProbeFailures"),
            f"{label} pointer failures",
        )
    ]
    probe_count = integer(
        snapshot.get("registerPointerProbeCount"), f"{label} pointer count"
    )
    if probe_count != len(probes) + len(failures):
        raise ValueError(f"{label} pointer count differs")
    expected_groups: defaultdict[int, list[str]] = defaultdict(list)
    for name in full_base.POINTER_PROBE_REGISTER_NAMES:
        address = general[name]
        if (
            full_base.MINIMUM_POINTER_PROBE_ADDRESS
            <= address
            <= full_base.MAXIMUM_POINTER_PROBE_ADDRESS
        ):
            expected_groups[
                address - full_base.REGISTER_POINTER_SNAPSHOT_BACKTRACK
            ].append(name)
    observed_groups = {}
    for item, succeeded in [
        *((probe, True) for probe in probes),
        *((failure, False) for failure in failures),
    ]:
        address = integer(item.get("address"), f"{label} pointer address")
        register_value = integer(
            item.get("registerValue"), f"{label} pointer register value"
        )
        names = list(
            sequence(item.get("registerNames"), f"{label} pointer names")
        )
        if (
            address in observed_groups
            or register_value
            != address + full_base.REGISTER_POINTER_SNAPSHOT_BACKTRACK
            or names != expected_groups.get(address)
        ):
            raise ValueError(f"{label} pointer identity differs")
        observed_groups[address] = names
        if succeeded:
            writer_base.memory_snapshot(
                item,
                f"{label} pointer memory",
                expected_address=address,
                expected_byte_count=full_base.REGISTER_POINTER_SNAPSHOT_BYTE_COUNT,
            )
        elif not isinstance(item.get("message"), str) or not item["message"]:
            raise ValueError(f"{label} pointer failure differs")
    if observed_groups != dict(expected_groups):
        raise ValueError(f"{label} pointer inventory differs")
    return general


def _candidate_events(
    trace: Mapping[str, Any],
    order: Mapping[int, str],
    *,
    prepare_start: int,
    prepare_module: Mapping[str, Any],
    site_records: Mapping[str, Mapping[str, Any]],
    source_sequence: int,
) -> tuple[list[Mapping[str, Any]], dict[str, int]]:
    windows = _code_windows(trace)
    values = list(sequence(trace.get("writerCandidateEvents"), "writer events"))
    if trace.get("finalWriterCandidateEventCount") != len(values) or not values:
        raise ValueError("writer event count differs")
    retained = {name: 0 for name in WRITER_SITE_BY_NAME}
    last_by_frame: dict[tuple[int, int, int], int] = {}
    referenced_windows = set()
    events = []
    previous_callback = 0
    for index, value in enumerate(values):
        label = f"writer event {index}"
        event = mapping(value, label)
        name = event.get("siteName")
        if name not in WRITER_SITE_BY_NAME:
            raise ValueError(f"{label} site differs")
        site = WRITER_SITE_BY_NAME[name]
        site_record = site_records[name]
        callback = _require_callback(
            order,
            event.get("callbackSequence"),
            "writer-site:" + name,
            f"{label} callback",
        )
        stop_pc = prepare_start + site["relativeToPrepareLayer"]
        thread_id = integer(event.get("threadID"), f"{label} thread")
        source_known = event.get("sourceKnownAtHit")
        if (
            event.get("eventIndex") != index
            or callback <= previous_callback
            or event.get("siteRelativeToPrepareLayer")
            != site["relativeToPrepareLayer"]
            or event.get("epochStart") is not site["epochStart"]
            or not isinstance(source_known, bool)
            or source_known
            and callback <= source_sequence
            or not source_known
            and callback >= source_sequence
            or thread_id <= 0
            or event.get("stopPC") != stop_pc
        ):
            raise ValueError(f"{label} identity differs")
        frame = writer_base.frame_record(event.get("frame"), f"{label} frame")
        if (
            frame.get("pc") != stop_pc
            or frame.get("function") != site["function"]
            or mapping(frame.get("module"), f"{label} frame module")
            != prepare_module
        ):
            raise ValueError(f"{label} top frame differs")
        backtrace = _backtrace(event.get("backtrace"), f"{label} backtrace")
        if backtrace[0] != frame:
            raise ValueError(f"{label} backtrace head differs")
        prepare_index = integer(
            event.get("prepareFrameIndex"), f"{label} prepare frame index"
        )
        if not 0 <= prepare_index < len(backtrace):
            raise ValueError(f"{label} prepare frame index differs")
        prepare_frame = mapping(event.get("prepareFrame"), f"{label} prepare frame")
        if prepare_frame != backtrace[prepare_index]:
            raise ValueError(f"{label} prepare ancestry differs")
        prepare_pc = integer(prepare_frame.get("pc"), f"{label} prepare PC")
        merge_base.frame_record(
            prepare_frame,
            f"{label} exact prepare frame",
            expected_pc=prepare_pc,
            expected_symbol_start=prepare_start,
            expected_module=prepare_module,
        )
        for earlier in backtrace[:prepare_index]:
            if (
                earlier.get("function") == merge_base.PREPARE_LAYER_FUNCTION
                and earlier.get("symbolStart") == prepare_start
                and earlier.get("module") == prepare_module
            ):
                raise ValueError(f"{label} prepare frame is not nearest")
        registers = _registers(
            event.get("prepareFrameRegisters"),
            PREPARE_FRAME_REGISTER_NAMES,
            f"{label} prepare registers",
        )
        identity = mapping(event.get("frameIdentity"), f"{label} identity")
        role_base = integer(identity.get("roleBase"), f"{label} role base")
        frame_pointer = integer(
            identity.get("framePointer"), f"{label} frame pointer"
        )
        identity_key = (thread_id, role_base, frame_pointer)
        if (
            set(identity) != {"threadID", "roleBase", "framePointer"}
            or identity.get("threadID") != thread_id
            or role_base <= 0
            or frame_pointer <= 0
            or registers["x19"] != role_base
            or registers["x29"] != frame_pointer
            or registers["pc"] != prepare_pc
        ):
            raise ValueError(f"{label} frame correlation differs")
        if site["function"] == merge_base.PREPARE_LAYER_FUNCTION:
            if prepare_index != 0 or prepare_frame != frame:
                raise ValueError(f"{label} direct ancestry differs")
        elif prepare_index == 0:
            raise ValueError(f"{label} helper ancestry differs")
        previous_index = (
            None if site["epochStart"] else last_by_frame.get(identity_key)
        )
        previous_aggregate = None
        if previous_index is not None:
            previous_aggregate = bytes.fromhex(
                events[previous_index]["aggregateAfterHex"]
            )
        role = _memory_payload(
            event.get("roleStateAfter"),
            f"{label} role",
            expected_address=role_base,
            expected_byte_count=full_base.ROLE_STATE_BYTE_COUNT,
        )
        aggregate = role[
            full_base.AGGREGATE_OFFSET : full_base.AGGREGATE_OFFSET
            + full_base.AGGREGATE_BYTE_COUNT
        ]
        changed = (
            None if previous_aggregate is None else aggregate != previous_aggregate
        )
        if (
            event.get("previousSameFrameCandidateEventIndex") != previous_index
            or event.get("aggregateChangedFromPreviousSameFrameCandidate")
            is not changed
            or _payload(
                event.get("aggregateAfterHex"),
                full_base.AGGREGATE_BYTE_COUNT,
                f"{label} aggregate",
            )
            != aggregate
        ):
            raise ValueError(f"{label} aggregate chain differs")
        window_index = integer(event.get("codeWindowIndex"), f"{label} window")
        if not 0 <= window_index < len(windows):
            raise ValueError(f"{label} code window differs")
        window_start, window_payload, stop_offset = windows[window_index]
        if (
            stop_pc != window_start + stop_offset
            or window_payload[stop_offset - 4 : stop_offset].hex()
            != site_record["precedingInstructionRawLittleEndianHex"]
        ):
            raise ValueError(f"{label} code containment differs")
        referenced_windows.add(window_index)
        general = _top_operands(
            event.get("topOperandSnapshot"),
            label + " operands",
            expected_pc=stop_pc,
        )
        if site["function"] == merge_base.PREPARE_LAYER_FUNCTION and (
            general["x19"] != role_base or general["x29"] != frame_pointer
        ):
            raise ValueError(f"{label} direct operand aliases differ")
        retained[name] += 1
        if retained[name] > MAXIMUM_RECORD_COUNT_PER_WRITER_SITE:
            raise ValueError(f"{label} retained bound differs")
        last_by_frame[identity_key] = index
        previous_callback = callback
        events.append(event)
    if referenced_windows != set(range(len(windows))):
        raise ValueError("unreferenced writer code window")
    return events, retained


def _writer_accounting(
    trace: Mapping[str, Any],
    retained: Mapping[str, int],
    *,
    prepare_start: int,
    prepare_module: Mapping[str, Any],
) -> None:
    hit_counts = mapping(trace.get("writerSiteHitCounts"), "writer hit counts")
    rejected_counts = mapping(
        trace.get("rejectedWriterSiteHitCounts"), "rejected writer counts"
    )
    discarded_counts = mapping(
        trace.get("discardedWriterSiteHitCounts"), "discarded writer counts"
    )
    expected_names = set(WRITER_SITE_BY_NAME)
    if not all(
        set(values) == expected_names
        for values in (hit_counts, rejected_counts, discarded_counts)
    ):
        raise ValueError("writer accounting inventory differs")
    for name in WRITER_SITE_BY_NAME:
        hits = integer(hit_counts[name], f"{name} hit count")
        rejected = integer(rejected_counts[name], f"{name} rejected count")
        discarded = integer(discarded_counts[name], f"{name} discarded count")
        if (
            discarded != 0
            or hits != retained[name] + rejected + discarded
            or hits > MAXIMUM_WRITER_SITE_HIT_COUNT
        ):
            raise ValueError(f"{name} writer accounting differs")
    diagnostics = list(
        sequence(trace.get("rejectedWriterDiagnostics"), "rejected diagnostics")
    )
    unretained = integer(
        trace.get("unretainedRejectedWriterHitCount"),
        "unretained rejected writer count",
    )
    if (
        unretained != 0
        or len(diagnostics) > MAXIMUM_REJECTED_WRITER_DIAGNOSTIC_COUNT
    ):
        raise ValueError("rejected writer diagnostic bounds differ")
    sums = {name: 0 for name in WRITER_SITE_BY_NAME}
    identities = set()
    for index, value in enumerate(diagnostics):
        label = f"rejected writer diagnostic {index}"
        item = mapping(value, label)
        name = item.get("siteName")
        if name not in WRITER_SITE_BY_NAME:
            raise ValueError(f"{label} site differs")
        site = WRITER_SITE_BY_NAME[name]
        stop_pc = integer(item.get("stopPC"), f"{label} PC")
        function = item.get("function")
        reason = item.get("reason")
        hits = integer(item.get("hitCount"), f"{label} hit count")
        identity = (name, stop_pc, function, reason)
        if (
            stop_pc != prepare_start + site["relativeToPrepareLayer"]
            or not isinstance(function, str)
            or not function
            or reason not in {"top function differs", "exact prepare frame absent"}
            or hits <= 0
            or identity in identities
            or _module(item.get("module"), f"{label} module") != prepare_module
            or reason == "top function differs"
            and function == site["function"]
            or reason == "exact prepare frame absent"
            and function != site["function"]
        ):
            raise ValueError(f"{label} identity differs")
        identities.add(identity)
        sums[name] += hits
    if any(sums[name] != rejected_counts[name] for name in sums):
        raise ValueError("rejected writer diagnostic accounting differs")


def _selection(
    trace: Mapping[str, Any],
    order: Mapping[int, str],
    events: Sequence[Mapping[str, Any]],
    *,
    prepare_start: int,
    prepare_module: Mapping[str, Any],
    object_addresses: Mapping[str, Any],
    selected_source: int,
    source_sequence: int,
) -> tuple[list[int], int, int]:
    diagnostics = list(
        sequence(
            trace.get("preselectionMarkerDiagnostics"),
            "preselection marker diagnostics",
        )
    )
    if len(diagnostics) > MAXIMUM_PRESELECTION_MARKER_DIAGNOSTIC_COUNT:
        raise ValueError("preselection marker diagnostic bound differs")
    previous_hit = 0
    for index, value in enumerate(diagnostics):
        label = f"preselection marker diagnostic {index}"
        item = mapping(value, label)
        hit = integer(item.get("markerHitIndex"), f"{label} hit")
        if (
            hit <= previous_hit
            or integer(item.get("threadID"), f"{label} thread") <= 0
            or integer(item.get("roleBase"), f"{label} role") <= 0
            or integer(item.get("sourceRegister"), f"{label} source") <= 0
            or integer(item.get("framePointer"), f"{label} frame") <= 0
        ):
            raise ValueError(f"{label} identity differs")
        previous_hit = hit
    selected = mapping(trace.get("selectedFrame"), "selected frame")
    callback = _require_callback(
        order,
        selected.get("callbackSequence"),
        "live-selected-frame-correlated",
        "selected frame callback",
    )
    marker_hit = integer(selected.get("markerHitIndex"), "selected marker hit")
    thread_id = integer(selected.get("threadID"), "selected thread")
    marker_pc = prepare_start + LIVE_SELECTION_MARKER_OFFSET
    if (
        callback <= source_sequence
        or callback != len(order)
        or marker_hit <= previous_hit
        or thread_id <= 0
        or selected.get("pc") != marker_pc
        or selected.get("selectedSource") != selected_source
    ):
        raise ValueError("selected marker identity differs")
    merge_base.frame_record(
        selected.get("frame"),
        "selected frame",
        expected_pc=marker_pc,
        expected_symbol_start=prepare_start,
        expected_module=prepare_module,
    )
    backtrace = _backtrace(selected.get("backtrace"), "selected backtrace")
    if mapping(selected.get("frame"), "selected frame") != backtrace[0]:
        raise ValueError("selected backtrace head differs")
    registers = _registers(
        selected.get("registers"),
        PREPARE_FRAME_REGISTER_NAMES,
        "selected registers",
    )
    identity = mapping(selected.get("frameIdentity"), "selected identity")
    role_base = integer(identity.get("roleBase"), "selected role base")
    frame_pointer = integer(identity.get("framePointer"), "selected frame pointer")
    if (
        set(identity) != {"threadID", "roleBase", "framePointer"}
        or identity.get("threadID") != thread_id
        or role_base <= 0
        or frame_pointer <= 0
        or registers["x19"] != role_base
        or registers["x28"] != selected_source
        or registers["x29"] != frame_pointer
        or registers["pc"] != marker_pc
    ):
        raise ValueError("selected frame correlation differs")
    role = _memory_payload(
        selected.get("roleStateAtMarker"),
        "selected marker role",
        expected_address=role_base,
        expected_byte_count=full_base.ROLE_STATE_BYTE_COUNT,
    )
    marker_aggregate = role[
        full_base.AGGREGATE_OFFSET : full_base.AGGREGATE_OFFSET
        + full_base.AGGREGATE_BYTE_COUNT
    ]
    if (
        _payload(
            selected.get("aggregateAtMarkerHex"),
            full_base.AGGREGATE_BYTE_COUNT,
            "selected marker aggregate",
        )
        != marker_aggregate
    ):
        raise ValueError("selected marker aggregate alias differs")
    writer_base.private_fields(
        selected.get("privateFieldsAtMarker"), "selected marker private fields"
    )
    objects = mapping(selected.get("selectedObjectsAtMarker"), "selected objects")
    specs = dict(full_base.OBJECT_SNAPSHOT_SPECS)
    if set(objects) != set(specs):
        raise ValueError("selected object inventory differs")
    for name, byte_count in specs.items():
        _memory_payload(
            objects[name],
            f"selected object {name}",
            expected_address=integer(object_addresses.get(name), f"{name} address"),
            expected_byte_count=byte_count,
        )
    selected_indices = [
        integer(value, "selected event index")
        for value in sequence(
            trace.get("selectedWriterEventIndices"), "selected event indices"
        )
    ]
    if (
        not selected_indices
        or selected_indices != sorted(set(selected_indices))
        or selected_indices[-1] >= len(events)
    ):
        raise ValueError("selected event index bounds differ")
    identity_value = dict(identity)
    matching = [
        event
        for event in events
        if event.get("frameIdentity") == identity_value
        and event.get("callbackSequence") < callback
    ]
    epochs = [event for event in matching if event.get("epochStart") is True]
    if not epochs:
        raise ValueError("selected writer epoch is absent")
    epoch = max(epochs, key=lambda event: event["callbackSequence"])
    expected_selected = [
        event["eventIndex"]
        for event in matching
        if event["callbackSequence"] >= epoch["callbackSequence"]
    ]
    expected_selected.sort(key=lambda index: events[index]["callbackSequence"])
    selected_events = [events[index] for index in selected_indices]
    distinct = len({event["aggregateAfterHex"] for event in selected_events})
    changing = sum(
        event.get("aggregateChangedFromPreviousSameFrameCandidate") is True
        for event in selected_events
    )
    if (
        selected_indices != expected_selected
        or selected.get("epochStartEventIndex") != epoch["eventIndex"]
        or selected_indices[0] != epoch["eventIndex"]
        or epoch.get("siteName") != "zeroInitializationAfter"
        or selected.get("selectedWriterEventCount") != len(selected_indices)
        or trace.get("finalSelectedWriterEventCount") != len(selected_indices)
        or selected_events[-1]["aggregateAfterHex"] != marker_aggregate.hex()
        or distinct < MINIMUM_SELECTED_DISTINCT_AGGREGATE_COUNT
        or trace.get("finalSelectedDistinctAggregateCount") != distinct
        or changing < MINIMUM_SELECTED_CHANGING_TRANSITION_COUNT
        or trace.get("finalSelectedChangingTransitionCount") != changing
    ):
        raise ValueError("selected writer suffix differs")
    hits = integer(trace.get("selectionMarkerHitCount"), "marker hit count")
    rejected = integer(
        trace.get("rejectedSelectionMarkerHitCount"), "rejected marker count"
    )
    discarded = integer(
        trace.get("discardedSelectionMarkerHitCount"), "discarded marker count"
    )
    if (
        discarded != 0
        or hits != len(diagnostics) + rejected + 1 + discarded
        or hits > MAXIMUM_LIVE_SELECTION_MARKER_HIT_COUNT
        or marker_hit != hits
    ):
        raise ValueError("selection marker accounting differs")
    return selected_indices, distinct, changing


def validate(trace_path: Path) -> dict[str, Any]:
    trace_bytes = trace_path.read_bytes()
    trace = mapping(json.loads(trace_bytes), "frame-correlated writer trace")
    if (
        trace.get("prepareLayerFrameWriterTraceSchemaVersion")
        != EXPECTED_TRACE_SCHEMA_VERSION
        or trace.get("classification") != EXPECTED_CLASSIFICATION
        or trace.get("status") != "finalized"
        or trace.get("statusBeforeFinalization")
        != "live-selected-frame-correlated"
        or mapping(trace.get("configuration"), "trace configuration")
        != EXPECTED_CONFIGURATION
        or list(sequence(trace.get("failures"), "trace failures"))
        or trace.get("finalFailureCount") != 0
    ):
        raise ValueError("trace envelope differs")
    order = _callback_order(trace)
    prepare_start, prepare_module, full_code, site_records, capture_sequence = (
        _static_gates(trace, order)
    )
    chain, selected_source = construction_base._selected_object_chain(trace)
    object_addresses = mapping(chain.get("addresses"), "selected object addresses")
    source_sequence = _require_callback(
        order,
        chain.get("callbackSequence"),
        "source-selected",
        "source callback",
    )
    late_count = integer(trace.get("lateCandidateCount"), "late candidate count")
    if (
        late_count != chain.get("selectedLateCandidateIndex")
        or not 1 <= late_count <= full_base.MAXIMUM_LATE_CANDIDATE_COUNT
        or len(sequence(trace.get("lateCandidateDiagnostics"), "late diagnostics"))
        > full_base.MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT
        or source_sequence <= capture_sequence
    ):
        raise ValueError("source selection accounting differs")
    events, retained = _candidate_events(
        trace,
        order,
        prepare_start=prepare_start,
        prepare_module=prepare_module,
        site_records=site_records,
        source_sequence=source_sequence,
    )
    _writer_accounting(
        trace,
        retained,
        prepare_start=prepare_start,
        prepare_module=prepare_module,
    )
    selected_indices, distinct, changing = _selection(
        trace,
        order,
        events,
        prepare_start=prepare_start,
        prepare_module=prepare_module,
        object_addresses=object_addresses,
        selected_source=selected_source,
        source_sequence=source_sequence,
    )
    selected_sites = sorted({events[index]["siteName"] for index in selected_indices})
    return {
        "prepareLayerFrameWriterTraceValidationSchemaVersion": (
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
            "writerCandidateEventCount": len(events),
            "selectedWriterEventCount": len(selected_indices),
            "selectedDistinctAggregateCount": distinct,
            "selectedChangingTransitionCount": changing,
            "selectedWriterSites": selected_sites,
            "rejectedSelectionMarkerHitCount": trace.get(
                "rejectedSelectionMarkerHitCount"
            ),
        },
        "sealedConclusion": {
            "exactPrepareLayerEntryProved": True,
            "completePrepareLayerCodeCaptured": True,
            "longLivedStackWatchpointUsed": False,
            "sameInvocationFrameCorrelationProved": True,
            "frameCorrelatedWriterSuffixCaptured": True,
            "selectedAggregateChainClosedAtMarker": True,
            "writerInstructionSemanticsOpened": False,
            "completePublicCropRuleRecovered": False,
            "unseenGeometryTransferPassed": False,
            "productionShaderAuthorized": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.trace)
    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(output, end="")
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
