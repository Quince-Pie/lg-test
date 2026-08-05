"""Capture the final ``prepare_layer`` crop state for every timeline replay.

The prior instruction trace opened the exact marker at ``prepare_layer+0x3ef0``
and proved that the relevant backdrop invocation has exactly four structural
``prepare_layer`` frames.  This probe keeps only that already-opened marker. It
records one complete role snapshot for every normal transition-background
CARenderer replay, without selecting records from their eventual crop values.

This module is imported by LLDB's macOS system Python, so it deliberately uses
syntax supported by that runtime rather than the repository's Python 3.14
analysis baseline.
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
import capture_prepare_layer_full_path_trace_lldb as capture_base  # noqa: E402


TRACE_SCHEMA_VERSION = 1
PREPARE_LAYER_FULL_CODE_SHA256 = (
    "fe58001369708e0276599f26865be03fdf1dd2348524f92a72c1427be8d1817c"
)
MARKER_NAME = "sourceLaterHandle"
MARKER_OFFSET = 0x3EF0
MARKER_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = "28330b91"
REQUIRED_PREPARE_RECURSION_DEPTHS = (3, 4)
EXPECTED_NORMAL_PREPARE_RECURSION_DEPTHS = (3,) + (4,) * 31
MAXIMUM_MARKER_HIT_COUNT = 4096
MAXIMUM_QUALIFIED_RECORD_COUNT = 128
MAXIMUM_REJECTION_GROUP_COUNT = 64
ROLE_STATE_BYTE_COUNT = 0x800
SOURCE_STATE_BYTE_COUNT = 0x180
STACK_STATE_BYTE_COUNT = 0x800
POINTER_STATE_BYTE_COUNT = 0x200
MINIMUM_POINTER_ADDRESS = 0x1_0000_0000
MAXIMUM_POINTER_ADDRESS = 0x0000_FFFF_FFFF_FFFF
GENERAL_REGISTER_NAMES = tuple("x%d" % index for index in range(30)) + (
    "sp",
    "pc",
    "cpsr",
)
POINTER_REGISTER_NAMES = (
    "x0",
    "x1",
    "x2",
    "x3",
    "x4",
    "x5",
    "x19",
    "x23",
    "x24",
    "x27",
    "x28",
)
PREPARE_FRAME_REGISTER_NAMES = ("x19", "x28", "x29", "sp", "pc")
DIRECT_TIMELINE_CALLER_FRAGMENT = "transitionBackgroundUniformEvidence("
REQUIRED_CALLER_FRAGMENTS = (
    "carendererUniformEvidence(",
    "localTransitionCARendererEvidence(",
    DIRECT_TIMELINE_CALLER_FRAGMENT,
)
EXCLUDED_CALLER_FRAGMENTS = (
    "transitionFixedStateAllocationEvidence(",
    "transitionPathIsolationAllocationEvidence(",
    "transitionMatrixUniformBasisEvidence(",
)
TRACE_OUTPUT_ENVIRONMENT = "LG_PREPARE_LAYER_CROP_TRANSFER_TRACE_OUTPUT"
DEFAULT_TRACE_OUTPUT = (
    "transition-introspection/prepare-layer-crop-transfer-trace.json"
)


def _fresh_state():
    return {
        "debugger": None,
        "trace": None,
        "prepareEntryBreakpoint": None,
        "markerBreakpoint": None,
        "prepareLayer": None,
        "callbackSequence": 0,
        "markerHitCount": 0,
        "qualifiedRecordCount": 0,
        "rejectedMarkerCount": 0,
        "discardedQualifiedRecordCount": 0,
        "rejectionGroups": {},
        "unretainedRejectionCount": 0,
    }


_state = _fresh_state()


def _reset_state():
    _state.clear()
    _state.update(_fresh_state())


def _trace_path():
    return Path(os.environ.get(TRACE_OUTPUT_ENVIRONMENT, DEFAULT_TRACE_OUTPUT))


def _expected_configuration():
    return {
        "prepareLayerFunction": capture_base.PREPARE_LAYER_FUNCTION,
        "prepareLayerSymbolByteCount": capture_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
        "prepareLayerFullCodeSHA256": PREPARE_LAYER_FULL_CODE_SHA256,
        "knownPrepareLayerWindows": [
            {"offset": offset, "byteCount": count, "sha256": digest}
            for offset, count, digest in capture_base.KNOWN_PREPARE_LAYER_WINDOWS
        ],
        "markerName": MARKER_NAME,
        "markerOffset": MARKER_OFFSET,
        "markerInstructionRawLittleEndianHex": (
            MARKER_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
        ),
        "requiredPrepareRecursionDepths": list(REQUIRED_PREPARE_RECURSION_DEPTHS),
        "expectedNormalPrepareRecursionDepths": list(
            EXPECTED_NORMAL_PREPARE_RECURSION_DEPTHS
        ),
        "maximumMarkerHitCount": MAXIMUM_MARKER_HIT_COUNT,
        "maximumQualifiedRecordCount": MAXIMUM_QUALIFIED_RECORD_COUNT,
        "maximumRejectionGroupCount": MAXIMUM_REJECTION_GROUP_COUNT,
        "maximumBacktraceFrameCount": capture_base.MAXIMUM_BACKTRACE_FRAME_COUNT,
        "roleStateByteCount": ROLE_STATE_BYTE_COUNT,
        "sourceStateByteCount": SOURCE_STATE_BYTE_COUNT,
        "stackStateByteCount": STACK_STATE_BYTE_COUNT,
        "pointerStateByteCount": POINTER_STATE_BYTE_COUNT,
        "pointerAddressRange": [MINIMUM_POINTER_ADDRESS, MAXIMUM_POINTER_ADDRESS],
        "generalRegisterNames": list(GENERAL_REGISTER_NAMES),
        "pointerRegisterNames": list(POINTER_REGISTER_NAMES),
        "prepareFrameRegisterNames": list(PREPARE_FRAME_REGISTER_NAMES),
        "requiredCallerFragments": list(REQUIRED_CALLER_FRAGMENTS),
        "excludedCallerFragments": list(EXCLUDED_CALLER_FRAGMENTS),
        "selectionRule": (
            "retain every exact prepare_layer+0x3ef0 stop whose backtrace has "
            "exactly three or four structural prepare_layer frames and the "
            "direct normal "
            "transitionBackgroundUniformEvidence -> localTransitionCARendererEvidence "
            "-> carendererUniformEvidence caller chain, excluding every matrix, "
            "fixed-state, and path-isolation intervention caller; never inspect "
            "crop bytes when selecting"
        ),
        "ordinalJoinRule": (
            "qualified marker records in callback order join one-to-one to "
            "dynamicBackgroundUniforms.records in array order; duplicate or "
            "missing records fail validation"
        ),
        "hardwareWatchpointsUsed": False,
    }


def _new_trace():
    return {
        "prepareLayerCropTransferTraceSchemaVersion": TRACE_SCHEMA_VERSION,
        "classification": (
            "prospective-multi-state-public-layer-to-private-crop-discovery; "
            "selection-is-structural-and-crop-value-independent; general-law-"
            "holdout-production-shader-change-and-parity-remain-sealed"
        ),
        "status": "initialized",
        "configuration": _expected_configuration(),
        "prepareLayer": {},
        "callbackOrder": [],
        "qualifiedRecords": [],
        "rejectionGroups": [],
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


def _next_sequence(kind):
    _state["callbackSequence"] += 1
    sequence = _state["callbackSequence"]
    _state["trace"]["callbackOrder"].append(
        {"sequence": sequence, "kind": str(kind)}
    )
    return sequence


def _failure(stage, error):
    _state["trace"]["failures"].append(
        {"stage": str(stage), "message": str(error)}
    )
    _write_trace()


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


def _exact_prepare_frames(thread):
    """Return structural prepare frames without consulting crop values."""
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
        frame_pointer = candidate.GetFP()
        if frame_pointer in (0, lldb.LLDB_INVALID_ADDRESS):
            frame_pointer = None
        records.append(
            {
                "frame": candidate,
                "frameIndex": index,
                "framePointer": frame_pointer,
            }
        )
    return records


def _backtrace_functions(backtrace):
    return [
        record.get("function") or ""
        for record in backtrace
    ]


def _direct_timeline_caller(functions):
    joined = "\n".join(functions)
    return (
        all(fragment in joined for fragment in REQUIRED_CALLER_FRAGMENTS)
        and not any(fragment in joined for fragment in EXCLUDED_CALLER_FRAGMENTS)
    )


def _rejection(frame, reason, depth, functions):
    _state["rejectedMarkerCount"] += 1
    key = (str(reason), int(depth))
    groups = _state["rejectionGroups"]
    if key in groups:
        groups[key]["hitCount"] += 1
        return
    if len(groups) >= MAXIMUM_REJECTION_GROUP_COUNT:
        _state["unretainedRejectionCount"] += 1
        return
    groups[key] = {
        "reason": str(reason),
        "prepareRecursionDepth": int(depth),
        "hitCount": 1,
        "firstThreadID": frame.GetThread().GetThreadID(),
        "firstPC": frame.GetPC(),
        "firstFunctionInventory": functions,
    }


def _register_values(records):
    return {
        record["name"]: record.get("unsignedValue")
        for record in records
    }


def _pointer_snapshots(process, registers):
    snapshots = []
    values = _register_values(registers)
    seen = set()
    for name in POINTER_REGISTER_NAMES:
        address = values.get(name)
        if (
            not isinstance(address, int)
            or address < MINIMUM_POINTER_ADDRESS
            or address > MAXIMUM_POINTER_ADDRESS
            or address in seen
        ):
            continue
        seen.add(address)
        payload, error = capture_base._try_read_memory(
            process, address, POINTER_STATE_BYTE_COUNT
        )
        if payload is None:
            snapshots.append(
                {
                    "register": name,
                    "address": address,
                    "readable": False,
                    "error": error,
                }
            )
            continue
        snapshots.append(
            {
                "register": name,
                "address": address,
                "readable": True,
                "byteCount": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "hex": payload.hex(),
            }
        )
    return snapshots


def _prepare_frame_snapshot(process, target, item):
    frame = item["frame"]
    registers = capture_base._register_snapshot(
        frame, PREPARE_FRAME_REGISTER_NAMES
    )
    values = _register_values(registers)
    role_base = values["x19"]
    role = capture_base._memory_snapshot(
        process,
        role_base,
        ROLE_STATE_BYTE_COUNT,
        "prepare ancestor role state",
    )
    return {
        "frameIndex": item["frameIndex"],
        "unwindFramePointer": item["framePointer"],
        "frame": capture_base._frame_record(frame, target),
        "registers": registers,
        "roleState": role,
    }


def prepare_layer_entry(frame, breakpoint_location, _internal_dict):
    """Validate the opened function and install the one fixed marker."""
    try:
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        symbol = frame.GetSymbol()
        if not symbol.IsValid():
            raise RuntimeError("prepare_layer symbol is invalid")
        start = symbol.GetStartAddress().GetLoadAddress(target)
        end = symbol.GetEndAddress().GetLoadAddress(target)
        location = breakpoint_location.GetAddress().GetLoadAddress(target)
        if (
            frame.GetFunctionName() != capture_base.PREPARE_LAYER_FUNCTION
            or start == lldb.LLDB_INVALID_ADDRESS
            or end == lldb.LLDB_INVALID_ADDRESS
            or frame.GetPC() != start
            or location != start
            or end - start != capture_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        ):
            raise RuntimeError("prepare_layer exact entry differs")
        code = capture_base._read_memory(
            process,
            start,
            capture_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "complete prepare_layer code",
        )
        digest = hashlib.sha256(code).hexdigest()
        if digest != PREPARE_LAYER_FULL_CODE_SHA256:
            raise RuntimeError("complete prepare_layer SHA-256 differs")
        for offset, count, expected in capture_base.KNOWN_PREPARE_LAYER_WINDOWS:
            observed = hashlib.sha256(code[offset : offset + count]).hexdigest()
            if observed != expected:
                raise RuntimeError("known prepare_layer window differs")
        marker_bytes = code[MARKER_OFFSET : MARKER_OFFSET + 4]
        if marker_bytes.hex() != MARKER_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX:
            raise RuntimeError("prepare_layer marker instruction differs")
        marker = _address_breakpoint(
            target,
            start + MARKER_OFFSET,
            "crop_transfer_marker",
            "crop transfer marker",
        )
        sequence = _next_sequence("prepare-layer-entry")
        _state["prepareLayer"] = {
            "callbackSequence": sequence,
            "function": capture_base.PREPARE_LAYER_FUNCTION,
            "symbolStart": start,
            "symbolEnd": end,
            "symbolByteCount": end - start,
            "fullCodeSHA256": digest,
            "module": capture_base._module_record(frame.GetModule(), target),
            "marker": {
                "name": MARKER_NAME,
                "offset": MARKER_OFFSET,
                "address": start + MARKER_OFFSET,
                "instructionRawLittleEndianHex": marker_bytes.hex(),
                "breakpointID": marker.GetID(),
            },
        }
        _state["trace"]["prepareLayer"] = _state["prepareLayer"]
        _state["markerBreakpoint"] = marker
        _state["prepareEntryBreakpoint"].SetEnabled(False)
        _state["trace"]["status"] = "crop-transfer-marker-active"
        _write_trace()
    except Exception as error:
        _failure("prepare-layer-entry", error)
        if _state["prepareEntryBreakpoint"] is not None:
            _state["prepareEntryBreakpoint"].SetEnabled(False)
        if _state["markerBreakpoint"] is not None:
            _state["markerBreakpoint"].SetEnabled(False)
    return False


def crop_transfer_marker(frame, breakpoint_location, _internal_dict):
    """Retain only value-independent normal-timeline depth-three/four stops."""
    try:
        _state["markerHitCount"] += 1
        if _state["markerHitCount"] > MAXIMUM_MARKER_HIT_COUNT:
            raise RuntimeError("crop transfer marker hit bound exceeded")
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        location = breakpoint_location.GetAddress().GetLoadAddress(target)
        expected = _state["prepareLayer"]["symbolStart"] + MARKER_OFFSET
        if frame.GetPC() != expected or location != expected:
            raise RuntimeError("crop transfer marker PC differs")
        backtrace = capture_base._backtrace(frame.GetThread())
        functions = _backtrace_functions(backtrace)
        exact = _exact_prepare_frames(frame.GetThread())
        depth = len(exact)
        if not _direct_timeline_caller(functions):
            _rejection(frame, "caller-chain-excluded", depth, functions)
            return False
        if depth not in REQUIRED_PREPARE_RECURSION_DEPTHS:
            _rejection(frame, "prepare-recursion-depth-differs", depth, functions)
            return False
        if len(_state["trace"]["qualifiedRecords"]) >= MAXIMUM_QUALIFIED_RECORD_COUNT:
            _state["discardedQualifiedRecordCount"] += 1
            raise RuntimeError("qualified crop transfer record bound exceeded")
        registers = capture_base._register_snapshot(frame, GENERAL_REGISTER_NAMES)
        values = _register_values(registers)
        role_base = values["x19"]
        source = values["x28"]
        role = capture_base._memory_snapshot(
            process,
            role_base,
            ROLE_STATE_BYTE_COUNT,
            "qualified crop transfer role",
        )
        source_state = capture_base._memory_snapshot(
            process,
            source,
            SOURCE_STATE_BYTE_COUNT,
            "qualified crop transfer source",
        )
        stack = capture_base._memory_snapshot(
            process,
            values["sp"],
            STACK_STATE_BYTE_COUNT,
            "qualified crop transfer stack",
        )
        prepare_frames = [
            _prepare_frame_snapshot(process, target, item)
            for item in exact
        ]
        sequence = _next_sequence("qualified-crop-transfer-marker")
        record = {
            "recordIndex": len(_state["trace"]["qualifiedRecords"]),
            "normalRenderOrdinal": len(_state["trace"]["qualifiedRecords"]) + 1,
            "callbackSequence": sequence,
            "markerHitIndex": _state["markerHitCount"],
            "threadID": frame.GetThread().GetThreadID(),
            "pc": frame.GetPC(),
            "prepareRecursionDepth": depth,
            "frame": capture_base._frame_record(frame, target),
            "backtrace": backtrace,
            "registers": registers,
            "frameIdentity": {
                "threadID": frame.GetThread().GetThreadID(),
                "roleBase": role_base,
                "source": source,
                "framePointer": values["x29"],
            },
            "roleState": role,
            "sourceState": source_state,
            "stackState": stack,
            "pointerStates": _pointer_snapshots(process, registers),
            "prepareFrames": prepare_frames,
        }
        _state["trace"]["qualifiedRecords"].append(record)
        _state["qualifiedRecordCount"] += 1
        if _state["qualifiedRecordCount"] % 4 == 0:
            _write_trace()
    except Exception as error:
        _failure("crop-transfer-marker", error)
        if _state["markerBreakpoint"] is not None:
            _state["markerBreakpoint"].SetEnabled(False)
    return False


def finalize():
    """Seal accounting and terminal process state after ``run`` returns."""
    trace = _state["trace"]
    if trace is None:
        return
    trace["statusBeforeFinalization"] = trace["status"]
    trace["status"] = "finalized"
    trace["finalCallbackSequence"] = _state["callbackSequence"]
    trace["finalMarkerHitCount"] = _state["markerHitCount"]
    trace["finalQualifiedRecordCount"] = len(trace["qualifiedRecords"])
    trace["finalRejectedMarkerCount"] = _state["rejectedMarkerCount"]
    trace["finalDiscardedQualifiedRecordCount"] = (
        _state["discardedQualifiedRecordCount"]
    )
    trace["finalUnretainedRejectionCount"] = _state["unretainedRejectionCount"]
    trace["rejectionGroups"] = sorted(
        _state["rejectionGroups"].values(),
        key=lambda item: (item["reason"], item["prepareRecursionDepth"]),
    )
    trace["finalFailureCount"] = len(trace["failures"])
    debugger = _state["debugger"]
    if debugger is not None:
        process = debugger.GetSelectedTarget().GetProcess()
        trace["terminalProcess"] = {
            "state": process.GetState(),
            "exited": process.GetState() == lldb.eStateExited,
            "detached": process.GetState() == lldb.eStateDetached,
            "exitStatus": (
                process.GetExitStatus()
                if process.GetState() == lldb.eStateExited
                else None
            ),
        }
    _write_trace()


def __lldb_init_module(debugger, _internal_dict):
    """Install one pending exact-name breakpoint before target launch."""
    _reset_state()
    _state["debugger"] = debugger
    _state["trace"] = _new_trace()
    target = debugger.GetSelectedTarget()
    prepare = target.BreakpointCreateByName(capture_base.PREPARE_LAYER_FUNCTION)
    if not prepare.IsValid():
        _failure("initialization", "prepare_layer breakpoint is invalid")
        return
    _set_callback(prepare, "prepare_layer_entry", "prepare_layer entry")
    _state["prepareEntryBreakpoint"] = prepare
    _state["trace"]["prepareLayerEntryBreakpointID"] = prepare.GetID()
    _write_trace()
