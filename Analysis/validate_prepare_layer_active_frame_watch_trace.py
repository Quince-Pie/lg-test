#!/usr/bin/env python3
"""Validate the sealed four-lane active-frame aggregate writer trace."""

import argparse
import hashlib
import json
import math
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_capture_backdrop_writer_trace as writer_base
import validate_layer_shapes_merge_trace as merge_base
import validate_prepare_layer_frame_correlated_writer_trace as frame_validator


full_base = frame_validator.full_base

EXPECTED_TRACE_SCHEMA_VERSION = 3
VALIDATION_SCHEMA_VERSION = 3
EXPECTED_CLASSIFICATION = (
    "preregistered-live-depth-qualified-four-lane-prepare-layer-aggregate-"
    "watch-trace; complete-causal-writer-list-semantics-public-crop-policy-"
    "unseen-transfer-and-product-parity-remain-sealed"
)
EXPECTED_VALIDATION_CLASSIFICATION = (
    "prospective-integrity-gate-for-complete-live-prepare-layer-aggregate-"
    "writer-PC-chain; instruction-semantics-remain-sealed"
)
PREPARE_LAYER_FULL_CODE_SHA256 = (
    "fe58001369708e0276599f26865be03fdf1dd2348524f92a72c1427be8d1817c"
)
EPOCH_MARKER_NAME = "zeroInitializationAfter"
EPOCH_MARKER_OFFSET = 0xB60
EPOCH_PRECEDING_INSTRUCTION_HEX = "60a6803d"
RETURN_MARKER_NAME = "recursivePrepareReturn"
RETURN_MARKER_OFFSET = 0x2A68
RETURN_MARKER_INSTRUCTION_HEX = "a8ce4039"
SELECTION_MARKER_NAME = "sourceLaterHandle"
SELECTION_MARKER_OFFSET = 0x3EF0
SELECTION_MARKER_INSTRUCTION_HEX = "28330b91"
TARGET_PREPARE_RECURSION_DEPTH = 4
WATCH_LANE_OFFSETS = (0, 8, 16, 24)
WATCH_LANE_BYTE_COUNT = 8
MAXIMUM_EPOCH_MARKER_HIT_COUNT = 4096
MAXIMUM_EPOCH_RECORD_COUNT = 128
MAXIMUM_RETURN_MARKER_HIT_COUNT = 8192
MAXIMUM_SELECTION_MARKER_HIT_COUNT = 4096
MAXIMUM_RAW_WATCHPOINT_HIT_COUNT = 4096
MAXIMUM_QUALIFIED_WATCHPOINT_EVENT_COUNT = 512
MAXIMUM_IGNORED_WATCHPOINT_DIAGNOSTIC_COUNT = 64
MAXIMUM_REJECTED_MARKER_DIAGNOSTIC_COUNT = 64
MINIMUM_SELECTED_CHANGED_TRANSITION_COUNT = 3
KNOWN_CANVAS_EXTENT = 1024.0
KNOWN_GLASS_EXTENT = 640.0
KNOWN_EDGE_PADDING = 8.0
IDENTITY_FRAME_REGISTER_NAMES = ("x19", "x29", "pc")
SELECTION_FRAME_REGISTER_NAMES = ("x19", "x28", "x29", "pc")
RETIRED_INHERITED_WRITER_SITE_NAMES = tuple(
    site["name"]
    for site in frame_validator.WRITER_SITES
    if site["name"] != EPOCH_MARKER_NAME
)
RETAINED_CONTROL_BREAKPOINT_NAMES = (
    EPOCH_MARKER_NAME,
    SELECTION_MARKER_NAME,
    RETURN_MARKER_NAME,
)
FRAME_TRACE_OUTPUT_ENVIRONMENT = "LG_PREPARE_LAYER_FRAME_WRITER_TRACE_OUTPUT"
KNOWN_SAMPLED_WRITER_AFTER_OFFSETS = tuple(
    sorted(site["relativeToPrepareLayer"] for site in frame_validator.WRITER_SITES)
)

EXPECTED_CONFIGURATION = {
    "prepareLayerFunction": merge_base.PREPARE_LAYER_FUNCTION,
    "prepareLayerSymbolByteCount": full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
    "prepareLayerFullCodeSHA256": PREPARE_LAYER_FULL_CODE_SHA256,
    "aggregateOffset": full_base.AGGREGATE_OFFSET,
    "aggregateByteCount": full_base.AGGREGATE_BYTE_COUNT,
    "roleStateByteCount": full_base.ROLE_STATE_BYTE_COUNT,
    "epochMarkerName": EPOCH_MARKER_NAME,
    "epochMarkerOffset": EPOCH_MARKER_OFFSET,
    "epochPrecedingInstructionRawLittleEndianHex": (EPOCH_PRECEDING_INSTRUCTION_HEX),
    "returnMarkerName": RETURN_MARKER_NAME,
    "returnMarkerOffset": RETURN_MARKER_OFFSET,
    "returnMarkerInstructionRawLittleEndianHex": RETURN_MARKER_INSTRUCTION_HEX,
    "selectionMarkerName": SELECTION_MARKER_NAME,
    "selectionMarkerOffset": SELECTION_MARKER_OFFSET,
    "selectionMarkerInstructionRawLittleEndianHex": (SELECTION_MARKER_INSTRUCTION_HEX),
    "targetPrepareRecursionDepth": TARGET_PREPARE_RECURSION_DEPTH,
    "watchLaneOffsets": list(WATCH_LANE_OFFSETS),
    "watchLaneByteCount": WATCH_LANE_BYTE_COUNT,
    "maximumEpochMarkerHitCount": MAXIMUM_EPOCH_MARKER_HIT_COUNT,
    "maximumEpochRecordCount": MAXIMUM_EPOCH_RECORD_COUNT,
    "maximumReturnMarkerHitCount": MAXIMUM_RETURN_MARKER_HIT_COUNT,
    "maximumSelectionMarkerHitCount": MAXIMUM_SELECTION_MARKER_HIT_COUNT,
    "maximumRawWatchpointHitCount": MAXIMUM_RAW_WATCHPOINT_HIT_COUNT,
    "maximumQualifiedWatchpointEventCount": (MAXIMUM_QUALIFIED_WATCHPOINT_EVENT_COUNT),
    "maximumIgnoredWatchpointDiagnosticCount": (
        MAXIMUM_IGNORED_WATCHPOINT_DIAGNOSTIC_COUNT
    ),
    "maximumRejectedMarkerDiagnosticCount": (MAXIMUM_REJECTED_MARKER_DIAGNOSTIC_COUNT),
    "minimumSelectedChangedTransitionCount": (
        MINIMUM_SELECTED_CHANGED_TRANSITION_COUNT
    ),
    "knownCanvasExtent": KNOWN_CANVAS_EXTENT,
    "knownGlassExtent": KNOWN_GLASS_EXTENT,
    "knownEdgePadding": KNOWN_EDGE_PADDING,
    "identityFrameRegisterNames": list(IDENTITY_FRAME_REGISTER_NAMES),
    "selectionFrameRegisterNames": list(SELECTION_FRAME_REGISTER_NAMES),
    "structuralFramePointerSource": "SBFrame.GetFP",
    "retiredInheritedWriterSiteNames": list(RETIRED_INHERITED_WRITER_SITE_NAMES),
    "retainedControlBreakpointNames": list(RETAINED_CONTROL_BREAKPOINT_NAMES),
    "knownSampledWriterAfterOffsets": list(KNOWN_SAMPLED_WRITER_AFTER_OFFSETS),
    "frameTraceOutputEnvironment": FRAME_TRACE_OUTPUT_ENVIRONMENT,
    "frameTraceSchemaVersion": frame_validator.EXPECTED_TRACE_SCHEMA_VERSION,
    "maximumBacktraceFrameCount": full_base.MAXIMUM_BACKTRACE_FRAME_COUNT,
    "pcCenteredCodeWindowByteCount": full_base.PC_CENTERED_CODE_WINDOW_BYTE_COUNT,
    "pcCenteredCodeWindowBacktrack": full_base.PC_CENTERED_CODE_WINDOW_BACKTRACK,
    "stackSnapshotByteCount": full_base.STACK_SNAPSHOT_BYTE_COUNT,
    "registerPointerSnapshotByteCount": (
        full_base.REGISTER_POINTER_SNAPSHOT_BYTE_COUNT
    ),
    "registerPointerSnapshotBacktrack": (full_base.REGISTER_POINTER_SNAPSHOT_BACKTRACK),
    "generalRegisterNames": list(full_base.GENERAL_REGISTER_NAMES),
    "simdRegisterNames": list(full_base.SIMD_REGISTER_NAMES),
    "armRule": (
        "after source selection, arm four aligned 8-byte write watches at "
        "+0xb60 only when the bounded live backtrace contains exactly four "
        "exact prepare_layer frames independent of register availability; "
        "identify the current frame by thread ID, top-frame x19 role base, and "
        "x29 frame pointer, cross-checking x29 against SBFrame.GetFP"
    ),
    "retirementRule": (
        "at recursive return +0x2a68, delete all four watches as soon as the "
        "watched thread/frame-pointer pair is absent from the exact live "
        "prepare_layer ancestry"
    ),
    "selectionRule": (
        "at the first +0x3ef0 frame whose x28 equals the independently selected "
        "source, require the active identity and latest epoch to match and close "
        "the contiguous full-aggregate chain at the marker"
    ),
    "callbackMultiplexingRule": (
        "reuse the inherited prepare entry, +0xb60 epoch, and +0x3ef0 "
        "selection breakpoints; at each shared address run the inherited callback "
        "first and the active-watch callback second"
    ),
    "inheritedCallbackForwardingRule": (
        "bind every inherited entry and dynamically created breakpoint through "
        "a callback exported by this command-script module"
    ),
    "breakpointIsolationRule": (
        "immediately after independent source selection, disable every inherited "
        "sampled writer breakpoint except the shared +0xb60 zero epoch before any "
        "hardware watch is armed; retain only the shared zero epoch, selection "
        "marker, and return marker while hardware watches are live"
    ),
    "knownStateTransferRule": (
        "the selected full-aggregate state sequence must contain, bit-for-bit "
        "and in order, zero; [P,1024-P-640,640,640]; "
        "[P,1024-P-640-8,640,648]; and "
        "[floor(P)-1,1024-P-640-8,P+640-(floor(P)-1),"
        "P+648-(floor(P)-1)], with P recovered from the final second lane"
    ),
}


mapping = frame_validator.mapping
sequence = frame_validator.sequence
integer = frame_validator.integer


def _payload(value: Any, byte_count: int, label: str) -> bytes:
    return frame_validator._payload(value, byte_count, label)


def _callback_order(trace: Mapping[str, Any]) -> dict[int, str]:
    return frame_validator._callback_order(trace)


def _require_callback(
    order: Mapping[int, str], value: Any, kind: str, label: str
) -> int:
    return frame_validator._require_callback(order, value, kind, label)


def _identity(value: Any, label: str) -> dict[str, int]:
    item = mapping(value, label)
    if set(item) != {"threadID", "roleBase", "framePointer"}:
        raise ValueError(f"{label} fields differ")
    result = {
        name: integer(item.get(name), f"{label} {name}")
        for name in ("threadID", "roleBase", "framePointer")
    }
    if any(value <= 0 for value in result.values()):
        raise ValueError(f"{label} values differ")
    return result


def _role_aggregate(value: Any, label: str, role_base: int) -> bytes:
    role = frame_validator._memory_payload(
        value,
        label,
        expected_address=role_base,
        expected_byte_count=full_base.ROLE_STATE_BYTE_COUNT,
    )
    return role[
        full_base.AGGREGATE_OFFSET : full_base.AGGREGATE_OFFSET
        + full_base.AGGREGATE_BYTE_COUNT
    ]


def _identity_registers(
    value: Any, label: str, identity: Mapping[str, int]
) -> dict[str, int]:
    registers = frame_validator._registers(value, IDENTITY_FRAME_REGISTER_NAMES, label)
    if (
        registers["x19"] != identity["roleBase"]
        or registers["x29"] != identity["framePointer"]
    ):
        raise ValueError(f"{label} identity differs")
    return registers


def _selection_registers(
    value: Any, label: str, identity: Mapping[str, int]
) -> dict[str, int]:
    registers = frame_validator._registers(value, SELECTION_FRAME_REGISTER_NAMES, label)
    if (
        registers["x19"] != identity["roleBase"]
        or registers["x29"] != identity["framePointer"]
    ):
        raise ValueError(f"{label} identity differs")
    return registers


def _inherited_frame_context(trace: Mapping[str, Any]) -> dict[str, Any]:
    """Validate inherited static/source/marker evidence without its masked suffix."""
    if (
        trace.get("prepareLayerFrameWriterTraceSchemaVersion")
        != frame_validator.EXPECTED_TRACE_SCHEMA_VERSION
        or trace.get("classification") != frame_validator.EXPECTED_CLASSIFICATION
        or trace.get("status") != "finalized"
        or trace.get("statusBeforeFinalization") != "live-selected-frame-correlated"
        or mapping(trace.get("configuration"), "inherited configuration")
        != frame_validator.EXPECTED_CONFIGURATION
        or list(sequence(trace.get("failures"), "inherited failures"))
        or trace.get("finalFailureCount") != 0
    ):
        raise ValueError("inherited frame context envelope differs")
    order = frame_validator._callback_order(trace)
    prepare_start, prepare_module, _code, site_records, capture_sequence = (
        frame_validator._static_gates(trace, order)
    )
    chain, selected_source = frame_validator.construction_base._selected_object_chain(
        trace
    )
    object_addresses = mapping(chain.get("addresses"), "inherited object addresses")
    source_sequence = frame_validator._require_callback(
        order,
        chain.get("callbackSequence"),
        "source-selected",
        "inherited source callback",
    )
    late_count = integer(trace.get("lateCandidateCount"), "inherited late count")
    if (
        late_count != chain.get("selectedLateCandidateIndex")
        or not 1 <= late_count <= full_base.MAXIMUM_LATE_CANDIDATE_COUNT
        or len(
            sequence(
                trace.get("lateCandidateDiagnostics"),
                "inherited late diagnostics",
            )
        )
        > full_base.MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT
        or source_sequence <= capture_sequence
    ):
        raise ValueError("inherited source selection accounting differs")
    events, retained = frame_validator._candidate_events(
        trace,
        order,
        prepare_start=prepare_start,
        prepare_module=prepare_module,
        site_records=site_records,
        source_sequence=source_sequence,
    )
    frame_validator._writer_accounting(
        trace,
        retained,
        prepare_start=prepare_start,
        prepare_module=prepare_module,
    )
    diagnostics = list(
        sequence(
            trace.get("preselectionMarkerDiagnostics"),
            "inherited preselection diagnostics",
        )
    )
    if len(diagnostics) > frame_validator.MAXIMUM_PRESELECTION_MARKER_DIAGNOSTIC_COUNT:
        raise ValueError("inherited preselection diagnostic bound differs")
    previous_hit = 0
    for index, value in enumerate(diagnostics):
        label = f"inherited preselection diagnostic {index}"
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
    selected = mapping(trace.get("selectedFrame"), "inherited selected frame")
    callback = frame_validator._require_callback(
        order,
        selected.get("callbackSequence"),
        "live-selected-frame-correlated",
        "inherited selected callback",
    )
    marker_hit = integer(selected.get("markerHitIndex"), "inherited marker hit")
    thread_id = integer(selected.get("threadID"), "inherited selected thread")
    marker_pc = prepare_start + frame_validator.LIVE_SELECTION_MARKER_OFFSET
    if (
        callback <= source_sequence
        or callback != len(order)
        or marker_hit <= previous_hit
        or thread_id <= 0
        or selected.get("pc") != marker_pc
        or selected.get("selectedSource") != selected_source
    ):
        raise ValueError("inherited selected marker identity differs")
    selected_frame = merge_base.frame_record(
        selected.get("frame"),
        "inherited selected frame",
        expected_pc=marker_pc,
        expected_symbol_start=prepare_start,
        expected_module=prepare_module,
    )
    backtrace = frame_validator._backtrace(
        selected.get("backtrace"), "inherited selected backtrace"
    )
    if selected_frame != backtrace[0]:
        raise ValueError("inherited selected backtrace head differs")
    registers = frame_validator._registers(
        selected.get("registers"),
        frame_validator.PREPARE_FRAME_REGISTER_NAMES,
        "inherited selected registers",
    )
    identity = _identity(selected.get("frameIdentity"), "inherited identity")
    if (
        identity["threadID"] != thread_id
        or registers["x19"] != identity["roleBase"]
        or registers["x28"] != selected_source
        or registers["x29"] != identity["framePointer"]
        or registers["pc"] != marker_pc
    ):
        raise ValueError("inherited selected frame correlation differs")
    role = frame_validator._memory_payload(
        selected.get("roleStateAtMarker"),
        "inherited selected marker role",
        expected_address=identity["roleBase"],
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
            "inherited selected marker aggregate",
        )
        != marker_aggregate
    ):
        raise ValueError("inherited marker aggregate alias differs")
    writer_base.private_fields(
        selected.get("privateFieldsAtMarker"),
        "inherited selected marker private fields",
    )
    objects = mapping(
        selected.get("selectedObjectsAtMarker"), "inherited selected objects"
    )
    specs = dict(full_base.OBJECT_SNAPSHOT_SPECS)
    if set(objects) != set(specs):
        raise ValueError("inherited selected object inventory differs")
    for name, byte_count in specs.items():
        frame_validator._memory_payload(
            objects[name],
            f"inherited selected object {name}",
            expected_address=integer(object_addresses.get(name), f"{name} address"),
            expected_byte_count=byte_count,
        )
    selected_indices = [
        integer(value, "inherited selected event index")
        for value in sequence(
            trace.get("selectedWriterEventIndices"),
            "inherited selected event indices",
        )
    ]
    if (
        not selected_indices
        or selected_indices != sorted(set(selected_indices))
        or selected_indices[-1] >= len(events)
    ):
        raise ValueError("inherited selected event bounds differ")
    matching = [
        event
        for event in events
        if event.get("frameIdentity") == dict(identity)
        and event.get("callbackSequence") < callback
    ]
    epochs = [event for event in matching if event.get("epochStart") is True]
    if not epochs:
        raise ValueError("inherited selected epoch is absent")
    epoch = max(epochs, key=lambda event: event["callbackSequence"])
    expected_selected = sorted(
        (
            event["eventIndex"]
            for event in matching
            if event["callbackSequence"] >= epoch["callbackSequence"]
        ),
        key=lambda index: events[index]["callbackSequence"],
    )
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
        or epoch.get("siteName") != EPOCH_MARKER_NAME
        or selected.get("selectedWriterEventCount") != len(selected_indices)
        or trace.get("finalSelectedWriterEventCount") != len(selected_indices)
        or trace.get("finalSelectedDistinctAggregateCount") != distinct
        or trace.get("finalSelectedChangingTransitionCount") != changing
    ):
        raise ValueError("inherited selected context differs")
    hits = integer(trace.get("selectionMarkerHitCount"), "inherited marker hits")
    rejected = integer(
        trace.get("rejectedSelectionMarkerHitCount"),
        "inherited rejected marker count",
    )
    discarded = integer(
        trace.get("discardedSelectionMarkerHitCount"),
        "inherited discarded marker count",
    )
    if (
        discarded != 0
        or hits != len(diagnostics) + rejected + 1
        or hits > frame_validator.MAXIMUM_LIVE_SELECTION_MARKER_HIT_COUNT
        or marker_hit != hits
    ):
        raise ValueError("inherited marker accounting differs")
    return {
        "prepareStart": prepare_start,
        "prepareModule": prepare_module,
        "selectedSource": selected_source,
        "objectChain": chain,
        "selectedFrame": selected,
        "markerAggregate": marker_aggregate,
        "selectedSampleEventCount": len(selected_indices),
        "selectedSampleDistinctAggregateCount": distinct,
        "selectedSampleChangingTransitionCount": changing,
        "sampledSuffixClosedAtMarker": (
            selected_events[-1]["aggregateAfterHex"] == marker_aggregate.hex()
        ),
    }


def _structural_prepare_frames(
    backtrace: Sequence[Mapping[str, Any]],
    *,
    prepare_start: int,
    prepare_module: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    return [
        frame
        for frame in backtrace
        if frame.get("function") == merge_base.PREPARE_LAYER_FUNCTION
        and frame.get("symbolStart") == prepare_start
        and frame.get("symbolEnd")
        == prepare_start + full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        and frame.get("module") == prepare_module
    ]


def _static_gate(
    trace: Mapping[str, Any],
    base_trace: Mapping[str, Any],
    order: Mapping[int, str],
) -> tuple[int, Mapping[str, Any]]:
    prepare = mapping(trace.get("prepareLayer"), "active watch prepare layer")
    base_prepare = mapping(base_trace.get("prepareLayer"), "base prepare layer")
    callback = _require_callback(
        order,
        prepare.get("callbackSequence"),
        "prepare-layer-entry",
        "active watch prepare callback",
    )
    start = integer(prepare.get("symbolStart"), "active watch prepare start")
    end = integer(prepare.get("symbolEnd"), "active watch prepare end")
    prepare_module = mapping(prepare.get("module"), "active watch prepare module")
    if (
        callback != 1
        or prepare.get("callbackPC") != start
        or prepare.get("callbackLocationAddress") != start
        or prepare.get("function") != merge_base.PREPARE_LAYER_FUNCTION
        or end - start != full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        or prepare.get("symbolByteCount") != full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        or prepare.get("fullCodeSHA256") != PREPARE_LAYER_FULL_CODE_SHA256
        or start != base_prepare.get("symbolStart")
        or end != base_prepare.get("symbolEnd")
        or prepare_module != base_prepare.get("module")
    ):
        raise ValueError("active watch prepare gate differs")
    markers = (
        ("epochMarker", EPOCH_MARKER_OFFSET),
        ("returnMarker", RETURN_MARKER_OFFSET),
        ("selectionMarker", SELECTION_MARKER_OFFSET),
    )
    breakpoint_ids = set()
    for name, offset in markers:
        marker = mapping(prepare.get(name), f"active watch {name}")
        breakpoint_id = integer(marker.get("breakpointID"), f"{name} breakpoint")
        if marker.get("address") != start + offset or breakpoint_id <= 0:
            raise ValueError(f"active watch {name} differs")
        breakpoint_ids.add(breakpoint_id)
    entry_id = integer(
        trace.get("prepareLayerEntryBreakpointID"), "active watch entry breakpoint"
    )
    base_sites = {
        mapping(value, "base writer site").get("name"): mapping(
            value, "base writer site"
        )
        for value in sequence(base_prepare.get("writerSites"), "base writer sites")
    }
    base_epoch = mapping(
        base_sites.get(EPOCH_MARKER_NAME), "base zero epoch writer site"
    )
    base_selection = mapping(
        base_prepare.get("liveSelectionMarker"), "base selection marker"
    )
    if (
        len(breakpoint_ids) != 3
        or entry_id in breakpoint_ids
        or entry_id <= 0
        or entry_id != base_prepare.get("entryBreakpointID")
        or mapping(prepare.get("epochMarker"), "shared epoch marker").get(
            "breakpointID"
        )
        != base_epoch.get("breakpointID")
        or mapping(prepare.get("selectionMarker"), "shared selection marker").get(
            "breakpointID"
        )
        != base_selection.get("breakpointID")
    ):
        raise ValueError("active watch breakpoint identities differ")
    return start, prepare_module


def _breakpoint_isolation_gate(
    trace: Mapping[str, Any],
    base_trace: Mapping[str, Any],
    order: Mapping[int, str],
    *,
    selected_source: int,
) -> int:
    retirement = mapping(
        trace.get("inheritedWriterBreakpointRetirement"),
        "inherited writer breakpoint retirement",
    )
    if set(retirement) != {
        "callbackSequence",
        "threadID",
        "pc",
        "selectedSource",
        "retired",
        "retainedControlBreakpoints",
    }:
        raise ValueError("inherited writer breakpoint retirement fields differ")
    callback = _require_callback(
        order,
        retirement.get("callbackSequence"),
        "inherited-writer-breakpoints-retired",
        "inherited writer retirement callback",
    )
    if callback != 2:
        raise ValueError("inherited writer retirement timing differs")
    base_prepare = mapping(base_trace.get("prepareLayer"), "base prepare layer")
    sites = {
        mapping(value, "base writer site").get("name"): mapping(
            value, "base writer site"
        )
        for value in sequence(base_prepare.get("writerSites"), "base writer sites")
    }
    retired = list(sequence(retirement.get("retired"), "retired writer breakpoints"))
    if len(retired) != len(RETIRED_INHERITED_WRITER_SITE_NAMES):
        raise ValueError("retired writer breakpoint inventory differs")
    for expected_name, value in zip(
        RETIRED_INHERITED_WRITER_SITE_NAMES, retired, strict=True
    ):
        item = mapping(value, f"retired writer breakpoint {expected_name}")
        base_site = mapping(sites.get(expected_name), f"base site {expected_name}")
        if (
            set(item) != {"name", "breakpointID", "enabledAfterRetirement"}
            or item.get("name") != expected_name
            or item.get("breakpointID") != base_site.get("breakpointID")
            or item.get("enabledAfterRetirement") is not False
        ):
            raise ValueError(f"retired writer breakpoint {expected_name} differs")
    retained = list(
        sequence(
            retirement.get("retainedControlBreakpoints"),
            "retained control breakpoints",
        )
    )
    active_prepare = mapping(trace.get("prepareLayer"), "active prepare layer")
    expected_retained_ids = (
        mapping(sites.get(EPOCH_MARKER_NAME), "base zero epoch").get("breakpointID"),
        mapping(base_prepare.get("liveSelectionMarker"), "base selection marker").get(
            "breakpointID"
        ),
        mapping(active_prepare.get("returnMarker"), "active return marker").get(
            "breakpointID"
        ),
    )
    if len(retained) != len(RETAINED_CONTROL_BREAKPOINT_NAMES):
        raise ValueError("retained control breakpoint inventory differs")
    for expected_name, expected_id, value in zip(
        RETAINED_CONTROL_BREAKPOINT_NAMES,
        expected_retained_ids,
        retained,
        strict=True,
    ):
        item = mapping(value, f"retained control breakpoint {expected_name}")
        if item != {
            "name": expected_name,
            "breakpointID": expected_id,
            "enabledAfterRetirement": True,
        }:
            raise ValueError(f"retained control breakpoint {expected_name} differs")
    isolated_ids = [
        integer(item.get("breakpointID"), "isolated breakpoint ID")
        for item in (
            mapping(value, "isolated breakpoint") for value in [*retired, *retained]
        )
    ]
    if len(isolated_ids) != len(set(isolated_ids)):
        raise ValueError("isolated breakpoint identities differ")
    capture = mapping(base_trace.get("captureBackdrop"), "base capture backdrop")
    expected_retirement_pc = (
        integer(capture.get("symbolAddress"), "base capture symbol")
        + full_base.CAPTURE_BACKDROP_LATE_OFFSET
    )
    if (
        trace.get("inheritedWriterBreakpointsRetired") is not True
        or integer(retirement.get("threadID"), "retirement thread") <= 0
        or retirement.get("pc") != expected_retirement_pc
        or retirement.get("selectedSource") != selected_source
    ):
        raise ValueError("inherited writer breakpoint retirement differs")
    return callback


def _epochs_and_groups(
    trace: Mapping[str, Any],
    order: Mapping[int, str],
    *,
    prepare_start: int,
    prepare_module: Mapping[str, Any],
    selected_source: int,
) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    epochs = [
        mapping(value, f"epoch {index}")
        for index, value in enumerate(sequence(trace.get("epochRecords"), "epochs"))
    ]
    groups = [
        mapping(value, f"watchpoint group {index}")
        for index, value in enumerate(
            sequence(trace.get("watchpointGroups"), "watchpoint groups")
        )
    ]
    if (
        not epochs
        or len(epochs) != len(groups)
        or len(epochs) > MAXIMUM_EPOCH_RECORD_COUNT
        or trace.get("finalEpochRecordCount") != len(epochs)
        or trace.get("discardedEpochRecordCount") != 0
    ):
        raise ValueError("active watch epoch bounds differ")
    previous_callback = 0
    watchpoint_ids = set()
    for index, (epoch, group) in enumerate(zip(epochs, groups, strict=True)):
        label = f"epoch {index}"
        callback = _require_callback(
            order,
            epoch.get("callbackSequence"),
            "depth-four-zero-epoch",
            f"{label} callback",
        )
        identity = _identity(epoch.get("identity"), f"{label} identity")
        if (
            epoch.get("recordIndex") != index
            or callback <= previous_callback
            or epoch.get("pc") != prepare_start + EPOCH_MARKER_OFFSET
            or epoch.get("threadID") != identity["threadID"]
            or epoch.get("prepareRecursionDepth") != TARGET_PREPARE_RECURSION_DEPTH
            or epoch.get("selectedSourceKnown") != selected_source
        ):
            raise ValueError(f"{label} identity differs")
        frame = merge_base.frame_record(
            epoch.get("frame"),
            f"{label} frame",
            expected_pc=prepare_start + EPOCH_MARKER_OFFSET,
            expected_symbol_start=prepare_start,
            expected_module=prepare_module,
        )
        backtrace = frame_validator._backtrace(
            epoch.get("backtrace"), f"{label} backtrace"
        )
        if frame != backtrace[0]:
            raise ValueError(f"{label} backtrace head differs")
        structural_frames = _structural_prepare_frames(
            backtrace,
            prepare_start=prepare_start,
            prepare_module=prepare_module,
        )
        registers = _identity_registers(
            epoch.get("registers"), f"{label} registers", identity
        )
        if registers["pc"] != prepare_start + EPOCH_MARKER_OFFSET:
            raise ValueError(f"{label} registers differ")
        prepare_frames = list(
            sequence(epoch.get("prepareFrames"), f"{label} prepare frames")
        )
        if (
            len(prepare_frames) != TARGET_PREPARE_RECURSION_DEPTH
            or len(structural_frames) != TARGET_PREPARE_RECURSION_DEPTH
        ):
            raise ValueError(f"{label} prepare depth differs")
        frame_pointers = []
        frame_indices = []
        for ordinal, frame_value in enumerate(prepare_frames):
            item = mapping(frame_value, f"{label} prepare frame {ordinal}")
            frame_record = mapping(
                item.get("frame"), f"{label} prepare frame record {ordinal}"
            )
            frame_index = integer(
                item.get("frameIndex"), f"{label} prepare frame index {ordinal}"
            )
            frame_pointer = integer(
                item.get("unwindFramePointer"),
                f"{label} prepare frame pointer {ordinal}",
            )
            if (
                frame_pointer <= 0
                or frame_record.get("function") != merge_base.PREPARE_LAYER_FUNCTION
                or frame_record.get("symbolStart") != prepare_start
                or frame_record.get("symbolEnd")
                != prepare_start + full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
                or frame_record.get("module") != prepare_module
                or frame_record.get("frameIndex") != frame_index
                or frame_record != structural_frames[ordinal]
                or (ordinal == 0 and frame_pointer != identity["framePointer"])
            ):
                raise ValueError(f"{label} prepare frame {ordinal} differs")
            frame_pointers.append(frame_pointer)
            frame_indices.append(frame_index)
        if (
            frame_indices != sorted(frame_indices)
            or frame_indices[0] != 0
            or len(set(frame_indices)) != TARGET_PREPARE_RECURSION_DEPTH
            or len(set(frame_pointers)) != TARGET_PREPARE_RECURSION_DEPTH
        ):
            raise ValueError(f"{label} prepare frame pointers differ")
        aggregate = _role_aggregate(
            epoch.get("roleStateAtEpoch"), f"{label} role", identity["roleBase"]
        )
        if (
            _payload(
                epoch.get("aggregateAtEpochHex"),
                full_base.AGGREGATE_BYTE_COUNT,
                f"{label} aggregate",
            )
            != aggregate
        ):
            raise ValueError(f"{label} aggregate alias differs")
        group_callback = _require_callback(
            order,
            group.get("callbackSequence"),
            "active-watch-group-armed",
            f"watchpoint group {index} callback",
        )
        group_identity = _identity(
            group.get("identity"), f"watchpoint group {index} identity"
        )
        watches = list(
            sequence(group.get("watchpoints"), f"watchpoint group {index} watches")
        )
        lanes = []
        for watch_value in watches:
            watch = mapping(watch_value, f"watchpoint group {index} watch")
            watchpoint_id = integer(watch.get("id"), "watchpoint ID")
            lane = integer(watch.get("laneOffset"), "watchpoint lane")
            integer(watch.get("deprecatedHardwareIndex"), "watchpoint hardware index")
            if (
                watchpoint_id in watchpoint_ids
                or watch.get("address")
                != identity["roleBase"] + full_base.AGGREGATE_OFFSET + lane
                or watch.get("byteCount") != WATCH_LANE_BYTE_COUNT
            ):
                raise ValueError(f"watchpoint group {index} watch differs")
            watchpoint_ids.add(watchpoint_id)
            lanes.append(lane)
        if (
            group.get("groupIndex") != index
            or group.get("epochRecordIndex") != index
            or group_callback <= callback
            or group_identity != identity
            or group.get("initialAggregateHex") != aggregate.hex()
            or sorted(lanes) != list(WATCH_LANE_OFFSETS)
            or integer(
                group.get("retiredCallbackSequence"),
                f"watchpoint group {index} retirement",
            )
            <= group_callback
            or group.get("retirementReason")
            not in {
                "superseded-by-next-depth-four-epoch",
                "watched-prepare-frame-returned",
                "selected-marker-closed",
                "target-finalization",
            }
        ):
            raise ValueError(f"watchpoint group {index} differs")
        previous_callback = callback
    retirements = list(sequence(trace.get("retirementRecords"), "retirement records"))
    if len(retirements) != len(groups):
        raise ValueError("watchpoint retirement count differs")
    seen_groups = set()
    for index, value in enumerate(retirements):
        item = mapping(value, f"retirement {index}")
        group_index = integer(item.get("groupIndex"), f"retirement {index} group")
        callback = _require_callback(
            order,
            item.get("callbackSequence"),
            "active-watch-group-retired",
            f"retirement {index} callback",
        )
        if (
            item.get("recordIndex") != index
            or group_index >= len(groups)
            or group_index in seen_groups
            or item.get("epochRecordIndex") != group_index
            or _identity(item.get("identity"), f"retirement {index} identity")
            != _identity(groups[group_index].get("identity"), "retired group identity")
            or item.get("reason") != groups[group_index].get("retirementReason")
            or callback != groups[group_index].get("retiredCallbackSequence")
            or _payload(
                item.get("lastAggregateHex"),
                full_base.AGGREGATE_BYTE_COUNT,
                f"retirement {index} aggregate",
            ).hex()
            != groups[group_index].get("lastAggregateHex")
        ):
            raise ValueError(f"retirement {index} differs")
        seen_groups.add(group_index)
    return epochs, groups


def _rejected_marker_diagnostics(
    trace: Mapping[str, Any],
    *,
    prepare_start: int,
    prepare_module: Mapping[str, Any],
) -> None:
    diagnostics = list(
        sequence(
            trace.get("rejectedMarkerDiagnostics"),
            "rejected marker diagnostics",
        )
    )
    source_unknown = integer(
        trace.get("sourceUnknownEpochCount"), "source-unknown epoch count"
    )
    rejected_epoch = integer(
        trace.get("rejectedEpochDepthCount"), "rejected epoch depth count"
    )
    rejected_selection = integer(
        trace.get("rejectedSelectionMarkerHitCount"),
        "rejected selection marker count",
    )
    unretained = integer(
        trace.get("unretainedRejectedMarkerDiagnosticCount"),
        "unretained rejected marker diagnostic count",
    )
    if (
        len(diagnostics) > MAXIMUM_REJECTED_MARKER_DIAGNOSTIC_COUNT
        or unretained != 0
        or trace.get("finalRejectedMarkerDiagnosticCount") != len(diagnostics)
        or len(diagnostics) != source_unknown + rejected_epoch + rejected_selection
    ):
        raise ValueError("rejected marker diagnostic accounting differs")
    expected = {
        ("epoch", "source-unknown"),
        ("epoch", "structural-depth-differs"),
        ("selection", "source-register-differs"),
        ("selection", "structural-depth-differs"),
    }
    for index, value in enumerate(diagnostics):
        label = f"rejected marker diagnostic {index}"
        item = mapping(value, label)
        marker = item.get("marker")
        reason = item.get("reason")
        frames = list(sequence(item.get("prepareFrames"), f"{label} frames"))
        backtrace = frame_validator._backtrace(
            item.get("backtrace"), f"{label} backtrace"
        )
        structural_frames = _structural_prepare_frames(
            backtrace,
            prepare_start=prepare_start,
            prepare_module=prepare_module,
        )
        depth = integer(item.get("structuralPrepareRecursionDepth"), f"{label} depth")
        marker_hit = integer(item.get("markerHitIndex"), f"{label} marker hit")
        thread_id = integer(item.get("threadID"), f"{label} thread")
        selected_source = item.get("selectedSource")
        observed_x28 = item.get("observedX28")
        marker_hit_bound = integer(
            trace.get(
                "epochMarkerHitCount"
                if marker == "epoch"
                else "selectionMarkerHitCount"
            ),
            f"{label} marker hit bound",
        )
        expected_pc = prepare_start + (
            EPOCH_MARKER_OFFSET if marker == "epoch" else SELECTION_MARKER_OFFSET
        )
        if (
            item.get("diagnosticIndex") != index
            or (marker, reason) not in expected
            or depth != len(frames)
            or depth != len(structural_frames)
            or marker_hit <= 0
            or marker_hit > marker_hit_bound
            or thread_id <= 0
            or item.get("pc") != expected_pc
        ):
            raise ValueError(f"{label} envelope differs")
        reason_fields_differ = False
        if reason == "source-unknown":
            reason_fields_differ = (
                selected_source is not None or observed_x28 is not None
            )
        elif marker == "epoch":
            reason_fields_differ = (
                not isinstance(selected_source, int)
                or selected_source <= 0
                or observed_x28 is not None
            )
        elif reason == "source-register-differs":
            reason_fields_differ = (
                not isinstance(observed_x28, int)
                or observed_x28 <= 0
                or selected_source == observed_x28
            )
        else:
            reason_fields_differ = (
                not isinstance(selected_source, int)
                or selected_source <= 0
                or observed_x28 != selected_source
            )
        if reason_fields_differ:
            raise ValueError(f"{label} reason differs")
        for ordinal, frame_value in enumerate(frames):
            frame_item = mapping(frame_value, f"{label} frame {ordinal}")
            frame_record = mapping(
                frame_item.get("frame"), f"{label} frame record {ordinal}"
            )
            frame_index = integer(
                frame_item.get("frameIndex"), f"{label} frame index {ordinal}"
            )
            frame_pointer = frame_item.get("unwindFramePointer")
            if frame_pointer is not None:
                frame_pointer = integer(
                    frame_pointer, f"{label} frame pointer {ordinal}"
                )
            if (
                frame_record.get("function") != merge_base.PREPARE_LAYER_FUNCTION
                or frame_record.get("symbolStart") != prepare_start
                or frame_record.get("symbolEnd")
                != prepare_start + full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
                or frame_record.get("module") != prepare_module
                or frame_record.get("frameIndex") != frame_index
                or frame_record != structural_frames[ordinal]
                or (frame_pointer is not None and frame_pointer <= 0)
            ):
                raise ValueError(f"{label} frame {ordinal} differs")
        if (
            reason == "structural-depth-differs"
            and depth == TARGET_PREPARE_RECURSION_DEPTH
            and frames
            and frames[0].get("frameIndex") == 0
        ):
            raise ValueError(f"{label} structural rejection differs")


def _events(
    trace: Mapping[str, Any],
    order: Mapping[int, str],
    groups: Sequence[Mapping[str, Any]],
    epochs: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    windows = frame_validator._code_windows(trace)
    events = [
        mapping(value, f"active watch event {index}")
        for index, value in enumerate(
            sequence(trace.get("qualifiedWatchpointEvents"), "active watch events")
        )
    ]
    if (
        not events
        or len(events) > MAXIMUM_QUALIFIED_WATCHPOINT_EVENT_COUNT
        or trace.get("finalQualifiedWatchpointEventCount") != len(events)
        or trace.get("qualifiedWatchpointHitCount") != len(events)
    ):
        raise ValueError("active watch event count differs")
    referenced_windows = set()
    previous_callback = 0
    previous_by_group = {
        index: _payload(
            group.get("initialAggregateHex"),
            full_base.AGGREGATE_BYTE_COUNT,
            f"watchpoint group {index} initial aggregate",
        )
        for index, group in enumerate(groups)
    }
    watch_by_group = {
        index: {
            integer(item.get("id"), "event watch ID"): mapping(
                item, "event watchpoint spec"
            )
            for item in sequence(group.get("watchpoints"), "event watchpoint specs")
        }
        for index, group in enumerate(groups)
    }
    changed_count = 0
    for index, event in enumerate(events):
        label = f"active watch event {index}"
        callback = _require_callback(
            order,
            event.get("callbackSequence"),
            "qualified-active-frame-watchpoint-hit",
            f"{label} callback",
        )
        group_index = integer(event.get("groupIndex"), f"{label} group")
        epoch_index = integer(event.get("epochRecordIndex"), f"{label} epoch")
        if not 0 <= group_index < len(groups) or epoch_index != group_index:
            raise ValueError(f"{label} group differs")
        group = groups[group_index]
        identity = _identity(event.get("frameIdentity"), f"{label} identity")
        if identity != _identity(group.get("identity"), f"{label} group identity"):
            raise ValueError(f"{label} frame identity differs")
        watchpoint_id = integer(event.get("watchpointID"), f"{label} watchpoint")
        spec = watch_by_group[group_index].get(watchpoint_id)
        lane = integer(event.get("triggeredLaneOffset"), f"{label} lane")
        if spec is None or spec.get("laneOffset") != lane:
            raise ValueError(f"{label} watchpoint identity differs")
        before = _payload(
            event.get("beforeHex"), full_base.AGGREGATE_BYTE_COUNT, f"{label} before"
        )
        after = _payload(
            event.get("afterHex"), full_base.AGGREGATE_BYTE_COUNT, f"{label} after"
        )
        changed_lanes = [
            offset
            for offset in WATCH_LANE_OFFSETS
            if before[offset : offset + WATCH_LANE_BYTE_COUNT]
            != after[offset : offset + WATCH_LANE_BYTE_COUNT]
        ]
        changed = before != after
        if (
            event.get("eventIndex") != index
            or callback <= previous_callback
            or event.get("threadID") != identity["threadID"]
            or event.get("watchedAddress") != spec.get("address")
            or event.get("aggregateAddress")
            != identity["roleBase"] + full_base.AGGREGATE_OFFSET
            or event.get("valueChanged") is not changed
            or event.get("changedLaneOffsets") != changed_lanes
            or before != previous_by_group[group_index]
        ):
            raise ValueError(f"{label} chain differs")
        role_aggregate = _role_aggregate(
            event.get("roleStateAfter"), f"{label} role", identity["roleBase"]
        )
        if role_aggregate != after:
            raise ValueError(f"{label} role alias differs")
        top = writer_base.frame_record(event.get("frame"), f"{label} frame")
        stop_pc = integer(event.get("stopPC"), f"{label} PC")
        backtrace = frame_validator._backtrace(
            event.get("backtrace"), f"{label} backtrace"
        )
        epoch_frame = mapping(epochs[epoch_index].get("frame"), "epoch frame")
        structural_frames = _structural_prepare_frames(
            backtrace,
            prepare_start=epoch_frame.get("symbolStart"),
            prepare_module=epoch_frame.get("module"),
        )
        if top != backtrace[0] or top.get("pc") != stop_pc:
            raise ValueError(f"{label} top frame differs")
        prepare_count = integer(
            event.get("prepareFrameCount"), f"{label} prepare count"
        )
        prepare_ordinal = integer(
            event.get("prepareFrameOrdinal"), f"{label} prepare ordinal"
        )
        prepare_index = integer(
            event.get("prepareFrameIndex"), f"{label} prepare index"
        )
        prepare_frame = mapping(event.get("prepareFrame"), f"{label} prepare frame")
        prepare_frame_pointer = integer(
            event.get("prepareFramePointer"), f"{label} prepare frame pointer"
        )
        if (
            prepare_count != len(structural_frames)
            or prepare_count < TARGET_PREPARE_RECURSION_DEPTH
            or not 0 <= prepare_ordinal < prepare_count
            or prepare_ordinal >= len(structural_frames)
            or prepare_frame.get("frameIndex") != prepare_index
            or prepare_frame != structural_frames[prepare_ordinal]
            or prepare_frame.get("function") != merge_base.PREPARE_LAYER_FUNCTION
            or prepare_frame.get("symbolStart") != epoch_frame.get("symbolStart")
            or prepare_frame.get("module") != epoch_frame.get("module")
            or prepare_frame_pointer != identity["framePointer"]
        ):
            raise ValueError(f"{label} prepare ancestry differs")
        window_index = integer(event.get("codeWindowIndex"), f"{label} window")
        if not 0 <= window_index < len(windows):
            raise ValueError(f"{label} code window index differs")
        window_start, _payload_bytes, stop_offset = windows[window_index]
        if window_start + stop_offset != stop_pc:
            raise ValueError(f"{label} code window PC differs")
        referenced_windows.add(window_index)
        if changed:
            writer_base.private_fields(
                event.get("privateFieldsAfter"), f"{label} private fields"
            )
            frame_validator._top_operands(
                event.get("operandSnapshot"),
                f"{label} operands",
                expected_pc=stop_pc,
            )
            changed_count += 1
        elif "privateFieldsAfter" in event or "operandSnapshot" in event:
            raise ValueError(f"{label} unchanged payload differs")
        previous_by_group[group_index] = after
        previous_callback = callback
    if referenced_windows != set(range(len(windows))):
        raise ValueError("active watch code window references differ")
    if trace.get("finalChangedQualifiedWatchpointEventCount") != changed_count:
        raise ValueError("active watch changed count differs")
    for index, group in enumerate(groups):
        if previous_by_group[index].hex() != group.get("lastAggregateHex"):
            raise ValueError(f"watchpoint group {index} final aggregate differs")
    return events


def _known_state_transfer(states: Sequence[bytes], marker: bytes) -> dict[str, Any]:
    final = struct.unpack("<4d", marker)
    carrier = KNOWN_CANVAS_EXTENT - KNOWN_GLASS_EXTENT - KNOWN_EDGE_PADDING - final[1]
    integer_origin = math.floor(carrier) - 1
    expected_values = (
        (0.0, 0.0, 0.0, 0.0),
        (
            carrier,
            KNOWN_CANVAS_EXTENT - carrier - KNOWN_GLASS_EXTENT,
            KNOWN_GLASS_EXTENT,
            KNOWN_GLASS_EXTENT,
        ),
        (
            carrier,
            KNOWN_CANVAS_EXTENT - carrier - KNOWN_GLASS_EXTENT - KNOWN_EDGE_PADDING,
            KNOWN_GLASS_EXTENT,
            KNOWN_GLASS_EXTENT + KNOWN_EDGE_PADDING,
        ),
        (
            float(integer_origin),
            KNOWN_CANVAS_EXTENT - carrier - KNOWN_GLASS_EXTENT - KNOWN_EDGE_PADDING,
            carrier + KNOWN_GLASS_EXTENT - integer_origin,
            carrier + KNOWN_GLASS_EXTENT + KNOWN_EDGE_PADDING - integer_origin,
        ),
    )
    if not all(math.isfinite(value) for values in expected_values for value in values):
        raise ValueError("known aggregate transfer is non-finite")
    expected = [struct.pack("<4d", *values) for values in expected_values]
    if expected[-1] != marker:
        raise ValueError("known final aggregate transfer differs")
    indices = []
    cursor = 0
    for payload in expected:
        try:
            index = states.index(payload, cursor)
        except ValueError as error:
            raise ValueError("known aggregate state transfer differs") from error
        indices.append(index)
        cursor = index + 1
    return {
        "carrierP": carrier,
        "integerOriginL": integer_origin,
        "stateIndices": indices,
        "stateHex": [payload.hex() for payload in expected],
    }


def _selection(
    trace: Mapping[str, Any],
    base_trace: Mapping[str, Any],
    order: Mapping[int, str],
    epochs: Sequence[Mapping[str, Any]],
    groups: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    *,
    prepare_start: int,
    prepare_module: Mapping[str, Any],
) -> tuple[list[int], list[int], int, int, dict[str, Any]]:
    selected = mapping(trace.get("selectedFrame"), "active watch selected frame")
    base_selected = mapping(base_trace.get("selectedFrame"), "base selected frame")
    callback = _require_callback(
        order,
        selected.get("callbackSequence"),
        "live-selected-active-frame-watch-closed",
        "active watch selection callback",
    )
    identity = _identity(selected.get("frameIdentity"), "selected identity")
    base_identity = _identity(base_selected.get("frameIdentity"), "base identity")
    source = integer(selected.get("selectedSource"), "selected source")
    epoch_index = integer(
        selected.get("selectedEpochRecordIndex"), "selected epoch index"
    )
    group_index = integer(
        selected.get("selectedWatchpointGroupIndex"), "selected group index"
    )
    if (
        identity != base_identity
        or source != base_selected.get("selectedSource")
        or selected.get("pc") != prepare_start + SELECTION_MARKER_OFFSET
        or selected.get("threadID") != identity["threadID"]
        or selected.get("prepareRecursionDepth") != TARGET_PREPARE_RECURSION_DEPTH
        or not 0 <= epoch_index < len(epochs)
        or group_index != epoch_index
        or _identity(epochs[epoch_index].get("identity"), "selected epoch identity")
        != identity
        or _identity(groups[group_index].get("identity"), "selected group identity")
        != identity
    ):
        raise ValueError("active watch selected identity differs")
    latest = max(
        (
            epoch
            for epoch in epochs
            if _identity(epoch.get("identity"), "matching epoch identity") == identity
            and integer(epoch.get("callbackSequence"), "matching epoch callback")
            < callback
        ),
        key=lambda epoch: integer(epoch.get("callbackSequence"), "latest epoch"),
    )
    if latest.get("recordIndex") != epoch_index:
        raise ValueError("active watch selected epoch is not latest")
    frame = merge_base.frame_record(
        selected.get("frame"),
        "active watch selected frame",
        expected_pc=prepare_start + SELECTION_MARKER_OFFSET,
        expected_symbol_start=prepare_start,
        expected_module=prepare_module,
    )
    backtrace = frame_validator._backtrace(
        selected.get("backtrace"), "active watch selected backtrace"
    )
    structural_frames = _structural_prepare_frames(
        backtrace,
        prepare_start=prepare_start,
        prepare_module=prepare_module,
    )
    registers = _selection_registers(
        selected.get("registers"), "active watch selected registers", identity
    )
    if (
        frame != backtrace[0]
        or len(structural_frames) != TARGET_PREPARE_RECURSION_DEPTH
        or structural_frames[0] != frame
        or registers["x28"] != source
        or registers["pc"] != prepare_start + SELECTION_MARKER_OFFSET
        or mapping(selected.get("objectChain"), "active watch object chain")
        != mapping(base_trace.get("objectChain"), "base object chain")
    ):
        raise ValueError("active watch selected frame differs")
    marker_aggregate = _role_aggregate(
        selected.get("roleStateAtMarker"),
        "active watch selected role",
        identity["roleBase"],
    )
    base_marker_aggregate = _role_aggregate(
        base_selected.get("roleStateAtMarker"),
        "base selected role",
        identity["roleBase"],
    )
    if (
        _payload(
            selected.get("aggregateAtMarkerHex"),
            full_base.AGGREGATE_BYTE_COUNT,
            "active watch marker aggregate",
        )
        != marker_aggregate
        or marker_aggregate != base_marker_aggregate
        or selected.get("aggregateAtMarkerHex")
        != base_selected.get("aggregateAtMarkerHex")
    ):
        raise ValueError("active watch marker closure differs")
    selected_indices = [
        integer(value, "selected event index")
        for value in sequence(
            trace.get("selectedWriterEventIndices"), "selected event indices"
        )
    ]
    expected_indices = [
        event["eventIndex"]
        for event in events
        if event.get("groupIndex") == group_index
        and event.get("epochRecordIndex") == epoch_index
        and event.get("frameIdentity") == dict(identity)
        and event.get("callbackSequence") < callback
    ]
    if (
        not selected_indices
        or selected_indices != expected_indices
        or selected.get("selectedWriterEventCount") != len(selected_indices)
        or trace.get("finalSelectedWriterEventCount") != len(selected_indices)
    ):
        raise ValueError("active watch selected event inventory differs")
    initial = _payload(
        epochs[epoch_index].get("aggregateAtEpochHex"),
        full_base.AGGREGATE_BYTE_COUNT,
        "selected epoch aggregate",
    )
    if initial != bytes(full_base.AGGREGATE_BYTE_COUNT):
        raise ValueError("active watch selected epoch is not zero initialized")
    selected_events = [events[index] for index in selected_indices]
    previous = initial
    states = [initial]
    changed = 0
    changed_offsets = []
    for event in selected_events:
        before = _payload(
            event.get("beforeHex"),
            full_base.AGGREGATE_BYTE_COUNT,
            "selected event before",
        )
        after = _payload(
            event.get("afterHex"),
            full_base.AGGREGATE_BYTE_COUNT,
            "selected event after",
        )
        if before != previous:
            raise ValueError("active watch selected chain is discontinuous")
        if event.get("valueChanged") is True:
            changed += 1
            changed_offsets.append(event["stopPC"] - prepare_start)
        states.append(after)
        previous = after
    distinct = len(set(states))
    known_transfer = _known_state_transfer(states, marker_aggregate)
    newly_opened = sorted(
        set(changed_offsets).difference(KNOWN_SAMPLED_WRITER_AFTER_OFFSETS)
    )
    if (
        previous != marker_aggregate
        or changed < MINIMUM_SELECTED_CHANGED_TRANSITION_COUNT
        or distinct < MINIMUM_SELECTED_CHANGED_TRANSITION_COUNT + 1
        or not newly_opened
        or trace.get("finalSelectedChangedTransitionCount") != changed
        or trace.get("finalSelectedDistinctAggregateCount") != distinct
        or groups[group_index].get("retirementReason") != "selected-marker-closed"
    ):
        raise ValueError("active watch selected causal chain differs")
    return selected_indices, newly_opened, changed, distinct, known_transfer


def validate(trace_path: Path, frame_trace_path: Path) -> dict[str, Any]:
    trace_bytes = trace_path.read_bytes()
    frame_trace_bytes = frame_trace_path.read_bytes()
    trace = mapping(json.loads(trace_bytes), "active watch trace")
    base_trace = mapping(json.loads(frame_trace_bytes), "frame writer trace")
    frame_context = _inherited_frame_context(base_trace)
    if (
        trace.get("prepareLayerActiveFrameWatchTraceSchemaVersion")
        != EXPECTED_TRACE_SCHEMA_VERSION
        or trace.get("classification") != EXPECTED_CLASSIFICATION
        or trace.get("status") != "finalized"
        or trace.get("statusBeforeFinalization")
        != "live-selected-active-frame-watch-closed"
        or mapping(trace.get("configuration"), "active watch configuration")
        != EXPECTED_CONFIGURATION
        or list(sequence(trace.get("failures"), "active watch failures"))
        or trace.get("finalFailureCount") != 0
    ):
        raise ValueError("active watch trace envelope differs")
    order = _callback_order(trace)
    prepare_start, prepare_module = _static_gate(trace, base_trace, order)
    _rejected_marker_diagnostics(
        trace,
        prepare_start=prepare_start,
        prepare_module=prepare_module,
    )
    selected_source = integer(
        frame_context.get("selectedSource"), "base selected source"
    )
    breakpoint_retirement_callback = _breakpoint_isolation_gate(
        trace,
        base_trace,
        order,
        selected_source=selected_source,
    )
    epochs, groups = _epochs_and_groups(
        trace,
        order,
        prepare_start=prepare_start,
        prepare_module=prepare_module,
        selected_source=selected_source,
    )
    if any(
        integer(epoch.get("callbackSequence"), "epoch callback")
        <= breakpoint_retirement_callback
        for epoch in epochs
    ):
        raise ValueError("active watch epoch precedes breakpoint isolation")
    if trace.get("epochMarkerHitCount") != len(epochs) + trace.get(
        "sourceUnknownEpochCount"
    ) + trace.get("rejectedEpochDepthCount") or trace.get(
        "selectionMarkerHitCount"
    ) != 1 + trace.get("rejectedSelectionMarkerHitCount"):
        raise ValueError("active watch marker accounting differs")
    if (
        integer(trace.get("epochMarkerHitCount"), "epoch marker hits")
        > MAXIMUM_EPOCH_MARKER_HIT_COUNT
        or integer(trace.get("returnMarkerHitCount"), "return marker hits")
        > MAXIMUM_RETURN_MARKER_HIT_COUNT
        or integer(trace.get("selectionMarkerHitCount"), "selection marker hits")
        > MAXIMUM_SELECTION_MARKER_HIT_COUNT
        or integer(trace.get("rawWatchpointHitCount"), "raw watchpoint hits")
        > MAXIMUM_RAW_WATCHPOINT_HIT_COUNT
        or trace.get("ignoredWatchpointHitCount") != 0
        or trace.get("unretainedIgnoredWatchpointHitCount") != 0
        or list(
            sequence(
                trace.get("ignoredWatchpointDiagnostics"),
                "ignored watchpoint diagnostics",
            )
        )
    ):
        raise ValueError("active watch bounded accounting differs")
    events = _events(trace, order, groups, epochs)
    if trace.get("rawWatchpointHitCount") != len(events):
        raise ValueError("active watch raw and qualified accounting differs")
    selected_indices, newly_opened, changed, distinct, known_transfer = _selection(
        trace,
        base_trace,
        order,
        epochs,
        groups,
        events,
        prepare_start=prepare_start,
        prepare_module=prepare_module,
    )
    changed_offsets = sorted(
        {
            events[index]["stopPC"] - prepare_start
            for index in selected_indices
            if events[index].get("valueChanged") is True
        }
    )
    return {
        "prepareLayerActiveFrameWatchValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": EXPECTED_VALIDATION_CLASSIFICATION,
        "inputTrace": trace_path.name,
        "inputTraceSHA256": hashlib.sha256(trace_bytes).hexdigest(),
        "inheritedFrameTrace": frame_trace_path.name,
        "inheritedFrameTraceSHA256": hashlib.sha256(frame_trace_bytes).hexdigest(),
        "conclusion": "success",
        "prospectiveGatePassed": True,
        "aggregate": {
            "epochRecordCount": len(epochs),
            "watchpointGroupCount": len(groups),
            "qualifiedWatchpointEventCount": len(events),
            "selectedWriterEventCount": len(selected_indices),
            "selectedChangedTransitionCount": changed,
            "selectedDistinctAggregateCount": distinct,
            "selectedChangedWriterOffsets": changed_offsets,
            "newlyOpenedChangedWriterOffsets": newly_opened,
            "knownStateTransfer": known_transfer,
            "inheritedSelectedSampleEventCount": frame_context[
                "selectedSampleEventCount"
            ],
            "inheritedSampledSuffixClosedAtMarker": frame_context[
                "sampledSuffixClosedAtMarker"
            ],
        },
        "sealedConclusion": {
            "inheritedStaticSourceMarkerContextPassed": True,
            "sampledWriterBreakpointsRetiredBeforeHardwareWatch": True,
            "fourLaneAggregateCoverageInstalled": True,
            "watchLifetimeBoundToLiveFrame": True,
            "selectedHardwareChainContiguous": True,
            "knownAggregateStateTransferPassed": True,
            "completeCausalWriterPCSequenceCaptured": True,
            "previouslyUnsampledChangedWriterOpened": True,
            "writerInstructionSemanticsOpened": False,
            "completePublicCropRuleRecovered": False,
            "unseenGeometryTransferPassed": False,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("frame_trace", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.trace, arguments.frame_trace)
    rendered = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(rendered, end="")
    else:
        arguments.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
