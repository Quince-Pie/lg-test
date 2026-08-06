"""Capture the complete live ``marginWidth`` transport without selecting pixels.

The probe joins three structurally related events by object identity:

* ``-[CABackdropLayer setMarginWidth:]`` receives the model-layer binary64 value;
* ``-[CABackdropLayer _copyRenderLayer:layerFlags:commitFlags:]`` converts that
  value to binary32 and stores it in the render layer; and
* ``CA::Render::BackdropLayer::get_bounds`` consumes the same render object.

Every matching invocation is retained.  No margin, crop, image, or transition
output participates in breakpoint selection.  LLDB imports this file with the
macOS system Python, so the implementation deliberately avoids newer syntax.
"""

import hashlib
import json
import os
import struct
from pathlib import Path

import lldb


TRACE_SCHEMA_VERSION = 1
QUARTZCORE_UUID = "4D34EB4E-2BBB-3751-A362-8E2EB74656E8"

COPY_FUNCTION = "-[CABackdropLayer _copyRenderLayer:layerFlags:commitFlags:]"
COPY_BYTE_COUNT = 1640
COPY_CODE_SHA256 = (
    "6547059b681d624b57e2996cfe4ebec262759a7e11be3f43cdd56e6b5794d838"
)
COPY_MARGIN_STORE_OFFSET = 948
COPY_MARGIN_STORE_INSTRUCTION_HEX = "a02600bd"

SETTER_FUNCTION = "-[CABackdropLayer setMarginWidth:]"
SETTER_BYTE_COUNT = 96
SETTER_CODE_SHA256 = (
    "b7c5020620b41d7d8f3107e525521ad6c381b5f26dac500449838e813c2f2901"
)

BOUNDS_FUNCTION = (
    "CA::Render::BackdropLayer::get_bounds("
    "CA::Render::Layer const*, CA::Rect&, CA::Rect*) const"
)
BOUNDS_BYTE_COUNT = 80
BOUNDS_CODE_SHA256 = (
    "85a99558cc08c2a693969b55c804cd811e8ef710ac2d02460830f8bf9d6ec85a"
)
RENDER_MARGIN_OFFSET = 0x24

MAXIMUM_EVENT_COUNT = 8192
MAXIMUM_BACKTRACE_FRAME_COUNT = 24
MAXIMUM_CALLER_COUNT = 64
MAXIMUM_CALLER_BYTE_COUNT = 131072
MAXIMUM_TOTAL_CALLER_BYTE_COUNT = 2 * 1024 * 1024
OBJECT_PREFIX_BYTE_COUNT = 0x40

TRACE_OUTPUT_ENVIRONMENT = "LG_BACKDROP_MARGIN_WRITER_TRACE_OUTPUT"
DEFAULT_TRACE_OUTPUT = "backdrop-margin-writer/backdrop-margin-writer-trace.json"


_state = {
    "debugger": None,
    "trace": None,
    "breakpoints": {},
    "copyStoreBreakpoint": None,
    "pendingCopies": {},
    "callerKeys": {},
    "callerTotalBytes": 0,
}


def _trace_path():
    return Path(os.environ.get(TRACE_OUTPUT_ENVIRONMENT, DEFAULT_TRACE_OUTPUT))


def _new_trace():
    return {
        "backdropMarginWriterExecutionTraceSchemaVersion": TRACE_SCHEMA_VERSION,
        "classification": (
            "output-blind exhaustive live writer-chain discovery and prospective "
            "transition-maximum transfer evidence; not optical, physical-output, "
            "production-shader, or product-parity authority"
        ),
        "status": "initialized",
        "configuration": {
            "material": os.environ.get("LG_GLASS_MATERIAL", ""),
            "appearance": os.environ.get("LG_GLASS_APPEARANCE", ""),
            "direction": os.environ.get("LG_TRANSITION_DIRECTION", ""),
            "geometry": os.environ.get("LG_GLASS_GEOMETRY", ""),
            "quartzCoreUUID": QUARTZCORE_UUID,
            "copyFunction": COPY_FUNCTION,
            "copyByteCount": COPY_BYTE_COUNT,
            "copyCodeSHA256": COPY_CODE_SHA256,
            "copyMarginStoreOffset": COPY_MARGIN_STORE_OFFSET,
            "copyMarginStoreInstructionHex": COPY_MARGIN_STORE_INSTRUCTION_HEX,
            "setterFunction": SETTER_FUNCTION,
            "setterByteCount": SETTER_BYTE_COUNT,
            "setterCodeSHA256": SETTER_CODE_SHA256,
            "boundsFunction": BOUNDS_FUNCTION,
            "boundsByteCount": BOUNDS_BYTE_COUNT,
            "boundsCodeSHA256": BOUNDS_CODE_SHA256,
            "renderMarginOffset": RENDER_MARGIN_OFFSET,
            "maximumEventCount": MAXIMUM_EVENT_COUNT,
            "maximumBacktraceFrameCount": MAXIMUM_BACKTRACE_FRAME_COUNT,
            "maximumCallerCount": MAXIMUM_CALLER_COUNT,
            "maximumCallerByteCount": MAXIMUM_CALLER_BYTE_COUNT,
            "maximumTotalCallerByteCount": MAXIMUM_TOTAL_CALLER_BYTE_COUNT,
            "objectPrefixByteCount": OBJECT_PREFIX_BYTE_COUNT,
            "breakpointSelection": (
                "all invocations of three preregistered exact code symbols plus "
                "the fixed copy-store instruction"
            ),
            "capturedMarginUsedForSelection": False,
            "capturedCropUsedForSelection": False,
            "capturedImageUsedForSelection": False,
        },
        "codeGates": {},
        "breakpoints": [],
        "callers": [],
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


def _failure(stage, error):
    trace = _state["trace"]
    if trace is not None:
        trace["failures"].append({"stage": str(stage), "message": str(error)})
    _write_trace()


def _read_memory(process, address, byte_count, label):
    error = lldb.SBError()
    payload = process.ReadMemory(address, byte_count, error)
    if not error.Success() or payload is None or len(payload) != byte_count:
        detail = error.GetCString() or "partial memory read"
        raise RuntimeError(
            "%s at 0x%016x failed: %s" % (label, address, detail)
        )
    return bytes(payload)


def _register_u64(frame, name):
    register = frame.FindRegister(name)
    if not register.IsValid():
        raise RuntimeError("missing register %s" % name)
    return register.GetValueAsUnsigned(0)


def _register_bytes(frame, name):
    register = frame.FindRegister(name)
    if not register.IsValid():
        raise RuntimeError("missing register %s" % name)
    data = register.GetData()
    byte_count = register.GetByteSize()
    if byte_count <= 0 or not data.IsValid() or data.GetByteSize() != byte_count:
        raise RuntimeError("register %s data is unavailable" % name)
    error = lldb.SBError()
    payload = bytearray()
    for offset in range(byte_count):
        payload.append(data.GetUnsignedInt8(error, offset))
        if not error.Success():
            raise RuntimeError(
                "register %s byte %d failed: %s"
                % (name, offset, error.GetCString() or "unknown SBData error")
            )
    return bytes(payload)


def _file_spec_path(file_spec):
    directory = file_spec.GetDirectory()
    filename = file_spec.GetFilename()
    if directory and filename:
        return str(Path(directory) / filename)
    return str(filename or directory or "")


def _module_record(module, target):
    if not module.IsValid():
        return {"valid": False}
    header = module.GetObjectFileHeaderAddress().GetLoadAddress(target)
    return {
        "valid": True,
        "path": _file_spec_path(module.GetFileSpec()),
        "uuid": module.GetUUIDString() or "",
        "loadAddress": (
            None if header == lldb.LLDB_INVALID_ADDRESS else header
        ),
    }


def _frame_record(frame, target):
    symbol = frame.GetSymbol()
    start = lldb.LLDB_INVALID_ADDRESS
    end = lldb.LLDB_INVALID_ADDRESS
    if symbol.IsValid():
        start = symbol.GetStartAddress().GetLoadAddress(target)
        end = symbol.GetEndAddress().GetLoadAddress(target)
    pc = frame.GetPC()
    return {
        "frameIndex": frame.GetFrameID(),
        "pc": pc,
        "function": frame.GetFunctionName() or "",
        "symbolStart": None if start == lldb.LLDB_INVALID_ADDRESS else start,
        "symbolEnd": None if end == lldb.LLDB_INVALID_ADDRESS else end,
        "symbolOffset": (
            None
            if start == lldb.LLDB_INVALID_ADDRESS or pc < start
            else pc - start
        ),
        "module": _module_record(frame.GetModule(), target),
    }


def _backtrace(thread):
    target = thread.GetProcess().GetTarget()
    count = min(thread.GetNumFrames(), MAXIMUM_BACKTRACE_FRAME_COUNT)
    return [
        _frame_record(thread.GetFrameAtIndex(index), target)
        for index in range(count)
    ]


def _snapshot_prefix(process, address, label):
    payload = _read_memory(process, address, OBJECT_PREFIX_BYTE_COUNT, label)
    return {
        "address": address,
        "byteCount": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "hex": payload.hex(),
    }


def _gate_symbol(frame, key, function, byte_count, expected_sha256):
    trace = _state["trace"]
    existing = trace["codeGates"].get(key)
    target = frame.GetThread().GetProcess().GetTarget()
    symbol = frame.GetSymbol()
    if not symbol.IsValid():
        raise RuntimeError("%s symbol is invalid" % key)
    start = symbol.GetStartAddress().GetLoadAddress(target)
    end = symbol.GetEndAddress().GetLoadAddress(target)
    observed_function = frame.GetFunctionName() or symbol.GetName() or ""
    if (
        start == lldb.LLDB_INVALID_ADDRESS
        or end == lldb.LLDB_INVALID_ADDRESS
        or end - start != byte_count
        or observed_function != function
    ):
        raise RuntimeError("%s symbol identity differs" % key)
    module = _module_record(frame.GetModule(), target)
    if module.get("uuid") != QUARTZCORE_UUID:
        raise RuntimeError("%s QuartzCore UUID differs" % key)
    if existing is not None:
        if existing["symbolStart"] != start or existing["symbolEnd"] != end:
            raise RuntimeError("%s symbol moved during execution" % key)
        return existing
    process = frame.GetThread().GetProcess()
    code = _read_memory(process, start, byte_count, key + " complete code")
    digest = hashlib.sha256(code).hexdigest()
    if digest != expected_sha256:
        raise RuntimeError("%s complete-code SHA-256 differs" % key)
    record = {
        "function": function,
        "symbolStart": start,
        "symbolEnd": end,
        "symbolByteCount": byte_count,
        "codeSHA256": digest,
        "module": module,
    }
    trace["codeGates"][key] = record
    _write_trace()
    return record


def _capture_caller(frame):
    thread = frame.GetThread()
    if thread.GetNumFrames() < 2:
        return None
    caller = thread.GetFrameAtIndex(1)
    target = thread.GetProcess().GetTarget()
    record = _frame_record(caller, target)
    start = record["symbolStart"]
    end = record["symbolEnd"]
    if start is None or end is None or end <= start:
        record["completeCodeCaptured"] = False
        record["completeCodeFailure"] = "caller symbol bounds unavailable"
        key = (record["pc"], record["function"])
    else:
        key = (start, end)
    existing = _state["callerKeys"].get(key)
    if existing is not None:
        return existing
    callers = _state["trace"]["callers"]
    if len(callers) >= MAXIMUM_CALLER_COUNT:
        raise RuntimeError("setter caller count exceeded the bounded maximum")
    byte_count = 0 if start is None or end is None else end - start
    if start is not None and end is not None and end > start:
        if byte_count > MAXIMUM_CALLER_BYTE_COUNT:
            record["completeCodeCaptured"] = False
            record["completeCodeFailure"] = "caller symbol exceeds byte bound"
        elif _state["callerTotalBytes"] + byte_count > MAXIMUM_TOTAL_CALLER_BYTE_COUNT:
            raise RuntimeError("setter caller code exceeded the total byte bound")
        else:
            code = _read_memory(
                thread.GetProcess(), start, byte_count, "setter caller complete code"
            )
            record.update(
                {
                    "completeCodeCaptured": True,
                    "symbolByteCount": byte_count,
                    "codeSHA256": hashlib.sha256(code).hexdigest(),
                    "hex": code.hex(),
                }
            )
            _state["callerTotalBytes"] += byte_count
    index = len(callers)
    callers.append(record)
    _state["callerKeys"][key] = index
    return index


def _append_event(event):
    events = _state["trace"]["events"]
    if len(events) >= MAXIMUM_EVENT_COUNT:
        raise RuntimeError("writer-chain event count exceeded the bounded maximum")
    event["eventIndex"] = len(events)
    events.append(event)
    _write_trace()
    return event["eventIndex"]


def _install_copy_store_breakpoint(frame, gate):
    if _state["copyStoreBreakpoint"] is not None:
        return
    target = frame.GetThread().GetProcess().GetTarget()
    address = gate["symbolStart"] + COPY_MARGIN_STORE_OFFSET
    instruction = _read_memory(
        frame.GetThread().GetProcess(), address, 4, "copy margin store instruction"
    )
    if instruction.hex() != COPY_MARGIN_STORE_INSTRUCTION_HEX:
        raise RuntimeError("copy margin store instruction differs")
    breakpoint = target.BreakpointCreateByAddress(address)
    if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
        raise RuntimeError("copy margin store breakpoint is unresolved")
    error = breakpoint.SetScriptCallbackFunction(__name__ + ".copy_margin_store")
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or "copy store callback rejected")
    _state["copyStoreBreakpoint"] = breakpoint
    _state["breakpoints"]["copyStore"] = breakpoint
    _state["trace"]["breakpoints"].append(
        {
            "name": "copyStore",
            "id": breakpoint.GetID(),
            "address": address,
            "selection": "fixed exact-code instruction offset",
        }
    )
    _write_trace()


def copy_entry(frame, _breakpoint_location, _internal_dict):
    try:
        gate = _gate_symbol(
            frame, "copy", COPY_FUNCTION, COPY_BYTE_COUNT, COPY_CODE_SHA256
        )
        _install_copy_store_breakpoint(frame, gate)
        thread = frame.GetThread()
        process = thread.GetProcess()
        model = _register_u64(frame, "x0")
        render_argument = _register_u64(frame, "x2")
        event_index = _append_event(
            {
                "type": "copyEntry",
                "threadID": thread.GetThreadID(),
                "pc": frame.GetPC(),
                "modelSelf": model,
                "renderArgument": render_argument,
                "modelPrefix": _snapshot_prefix(
                    process, model, "copy-entry model object prefix"
                ),
                "backtrace": _backtrace(thread),
            }
        )
        _state["pendingCopies"].setdefault(thread.GetThreadID(), []).append(
            {
                "eventIndex": event_index,
                "modelSelf": model,
                "renderArgument": render_argument,
            }
        )
    except Exception as error:
        _failure("copy-entry", error)
    return False


def copy_margin_store(frame, _breakpoint_location, _internal_dict):
    try:
        gate = _state["trace"]["codeGates"].get("copy")
        if gate is None or frame.GetPC() != gate["symbolStart"] + COPY_MARGIN_STORE_OFFSET:
            raise RuntimeError("copy store PC differs")
        process = frame.GetThread().GetProcess()
        thread_id = frame.GetThread().GetThreadID()
        model = _register_u64(frame, "x20")
        render = _register_u64(frame, "x21")
        v0 = _register_bytes(frame, "v0")
        if len(v0) < 4:
            raise RuntimeError("v0 is too short for the binary32 margin")
        margin_raw = v0[:4]
        pending = _state["pendingCopies"].get(thread_id, [])
        matched = None
        matched_index = None
        for index in range(len(pending) - 1, -1, -1):
            candidate = pending[index]
            if candidate["modelSelf"] == model:
                matched = candidate
                matched_index = index
                break
        if matched_index is not None:
            pending.pop(matched_index)
        _append_event(
            {
                "type": "copyMarginStore",
                "threadID": thread_id,
                "pc": frame.GetPC(),
                "copyEntryEventIndex": (
                    None if matched is None else matched["eventIndex"]
                ),
                "modelSelf": model,
                "renderSelf": render,
                "entryRenderArgument": (
                    None if matched is None else matched["renderArgument"]
                ),
                "entryModelMatched": matched is not None,
                "entryRenderArgumentMatched": (
                    matched is not None and matched["renderArgument"] == render
                ),
                "marginF32": struct.unpack("<f", margin_raw)[0],
                "marginF32RawLittleEndianHex": margin_raw.hex(),
                "renderMarginBeforeRawLittleEndianHex": _read_memory(
                    process,
                    render + RENDER_MARGIN_OFFSET,
                    4,
                    "render margin before copy store",
                ).hex(),
                "renderPrefixBeforeStore": _snapshot_prefix(
                    process, render, "render object prefix before margin store"
                ),
            }
        )
    except Exception as error:
        _failure("copy-margin-store", error)
    return False


def margin_setter(frame, _breakpoint_location, _internal_dict):
    try:
        _gate_symbol(
            frame, "setter", SETTER_FUNCTION, SETTER_BYTE_COUNT, SETTER_CODE_SHA256
        )
        thread = frame.GetThread()
        process = thread.GetProcess()
        model = _register_u64(frame, "x0")
        v0 = _register_bytes(frame, "v0")
        if len(v0) < 8:
            raise RuntimeError("v0 is too short for the binary64 setter value")
        raw = v0[:8]
        _append_event(
            {
                "type": "marginSetter",
                "threadID": thread.GetThreadID(),
                "pc": frame.GetPC(),
                "modelSelf": model,
                "marginF64": struct.unpack("<d", raw)[0],
                "marginF64RawLittleEndianHex": raw.hex(),
                "modelPrefix": _snapshot_prefix(
                    process, model, "margin-setter model object prefix"
                ),
                "directCallerIndex": _capture_caller(frame),
                "backtrace": _backtrace(thread),
            }
        )
    except Exception as error:
        _failure("margin-setter", error)
    return False


def backdrop_bounds(frame, _breakpoint_location, _internal_dict):
    try:
        _gate_symbol(
            frame, "bounds", BOUNDS_FUNCTION, BOUNDS_BYTE_COUNT, BOUNDS_CODE_SHA256
        )
        thread = frame.GetThread()
        process = thread.GetProcess()
        render = _register_u64(frame, "x0")
        layer = _register_u64(frame, "x1")
        output = _register_u64(frame, "x2")
        raw = _read_memory(
            process,
            render + RENDER_MARGIN_OFFSET,
            4,
            "render margin consumed by get_bounds",
        )
        _append_event(
            {
                "type": "backdropBounds",
                "threadID": thread.GetThreadID(),
                "pc": frame.GetPC(),
                "renderSelf": render,
                "layer": layer,
                "output": output,
                "marginF32": struct.unpack("<f", raw)[0],
                "marginF32RawLittleEndianHex": raw.hex(),
                "renderPrefix": _snapshot_prefix(
                    process, render, "get-bounds render object prefix"
                ),
            }
        )
    except Exception as error:
        _failure("backdrop-bounds", error)
    return False


def _install_named_breakpoint(target, name, function, callback):
    breakpoint = target.BreakpointCreateByName(function)
    if not breakpoint.IsValid():
        raise RuntimeError("%s breakpoint is invalid" % name)
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or name + " callback rejected")
    _state["breakpoints"][name] = breakpoint
    _state["trace"]["breakpoints"].append(
        {
            "name": name,
            "id": breakpoint.GetID(),
            "function": function,
            "selection": "all exact symbol invocations",
        }
    )


def finalize():
    trace = _state["trace"]
    if trace is None:
        return
    trace["statusBeforeFinalization"] = trace["status"]
    trace["status"] = "finalized"
    trace["finalEventCount"] = len(trace["events"])
    trace["finalFailureCount"] = len(trace["failures"])
    trace["finalCallerCount"] = len(trace["callers"])
    trace["finalCallerCodeByteCount"] = _state["callerTotalBytes"]
    trace["eventTypeCounts"] = {
        event_type: sum(
            event["type"] == event_type for event in trace["events"]
        )
        for event_type in (
            "marginSetter",
            "copyEntry",
            "copyMarginStore",
            "backdropBounds",
        )
    }
    trace["pendingCopyEntryCount"] = sum(
        len(entries) for entries in _state["pendingCopies"].values()
    )
    _write_trace()


def __lldb_init_module(debugger, _internal_dict):
    _state["debugger"] = debugger
    _state["trace"] = _new_trace()
    try:
        target = debugger.GetSelectedTarget()
        _install_named_breakpoint(target, "copyEntry", COPY_FUNCTION, "copy_entry")
        _install_named_breakpoint(
            target, "marginSetter", SETTER_FUNCTION, "margin_setter"
        )
        _install_named_breakpoint(
            target, "backdropBounds", BOUNDS_FUNCTION, "backdrop_bounds"
        )
        _state["trace"]["status"] = "breakpoints-armed"
    except Exception as error:
        _state["trace"]["status"] = "initialization-failed"
        _failure("initialization", error)
    _write_trace()
