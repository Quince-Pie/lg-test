"""LLDB capture of the live selected ``prepare_layer`` aggregate writer.

The predecessor proved that retrospectively arming a watchpoint on an expired
``prepare_layer`` stack frame observes unrelated stack reuse.  This successor
arms only from a source-known live frame and accepts a hardware stop only when
an exact unwound ``prepare_layer`` frame carries both the watched ``x19`` role
base and the independently selected ``x28`` source.
"""

import hashlib
import json
import os
import struct
import sys
from pathlib import Path

import lldb


ANALYSIS_ROOT = Path(__file__).resolve().parent
if str(ANALYSIS_ROOT) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_ROOT))
import capture_prepare_layer_full_path_trace_lldb as capture_base  # noqa: E402


TRACE_SCHEMA_VERSION = 1
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
TRACE_OUTPUT_ENVIRONMENT = "LG_PREPARE_LAYER_LIVE_WRITER_TRACE_OUTPUT"
DEFAULT_TRACE_OUTPUT = (
    "transition-introspection/prepare-layer-live-writer-trace.json"
)


_state = {
    "debugger": None,
    "trace": None,
    "captureEntryBreakpoint": None,
    "captureLateBreakpoint": None,
    "prepareEntryBreakpoint": None,
    "liveArmBreakpoint": None,
    "prepareLayer": None,
    "objectAddresses": {},
    "lateCandidateCount": 0,
    "callbackSequence": 0,
    "markerHitCount": 0,
    "rejectedMarkerHitCount": 0,
    "discardedMarkerHitCount": 0,
    "aggregateWatchpoint": None,
    "aggregateWatchpointSpec": None,
    "rawWatchpointHitCount": 0,
    "ignoredWatchpointHitCount": 0,
    "ignoredPrepareFrameSeenCount": 0,
    "unretainedIgnoredWatchpointHitCount": 0,
    "qualifiedWatchpointHitCount": 0,
    "ignoredWatchpointGroups": {},
}
capture_base._state = _state


def _trace_path():
    return Path(os.environ.get(TRACE_OUTPUT_ENVIRONMENT, DEFAULT_TRACE_OUTPUT))


def _new_trace():
    return {
        "prepareLayerLiveWriterTraceSchemaVersion": TRACE_SCHEMA_VERSION,
        "classification": (
            "preregistered-live-selected-prepare-layer-frame-qualified-aggregate-"
            "origin-writer-trace; writer-semantics-public-crop-law-unseen-"
            "transfer-and-product-parity-remain-sealed"
        ),
        "status": "initialized",
        "configuration": {
            "captureBackdropSymbol": capture_base.CAPTURE_BACKDROP_SYMBOL,
            "captureBackdropCodeByteCount": (
                capture_base.CAPTURE_BACKDROP_CODE_BYTE_COUNT
            ),
            "captureBackdropCodeSHA256": (
                capture_base.CAPTURE_BACKDROP_CODE_SHA256
            ),
            "captureBackdropLateOffset": capture_base.CAPTURE_BACKDROP_LATE_OFFSET,
            "prepareLayerFunction": capture_base.PREPARE_LAYER_FUNCTION,
            "prepareLayerSymbolByteCount": (
                capture_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
            ),
            "prepareLayerFullCodeSHA256": PREPARE_LAYER_FULL_CODE_SHA256,
            "knownPrepareLayerWindows": [
                {"offset": offset, "byteCount": count, "sha256": digest}
                for offset, count, digest in capture_base.KNOWN_PREPARE_LAYER_WINDOWS
            ],
            "unionHelperRelativeToPrepareLayer": (
                capture_base.UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
            ),
            "unionHelperSymbolName": capture_base.UNION_HELPER_SYMBOL_NAME,
            "unionHelperSymbolByteCount": (
                capture_base.UNION_HELPER_SYMBOL_BYTE_COUNT
            ),
            "unionHelperSymbolSHA256": capture_base.UNION_HELPER_SYMBOL_SHA256,
            "liveArmMarkerName": LIVE_ARM_MARKER_NAME,
            "liveArmMarkerOffset": LIVE_ARM_MARKER_OFFSET,
            "maximumPreselectionMarkerRecordCount": (
                MAXIMUM_PRESELECTION_MARKER_RECORD_COUNT
            ),
            "maximumMarkerHitCount": MAXIMUM_MARKER_HIT_COUNT,
            "roleStateByteCount": capture_base.ROLE_STATE_BYTE_COUNT,
            "aggregateOffset": capture_base.AGGREGATE_OFFSET,
            "aggregateByteCount": capture_base.AGGREGATE_BYTE_COUNT,
            "watchpointByteCount": capture_base.WATCHPOINT_BYTE_COUNT,
            "maximumRawWatchpointHitCount": MAXIMUM_RAW_WATCHPOINT_HIT_COUNT,
            "maximumIgnoredWatchpointDiagnosticCount": (
                MAXIMUM_IGNORED_WATCHPOINT_DIAGNOSTIC_COUNT
            ),
            "maximumQualifiedWatchpointEventCount": (
                MAXIMUM_QUALIFIED_WATCHPOINT_EVENT_COUNT
            ),
            "prepareFrameRegisterNames": list(PREPARE_FRAME_REGISTER_NAMES),
            "maximumLateCandidateCount": (
                capture_base.MAXIMUM_LATE_CANDIDATE_COUNT
            ),
            "maximumLateCandidateDiagnosticCount": (
                capture_base.MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT
            ),
            "maximumBacktraceFrameCount": (
                capture_base.MAXIMUM_BACKTRACE_FRAME_COUNT
            ),
            "pcCenteredCodeWindowByteCount": (
                capture_base.PC_CENTERED_CODE_WINDOW_BYTE_COUNT
            ),
            "pcCenteredCodeWindowBacktrack": (
                capture_base.PC_CENTERED_CODE_WINDOW_BACKTRACK
            ),
            "stackSnapshotByteCount": capture_base.STACK_SNAPSHOT_BYTE_COUNT,
            "registerPointerSnapshotByteCount": (
                capture_base.REGISTER_POINTER_SNAPSHOT_BYTE_COUNT
            ),
            "registerPointerSnapshotBacktrack": (
                capture_base.REGISTER_POINTER_SNAPSHOT_BACKTRACK
            ),
            "pointerProbeAddressRange": [
                capture_base.MINIMUM_POINTER_PROBE_ADDRESS,
                capture_base.MAXIMUM_POINTER_PROBE_ADDRESS,
            ],
            "generalRegisterNames": list(capture_base.GENERAL_REGISTER_NAMES),
            "simdRegisterNames": list(capture_base.SIMD_REGISTER_NAMES),
            "pointerProbeRegisterNames": list(
                capture_base.POINTER_PROBE_REGISTER_NAMES
            ),
            "prepareLayerRoleRegisterNames": list(
                capture_base.PREPARE_LAYER_ROLE_REGISTER_NAMES
            ),
            "objectSnapshotSpecs": [
                {"base": base_name, "byteCount": byte_count}
                for base_name, byte_count in capture_base.OBJECT_SNAPSHOT_SPECS
            ],
            "watchpointArmRule": (
                "never arm retrospectively; arm once at the first source-known "
                "live +0x3ef0 marker whose x28 is the exact selected source; "
                "require marker aggregate bytes to equal watchpoint initial bytes"
            ),
            "watchpointQualificationRule": (
                "retain a hardware stop only when an exact prepare_layer frame "
                "in its live backtrace has unwound x19 equal to the watched role "
                "base and unwound x28 equal to the selected source"
            ),
        },
        "callbackOrder": [],
        "captureBackdrop": {},
        "prepareLayer": {},
        "lateCandidateCount": 0,
        "lateCandidateDiagnostics": [],
        "objectChain": {},
        "liveArmMarkerRecords": [],
        "aggregateWatchpoint": {},
        "ignoredWatchpointDiagnostics": [],
        "codeWindows": [],
        "qualifiedWatchpointEvents": [],
        "failures": [],
    }


def _write_trace():
    trace = _state["trace"]
    if trace is None:
        return
    path = _trace_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(trace, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _failure(stage, error):
    _state["trace"]["failures"].append(
        {"stage": str(stage), "message": str(error)}
    )
    _write_trace()


def _next_sequence(kind):
    _state["callbackSequence"] += 1
    sequence = _state["callbackSequence"]
    _state["trace"]["callbackOrder"].append(
        {"sequence": sequence, "kind": str(kind)}
    )
    return sequence


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _address_breakpoint(target, address, callback, label):
    breakpoint = target.BreakpointCreateByAddress(address)
    if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
        raise RuntimeError(label + " breakpoint is unresolved")
    _set_callback(breakpoint, callback, label)
    return breakpoint


def _breakpoint_location_addresses(breakpoint, target):
    return [
        breakpoint.GetLocationAtIndex(index).GetAddress().GetLoadAddress(target)
        for index in range(breakpoint.GetNumLocations())
    ]


def _selected_source():
    return _state["objectAddresses"].get("source")


def _classify_marker_records():
    source = _selected_source()
    if source is None:
        return
    for record in _state["trace"]["liveArmMarkerRecords"]:
        record["selectedSource"] = record["source"] == source


def capture_backdrop_entry(frame, _breakpoint_location, _internal_dict):
    """Gate ``capture_backdrop`` and arm its exact source selector."""
    try:
        sequence = _next_sequence("capture-backdrop-entry")
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        symbol_address = frame.GetPC()
        code = capture_base._read_memory(
            process,
            symbol_address,
            capture_base.CAPTURE_BACKDROP_CODE_BYTE_COUNT,
            "capture_backdrop code",
        )
        digest = hashlib.sha256(code).hexdigest()
        _state["trace"]["captureBackdrop"] = {
            "callbackSequence": sequence,
            "symbolAddress": symbol_address,
            "codeByteCount": len(code),
            "codeSHA256": digest,
            "module": capture_base._module_record(frame.GetModule(), target),
        }
        if digest != capture_base.CAPTURE_BACKDROP_CODE_SHA256:
            raise RuntimeError("capture_backdrop code SHA-256 differs")
        late = _address_breakpoint(
            target,
            symbol_address + capture_base.CAPTURE_BACKDROP_LATE_OFFSET,
            "capture_backdrop_late",
            "capture_backdrop late",
        )
        _state["captureLateBreakpoint"] = late
        _state["trace"]["captureBackdrop"]["lateBreakpointID"] = late.GetID()
        _state["captureEntryBreakpoint"].SetEnabled(False)
        _state["trace"]["status"] = "capture-backdrop-late-armed"
        _write_trace()
    except Exception as error:
        _failure("capture-backdrop-entry", error)
        if _state["captureEntryBreakpoint"] is not None:
            _state["captureEntryBreakpoint"].SetEnabled(False)
    return False


def _reject_late_candidate(candidate):
    trace = _state["trace"]
    trace["lateCandidateCount"] = _state["lateCandidateCount"]
    if (
        len(trace["lateCandidateDiagnostics"])
        < capture_base.MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT
    ):
        trace["lateCandidateDiagnostics"].append(candidate)
    if _state["lateCandidateCount"] >= capture_base.MAXIMUM_LATE_CANDIDATE_COUNT:
        _failure(
            "capture-backdrop-late-candidate-limit",
            "no exact late candidate within %d invocations"
            % capture_base.MAXIMUM_LATE_CANDIDATE_COUNT,
        )
        _state["captureLateBreakpoint"].SetEnabled(False)
    else:
        _write_trace()


def capture_backdrop_late(frame, _breakpoint_location, _internal_dict):
    """Select the exact preconvergence source without arming retrospectively."""
    try:
        process = frame.GetThread().GetProcess()
        source = capture_base._register(frame, "x19")
        owner = capture_base._register(frame, "x20")
        layer = capture_base._register(frame, "x24")
        _state["lateCandidateCount"] += 1
        candidate = {
            "lateCandidateIndex": _state["lateCandidateCount"],
            "source": source,
            "owner": owner,
            "layer": layer,
        }
        if 0 in (source, owner, layer):
            candidate["rejection"] = "null primary object pointer"
            _reject_late_candidate(candidate)
            return False
        layer_state = capture_base._read_u64(
            process, layer + 0x10, "layer-state pointer"
        )
        candidate["layerState"] = layer_state
        if layer_state == 0:
            candidate["rejection"] = "null layer-state pointer"
            _reject_late_candidate(candidate)
            return False
        source_owner = capture_base._read_u64(
            process, source + 0x48, "source owner pointer"
        )
        layer_state_source = capture_base._read_u64(
            process, layer_state + 0x120, "layer-state source pointer"
        )
        pointer_chain_exact = source_owner == owner and layer_state_source == source
        candidate.update(
            {
                "sourceOwner": source_owner,
                "layerStateSource": layer_state_source,
                "pointerChainExact": pointer_chain_exact,
            }
        )
        if not pointer_chain_exact:
            candidate["rejection"] = "object pointer chain differs"
            _reject_late_candidate(candidate)
            return False
        source_bytes = capture_base._read_memory(
            process, source + 0x50, 16, "source rectangle"
        )
        layer_state_bytes = capture_base._read_memory(
            process, layer_state + 0xB0, 16, "layer-state rectangle"
        )
        owner_bytes = capture_base._read_memory(
            process, owner + 0xE0, 32, "owner rectangle"
        )
        source_rectangle = list(struct.unpack("<4i", source_bytes))
        layer_state_rectangle = list(struct.unpack("<4i", layer_state_bytes))
        owner_rectangle = list(struct.unpack("<4d", owner_bytes))
        owner_equals_layer_state = owner_rectangle == [
            float(value) for value in layer_state_rectangle
        ]
        source_equals_layer_state = source_rectangle == layer_state_rectangle
        preconvergence_exact = owner_equals_layer_state and not source_equals_layer_state
        candidate.update(
            {
                "ownerEqualsLayerStateRectangle": owner_equals_layer_state,
                "sourceEqualsLayerStateRectangle": source_equals_layer_state,
                "preconvergenceExact": preconvergence_exact,
            }
        )
        if not preconvergence_exact:
            candidate["rejection"] = "preconvergence rectangle state differs"
            _reject_late_candidate(candidate)
            return False
        sequence = _next_sequence("source-selected")
        _state["objectAddresses"] = {
            "source": source,
            "owner": owner,
            "layer": layer,
            "layerState": layer_state,
        }
        _state["trace"]["lateCandidateCount"] = _state["lateCandidateCount"]
        _state["trace"]["objectChain"] = {
            "callbackSequence": sequence,
            "addresses": dict(_state["objectAddresses"]),
            "exact": True,
            "pointerChainExact": True,
            "selectedLateCandidateIndex": _state["lateCandidateCount"],
            "ownerEqualsLayerStateRectangle": owner_equals_layer_state,
            "sourceEqualsLayerStateRectangle": source_equals_layer_state,
            "preconvergenceExact": preconvergence_exact,
            "sourceSelectedRectI32": source_rectangle,
            "sourceSelectedRectI32Hex": source_bytes.hex(),
            "layerStateSelectedRectI32": layer_state_rectangle,
            "layerStateSelectedRectI32Hex": layer_state_bytes.hex(),
            "ownerSelectedRectF64": owner_rectangle,
            "ownerSelectedRectF64Hex": owner_bytes.hex(),
        }
        _classify_marker_records()
        _state["captureLateBreakpoint"].SetEnabled(False)
        _state["trace"]["status"] = "source-selected-awaiting-live-arm-marker"
        _write_trace()
    except Exception as error:
        _failure("capture-backdrop-late", error)
        if _state["captureLateBreakpoint"] is not None:
            _state["captureLateBreakpoint"].SetEnabled(False)
    return False


def prepare_layer_entry(frame, breakpoint_location, _internal_dict):
    """Capture and gate the exact full function before installing one marker."""
    try:
        sequence = _next_sequence("prepare-layer-entry")
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        symbol = frame.GetSymbol()
        if (
            frame.GetFunctionName() != capture_base.PREPARE_LAYER_FUNCTION
            or not symbol.IsValid()
        ):
            raise RuntimeError("prepare_layer function identity differs")
        start = symbol.GetStartAddress().GetLoadAddress(target)
        end = symbol.GetEndAddress().GetLoadAddress(target)
        location_address = breakpoint_location.GetAddress().GetLoadAddress(target)
        if (
            start == lldb.LLDB_INVALID_ADDRESS
            or end == lldb.LLDB_INVALID_ADDRESS
            or end - start != capture_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
            or frame.GetPC() != start
            or location_address != start
        ):
            raise RuntimeError("prepare_layer exact entry differs")
        code = capture_base._read_memory(
            process,
            start,
            capture_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "full prepare_layer code",
        )
        digest = hashlib.sha256(code).hexdigest()
        if digest != PREPARE_LAYER_FULL_CODE_SHA256:
            raise RuntimeError("full prepare_layer code SHA-256 differs")
        for offset, count, expected in capture_base.KNOWN_PREPARE_LAYER_WINDOWS:
            if hashlib.sha256(code[offset : offset + count]).hexdigest() != expected:
                raise RuntimeError("known prepare_layer code window differs")
        helper_address = start + capture_base.UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
        helper_resolved = target.ResolveLoadAddress(helper_address)
        helper_symbol = capture_base._symbol_record(
            helper_resolved.GetSymbol(), target
        )
        helper_code = capture_base._read_memory(
            process,
            helper_address,
            capture_base.UNION_HELPER_SYMBOL_BYTE_COUNT,
            "union_bounds symbol code",
        )
        if (
            helper_symbol.get("valid") is not True
            or helper_symbol.get("name") != capture_base.UNION_HELPER_SYMBOL_NAME
            or helper_symbol.get("startAddress") != helper_address
            or helper_symbol.get("endAddress")
            != helper_address + capture_base.UNION_HELPER_SYMBOL_BYTE_COUNT
            or hashlib.sha256(helper_code).hexdigest()
            != capture_base.UNION_HELPER_SYMBOL_SHA256
        ):
            raise RuntimeError("union_bounds identity differs")
        marker_address = start + LIVE_ARM_MARKER_OFFSET
        marker = _address_breakpoint(
            target,
            marker_address,
            "prepare_layer_live_arm_marker",
            "prepare_layer live arm marker",
        )
        _state["liveArmBreakpoint"] = marker
        prepare = {
            "callbackSequence": sequence,
            "callbackPC": frame.GetPC(),
            "callbackLocationAddress": location_address,
            "entryBreakpointID": _state["prepareEntryBreakpoint"].GetID(),
            "entryBreakpointLocationAddresses": _breakpoint_location_addresses(
                _state["prepareEntryBreakpoint"], target
            ),
            "function": capture_base.PREPARE_LAYER_FUNCTION,
            "symbolStart": start,
            "symbolEnd": end,
            "symbolByteCount": end - start,
            "module": capture_base._module_record(frame.GetModule(), target),
            "fullCode": {
                "address": start,
                "byteCount": len(code),
                "sha256": digest,
                "hex": code.hex(),
            },
            "knownWindows": [
                {
                    "offset": offset,
                    "byteCount": count,
                    "sha256": hashlib.sha256(
                        code[offset : offset + count]
                    ).hexdigest(),
                }
                for offset, count, _expected in capture_base.KNOWN_PREPARE_LAYER_WINDOWS
            ],
            "unionHelper": {
                "address": helper_address,
                "relativeToPrepareLayer": helper_address - start,
                "module": capture_base._module_record(
                    helper_resolved.GetModule(), target
                ),
                "symbol": helper_symbol,
                "symbolCodeSHA256": hashlib.sha256(helper_code).hexdigest(),
            },
            "liveArmMarker": {
                "name": LIVE_ARM_MARKER_NAME,
                "offset": LIVE_ARM_MARKER_OFFSET,
                "address": marker_address,
                "breakpointID": marker.GetID(),
                "instructionRawLittleEndianHex": code[
                    LIVE_ARM_MARKER_OFFSET : LIVE_ARM_MARKER_OFFSET + 4
                ].hex(),
            },
        }
        _state["prepareLayer"] = prepare
        _state["trace"]["prepareLayer"] = prepare
        _state["prepareEntryBreakpoint"].SetEnabled(False)
        _state["trace"]["status"] = "full-code-gated-live-arm-marker-installed"
        _write_trace()
    except Exception as error:
        _failure("prepare-layer-entry", error)
        if _state["prepareEntryBreakpoint"] is not None:
            _state["prepareEntryBreakpoint"].SetEnabled(False)
    return False


def _install_live_watchpoint(frame, marker_record, role):
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    role_base = marker_record["roleBase"]
    watched_address = role_base + capture_base.AGGREGATE_OFFSET
    initial = capture_base._read_memory(
        process,
        watched_address,
        capture_base.WATCHPOINT_BYTE_COUNT,
        "live aggregate origin initial value",
    )
    marker_initial = bytes.fromhex(marker_record["aggregateHex"])[
        : capture_base.WATCHPOINT_BYTE_COUNT
    ]
    if initial != marker_initial:
        raise RuntimeError("live marker and watchpoint initial bytes differ")
    error = lldb.SBError()
    watchpoint = target.WatchAddress(
        watched_address,
        capture_base.WATCHPOINT_BYTE_COUNT,
        False,
        True,
        error,
    )
    if not error.Success() or not watchpoint.IsValid():
        raise RuntimeError(
            "live aggregate watchpoint failed: %s"
            % (error.GetCString() or "invalid watchpoint")
        )
    result = lldb.SBCommandReturnObject()
    command = "watchpoint command add -F %s.aggregate_origin_watchpoint %d" % (
        __name__,
        watchpoint.GetID(),
    )
    _state["debugger"].GetCommandInterpreter().HandleCommand(command, result)
    if not result.Succeeded():
        raise RuntimeError(
            "live aggregate watchpoint callback failed: %s" % result.GetError()
        )
    sequence = _next_sequence("live-aggregate-watchpoint-armed")
    spec = {
        "callbackSequence": sequence,
        "id": watchpoint.GetID(),
        "deprecatedHardwareIndex": watchpoint.GetHardwareIndex(),
        "markerRecordIndex": marker_record["recordIndex"],
        "markerCallbackSequence": marker_record["callbackSequence"],
        "roleBase": role_base,
        "selectedSource": _selected_source(),
        "address": watched_address,
        "byteCount": capture_base.WATCHPOINT_BYTE_COUNT,
        "initialHex": initial.hex(),
        "initialRoleStateSHA256": hashlib.sha256(role).hexdigest(),
        "initialRoleStateHex": role.hex(),
        "lastValue": initial,
    }
    _state["aggregateWatchpoint"] = watchpoint
    _state["aggregateWatchpointSpec"] = spec
    _state["trace"]["aggregateWatchpoint"] = {
        name: value for name, value in spec.items() if name != "lastValue"
    }
    _state["liveArmBreakpoint"].SetEnabled(False)
    _state["trace"]["status"] = "live-selected-watchpoint-active"
    _write_trace()


def prepare_layer_live_arm_marker(frame, _breakpoint_location, _internal_dict):
    """Retain bounded early state and arm only from a live selected frame."""
    try:
        _state["markerHitCount"] += 1
        if _state["markerHitCount"] > MAXIMUM_MARKER_HIT_COUNT:
            _state["discardedMarkerHitCount"] += 1
            _state["liveArmBreakpoint"].SetEnabled(False)
            raise RuntimeError("live arm marker hit bound exceeded")
        process = frame.GetThread().GetProcess()
        x19 = capture_base._register(frame, "x19")
        x28 = capture_base._register(frame, "x28")
        source = _selected_source()
        if source is not None and x28 != source:
            _state["rejectedMarkerHitCount"] += 1
            return False
        records = _state["trace"]["liveArmMarkerRecords"]
        preselection_count = sum(
            record.get("sourceKnownAtHit") is False for record in records
        )
        if source is None and preselection_count >= MAXIMUM_PRESELECTION_MARKER_RECORD_COUNT:
            _state["discardedMarkerHitCount"] += 1
            _state["liveArmBreakpoint"].SetEnabled(False)
            raise RuntimeError("preselection live arm marker bound exceeded")
        role = capture_base._read_memory(
            process,
            x19,
            capture_base.ROLE_STATE_BYTE_COUNT,
            "live arm marker role state",
        )
        sequence = _next_sequence("live-arm-marker")
        aggregate = role[
            capture_base.AGGREGATE_OFFSET : capture_base.AGGREGATE_OFFSET
            + capture_base.AGGREGATE_BYTE_COUNT
        ]
        record = {
            "recordIndex": len(records),
            "callbackSequence": sequence,
            "sourceKnownAtHit": source is not None,
            "selectedSource": None if source is None else True,
            "threadID": frame.GetThread().GetThreadID(),
            "pc": frame.GetPC(),
            "frame": capture_base._frame_record(
                frame, process.GetTarget()
            ),
            "backtrace": capture_base._backtrace(frame.GetThread()),
            "roleBase": x19,
            "source": x28,
            "registers": capture_base._register_snapshot(
                frame, PREPARE_FRAME_REGISTER_NAMES
            ),
            "roleState": {
                "address": x19,
                "byteCount": len(role),
                "sha256": hashlib.sha256(role).hexdigest(),
                "hex": role.hex(),
            },
            "aggregateHex": aggregate.hex(),
        }
        records.append(record)
        if source is not None:
            _install_live_watchpoint(frame, record, role)
        else:
            _write_trace()
    except Exception as error:
        _failure("prepare-layer-live-arm-marker", error)
        if _state["liveArmBreakpoint"] is not None:
            _state["liveArmBreakpoint"].SetEnabled(False)
    return False


def _matching_prepare_frame(thread, spec):
    target = thread.GetProcess().GetTarget()
    start = _state["prepareLayer"]["symbolStart"]
    end = _state["prepareLayer"]["symbolEnd"]
    saw_exact_prepare = False
    for index in range(
        min(thread.GetNumFrames(), capture_base.MAXIMUM_BACKTRACE_FRAME_COUNT)
    ):
        candidate = thread.GetFrameAtIndex(index)
        if candidate.GetFunctionName() != capture_base.PREPARE_LAYER_FUNCTION:
            continue
        symbol = candidate.GetSymbol()
        if not symbol.IsValid():
            continue
        symbol_start = symbol.GetStartAddress().GetLoadAddress(target)
        symbol_end = symbol.GetEndAddress().GetLoadAddress(target)
        if symbol_start != start or symbol_end != end:
            continue
        saw_exact_prepare = True
        try:
            x19 = capture_base._register(candidate, "x19")
            x28 = capture_base._register(candidate, "x28")
        except Exception:
            continue
        if x19 == spec["roleBase"] and x28 == spec["selectedSource"]:
            return candidate, index, True
    return None, None, saw_exact_prepare


def _record_ignored_watchpoint(frame, before, after, saw_exact_prepare):
    _state["ignoredWatchpointHitCount"] += 1
    if saw_exact_prepare:
        _state["ignoredPrepareFrameSeenCount"] += 1
    pc = frame.GetPC()
    function = frame.GetFunctionName() or ""
    module = capture_base._module_record(
        frame.GetModule(), frame.GetThread().GetProcess().GetTarget()
    )
    key = (pc, function, saw_exact_prepare, module.get("path"))
    groups = _state["ignoredWatchpointGroups"]
    group = groups.get(key)
    if group is not None:
        group["hitCount"] += 1
        group["changedCount"] += before != after
        group["lastAfterHex"] = after.hex()
    elif len(groups) < MAXIMUM_IGNORED_WATCHPOINT_DIAGNOSTIC_COUNT:
        groups[key] = {
            "stopPC": pc,
            "function": function,
            "module": module,
            "exactPrepareFrameSeen": saw_exact_prepare,
            "hitCount": 1,
            "changedCount": int(before != after),
            "firstBeforeHex": before.hex(),
            "lastAfterHex": after.hex(),
        }
    else:
        _state["unretainedIgnoredWatchpointHitCount"] += 1


def aggregate_origin_watchpoint(frame, watchpoint, _internal_dict):
    """Retain only writes from the exact live selected prepare-layer ancestry."""
    try:
        spec = _state["aggregateWatchpointSpec"]
        if spec is None or watchpoint.GetID() != spec["id"]:
            raise RuntimeError("live aggregate watchpoint identity differs")
        process = frame.GetThread().GetProcess()
        after = capture_base._read_memory(
            process,
            spec["address"],
            capture_base.WATCHPOINT_BYTE_COUNT,
            "live aggregate origin after write",
        )
        before = spec["lastValue"]
        spec["lastValue"] = after
        _state["rawWatchpointHitCount"] += 1
        if _state["rawWatchpointHitCount"] > MAXIMUM_RAW_WATCHPOINT_HIT_COUNT:
            raise RuntimeError("raw watchpoint hit bound exceeded")
        prepare_frame, prepare_frame_index, saw_exact_prepare = (
            _matching_prepare_frame(frame.GetThread(), spec)
        )
        if prepare_frame is None:
            _record_ignored_watchpoint(
                frame, before, after, saw_exact_prepare
            )
            if _state["rawWatchpointHitCount"] % 128 == 0:
                _write_trace()
            return False
        _state["qualifiedWatchpointHitCount"] += 1
        sequence = _next_sequence("qualified-live-aggregate-watchpoint-hit")
        role_after = capture_base._read_memory(
            process,
            spec["roleBase"],
            capture_base.ROLE_STATE_BYTE_COUNT,
            "live aggregate role after qualified write",
        )
        event = {
            "eventIndex": len(_state["trace"]["qualifiedWatchpointEvents"]),
            "callbackSequence": sequence,
            "watchpointID": watchpoint.GetID(),
            "rawWatchpointHitIndex": _state["rawWatchpointHitCount"],
            "qualifiedWatchpointHitIndex": _state[
                "qualifiedWatchpointHitCount"
            ],
            "threadID": frame.GetThread().GetThreadID(),
            "stopPC": frame.GetPC(),
            "watchedAddress": spec["address"],
            "beforeHex": before.hex(),
            "afterHex": after.hex(),
            "valueChanged": before != after,
            "frame": capture_base._frame_record(
                frame, process.GetTarget()
            ),
            "backtrace": capture_base._backtrace(frame.GetThread()),
            "prepareFrameIndex": prepare_frame_index,
            "prepareFrame": capture_base._frame_record(
                prepare_frame, process.GetTarget()
            ),
            "prepareFrameRegisters": capture_base._register_snapshot(
                prepare_frame, PREPARE_FRAME_REGISTER_NAMES
            ),
            "codeWindowIndex": capture_base._code_window(frame),
            "roleStateAfter": {
                "address": spec["roleBase"],
                "byteCount": len(role_after),
                "sha256": hashlib.sha256(role_after).hexdigest(),
                "hex": role_after.hex(),
            },
            "privateFieldsAfter": capture_base._snapshot_private_fields(process),
            "operandSnapshot": capture_base._operand_snapshot(frame),
        }
        _state["trace"]["qualifiedWatchpointEvents"].append(event)
        if (
            _state["qualifiedWatchpointHitCount"]
            >= MAXIMUM_QUALIFIED_WATCHPOINT_EVENT_COUNT
        ):
            watchpoint.SetEnabled(False)
            _state["trace"]["status"] = "qualified-watchpoint-hit-limit-reached"
        else:
            _state["trace"]["status"] = "qualified-live-writer-captured"
        _write_trace()
    except Exception as error:
        _failure("qualified-live-aggregate-watchpoint", error)
        watchpoint.SetEnabled(False)
    return False


def finalize():
    """Finalize exact raw, ignored, marker, and qualified-event accounting."""
    trace = _state["trace"]
    if trace is None:
        return
    _classify_marker_records()
    trace["ignoredWatchpointDiagnostics"] = sorted(
        _state["ignoredWatchpointGroups"].values(),
        key=lambda item: (
            item["stopPC"],
            item["function"],
            item["exactPrepareFrameSeen"],
        ),
    )
    trace["statusBeforeFinalization"] = trace["status"]
    trace["status"] = "finalized"
    trace["finalFailureCount"] = len(trace["failures"])
    trace["finalCallbackSequence"] = _state["callbackSequence"]
    trace["markerHitCount"] = _state["markerHitCount"]
    trace["rejectedMarkerHitCount"] = _state["rejectedMarkerHitCount"]
    trace["discardedMarkerHitCount"] = _state["discardedMarkerHitCount"]
    trace["finalMarkerRecordCount"] = len(trace["liveArmMarkerRecords"])
    trace["finalSelectedMarkerRecordCount"] = sum(
        record.get("selectedSource") is True
        for record in trace["liveArmMarkerRecords"]
    )
    trace["rawWatchpointHitCount"] = _state["rawWatchpointHitCount"]
    trace["ignoredWatchpointHitCount"] = _state["ignoredWatchpointHitCount"]
    trace["ignoredPrepareFrameSeenCount"] = _state[
        "ignoredPrepareFrameSeenCount"
    ]
    trace["unretainedIgnoredWatchpointHitCount"] = _state[
        "unretainedIgnoredWatchpointHitCount"
    ]
    trace["qualifiedWatchpointHitCount"] = _state[
        "qualifiedWatchpointHitCount"
    ]
    trace["finalQualifiedWatchpointEventCount"] = len(
        trace["qualifiedWatchpointEvents"]
    )
    trace["finalChangedQualifiedWatchpointEventCount"] = sum(
        event.get("valueChanged") is True
        for event in trace["qualifiedWatchpointEvents"]
    )
    _write_trace()


def __lldb_init_module(debugger, _internal_dict):
    """Install pending exact-name breakpoints for source and prepare-layer."""
    _state["debugger"] = debugger
    _state["trace"] = _new_trace()
    capture_base._state = _state
    target = debugger.GetSelectedTarget()
    capture = target.BreakpointCreateByName(capture_base.CAPTURE_BACKDROP_SYMBOL)
    if not capture.IsValid():
        _failure("initialization", "capture_backdrop breakpoint is invalid")
        return
    _set_callback(capture, "capture_backdrop_entry", "capture_backdrop entry")
    prepare = target.BreakpointCreateByName(capture_base.PREPARE_LAYER_FUNCTION)
    if not prepare.IsValid():
        _failure("initialization", "prepare_layer breakpoint is invalid")
        return
    _set_callback(prepare, "prepare_layer_entry", "prepare_layer entry")
    _state["captureEntryBreakpoint"] = capture
    _state["prepareEntryBreakpoint"] = prepare
    _state["trace"]["captureBackdropEntryBreakpointID"] = capture.GetID()
    _state["trace"]["prepareLayerEntryBreakpointID"] = prepare.GetID()
    _write_trace()
