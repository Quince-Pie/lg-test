"""Capture the exact live Parameters -> constructor -> provider chain.

The predecessor census proved a strict one-to-one sequence for every observed
render.  This successor therefore uses four stops per chain: the fixed
ResolvedRecipe builder call and return, the fixed BackgroundFilter constructor
call, and the exact provider entry.  It captures complete values but selects
calls exclusively by authenticated control flow, thread identity, event order,
and timeline-marker ordinal.

LLDB imports this module with Apple's system Python 3.9.
"""

import json
import os
from pathlib import Path

import capture_backdrop_margin_case22_provider_timeline_marker_transfer_local_macos_26_6_1_lldb as timeline
import capture_background_filter_constructor_public_render_interval_local_macos_26_6_1_lldb as parked


TRACE_SCHEMA_VERSION = 1
TRACE_OUTPUT_ENVIRONMENT = (
    "LG_BACKGROUND_FILTER_CONSTRUCTOR_TIMELINE_MARKER_DIRECT_JOIN_TRACE_OUTPUT"
)
MAXIMUM_CHAIN_COUNT = 4096

field = timeline.field
case22 = timeline.case22
base = parked.base

_state = {
    "trace": None,
    "pendingByThread": {},
    "lastMarkerCallCount": 0,
    "markerBreakpoint": None,
    "builderCallsiteBreakpoint": None,
    "builderReturnBreakpoint": None,
    "constructorCallsiteBreakpoint": None,
    "providerEntryBreakpoint": None,
    "captureEnabled": False,
    "finalMarkerObserved": False,
    "ignoredProviderEntryCount": 0,
}


def _trace_path():
    raw = os.environ.get(TRACE_OUTPUT_ENVIRONMENT)
    if not raw:
        raise RuntimeError(TRACE_OUTPUT_ENVIRONMENT + " is required")
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
        "backgroundFilterConstructorTimelineMarkerDirectJoinLocalMacOSLldbTraceSchemaVersion": (
            TRACE_SCHEMA_VERSION
        ),
        "classification": (
            "prospectively frozen value-blind four-stop direct join from the "
            "live ResolvedRecipe Parameters builder through BackgroundFilter "
            "construction to exact provider entry, segmented only by exact "
            "public timeline marker ordinal"
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
            "mainUUID": timeline.MAIN_UUID,
            "timelineMarkerModuleOffset": timeline.TIMELINE_MARKER_MODULE_OFFSET,
            "timelineMarkerByteCount": timeline.TIMELINE_MARKER_BYTE_COUNT,
            "timelineMarkerCodeSHA256": timeline.TIMELINE_MARKER_CODE_SHA256,
            "timelineMarkerCount": timeline.TIMELINE_MARKER_COUNT,
            "designLibraryUUID": parked.DESIGN_LIBRARY_UUID,
            "constructorModuleOffset": parked.CONSTRUCTOR_MODULE_OFFSET,
            "constructorByteCount": parked.CONSTRUCTOR_BYTE_COUNT,
            "constructorCodeSHA256": parked.CONSTRUCTOR_CODE_SHA256,
            "producerModuleOffset": parked.PRODUCER_MODULE_OFFSET,
            "producerByteCount": parked.PRODUCER_BYTE_COUNT,
            "producerCodeSHA256": parked.PRODUCER_CODE_SHA256,
            "constructorCallOffsetInProducer": (
                parked.CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER
            ),
            "constructorReturnOffsetInProducer": (
                parked.CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER
            ),
            "constructorCallInstructionHex": (
                parked.CONSTRUCTOR_CALL_INSTRUCTION_HEX
            ),
            "resolvedRecipeBuilderModuleOffset": (
                parked.RESOLVED_RECIPE_BUILDER_MODULE_OFFSET
            ),
            "resolvedRecipeBuilderByteCount": (
                parked.RESOLVED_RECIPE_BUILDER_BYTE_COUNT
            ),
            "resolvedRecipeBuilderCodeSHA256": (
                parked.RESOLVED_RECIPE_BUILDER_CODE_SHA256
            ),
            "resolvedRecipeBuilderCallerModuleOffset": (
                parked.RESOLVED_RECIPE_BUILDER_CALLER_MODULE_OFFSET
            ),
            "resolvedRecipeBuilderCallerByteCount": (
                parked.RESOLVED_RECIPE_BUILDER_CALLER_BYTE_COUNT
            ),
            "resolvedRecipeBuilderCallerCodeSHA256": (
                parked.RESOLVED_RECIPE_BUILDER_CALLER_CODE_SHA256
            ),
            "resolvedRecipeBuilderCallOffsetInCaller": (
                parked.RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER
            ),
            "resolvedRecipeBuilderReturnOffsetInCaller": (
                parked.RESOLVED_RECIPE_BUILDER_RETURN_OFFSET_IN_CALLER
            ),
            "resolvedRecipeBuilderCallInstructionHex": (
                parked.RESOLVED_RECIPE_BUILDER_CALL_INSTRUCTION_HEX
            ),
            "parametersByteCount": parked.PARAMETERS_BYTE_COUNT,
            "backgroundFilterByteCount": parked.BACKGROUND_FILTER_BYTE_COUNT,
            "maximumChainCount": MAXIMUM_CHAIN_COUNT,
            "captureEnabledAfterMarkerIndex": 0,
            "captureDisabledAtMarkerIndex": 32,
            "stopsPerSelectedChain": 4,
            "expectedControlFlowSequence": [
                "parameters-builder-call",
                "parameters-builder-return",
                "constructor-call",
                "provider-entry",
            ],
            "capturedParametersUsedForSelection": False,
            "capturedConstructorOutputUsedForSelection": False,
            "capturedProviderObjectUsedForSelection": False,
            "capturedRegisterArgumentUsedForSelection": False,
            "capturedAddressUsedForSelection": False,
            "capturedImageUsedForSelection": False,
            "capturedPixelUsedForSelection": False,
        },
        "modules": {},
        "timelineMarkerFunction": {},
        "constructor": {},
        "constructorProducer": {},
        "resolvedRecipeBuilder": {},
        "resolvedRecipeBuilderCaller": {},
        "provider": {},
        "breakpoints": [],
        "events": [],
        "timelineMarkers": [],
        "chains": [],
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


def _install_breakpoint(target, address, callback, label, enabled):
    breakpoint = target.BreakpointCreateByAddress(address)
    if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
        raise RuntimeError(label + " breakpoint is unresolved")
    _set_callback(breakpoint, callback, label)
    breakpoint.SetEnabled(enabled)
    return breakpoint


def _append_event(kind, record_index):
    events = _state["trace"]["events"]
    event = {
        "eventIndex": len(events),
        "kind": kind,
        "recordIndex": record_index,
    }
    events.append(event)
    return event["eventIndex"]


def _set_window_capture_enabled(enabled):
    _state["builderCallsiteBreakpoint"].SetEnabled(enabled)
    _state["builderReturnBreakpoint"].SetEnabled(enabled)
    _state["constructorCallsiteBreakpoint"].SetEnabled(enabled)
    _state["captureEnabled"] = enabled
    if not enabled and not _state["pendingByThread"]:
        _state["providerEntryBreakpoint"].SetEnabled(False)


def _capture_marker_function(frame):
    timeline._capture_marker_function(frame)


def timeline_marker(frame, _breakpoint_location, _internal_dict):
    try:
        trace = _state["trace"]
        markers = trace["timelineMarkers"]
        marker_index = len(markers)
        if marker_index >= timeline.TIMELINE_MARKER_COUNT:
            raise RuntimeError("timeline marker count exceeded")
        if frame.GetPC() != (
            trace["modules"]["main"]["loadAddress"]
            + timeline.TIMELINE_MARKER_MODULE_OFFSET
        ):
            raise RuntimeError("timeline marker PC differs")
        if _state["pendingByThread"]:
            raise RuntimeError("timeline marker crossed an active direct chain")
        if marker_index == 0:
            _capture_marker_function(frame)
        start = _state["lastMarkerCallCount"]
        end = len(trace["chains"])
        marker = {
            "markerIndex": marker_index,
            "sampleIndex": marker_index,
            "threadID": frame.GetThread().GetThreadID(),
            "frame": case22._frame_record(frame),
            "precedingCompletedChainStartIndex": start,
            "precedingCompletedChainEndIndexExclusive": end,
            "eventIndex": None,
        }
        markers.append(marker)
        marker["eventIndex"] = _append_event("timeline-marker", marker_index)
        _state["lastMarkerCallCount"] = end
        if marker_index == 0:
            _set_window_capture_enabled(True)
        elif marker_index == timeline.TIMELINE_MARKER_COUNT - 1:
            _state["finalMarkerObserved"] = True
            _set_window_capture_enabled(False)
        trace["status"] = "timeline-active"
        _write_trace()
    except Exception as error:
        _failure("timeline-marker", error)
    return False


def parameters_builder_callsite(frame, _breakpoint_location, _internal_dict):
    try:
        trace = _state["trace"]
        if not _state["captureEnabled"]:
            raise RuntimeError("Parameters builder fired outside marker window")
        expected_pc = (
            trace["resolvedRecipeBuilderCaller"]["startAddress"]
            + parked.RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER
        )
        if frame.GetPC() != expected_pc:
            raise RuntimeError("Parameters builder callsite PC differs")
        thread_id = frame.GetThread().GetThreadID()
        if thread_id in _state["pendingByThread"]:
            raise RuntimeError("direct chains overlap on one thread")
        calls = trace["chains"]
        if len(calls) >= MAXIMUM_CHAIN_COUNT:
            raise RuntimeError("direct-chain bound exceeded")
        output_address = base._register_u64(frame, "x8")
        if output_address <= 0:
            raise RuntimeError("Parameters builder output address differs")
        call_index = len(calls)
        call = {
            "chainIndex": call_index,
            "threadID": thread_id,
            "stage": "parameters-builder-called",
            "builderCallEventIndex": None,
            "builderCallFrame": case22._frame_record(frame),
            "builderOutputAddress": output_address,
            "builderReturnEventIndex": None,
            "builderReturnFrame": None,
            "builderOutputAtReturn": None,
            "constructorCallEventIndex": None,
            "constructorCallFrame": None,
            "constructorParametersAddress": None,
            "constructorParametersAtCallsite": None,
            "constructorLayerIndex": None,
            "constructorFlagsRawValue": None,
            "constructorOutputAddress": None,
            "providerEntryEventIndex": None,
            "providerEntryFrame": None,
            "providerObjectAddress": None,
            "constructorOutputAtProviderEntry": None,
            "providerObjectAtEntry": None,
        }
        calls.append(call)
        call["builderCallEventIndex"] = _append_event(
            "parameters-builder-call", call_index
        )
        _state["pendingByThread"][thread_id] = call_index
        if call_index == 0:
            _write_trace()
    except Exception as error:
        _failure("parameters-builder-callsite", error)
    return False


def parameters_builder_return(frame, _breakpoint_location, _internal_dict):
    try:
        trace = _state["trace"]
        expected_pc = (
            trace["resolvedRecipeBuilderCaller"]["startAddress"]
            + parked.RESOLVED_RECIPE_BUILDER_RETURN_OFFSET_IN_CALLER
        )
        if frame.GetPC() != expected_pc:
            raise RuntimeError("Parameters builder return PC differs")
        thread_id = frame.GetThread().GetThreadID()
        call_index = _state["pendingByThread"].get(thread_id)
        if call_index is None:
            raise RuntimeError("Parameters builder return lacks its direct chain")
        call = trace["chains"][call_index]
        if call["stage"] != "parameters-builder-called":
            raise RuntimeError("Parameters builder return stage differs")
        call["builderReturnFrame"] = case22._frame_record(frame)
        call["builderOutputAtReturn"] = case22._snapshot(
            frame.GetThread().GetProcess(),
            call["builderOutputAddress"],
            parked.PARAMETERS_BYTE_COUNT,
            "live Parameters builder output",
        )
        call["builderReturnEventIndex"] = _append_event(
            "parameters-builder-return", call_index
        )
        call["stage"] = "parameters-builder-returned"
    except Exception as error:
        _failure("parameters-builder-return", error)
    return False


def constructor_callsite(frame, _breakpoint_location, _internal_dict):
    try:
        trace = _state["trace"]
        expected_pc = (
            trace["constructorProducer"]["startAddress"]
            + parked.CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER
        )
        if frame.GetPC() != expected_pc:
            raise RuntimeError("BackgroundFilter constructor callsite PC differs")
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        call_index = _state["pendingByThread"].get(thread_id)
        if call_index is None:
            raise RuntimeError("constructor callsite lacks its Parameters builder")
        call = trace["chains"][call_index]
        if call["stage"] != "parameters-builder-returned":
            raise RuntimeError("constructor callsite stage differs")
        parameters_address = base._register_u64(frame, "x0")
        output_address = base._register_u64(frame, "x8")
        if parameters_address <= 0 or output_address <= 0:
            raise RuntimeError("constructor address argument differs")
        call["constructorCallFrame"] = case22._frame_record(frame)
        call["constructorParametersAddress"] = parameters_address
        call["constructorParametersAtCallsite"] = case22._snapshot(
            thread.GetProcess(),
            parameters_address,
            parked.PARAMETERS_BYTE_COUNT,
            "live constructor Parameters input",
        )
        call["constructorLayerIndex"] = base._register_u64(frame, "x1")
        call["constructorFlagsRawValue"] = base._register_u64(frame, "x2")
        call["constructorOutputAddress"] = output_address
        call["constructorCallEventIndex"] = _append_event(
            "constructor-call", call_index
        )
        call["stage"] = "constructor-called"
        _state["providerEntryBreakpoint"].SetEnabled(True)
    except Exception as error:
        _failure("constructor-callsite", error)
    return False


def provider_entry(frame, _breakpoint_location, _internal_dict):
    try:
        trace = _state["trace"]
        if frame.GetPC() != trace["provider"]["symbolStart"]:
            raise RuntimeError("provider entry PC differs")
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        call_index = _state["pendingByThread"].get(thread_id)
        if call_index is None:
            _state["ignoredProviderEntryCount"] += 1
            return False
        call = trace["chains"][call_index]
        if call["stage"] != "constructor-called":
            _state["ignoredProviderEntryCount"] += 1
            return False
        provider_address = base._register_u64(frame, "x20")
        if provider_address <= 0:
            raise RuntimeError("provider object address differs")
        process = thread.GetProcess()
        call["providerEntryFrame"] = case22._frame_record(frame)
        call["providerObjectAddress"] = provider_address
        call["constructorOutputAtProviderEntry"] = case22._snapshot(
            process,
            call["constructorOutputAddress"],
            parked.BACKGROUND_FILTER_BYTE_COUNT,
            "live constructor output at provider entry",
        )
        call["providerObjectAtEntry"] = case22._snapshot(
            process,
            provider_address,
            parked.BACKGROUND_FILTER_BYTE_COUNT,
            "live complete provider object at entry",
        )
        call["providerEntryEventIndex"] = _append_event(
            "provider-entry", call_index
        )
        call["stage"] = "complete"
        del _state["pendingByThread"][thread_id]
        if not any(
            record.get("stage") == "constructor-called"
            for record in trace["chains"]
        ):
            _state["providerEntryBreakpoint"].SetEnabled(False)
    except Exception as error:
        _failure("provider-entry", error)
    return False


def _install_capture(debugger):
    target = debugger.GetSelectedTarget()
    process = target.GetProcess()
    trace = _state["trace"]
    main_module = field._module_by_uuid(
        target,
        timeline.MAIN_UUID,
        timeline.MAIN_PATH_SUFFIX,
        "main executable",
    )
    design_module = field._module_by_uuid(
        target,
        parked.DESIGN_LIBRARY_UUID,
        "/DesignLibrary",
        "DesignLibrary",
    )
    constructor = parked._capture_fixed_region(
        process,
        design_module,
        parked.CONSTRUCTOR_MODULE_OFFSET,
        parked.CONSTRUCTOR_BYTE_COUNT,
        parked.CONSTRUCTOR_CODE_SHA256,
        "live BackgroundFilter constructor",
    )
    producer = parked._capture_fixed_region(
        process,
        design_module,
        parked.PRODUCER_MODULE_OFFSET,
        parked.PRODUCER_BYTE_COUNT,
        parked.PRODUCER_CODE_SHA256,
        "live BackgroundFilter producer",
    )
    builder = parked._capture_fixed_region(
        process,
        design_module,
        parked.RESOLVED_RECIPE_BUILDER_MODULE_OFFSET,
        parked.RESOLVED_RECIPE_BUILDER_BYTE_COUNT,
        parked.RESOLVED_RECIPE_BUILDER_CODE_SHA256,
        "live ResolvedRecipe Parameters builder",
    )
    builder_caller = parked._capture_fixed_region(
        process,
        design_module,
        parked.RESOLVED_RECIPE_BUILDER_CALLER_MODULE_OFFSET,
        parked.RESOLVED_RECIPE_BUILDER_CALLER_BYTE_COUNT,
        parked.RESOLVED_RECIPE_BUILDER_CALLER_CODE_SHA256,
        "live ResolvedRecipe Parameters builder caller",
    )
    provider = field._capture_provider(process, design_module)

    constructor_call_address = (
        producer["startAddress"] + parked.CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER
    )
    constructor_raw = bytes.fromhex(producer["hex"])[
        parked.CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER :
        parked.CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER + 4
    ]
    if constructor_raw.hex() != parked.CONSTRUCTOR_CALL_INSTRUCTION_HEX:
        raise RuntimeError("constructor BL instruction differs")
    if (
        parked._decode_direct_branch_target(constructor_raw, constructor_call_address)
        != constructor["startAddress"]
    ):
        raise RuntimeError("constructor BL target differs")

    builder_call_address = (
        builder_caller["startAddress"]
        + parked.RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER
    )
    builder_raw = bytes.fromhex(builder_caller["hex"])[
        parked.RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER :
        parked.RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER + 4
    ]
    if builder_raw.hex() != parked.RESOLVED_RECIPE_BUILDER_CALL_INSTRUCTION_HEX:
        raise RuntimeError("Parameters builder BL instruction differs")
    if (
        parked._decode_direct_branch_target(builder_raw, builder_call_address)
        != builder["startAddress"]
    ):
        raise RuntimeError("Parameters builder BL target differs")

    specifications = (
        (
            main_module["loadAddress"] + timeline.TIMELINE_MARKER_MODULE_OFFSET,
            "timeline_marker",
            "exact public timeline marker",
            True,
        ),
        (
            builder_call_address,
            "parameters_builder_callsite",
            "exact Parameters builder direct call",
            False,
        ),
        (
            builder_caller["startAddress"]
            + parked.RESOLVED_RECIPE_BUILDER_RETURN_OFFSET_IN_CALLER,
            "parameters_builder_return",
            "exact Parameters builder direct return",
            False,
        ),
        (
            constructor_call_address,
            "constructor_callsite",
            "exact BackgroundFilter constructor direct call",
            False,
        ),
        (
            provider["symbolStart"],
            "provider_entry",
            "exact BackgroundFilter provider entry",
            False,
        ),
    )
    installed = [
        _install_breakpoint(target, address, callback, label, enabled)
        for address, callback, label, enabled in specifications
    ]
    (
        _state["markerBreakpoint"],
        _state["builderCallsiteBreakpoint"],
        _state["builderReturnBreakpoint"],
        _state["constructorCallsiteBreakpoint"],
        _state["providerEntryBreakpoint"],
    ) = installed
    trace["modules"] = {"main": main_module, "designLibrary": design_module}
    trace["timelineMarkerModule"] = main_module
    trace["constructor"] = constructor
    trace["constructorProducer"] = producer
    trace["resolvedRecipeBuilder"] = builder
    trace["resolvedRecipeBuilderCaller"] = builder_caller
    trace["provider"] = provider
    trace["breakpoints"] = [
        {
            "name": callback,
            "label": label,
            "id": breakpoint.GetID(),
            "address": address,
            "locationCount": breakpoint.GetNumLocations(),
            "initiallyEnabled": enabled,
            "selection": "fixed offset in exact authenticated code",
        }
        for breakpoint, (address, callback, label, enabled) in zip(
            installed, specifications
        )
    ]
    trace["status"] = "exact-breakpoints-ready"
    _write_trace()


def finalize():
    trace = _state["trace"]
    if trace is None:
        return
    for key in (
        "markerBreakpoint",
        "builderCallsiteBreakpoint",
        "builderReturnBreakpoint",
        "constructorCallsiteBreakpoint",
        "providerEntryBreakpoint",
    ):
        breakpoint = _state[key]
        if breakpoint is not None:
            breakpoint.SetEnabled(False)
    trace["statusBeforeFinalization"] = trace["status"]
    trace["status"] = "finalized"
    trace["finalTimelineMarkerCount"] = len(trace["timelineMarkers"])
    trace["finalChainCount"] = len(trace["chains"])
    trace["finalCompleteChainCount"] = sum(
        call.get("stage") == "complete" for call in trace["chains"]
    )
    trace["finalPendingThreadCount"] = len(_state["pendingByThread"])
    trace["finalMarkerAssignedChainCount"] = _state["lastMarkerCallCount"]
    trace["finalEventCount"] = len(trace["events"])
    trace["finalFailureCount"] = len(trace["failures"])
    trace["finalMarkerObserved"] = _state["finalMarkerObserved"]
    trace["finalCaptureEnabled"] = _state["captureEnabled"]
    trace["finalIgnoredProviderEntryCount"] = _state["ignoredProviderEntryCount"]
    trace["finalBreakpointEnabledStates"] = {
        key: _state[key].IsEnabled()
        for key in (
            "markerBreakpoint",
            "builderCallsiteBreakpoint",
            "builderReturnBreakpoint",
            "constructorCallsiteBreakpoint",
            "providerEntryBreakpoint",
        )
    }
    _write_trace()


def __lldb_init_module(debugger, _internal_dict):
    _state["trace"] = _new_trace()
    timeline.minimal._state["trace"] = _state["trace"]
    _write_trace()
    _install_capture(debugger)
