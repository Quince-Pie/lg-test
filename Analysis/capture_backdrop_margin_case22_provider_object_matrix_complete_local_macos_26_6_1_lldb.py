"""Capture the complete process-lifetime provider-object matrix.

The previous callsite gate was imported only after the executable reached
``main`` and disabled the wrapper chain after the first case-22 return inside
each selected ``Group.margin`` call.  This successor installs a pending exact
``updateSDFEffects`` entry bootstrap before launch.  Once SwiftUICore loads,
it authenticates the complete caller and arms the fixed callsite.  For every
selected Group call, all wrapper/provider/return callbacks stay armed until
the enclosing caller returns, so every case-22 iteration is retained.
Captured values never participate in selection.
"""

import capture_backdrop_margin_case22_provider_object_matrix_minimal_retry2_local_macos_26_6_1_lldb as bounded


gate = bounded.frozen
minimal = gate.frozen
local = minimal.local
group = minimal.group
field = minimal.field
case22 = minimal.case22

TRACE_SCHEMA_VERSION = 1
MAXIMUM_CALL_COUNT = bounded.MAXIMUM_CALL_COUNT
CALLER_CALL_OFFSET = gate.CALLER_CALL_OFFSET
CALLER_RETURN_OFFSET = gate.CALLER_RETURN_OFFSET

_bounded_new_trace = bounded._new_trace
_state = {
    "bootstrapBreakpoint": None,
    "callsiteBreakpoint": None,
    "wrapperEntryBreakpoint": None,
    "callerReturnBreakpoint": None,
    "selectedByThread": {},
    "bootstrapObserved": False,
}


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _new_trace():
    trace = _bounded_new_trace()
    trace[
        "case22ProviderObjectMatrixCompleteLocalMacOSLldbTraceSchemaVersion"
    ] = TRACE_SCHEMA_VERSION
    trace["classification"] = (
        "output-blind complete-process, all-iteration provider-object "
        "capture of the exact updateSDFEffects -> Group.margin -> wrapper "
        "-> DesignLibrary provider chain"
    )
    trace["configuration"].update(
        {
            "selection": (
                "import before launch; bootstrap at the first exact "
                "updateSDFEffects entry; select every fixed +0x1680 Group "
                "callsite; retain every structurally joined case-22 wrapper "
                "iteration until exact +0x1684 caller return"
            ),
            "importedBeforeProcessLaunch": True,
            "pendingCallerEntryBootstrap": True,
            "capturesFirstExactCallerInvocation": True,
            "capturesEveryCase22IterationUntilCallerReturn": True,
            "previousFirstCaseDisarmRemoved": True,
            "perSelectedCallerStopCountFormula": (
                "2 + 4 * case22ProviderCallCount"
            ),
            "perSelectedCallMaximumStopCount": 2 + 4 * MAXIMUM_CALL_COUNT,
            "activeBreakpointCountPerSelectedCall": 6,
            "unrelatedWrapperOrProviderCallbacksArmed": False,
        }
    )
    trace["bootstrap"] = {}
    trace["selectedCallerCalls"] = []
    return trace


def _failure(stage, error):
    minimal._failure("complete-" + str(stage), error)


def _dynamic_breakpoints():
    return (
        _state["wrapperEntryBreakpoint"],
        minimal._state["providerBreakpoint"],
        minimal._state["wrapperReturnBreakpoint"],
        minimal._state["groupReturnBreakpoint"],
        _state["callerReturnBreakpoint"],
    )


def _set_dynamic_breakpoints_enabled(enabled):
    for breakpoint in _dynamic_breakpoints():
        if breakpoint is not None:
            breakpoint.SetEnabled(enabled)


def _append_breakpoint_record(trace, breakpoint, name, label, selection):
    trace["breakpoints"].append(
        {
            "name": name,
            "label": label,
            "id": breakpoint.GetID(),
            "selection": selection,
        }
    )


def _install_after_caller_entry(frame):
    if _state["callsiteBreakpoint"] is not None:
        return
    minimal._install_exact_breakpoints(frame)
    caller = gate._capture_local_caller(frame, 0)
    if (
        frame.GetPC() != caller["symbolStart"]
        or caller["hex"][
            2 * CALLER_CALL_OFFSET : 2 * (CALLER_CALL_OFFSET + 4)
        ]
        != local.LOCAL_CALLER_CALL_INSTRUCTION_HEX
    ):
        raise RuntimeError("bootstrap caller entry identity differs")
    trace = minimal._state["trace"]
    trace["caller"] = caller
    target = frame.GetThread().GetProcess().GetTarget()
    specifications = (
        (
            trace["wrapper"]["symbolStart"],
            "wrapper_entry",
            "wrapper entry",
            "enabled only while an exact selected Group call is active",
        ),
        (
            caller["symbolStart"] + CALLER_CALL_OFFSET,
            "selected_callsite",
            "selected caller callsite",
            "fixed exact-code updateSDFEffects Group call offset",
        ),
        (
            caller["symbolStart"] + CALLER_RETURN_OFFSET,
            "selected_caller_return",
            "selected caller return",
            "enabled until every case-22 iteration in the Group call closes",
        ),
    )
    installed = []
    for address, callback, label, selection in specifications:
        breakpoint = target.BreakpointCreateByAddress(address)
        if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
            raise RuntimeError(label + " breakpoint is unresolved")
        _set_callback(breakpoint, callback, label)
        installed.append(breakpoint)
        _append_breakpoint_record(
            trace, breakpoint, callback, label, selection
        )
    (
        _state["wrapperEntryBreakpoint"],
        _state["callsiteBreakpoint"],
        _state["callerReturnBreakpoint"],
    ) = installed
    _set_dynamic_breakpoints_enabled(False)
    trace["bootstrap"] = {
        "observed": True,
        "frame": case22._frame_record(frame),
        "callerEntryPC": frame.GetPC(),
        "callerSymbolStart": caller["symbolStart"],
        "callerCallsiteAddress": caller["symbolStart"] + CALLER_CALL_OFFSET,
        "callerReturnAddress": caller["symbolStart"] + CALLER_RETURN_OFFSET,
    }
    trace["status"] = "complete-callsite-gate-ready"
    _state["bootstrapObserved"] = True
    if _state["bootstrapBreakpoint"] is not None:
        _state["bootstrapBreakpoint"].SetEnabled(False)
    minimal._write_trace()


def bootstrap_caller_entry(frame, _breakpoint_location, _internal_dict):
    try:
        _install_after_caller_entry(frame)
    except Exception as error:
        _failure("bootstrap-caller-entry", error)
    return False


def selected_callsite(frame, _breakpoint_location, _internal_dict):
    try:
        trace = minimal._state["trace"]
        caller = trace["caller"]
        if frame.GetPC() != caller["symbolStart"] + CALLER_CALL_OFFSET:
            raise RuntimeError("selected caller callsite PC differs")
        if _state["selectedByThread"]:
            raise RuntimeError("selected updateSDFEffects Group calls overlap")
        thread_id = frame.GetThread().GetThreadID()
        selected_index = len(trace["selectedCallerCalls"])
        _state["selectedByThread"][thread_id] = {
            "selectedCallerIndex": selected_index,
            "threadID": thread_id,
            "callsiteFrame": case22._frame_record(frame),
            "providerCallIndices": [],
            "completedProviderCallCount": 0,
        }
        _set_dynamic_breakpoints_enabled(True)
        trace["status"] = "complete-selected-caller-active"
    except Exception as error:
        _failure("selected-callsite", error)
    return False


def _selected_group_caller(frame, caller):
    thread = frame.GetThread()
    if thread.GetNumFrames() < 3:
        return None
    group_frame = thread.GetFrameAtIndex(1)
    caller_frame = thread.GetFrameAtIndex(2)
    if (
        group_frame.GetPC()
        != minimal._state["trace"]["group"]["symbolStart"]
        + minimal.GROUP_RETURN_OFFSET
        or (group_frame.GetFunctionName() or "") != group.PRODUCER_FUNCTION
        or caller_frame.GetPC()
        != caller["symbolStart"] + CALLER_RETURN_OFFSET
        or (caller_frame.GetFunctionName() or "") != caller["function"]
    ):
        return None
    return caller_frame


def wrapper_entry(frame, breakpoint_location, internal_dict):
    thread_id = frame.GetThread().GetThreadID()
    selected = _state["selectedByThread"].get(thread_id)
    if selected is None:
        return False
    trace = minimal._state["trace"]
    if _selected_group_caller(frame, trace["caller"]) is None:
        return False
    before = len(trace["calls"])
    result = minimal.wrapper_entry(frame, breakpoint_location, internal_dict)
    after = len(trace["calls"])
    if after == before + 1:
        call_index = after - 1
        call = trace["calls"][call_index]
        call["selectedCallerIndex"] = selected["selectedCallerIndex"]
        call["providerCallIndexWithinSelectedCaller"] = len(
            selected["providerCallIndices"]
        )
        selected["providerCallIndices"].append(call_index)
    elif after != before:
        _failure(
            "selected-wrapper-entry",
            RuntimeError("selected wrapper changed call count unexpectedly"),
        )
    else:
        _failure(
            "selected-wrapper-entry",
            RuntimeError("selected wrapper did not create a provider call"),
        )
    return result


provider_entry = minimal.provider_entry
provider_return = minimal.provider_return


def group_return(frame, breakpoint_location, internal_dict):
    thread_id = frame.GetThread().GetThreadID()
    selected = _state["selectedByThread"].get(thread_id)
    had_pending = thread_id in minimal._state["pendingByThread"]
    result = minimal.group_return(frame, breakpoint_location, internal_dict)
    if selected is not None and had_pending:
        if thread_id in minimal._state["pendingByThread"]:
            _failure(
                "selected-group-return",
                RuntimeError("selected Group return did not close provider call"),
            )
        else:
            selected["completedProviderCallCount"] += 1
    return result


def selected_caller_return(frame, _breakpoint_location, _internal_dict):
    try:
        thread_id = frame.GetThread().GetThreadID()
        selected = _state["selectedByThread"].get(thread_id)
        if selected is None:
            raise RuntimeError("selected caller return lacks its callsite")
        trace = minimal._state["trace"]
        caller = trace["caller"]
        if frame.GetPC() != caller["symbolStart"] + CALLER_RETURN_OFFSET:
            raise RuntimeError("selected caller return PC differs")
        call_indices = selected["providerCallIndices"]
        if (
            not call_indices
            or selected["completedProviderCallCount"] != len(call_indices)
            or thread_id in minimal._state["pendingByThread"]
        ):
            raise RuntimeError(
                "selected caller did not close every case-22 provider call"
            )
        trace["selectedCallerCalls"].append(
            {
                "selectedCallerIndex": selected["selectedCallerIndex"],
                "threadID": thread_id,
                "callsiteFrame": selected["callsiteFrame"],
                "callerReturnFrame": case22._frame_record(frame),
                "providerCallIndices": call_indices,
                "providerCallCount": len(call_indices),
                "allProviderCallsCompleted": True,
            }
        )
        del _state["selectedByThread"][thread_id]
        if not _state["selectedByThread"]:
            _set_dynamic_breakpoints_enabled(False)
        trace["status"] = "between-complete-selected-callers"
        if len(trace["selectedCallerCalls"]) % 16 == 0:
            minimal._write_trace()
    except Exception as error:
        _failure("selected-caller-return", error)
    return False


def finalize():
    if _state["selectedByThread"]:
        _failure(
            "finalize",
            RuntimeError("selected caller remained active at finalization"),
        )
    if not _state["bootstrapObserved"]:
        _failure(
            "finalize",
            RuntimeError("exact caller-entry bootstrap was never observed"),
        )
    minimal.finalize()
    trace = minimal._state["trace"]
    caller_calls = trace["selectedCallerCalls"]
    provider_counts = [value["providerCallCount"] for value in caller_calls]
    trace["finalSelectedCallerCount"] = len(caller_calls)
    trace["finalActiveSelectedCallerCount"] = len(
        _state["selectedByThread"]
    )
    trace["finalMinimumProviderCallsPerSelectedCaller"] = (
        min(provider_counts) if provider_counts else 0
    )
    trace["finalMaximumProviderCallsPerSelectedCaller"] = (
        max(provider_counts) if provider_counts else 0
    )
    trace["finalBootstrapObserved"] = _state["bootstrapObserved"]
    minimal._write_trace()


def __lldb_init_module(debugger, _internal_dict):
    local._apply_local_host_profile()
    minimal.MAXIMUM_CALL_COUNT = MAXIMUM_CALL_COUNT
    minimal._set_callback = _set_callback
    gate._set_callback = _set_callback
    minimal._state.update(
        {
            "trace": _new_trace(),
            "pendingByThread": {},
            "providerBreakpoint": None,
            "wrapperReturnBreakpoint": None,
            "groupReturnBreakpoint": None,
        }
    )
    _state.update(
        {
            "bootstrapBreakpoint": None,
            "callsiteBreakpoint": None,
            "wrapperEntryBreakpoint": None,
            "callerReturnBreakpoint": None,
            "selectedByThread": {},
            "bootstrapObserved": False,
        }
    )
    minimal._write_trace()
    target = debugger.GetSelectedTarget()
    breakpoint = target.BreakpointCreateByName(group.CALLER_FUNCTION)
    if not breakpoint.IsValid():
        raise RuntimeError("pending updateSDFEffects entry breakpoint is invalid")
    _set_callback(
        breakpoint,
        "bootstrap_caller_entry",
        "pending exact caller-entry bootstrap",
    )
    _state["bootstrapBreakpoint"] = breakpoint
    _append_breakpoint_record(
        minimal._state["trace"],
        breakpoint,
        "bootstrap_caller_entry",
        "pending exact caller-entry bootstrap",
        "requested before launch by exact full caller symbol name",
    )
    minimal._state["trace"]["status"] = "pending-caller-entry-bootstrap"
    minimal._write_trace()
