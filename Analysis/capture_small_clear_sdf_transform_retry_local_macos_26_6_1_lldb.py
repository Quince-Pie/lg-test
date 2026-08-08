"""Retry the SDF-entry trace with its missing transform pointer chain.

This keeps the original output-blind breakpoint and record bounds.  The only
new data are the owner reached through ``layer+0x10`` and the transform reached
through ``owner+0x38``—the exact chain read by the already frozen QuartzCore
instructions.  LLDB imports this file with macOS's embedded Python.
"""

import hashlib
import json
import os
from pathlib import Path
import struct

import capture_small_clear_sdf_entry_local_macos_26_6_1_lldb as base


TRACE_SCHEMA_VERSION = 1
TRACE_OUTPUT_ENVIRONMENT = "LG_SMALL_CLEAR_SDF_TRANSFORM_RETRY_TRACE_OUTPUT"
TRANSFORM_OWNER_PREFIX_BYTE_COUNT = 0x40
TRANSFORM_PREFIX_BYTE_COUNT = 0xA0


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


def _capture_code_gate(frame):
    trace = _state["trace"]
    if trace["codeGate"] is not None:
        return
    process = frame.GetThread().GetProcess()
    address = frame.GetPCAddress()
    module = address.GetModule()
    code = base._read_memory(
        process,
        frame.GetPC(),
        base.FUNCTION_BYTE_COUNT,
        "emit_sdf_bounds_internal code",
    )
    trace["codeGate"] = {
        "function": base.FUNCTION,
        "byteCount": base.FUNCTION_BYTE_COUNT,
        "sha256": hashlib.sha256(code).hexdigest(),
        "module": (
            base._file_spec_path(module.GetFileSpec()) if module.IsValid() else ""
        ),
        "moduleUUID": module.GetUUIDString() if module.IsValid() else "",
    }


def capture_entry(frame, _breakpoint_location, _internal_dict):
    try:
        trace = _state["trace"]
        if len(trace["records"]) >= base.MAXIMUM_RECORD_COUNT:
            raise RuntimeError("record limit exceeded")
        _capture_code_gate(frame)
        process = frame.GetThread().GetProcess()
        layer_address = base._register_u64(frame, "x1")
        layer = base._read_memory(
            process,
            layer_address,
            base.LAYER_PREFIX_BYTE_COUNT,
            "layer prefix",
        )
        layer_state_address = base._pointer_from(layer, 0x18)
        layer_state = base._read_memory(
            process,
            layer_state_address,
            base.LAYER_STATE_PREFIX_BYTE_COUNT,
            "layer-state prefix",
        )
        shape_address = base._pointer_from(layer_state, 0x88)
        shape = (
            base._read_memory(
                process,
                shape_address,
                base.SHAPE_PREFIX_BYTE_COUNT,
                "shape prefix",
            )
            if shape_address
            else b""
        )
        transform_owner_address = base._pointer_from(layer, 0x10)
        transform_owner = base._read_memory(
            process,
            transform_owner_address,
            TRANSFORM_OWNER_PREFIX_BYTE_COUNT,
            "transform-owner prefix",
        )
        transform_address = base._pointer_from(transform_owner, 0x38)
        transform = (
            base._read_memory(
                process,
                transform_address,
                TRANSFORM_PREFIX_BYTE_COUNT,
                "transform prefix",
            )
            if transform_address
            else b""
        )
        vector_registers = {}
        for index in range(8):
            name = "v%d" % index
            payload = base._register_bytes(frame, name)
            vector_registers[name] = {
                "hex": payload.hex(),
                "binary32": list(struct.unpack_from("<4f", payload)),
            }
        record = {
            "index": len(trace["records"]),
            "threadID": frame.GetThread().GetThreadID(),
            "contextAddress": base._register_u64(frame, "x0"),
            "layerAddress": layer_address,
            "surfaceAddress": base._register_u64(frame, "x2"),
            "booleanArgument": base._register_u64(frame, "w3"),
            "layerPrefixHex": layer.hex(),
            "layerStateAddress": layer_state_address,
            "layerStatePrefixHex": layer_state.hex(),
            "shapeAddress": shape_address,
            "shapePrefixHex": shape.hex(),
            "transformOwnerAddress": transform_owner_address,
            "transformOwnerPrefixHex": transform_owner.hex(),
            "transformAddress": transform_address,
            "transformPrefixHex": transform.hex(),
            "vectorRegisters": vector_registers,
            "stack": base._stack(frame),
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
            "smallClearSDFTransformRetryTraceSchemaVersion": TRACE_SCHEMA_VERSION,
            "classification": (
                "output-blind exhaustive live SDF-emitter transform retry; "
                "not optical, production-shader, or product-parity authority"
            ),
            "status": "initialized",
            "configuration": {
                "function": base.FUNCTION,
                "functionByteCount": base.FUNCTION_BYTE_COUNT,
                "maximumRecordCount": base.MAXIMUM_RECORD_COUNT,
                "maximumStackFrameCount": base.MAXIMUM_STACK_FRAME_COUNT,
                "layerPrefixByteCount": base.LAYER_PREFIX_BYTE_COUNT,
                "layerStatePrefixByteCount": base.LAYER_STATE_PREFIX_BYTE_COUNT,
                "shapePrefixByteCount": base.SHAPE_PREFIX_BYTE_COUNT,
                "transformOwnerPrefixByteCount": (TRANSFORM_OWNER_PREFIX_BYTE_COUNT),
                "transformPrefixByteCount": TRANSFORM_PREFIX_BYTE_COUNT,
                "transformPointerChain": "layer+0x10 -> owner+0x38",
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
        breakpoint = target.BreakpointCreateByName(base.FUNCTION)
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
