"""Gate the minimal provider matrix at the exact updateSDFEffects callsite.

The first minimal adapter stopped on every Group-owned wrapper invocation.  It
therefore broadened the frozen domain and paid debugger overhead for unrelated
callers.  This overlay arms the four exact case-22 callbacks only between the
authenticated ``updateSDFEffects+0x1680`` Group call and its ``+0x1684``
return.  Captured values never participate in arming or selection.
"""

import capture_backdrop_margin_case22_provider_object_matrix_minimal_local_macos_26_6_1_lldb as frozen


local = frozen.local
group = frozen.group
field = frozen.field
case22 = frozen.case22
base = frozen.base

CALLER_BYTE_COUNT = 6844
CALLER_CALL_OFFSET = local.LOCAL_CALLER_CALL_OFFSET
CALLER_RETURN_OFFSET = group.CALLER_RETURN_AFTER_PRODUCER_OFFSET

_minimal_new_trace = frozen._new_trace


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _new_trace():
    trace = _minimal_new_trace()
    trace["classification"] = (
        "output-blind callsite-gated minimal provider-object capture of the "
        "exact updateSDFEffects -> Group.margin -> wrapper -> DesignLibrary "
        "provider chain; no captured value participates in selection"
    )
    trace["configuration"].update(
        {
            "callerModuleOffset": local.LOCAL_CALLER_MODULE_OFFSET,
            "callerFunction": group.CALLER_FUNCTION,
            "callerByteCount": CALLER_BYTE_COUNT,
            "callerCodeSHA256": local.LOCAL_CALLER_CODE_SHA256,
            "callerGroupCallOffset": CALLER_CALL_OFFSET,
            "callerReturnAfterGroupOffset": CALLER_RETURN_OFFSET,
            "callerGroupCallInstructionHex": (
                local.LOCAL_CALLER_CALL_INSTRUCTION_HEX
            ),
            "selection": (
                "arm only at exact updateSDFEffects+0x1680, retain the exact "
                "Group+0x26c -> wrapper -> provider -> wrapper+0x68 chain, "
                "and disarm at exact updateSDFEffects+0x1684"
            ),
            "activeBreakpointCountPerSelectedCall": 6,
            "perSelectedCallMaximumStopCount": 6,
            "unrelatedWrapperOrProviderCallbacksArmed": False,
        }
    )
    trace["caller"] = {}
    return trace


def _capture_local_caller(frame, expected_offset):
    process = frame.GetThread().GetProcess()
    record = case22._capture_symbol(
        process,
        frame.GetPC(),
        "local updateSDFEffects caller",
    )
    identity = record.get("module", {})
    if (
        identity.get("uuid") != local.LOCAL_SWIFTUICORE_UUID
        or not str(identity.get("path", "")).endswith("/SwiftUICore")
        or record.get("function") != group.CALLER_FUNCTION
        or record.get("symbolStart")
        != identity.get("loadAddress", 0) + local.LOCAL_CALLER_MODULE_OFFSET
        or record.get("symbolOffset") != expected_offset
        or record.get("selectedAddress") != frame.GetPC()
        or record.get("symbolByteCount") != CALLER_BYTE_COUNT
        or record.get("codeSHA256") != local.LOCAL_CALLER_CODE_SHA256
    ):
        raise RuntimeError("local updateSDFEffects exact identity differs")
    if (
        expected_offset == CALLER_CALL_OFFSET
        and record["hex"][2 * CALLER_CALL_OFFSET : 2 * (CALLER_CALL_OFFSET + 4)]
        != local.LOCAL_CALLER_CALL_INSTRUCTION_HEX
    ):
        raise RuntimeError("local updateSDFEffects Group call instruction differs")
    return record


def _selected_breakpoints():
    return (
        frozen._state.get("wrapperEntryBreakpoint"),
        frozen._state.get("providerBreakpoint"),
        frozen._state.get("wrapperReturnBreakpoint"),
        frozen._state.get("groupReturnBreakpoint"),
        frozen._state.get("callerReturnBreakpoint"),
    )


def _set_selected_breakpoints_enabled(enabled):
    for breakpoint in _selected_breakpoints():
        if breakpoint is not None:
            breakpoint.SetEnabled(enabled)


def _install_selected_breakpoints(frame):
    if frozen._state.get("wrapperEntryBreakpoint") is not None:
        return
    frozen._install_exact_breakpoints(frame)
    trace = frozen._state["trace"]
    caller = _capture_local_caller(frame, CALLER_CALL_OFFSET)
    trace["caller"] = caller
    target = frame.GetThread().GetProcess().GetTarget()
    specifications = (
        (trace["wrapper"]["symbolStart"], "wrapper_entry", "wrapper entry"),
        (
            caller["symbolStart"] + CALLER_RETURN_OFFSET,
            "selected_caller_return",
            "selected caller return",
        ),
    )
    installed = []
    for address, callback, label in specifications:
        breakpoint = target.BreakpointCreateByAddress(address)
        if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
            raise RuntimeError(label + " breakpoint is unresolved")
        _set_callback(breakpoint, callback, label)
        breakpoint.SetEnabled(False)
        installed.append(breakpoint)
        trace["breakpoints"].append(
            {
                "name": callback,
                "label": label,
                "id": breakpoint.GetID(),
                "address": address,
                "selection": "enabled only inside the exact selected caller call",
            }
        )
    (
        frozen._state["wrapperEntryBreakpoint"],
        frozen._state["callerReturnBreakpoint"],
    ) = installed
    for breakpoint in (
        frozen._state["providerBreakpoint"],
        frozen._state["wrapperReturnBreakpoint"],
        frozen._state["groupReturnBreakpoint"],
    ):
        breakpoint.SetEnabled(False)
    trace["status"] = "callsite-gate-ready"


def selected_callsite(frame, _breakpoint_location, _internal_dict):
    try:
        if frozen._state["selectedByThread"]:
            raise RuntimeError("selected updateSDFEffects calls overlap")
        if frozen._state.get("wrapperEntryBreakpoint") is None:
            _install_selected_breakpoints(frame)
        trace = frozen._state["trace"]
        caller = trace["caller"]
        if frame.GetPC() != caller["symbolStart"] + CALLER_CALL_OFFSET:
            raise RuntimeError("selected caller callsite PC differs")
        thread_id = frame.GetThread().GetThreadID()
        frozen._state["selectedByThread"][thread_id] = {
            "callCountBefore": len(trace["calls"]),
            "wrapperObserved": False,
            "groupReturnObserved": False,
        }
        _set_selected_breakpoints_enabled(True)
        trace["status"] = "selected-caller-active"
    except Exception as error:
        frozen._failure("selected-callsite", error)
    return False


def wrapper_entry(frame, breakpoint_location, internal_dict):
    thread_id = frame.GetThread().GetThreadID()
    selected = frozen._state["selectedByThread"].get(thread_id)
    if selected is None:
        frozen._failure(
            "selected-wrapper-entry",
            RuntimeError("armed wrapper entry lacks its selected caller"),
        )
        return False
    before = len(frozen._state["trace"]["calls"])
    result = frozen.wrapper_entry(frame, breakpoint_location, internal_dict)
    after = len(frozen._state["trace"]["calls"])
    if after == before + 1:
        selected["wrapperObserved"] = True
    elif after != before:
        frozen._failure(
            "selected-wrapper-entry",
            RuntimeError("selected wrapper changed the call count unexpectedly"),
        )
    return result


provider_entry = frozen.provider_entry
provider_return = frozen.provider_return


def group_return(frame, breakpoint_location, internal_dict):
    thread_id = frame.GetThread().GetThreadID()
    selected = frozen._state["selectedByThread"].get(thread_id)
    had_pending = thread_id in frozen._state["pendingByThread"]
    result = frozen.group_return(frame, breakpoint_location, internal_dict)
    if selected is not None and had_pending:
        if thread_id in frozen._state["pendingByThread"]:
            frozen._failure(
                "selected-group-return",
                RuntimeError("selected Group return did not close its provider call"),
            )
        else:
            selected["groupReturnObserved"] = True
            for breakpoint in (
                frozen._state["wrapperEntryBreakpoint"],
                frozen._state["providerBreakpoint"],
                frozen._state["wrapperReturnBreakpoint"],
                frozen._state["groupReturnBreakpoint"],
            ):
                breakpoint.SetEnabled(False)
    return result


def selected_caller_return(frame, _breakpoint_location, _internal_dict):
    try:
        thread_id = frame.GetThread().GetThreadID()
        selected = frozen._state["selectedByThread"].get(thread_id)
        if selected is None:
            raise RuntimeError("selected caller return lacks its callsite")
        caller = frozen._state["trace"]["caller"]
        if frame.GetPC() != caller["symbolStart"] + CALLER_RETURN_OFFSET:
            raise RuntimeError("selected caller return PC differs")
        if (
            not selected["wrapperObserved"]
            or not selected["groupReturnObserved"]
            or len(frozen._state["trace"]["calls"])
            != selected["callCountBefore"] + 1
            or thread_id in frozen._state["pendingByThread"]
        ):
            raise RuntimeError("selected caller did not complete exactly one provider call")
        frozen._state["callerReturnBreakpoint"].SetEnabled(False)
        del frozen._state["selectedByThread"][thread_id]
        trace = frozen._state["trace"]
        trace["status"] = "between-selected-calls"
        if len(trace["calls"]) % 16 == 0:
            frozen._write_trace()
    except Exception as error:
        frozen._failure("selected-caller-return", error)
    return False


def finalize():
    if frozen._state["selectedByThread"]:
        frozen._failure(
            "finalize",
            RuntimeError("selected caller remained active at finalization"),
        )
    frozen.finalize()
    trace = frozen._state["trace"]
    trace["finalSelectedCallerCount"] = trace.get("finalCallCount", 0)
    trace["finalActiveSelectedCallerCount"] = len(
        frozen._state["selectedByThread"]
    )
    frozen._write_trace()


def __lldb_init_module(debugger, _internal_dict):
    frozen._set_callback = _set_callback
    frozen._state["trace"] = _new_trace()
    frozen._state["selectedByThread"] = {}
    frozen._state["wrapperEntryBreakpoint"] = None
    frozen._state["callerReturnBreakpoint"] = None
    frozen._write_trace()
    target = debugger.GetSelectedTarget()
    swift_module = field._module_by_uuid(
        target,
        local.LOCAL_SWIFTUICORE_UUID,
        "/SwiftUICore",
        "SwiftUICore",
    )
    address = (
        swift_module["loadAddress"]
        + local.LOCAL_CALLER_MODULE_OFFSET
        + CALLER_CALL_OFFSET
    )
    breakpoint = target.BreakpointCreateByAddress(address)
    if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
        raise RuntimeError("selected updateSDFEffects callsite is unresolved")
    _set_callback(breakpoint, "selected_callsite", "selected caller callsite")
    frozen._state["trace"]["breakpoints"].append(
        {
            "name": "selected_callsite",
            "label": "selected caller callsite",
            "id": breakpoint.GetID(),
            "address": address,
            "selection": "fixed exact-code updateSDFEffects Group call offset",
        }
    )
    frozen._state["trace"]["status"] = "selected-callsite-armed"
    frozen._write_trace()
