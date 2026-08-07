"""Capture live writer/caller symbol bytes without reading application values.

Import this module while the stable probe is stopped at its executable ``main``
entry.  It resolves only frozen symbol names, reads complete code ranges, and
writes their module identities and hashes.  It never continues the process or
reads a register, object, margin, crop, image, or pixel.

LLDB uses the macOS system Python, so this source avoids newer-only syntax.
"""

import hashlib
import json
import os
from pathlib import Path

import lldb


SCHEMA_VERSION = 1
OUTPUT_ENVIRONMENT = "LG_LIVE_WRITER_CODE_INVENTORY_OUTPUT"
SPECS = (
    {
        "key": "copy",
        "function": "-[CABackdropLayer _copyRenderLayer:layerFlags:commitFlags:]",
        "moduleSuffix": "/QuartzCore",
        "historicalByteCount": 1640,
        "historicalSHA256": (
            "6547059b681d624b57e2996cfe4ebec262759a7e11be3f43cdd56e6b5794d838"
        ),
    },
    {
        "key": "setter",
        "function": "-[CABackdropLayer setMarginWidth:]",
        "moduleSuffix": "/QuartzCore",
        "historicalByteCount": 96,
        "historicalSHA256": (
            "b7c5020620b41d7d8f3107e525521ad6c381b5f26dac500449838e813c2f2901"
        ),
    },
    {
        "key": "bounds",
        "function": (
            "CA::Render::BackdropLayer::get_bounds("
            "CA::Render::Layer const*, CA::Rect&, CA::Rect*) const"
        ),
        "moduleSuffix": "/QuartzCore",
        "historicalByteCount": 80,
        "historicalSHA256": (
            "85a99558cc08c2a693969b55c804cd811e8ef710ac2d02460830f8bf9d6ec85a"
        ),
    },
    {
        "key": "caller",
        "function": (
            "SwiftUI.SDFLayer.updateSDFEffects(for: SwiftUI.SDFStyle, at: inout "
            "Swift.Int, in: SwiftUI.DisplayList.ViewRenderer.Environment, "
            "backdropGroupID: Swift.Optional<SwiftUI.BackdropGroupID>, blend: "
            "SwiftUI.Material.Layer.SDFLayer.GroupLayer.Blend, opacity: "
            "Swift.Float, options: SwiftUI.Material.Layer.SDFLayer.GroupLayer.Options, "
            "gain: Swift.Float, maxColorComponent: Swift.Float) -> ()"
        ),
        "moduleSuffix": "/SwiftUICore",
        "historicalByteCount": 6844,
        "historicalSHA256": (
            "65dff1ba1d4e0ae3376a6ad2e1946bb6ee8725c6380ff886e68111d92fff933e"
        ),
    },
)


def _module_record(module, target):
    header = module.GetObjectFileHeaderAddress()
    load_address = header.GetLoadAddress(target)
    return {
        "valid": module.IsValid(),
        "path": module.GetFileSpec().fullpath or "",
        "uuid": module.GetUUIDString() or "",
        "loadAddress": (
            None if load_address == lldb.LLDB_INVALID_ADDRESS else load_address
        ),
    }


def _read_memory(process, address, byte_count, label):
    error = lldb.SBError()
    payload = process.ReadMemory(address, byte_count, error)
    if not error.Success() or payload is None or len(payload) != byte_count:
        raise RuntimeError(error.GetCString() or label + " read failed")
    return payload


def _symbol_record(target, process, spec):
    breakpoint = target.BreakpointCreateByName(spec["function"])
    if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
        raise RuntimeError(spec["key"] + " symbol location count differs")
    location = breakpoint.GetLocationAtIndex(0)
    address = location.GetAddress()
    symbol = address.GetSymbol()
    module = address.GetModule()
    start = symbol.GetStartAddress().GetLoadAddress(target)
    end = symbol.GetEndAddress().GetLoadAddress(target)
    if (
        not symbol.IsValid()
        or start == lldb.LLDB_INVALID_ADDRESS
        or end == lldb.LLDB_INVALID_ADDRESS
        or end <= start
    ):
        raise RuntimeError(spec["key"] + " symbol bounds differ")
    observed_function = symbol.GetName() or ""
    module_record = _module_record(module, target)
    if (
        observed_function != spec["function"]
        or not module_record["path"].endswith(spec["moduleSuffix"])
    ):
        raise RuntimeError(spec["key"] + " symbol identity differs")
    payload = _read_memory(process, start, end - start, spec["key"] + " code")
    observed_hash = hashlib.sha256(payload).hexdigest()
    return {
        "function": observed_function,
        "symbolStart": start,
        "symbolEnd": end,
        "symbolByteCount": len(payload),
        "codeSHA256": observed_hash,
        "hex": payload.hex(),
        "module": module_record,
        "historicalByteCount": spec["historicalByteCount"],
        "historicalSHA256": spec["historicalSHA256"],
        "byteCountMatchesHistorical": len(payload) == spec["historicalByteCount"],
        "codeSHA256MatchesHistorical": observed_hash == spec["historicalSHA256"],
    }


def capture(debugger):
    target = debugger.GetSelectedTarget()
    process = target.GetProcess()
    if not target.IsValid() or not process.IsValid() or process.GetState() != lldb.eStateStopped:
        raise RuntimeError("target must be stopped at executable main")
    records = {}
    failures = []
    for spec in SPECS:
        try:
            records[spec["key"]] = _symbol_record(target, process, spec)
        except Exception as error:
            failures.append({"key": spec["key"], "message": str(error)})
    result = {
        "liveWriterCodeInventorySchemaVersion": SCHEMA_VERSION,
        "classification": (
            "value-blind complete-code inventory at stable executable main; "
            "no application value or output is read"
        ),
        "status": "complete" if not failures else "failed",
        "symbols": records,
        "failures": failures,
        "capturedMarginUsed": False,
        "capturedCropUsed": False,
        "capturedImageOrPixelUsed": False,
        "processContinuedAfterMain": False,
    }
    output = os.environ.get(OUTPUT_ENVIRONMENT, "")
    if not output:
        raise RuntimeError(OUTPUT_ENVIRONMENT + " is unset")
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    if failures:
        raise RuntimeError("one or more structural symbols were not captured")


def __lldb_init_module(debugger, _internal_dict):
    capture(debugger)
