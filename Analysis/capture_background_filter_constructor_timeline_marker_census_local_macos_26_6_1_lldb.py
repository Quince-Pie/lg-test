"""Census exact producer calls on the authenticated live Retina timeline.

This overlay retains the already-frozen provider/marker capture unchanged and
adds four value-blind stops: the fixed direct call and matching return for the
ResolvedRecipe Parameters builder, and the fixed direct call and matching
return for the BackgroundFilter constructor.  It records only exact control
flow, thread identity, and marker ordinal.  No Parameters byte, filter byte,
register argument, image, pixel, or computed value is read or used to select a
call.  The census determines where a later full-object join must be placed.

LLDB imports this module with Apple's system Python 3.9.
"""

import capture_backdrop_margin_case22_provider_timeline_marker_transfer_local_macos_26_6_1_lldb as live
import capture_background_filter_constructor_public_render_interval_local_macos_26_6_1_lldb as parked


TRACE_SCHEMA_VERSION = 1
MAXIMUM_CONSTRUCTOR_CALLS = 4096
MAXIMUM_PARAMETERS_BUILDER_CALLS = 4096

_LIVE_NEW_TRACE = live._new_trace
_LIVE_TIMELINE_MARKER = live.timeline_marker
_LIVE_SELECTED_CALLSITE = live.selected_callsite
_LIVE_WRAPPER_ENTRY = live.wrapper_entry
_LIVE_PROVIDER_ENTRY = live.provider_entry
_LIVE_PROVIDER_RETURN = live.provider_return
_LIVE_GROUP_RETURN = live.group_return
_LIVE_SELECTED_CALLER_RETURN = live.selected_caller_return
_LIVE_FINALIZE = live.finalize

minimal = live.minimal
case22 = live.case22
field = live.field

_census_state = {
    "constructorCallsiteBreakpoint": None,
    "constructorReturnBreakpoint": None,
    "builderCallsiteBreakpoint": None,
    "builderReturnBreakpoint": None,
    "pendingConstructorByThread": {},
    "pendingBuilderByThread": {},
    "entryCaptureEnabled": False,
    "finalMarkerObserved": False,
}


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _new_trace():
    trace = _LIVE_NEW_TRACE()
    trace[
        "backgroundFilterConstructorTimelineMarkerCensusLocalMacOSLldbTraceSchemaVersion"
    ] = TRACE_SCHEMA_VERSION
    trace["classification"] = (
        "prospectively frozen output-blind census of exact ResolvedRecipe "
        "Parameters-builder and BackgroundFilter-constructor direct calls "
        "between authenticated live Retina timeline markers 0 and 32"
    )
    trace["configuration"].update(
        {
            "constructorCensusEnabledAfterMarkerIndex": 0,
            "constructorCensusDisabledAtMarkerIndex": 32,
            "constructorCensusMaximumCalls": MAXIMUM_CONSTRUCTOR_CALLS,
            "parametersBuilderCensusMaximumCalls": (
                MAXIMUM_PARAMETERS_BUILDER_CALLS
            ),
            "constructorCensusSelection": (
                "fixed authenticated producer BL callsite and matching "
                "immediate return, bounded by marker ordinal"
            ),
            "parametersBuilderCensusSelection": (
                "fixed authenticated caller BL callsite and matching "
                "immediate return, bounded by marker ordinal"
            ),
            "capturedParametersUsedForCensusSelection": False,
            "capturedBackgroundFilterUsedForCensusSelection": False,
            "capturedProviderObjectUsedForCensusSelection": False,
            "capturedRegisterArgumentUsedForCensusSelection": False,
            "capturedAddressValueUsedForCensusSelection": False,
            "capturedImageUsedForCensusSelection": False,
            "capturedPixelUsedForCensusSelection": False,
        }
    )
    trace["constructorCensusDesignLibraryModule"] = {}
    trace["constructorCensusConstructor"] = {}
    trace["constructorCensusProducer"] = {}
    trace["constructorCensusParametersBuilder"] = {}
    trace["constructorCensusParametersBuilderCaller"] = {}
    trace["constructorCensusBreakpoints"] = []
    trace["constructorCensusEvents"] = []
    trace["constructorCensusCalls"] = []
    trace["parametersBuilderCensusCalls"] = []
    return trace


def _append_census_event(kind, record_index, marker_index):
    events = minimal._state["trace"]["constructorCensusEvents"]
    event = {
        "eventIndex": len(events),
        "kind": kind,
        "recordIndex": record_index,
        "latestObservedMarkerIndex": marker_index,
    }
    events.append(event)
    return event["eventIndex"]


def _install_breakpoint(target, address, callback, label):
    breakpoint = target.BreakpointCreateByAddress(address)
    if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
        raise RuntimeError(label + " breakpoint is unresolved")
    _set_callback(breakpoint, callback, label)
    breakpoint.SetEnabled(False)
    return breakpoint


def _install_census(debugger):
    target = debugger.GetSelectedTarget()
    process = target.GetProcess()
    trace = minimal._state["trace"]
    module = field._module_by_uuid(
        target,
        parked.DESIGN_LIBRARY_UUID,
        "/DesignLibrary",
        "DesignLibrary",
    )
    constructor = parked._capture_fixed_region(
        process,
        module,
        parked.CONSTRUCTOR_MODULE_OFFSET,
        parked.CONSTRUCTOR_BYTE_COUNT,
        parked.CONSTRUCTOR_CODE_SHA256,
        "BackgroundFilter constructor census",
    )
    producer = parked._capture_fixed_region(
        process,
        module,
        parked.PRODUCER_MODULE_OFFSET,
        parked.PRODUCER_BYTE_COUNT,
        parked.PRODUCER_CODE_SHA256,
        "BackgroundFilter producer census",
    )
    builder = parked._capture_fixed_region(
        process,
        module,
        parked.RESOLVED_RECIPE_BUILDER_MODULE_OFFSET,
        parked.RESOLVED_RECIPE_BUILDER_BYTE_COUNT,
        parked.RESOLVED_RECIPE_BUILDER_CODE_SHA256,
        "ResolvedRecipe Parameters builder census",
    )
    builder_caller = parked._capture_fixed_region(
        process,
        module,
        parked.RESOLVED_RECIPE_BUILDER_CALLER_MODULE_OFFSET,
        parked.RESOLVED_RECIPE_BUILDER_CALLER_BYTE_COUNT,
        parked.RESOLVED_RECIPE_BUILDER_CALLER_CODE_SHA256,
        "ResolvedRecipe Parameters builder caller census",
    )

    constructor_call_address = (
        producer["startAddress"] + parked.CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER
    )
    constructor_call_raw = bytes.fromhex(producer["hex"])[
        parked.CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER :
        parked.CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER + 4
    ]
    if constructor_call_raw.hex() != parked.CONSTRUCTOR_CALL_INSTRUCTION_HEX:
        raise RuntimeError("BackgroundFilter constructor BL differs")
    if (
        parked._decode_direct_branch_target(
            constructor_call_raw,
            constructor_call_address,
        )
        != constructor["startAddress"]
    ):
        raise RuntimeError("BackgroundFilter constructor BL target differs")

    builder_call_address = (
        builder_caller["startAddress"]
        + parked.RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER
    )
    builder_call_raw = bytes.fromhex(builder_caller["hex"])[
        parked.RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER :
        parked.RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER + 4
    ]
    if builder_call_raw.hex() != parked.RESOLVED_RECIPE_BUILDER_CALL_INSTRUCTION_HEX:
        raise RuntimeError("ResolvedRecipe Parameters builder BL differs")
    if (
        parked._decode_direct_branch_target(builder_call_raw, builder_call_address)
        != builder["startAddress"]
    ):
        raise RuntimeError("ResolvedRecipe Parameters builder BL target differs")

    specifications = (
        (
            constructor_call_address,
            "constructor_callsite",
            "BackgroundFilter constructor direct call",
        ),
        (
            producer["startAddress"]
            + parked.CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER,
            "constructor_return",
            "BackgroundFilter constructor direct return",
        ),
        (
            builder_call_address,
            "parameters_builder_callsite",
            "ResolvedRecipe Parameters builder direct call",
        ),
        (
            builder_caller["startAddress"]
            + parked.RESOLVED_RECIPE_BUILDER_RETURN_OFFSET_IN_CALLER,
            "parameters_builder_return",
            "ResolvedRecipe Parameters builder direct return",
        ),
    )
    installed = [
        _install_breakpoint(target, address, callback, label)
        for address, callback, label in specifications
    ]
    (
        _census_state["constructorCallsiteBreakpoint"],
        _census_state["constructorReturnBreakpoint"],
        _census_state["builderCallsiteBreakpoint"],
        _census_state["builderReturnBreakpoint"],
    ) = installed

    trace["constructorCensusDesignLibraryModule"] = module
    trace["constructorCensusConstructor"] = constructor
    trace["constructorCensusProducer"] = producer
    trace["constructorCensusParametersBuilder"] = builder
    trace["constructorCensusParametersBuilderCaller"] = builder_caller
    trace["constructorCensusBreakpoints"] = [
        {
            "name": callback,
            "label": label,
            "id": breakpoint.GetID(),
            "address": address,
            "locationCount": breakpoint.GetNumLocations(),
            "selection": (
                "fixed offset in exact authenticated DesignLibrary code; "
                "enabled only after marker 0 and disabled at marker 32"
            ),
        }
        for breakpoint, (address, callback, label) in zip(installed, specifications)
    ]
    minimal._write_trace()


def _set_entry_capture_enabled(enabled):
    _census_state["constructorCallsiteBreakpoint"].SetEnabled(enabled)
    _census_state["builderCallsiteBreakpoint"].SetEnabled(enabled)
    _census_state["entryCaptureEnabled"] = enabled
    if enabled:
        _census_state["constructorReturnBreakpoint"].SetEnabled(True)
        _census_state["builderReturnBreakpoint"].SetEnabled(True)
    else:
        if not _census_state["pendingConstructorByThread"]:
            _census_state["constructorReturnBreakpoint"].SetEnabled(False)
        if not _census_state["pendingBuilderByThread"]:
            _census_state["builderReturnBreakpoint"].SetEnabled(False)


def _latest_marker_index():
    return len(minimal._state["trace"]["timelineMarkers"]) - 1


def timeline_marker(frame, breakpoint_location, internal_dict):
    trace = minimal._state["trace"]
    marker_index = len(trace["timelineMarkers"])
    census_event_index = _append_census_event(
        "timeline-marker-entry",
        marker_index,
        marker_index,
    )
    before = len(trace["timelineMarkers"])
    result = _LIVE_TIMELINE_MARKER(frame, breakpoint_location, internal_dict)
    try:
        if len(trace["timelineMarkers"]) != before + 1:
            raise RuntimeError("live timeline marker was not retained")
        marker = trace["timelineMarkers"][-1]
        if marker.get("markerIndex") != marker_index:
            raise RuntimeError("live timeline marker ordinal differs")
        marker.update(
            {
                "constructorCensusEventIndex": census_event_index,
                "constructorCensusEntryCountAtMarker": len(
                    trace["constructorCensusCalls"]
                ),
                "constructorCensusReturnCountAtMarker": sum(
                    call.get("returnEventIndex") is not None
                    for call in trace["constructorCensusCalls"]
                ),
                "parametersBuilderCensusEntryCountAtMarker": len(
                    trace["parametersBuilderCensusCalls"]
                ),
                "parametersBuilderCensusReturnCountAtMarker": sum(
                    call.get("returnEventIndex") is not None
                    for call in trace["parametersBuilderCensusCalls"]
                ),
                "pendingConstructorCensusThreadCountAtMarker": len(
                    _census_state["pendingConstructorByThread"]
                ),
                "pendingParametersBuilderCensusThreadCountAtMarker": len(
                    _census_state["pendingBuilderByThread"]
                ),
            }
        )
        if marker_index == 0:
            _set_entry_capture_enabled(True)
        elif marker_index == live.TIMELINE_MARKER_COUNT - 1:
            _census_state["finalMarkerObserved"] = True
            _set_entry_capture_enabled(False)
        minimal._write_trace()
    except Exception as error:
        minimal._failure("constructor-census-timeline-marker", error)
    return result


def _callsite_record(frame, call_index, label):
    return {
        "callIndex": call_index,
        "threadID": frame.GetThread().GetThreadID(),
        "entryEventIndex": None,
        "entryAfterMarkerIndex": _latest_marker_index(),
        "entryFrame": case22._frame_record(frame),
        "returnEventIndex": None,
        "returnAfterMarkerIndex": None,
        "returnFrame": None,
        "selection": label,
    }


def constructor_callsite(frame, _breakpoint_location, _internal_dict):
    try:
        trace = minimal._state["trace"]
        if not _census_state["entryCaptureEnabled"]:
            raise RuntimeError("constructor callsite fired outside the marker window")
        expected_pc = (
            trace["constructorCensusProducer"]["startAddress"]
            + parked.CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER
        )
        if frame.GetPC() != expected_pc:
            raise RuntimeError("constructor callsite PC differs")
        calls = trace["constructorCensusCalls"]
        if len(calls) >= MAXIMUM_CONSTRUCTOR_CALLS:
            raise RuntimeError("constructor census bound exceeded")
        thread_id = frame.GetThread().GetThreadID()
        if thread_id in _census_state["pendingConstructorByThread"]:
            raise RuntimeError("constructor direct calls nested on one thread")
        call_index = len(calls)
        call = _callsite_record(
            frame,
            call_index,
            "exact BackgroundFilter producer BL",
        )
        calls.append(call)
        call["entryEventIndex"] = _append_census_event(
            "constructor-call",
            call_index,
            call["entryAfterMarkerIndex"],
        )
        _census_state["pendingConstructorByThread"][thread_id] = call_index
        if len(calls) % 64 == 0:
            minimal._write_trace()
    except Exception as error:
        minimal._failure("constructor-census-callsite", error)
    return False


def constructor_return(frame, _breakpoint_location, _internal_dict):
    try:
        trace = minimal._state["trace"]
        expected_pc = (
            trace["constructorCensusProducer"]["startAddress"]
            + parked.CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER
        )
        if frame.GetPC() != expected_pc:
            raise RuntimeError("constructor return PC differs")
        thread_id = frame.GetThread().GetThreadID()
        call_index = _census_state["pendingConstructorByThread"].pop(
            thread_id,
            None,
        )
        if call_index is None:
            raise RuntimeError("constructor return lacks its direct call")
        call = trace["constructorCensusCalls"][call_index]
        call["returnAfterMarkerIndex"] = _latest_marker_index()
        call["returnFrame"] = case22._frame_record(frame)
        call["returnEventIndex"] = _append_census_event(
            "constructor-return",
            call_index,
            call["returnAfterMarkerIndex"],
        )
        if (
            _census_state["finalMarkerObserved"]
            and not _census_state["pendingConstructorByThread"]
        ):
            _census_state["constructorReturnBreakpoint"].SetEnabled(False)
    except Exception as error:
        minimal._failure("constructor-census-return", error)
    return False


def parameters_builder_callsite(frame, _breakpoint_location, _internal_dict):
    try:
        trace = minimal._state["trace"]
        if not _census_state["entryCaptureEnabled"]:
            raise RuntimeError("Parameters builder callsite fired outside marker window")
        expected_pc = (
            trace["constructorCensusParametersBuilderCaller"]["startAddress"]
            + parked.RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER
        )
        if frame.GetPC() != expected_pc:
            raise RuntimeError("Parameters builder callsite PC differs")
        calls = trace["parametersBuilderCensusCalls"]
        if len(calls) >= MAXIMUM_PARAMETERS_BUILDER_CALLS:
            raise RuntimeError("Parameters builder census bound exceeded")
        thread_id = frame.GetThread().GetThreadID()
        if thread_id in _census_state["pendingBuilderByThread"]:
            raise RuntimeError("Parameters builder direct calls nested on one thread")
        call_index = len(calls)
        call = _callsite_record(
            frame,
            call_index,
            "exact ResolvedRecipe Parameters-builder caller BL",
        )
        calls.append(call)
        call["entryEventIndex"] = _append_census_event(
            "parameters-builder-call",
            call_index,
            call["entryAfterMarkerIndex"],
        )
        _census_state["pendingBuilderByThread"][thread_id] = call_index
        if len(calls) % 64 == 0:
            minimal._write_trace()
    except Exception as error:
        minimal._failure("parameters-builder-census-callsite", error)
    return False


def parameters_builder_return(frame, _breakpoint_location, _internal_dict):
    try:
        trace = minimal._state["trace"]
        expected_pc = (
            trace["constructorCensusParametersBuilderCaller"]["startAddress"]
            + parked.RESOLVED_RECIPE_BUILDER_RETURN_OFFSET_IN_CALLER
        )
        if frame.GetPC() != expected_pc:
            raise RuntimeError("Parameters builder return PC differs")
        thread_id = frame.GetThread().GetThreadID()
        call_index = _census_state["pendingBuilderByThread"].pop(thread_id, None)
        if call_index is None:
            raise RuntimeError("Parameters builder return lacks its direct call")
        call = trace["parametersBuilderCensusCalls"][call_index]
        call["returnAfterMarkerIndex"] = _latest_marker_index()
        call["returnFrame"] = case22._frame_record(frame)
        call["returnEventIndex"] = _append_census_event(
            "parameters-builder-return",
            call_index,
            call["returnAfterMarkerIndex"],
        )
        if (
            _census_state["finalMarkerObserved"]
            and not _census_state["pendingBuilderByThread"]
        ):
            _census_state["builderReturnBreakpoint"].SetEnabled(False)
    except Exception as error:
        minimal._failure("parameters-builder-census-return", error)
    return False


def selected_callsite(frame, breakpoint_location, internal_dict):
    return _LIVE_SELECTED_CALLSITE(frame, breakpoint_location, internal_dict)


def wrapper_entry(frame, breakpoint_location, internal_dict):
    return _LIVE_WRAPPER_ENTRY(frame, breakpoint_location, internal_dict)


def provider_entry(frame, breakpoint_location, internal_dict):
    return _LIVE_PROVIDER_ENTRY(frame, breakpoint_location, internal_dict)


def provider_return(frame, breakpoint_location, internal_dict):
    return _LIVE_PROVIDER_RETURN(frame, breakpoint_location, internal_dict)


def group_return(frame, breakpoint_location, internal_dict):
    return _LIVE_GROUP_RETURN(frame, breakpoint_location, internal_dict)


def selected_caller_return(frame, breakpoint_location, internal_dict):
    return _LIVE_SELECTED_CALLER_RETURN(frame, breakpoint_location, internal_dict)


def finalize():
    _LIVE_FINALIZE()
    trace = minimal._state["trace"]
    for key in (
        "constructorCallsiteBreakpoint",
        "constructorReturnBreakpoint",
        "builderCallsiteBreakpoint",
        "builderReturnBreakpoint",
    ):
        breakpoint = _census_state[key]
        if breakpoint is not None:
            breakpoint.SetEnabled(False)
    trace["finalConstructorCensusCallCount"] = len(
        trace["constructorCensusCalls"]
    )
    trace["finalConstructorCensusReturnCount"] = sum(
        call.get("returnEventIndex") is not None
        for call in trace["constructorCensusCalls"]
    )
    trace["finalParametersBuilderCensusCallCount"] = len(
        trace["parametersBuilderCensusCalls"]
    )
    trace["finalParametersBuilderCensusReturnCount"] = sum(
        call.get("returnEventIndex") is not None
        for call in trace["parametersBuilderCensusCalls"]
    )
    trace["finalPendingConstructorCensusThreadCount"] = len(
        _census_state["pendingConstructorByThread"]
    )
    trace["finalPendingParametersBuilderCensusThreadCount"] = len(
        _census_state["pendingBuilderByThread"]
    )
    trace["finalConstructorCensusEventCount"] = len(
        trace["constructorCensusEvents"]
    )
    trace["finalConstructorCensusEntryCaptureEnabled"] = _census_state[
        "entryCaptureEnabled"
    ]
    trace["finalConstructorCensusMarkerObserved"] = _census_state[
        "finalMarkerObserved"
    ]
    trace["finalConstructorCensusBreakpointEnabledStates"] = {
        key: _census_state[key].IsEnabled()
        for key in (
            "constructorCallsiteBreakpoint",
            "constructorReturnBreakpoint",
            "builderCallsiteBreakpoint",
            "builderReturnBreakpoint",
        )
    }
    minimal._write_trace()


def __lldb_init_module(debugger, internal_dict):
    live._set_callback = _set_callback
    live._new_trace = _new_trace
    live.__lldb_init_module(debugger, internal_dict)
    _install_census(debugger)
