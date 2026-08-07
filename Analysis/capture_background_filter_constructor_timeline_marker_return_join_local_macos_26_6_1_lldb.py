"""Capture the constructor output at its authenticated immediate return.

The four-stop predecessor proved the complete live builder-to-constructor and
public-to-provider joins, but read the constructor's temporary stack output too
late.  This overlay adds the producer's exact post-BL return stop and snapshots
the 504-byte value before producer code may reuse the stack slot.  Call
selection remains exact control flow, thread identity, event order, and marker
ordinal only.

LLDB imports this module with Apple's system Python 3.9.
"""

import capture_background_filter_constructor_timeline_marker_direct_join_local_macos_26_6_1_lldb as direct


TRACE_SCHEMA_VERSION = 1

parked = direct.parked
base = direct.base
case22 = direct.case22

_DIRECT_NEW_TRACE = direct._new_trace
_DIRECT_INSTALL_CAPTURE = direct._install_capture
_DIRECT_SET_WINDOW_CAPTURE_ENABLED = direct._set_window_capture_enabled
_DIRECT_TIMELINE_MARKER = direct.timeline_marker
_DIRECT_BUILDER_CALLSITE = direct.parameters_builder_callsite
_DIRECT_BUILDER_RETURN = direct.parameters_builder_return
_DIRECT_CONSTRUCTOR_CALLSITE = direct.constructor_callsite
_DIRECT_FINALIZE = direct.finalize

_return_state = {"constructorReturnBreakpoint": None}


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _new_trace():
    trace = _DIRECT_NEW_TRACE()
    trace[
        "backgroundFilterConstructorTimelineMarkerReturnJoinLocalMacOSLldbTraceSchemaVersion"
    ] = TRACE_SCHEMA_VERSION
    trace["classification"] = (
        "prospectively frozen value-blind five-stop live direct join with the "
        "complete 504-byte constructor value captured at its authenticated "
        "immediate producer return before the temporary stack slot is reused"
    )
    trace["configuration"].update(
        {
            "stopsPerSelectedChain": 5,
            "expectedControlFlowSequence": [
                "parameters-builder-call",
                "parameters-builder-return",
                "constructor-call",
                "constructor-return",
                "provider-entry",
            ],
            "constructorOutputSnapshotTiming": (
                "exact producer instruction immediately after constructor BL"
            ),
            "constructorOutputAtProviderEntryUsedForJoin": False,
            "capturedConstructorReturnValueUsedForSelection": False,
        }
    )
    return trace


def _install_capture(debugger):
    _DIRECT_INSTALL_CAPTURE(debugger)
    target = debugger.GetSelectedTarget()
    trace = direct._state["trace"]
    address = (
        trace["constructorProducer"]["startAddress"]
        + parked.CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER
    )
    breakpoint = direct._install_breakpoint(
        target,
        address,
        "constructor_return",
        "exact BackgroundFilter constructor immediate return",
        False,
    )
    _return_state["constructorReturnBreakpoint"] = breakpoint
    trace["breakpoints"].append(
        {
            "name": "constructor_return",
            "label": "exact BackgroundFilter constructor immediate return",
            "id": breakpoint.GetID(),
            "address": address,
            "locationCount": breakpoint.GetNumLocations(),
            "initiallyEnabled": False,
            "selection": "fixed immediate post-BL offset in exact authenticated producer code",
        }
    )
    direct._write_trace()


def _set_window_capture_enabled(enabled):
    _DIRECT_SET_WINDOW_CAPTURE_ENABLED(enabled)
    breakpoint = _return_state["constructorReturnBreakpoint"]
    if breakpoint is not None:
        breakpoint.SetEnabled(enabled)


def timeline_marker(frame, breakpoint_location, internal_dict):
    return _DIRECT_TIMELINE_MARKER(frame, breakpoint_location, internal_dict)


def parameters_builder_callsite(frame, breakpoint_location, internal_dict):
    return _DIRECT_BUILDER_CALLSITE(frame, breakpoint_location, internal_dict)


def parameters_builder_return(frame, breakpoint_location, internal_dict):
    return _DIRECT_BUILDER_RETURN(frame, breakpoint_location, internal_dict)


def constructor_callsite(frame, breakpoint_location, internal_dict):
    thread_id = frame.GetThread().GetThreadID()
    result = _DIRECT_CONSTRUCTOR_CALLSITE(
        frame,
        breakpoint_location,
        internal_dict,
    )
    try:
        call_index = direct._state["pendingByThread"].get(thread_id)
        if call_index is None:
            return result
        call = direct._state["trace"]["chains"][call_index]
        if call.get("stage") != "constructor-called":
            return result
        call["constructorReturnEventIndex"] = None
        call["constructorReturnFrame"] = None
        call["constructorOutputAtReturn"] = None
        if not any(
            record.get("stage") == "constructor-returned"
            for record in direct._state["trace"]["chains"]
        ):
            direct._state["providerEntryBreakpoint"].SetEnabled(False)
    except Exception as error:
        direct._failure("return-join-constructor-callsite", error)
    return result


def constructor_return(frame, _breakpoint_location, _internal_dict):
    try:
        trace = direct._state["trace"]
        expected_pc = (
            trace["constructorProducer"]["startAddress"]
            + parked.CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER
        )
        if frame.GetPC() != expected_pc:
            raise RuntimeError("BackgroundFilter constructor return PC differs")
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        call_index = direct._state["pendingByThread"].get(thread_id)
        if call_index is None:
            raise RuntimeError("constructor return lacks its direct chain")
        call = trace["chains"][call_index]
        if call.get("stage") != "constructor-called":
            raise RuntimeError("constructor return stage differs")
        call["constructorReturnFrame"] = case22._frame_record(frame)
        call["constructorOutputAtReturn"] = case22._snapshot(
            thread.GetProcess(),
            call["constructorOutputAddress"],
            parked.BACKGROUND_FILTER_BYTE_COUNT,
            "live BackgroundFilter constructor output at immediate return",
        )
        call["constructorReturnEventIndex"] = direct._append_event(
            "constructor-return", call_index
        )
        call["stage"] = "constructor-returned"
        direct._state["providerEntryBreakpoint"].SetEnabled(True)
    except Exception as error:
        direct._failure("constructor-return", error)
    return False


def provider_entry(frame, _breakpoint_location, _internal_dict):
    try:
        trace = direct._state["trace"]
        if frame.GetPC() != trace["provider"]["symbolStart"]:
            raise RuntimeError("provider entry PC differs")
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        call_index = direct._state["pendingByThread"].get(thread_id)
        if call_index is None:
            direct._state["ignoredProviderEntryCount"] += 1
            return False
        call = trace["chains"][call_index]
        if call.get("stage") != "constructor-returned":
            direct._state["ignoredProviderEntryCount"] += 1
            return False
        provider_address = base._register_u64(frame, "x20")
        if provider_address <= 0:
            raise RuntimeError("provider object address differs")
        call["providerEntryFrame"] = case22._frame_record(frame)
        call["providerObjectAddress"] = provider_address
        call["constructorOutputAtProviderEntry"] = None
        call["providerObjectAtEntry"] = case22._snapshot(
            thread.GetProcess(),
            provider_address,
            parked.BACKGROUND_FILTER_BYTE_COUNT,
            "live complete provider object at entry",
        )
        call["providerEntryEventIndex"] = direct._append_event(
            "provider-entry", call_index
        )
        call["stage"] = "complete"
        del direct._state["pendingByThread"][thread_id]
        if not any(
            record.get("stage") == "constructor-returned"
            for record in trace["chains"]
        ):
            direct._state["providerEntryBreakpoint"].SetEnabled(False)
    except Exception as error:
        direct._failure("provider-entry", error)
    return False


def finalize():
    _DIRECT_FINALIZE()
    trace = direct._state["trace"]
    breakpoint = _return_state["constructorReturnBreakpoint"]
    if breakpoint is not None:
        breakpoint.SetEnabled(False)
    trace["finalConstructorReturnSnapshotCount"] = sum(
        call.get("constructorOutputAtReturn") is not None
        for call in trace["chains"]
    )
    trace["finalConstructorReturnBreakpointEnabled"] = (
        breakpoint.IsEnabled() if breakpoint is not None else None
    )
    direct._write_trace()


def __lldb_init_module(debugger, internal_dict):
    direct._set_callback = _set_callback
    direct._new_trace = _new_trace
    direct._install_capture = _install_capture
    direct._set_window_capture_enabled = _set_window_capture_enabled
    direct.__lldb_init_module(debugger, internal_dict)
