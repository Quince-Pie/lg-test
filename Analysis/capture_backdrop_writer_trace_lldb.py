"""LLDB callbacks for a bounded trace of Apple's private crop-region writers.

This module is imported by LLDB, not by the capture executable.  It first
byte-gates the exact ``capture_backdrop`` body used by the passing run, then
arms four hardware watchpoints from the live x19/x20/x24 object chain at the
already-proven late instruction.  Returning ``False`` from every callback
keeps the target running without interactive debugger input.
"""

import hashlib
import json
import os
import struct
from pathlib import Path

import lldb


TRACE_SCHEMA_VERSION = 1
CAPTURE_BACKDROP_SYMBOL = "_ZN2CA3OGL16capture_backdropERNS0_8RendererEPKNS0_5LayerE"
CAPTURE_BACKDROP_CODE_BYTE_COUNT = 0x4000
CAPTURE_BACKDROP_CODE_SHA256 = (
    "14f25960556bec9e88ba8ade176ee7f1d39b84726226ade3eb1b0f1be00b70d2"
)
CAPTURE_BACKDROP_LATE_OFFSET = 0x2B58
WATCHPOINT_BYTE_COUNT = 8
MAXIMUM_HITS_PER_WATCHPOINT = 6
MAXIMUM_TOTAL_HITS = 24
MAXIMUM_BACKTRACE_FRAME_COUNT = 32
SYMBOL_CODE_WINDOW_BYTE_COUNT = 0x1000
FALLBACK_CODE_WINDOW_BYTE_COUNT = 0x400
FALLBACK_CODE_WINDOW_BACKTRACK = 0x200
TRACE_OUTPUT_ENVIRONMENT = "LG_CAPTURE_BACKDROP_WRITER_TRACE_OUTPUT"
DEFAULT_TRACE_OUTPUT = "transition-introspection/capture-backdrop-writer-trace.json"
WATCH_SPECS = (
    ("sourceSelectedRectI32", "source", 0x50),
    ("ownerSelectedRectF64", "owner", 0xE0),
    ("ownerRegion248Handle", "owner", 0x248),
    ("layerStateSelectedRectI32", "layerState", 0xB0),
)


_state = {
    "debugger": None,
    "entryBreakpoint": None,
    "lateBreakpoint": None,
    "objectAddresses": {},
    "watchpoints": {},
    "lastValues": {},
    "trace": None,
}


def _trace_path():
    return Path(os.environ.get(TRACE_OUTPUT_ENVIRONMENT, DEFAULT_TRACE_OUTPUT))


def _new_trace():
    return {
        "captureBackdropWriterTraceSchemaVersion": TRACE_SCHEMA_VERSION,
        "classification": (
            "preregistered-bounded-lldb-hardware-watchpoint-trace-of-private-"
            "crop-writers; not-a-public-crop-law-unseen-transfer-or-product-"
            "parity-claim"
        ),
        "status": "initialized",
        "configuration": {
            "captureBackdropSymbol": CAPTURE_BACKDROP_SYMBOL,
            "captureBackdropCodeByteCount": CAPTURE_BACKDROP_CODE_BYTE_COUNT,
            "captureBackdropCodeSHA256": CAPTURE_BACKDROP_CODE_SHA256,
            "lateInstructionOffset": CAPTURE_BACKDROP_LATE_OFFSET,
            "watchpointByteCount": WATCHPOINT_BYTE_COUNT,
            "maximumHitsPerWatchpoint": MAXIMUM_HITS_PER_WATCHPOINT,
            "maximumTotalHits": MAXIMUM_TOTAL_HITS,
            "maximumBacktraceFrameCount": MAXIMUM_BACKTRACE_FRAME_COUNT,
            "symbolCodeWindowByteCount": SYMBOL_CODE_WINDOW_BYTE_COUNT,
            "fallbackCodeWindowByteCount": FALLBACK_CODE_WINDOW_BYTE_COUNT,
            "watchSpecs": [
                {"name": name, "base": base, "offset": offset}
                for name, base, offset in WATCH_SPECS
            ],
        },
        "captureBackdrop": {},
        "objectChain": {},
        "watchpoints": [],
        "codeWindows": [],
        "events": [],
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


def _failure(stage, message):
    _state["trace"]["failures"].append({"stage": str(stage), "message": str(message)})
    _write_trace()


def _read_memory(process, address, byte_count, label):
    error = lldb.SBError()
    payload = process.ReadMemory(address, byte_count, error)
    if not error.Success() or payload is None or len(payload) != byte_count:
        detail = error.GetCString() or "partial memory read"
        raise RuntimeError("%s at 0x%016x failed: %s" % (label, address, detail))
    return bytes(payload)


def _read_u64(process, address, label):
    return struct.unpack("<Q", _read_memory(process, address, 8, label))[0]


def _register(frame, name):
    value = frame.FindRegister(name)
    if not value.IsValid():
        raise RuntimeError("missing register %s" % name)
    return value.GetValueAsUnsigned(0)


def _file_spec_path(file_spec):
    """Use the SBFileSpec API shared by Apple's and upstream LLDB bindings."""
    directory = file_spec.GetDirectory()
    filename = file_spec.GetFilename()
    if directory and filename:
        return str(Path(directory) / filename)
    if filename:
        return str(filename)
    if directory:
        return str(directory)
    return ""


def _module_record(module, target):
    if not module.IsValid():
        return {"valid": False}
    header = module.GetObjectFileHeaderAddress().GetLoadAddress(target)
    return {
        "valid": True,
        "path": _file_spec_path(module.GetFileSpec()),
        "loadAddress": None if header == lldb.LLDB_INVALID_ADDRESS else header,
    }


def _frame_record(frame, target):
    pc = frame.GetPC()
    symbol = frame.GetSymbol()
    symbol_start = lldb.LLDB_INVALID_ADDRESS
    symbol_end = lldb.LLDB_INVALID_ADDRESS
    if symbol.IsValid():
        symbol_start = symbol.GetStartAddress().GetLoadAddress(target)
        symbol_end = symbol.GetEndAddress().GetLoadAddress(target)
    return {
        "frameIndex": frame.GetFrameID(),
        "pc": pc,
        "function": frame.GetFunctionName(),
        "symbolStart": (
            None if symbol_start == lldb.LLDB_INVALID_ADDRESS else symbol_start
        ),
        "symbolEnd": (None if symbol_end == lldb.LLDB_INVALID_ADDRESS else symbol_end),
        "symbolOffset": (
            None
            if symbol_start == lldb.LLDB_INVALID_ADDRESS or pc < symbol_start
            else pc - symbol_start
        ),
        "module": _module_record(frame.GetModule(), target),
    }


def _backtrace(thread):
    target = thread.GetProcess().GetTarget()
    count = min(thread.GetNumFrames(), MAXIMUM_BACKTRACE_FRAME_COUNT)
    return [
        _frame_record(thread.GetFrameAtIndex(index), target) for index in range(count)
    ]


def _snapshot_private_fields(process):
    addresses = _state["objectAddresses"]
    source = addresses["source"]
    owner = addresses["owner"]
    layer_state = addresses["layerState"]
    return {
        "layerStateInputBoundsI32": list(
            struct.unpack(
                "<4i",
                _read_memory(
                    process,
                    layer_state + 0xA0,
                    16,
                    "layer-state input bounds",
                ),
            )
        ),
        "layerStateSelectedRectI32": list(
            struct.unpack(
                "<4i",
                _read_memory(
                    process,
                    layer_state + 0xB0,
                    16,
                    "layer-state selected rectangle",
                ),
            )
        ),
        "sourceSelectedRectI32": list(
            struct.unpack(
                "<4i",
                _read_memory(
                    process,
                    source + 0x50,
                    16,
                    "source selected rectangle",
                ),
            )
        ),
        "ownerSelectedRectF64": list(
            struct.unpack(
                "<4d",
                _read_memory(
                    process,
                    owner + 0xE0,
                    32,
                    "owner selected rectangle",
                ),
            )
        ),
        "ownerRegion248Handle": _read_u64(
            process, owner + 0x248, "owner +0x248 region"
        ),
        "ownerRegion270Handle": _read_u64(
            process, owner + 0x270, "owner +0x270 region"
        ),
    }


def _code_window(frame):
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    pc = frame.GetPC()
    symbol = frame.GetSymbol()
    start = lldb.LLDB_INVALID_ADDRESS
    if symbol.IsValid():
        start = symbol.GetStartAddress().GetLoadAddress(target)
    if start == lldb.LLDB_INVALID_ADDRESS or start > pc:
        start = max(0, pc - FALLBACK_CODE_WINDOW_BACKTRACK)
        byte_count = FALLBACK_CODE_WINDOW_BYTE_COUNT
        source = "pc-centered fallback"
    else:
        byte_count = SYMBOL_CODE_WINDOW_BYTE_COUNT
        source = "resolved symbol start"
    payload = _read_memory(process, start, byte_count, "writer code window")
    key = (start, hashlib.sha256(payload).hexdigest())
    windows = _state["trace"]["codeWindows"]
    for index, item in enumerate(windows):
        if (item["startAddress"], item["sha256"]) == key:
            return index
    windows.append(
        {
            "startAddress": start,
            "byteCount": byte_count,
            "source": source,
            "sha256": key[1],
            "hex": payload.hex(),
        }
    )
    return len(windows) - 1


def capture_backdrop_entry(frame, _breakpoint_location, _internal_dict):
    """Gate the Apple code and place the one-shot late-state breakpoint."""
    try:
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        symbol_address = frame.GetPC()
        code = _read_memory(
            process,
            symbol_address,
            CAPTURE_BACKDROP_CODE_BYTE_COUNT,
            "capture_backdrop code",
        )
        digest = hashlib.sha256(code).hexdigest()
        _state["trace"]["captureBackdrop"] = {
            "symbolAddress": symbol_address,
            "codeByteCount": len(code),
            "codeSHA256": digest,
            "module": _module_record(frame.GetModule(), target),
        }
        if digest != CAPTURE_BACKDROP_CODE_SHA256:
            raise RuntimeError("capture_backdrop code SHA-256 differs")
        late = target.BreakpointCreateByAddress(
            symbol_address + CAPTURE_BACKDROP_LATE_OFFSET
        )
        if not late.IsValid() or late.GetNumLocations() != 1:
            raise RuntimeError("late capture_backdrop breakpoint is unresolved")
        error = late.SetScriptCallbackFunction(__name__ + ".capture_backdrop_late")
        if error is not None and hasattr(error, "Success") and not error.Success():
            raise RuntimeError(error.GetCString() or "late callback rejected")
        _state["lateBreakpoint"] = late
        _state["entryBreakpoint"].SetEnabled(False)
        _state["trace"]["status"] = "late-breakpoint-armed"
        _write_trace()
    except Exception as error:  # LLDB must retain the failure as evidence.
        _failure("capture_backdrop-entry", error)
        if _state["entryBreakpoint"] is not None:
            _state["entryBreakpoint"].SetEnabled(False)
    return False


def _install_watchpoint(target, name, address):
    error = lldb.SBError()
    watchpoint = target.WatchAddress(
        address,
        WATCHPOINT_BYTE_COUNT,
        False,
        True,
        error,
    )
    if not error.Success() or not watchpoint.IsValid():
        raise RuntimeError(
            "%s watchpoint failed: %s"
            % (name, error.GetCString() or "invalid watchpoint")
        )
    result = lldb.SBCommandReturnObject()
    command = "watchpoint command add -F %s.capture_writer_watchpoint %d" % (
        __name__,
        watchpoint.GetID(),
    )
    _state["debugger"].GetCommandInterpreter().HandleCommand(command, result)
    if not result.Succeeded():
        raise RuntimeError("%s callback failed: %s" % (name, result.GetError()))
    return watchpoint


def capture_backdrop_late(frame, _breakpoint_location, _internal_dict):
    """Validate the x19/x20/x24 chain and arm four bounded watchpoints."""
    try:
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        source = _register(frame, "x19")
        owner = _register(frame, "x20")
        layer = _register(frame, "x24")
        layer_state = _read_u64(process, layer + 0x10, "layer-state pointer")
        if (
            0 in (source, owner, layer, layer_state)
            or _read_u64(process, source + 0x48, "source owner pointer") != owner
            or _read_u64(process, layer_state + 0x120, "layer-state source pointer")
            != source
        ):
            raise RuntimeError("late capture_backdrop object chain differs")
        _state["objectAddresses"] = {
            "source": source,
            "owner": owner,
            "layer": layer,
            "layerState": layer_state,
        }
        initial = _snapshot_private_fields(process)
        selected = initial["sourceSelectedRectI32"]
        if initial["layerStateSelectedRectI32"] != selected or initial[
            "ownerSelectedRectF64"
        ] != [float(value) for value in selected]:
            raise RuntimeError("late selected rectangle identity differs")
        _state["trace"]["objectChain"] = {
            "addresses": dict(_state["objectAddresses"]),
            "exact": True,
            "initialPrivateFields": initial,
        }
        for name, base, offset in WATCH_SPECS:
            address = _state["objectAddresses"][base] + offset
            value = _read_memory(
                process, address, WATCHPOINT_BYTE_COUNT, name + " initial value"
            )
            watchpoint = _install_watchpoint(target, name, address)
            _state["watchpoints"][watchpoint.GetID()] = {
                "name": name,
                "address": address,
                "hitCount": 0,
            }
            _state["lastValues"][name] = value
            _state["trace"]["watchpoints"].append(
                {
                    "id": watchpoint.GetID(),
                    "hardwareIndex": watchpoint.GetHardwareIndex(),
                    "name": name,
                    "address": address,
                    "byteCount": WATCHPOINT_BYTE_COUNT,
                    "initialHex": value.hex(),
                }
            )
        _state["lateBreakpoint"].SetEnabled(False)
        _state["trace"]["status"] = "watchpoints-armed"
        _write_trace()
    except Exception as error:  # LLDB must retain the failure as evidence.
        _failure("capture_backdrop-late", error)
        if _state["lateBreakpoint"] is not None:
            _state["lateBreakpoint"].SetEnabled(False)
    return False


def capture_writer_watchpoint(frame, watchpoint):
    """Record one changed value, writer stack, and deduplicated code window."""
    try:
        identifier = watchpoint.GetID()
        spec = _state["watchpoints"].get(identifier)
        if spec is None:
            raise RuntimeError("unknown watchpoint %d" % identifier)
        process = frame.GetThread().GetProcess()
        after = _read_memory(
            process,
            spec["address"],
            WATCHPOINT_BYTE_COUNT,
            spec["name"] + " changed value",
        )
        before = _state["lastValues"][spec["name"]]
        spec["hitCount"] += 1
        event = {
            "eventIndex": len(_state["trace"]["events"]),
            "watchpointID": identifier,
            "watchpointName": spec["name"],
            "watchpointHitIndex": spec["hitCount"],
            "threadID": frame.GetThread().GetThreadID(),
            "stopPC": frame.GetPC(),
            "beforeHex": before.hex(),
            "afterHex": after.hex(),
            "valueChanged": before != after,
            "frame": _frame_record(frame, process.GetTarget()),
            "backtrace": _backtrace(frame.GetThread()),
            "codeWindowIndex": _code_window(frame),
            "privateFieldsAfter": _snapshot_private_fields(process),
        }
        _state["trace"]["events"].append(event)
        _state["lastValues"][spec["name"]] = after
        if spec["hitCount"] >= MAXIMUM_HITS_PER_WATCHPOINT:
            watchpoint.SetEnabled(False)
        if len(_state["trace"]["events"]) >= MAXIMUM_TOTAL_HITS:
            process.GetTarget().DisableAllWatchpoints()
            _state["trace"]["status"] = "bounded-event-limit-reached"
        _write_trace()
    except Exception as error:  # LLDB must retain the failure as evidence.
        _failure("writer-watchpoint", error)
        watchpoint.SetEnabled(False)
    return False


def finalize():
    """Finalize the raw trace after LLDB's synchronous run command returns."""
    trace = _state["trace"]
    if trace is None:
        return
    trace["statusBeforeFinalization"] = trace["status"]
    trace["status"] = "finalized"
    trace["finalEventCount"] = len(trace["events"])
    trace["finalFailureCount"] = len(trace["failures"])
    trace["watchpointHitCounts"] = {
        spec["name"]: spec["hitCount"] for spec in _state["watchpoints"].values()
    }
    _write_trace()


def __lldb_init_module(debugger, _internal_dict):
    """Install one pending symbol breakpoint when LLDB imports this module."""
    _state["debugger"] = debugger
    _state["trace"] = _new_trace()
    target = debugger.GetSelectedTarget()
    breakpoint = target.BreakpointCreateByName(CAPTURE_BACKDROP_SYMBOL)
    if not breakpoint.IsValid():
        _failure("initialization", "capture_backdrop breakpoint is invalid")
        return
    error = breakpoint.SetScriptCallbackFunction(__name__ + ".capture_backdrop_entry")
    if error is not None and hasattr(error, "Success") and not error.Success():
        _failure(
            "initialization",
            error.GetCString() or "entry callback rejected",
        )
        return
    _state["entryBreakpoint"] = breakpoint
    _state["trace"]["entryBreakpointID"] = breakpoint.GetID()
    _write_trace()
