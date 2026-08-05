"""Trace every write to the selected-depth live ``prepare_layer`` aggregate.

The sampled-site run closed one frame's final bytes but proved that its helper
callbacks were not a complete causal writer list.  This successor keeps the
independent object selection and sampled trace, while four aligned hardware
watchpoints cover all 32 aggregate bytes only during the evidence-selected
recursion-depth-four frame.  The watches are retired with that live frame.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

import lldb


ANALYSIS_ROOT = Path(__file__).resolve().parent
if str(ANALYSIS_ROOT) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_ROOT))
import capture_prepare_layer_frame_correlated_writer_trace_lldb as frame_base  # noqa: E402


capture_base = frame_base.capture_base

TRACE_SCHEMA_VERSION = 1
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
MINIMUM_SELECTED_CHANGED_TRANSITION_COUNT = 3
PREPARE_FRAME_REGISTER_NAMES = ("x19", "x28", "x29", "x30", "sp", "pc")
TRACE_OUTPUT_ENVIRONMENT = "LG_PREPARE_LAYER_ACTIVE_FRAME_WATCH_TRACE_OUTPUT"
DEFAULT_TRACE_OUTPUT = (
    "transition-introspection/prepare-layer-active-frame-watch-trace.json"
)


def _fresh_state():
    return {
        "debugger": None,
        "trace": None,
        "prepareEntryBreakpoint": None,
        "epochBreakpoint": None,
        "returnBreakpoint": None,
        "selectionBreakpoint": None,
        "prepareLayer": None,
        "callbackSequence": 0,
        "epochMarkerHitCount": 0,
        "rejectedEpochDepthCount": 0,
        "sourceUnknownEpochCount": 0,
        "discardedEpochRecordCount": 0,
        "returnMarkerHitCount": 0,
        "selectionMarkerHitCount": 0,
        "rejectedSelectionMarkerHitCount": 0,
        "rawWatchpointHitCount": 0,
        "qualifiedWatchpointHitCount": 0,
        "ignoredWatchpointHitCount": 0,
        "unretainedIgnoredWatchpointHitCount": 0,
        "ignoredWatchpointGroups": {},
        "activeGroup": None,
        "watchSpecByID": {},
    }


_state = _fresh_state()


def _reset_state():
    _state.clear()
    _state.update(_fresh_state())


def _trace_path():
    return Path(os.environ.get(TRACE_OUTPUT_ENVIRONMENT, DEFAULT_TRACE_OUTPUT))


def _new_trace():
    return {
        "prepareLayerActiveFrameWatchTraceSchemaVersion": TRACE_SCHEMA_VERSION,
        "classification": (
            "preregistered-live-depth-qualified-four-lane-prepare-layer-"
            "aggregate-watch-trace; complete-causal-writer-list-semantics-"
            "public-crop-policy-unseen-transfer-and-product-parity-remain-sealed"
        ),
        "status": "initialized",
        "configuration": {
            "prepareLayerFunction": capture_base.PREPARE_LAYER_FUNCTION,
            "prepareLayerSymbolByteCount": capture_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "prepareLayerFullCodeSHA256": PREPARE_LAYER_FULL_CODE_SHA256,
            "aggregateOffset": capture_base.AGGREGATE_OFFSET,
            "aggregateByteCount": capture_base.AGGREGATE_BYTE_COUNT,
            "roleStateByteCount": capture_base.ROLE_STATE_BYTE_COUNT,
            "epochMarkerName": EPOCH_MARKER_NAME,
            "epochMarkerOffset": EPOCH_MARKER_OFFSET,
            "epochPrecedingInstructionRawLittleEndianHex": (
                EPOCH_PRECEDING_INSTRUCTION_HEX
            ),
            "returnMarkerName": RETURN_MARKER_NAME,
            "returnMarkerOffset": RETURN_MARKER_OFFSET,
            "returnMarkerInstructionRawLittleEndianHex": (
                RETURN_MARKER_INSTRUCTION_HEX
            ),
            "selectionMarkerName": SELECTION_MARKER_NAME,
            "selectionMarkerOffset": SELECTION_MARKER_OFFSET,
            "selectionMarkerInstructionRawLittleEndianHex": (
                SELECTION_MARKER_INSTRUCTION_HEX
            ),
            "targetPrepareRecursionDepth": TARGET_PREPARE_RECURSION_DEPTH,
            "watchLaneOffsets": list(WATCH_LANE_OFFSETS),
            "watchLaneByteCount": WATCH_LANE_BYTE_COUNT,
            "maximumEpochMarkerHitCount": MAXIMUM_EPOCH_MARKER_HIT_COUNT,
            "maximumEpochRecordCount": MAXIMUM_EPOCH_RECORD_COUNT,
            "maximumReturnMarkerHitCount": MAXIMUM_RETURN_MARKER_HIT_COUNT,
            "maximumSelectionMarkerHitCount": MAXIMUM_SELECTION_MARKER_HIT_COUNT,
            "maximumRawWatchpointHitCount": MAXIMUM_RAW_WATCHPOINT_HIT_COUNT,
            "maximumQualifiedWatchpointEventCount": (
                MAXIMUM_QUALIFIED_WATCHPOINT_EVENT_COUNT
            ),
            "maximumIgnoredWatchpointDiagnosticCount": (
                MAXIMUM_IGNORED_WATCHPOINT_DIAGNOSTIC_COUNT
            ),
            "minimumSelectedChangedTransitionCount": (
                MINIMUM_SELECTED_CHANGED_TRANSITION_COUNT
            ),
            "prepareFrameRegisterNames": list(PREPARE_FRAME_REGISTER_NAMES),
            "knownSampledWriterAfterOffsets": sorted(
                site["relativeToPrepareLayer"] for site in frame_base.WRITER_SITES
            ),
            "frameTraceOutputEnvironment": (
                frame_base.TRACE_OUTPUT_ENVIRONMENT
            ),
            "frameTraceSchemaVersion": frame_base.TRACE_SCHEMA_VERSION,
            "maximumBacktraceFrameCount": capture_base.MAXIMUM_BACKTRACE_FRAME_COUNT,
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
            "generalRegisterNames": list(capture_base.GENERAL_REGISTER_NAMES),
            "simdRegisterNames": list(capture_base.SIMD_REGISTER_NAMES),
            "armRule": (
                "after source selection, arm four aligned 8-byte write watches "
                "at +0xb60 only when the bounded live backtrace contains exactly "
                "four exact prepare_layer frames; identify the current frame by "
                "thread ID, x19 role base, and x29 frame pointer"
            ),
            "retirementRule": (
                "at recursive return +0x2a68, delete all four watches as soon as "
                "the watched thread/x19/x29 frame is absent from the exact live "
                "prepare_layer ancestry"
            ),
            "selectionRule": (
                "at the first +0x3ef0 frame whose x28 equals the independently "
                "selected source, require the active identity and latest epoch to "
                "match and close the contiguous full-aggregate chain at the marker"
            ),
            "callbackMultiplexingRule": (
                "reuse the inherited prepare entry, +0xb60 epoch, and +0x3ef0 "
                "selection breakpoints; at each shared address run the inherited "
                "callback first and the active-watch callback second"
            ),
        },
        "callbackOrder": [],
        "prepareLayer": {},
        "epochRecords": [],
        "watchpointGroups": [],
        "retirementRecords": [],
        "qualifiedWatchpointEvents": [],
        "ignoredWatchpointDiagnostics": [],
        "codeWindows": [],
        "selectedFrame": {},
        "selectedWriterEventIndices": [],
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
    location = breakpoint.GetLocationAtIndex(0)
    if location.GetAddress().GetLoadAddress(target) != address:
        raise RuntimeError(label + " breakpoint address differs")
    _set_callback(breakpoint, callback, label)
    return breakpoint


def _selected_source():
    return frame_base._selected_source()


def _identity(thread_id, role_base, frame_pointer):
    return {
        "threadID": thread_id,
        "roleBase": role_base,
        "framePointer": frame_pointer,
    }


def _exact_prepare_frames(thread):
    target = thread.GetProcess().GetTarget()
    start = _state["prepareLayer"]["symbolStart"]
    end = _state["prepareLayer"]["symbolEnd"]
    records = []
    for index in range(
        min(thread.GetNumFrames(), capture_base.MAXIMUM_BACKTRACE_FRAME_COUNT)
    ):
        candidate = thread.GetFrameAtIndex(index)
        if candidate.GetFunctionName() != capture_base.PREPARE_LAYER_FUNCTION:
            continue
        symbol = candidate.GetSymbol()
        if not symbol.IsValid():
            continue
        if (
            symbol.GetStartAddress().GetLoadAddress(target) != start
            or symbol.GetEndAddress().GetLoadAddress(target) != end
        ):
            continue
        try:
            registers = capture_base._register_snapshot(
                candidate, PREPARE_FRAME_REGISTER_NAMES
            )
            values = {
                item["name"]: item["unsignedValue"] for item in registers
            }
        except Exception:
            continue
        records.append(
            {
                "frame": candidate,
                "frameIndex": index,
                "registers": registers,
                "values": values,
                "identity": _identity(
                    thread.GetThreadID(), values["x19"], values["x29"]
                ),
            }
        )
    return records


def _memory_payload(process, address, byte_count, label):
    payload = capture_base._read_memory(process, address, byte_count, label)
    return payload, {
        "address": address,
        "byteCount": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "hex": payload.hex(),
    }


def _code_window(frame):
    process = frame.GetThread().GetProcess()
    pc = frame.GetPC()
    start = max(0, pc - capture_base.PC_CENTERED_CODE_WINDOW_BACKTRACK)
    payload = capture_base._read_memory(
        process,
        start,
        capture_base.PC_CENTERED_CODE_WINDOW_BYTE_COUNT,
        "active-frame writer code window",
    )
    digest = hashlib.sha256(payload).hexdigest()
    windows = _state["trace"]["codeWindows"]
    for index, item in enumerate(windows):
        if item["startAddress"] == start and item["sha256"] == digest:
            return index
    windows.append(
        {
            "startAddress": start,
            "byteCount": len(payload),
            "source": "pc-centered",
            "stopPCOffset": pc - start,
            "containsStopPC": start <= pc < start + len(payload),
            "sha256": digest,
            "hex": payload.hex(),
        }
    )
    return len(windows) - 1


def _changed_lane_offsets(before, after):
    return [
        offset
        for offset in WATCH_LANE_OFFSETS
        if before[offset : offset + WATCH_LANE_BYTE_COUNT]
        != after[offset : offset + WATCH_LANE_BYTE_COUNT]
    ]


def _delete_active_watchpoints(target):
    group = _state["activeGroup"]
    if group is None:
        return
    for watchpoint in group["watchpoints"]:
        watchpoint.SetEnabled(False)
    for watchpoint in group["watchpoints"]:
        if not target.DeleteWatchpoint(watchpoint.GetID()):
            raise RuntimeError("active frame watchpoint deletion failed")
    _state["watchSpecByID"].clear()


def _retire_active_group(reason, thread=None):
    group = _state["activeGroup"]
    if group is None:
        return
    target = (
        thread.GetProcess().GetTarget()
        if thread is not None
        else _state["debugger"].GetSelectedTarget()
    )
    _delete_active_watchpoints(target)
    sequence = _next_sequence("active-watch-group-retired")
    retirement = {
        "recordIndex": len(_state["trace"]["retirementRecords"]),
        "callbackSequence": sequence,
        "groupIndex": group["groupIndex"],
        "epochRecordIndex": group["epochRecordIndex"],
        "reason": str(reason),
        "identity": dict(group["identity"]),
        "lastAggregateHex": group["lastAggregate"].hex(),
    }
    _state["trace"]["retirementRecords"].append(retirement)
    public_group = _state["trace"]["watchpointGroups"][group["groupIndex"]]
    public_group["retiredCallbackSequence"] = sequence
    public_group["retirementReason"] = str(reason)
    public_group["lastAggregateHex"] = group["lastAggregate"].hex()
    _state["activeGroup"] = None


def _install_watch_group(frame, epoch_record, aggregate):
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    if _state["activeGroup"] is not None:
        _retire_active_group("superseded-by-next-depth-four-epoch", frame.GetThread())
    group_index = len(_state["trace"]["watchpointGroups"])
    watchpoints = []
    specs = []
    try:
        for lane_offset in WATCH_LANE_OFFSETS:
            address = (
                epoch_record["identity"]["roleBase"]
                + capture_base.AGGREGATE_OFFSET
                + lane_offset
            )
            error = lldb.SBError()
            watchpoint = target.WatchAddress(
                address, WATCH_LANE_BYTE_COUNT, False, True, error
            )
            if not error.Success() or not watchpoint.IsValid():
                raise RuntimeError(
                    "four-lane active watchpoint installation failed at lane %d: %s"
                    % (lane_offset, error.GetCString() or "invalid watchpoint")
                )
            result = lldb.SBCommandReturnObject()
            command = (
                "watchpoint command add -F %s.aggregate_lane_watchpoint %d"
                % (__name__, watchpoint.GetID())
            )
            _state["debugger"].GetCommandInterpreter().HandleCommand(command, result)
            if not result.Succeeded():
                raise RuntimeError(
                    "four-lane watchpoint callback failed: %s" % result.GetError()
                )
            spec = {
                "id": watchpoint.GetID(),
                "deprecatedHardwareIndex": watchpoint.GetHardwareIndex(),
                "laneOffset": lane_offset,
                "address": address,
                "byteCount": WATCH_LANE_BYTE_COUNT,
            }
            watchpoints.append(watchpoint)
            specs.append(spec)
        sequence = _next_sequence("active-watch-group-armed")
        public_group = {
            "groupIndex": group_index,
            "callbackSequence": sequence,
            "epochRecordIndex": epoch_record["recordIndex"],
            "identity": dict(epoch_record["identity"]),
            "initialAggregateHex": aggregate.hex(),
            "watchpoints": specs,
        }
        _state["trace"]["watchpointGroups"].append(public_group)
        active = {
            "groupIndex": group_index,
            "epochRecordIndex": epoch_record["recordIndex"],
            "identity": dict(epoch_record["identity"]),
            "lastAggregate": aggregate,
            "watchpoints": watchpoints,
        }
        _state["activeGroup"] = active
        _state["watchSpecByID"] = {
            spec["id"]: {**spec, "groupIndex": group_index}
            for spec in specs
        }
        epoch_record["watchpointGroupIndex"] = group_index
        _state["trace"]["status"] = "depth-four-active-watch-group-armed"
    except Exception:
        for watchpoint in watchpoints:
            watchpoint.SetEnabled(False)
            target.DeleteWatchpoint(watchpoint.GetID())
        _state["watchSpecByID"].clear()
        _state["activeGroup"] = None
        raise


def multiplexed_prepare_layer_entry(frame, breakpoint_location, internal_dict):
    """Run both entry callbacks on the inherited single physical breakpoint."""
    frame_base.prepare_layer_entry(frame, breakpoint_location, internal_dict)
    prepare_layer_entry(frame, breakpoint_location, internal_dict)
    return False


def multiplexed_epoch_marker(frame, breakpoint_location, internal_dict):
    """Retain the inherited sampled epoch before arming active hardware watches."""
    frame_base.writer_site(frame, breakpoint_location, internal_dict)
    prepare_layer_epoch_marker(frame, breakpoint_location, internal_dict)
    return False


def multiplexed_selection_marker(frame, breakpoint_location, internal_dict):
    """Close inherited sampling before closing the active hardware chain."""
    frame_base.live_selection_marker(frame, breakpoint_location, internal_dict)
    prepare_layer_selection_marker(frame, breakpoint_location, internal_dict)
    return False


def prepare_layer_entry(frame, breakpoint_location, _internal_dict):
    """Freeze complete code and install epoch, return, and selection markers."""
    try:
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        symbol = frame.GetSymbol()
        if not symbol.IsValid():
            raise RuntimeError("active watch prepare_layer symbol is invalid")
        start = symbol.GetStartAddress().GetLoadAddress(target)
        end = symbol.GetEndAddress().GetLoadAddress(target)
        callback_location = breakpoint_location.GetAddress().GetLoadAddress(target)
        if (
            frame.GetFunctionName() != capture_base.PREPARE_LAYER_FUNCTION
            or frame.GetPC() != start
            or callback_location != start
            or end - start != capture_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        ):
            raise RuntimeError("active watch exact prepare_layer entry differs")
        code = capture_base._read_memory(
            process,
            start,
            capture_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "active watch complete prepare_layer code",
        )
        if hashlib.sha256(code).hexdigest() != PREPARE_LAYER_FULL_CODE_SHA256:
            raise RuntimeError("active watch complete prepare_layer hash differs")
        frozen = {
            EPOCH_MARKER_OFFSET - 4: EPOCH_PRECEDING_INSTRUCTION_HEX,
            RETURN_MARKER_OFFSET: RETURN_MARKER_INSTRUCTION_HEX,
            SELECTION_MARKER_OFFSET: SELECTION_MARKER_INSTRUCTION_HEX,
        }
        if any(code[offset : offset + 4].hex() != raw for offset, raw in frozen.items()):
            raise RuntimeError("active watch marker instruction bytes differ")
        epoch = frame_base._state["writerBreakpoints"].get(EPOCH_MARKER_NAME)
        selection = frame_base._state["selectionMarkerBreakpoint"]
        if (
            epoch is None
            or not epoch.IsValid()
            or epoch.GetNumLocations() != 1
            or epoch.GetLocationAtIndex(0).GetAddress().GetLoadAddress(target)
            != start + EPOCH_MARKER_OFFSET
            or selection is None
            or not selection.IsValid()
            or selection.GetNumLocations() != 1
            or selection.GetLocationAtIndex(0).GetAddress().GetLoadAddress(target)
            != start + SELECTION_MARKER_OFFSET
        ):
            raise RuntimeError("inherited shared active watch breakpoints differ")
        _set_callback(
            epoch,
            "multiplexed_epoch_marker",
            "shared active watch zero epoch",
        )
        _set_callback(
            selection,
            "multiplexed_selection_marker",
            "shared active watch source selection",
        )
        returned = _address_breakpoint(
            target,
            start + RETURN_MARKER_OFFSET,
            "prepare_layer_return_marker",
            "active watch recursive return",
        )
        sequence = _next_sequence("prepare-layer-entry")
        prepare = {
            "callbackSequence": sequence,
            "callbackPC": frame.GetPC(),
            "callbackLocationAddress": callback_location,
            "function": capture_base.PREPARE_LAYER_FUNCTION,
            "symbolStart": start,
            "symbolEnd": end,
            "symbolByteCount": len(code),
            "fullCodeSHA256": hashlib.sha256(code).hexdigest(),
            "module": capture_base._module_record(frame.GetModule(), target),
            "epochMarker": {
                "address": start + EPOCH_MARKER_OFFSET,
                "breakpointID": epoch.GetID(),
            },
            "returnMarker": {
                "address": start + RETURN_MARKER_OFFSET,
                "breakpointID": returned.GetID(),
            },
            "selectionMarker": {
                "address": start + SELECTION_MARKER_OFFSET,
                "breakpointID": selection.GetID(),
            },
        }
        _state["prepareLayer"] = prepare
        _state["trace"]["prepareLayer"] = prepare
        _state["epochBreakpoint"] = epoch
        _state["returnBreakpoint"] = returned
        _state["selectionBreakpoint"] = selection
        _state["prepareEntryBreakpoint"].SetEnabled(False)
        _state["trace"]["status"] = "active-watch-markers-installed"
        _write_trace()
    except Exception as error:
        _failure("prepare-layer-entry", error)
        if _state["prepareEntryBreakpoint"] is not None:
            _state["prepareEntryBreakpoint"].SetEnabled(False)
    return False


def prepare_layer_epoch_marker(frame, _breakpoint_location, _internal_dict):
    """Arm full aggregate coverage only on the proven recursion-depth-four frame."""
    try:
        _state["epochMarkerHitCount"] += 1
        if _state["epochMarkerHitCount"] > MAXIMUM_EPOCH_MARKER_HIT_COUNT:
            raise RuntimeError("active watch epoch marker hit bound exceeded")
        source = _selected_source()
        if source is None:
            _state["sourceUnknownEpochCount"] += 1
            return False
        exact = _exact_prepare_frames(frame.GetThread())
        if len(exact) != TARGET_PREPARE_RECURSION_DEPTH or exact[0]["frameIndex"] != 0:
            _state["rejectedEpochDepthCount"] += 1
            return False
        records = _state["trace"]["epochRecords"]
        if len(records) >= MAXIMUM_EPOCH_RECORD_COUNT:
            _state["discardedEpochRecordCount"] += 1
            raise RuntimeError("active watch epoch record bound exceeded")
        process = frame.GetThread().GetProcess()
        identity = exact[0]["identity"]
        role, role_record = _memory_payload(
            process,
            identity["roleBase"],
            capture_base.ROLE_STATE_BYTE_COUNT,
            "active watch epoch role state",
        )
        aggregate = role[
            capture_base.AGGREGATE_OFFSET : capture_base.AGGREGATE_OFFSET
            + capture_base.AGGREGATE_BYTE_COUNT
        ]
        sequence = _next_sequence("depth-four-zero-epoch")
        record = {
            "recordIndex": len(records),
            "callbackSequence": sequence,
            "markerHitIndex": _state["epochMarkerHitCount"],
            "threadID": frame.GetThread().GetThreadID(),
            "pc": frame.GetPC(),
            "frame": capture_base._frame_record(frame, process.GetTarget()),
            "backtrace": capture_base._backtrace(frame.GetThread()),
            "prepareRecursionDepth": len(exact),
            "prepareFrames": [
                {
                    "frameIndex": item["frameIndex"],
                    "frame": capture_base._frame_record(
                        item["frame"], process.GetTarget()
                    ),
                    "registers": item["registers"],
                    "identity": item["identity"],
                }
                for item in exact
            ],
            "identity": identity,
            "selectedSourceKnown": source,
            "roleStateAtEpoch": role_record,
            "aggregateAtEpochHex": aggregate.hex(),
        }
        records.append(record)
        _install_watch_group(frame, record, aggregate)
        _write_trace()
    except Exception as error:
        _failure("depth-four-zero-epoch", error)
        if _state["epochBreakpoint"] is not None:
            _state["epochBreakpoint"].SetEnabled(False)
    return False


def _matching_identity(exact, identity):
    for ordinal, item in enumerate(exact):
        if item["identity"] == identity:
            return ordinal, item
    return None, None


def _record_ignored_watchpoint(frame, spec, before, after, exact):
    _state["ignoredWatchpointHitCount"] += 1
    key = (
        spec["groupIndex"],
        spec["laneOffset"],
        frame.GetPC(),
        frame.GetFunctionName() or "",
        len(exact),
    )
    groups = _state["ignoredWatchpointGroups"]
    group = groups.get(key)
    if group is not None:
        group["hitCount"] += 1
        group["changedCount"] += before != after
        group["lastAfterHex"] = after.hex()
    elif len(groups) < MAXIMUM_IGNORED_WATCHPOINT_DIAGNOSTIC_COUNT:
        groups[key] = {
            "groupIndex": spec["groupIndex"],
            "laneOffset": spec["laneOffset"],
            "stopPC": frame.GetPC(),
            "function": frame.GetFunctionName() or "",
            "exactPrepareFrameCount": len(exact),
            "hitCount": 1,
            "changedCount": int(before != after),
            "firstBeforeHex": before.hex(),
            "lastAfterHex": after.hex(),
        }
    else:
        _state["unretainedIgnoredWatchpointHitCount"] += 1


def aggregate_lane_watchpoint(frame, watchpoint, _internal_dict):
    """Capture one hardware stop and retain it only for the active live identity."""
    try:
        spec = _state["watchSpecByID"].get(watchpoint.GetID())
        group = _state["activeGroup"]
        if spec is None or group is None or spec["groupIndex"] != group["groupIndex"]:
            raise RuntimeError("active lane watchpoint identity differs")
        _state["rawWatchpointHitCount"] += 1
        if _state["rawWatchpointHitCount"] > MAXIMUM_RAW_WATCHPOINT_HIT_COUNT:
            raise RuntimeError("active lane raw watchpoint hit bound exceeded")
        process = frame.GetThread().GetProcess()
        aggregate_address = (
            group["identity"]["roleBase"] + capture_base.AGGREGATE_OFFSET
        )
        after = capture_base._read_memory(
            process,
            aggregate_address,
            capture_base.AGGREGATE_BYTE_COUNT,
            "active lane full aggregate after write",
        )
        before = group["lastAggregate"]
        group["lastAggregate"] = after
        exact = _exact_prepare_frames(frame.GetThread())
        ordinal, prepare = _matching_identity(exact, group["identity"])
        if prepare is None:
            _record_ignored_watchpoint(frame, spec, before, after, exact)
            return False
        _state["qualifiedWatchpointHitCount"] += 1
        if (
            _state["qualifiedWatchpointHitCount"]
            > MAXIMUM_QUALIFIED_WATCHPOINT_EVENT_COUNT
        ):
            raise RuntimeError("active lane qualified event bound exceeded")
        changed_lanes = _changed_lane_offsets(before, after)
        sequence = _next_sequence("qualified-active-frame-watchpoint-hit")
        role, role_record = _memory_payload(
            process,
            group["identity"]["roleBase"],
            capture_base.ROLE_STATE_BYTE_COUNT,
            "active frame role state after writer",
        )
        aggregate_alias = role[
            capture_base.AGGREGATE_OFFSET : capture_base.AGGREGATE_OFFSET
            + capture_base.AGGREGATE_BYTE_COUNT
        ]
        if aggregate_alias != after:
            raise RuntimeError("active lane aggregate and role alias differ")
        changed = before != after
        event = {
            "eventIndex": len(_state["trace"]["qualifiedWatchpointEvents"]),
            "callbackSequence": sequence,
            "groupIndex": group["groupIndex"],
            "epochRecordIndex": group["epochRecordIndex"],
            "watchpointID": watchpoint.GetID(),
            "triggeredLaneOffset": spec["laneOffset"],
            "threadID": frame.GetThread().GetThreadID(),
            "stopPC": frame.GetPC(),
            "watchedAddress": spec["address"],
            "aggregateAddress": aggregate_address,
            "beforeHex": before.hex(),
            "afterHex": after.hex(),
            "valueChanged": changed,
            "changedLaneOffsets": changed_lanes,
            "frame": capture_base._frame_record(frame, process.GetTarget()),
            "backtrace": capture_base._backtrace(frame.GetThread()),
            "prepareFrameOrdinal": ordinal,
            "prepareFrameCount": len(exact),
            "prepareFrameIndex": prepare["frameIndex"],
            "prepareFrame": capture_base._frame_record(
                prepare["frame"], process.GetTarget()
            ),
            "prepareFrameRegisters": prepare["registers"],
            "frameIdentity": dict(group["identity"]),
            "roleStateAfter": role_record,
            "codeWindowIndex": _code_window(frame),
        }
        if changed:
            event["privateFieldsAfter"] = capture_base._snapshot_private_fields(
                process
            )
            event["operandSnapshot"] = capture_base._operand_snapshot(frame)
        _state["trace"]["qualifiedWatchpointEvents"].append(event)
        _state["trace"]["status"] = "qualified-active-frame-writer-captured"
        if changed or sequence % 32 == 0:
            _write_trace()
    except Exception as error:
        _failure("qualified-active-frame-watchpoint", error)
        watchpoint.SetEnabled(False)
    return False


def prepare_layer_return_marker(frame, _breakpoint_location, _internal_dict):
    """Retire watches immediately after the watched recursive frame returns."""
    try:
        _state["returnMarkerHitCount"] += 1
        if _state["returnMarkerHitCount"] > MAXIMUM_RETURN_MARKER_HIT_COUNT:
            raise RuntimeError("active watch return marker hit bound exceeded")
        group = _state["activeGroup"]
        if group is None:
            return False
        exact = _exact_prepare_frames(frame.GetThread())
        _ordinal, matched = _matching_identity(exact, group["identity"])
        if matched is None:
            _retire_active_group("watched-prepare-frame-returned", frame.GetThread())
            _state["trace"]["status"] = "active-watch-group-retired-with-frame"
            _write_trace()
    except Exception as error:
        _failure("recursive-prepare-return", error)
        if _state["returnBreakpoint"] is not None:
            _state["returnBreakpoint"].SetEnabled(False)
    return False


def prepare_layer_selection_marker(frame, _breakpoint_location, _internal_dict):
    """Close the current hardware-observed epoch at the exact-source marker."""
    try:
        _state["selectionMarkerHitCount"] += 1
        if _state["selectionMarkerHitCount"] > MAXIMUM_SELECTION_MARKER_HIT_COUNT:
            raise RuntimeError("active watch selection marker hit bound exceeded")
        source = _selected_source()
        x28 = capture_base._register(frame, "x28")
        if source is None or x28 != source:
            _state["rejectedSelectionMarkerHitCount"] += 1
            return False
        exact = _exact_prepare_frames(frame.GetThread())
        if len(exact) != TARGET_PREPARE_RECURSION_DEPTH or exact[0]["frameIndex"] != 0:
            _state["rejectedSelectionMarkerHitCount"] += 1
            return False
        identity = exact[0]["identity"]
        group = _state["activeGroup"]
        if group is None or group["identity"] != identity:
            raise RuntimeError("selected active watch group identity differs")
        epoch = _state["trace"]["epochRecords"][group["epochRecordIndex"]]
        process = frame.GetThread().GetProcess()
        role, role_record = _memory_payload(
            process,
            identity["roleBase"],
            capture_base.ROLE_STATE_BYTE_COUNT,
            "active watch selected marker role",
        )
        aggregate = role[
            capture_base.AGGREGATE_OFFSET : capture_base.AGGREGATE_OFFSET
            + capture_base.AGGREGATE_BYTE_COUNT
        ]
        selected = [
            event["eventIndex"]
            for event in _state["trace"]["qualifiedWatchpointEvents"]
            if event["groupIndex"] == group["groupIndex"]
            and event["epochRecordIndex"] == group["epochRecordIndex"]
            and event["frameIdentity"] == identity
        ]
        if not selected:
            raise RuntimeError("selected active watch epoch has no qualified writes")
        sequence = _next_sequence("live-selected-active-frame-watch-closed")
        marker = {
            "callbackSequence": sequence,
            "markerHitIndex": _state["selectionMarkerHitCount"],
            "threadID": frame.GetThread().GetThreadID(),
            "pc": frame.GetPC(),
            "frame": capture_base._frame_record(frame, process.GetTarget()),
            "backtrace": capture_base._backtrace(frame.GetThread()),
            "registers": exact[0]["registers"],
            "prepareRecursionDepth": len(exact),
            "frameIdentity": identity,
            "selectedSource": source,
            "selectedEpochRecordIndex": epoch["recordIndex"],
            "selectedWatchpointGroupIndex": group["groupIndex"],
            "selectedWriterEventCount": len(selected),
            "roleStateAtMarker": role_record,
            "aggregateAtMarkerHex": aggregate.hex(),
            "objectChain": json.loads(
                json.dumps(frame_base._state["trace"]["objectChain"])
            ),
        }
        _state["trace"]["selectedFrame"] = marker
        _state["trace"]["selectedWriterEventIndices"] = selected
        _retire_active_group("selected-marker-closed", frame.GetThread())
        for breakpoint in (
            _state["epochBreakpoint"],
            _state["returnBreakpoint"],
            _state["selectionBreakpoint"],
        ):
            if breakpoint is not None:
                breakpoint.SetEnabled(False)
        _state["trace"]["status"] = "live-selected-active-frame-watch-closed"
        _write_trace()
    except Exception as error:
        _failure("live-selected-active-frame-watch", error)
        for breakpoint in (
            _state["epochBreakpoint"],
            _state["returnBreakpoint"],
            _state["selectionBreakpoint"],
        ):
            if breakpoint is not None:
                breakpoint.SetEnabled(False)
    return False


def finalize():
    """Finalize the reused sampled trace and exact active-watch accounting."""
    frame_base.finalize()
    trace = _state["trace"]
    if trace is None:
        return
    try:
        if _state["activeGroup"] is not None:
            _retire_active_group("target-finalization")
    except Exception as error:
        _failure("final-watchpoint-retirement", error)
    trace["ignoredWatchpointDiagnostics"] = sorted(
        _state["ignoredWatchpointGroups"].values(),
        key=lambda item: (
            item["groupIndex"],
            item["laneOffset"],
            item["stopPC"],
            item["function"],
        ),
    )
    trace["statusBeforeFinalization"] = trace["status"]
    trace["status"] = "finalized"
    trace["finalFailureCount"] = len(trace["failures"])
    trace["finalCallbackSequence"] = _state["callbackSequence"]
    trace["epochMarkerHitCount"] = _state["epochMarkerHitCount"]
    trace["rejectedEpochDepthCount"] = _state["rejectedEpochDepthCount"]
    trace["sourceUnknownEpochCount"] = _state["sourceUnknownEpochCount"]
    trace["discardedEpochRecordCount"] = _state["discardedEpochRecordCount"]
    trace["finalEpochRecordCount"] = len(trace["epochRecords"])
    trace["returnMarkerHitCount"] = _state["returnMarkerHitCount"]
    trace["selectionMarkerHitCount"] = _state["selectionMarkerHitCount"]
    trace["rejectedSelectionMarkerHitCount"] = _state[
        "rejectedSelectionMarkerHitCount"
    ]
    trace["rawWatchpointHitCount"] = _state["rawWatchpointHitCount"]
    trace["qualifiedWatchpointHitCount"] = _state[
        "qualifiedWatchpointHitCount"
    ]
    trace["ignoredWatchpointHitCount"] = _state["ignoredWatchpointHitCount"]
    trace["unretainedIgnoredWatchpointHitCount"] = _state[
        "unretainedIgnoredWatchpointHitCount"
    ]
    trace["finalQualifiedWatchpointEventCount"] = len(
        trace["qualifiedWatchpointEvents"]
    )
    trace["finalChangedQualifiedWatchpointEventCount"] = sum(
        event["valueChanged"] for event in trace["qualifiedWatchpointEvents"]
    )
    selected = trace["selectedWriterEventIndices"]
    trace["finalSelectedWriterEventCount"] = len(selected)
    trace["finalSelectedChangedTransitionCount"] = sum(
        trace["qualifiedWatchpointEvents"][index]["valueChanged"]
        for index in selected
    )
    selected_states = []
    if selected:
        epoch_index = trace["selectedFrame"]["selectedEpochRecordIndex"]
        selected_states.append(trace["epochRecords"][epoch_index]["aggregateAtEpochHex"])
        selected_states.extend(
            trace["qualifiedWatchpointEvents"][index]["afterHex"]
            for index in selected
        )
    trace["finalSelectedDistinctAggregateCount"] = len(set(selected_states))
    _write_trace()


def __lldb_init_module(debugger, internal_dict):
    """Run the immutable sampled harness and add the active-frame watch trace."""
    frame_base.__lldb_init_module(debugger, internal_dict)
    _reset_state()
    _state["debugger"] = debugger
    _state["trace"] = _new_trace()
    prepare = frame_base._state["prepareEntryBreakpoint"]
    if prepare is None or not prepare.IsValid():
        _failure(
            "initialization",
            "inherited active watch prepare_layer breakpoint is invalid",
        )
        return
    _set_callback(
        prepare,
        "multiplexed_prepare_layer_entry",
        "shared active watch prepare_layer entry",
    )
    _state["prepareEntryBreakpoint"] = prepare
    _state["trace"]["prepareLayerEntryBreakpointID"] = prepare.GetID()
    _write_trace()
