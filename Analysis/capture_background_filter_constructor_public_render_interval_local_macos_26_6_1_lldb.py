"""Capture BackgroundFilter construction and its public render consumers.

The unchanged application function is entered before any of its 32 sample
iterations.  Constructor calls are retained from that entry through the last
authenticated CARenderer interval.  Calls completed before a render are
assigned to the immediately following interval by event order; calls made
inside a render retain that interval directly.  Captured bytes never select a
call, interval, address, field, or value.
"""

import hashlib
import os
import struct
from pathlib import Path

import capture_backdrop_margin_case22_provider_public_render_interval_transfer_local_macos_26_6_1_lldb as public


TRACE_SCHEMA_VERSION = 1

DESIGN_LIBRARY_UUID = "1E980802-69F5-3E69-89EF-50088297FCF5"

CONSTRUCTOR_MODULE_OFFSET = 0xBAD00
CONSTRUCTOR_BYTE_COUNT = 0x414
CONSTRUCTOR_CODE_SHA256 = (
    "71a592bc8a187fe8bcca0fa50c3f4d36ea3c2916dbd5d16f3fa1df05b86f131d"
)

PRODUCER_MODULE_OFFSET = 0xB7FA8
PRODUCER_BYTE_COUNT = 0x66C
PRODUCER_CODE_SHA256 = (
    "0729f7b0f874c0fb9fb64fa3383a6f2ed328d1dc55fdce53b82038a188df6f97"
)
CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER = 0x38C
CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER = 0x390
CONSTRUCTOR_CALL_INSTRUCTION_HEX = "730a0094"

PARAMETERS_BYTE_COUNT = 0x401
BACKGROUND_FILTER_BYTE_COUNT = 0x1F8
MAXIMUM_CONSTRUCTOR_CALLS = 4096

_PUBLIC_NEW_TRACE = public._new_trace
_PUBLIC_INSTALL_CAPTURE = public._install_capture
_PUBLIC_RENDER_CALL = public.render_call
_PUBLIC_RENDER_RETURN = public.render_return
_PUBLIC_PROVIDER_ENTRY = public.provider_entry
_PUBLIC_PROVIDER_RETURN = public.provider_return
_PUBLIC_FINALIZE = public.finalize

base = public.base
case22 = public.case22

_constructor_state = {
    "entryBreakpoint": None,
    "returnBreakpoint": None,
    "pendingCalls": {},
    "unassignedCompletedCalls": [],
    "backgroundThreadID": None,
}


def _trace_path():
    raw = os.environ.get(
        "LG_BACKGROUND_FILTER_CONSTRUCTOR_PUBLIC_RENDER_INTERVAL_TRACE_OUTPUT"
    )
    if not raw:
        raise RuntimeError(
            "LG_BACKGROUND_FILTER_CONSTRUCTOR_PUBLIC_RENDER_INTERVAL_TRACE_OUTPUT "
            "is required"
        )
    return Path(raw)


def _new_trace():
    trace = _PUBLIC_NEW_TRACE()
    trace[
        "backgroundFilterConstructorPublicRenderIntervalLocalMacOSLldbTraceSchemaVersion"
    ] = TRACE_SCHEMA_VERSION
    trace["classification"] = (
        "prospectively frozen value-blind capture of every DesignLibrary "
        "BackgroundFilter constructor call from exact public sample-function "
        "entry through the final authenticated carrier-render interval"
    )
    trace["configuration"].update(
        {
            "designLibraryUUID": DESIGN_LIBRARY_UUID,
            "constructorModuleOffset": CONSTRUCTOR_MODULE_OFFSET,
            "constructorByteCount": CONSTRUCTOR_BYTE_COUNT,
            "constructorCodeSHA256": CONSTRUCTOR_CODE_SHA256,
            "producerModuleOffset": PRODUCER_MODULE_OFFSET,
            "producerByteCount": PRODUCER_BYTE_COUNT,
            "producerCodeSHA256": PRODUCER_CODE_SHA256,
            "constructorCallOffsetInProducer": (
                CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER
            ),
            "constructorReturnOffsetInProducer": (
                CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER
            ),
            "constructorCallInstructionHex": (
                CONSTRUCTOR_CALL_INSTRUCTION_HEX
            ),
            "parametersByteCount": PARAMETERS_BYTE_COUNT,
            "backgroundFilterByteCount": BACKGROUND_FILTER_BYTE_COUNT,
            "maximumConstructorCalls": MAXIMUM_CONSTRUCTOR_CALLS,
            "constructorCaptureStartsAtBackgroundFunctionEntry": True,
            "constructorCaptureEndsAtFinalRenderReturn": True,
            "preRenderAssignmentRule": (
                "all completed unassigned constructor calls are assigned to "
                "the immediately following structural render interval"
            ),
            "capturedParametersUsedForSelection": False,
            "capturedConstructorOutputUsedForSelection": False,
            "capturedProviderObjectUsedForSelection": False,
            "capturedAddressUsedForSelection": False,
        }
    )
    trace["constructor"] = {}
    trace["constructorProducer"] = {}
    trace["constructorCalls"] = []
    return trace


def _capture_fixed_region(process, module, offset, byte_count, digest, label):
    if (
        module.get("uuid") != DESIGN_LIBRARY_UUID
        or not str(module.get("path", "")).endswith("/DesignLibrary")
        or not isinstance(module.get("loadAddress"), int)
        or module["loadAddress"] <= 0
    ):
        raise RuntimeError(label + " DesignLibrary identity differs")
    address = module["loadAddress"] + offset
    payload = base._read_memory(process, address, byte_count, label + " code")
    observed = hashlib.sha256(payload).hexdigest()
    if observed != digest:
        raise RuntimeError(label + " complete-code SHA-256 differs")
    return {
        "startAddress": address,
        "endAddress": address + byte_count,
        "moduleOffset": offset,
        "byteCount": byte_count,
        "sha256": observed,
        "hex": payload.hex(),
        "module": module,
    }


def _decode_direct_branch_target(instruction_raw, instruction_address):
    if len(instruction_raw) != 4:
        raise RuntimeError("constructor call instruction width differs")
    instruction = struct.unpack("<I", instruction_raw)[0]
    if instruction >> 26 != 0b100101:
        raise RuntimeError("constructor callsite is not ARM64 BL")
    displacement = instruction & 0x03FFFFFF
    if displacement & (1 << 25):
        displacement -= 1 << 26
    return instruction_address + displacement * 4


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _install_breakpoint(target, address, callback, label):
    breakpoint = target.BreakpointCreateByAddress(address)
    if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
        raise RuntimeError(label + " breakpoint is unresolved")
    _set_callback(breakpoint, callback, label)
    breakpoint.SetEnabled(True)
    return breakpoint


def _install_capture(frame):
    _PUBLIC_INSTALL_CAPTURE(frame)
    if _constructor_state["entryBreakpoint"] is not None:
        raise RuntimeError("constructor capture installation repeated")

    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    trace = public._state["trace"]
    module = trace["modules"]["designLibrary"]
    constructor = _capture_fixed_region(
        process,
        module,
        CONSTRUCTOR_MODULE_OFFSET,
        CONSTRUCTOR_BYTE_COUNT,
        CONSTRUCTOR_CODE_SHA256,
        "BackgroundFilter constructor",
    )
    producer = _capture_fixed_region(
        process,
        module,
        PRODUCER_MODULE_OFFSET,
        PRODUCER_BYTE_COUNT,
        PRODUCER_CODE_SHA256,
        "BackgroundFilter producer",
    )
    call_raw = bytes.fromhex(producer["hex"])[
        CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER :
        CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER + 4
    ]
    call_address = producer["startAddress"] + CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER
    if call_raw.hex() != CONSTRUCTOR_CALL_INSTRUCTION_HEX:
        raise RuntimeError("BackgroundFilter constructor call instruction differs")
    if (
        _decode_direct_branch_target(call_raw, call_address)
        != constructor["startAddress"]
    ):
        raise RuntimeError("BackgroundFilter constructor call target differs")

    entry = _install_breakpoint(
        target,
        constructor["startAddress"],
        "constructor_entry",
        "BackgroundFilter constructor entry",
    )
    returned = _install_breakpoint(
        target,
        producer["startAddress"] + CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER,
        "constructor_return",
        "BackgroundFilter constructor return",
    )
    _constructor_state["entryBreakpoint"] = entry
    _constructor_state["returnBreakpoint"] = returned
    _constructor_state["backgroundThreadID"] = frame.GetThread().GetThreadID()

    trace["constructor"] = constructor
    trace["constructorProducer"] = producer
    trace["configuration"]["completeProviderObjectByteCount"] = (
        BACKGROUND_FILTER_BYTE_COUNT
    )
    trace["configuration"]["backgroundFunctionThreadID"] = (
        _constructor_state["backgroundThreadID"]
    )
    trace["breakpoints"].update(
        {
            "constructorEntry": {
                "id": entry.GetID(),
                "address": constructor["startAddress"],
                "locationCount": entry.GetNumLocations(),
            },
            "constructorReturn": {
                "id": returned.GetID(),
                "address": (
                    producer["startAddress"]
                    + CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER
                ),
                "locationCount": returned.GetNumLocations(),
            },
        }
    )


def _assign_pre_render_calls(interval):
    pending = _constructor_state["unassignedCompletedCalls"]
    call_indices = list(pending)
    pending.clear()
    interval["preRenderConstructorCallIndices"] = call_indices
    interval["inRenderConstructorCallIndices"] = []
    calls = public._state["trace"]["constructorCalls"]
    for call_index in call_indices:
        call = calls[call_index]
        if call.get("returnEventIndex") is None:
            raise RuntimeError("pre-render constructor call has not returned")
        if call.get("assignedIntervalIndex") is not None:
            raise RuntimeError("pre-render constructor call was already assigned")
        call["assignedIntervalIndex"] = interval["intervalIndex"]
        call["assignedSampleIndex"] = interval["sampleIndex"]
        call["timingRelativeToRender"] = "pre-render"


def render_call(frame, breakpoint_location, internal_dict):
    if _constructor_state["pendingCalls"]:
        public._failure(
            "constructor-render-call",
            RuntimeError("render call opened with an unfinished constructor call"),
        )
        return False
    result = _PUBLIC_RENDER_CALL(frame, breakpoint_location, internal_dict)
    try:
        interval_index = public._state["activeInterval"]
        if interval_index is not None:
            interval = public._state["trace"]["intervals"][interval_index]
            _assign_pre_render_calls(interval)
    except Exception as error:
        public._failure("constructor-render-call-assignment", error)
    return result


def render_return(frame, breakpoint_location, internal_dict):
    if _constructor_state["pendingCalls"]:
        public._failure(
            "constructor-render-return",
            RuntimeError("render return closed with an unfinished constructor call"),
        )
        return False
    result = _PUBLIC_RENDER_RETURN(frame, breakpoint_location, internal_dict)
    trace = public._state["trace"]
    if (
        public._state["activeInterval"] is None
        and len(trace["intervals"]) == len(public.SAMPLE_INDICES)
    ):
        _constructor_state["entryBreakpoint"].SetEnabled(False)
        _constructor_state["returnBreakpoint"].SetEnabled(False)
    return result


def provider_entry(frame, breakpoint_location, internal_dict):
    trace = public._state["trace"]
    call_count = len(trace["calls"])
    result = _PUBLIC_PROVIDER_ENTRY(frame, breakpoint_location, internal_dict)
    try:
        if len(trace["calls"]) == call_count + 1:
            call = trace["calls"][-1]
            process = frame.GetThread().GetProcess()
            call["providerObjectComplete"] = case22._snapshot(
                process,
                call["providerObjectAddress"],
                BACKGROUND_FILTER_BYTE_COUNT,
                "complete public render-interval provider object",
            )
            call["returnObjectComplete"] = None
            call["completeObjectChanged"] = None
    except Exception as error:
        public._failure("complete-provider-entry", error)
    return result


def provider_return(frame, breakpoint_location, internal_dict):
    thread_id = frame.GetThread().GetThreadID()
    call_index = public._state["pendingCalls"].get(thread_id)
    result = _PUBLIC_PROVIDER_RETURN(frame, breakpoint_location, internal_dict)
    try:
        if call_index is not None:
            trace = public._state["trace"]
            call = trace["calls"][call_index]
            process = frame.GetThread().GetProcess()
            returned = case22._snapshot(
                process,
                call["providerObjectAddress"],
                BACKGROUND_FILTER_BYTE_COUNT,
                "complete returned public render-interval provider object",
            )
            call["returnObjectComplete"] = returned
            call["completeObjectChanged"] = (
                returned["hex"] != call["providerObjectComplete"]["hex"]
            )
    except Exception as error:
        public._failure("complete-provider-return", error)
    return result


def constructor_entry(frame, _breakpoint_location, _internal_dict):
    try:
        trace = public._state["trace"]
        calls = trace["constructorCalls"]
        if len(calls) >= MAXIMUM_CONSTRUCTOR_CALLS:
            raise RuntimeError("BackgroundFilter constructor call bound exceeded")
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        if thread_id in _constructor_state["pendingCalls"]:
            raise RuntimeError("nested constructor call occurred on one thread")
        if frame.GetPC() != trace["constructor"]["startAddress"]:
            raise RuntimeError("BackgroundFilter constructor entry PC differs")

        process = thread.GetProcess()
        parameters_address = base._register_u64(frame, "x0")
        layer_index = base._register_u64(frame, "x1")
        flags_raw_value = base._register_u64(frame, "x2")
        output_address = base._register_u64(frame, "x8")
        interval_index = public._state["activeInterval"]
        call_index = len(calls)
        call = {
            "callIndex": call_index,
            "threadID": thread_id,
            "onBackgroundFunctionThread": (
                thread_id == _constructor_state["backgroundThreadID"]
            ),
            "entryEventIndex": None,
            "returnEventIndex": None,
            "entryFrame": case22._frame_record(frame),
            "parametersAddress": parameters_address,
            "parametersAtEntry": case22._snapshot(
                process,
                parameters_address,
                PARAMETERS_BYTE_COUNT,
                "BackgroundFilter Parameters at constructor entry",
            ),
            "layerIndex": layer_index,
            "flagsRawValue": flags_raw_value,
            "outputAddress": output_address,
            "assignedIntervalIndex": interval_index,
            "assignedSampleIndex": (
                trace["intervals"][interval_index]["sampleIndex"]
                if interval_index is not None
                else None
            ),
            "timingRelativeToRender": (
                "in-render" if interval_index is not None else None
            ),
            "structuralNextSampleIndexAtEntry": (
                len(trace["intervals"]) + 1
                if interval_index is None
                and len(trace["intervals"]) < len(public.SAMPLE_INDICES)
                else None
            ),
            "returnFrame": None,
            "parametersAtReturn": None,
            "parametersChanged": None,
            "outputAtReturn": None,
        }
        calls.append(call)
        if interval_index is not None:
            trace["intervals"][interval_index][
                "inRenderConstructorCallIndices"
            ].append(call_index)
        call["entryEventIndex"] = public._append_event(
            "constructor-entry", call_index
        )
        _constructor_state["pendingCalls"][thread_id] = call_index
        if len(calls) % 16 == 0:
            public._write_trace()
    except Exception as error:
        public._failure("constructor-entry", error)
    return False


def constructor_return(frame, _breakpoint_location, _internal_dict):
    try:
        trace = public._state["trace"]
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        call_index = _constructor_state["pendingCalls"].pop(thread_id, None)
        if call_index is None:
            return False
        call = trace["constructorCalls"][call_index]
        expected_pc = (
            trace["constructorProducer"]["startAddress"]
            + CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER
        )
        if frame.GetPC() != expected_pc:
            raise RuntimeError("BackgroundFilter constructor return PC differs")
        process = thread.GetProcess()
        parameters = case22._snapshot(
            process,
            call["parametersAddress"],
            PARAMETERS_BYTE_COUNT,
            "BackgroundFilter Parameters at constructor return",
        )
        output = case22._snapshot(
            process,
            call["outputAddress"],
            BACKGROUND_FILTER_BYTE_COUNT,
            "BackgroundFilter constructor output",
        )
        call["returnFrame"] = case22._frame_record(frame)
        call["parametersAtReturn"] = parameters
        call["parametersChanged"] = (
            parameters["hex"] != call["parametersAtEntry"]["hex"]
        )
        call["outputAtReturn"] = output
        call["returnEventIndex"] = public._append_event(
            "constructor-return", call_index
        )
        if call["assignedIntervalIndex"] is None:
            _constructor_state["unassignedCompletedCalls"].append(call_index)
    except Exception as error:
        public._failure("constructor-return", error)
    return False


def finalize():
    trace = public._state["trace"]
    if trace is not None:
        trace["finalConstructorCallCount"] = len(trace["constructorCalls"])
        trace["finalPendingConstructorCallCount"] = len(
            _constructor_state["pendingCalls"]
        )
        trace["finalUnassignedConstructorCallCount"] = len(
            _constructor_state["unassignedCompletedCalls"]
        )
        trace["allConstructorCallsReturned"] = all(
            call.get("returnEventIndex") is not None
            for call in trace["constructorCalls"]
        )
        trace["allConstructorCallsAssigned"] = all(
            call.get("assignedIntervalIndex") is not None
            for call in trace["constructorCalls"]
        )
    _PUBLIC_FINALIZE()


def __lldb_init_module(debugger, internal_dict):
    public._trace_path = _trace_path
    public._new_trace = _new_trace
    public._install_capture = _install_capture
    public.render_call = render_call
    public.render_return = render_return
    public.provider_entry = provider_entry
    public.provider_return = provider_return
    public.finalize = finalize
    public.__lldb_init_module(debugger, internal_dict)
