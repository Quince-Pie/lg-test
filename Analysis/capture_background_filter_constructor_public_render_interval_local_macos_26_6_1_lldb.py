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

import lldb

import capture_backdrop_margin_case22_provider_public_render_interval_transfer_local_macos_26_6_1_lldb as public


TRACE_SCHEMA_VERSION = 2

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

RESOLVED_RECIPE_BUILDER_MODULE_OFFSET = 0x120B4C
RESOLVED_RECIPE_BUILDER_BYTE_COUNT = 0x1334
RESOLVED_RECIPE_BUILDER_CODE_SHA256 = (
    "07d9b8571ca8fed42e1d8e71b312f00a9c9713ce19f406d6f2c15a9d2403fde4"
)
RESOLVED_RECIPE_BUILDER_CALLER_MODULE_OFFSET = 0x11F1BC
RESOLVED_RECIPE_BUILDER_CALLER_BYTE_COUNT = 0xD7C
RESOLVED_RECIPE_BUILDER_CALLER_CODE_SHA256 = (
    "ba0ad1081cece802ccd1e148660a542145f95bf57a92de4407a3fad55f4679c6"
)
RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER = 0xD34
RESOLVED_RECIPE_BUILDER_RETURN_OFFSET_IN_CALLER = 0xD38
RESOLVED_RECIPE_BUILDER_CALL_INSTRUCTION_HEX = "17030094"
BLEND_DECISION_OFFSET_IN_BUILDER = 0xFB8
BLEND_FINAL_GATE_OFFSET_IN_BUILDER = 0x1174
BLEND_RESOLVED_OFFSET_IN_BUILDER = 0x118C
BUILDER_FRAME_PARAMETERS_OFFSET = 0x1068
BUILDER_FRAME_ACCUMULATOR_OFFSET = 0x1900
BUILDER_FRAME_WORKING_PARAMETERS_OFFSET = 0xC60
BUILDER_FRAME_COLLECTION_COUNT_OFFSET = 0xB0
BUILDER_FRAME_RESOLVER_FLAG_OFFSET = 0x7C
ANIMATABLE_DATA_BYTE_COUNT = 0x481
MAXIMUM_PARAMETERS_BUILDER_CALLS = 4096
MAXIMUM_BLEND_DECISIONS = 16384

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
    "builderEntryBreakpoint": None,
    "builderReturnBreakpoint": None,
    "blendDecisionBreakpoint": None,
    "blendFinalBreakpoint": None,
    "blendResolvedBreakpoint": None,
    "pendingBuilderCalls": {},
    "unassignedCompletedBuilderCalls": [],
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
            "constructorCallOffsetInProducer": (CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER),
            "constructorReturnOffsetInProducer": (
                CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER
            ),
            "constructorCallInstructionHex": (CONSTRUCTOR_CALL_INSTRUCTION_HEX),
            "parametersByteCount": PARAMETERS_BYTE_COUNT,
            "backgroundFilterByteCount": BACKGROUND_FILTER_BYTE_COUNT,
            "maximumConstructorCalls": MAXIMUM_CONSTRUCTOR_CALLS,
            "resolvedRecipeBuilderModuleOffset": (
                RESOLVED_RECIPE_BUILDER_MODULE_OFFSET
            ),
            "resolvedRecipeBuilderByteCount": (RESOLVED_RECIPE_BUILDER_BYTE_COUNT),
            "resolvedRecipeBuilderCodeSHA256": (RESOLVED_RECIPE_BUILDER_CODE_SHA256),
            "resolvedRecipeBuilderCallerModuleOffset": (
                RESOLVED_RECIPE_BUILDER_CALLER_MODULE_OFFSET
            ),
            "resolvedRecipeBuilderCallerByteCount": (
                RESOLVED_RECIPE_BUILDER_CALLER_BYTE_COUNT
            ),
            "resolvedRecipeBuilderCallerCodeSHA256": (
                RESOLVED_RECIPE_BUILDER_CALLER_CODE_SHA256
            ),
            "resolvedRecipeBuilderCallOffsetInCaller": (
                RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER
            ),
            "resolvedRecipeBuilderReturnOffsetInCaller": (
                RESOLVED_RECIPE_BUILDER_RETURN_OFFSET_IN_CALLER
            ),
            "resolvedRecipeBuilderCallInstructionHex": (
                RESOLVED_RECIPE_BUILDER_CALL_INSTRUCTION_HEX
            ),
            "blendDecisionOffsetInBuilder": BLEND_DECISION_OFFSET_IN_BUILDER,
            "blendFinalGateOffsetInBuilder": BLEND_FINAL_GATE_OFFSET_IN_BUILDER,
            "blendResolvedOffsetInBuilder": BLEND_RESOLVED_OFFSET_IN_BUILDER,
            "builderFrameParametersOffset": BUILDER_FRAME_PARAMETERS_OFFSET,
            "builderFrameAccumulatorOffset": BUILDER_FRAME_ACCUMULATOR_OFFSET,
            "builderFrameWorkingParametersOffset": (
                BUILDER_FRAME_WORKING_PARAMETERS_OFFSET
            ),
            "builderFrameCollectionCountOffset": (
                BUILDER_FRAME_COLLECTION_COUNT_OFFSET
            ),
            "builderFrameResolverFlagOffset": (BUILDER_FRAME_RESOLVER_FLAG_OFFSET),
            "animatableDataByteCount": ANIMATABLE_DATA_BYTE_COUNT,
            "maximumParametersBuilderCalls": MAXIMUM_PARAMETERS_BUILDER_CALLS,
            "maximumBlendDecisions": MAXIMUM_BLEND_DECISIONS,
            "constructorCaptureStartsAtBackgroundFunctionEntry": True,
            "constructorCaptureEndsAtFinalRenderReturn": True,
            "parametersBuilderCaptureStartsAtBackgroundFunctionEntry": True,
            "parametersBuilderCaptureEndsAtFinalRenderReturn": True,
            "preRenderAssignmentRule": (
                "all completed unassigned constructor and Parameters builder "
                "calls are assigned to the immediately following structural "
                "render interval"
            ),
            "capturedParametersUsedForSelection": False,
            "capturedConstructorOutputUsedForSelection": False,
            "capturedProviderObjectUsedForSelection": False,
            "capturedAddressUsedForSelection": False,
            "capturedBlendFactorUsedForSelection": False,
            "capturedBlendCountUsedForSelection": False,
            "capturedAnimatableDataUsedForSelection": False,
            "capturedBuilderOutputUsedForSelection": False,
        }
    )
    trace["constructor"] = {}
    trace["constructorProducer"] = {}
    trace["resolvedRecipeBuilder"] = {}
    trace["resolvedRecipeBuilderCaller"] = {}
    trace["constructorCalls"] = []
    trace["parametersBuilderCalls"] = []
    trace["parametersBlendDecisions"] = []
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


def _read_u32(process, address, label):
    return struct.unpack("<I", base._read_memory(process, address, 4, label))[0]


def _read_u64(process, address, label):
    return struct.unpack("<Q", base._read_memory(process, address, 8, label))[0]


def _register_record(frame, name):
    register = frame.FindRegister(name)
    if not register.IsValid():
        raise RuntimeError("missing register " + name)
    byte_count = register.GetByteSize()
    data = register.GetData()
    if byte_count <= 0 or not data.IsValid() or data.GetByteSize() != byte_count:
        raise RuntimeError("register " + name + " data is unavailable")
    error = lldb.SBError()
    payload = bytearray()
    for offset in range(byte_count):
        payload.append(data.GetUnsignedInt8(error, offset))
        if not error.Success():
            raise RuntimeError(
                "register %s byte %d failed: %s"
                % (name, offset, error.GetCString() or "unknown SBData error")
            )
    return {
        "name": name,
        "byteCount": byte_count,
        "hex": bytes(payload).hex(),
        "valueString": str(register.GetValue() or ""),
    }


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
    builder = _capture_fixed_region(
        process,
        module,
        RESOLVED_RECIPE_BUILDER_MODULE_OFFSET,
        RESOLVED_RECIPE_BUILDER_BYTE_COUNT,
        RESOLVED_RECIPE_BUILDER_CODE_SHA256,
        "ResolvedRecipe Parameters builder",
    )
    builder_caller = _capture_fixed_region(
        process,
        module,
        RESOLVED_RECIPE_BUILDER_CALLER_MODULE_OFFSET,
        RESOLVED_RECIPE_BUILDER_CALLER_BYTE_COUNT,
        RESOLVED_RECIPE_BUILDER_CALLER_CODE_SHA256,
        "ResolvedRecipe Parameters builder caller",
    )
    call_raw = bytes.fromhex(producer["hex"])[
        CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER : CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER + 4
    ]
    call_address = producer["startAddress"] + CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER
    if call_raw.hex() != CONSTRUCTOR_CALL_INSTRUCTION_HEX:
        raise RuntimeError("BackgroundFilter constructor call instruction differs")
    if (
        _decode_direct_branch_target(call_raw, call_address)
        != constructor["startAddress"]
    ):
        raise RuntimeError("BackgroundFilter constructor call target differs")
    builder_call_raw = bytes.fromhex(builder_caller["hex"])[
        RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER : RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER
        + 4
    ]
    builder_call_address = (
        builder_caller["startAddress"] + RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER
    )
    if builder_call_raw.hex() != RESOLVED_RECIPE_BUILDER_CALL_INSTRUCTION_HEX:
        raise RuntimeError("ResolvedRecipe builder call instruction differs")
    if (
        _decode_direct_branch_target(builder_call_raw, builder_call_address)
        != builder["startAddress"]
    ):
        raise RuntimeError("ResolvedRecipe builder call target differs")

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
    builder_entry_breakpoint = _install_breakpoint(
        target,
        builder["startAddress"],
        "parameters_builder_entry",
        "ResolvedRecipe Parameters builder entry",
    )
    blend_decision_breakpoint = _install_breakpoint(
        target,
        builder["startAddress"] + BLEND_DECISION_OFFSET_IN_BUILDER,
        "parameters_blend_decision",
        "Parameters blend decision",
    )
    blend_final_breakpoint = _install_breakpoint(
        target,
        builder["startAddress"] + BLEND_FINAL_GATE_OFFSET_IN_BUILDER,
        "parameters_blend_final",
        "Parameters blend final gate",
    )
    blend_resolved_breakpoint = _install_breakpoint(
        target,
        builder["startAddress"] + BLEND_RESOLVED_OFFSET_IN_BUILDER,
        "parameters_blend_resolved",
        "Parameters blend resolved convergence",
    )
    builder_return_breakpoint = _install_breakpoint(
        target,
        builder_caller["startAddress"]
        + RESOLVED_RECIPE_BUILDER_RETURN_OFFSET_IN_CALLER,
        "parameters_builder_return",
        "ResolvedRecipe Parameters builder return",
    )
    _constructor_state["entryBreakpoint"] = entry
    _constructor_state["returnBreakpoint"] = returned
    _constructor_state["builderEntryBreakpoint"] = builder_entry_breakpoint
    _constructor_state["blendDecisionBreakpoint"] = blend_decision_breakpoint
    _constructor_state["blendFinalBreakpoint"] = blend_final_breakpoint
    _constructor_state["blendResolvedBreakpoint"] = blend_resolved_breakpoint
    _constructor_state["builderReturnBreakpoint"] = builder_return_breakpoint
    _constructor_state["backgroundThreadID"] = frame.GetThread().GetThreadID()

    trace["constructor"] = constructor
    trace["constructorProducer"] = producer
    trace["resolvedRecipeBuilder"] = builder
    trace["resolvedRecipeBuilderCaller"] = builder_caller
    trace["configuration"]["completeProviderObjectByteCount"] = (
        BACKGROUND_FILTER_BYTE_COUNT
    )
    trace["configuration"]["backgroundFunctionThreadID"] = _constructor_state[
        "backgroundThreadID"
    ]
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
                    producer["startAddress"] + CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER
                ),
                "locationCount": returned.GetNumLocations(),
            },
            "parametersBuilderEntry": {
                "id": builder_entry_breakpoint.GetID(),
                "address": builder["startAddress"],
                "locationCount": builder_entry_breakpoint.GetNumLocations(),
            },
            "parametersBlendDecision": {
                "id": blend_decision_breakpoint.GetID(),
                "address": (builder["startAddress"] + BLEND_DECISION_OFFSET_IN_BUILDER),
                "locationCount": blend_decision_breakpoint.GetNumLocations(),
            },
            "parametersBlendFinal": {
                "id": blend_final_breakpoint.GetID(),
                "address": (
                    builder["startAddress"] + BLEND_FINAL_GATE_OFFSET_IN_BUILDER
                ),
                "locationCount": blend_final_breakpoint.GetNumLocations(),
            },
            "parametersBlendResolved": {
                "id": blend_resolved_breakpoint.GetID(),
                "address": (builder["startAddress"] + BLEND_RESOLVED_OFFSET_IN_BUILDER),
                "locationCount": blend_resolved_breakpoint.GetNumLocations(),
            },
            "parametersBuilderReturn": {
                "id": builder_return_breakpoint.GetID(),
                "address": (
                    builder_caller["startAddress"]
                    + RESOLVED_RECIPE_BUILDER_RETURN_OFFSET_IN_CALLER
                ),
                "locationCount": builder_return_breakpoint.GetNumLocations(),
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


def _assign_pre_render_builder_calls(interval):
    pending = _constructor_state["unassignedCompletedBuilderCalls"]
    call_indices = list(pending)
    pending.clear()
    interval["preRenderParametersBuilderCallIndices"] = call_indices
    interval["inRenderParametersBuilderCallIndices"] = []
    calls = public._state["trace"]["parametersBuilderCalls"]
    for call_index in call_indices:
        call = calls[call_index]
        if call.get("returnEventIndex") is None:
            raise RuntimeError("pre-render Parameters builder call has not returned")
        if call.get("assignedIntervalIndex") is not None:
            raise RuntimeError("pre-render Parameters builder was already assigned")
        call["assignedIntervalIndex"] = interval["intervalIndex"]
        call["assignedSampleIndex"] = interval["sampleIndex"]
        call["timingRelativeToRender"] = "pre-render"


def render_call(frame, breakpoint_location, internal_dict):
    if _constructor_state["pendingCalls"] or _constructor_state["pendingBuilderCalls"]:
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
            _assign_pre_render_builder_calls(interval)
    except Exception as error:
        public._failure("constructor-render-call-assignment", error)
    return result


def render_return(frame, breakpoint_location, internal_dict):
    if _constructor_state["pendingCalls"] or _constructor_state["pendingBuilderCalls"]:
        public._failure(
            "constructor-render-return",
            RuntimeError("render return closed with an unfinished constructor call"),
        )
        return False
    result = _PUBLIC_RENDER_RETURN(frame, breakpoint_location, internal_dict)
    trace = public._state["trace"]
    if public._state["activeInterval"] is None and len(trace["intervals"]) == len(
        public.SAMPLE_INDICES
    ):
        _constructor_state["entryBreakpoint"].SetEnabled(False)
        _constructor_state["returnBreakpoint"].SetEnabled(False)
        _constructor_state["builderEntryBreakpoint"].SetEnabled(False)
        _constructor_state["blendDecisionBreakpoint"].SetEnabled(False)
        _constructor_state["blendFinalBreakpoint"].SetEnabled(False)
        _constructor_state["blendResolvedBreakpoint"].SetEnabled(False)
        _constructor_state["builderReturnBreakpoint"].SetEnabled(False)
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


def parameters_builder_entry(frame, _breakpoint_location, _internal_dict):
    try:
        trace = public._state["trace"]
        calls = trace["parametersBuilderCalls"]
        if len(calls) >= MAXIMUM_PARAMETERS_BUILDER_CALLS:
            raise RuntimeError("Parameters builder call bound exceeded")
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        if thread_id in _constructor_state["pendingBuilderCalls"]:
            raise RuntimeError("nested Parameters builder call occurred on one thread")
        if frame.GetPC() != trace["resolvedRecipeBuilder"]["startAddress"]:
            raise RuntimeError("Parameters builder entry PC differs")

        output_address = base._register_u64(frame, "x8")
        if output_address <= 0:
            raise RuntimeError("Parameters builder output address differs")
        interval_index = public._state["activeInterval"]
        call_index = len(calls)
        call = {
            "builderCallIndex": call_index,
            "threadID": thread_id,
            "onBackgroundFunctionThread": (
                thread_id == _constructor_state["backgroundThreadID"]
            ),
            "entryEventIndex": None,
            "finalEventIndex": None,
            "resolvedEventIndex": None,
            "returnEventIndex": None,
            "entryFrame": case22._frame_record(frame),
            "inputX0RawValue": base._register_u64(frame, "x0"),
            "inputX1RawValue": base._register_u64(frame, "x1"),
            "inputX2RawValue": base._register_u64(frame, "x2"),
            "outputParametersAddress": output_address,
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
            "decisionIndices": [],
            "finalFrame": None,
            "frameBaseAtFinalGate": None,
            "resolverFlagAtFinalGate": None,
            "preResolverWorkingParameters": None,
            "accumulatorAnimatableDataAtFinalGate": None,
            "resolvedFrame": None,
            "frameBaseAtResolvedConvergence": None,
            "resolvedWorkingParameters": None,
            "returnFrame": None,
            "outputParametersAtReturn": None,
        }
        calls.append(call)
        if interval_index is not None:
            trace["intervals"][interval_index][
                "inRenderParametersBuilderCallIndices"
            ].append(call_index)
        call["entryEventIndex"] = public._append_event(
            "parameters-builder-entry", call_index
        )
        _constructor_state["pendingBuilderCalls"][thread_id] = call_index
        if len(calls) % 16 == 0:
            public._write_trace()
    except Exception as error:
        public._failure("parameters-builder-entry", error)
    return False


def parameters_blend_decision(frame, _breakpoint_location, _internal_dict):
    try:
        trace = public._state["trace"]
        decisions = trace["parametersBlendDecisions"]
        if len(decisions) >= MAXIMUM_BLEND_DECISIONS:
            raise RuntimeError("Parameters blend decision bound exceeded")
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        call_index = _constructor_state["pendingBuilderCalls"].get(thread_id)
        if call_index is None:
            raise RuntimeError("Parameters blend decision has no active builder")
        expected_pc = (
            trace["resolvedRecipeBuilder"]["startAddress"]
            + BLEND_DECISION_OFFSET_IN_BUILDER
        )
        if frame.GetPC() != expected_pc:
            raise RuntimeError("Parameters blend decision PC differs")

        process = thread.GetProcess()
        frame_base = base._register_u64(frame, "x19")
        if frame_base <= 0:
            raise RuntimeError("Parameters blend frame base differs")
        decision_index = len(decisions)
        decision = {
            "decisionIndex": decision_index,
            "builderCallIndex": call_index,
            "threadID": thread_id,
            "eventIndex": None,
            "frame": case22._frame_record(frame),
            "frameBase": frame_base,
            "collectionCount": _read_u64(
                process,
                frame_base + BUILDER_FRAME_COLLECTION_COUNT_OFFSET,
                "Parameters blend collection count",
            ),
            "resolverFlagBeforeDecision": _read_u32(
                process,
                frame_base + BUILDER_FRAME_RESOLVER_FLAG_OFFSET,
                "Parameters blend resolver flag",
            ),
            "factorD9": _register_record(frame, "d9"),
            "unityD12": _register_record(frame, "d12"),
            "currentParameters": case22._snapshot(
                process,
                frame_base + BUILDER_FRAME_PARAMETERS_OFFSET,
                PARAMETERS_BYTE_COUNT,
                "current Parameters before blend decision",
            ),
            "priorAccumulatorAnimatableData": case22._snapshot(
                process,
                frame_base + BUILDER_FRAME_ACCUMULATOR_OFFSET,
                ANIMATABLE_DATA_BYTE_COUNT,
                "prior Parameters AnimatableData accumulator",
            ),
        }
        decisions.append(decision)
        trace["parametersBuilderCalls"][call_index]["decisionIndices"].append(
            decision_index
        )
        decision["eventIndex"] = public._append_event(
            "parameters-blend-decision", decision_index
        )
        if len(decisions) % 32 == 0:
            public._write_trace()
    except Exception as error:
        public._failure("parameters-blend-decision", error)
    return False


def parameters_blend_final(frame, _breakpoint_location, _internal_dict):
    try:
        trace = public._state["trace"]
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        call_index = _constructor_state["pendingBuilderCalls"].get(thread_id)
        if call_index is None:
            raise RuntimeError("Parameters blend final gate has no active builder")
        expected_pc = (
            trace["resolvedRecipeBuilder"]["startAddress"]
            + BLEND_FINAL_GATE_OFFSET_IN_BUILDER
        )
        if frame.GetPC() != expected_pc:
            raise RuntimeError("Parameters blend final gate PC differs")
        call = trace["parametersBuilderCalls"][call_index]
        if call["finalEventIndex"] is not None:
            raise RuntimeError("Parameters builder reached final gate more than once")

        process = thread.GetProcess()
        frame_base = base._register_u64(frame, "x19")
        if frame_base <= 0:
            raise RuntimeError("Parameters final-gate frame base differs")
        call["finalFrame"] = case22._frame_record(frame)
        call["frameBaseAtFinalGate"] = frame_base
        call["resolverFlagAtFinalGate"] = _read_u32(
            process,
            frame_base + BUILDER_FRAME_RESOLVER_FLAG_OFFSET,
            "Parameters final resolver flag",
        )
        call["preResolverWorkingParameters"] = case22._snapshot(
            process,
            frame_base + BUILDER_FRAME_WORKING_PARAMETERS_OFFSET,
            PARAMETERS_BYTE_COUNT,
            "pre-resolver working Parameters",
        )
        call["accumulatorAnimatableDataAtFinalGate"] = case22._snapshot(
            process,
            frame_base + BUILDER_FRAME_ACCUMULATOR_OFFSET,
            ANIMATABLE_DATA_BYTE_COUNT,
            "Parameters AnimatableData accumulator at final gate",
        )
        call["finalEventIndex"] = public._append_event(
            "parameters-blend-final", call_index
        )
    except Exception as error:
        public._failure("parameters-blend-final", error)
    return False


def parameters_blend_resolved(frame, _breakpoint_location, _internal_dict):
    try:
        trace = public._state["trace"]
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        call_index = _constructor_state["pendingBuilderCalls"].get(thread_id)
        if call_index is None:
            raise RuntimeError("Parameters resolved convergence has no active builder")
        expected_pc = (
            trace["resolvedRecipeBuilder"]["startAddress"]
            + BLEND_RESOLVED_OFFSET_IN_BUILDER
        )
        if frame.GetPC() != expected_pc:
            raise RuntimeError("Parameters resolved convergence PC differs")
        call = trace["parametersBuilderCalls"][call_index]
        if call["finalEventIndex"] is None:
            raise RuntimeError("Parameters resolved before its final gate")
        if call["resolvedEventIndex"] is not None:
            raise RuntimeError(
                "Parameters builder reached resolved convergence more than once"
            )

        process = thread.GetProcess()
        frame_base = base._register_u64(frame, "x19")
        if frame_base <= 0:
            raise RuntimeError("Parameters resolved frame base differs")
        call["resolvedFrame"] = case22._frame_record(frame)
        call["frameBaseAtResolvedConvergence"] = frame_base
        call["resolvedWorkingParameters"] = case22._snapshot(
            process,
            frame_base + BUILDER_FRAME_WORKING_PARAMETERS_OFFSET,
            PARAMETERS_BYTE_COUNT,
            "resolved working Parameters",
        )
        call["resolvedEventIndex"] = public._append_event(
            "parameters-blend-resolved", call_index
        )
    except Exception as error:
        public._failure("parameters-blend-resolved", error)
    return False


def parameters_builder_return(frame, _breakpoint_location, _internal_dict):
    try:
        trace = public._state["trace"]
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        call_index = _constructor_state["pendingBuilderCalls"].pop(thread_id, None)
        if call_index is None:
            return False
        expected_pc = (
            trace["resolvedRecipeBuilderCaller"]["startAddress"]
            + RESOLVED_RECIPE_BUILDER_RETURN_OFFSET_IN_CALLER
        )
        if frame.GetPC() != expected_pc:
            raise RuntimeError("Parameters builder return PC differs")
        call = trace["parametersBuilderCalls"][call_index]
        if call["resolvedEventIndex"] is None:
            raise RuntimeError(
                "Parameters builder returned before resolved convergence"
            )
        process = thread.GetProcess()
        call["returnFrame"] = case22._frame_record(frame)
        call["outputParametersAtReturn"] = case22._snapshot(
            process,
            call["outputParametersAddress"],
            PARAMETERS_BYTE_COUNT,
            "Parameters builder output",
        )
        call["returnEventIndex"] = public._append_event(
            "parameters-builder-return", call_index
        )
        if call["assignedIntervalIndex"] is None:
            _constructor_state["unassignedCompletedBuilderCalls"].append(call_index)
    except Exception as error:
        public._failure("parameters-builder-return", error)
    return False


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
            trace["intervals"][interval_index]["inRenderConstructorCallIndices"].append(
                call_index
            )
        call["entryEventIndex"] = public._append_event("constructor-entry", call_index)
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
        trace["finalParametersBuilderCallCount"] = len(trace["parametersBuilderCalls"])
        trace["finalBlendDecisionCount"] = len(trace["parametersBlendDecisions"])
        trace["finalPendingParametersBuilderCallCount"] = len(
            _constructor_state["pendingBuilderCalls"]
        )
        trace["finalUnassignedParametersBuilderCallCount"] = len(
            _constructor_state["unassignedCompletedBuilderCalls"]
        )
        trace["allParametersBuilderCallsReachedFinalGate"] = all(
            call.get("finalEventIndex") is not None
            for call in trace["parametersBuilderCalls"]
        )
        trace["allParametersBuilderCallsReachedResolvedConvergence"] = all(
            call.get("resolvedEventIndex") is not None
            for call in trace["parametersBuilderCalls"]
        )
        trace["allParametersBuilderCallsReturned"] = all(
            call.get("returnEventIndex") is not None
            for call in trace["parametersBuilderCalls"]
        )
        trace["allParametersBuilderCallsAssigned"] = all(
            call.get("assignedIntervalIndex") is not None
            for call in trace["parametersBuilderCalls"]
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
