"""Capture case-22 provider calls inside exact public carrier-render calls.

The application binary is unchanged.  A fixed direct call inside
``transitionBackgroundUniformEvidence`` opens each interval, and the adjacent
return address closes it.  Provider objects and returns are retained without
reading any captured value for runtime selection.
"""

import json
import os
import struct
from pathlib import Path

import capture_case22_provider_field_matrix_local_macos_26_6_1_lldb as field


TRACE_SCHEMA_VERSION = 1

MAIN_UUID = "F8B0B6E3-3270-3C94-817F-B4914852D04C"
MAIN_PATH_SUFFIX = "/glass-transition-introspect-721293f"
BACKGROUND_MANGLED = (
    "$s4main35transitionBackgroundUniformEvidence029_12232F587A4C5CD8B1EEDF696793G2FCLL"
    "9rootLayer9snapshots20matrixBasisRequested14allocationOnly010fixedStateR0013pathIsolationR0"
    "15outputDirectorySDySSypGSo7CALayerC_SayAA010TransitionC14FilterSnapshotACLLVGS4b10Foundation3URLVtF"
)
BACKGROUND_MODULE_OFFSET = 0x881B0
BACKGROUND_BYTE_COUNT = 0x23B0
BACKGROUND_CODE_SHA256 = (
    "1ca54720d237eb6970b65dd2ecc88b8372b64667f4ea2d28ef4bc8414668e2fd"
)
RENDER_MODULE_OFFSET = 0x7D12C
RENDER_BYTE_COUNT = 0x4E8
RENDER_CODE_SHA256 = (
    "0c661f1010199a56e6730d897079fda69fc4a267f7f48d1e2054b14ff9270e0c"
)
RENDER_CALL_OFFSET = 0x1000
RENDER_RETURN_OFFSET = 0x1004
RENDER_CALL_INSTRUCTION_HEX = "dfcfff97"

SAMPLE_INDICES = tuple(range(1, 33))
MAXIMUM_CALLS_PER_INTERVAL = 128
MAXIMUM_TOTAL_CALLS = len(SAMPLE_INDICES) * MAXIMUM_CALLS_PER_INTERVAL

SWIFTUICORE_UUID = field.SWIFTUICORE_UUID
DESIGN_LIBRARY_UUID = field.DESIGN_LIBRARY_UUID
WRAPPER_RETURN_OFFSET = field.WRAPPER_RETURN_OFFSET
PROVIDER_OBJECT_BYTE_COUNT = field.PROVIDER_OBJECT_BYTE_COUNT

base = field.base
case22 = field.case22

_state = {
    "trace": None,
    "bootstrapBreakpoint": None,
    "renderCallBreakpoint": None,
    "renderReturnBreakpoint": None,
    "providerBreakpoint": None,
    "providerReturnBreakpoint": None,
    "activeInterval": None,
    "pendingCalls": {},
}


def _trace_path():
    raw = os.environ.get("LG_CASE22_PROVIDER_PUBLIC_RENDER_INTERVAL_TRACE_OUTPUT")
    if not raw:
        raise RuntimeError(
            "LG_CASE22_PROVIDER_PUBLIC_RENDER_INTERVAL_TRACE_OUTPUT is required"
        )
    return Path(raw)


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


def _new_trace():
    return {
        "case22ProviderPublicRenderIntervalTransferLocalMacOSLldbTraceSchemaVersion": (
            TRACE_SCHEMA_VERSION
        ),
        "classification": (
            "prospectively frozen output-blind case-22 provider capture "
            "bracketed by the exact public carrier-render direct call"
        ),
        "status": "initialized",
        "configuration": {
            "macOSProductVersion": "26.6.1",
            "macOSBuildVersion": "25G76",
            "architecture": "arm64",
            "material": "regular",
            "appearance": "light",
            "geometry": "circle-127-center",
            "direction": "materialize",
            "sampleIndices": list(SAMPLE_INDICES),
            "mainUUID": MAIN_UUID,
            "backgroundModuleOffset": BACKGROUND_MODULE_OFFSET,
            "backgroundByteCount": BACKGROUND_BYTE_COUNT,
            "backgroundCodeSHA256": BACKGROUND_CODE_SHA256,
            "renderModuleOffset": RENDER_MODULE_OFFSET,
            "renderByteCount": RENDER_BYTE_COUNT,
            "renderCodeSHA256": RENDER_CODE_SHA256,
            "renderCallOffset": RENDER_CALL_OFFSET,
            "renderReturnOffset": RENDER_RETURN_OFFSET,
            "renderCallInstructionHex": RENDER_CALL_INSTRUCTION_HEX,
            "maximumCallsPerInterval": MAXIMUM_CALLS_PER_INTERVAL,
            "maximumTotalCalls": MAXIMUM_TOTAL_CALLS,
            "capturedObjectUsedForSelection": False,
            "capturedReturnUsedForSelection": False,
            "capturedPublicInputUsedForSelection": False,
            "capturedMarginUsedForSelection": False,
            "capturedCropUsedForSelection": False,
            "capturedImageUsedForSelection": False,
            "capturedPixelUsedForSelection": False,
        },
        "breakpoints": {},
        "modules": {},
        "backgroundFunction": {},
        "renderFunction": {},
        "wrapper": {},
        "provider": {},
        "intervals": [],
        "calls": [],
        "events": [],
        "failures": [],
    }


def _failure(stage, error):
    trace = _state["trace"]
    if trace is not None:
        trace["failures"].append({"stage": str(stage), "message": str(error)})
        trace["status"] = "failed"
        _write_trace()


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _append_event(kind, record_index):
    events = _state["trace"]["events"]
    event = {
        "eventIndex": len(events),
        "kind": kind,
        "recordIndex": record_index,
    }
    events.append(event)
    return event["eventIndex"]


def _capture_main_symbol(process, module, offset, byte_count, digest, label):
    record = case22._capture_symbol(
        process,
        module["loadAddress"] + offset,
        label,
    )
    if (
        not isinstance(record.get("function"), str)
        or not record["function"]
        or record.get("symbolStart") != module["loadAddress"] + offset
        or record.get("symbolByteCount") != byte_count
        or record.get("codeSHA256") != digest
        or record.get("module", {}).get("uuid") != MAIN_UUID
    ):
        raise RuntimeError(label + " exact identity differs")
    return record


def _decode_direct_branch_target(instruction_raw, instruction_address):
    if len(instruction_raw) != 4:
        raise RuntimeError("render call instruction width differs")
    instruction = struct.unpack("<I", instruction_raw)[0]
    if instruction >> 26 != 0b100101:
        raise RuntimeError("render callsite is not ARM64 BL")
    displacement = instruction & 0x03FFFFFF
    if displacement & (1 << 25):
        displacement -= 1 << 26
    return instruction_address + displacement * 4


def _install_exact_breakpoint(target, address, callback, label, enabled):
    breakpoint = target.BreakpointCreateByAddress(address)
    if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
        raise RuntimeError(label + " breakpoint is unresolved")
    _set_callback(breakpoint, callback, label)
    breakpoint.SetEnabled(enabled)
    return breakpoint


def _install_capture(frame):
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    main_module = field._module_by_uuid(
        target, MAIN_UUID, MAIN_PATH_SUFFIX, "main executable"
    )
    swift_module = field._module_by_uuid(
        target, SWIFTUICORE_UUID, "/SwiftUICore", "SwiftUICore"
    )
    design_module = field._module_by_uuid(
        target, DESIGN_LIBRARY_UUID, "/DesignLibrary", "DesignLibrary"
    )
    background = _capture_main_symbol(
        process,
        main_module,
        BACKGROUND_MODULE_OFFSET,
        BACKGROUND_BYTE_COUNT,
        BACKGROUND_CODE_SHA256,
        "transition background uniform function",
    )
    render = _capture_main_symbol(
        process,
        main_module,
        RENDER_MODULE_OFFSET,
        RENDER_BYTE_COUNT,
        RENDER_CODE_SHA256,
        "local transition CARenderer function",
    )
    call_raw = bytes.fromhex(background["hex"])[
        RENDER_CALL_OFFSET : RENDER_CALL_OFFSET + 4
    ]
    call_address = background["symbolStart"] + RENDER_CALL_OFFSET
    if call_raw.hex() != RENDER_CALL_INSTRUCTION_HEX:
        raise RuntimeError("render direct-call instruction differs")
    if _decode_direct_branch_target(call_raw, call_address) != render["symbolStart"]:
        raise RuntimeError("render direct-call target differs")
    wrapper = field._capture_wrapper(process, swift_module)
    provider = field._capture_provider(process, design_module)

    render_call = _install_exact_breakpoint(
        target,
        call_address,
        "render_call",
        "render call",
        True,
    )
    render_return = _install_exact_breakpoint(
        target,
        background["symbolStart"] + RENDER_RETURN_OFFSET,
        "render_return",
        "render return",
        True,
    )
    provider_entry = _install_exact_breakpoint(
        target,
        provider["symbolStart"],
        "provider_entry",
        "provider entry",
        False,
    )
    provider_return = _install_exact_breakpoint(
        target,
        wrapper["symbolStart"] + WRAPPER_RETURN_OFFSET,
        "provider_return",
        "provider return",
        False,
    )
    _state["renderCallBreakpoint"] = render_call
    _state["renderReturnBreakpoint"] = render_return
    _state["providerBreakpoint"] = provider_entry
    _state["providerReturnBreakpoint"] = provider_return
    trace = _state["trace"]
    trace["modules"] = {
        "main": main_module,
        "swiftUICore": swift_module,
        "designLibrary": design_module,
    }
    trace["backgroundFunction"] = background
    trace["renderFunction"] = render
    trace["wrapper"] = wrapper
    trace["provider"] = provider
    trace["breakpoints"].update(
        {
            "renderCall": {
                "id": render_call.GetID(),
                "address": call_address,
                "locationCount": render_call.GetNumLocations(),
            },
            "renderReturn": {
                "id": render_return.GetID(),
                "address": background["symbolStart"] + RENDER_RETURN_OFFSET,
                "locationCount": render_return.GetNumLocations(),
            },
            "providerEntry": {
                "id": provider_entry.GetID(),
                "address": provider["symbolStart"],
                "locationCount": provider_entry.GetNumLocations(),
            },
            "providerReturn": {
                "id": provider_return.GetID(),
                "address": wrapper["symbolStart"] + WRAPPER_RETURN_OFFSET,
                "locationCount": provider_return.GetNumLocations(),
            },
        }
    )


def bootstrap(frame, _breakpoint_location, _internal_dict):
    try:
        if _state["renderCallBreakpoint"] is not None:
            raise RuntimeError("background bootstrap repeated")
        _install_capture(frame)
        _state["bootstrapBreakpoint"].SetEnabled(False)
        _state["trace"]["status"] = "render-boundaries-armed"
        _write_trace()
    except Exception as error:
        _failure("bootstrap", error)
    return False


def render_call(frame, _breakpoint_location, _internal_dict):
    try:
        trace = _state["trace"]
        if _state["activeInterval"] is not None:
            raise RuntimeError("render call opened a nested interval")
        interval_index = len(trace["intervals"])
        if interval_index >= len(SAMPLE_INDICES):
            raise RuntimeError("render interval count exceeded the contract")
        background = trace["backgroundFunction"]
        expected_pc = background["symbolStart"] + RENDER_CALL_OFFSET
        if frame.GetPC() != expected_pc:
            raise RuntimeError("render call PC differs")
        thread_id = frame.GetThread().GetThreadID()
        interval = {
            "intervalIndex": interval_index,
            "sampleIndex": SAMPLE_INDICES[interval_index],
            "threadID": thread_id,
            "status": "active",
            "entryEventIndex": None,
            "returnEventIndex": None,
            "entryFrame": case22._frame_record(frame),
            "returnFrame": None,
            "callIndices": [],
        }
        trace["intervals"].append(interval)
        interval["entryEventIndex"] = _append_event(
            "render-call", interval_index
        )
        _state["activeInterval"] = interval_index
        _state["providerBreakpoint"].SetEnabled(True)
        _state["providerReturnBreakpoint"].SetEnabled(True)
        trace["status"] = "render-interval-active"
    except Exception as error:
        _failure("render-call", error)
    return False


def render_return(frame, _breakpoint_location, _internal_dict):
    try:
        trace = _state["trace"]
        interval_index = _state["activeInterval"]
        if interval_index is None:
            raise RuntimeError("render return has no active interval")
        interval = trace["intervals"][interval_index]
        if frame.GetThread().GetThreadID() != interval["threadID"]:
            raise RuntimeError("render interval returned on another thread")
        background = trace["backgroundFunction"]
        if frame.GetPC() != background["symbolStart"] + RENDER_RETURN_OFFSET:
            raise RuntimeError("render return PC differs")
        if _state["pendingCalls"]:
            raise RuntimeError("render interval closed with pending provider calls")
        _state["providerBreakpoint"].SetEnabled(False)
        _state["providerReturnBreakpoint"].SetEnabled(False)
        interval["returnFrame"] = case22._frame_record(frame)
        interval["returnEventIndex"] = _append_event(
            "render-return", interval_index
        )
        interval["finalCallCount"] = len(interval["callIndices"])
        interval["status"] = "closed"
        _state["activeInterval"] = None
        trace["status"] = (
            "all-render-intervals-closed"
            if len(trace["intervals"]) == len(SAMPLE_INDICES)
            else "between-render-intervals"
        )
        _write_trace()
    except Exception as error:
        _failure("render-return", error)
    return False


def provider_entry(frame, _breakpoint_location, _internal_dict):
    try:
        trace = _state["trace"]
        interval_index = _state["activeInterval"]
        if interval_index is None:
            raise RuntimeError("provider entry occurred outside a render interval")
        interval = trace["intervals"][interval_index]
        if len(interval["callIndices"]) >= MAXIMUM_CALLS_PER_INTERVAL:
            raise RuntimeError("provider call bound exceeded for render interval")
        calls = trace["calls"]
        if len(calls) >= MAXIMUM_TOTAL_CALLS:
            raise RuntimeError("total provider call bound exceeded")
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        if thread_id in _state["pendingCalls"]:
            raise RuntimeError("nested provider call occurred on one thread")
        provider = trace["provider"]
        if frame.GetPC() != provider["symbolStart"]:
            raise RuntimeError("provider entry PC differs")
        process = thread.GetProcess()
        object_address = base._register_u64(frame, "x20")
        call_index = len(calls)
        call = {
            "callIndex": call_index,
            "intervalIndex": interval_index,
            "sampleIndex": interval["sampleIndex"],
            "intervalCallIndex": len(interval["callIndices"]),
            "threadID": thread_id,
            "entryEventIndex": None,
            "returnEventIndex": None,
            "entryFrame": case22._frame_record(frame),
            "providerObject": case22._snapshot(
                process,
                object_address,
                PROVIDER_OBJECT_BYTE_COUNT,
                "public render-interval provider object",
            ),
            "providerObjectAddress": object_address,
            "returnFrame": None,
            "returnV0RawLittleEndianHex": None,
            "returnF64RawLittleEndianHex": None,
            "returnObject": None,
            "objectChanged": None,
        }
        calls.append(call)
        interval["callIndices"].append(call_index)
        call["entryEventIndex"] = _append_event("provider-entry", call_index)
        _state["pendingCalls"][thread_id] = call_index
        if len(calls) % 16 == 0:
            _write_trace()
    except Exception as error:
        _failure("provider-entry", error)
    return False


def provider_return(frame, _breakpoint_location, _internal_dict):
    try:
        trace = _state["trace"]
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        call_index = _state["pendingCalls"].pop(thread_id, None)
        if call_index is None:
            return False
        call = trace["calls"][call_index]
        wrapper = trace["wrapper"]
        if frame.GetPC() != wrapper["symbolStart"] + WRAPPER_RETURN_OFFSET:
            raise RuntimeError("provider return PC differs")
        v0 = base._register_bytes(frame, "v0")
        if len(v0) != 16:
            raise RuntimeError("provider return v0 byte count differs")
        process = thread.GetProcess()
        returned_object = case22._snapshot(
            process,
            call["providerObjectAddress"],
            PROVIDER_OBJECT_BYTE_COUNT,
            "public render-interval returned provider object",
        )
        call["returnFrame"] = case22._frame_record(frame)
        call["returnV0RawLittleEndianHex"] = v0.hex()
        call["returnF64RawLittleEndianHex"] = v0[:8].hex()
        call["returnObject"] = returned_object
        call["objectChanged"] = (
            returned_object["hex"] != call["providerObject"]["hex"]
        )
        call["returnEventIndex"] = _append_event("provider-return", call_index)
    except Exception as error:
        _failure("provider-return", error)
    return False


def finalize():
    trace = _state["trace"]
    if trace is None:
        return
    trace["statusBeforeFinalization"] = trace["status"]
    trace["status"] = "finalized"
    trace["finalIntervalCount"] = len(trace["intervals"])
    trace["finalCallCount"] = len(trace["calls"])
    trace["finalEventCount"] = len(trace["events"])
    trace["finalFailureCount"] = len(trace["failures"])
    trace["finalPendingCallCount"] = len(_state["pendingCalls"])
    trace["finalActiveInterval"] = _state["activeInterval"]
    trace["allIntervalsClosed"] = len(trace["intervals"]) == len(
        SAMPLE_INDICES
    ) and all(
        interval.get("status") == "closed" for interval in trace["intervals"]
    )
    _write_trace()


def __lldb_init_module(debugger, _internal_dict):
    _state["trace"] = _new_trace()
    _write_trace()
    target = debugger.GetSelectedTarget()
    breakpoint = target.BreakpointCreateByName(BACKGROUND_MANGLED)
    if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
        raise RuntimeError("background function bootstrap is unresolved")
    _set_callback(breakpoint, "bootstrap", "background bootstrap")
    _state["bootstrapBreakpoint"] = breakpoint
    _state["trace"]["breakpoints"]["bootstrap"] = {
        "id": breakpoint.GetID(),
        "requestedName": BACKGROUND_MANGLED,
        "locationCount": breakpoint.GetNumLocations(),
    }
    _state["trace"]["status"] = "bootstrap-armed"
    _write_trace()
