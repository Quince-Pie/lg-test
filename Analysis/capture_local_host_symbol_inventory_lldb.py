"""Inventory exact Liquid Glass symbols on a locally attached macOS host.

This bootstrap stops at the probe executable's own ``main`` before any capture
is rendered.  It records complete code and module identity for a fixed symbol
list so a host-specific execution adapter can be frozen without borrowing
offsets or hashes from another macOS build.

LLDB imports this file with the macOS system Python, so it avoids newer-only
syntax.
"""

import hashlib
import json
import os
from pathlib import Path

import lldb


TRACE_SCHEMA_VERSION = 1
TRACE_OUTPUT_ENVIRONMENT = "LG_LOCAL_HOST_SYMBOL_INVENTORY_OUTPUT"
DEFAULT_TRACE_OUTPUT = "local-host-symbol-inventory.json"
MAXIMUM_SYMBOL_BYTE_COUNT = 0x40000

SYMBOLS = (
    (
        "groupMargin",
        "SwiftUI.SDFStyle.Group.margin.getter : CoreGraphics.CGFloat",
    ),
    (
        "updateSDFEffects",
        "SwiftUI.SDFLayer.updateSDFEffects(for: SwiftUI.SDFStyle, at: inout "
        "Swift.Int, in: SwiftUI.DisplayList.ViewRenderer.Environment, "
        "backdropGroupID: Swift.Optional<SwiftUI.BackdropGroupID>, blend: "
        "SwiftUI.Material.Layer.SDFLayer.GroupLayer.Blend, opacity: Swift.Float, "
        "options: SwiftUI.Material.Layer.SDFLayer.GroupLayer.Options, gain: "
        "Swift.Float, maxColorComponent: Swift.Float) -> ()",
    ),
    (
        "marginSetter",
        "-[CABackdropLayer setMarginWidth:]",
    ),
    (
        "copyRenderLayer",
        "-[CABackdropLayer _copyRenderLayer:layerFlags:commitFlags:]",
    ),
    (
        "backdropBounds",
        "CA::Render::BackdropLayer::get_bounds("
        "CA::Render::Layer const*, CA::Rect&, CA::Rect*) const",
    ),
)

_state = {
    "trace": None,
    "mainBreakpoint": None,
}


def _trace_path():
    return Path(os.environ.get(TRACE_OUTPUT_ENVIRONMENT, DEFAULT_TRACE_OUTPUT))


def _new_trace():
    return {
        "localHostSymbolInventorySchemaVersion": TRACE_SCHEMA_VERSION,
        "classification": (
            "output-blind local macOS build-identity bootstrap; no public-input "
            "transfer, optical, physical-output, production, or parity authority"
        ),
        "status": "initialized",
        "configuration": {
            "stopSymbol": "main",
            "stopModule": "probe executable only",
            "maximumSymbolByteCount": MAXIMUM_SYMBOL_BYTE_COUNT,
            "symbols": [
                {"role": role, "function": function} for role, function in SYMBOLS
            ],
            "capturedMarginUsedForSelection": False,
            "capturedCropUsedForSelection": False,
            "capturedImageUsedForSelection": False,
            "capturedPixelUsedForSelection": False,
        },
        "target": {},
        "process": {},
        "modules": [],
        "symbols": [],
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
        "loadAddress": (None if header == lldb.LLDB_INVALID_ADDRESS else header),
    }


def _read_memory(process, address, byte_count, label):
    error = lldb.SBError()
    payload = process.ReadMemory(address, byte_count, error)
    if not error.Success() or payload is None or len(payload) != byte_count:
        detail = error.GetCString() or "partial memory read"
        raise RuntimeError("%s at 0x%016x failed: %s" % (label, address, detail))
    return bytes(payload)


def _capture_symbol(process, role, function):
    target = process.GetTarget()
    breakpoint = target.BreakpointCreateByName(function)
    try:
        if not breakpoint.IsValid() or breakpoint.GetNumLocations() < 1:
            raise RuntimeError(function + " did not resolve")
        records = []
        seen = set()
        for index in range(breakpoint.GetNumLocations()):
            location = breakpoint.GetLocationAtIndex(index)
            address = location.GetAddress()
            symbol = address.GetSymbol()
            if not address.IsValid() or not symbol.IsValid():
                continue
            start = symbol.GetStartAddress().GetLoadAddress(target)
            end = symbol.GetEndAddress().GetLoadAddress(target)
            if (
                start == lldb.LLDB_INVALID_ADDRESS
                or end == lldb.LLDB_INVALID_ADDRESS
                or not 0 < end - start <= MAXIMUM_SYMBOL_BYTE_COUNT
            ):
                raise RuntimeError(function + " has invalid symbol bounds")
            module = _module_record(address.GetModule(), target)
            key = (module.get("uuid"), start, end)
            if key in seen:
                continue
            seen.add(key)
            payload = _read_memory(process, start, end - start, role + " complete code")
            module_base = module.get("loadAddress")
            records.append(
                {
                    "function": symbol.GetName() or function,
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
                "%s resolved to %d distinct code symbols" % (function, len(records))
            )
        return {
            "role": role,
            "requestedFunction": function,
            "resolutionCount": len(records),
            "code": records[0],
        }
    finally:
        if breakpoint.IsValid():
            target.BreakpointDelete(breakpoint.GetID())


def _loaded_modules(target):
    records = []
    for index in range(target.GetNumModules()):
        module = target.GetModuleAtIndex(index)
        record = _module_record(module, target)
        path = record.get("path", "")
        filename = Path(path).name
        if filename in (
            "glass-transition-introspect",
            "SwiftUICore",
            "QuartzCore",
        ):
            records.append(record)
    return records


def capture_at_main(frame, breakpoint_location, internal_dict):
    del breakpoint_location, internal_dict
    trace = _state["trace"]
    try:
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        executable = target.GetExecutable()
        executable_module = target.GetModuleAtIndex(0)
        if frame.GetModule().GetUUIDString() != executable_module.GetUUIDString():
            return False
        trace["target"] = {
            "triple": target.GetTriple() or "",
            "executable": _file_spec_path(executable),
            "executableModule": _module_record(executable_module, target),
        }
        trace["process"] = {
            "processID": process.GetProcessID(),
            "stopPC": frame.GetPC(),
            "stopFunction": frame.GetFunctionName() or "",
        }
        trace["modules"] = _loaded_modules(target)
        trace["symbols"] = [
            _capture_symbol(process, role, function) for role, function in SYMBOLS
        ]
        trace["status"] = "captured"
    except Exception as error:
        trace["status"] = "capture-failed"
        _failure("main-capture", error)
    _write_trace()
    return True


def finalize():
    trace = _state["trace"]
    if trace is None:
        return
    trace["statusBeforeFinalization"] = trace["status"]
    trace["status"] = "finalized"
    trace["finalSymbolCount"] = len(trace["symbols"])
    trace["finalFailureCount"] = len(trace["failures"])
    _write_trace()


def __lldb_init_module(debugger, internal_dict):
    del internal_dict
    _state["trace"] = _new_trace()
    try:
        target = debugger.GetSelectedTarget()
        breakpoint = target.BreakpointCreateByName("main")
        if not breakpoint.IsValid() or breakpoint.GetNumLocations() < 1:
            raise RuntimeError("probe main did not resolve")
        error = breakpoint.SetScriptCallbackFunction(__name__ + ".capture_at_main")
        if error is not None and hasattr(error, "Success") and not error.Success():
            raise RuntimeError(error.GetCString() or "probe main callback rejected")
        breakpoint.SetOneShot(True)
        _state["mainBreakpoint"] = breakpoint
        _state["trace"]["status"] = "breakpoint-armed"
    except Exception as error:
        _state["trace"]["status"] = "initialization-failed"
        _failure("initialization", error)
    _write_trace()
