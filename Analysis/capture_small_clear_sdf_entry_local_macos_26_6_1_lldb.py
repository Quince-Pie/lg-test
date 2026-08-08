"""Capture every live input to QuartzCore's SDF-bounds emitter.

The breakpoint selection is structural: every invocation of the exact
``emit_sdf_bounds_internal`` symbol is retained, up to the frozen record
limit.  Captured radii, geometry, buffers, images, and pixels never select a
record.  LLDB imports this module with macOS's embedded Python, so this file
intentionally remains compatible with that interpreter.
"""

import hashlib
import json
import os
from pathlib import Path
import struct

import lldb


TRACE_SCHEMA_VERSION = 1
TRACE_OUTPUT_ENVIRONMENT = "LG_SMALL_CLEAR_SDF_ENTRY_TRACE_OUTPUT"
FUNCTION = (
    "_ZN2CA3OGLL24emit_sdf_bounds_internalERNS0_7ContextEPKNS0_5LayerE"
    "fffNS_4Vec2IfEEPNS0_7SurfaceEffb"
)
FUNCTION_BYTE_COUNT = 0xB74
MAXIMUM_RECORD_COUNT = 256
MAXIMUM_STACK_FRAME_COUNT = 16
LAYER_PREFIX_BYTE_COUNT = 0xB0
LAYER_STATE_PREFIX_BYTE_COUNT = 0x120
SHAPE_PREFIX_BYTE_COUNT = 0x140


_state = {
    "trace": None,
    "breakpoint": None,
}


def _trace_path():
    value = os.environ.get(TRACE_OUTPUT_ENVIRONMENT, "")
    if not value:
        raise RuntimeError(TRACE_OUTPUT_ENVIRONMENT + " is unset")
    return Path(value)


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
        trace["status"] = "failed"
        trace["failures"].append({"stage": str(stage), "message": str(error)})
    _write_trace()


def _read_memory(process, address, byte_count, label):
    error = lldb.SBError()
    payload = process.ReadMemory(address, byte_count, error)
    if not error.Success() or payload is None or len(payload) != byte_count:
        detail = error.GetCString() or "partial memory read"
        raise RuntimeError("%s at 0x%016x failed: %s" % (label, address, detail))
    return bytes(payload)


def _register_u64(frame, name):
    register = frame.FindRegister(name)
    if not register.IsValid():
        raise RuntimeError("missing register " + name)
    return register.GetValueAsUnsigned(0)


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


def _file_spec_path(file_spec):
    directory = file_spec.GetDirectory()
    filename = file_spec.GetFilename()
    if directory and filename:
        return str(Path(directory) / filename)
    return str(filename or directory or "")


def _stack(frame):
    result = []
    thread = frame.GetThread()
    for index in range(min(thread.GetNumFrames(), MAXIMUM_STACK_FRAME_COUNT)):
        current = thread.GetFrameAtIndex(index)
        if not current.IsValid():
            break
        address = current.GetPCAddress()
        module = address.GetModule()
        result.append(
            {
                "index": index,
                "function": current.GetFunctionName() or "",
                "pc": current.GetPC(),
                "module": (
                    _file_spec_path(module.GetFileSpec()) if module.IsValid() else ""
                ),
            }
        )
    return result


def _pointer_from(payload, offset):
    return struct.unpack_from("<Q", payload, offset)[0]


def _capture_code_gate(frame):
    trace = _state["trace"]
    if trace["codeGate"] is not None:
        return
    process = frame.GetThread().GetProcess()
    address = frame.GetPCAddress()
    module = address.GetModule()
    code = _read_memory(
        process,
        frame.GetPC(),
        FUNCTION_BYTE_COUNT,
        "emit_sdf_bounds_internal code",
    )
    trace["codeGate"] = {
        "function": FUNCTION,
        "byteCount": FUNCTION_BYTE_COUNT,
        "sha256": hashlib.sha256(code).hexdigest(),
        "module": (_file_spec_path(module.GetFileSpec()) if module.IsValid() else ""),
        "moduleUUID": module.GetUUIDString() if module.IsValid() else "",
    }


def capture_entry(frame, _breakpoint_location, _internal_dict):
    try:
        trace = _state["trace"]
        if len(trace["records"]) >= MAXIMUM_RECORD_COUNT:
            raise RuntimeError("record limit exceeded")
        _capture_code_gate(frame)
        process = frame.GetThread().GetProcess()
        layer_address = _register_u64(frame, "x1")
        layer = _read_memory(
            process,
            layer_address,
            LAYER_PREFIX_BYTE_COUNT,
            "layer prefix",
        )
        layer_state_address = _pointer_from(layer, 0x18)
        layer_state = _read_memory(
            process,
            layer_state_address,
            LAYER_STATE_PREFIX_BYTE_COUNT,
            "layer-state prefix",
        )
        shape_address = _pointer_from(layer_state, 0x88)
        shape = (
            _read_memory(
                process,
                shape_address,
                SHAPE_PREFIX_BYTE_COUNT,
                "shape prefix",
            )
            if shape_address
            else b""
        )
        vector_registers = {}
        for index in range(8):
            name = "v%d" % index
            payload = _register_bytes(frame, name)
            vector_registers[name] = {
                "hex": payload.hex(),
                "binary32": list(struct.unpack_from("<4f", payload)),
            }
        record = {
            "index": len(trace["records"]),
            "threadID": frame.GetThread().GetThreadID(),
            "contextAddress": _register_u64(frame, "x0"),
            "layerAddress": layer_address,
            "surfaceAddress": _register_u64(frame, "x2"),
            "booleanArgument": _register_u64(frame, "w3"),
            "layerPrefixHex": layer.hex(),
            "layerStateAddress": layer_state_address,
            "layerStatePrefixHex": layer_state.hex(),
            "shapeAddress": shape_address,
            "shapePrefixHex": shape.hex(),
            "vectorRegisters": vector_registers,
            "stack": _stack(frame),
        }
        trace["records"].append(record)
        trace["status"] = "capturing"
        _write_trace()
    except Exception as error:
        _failure("entry", error)
    return False


def __lldb_init_module(debugger, _internal_dict):
    try:
        trace = {
            "smallClearSDFEntryTraceSchemaVersion": TRACE_SCHEMA_VERSION,
            "classification": (
                "output-blind exhaustive live SDF-emitter input discovery; "
                "not optical, production-shader, or product-parity authority"
            ),
            "status": "initialized",
            "configuration": {
                "function": FUNCTION,
                "functionByteCount": FUNCTION_BYTE_COUNT,
                "maximumRecordCount": MAXIMUM_RECORD_COUNT,
                "maximumStackFrameCount": MAXIMUM_STACK_FRAME_COUNT,
                "layerPrefixByteCount": LAYER_PREFIX_BYTE_COUNT,
                "layerStatePrefixByteCount": LAYER_STATE_PREFIX_BYTE_COUNT,
                "shapePrefixByteCount": SHAPE_PREFIX_BYTE_COUNT,
                "breakpointSelection": "every invocation of the exact symbol",
                "capturedValueUsedForSelection": False,
                "capturedGeometryUsedForSelection": False,
                "capturedImageUsedForSelection": False,
                "capturedPixelUsedForSelection": False,
            },
            "codeGate": None,
            "records": [],
            "failures": [],
        }
        _state["trace"] = trace
        target = debugger.GetSelectedTarget()
        breakpoint = target.BreakpointCreateByName(FUNCTION)
        if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
            raise RuntimeError("emit_sdf_bounds_internal did not resolve exactly once")
        error = breakpoint.SetScriptCallbackFunction(__name__ + ".capture_entry")
        if error is not None and hasattr(error, "Success") and not error.Success():
            raise RuntimeError(error.GetCString() or "callback rejected")
        _state["breakpoint"] = breakpoint
        trace["breakpointID"] = breakpoint.GetID()
        trace["breakpointLocationCount"] = breakpoint.GetNumLocations()
        _write_trace()
    except Exception as error:
        _failure("initialize", error)
        raise
