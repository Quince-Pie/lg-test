"""Trace the clamp-related render-filter keys during dynamic replays.

The authenticated probe runs normally through the 60-second presentation
timeline.  Only when its frozen dynamic-uniform replay function begins do we
arm callbacks at ``carendererUniformEvidence`` and immediately after the live
QuartzCore key-378, key-414, and key-358 getters.  This keeps debugger latency
out of the captured presentation states and associates each exact binary64
return with one replay.
"""

import hashlib
import json
import os
import struct
from pathlib import Path

import lldb


OUTPUT_ENVIRONMENT = "LG_TRANSITION_RENDER_KEY_414_OUTPUT"
DEFAULT_OUTPUT = "transition-render-key-414.json"
EXECUTABLE_UUID = "CED67960-0FEE-3CD2-BF78-BA063CDEA45B"
QUARTZCORE_UUID = "F1BA3189-E95A-3ECA-B59A-5A6872754484"
RENDER_CODE_SHA256 = (
    "16faaced4d173d6af88e53cf4dde07e0d080572757a2a0d16d32f99048e1ef46"
)
RENDER_MANGLED_NAME = (
    "_ZNK2CA3OGL21GlassBackgroundFilter6renderEPKNS_6Render6Filter"
    "EPKNS0_5LayerERNS0_7ContextEfPPNS0_7SurfaceEPfS8_"
    "PKNS_11ColorMatrixE"
)
TRANSITION_UNIFORM_MANGLED_NAME = (
    "$s4main35transitionBackgroundUniformEvidence"
    "029_12232F587A4C5CD8B1EEDF696793G2FCLL9rootLayer9snapshots"
    "20matrixBasisRequested14allocationOnly010fixedStateR0"
    "013pathIsolationR015outputDirectorySDySSypGSo7CALayerC_"
    "SayAA010TransitionC14FilterSnapshotACLLVGS4b10Foundation3URLVtF"
)
CARENDERER_UNIFORM_MANGLED_NAME = (
    "$s4main25carendererUniformEvidence"
    "029_12232F587A4C5CD8B1EEDF696793F2FCLL9rootLayer6device7capture"
    "021includeGeometryPolicyD00p18LiveRenderBoundaryD015outputDirectory"
    "SDySSypGSo7CALayerC_So9MTLDevice_pSSS2b10Foundation3URLVSgtF"
)
KEY_RETURN_SITES = {
    358: (2412, "c12c8052a6c7fb970b40621e"),
    378: (1864, "412f80522fc8fb97e06f803d"),
    414: (2376, "c1338052afc7fb970e1ca04e"),
}
MAXIMUM_SYMBOL_BYTE_COUNT = 0x10000

_state = {
    "trace": None,
    "transitionBreakpoint": None,
    "carendererBreakpoint": None,
    "keyBreakpoints": {},
    "currentInvocation": 0,
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


def _read_memory(process, address, byte_count, label):
    error = lldb.SBError()
    payload = process.ReadMemory(address, byte_count, error)
    if not error.Success() or payload is None or len(payload) != byte_count:
        detail = error.GetCString() or "partial memory read"
        raise RuntimeError(
            "%s at 0x%016x failed: %s" % (label, address, detail)
        )
    return bytes(payload)


def _register_unsigned(frame, name):
    register = frame.FindRegister(name)
    if not register.IsValid():
        raise RuntimeError("register %s is unavailable" % name)
    return register.GetValueAsUnsigned()


def _d0_bits(frame):
    register = frame.FindRegister("d0")
    if not register.IsValid():
        raise RuntimeError("register d0 is unavailable")
    error = lldb.SBError()
    bits = register.GetData().GetUnsignedInt64(error, 0)
    if not error.Success():
        raise RuntimeError(error.GetCString() or "d0 data read failed")
    return bits


def _module_record(module, target):
    header = module.GetObjectFileHeaderAddress().GetLoadAddress(target)
    file_spec = module.GetFileSpec()
    directory = file_spec.GetDirectory()
    filename = file_spec.GetFilename()
    path = (
        str(Path(directory) / filename)
        if directory and filename
        else str(filename or directory or "")
    )
    return {
        "path": path,
        "uuid": module.GetUUIDString() or "",
        "loadAddress": (
            None if header == lldb.LLDB_INVALID_ADDRESS else header
        ),
    }


def _exact_symbol(target, mangled_name, discovery_regex):
    breakpoint = target.BreakpointCreateByRegex(discovery_regex)
    try:
        records = []
        for index in range(breakpoint.GetNumLocations()):
            address = breakpoint.GetLocationAtIndex(index).GetAddress()
            symbol = address.GetSymbol()
            if (
                address.IsValid()
                and symbol.IsValid()
                and (symbol.GetMangledName() or "") == mangled_name
            ):
                records.append((address, symbol))
        if len(records) != 1:
            raise RuntimeError(
                "%s resolved %d times" % (mangled_name, len(records))
            )
        return records[0]
    finally:
        if breakpoint.IsValid():
            target.BreakpointDelete(breakpoint.GetID())


def _set_address_callback(target, address, callback_name):
    breakpoint = target.BreakpointCreateByAddress(address)
    if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
        raise RuntimeError("breakpoint at 0x%016x did not resolve" % address)
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback_name)
    if (
        error is not None
        and hasattr(error, "Success")
        and not error.Success()
    ):
        raise RuntimeError(error.GetCString() or "callback rejected")
    return breakpoint


def _arm_value_callbacks(process):
    target = process.GetTarget()
    executable = target.GetModuleAtIndex(0)
    executable_record = _module_record(executable, target)
    if executable_record["uuid"] != EXECUTABLE_UUID:
        raise RuntimeError("authenticated executable UUID differs")

    render_address, render_symbol = _exact_symbol(
        target,
        RENDER_MANGLED_NAME,
        r"GlassBackgroundFilter::render",
    )
    render_start = render_symbol.GetStartAddress().GetLoadAddress(target)
    render_end = render_symbol.GetEndAddress().GetLoadAddress(target)
    render_byte_count = render_end - render_start
    if not 0 < render_byte_count <= MAXIMUM_SYMBOL_BYTE_COUNT:
        raise RuntimeError("render symbol bounds are invalid")
    render_module = _module_record(render_address.GetModule(), target)
    if render_module["uuid"] != QUARTZCORE_UUID:
        raise RuntimeError("QuartzCore UUID differs")
    render_code = _read_memory(
        process, render_start, render_byte_count, "complete render code"
    )
    render_hash = hashlib.sha256(render_code).hexdigest()
    if render_hash != RENDER_CODE_SHA256:
        raise RuntimeError("complete render code hash differs")
    instruction_gates = []
    for key in sorted(KEY_RETURN_SITES):
        return_offset, expected_hex = KEY_RETURN_SITES[key]
        gate = render_code[return_offset - 8 : return_offset + 4]
        if gate.hex() != expected_hex:
            raise RuntimeError(
                "key-%d call/return instruction gate differs" % key
            )
        instruction_gates.append(
            {
                "key": key,
                "getterReturnOffset": return_offset,
                "getterInstructionGateHex": gate.hex(),
            }
        )

    carenderer_address, carenderer_symbol = _exact_symbol(
        target,
        CARENDERER_UNIFORM_MANGLED_NAME,
        r"carendererUniformEvidence",
    )
    carenderer_start = carenderer_symbol.GetStartAddress().GetLoadAddress(target)
    _state["carendererBreakpoint"] = _set_address_callback(
        target, carenderer_start, "capture_carenderer_entry"
    )
    for key in sorted(KEY_RETURN_SITES):
        return_offset, _ = KEY_RETURN_SITES[key]
        _state["keyBreakpoints"][key] = _set_address_callback(
            target,
            render_start + return_offset,
            "capture_key_%d_return" % key,
        )
    trace = _state["trace"]
    trace["codeGate"] = {
        "executable": executable_record,
        "quartzCore": render_module,
        "renderMangledName": RENDER_MANGLED_NAME,
        "renderSymbolStart": render_start,
        "renderSymbolByteCount": render_byte_count,
        "renderCodeSHA256": render_hash,
        "scalarKeyInstructionGates": instruction_gates,
        "carendererUniformSymbolStart": carenderer_start,
    }
    trace["status"] = "value-callbacks-armed"


def capture_transition_uniform_entry(frame, breakpoint_location, internal_dict):
    del breakpoint_location, internal_dict
    trace = _state["trace"]
    try:
        _arm_value_callbacks(frame.GetThread().GetProcess())
    except Exception as error:
        trace["status"] = "callback-arm-failed"
        trace["failures"].append(
            {"stage": "transition-uniform-entry", "message": str(error)}
        )
    _write_trace()
    return False


def capture_carenderer_entry(frame, breakpoint_location, internal_dict):
    del breakpoint_location, internal_dict
    trace = _state["trace"]
    try:
        _state["currentInvocation"] += 1
        trace["carendererInvocations"].append(
            {
                "invocation": _state["currentInvocation"],
                "captureStringWord0": "0x%016x"
                % _register_unsigned(frame, "x2"),
                "captureStringWord1": "0x%016x"
                % _register_unsigned(frame, "x3"),
            }
        )
    except Exception as error:
        trace["failures"].append(
            {"stage": "carenderer-entry", "message": str(error)}
        )
    _write_trace()
    return False


def _capture_key_return(frame, key):
    trace = _state["trace"]
    try:
        bits = _d0_bits(frame)
        value = struct.unpack("<d", struct.pack("<Q", bits))[0]
        context = _register_unsigned(frame, "x19")
        record = {
            "sequence": len(trace["keyReturns"]),
            "carendererInvocation": _state["currentInvocation"],
            "key": key,
            "binary64Bits": "%016x" % bits,
            "value": value,
            "renderFilterKeyValueArray": "0x%016x"
            % _register_unsigned(frame, "x22"),
            "renderContext": "0x%016x" % context,
            "secondarySurface": "0x%016x"
            % _register_unsigned(frame, "x23"),
        }
        if key == 358:
            gamma = _read_memory(
                frame.GetThread().GetProcess(),
                context + 0x258,
                4,
                "render context gamma",
            )
            record["renderContextGammaBits"] = gamma.hex()
            record["renderContextGamma"] = struct.unpack("<f", gamma)[0]
        trace["keyReturns"].append(record)
    except Exception as error:
        trace["failures"].append(
            {"stage": "key-%d-return" % key, "message": str(error)}
        )
    _write_trace()
    return False


def capture_key_358_return(frame, breakpoint_location, internal_dict):
    del breakpoint_location, internal_dict
    return _capture_key_return(frame, 358)


def capture_key_378_return(frame, breakpoint_location, internal_dict):
    del breakpoint_location, internal_dict
    return _capture_key_return(frame, 378)


def capture_key_414_return(frame, breakpoint_location, internal_dict):
    del breakpoint_location, internal_dict
    return _capture_key_return(frame, 414)


def finalize():
    trace = _state["trace"]
    if trace is None:
        return
    trace["statusBeforeFinalization"] = trace["status"]
    trace["status"] = "finalized"
    trace["finalCarendererInvocationCount"] = len(
        trace["carendererInvocations"]
    )
    trace["finalKeyReturnCount"] = len(trace["keyReturns"])
    trace["finalFailureCount"] = len(trace["failures"])
    _write_trace()


def __lldb_init_module(debugger, internal_dict):
    del internal_dict
    _state["trace"] = {
        "schemaVersion": 1,
        "classification": (
            "post-presentation direct-M1 exact render-filter key trace; no "
            "captured value selects a breakpoint, sample, or model"
        ),
        "status": "initialized",
        "configuration": {
            "transitionUniformMangledName": TRANSITION_UNIFORM_MANGLED_NAME,
            "carendererUniformMangledName": CARENDERER_UNIFORM_MANGLED_NAME,
            "renderMangledName": RENDER_MANGLED_NAME,
            "keys": sorted(KEY_RETURN_SITES),
            "getterReturnOffsets": {
                str(key): KEY_RETURN_SITES[key][0]
                for key in sorted(KEY_RETURN_SITES)
            },
            "callbacksArmOnlyAfterPresentationTimeline": True,
        },
        "codeGate": {},
        "carendererInvocations": [],
        "keyReturns": [],
        "failures": [],
    }
    try:
        target = debugger.GetSelectedTarget()
        breakpoint = target.BreakpointCreateByRegex(
            r"transitionBackgroundUniformEvidence"
        )
        exact_locations = []
        for index in range(breakpoint.GetNumLocations()):
            address = breakpoint.GetLocationAtIndex(index).GetAddress()
            symbol = address.GetSymbol()
            if (
                address.IsValid()
                and symbol.IsValid()
                and (symbol.GetMangledName() or "")
                == TRANSITION_UNIFORM_MANGLED_NAME
            ):
                exact_locations.append(address)
        if breakpoint.GetNumLocations() != 1 or len(exact_locations) != 1:
            raise RuntimeError(
                "transition uniform entry did not resolve exactly once"
            )
        error = breakpoint.SetScriptCallbackFunction(
            __name__ + ".capture_transition_uniform_entry"
        )
        if (
            error is not None
            and hasattr(error, "Success")
            and not error.Success()
        ):
            raise RuntimeError(error.GetCString() or "callback rejected")
        breakpoint.SetOneShot(True)
        _state["transitionBreakpoint"] = breakpoint
        _state["trace"]["status"] = "transition-breakpoint-armed"
        _state["trace"]["transitionUniformSymbol"] = {
            "fileAddress": exact_locations[0].GetFileAddress(),
            "module": _module_record(
                exact_locations[0].GetModule(), target
            ),
        }
    except Exception as error:
        _state["trace"]["status"] = "initialization-failed"
        _state["trace"]["failures"].append(
            {"stage": "initialization", "message": str(error)}
        )
    _write_trace()
