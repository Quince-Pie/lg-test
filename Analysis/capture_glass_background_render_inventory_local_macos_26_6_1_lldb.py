"""Capture the complete live QuartzCore GlassBackgroundFilter render symbol.

LLDB imports this module with Apple's embedded Python while the authenticated
transition probe is stopped at its own ``main``.  No frame, filter, or pixel
value is inspected; this inventory only fixes the current code identity and
provides the bytes needed to decode the render-filter field reads.
"""

import hashlib
import json
import os
from pathlib import Path

import lldb


OUTPUT_ENVIRONMENT = "LG_GLASS_BACKGROUND_RENDER_INVENTORY_OUTPUT"
DEFAULT_OUTPUT = "glass-background-render-inventory.json"
MAXIMUM_SYMBOL_BYTE_COUNT = 0x10000
RENDER_MANGLED_NAME = (
    "_ZNK2CA3OGL21GlassBackgroundFilter6renderEPKNS_6Render6Filter"
    "EPKNS0_5LayerERNS0_7ContextEfPPNS0_7SurfaceEPfS8_"
    "PKNS_11ColorMatrixE"
)
RENDER_DISCOVERY_REGEX = r"GlassBackgroundFilter::render"

_state = {
    "trace": None,
    "mainBreakpoint": None,
}


def _output_path():
    return Path(os.environ.get(OUTPUT_ENVIRONMENT, DEFAULT_OUTPUT))


def _write_trace():
    trace = _state["trace"]
    if trace is None:
        return
    path = _output_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(trace, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _file_spec_path(file_spec):
    directory = file_spec.GetDirectory()
    filename = file_spec.GetFilename()
    if directory and filename:
        return str(Path(directory) / filename)
    return str(filename or directory or "")


def _module_record(module, target):
    header = module.GetObjectFileHeaderAddress().GetLoadAddress(target)
    return {
        "path": _file_spec_path(module.GetFileSpec()),
        "uuid": module.GetUUIDString() or "",
        "loadAddress": (
            None if header == lldb.LLDB_INVALID_ADDRESS else header
        ),
    }


def _read_memory(process, address, byte_count):
    error = lldb.SBError()
    payload = process.ReadMemory(address, byte_count, error)
    if not error.Success() or payload is None or len(payload) != byte_count:
        detail = error.GetCString() or "partial memory read"
        raise RuntimeError(
            "complete render code read at 0x%016x failed: %s"
            % (address, detail)
        )
    return bytes(payload)


def _render_symbol_record(process):
    target = process.GetTarget()
    breakpoint = target.BreakpointCreateByRegex(RENDER_DISCOVERY_REGEX)
    try:
        if not breakpoint.IsValid() or breakpoint.GetNumLocations() < 1:
            raise RuntimeError("GlassBackgroundFilter::render did not resolve")
        records = []
        seen = set()
        for index in range(breakpoint.GetNumLocations()):
            location = breakpoint.GetLocationAtIndex(index)
            address = location.GetAddress()
            symbol = address.GetSymbol()
            if not address.IsValid() or not symbol.IsValid():
                continue
            mangled = symbol.GetMangledName() or ""
            if mangled != RENDER_MANGLED_NAME:
                continue
            start = symbol.GetStartAddress().GetLoadAddress(target)
            end = symbol.GetEndAddress().GetLoadAddress(target)
            if (
                start == lldb.LLDB_INVALID_ADDRESS
                or end == lldb.LLDB_INVALID_ADDRESS
                or not 0 < end - start <= MAXIMUM_SYMBOL_BYTE_COUNT
            ):
                raise RuntimeError("render symbol has invalid bounds")
            module = _module_record(address.GetModule(), target)
            key = (module["uuid"], start, end)
            if key in seen:
                continue
            seen.add(key)
            payload = _read_memory(process, start, end - start)
            module_base = module["loadAddress"]
            records.append(
                {
                    "mangledName": mangled,
                    "demangledName": symbol.GetName() or "",
                    "symbolStart": start,
                    "symbolEnd": end,
                    "symbolByteCount": len(payload),
                    "moduleOffset": (
                        None if module_base is None else start - module_base
                    ),
                    "codeSHA256": hashlib.sha256(payload).hexdigest(),
                    "hex": payload.hex(),
                    "module": module,
                }
            )
        if len(records) != 1:
            raise RuntimeError(
                "exact render symbol resolved %d times" % len(records)
            )
        return records[0]
    finally:
        if breakpoint.IsValid():
            target.BreakpointDelete(breakpoint.GetID())


def capture_at_main(frame, breakpoint_location, internal_dict):
    del breakpoint_location, internal_dict
    trace = _state["trace"]
    try:
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        executable_module = target.GetModuleAtIndex(0)
        if frame.GetModule().GetUUIDString() != executable_module.GetUUIDString():
            return False
        trace["target"] = {
            "triple": target.GetTriple() or "",
            "executable": _file_spec_path(target.GetExecutable()),
            "executableModule": _module_record(executable_module, target),
        }
        trace["process"] = {
            "processID": process.GetProcessID(),
            "stopPC": frame.GetPC(),
            "stopFunction": frame.GetFunctionName() or "",
        }
        trace["renderSymbol"] = _render_symbol_record(process)
        trace["status"] = "captured"
    except Exception as error:
        trace["status"] = "capture-failed"
        trace["failures"].append(
            {"stage": "main-capture", "message": str(error)}
        )
    _write_trace()
    return True


def finalize():
    trace = _state["trace"]
    if trace is None:
        return
    trace["statusBeforeFinalization"] = trace["status"]
    trace["status"] = "finalized"
    trace["finalFailureCount"] = len(trace["failures"])
    _write_trace()


def __lldb_init_module(debugger, internal_dict):
    del internal_dict
    _state["trace"] = {
        "schemaVersion": 1,
        "classification": (
            "value-blind direct-M1 complete-symbol inventory; no filter, "
            "crop, image, pixel, production, or parity authority"
        ),
        "status": "initialized",
        "configuration": {
            "stopSymbol": "main",
            "requestedMangledName": RENDER_MANGLED_NAME,
            "maximumSymbolByteCount": MAXIMUM_SYMBOL_BYTE_COUNT,
        },
        "target": {},
        "process": {},
        "renderSymbol": {},
        "failures": [],
    }
    try:
        target = debugger.GetSelectedTarget()
        breakpoint = target.BreakpointCreateByName("main")
        if not breakpoint.IsValid() or breakpoint.GetNumLocations() < 1:
            raise RuntimeError("probe main did not resolve")
        error = breakpoint.SetScriptCallbackFunction(
            __name__ + ".capture_at_main"
        )
        if (
            error is not None
            and hasattr(error, "Success")
            and not error.Success()
        ):
            raise RuntimeError(
                error.GetCString() or "probe main callback rejected"
            )
        breakpoint.SetOneShot(True)
        _state["mainBreakpoint"] = breakpoint
        _state["trace"]["status"] = "breakpoint-armed"
    except Exception as error:
        _state["trace"]["status"] = "initialization-failed"
        _state["trace"]["failures"].append(
            {"stage": "initialization", "message": str(error)}
        )
    _write_trace()
