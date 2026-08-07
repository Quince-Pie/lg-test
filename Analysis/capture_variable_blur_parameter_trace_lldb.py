"""Capture the exact variable-blur allocation operands on the live Apple path.

Import this module while the probe is stopped at its executable ``main``.
Only calls whose live stack contains ``CA::OGL::capture_backdrop`` are retained.
The trace records the complete helper code, entry operands, and the helper's
72-byte result before the caller consumes it; it does not read an image or
pixel and it does not select a call from its numerical result.

LLDB imports this file with the macOS system Python, so keep it compatible
with that interpreter.
"""

import hashlib
import json
import os
from pathlib import Path
import struct

import lldb


TRACE_SCHEMA_VERSION = 1
TRACE_OUTPUT_ENVIRONMENT = "LG_VARIABLE_BLUR_PARAMETER_TRACE_OUTPUT"
FUNCTION = "_ZN2CA3OGL32compute_variable_blur_parametersEjjRKNS_6BoundsEff"
CAPTURE_BACKDROP_NAME = "CA::OGL::capture_backdrop"
OUTPUT_COMPLETE_OFFSET = 0x370
RESULT_BYTE_COUNT = 72
MAXIMUM_RECORD_COUNT = 4096

_state = {
    "trace": None,
    "active": {},
    "entryBreakpoint": None,
    "outputBreakpoint": None,
}


def _trace_path():
    output = os.environ.get(TRACE_OUTPUT_ENVIRONMENT, "")
    if not output:
        raise RuntimeError(TRACE_OUTPUT_ENVIRONMENT + " is unset")
    return Path(output)


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
        trace["status"] = "failed"
    _write_trace()


def _read_memory(process, address, byte_count, label):
    error = lldb.SBError()
    payload = process.ReadMemory(address, byte_count, error)
    if not error.Success() or payload is None or len(payload) != byte_count:
        detail = error.GetCString() or "partial memory read"
        raise RuntimeError("%s at 0x%016x failed: %s" % (label, address, detail))
    return bytes(payload)


def _register_bytes(frame, name):
    register = frame.FindRegister(name)
    if not register.IsValid():
        raise RuntimeError("missing register " + name)
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
                % (name, offset, error.GetCString() or "SBData error")
            )
    return bytes(payload)


def _register_u64(frame, name):
    register = frame.FindRegister(name)
    if not register.IsValid():
        raise RuntimeError("missing register " + name)
    return register.GetValueAsUnsigned(0)


def _float_register(frame, name):
    payload = _register_bytes(frame, name)
    if len(payload) < 4:
        raise RuntimeError("register %s is shorter than binary32" % name)
    return {
        "hex": payload.hex(),
        "binary32": struct.unpack_from("<f", payload)[0],
    }


def _file_spec_path(file_spec):
    directory = file_spec.GetDirectory()
    filename = file_spec.GetFilename()
    if directory and filename:
        return str(Path(directory) / filename)
    return str(filename or directory or "")


def _stack(frame):
    records = []
    thread = frame.GetThread()
    frame_count = min(thread.GetNumFrames(), 32)
    for index in range(frame_count):
        current = thread.GetFrameAtIndex(index)
        if not current.IsValid():
            break
        address = current.GetPCAddress()
        module = address.GetModule()
        records.append(
            {
                "index": index,
                "function": current.GetFunctionName() or "",
                "pc": current.GetPC(),
                "module": _file_spec_path(module.GetFileSpec())
                if module.IsValid()
                else "",
            }
        )
    return records


def _contains_capture_backdrop(frames):
    return any(CAPTURE_BACKDROP_NAME in record.get("function", "") for record in frames)


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def variable_blur_entry(frame, _breakpoint_location, _internal_dict):
    try:
        trace = _state["trace"]
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        if thread_id in _state["active"]:
            raise RuntimeError("nested helper invocation on one thread")
        frames = _stack(frame)
        if not _contains_capture_backdrop(frames):
            return False
        if len(trace["records"]) >= MAXIMUM_RECORD_COUNT:
            raise RuntimeError("record limit exceeded")
        process = thread.GetProcess()
        bounds_address = _register_u64(frame, "x3")
        bounds = _read_memory(process, bounds_address, 16, "input bounds")
        record = {
            "index": len(trace["records"]),
            "threadID": thread_id,
            "entrySP": frame.GetSP(),
            "outputAddress": _register_u64(frame, "x0"),
            "sourceExtent": [
                _register_u64(frame, "w1"),
                _register_u64(frame, "w2"),
            ],
            "boundsAddress": bounds_address,
            "boundsHex": bounds.hex(),
            "bounds": list(struct.unpack("<4i", bounds)),
            "radius0": _float_register(frame, "s0"),
            "radius1": _float_register(frame, "s1"),
            "stack": frames,
            "result": None,
        }
        trace["records"].append(record)
        _state["active"][thread_id] = record["index"]
    except Exception as error:
        _failure("entry", error)
    return False


def variable_blur_output(frame, _breakpoint_location, _internal_dict):
    try:
        trace = _state["trace"]
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        record_index = _state["active"].pop(thread_id, None)
        if record_index is None:
            return False
        record = trace["records"][record_index]
        output_address = _register_u64(frame, "x19")
        if output_address != record["outputAddress"]:
            raise RuntimeError("result pointer differs from entry output pointer")
        payload = _read_memory(
            thread.GetProcess(),
            output_address,
            RESULT_BYTE_COUNT,
            "complete variable-blur result",
        )
        integer_bounds = list(struct.unpack_from("<4i", payload, 20))
        record["result"] = {
            "hex": payload.hex(),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "radiusValues": list(struct.unpack_from("<2f", payload, 0)),
            "mipValues": list(struct.unpack_from("<2I", payload, 8)),
            "alignmentScale": struct.unpack_from("<f", payload, 16)[0],
            "integerBounds": integer_bounds,
            "floatingBounds": list(struct.unpack_from("<4d", payload, 40)),
        }
        _write_trace()
    except Exception as error:
        _failure("output", error)
    return False


def finalize():
    trace = _state["trace"]
    if trace is None:
        return
    if _state["active"]:
        _failure("finalize", "one or more retained helper calls did not return")
        return
    if not trace["records"]:
        _failure("finalize", "no capture_backdrop helper calls were retained")
        return
    if any(record.get("result") is None for record in trace["records"]):
        _failure("finalize", "one or more retained results are incomplete")
        return
    if not trace["failures"]:
        trace["status"] = "complete"
    _write_trace()


def __lldb_init_module(debugger, _internal_dict):
    try:
        target = debugger.GetSelectedTarget()
        process = target.GetProcess()
        if (
            not target.IsValid()
            or not process.IsValid()
            or process.GetState() != lldb.eStateStopped
        ):
            raise RuntimeError("target must be stopped at executable main")
        discovery = target.BreakpointCreateByName(FUNCTION)
        if not discovery.IsValid() or discovery.GetNumLocations() != 1:
            raise RuntimeError("variable-blur helper resolution differs")
        address = discovery.GetLocationAtIndex(0).GetAddress()
        symbol = address.GetSymbol()
        module = address.GetModule()
        start = symbol.GetStartAddress().GetLoadAddress(target)
        end = symbol.GetEndAddress().GetLoadAddress(target)
        target.BreakpointDelete(discovery.GetID())
        if (
            not symbol.IsValid()
            or start == lldb.LLDB_INVALID_ADDRESS
            or end == lldb.LLDB_INVALID_ADDRESS
            or end <= start
            or end - start > 0x10000
        ):
            raise RuntimeError("variable-blur helper bounds differ")
        code = _read_memory(process, start, end - start, "complete helper code")
        _state["trace"] = {
            "variableBlurParameterTraceSchemaVersion": TRACE_SCHEMA_VERSION,
            "classification": (
                "instruction-selected allocation calibration; no image, pixel, "
                "numerical-result selection, unseen transfer, or parity authority"
            ),
            "status": "capturing",
            "configuration": {
                "function": FUNCTION,
                "captureBackdropStackName": CAPTURE_BACKDROP_NAME,
                "outputCompleteOffset": OUTPUT_COMPLETE_OFFSET,
                "resultByteCount": RESULT_BYTE_COUNT,
                "maximumRecordCount": MAXIMUM_RECORD_COUNT,
            },
            "code": {
                "symbolStart": start,
                "symbolEnd": end,
                "symbolByteCount": len(code),
                "sha256": hashlib.sha256(code).hexdigest(),
                "hex": code.hex(),
                "module": _file_spec_path(module.GetFileSpec()),
                "moduleUUID": module.GetUUIDString() or "",
            },
            "records": [],
            "failures": [],
            "capturedImageOrPixelUsedForSelection": False,
            "capturedResultUsedForSelection": False,
        }
        entry = target.BreakpointCreateByAddress(start)
        output = target.BreakpointCreateByAddress(start + OUTPUT_COMPLETE_OFFSET)
        if (
            not entry.IsValid()
            or entry.GetNumLocations() != 1
            or not output.IsValid()
            or output.GetNumLocations() != 1
        ):
            raise RuntimeError("helper breakpoints are unresolved")
        _set_callback(entry, "variable_blur_entry", "helper entry")
        _set_callback(output, "variable_blur_output", "helper output")
        _state["entryBreakpoint"] = entry
        _state["outputBreakpoint"] = output
        _write_trace()
    except Exception as error:
        if _state["trace"] is None:
            _state["trace"] = {
                "variableBlurParameterTraceSchemaVersion": TRACE_SCHEMA_VERSION,
                "status": "failed",
                "records": [],
                "failures": [],
            }
        _failure("initialization", error)
