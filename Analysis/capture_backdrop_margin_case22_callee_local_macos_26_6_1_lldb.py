"""Apply the exact macOS 26.6.1 host profile to the frozen case-22 trace.

The Group implementation, caller callsite, case-22 callsite, target offset,
copy-store offset, and render margin layout are unchanged.  This overlay only
substitutes the module UUIDs and the two complete QuartzCore code hashes opened
by the preregistered local-host symbol inventory.
"""

import capture_backdrop_margin_case22_callee_lldb as case22


group = case22.group
base = group.writer.base

LOCAL_SWIFTUICORE_UUID = "99606D45-C40A-3C69-AE51-5F0C4E32E531"
LOCAL_QUARTZCORE_UUID = "F1BA3189-E95A-3ECA-B59A-5A6872754484"
LOCAL_COPY_CODE_SHA256 = (
    "5bdf866c13bfb00d9becada24ff9876f84515fa36acb4ee274785d5176593a1e"
)
LOCAL_SETTER_CODE_SHA256 = (
    "2421048e418c6cdcc7622dd65f881e514e0852687f7920e6c4bdaf75a301f6dd"
)
LOCAL_BOUNDS_CODE_SHA256 = (
    "85a99558cc08c2a693969b55c804cd811e8ef710ac2d02460830f8bf9d6ec85a"
)
LOCAL_GROUP_CODE_SHA256 = (
    "5414dac1e2dce7753af9afe072ceb3b7f938ec894df81bd621866f50d03b015d"
)
LOCAL_CALLER_CODE_SHA256 = (
    "d60a0510382f913b937ceb2c20111c4dcf1b4dd9d6d49388c2fe5c4d2683168c"
)
LOCAL_CALLER_MODULE_OFFSET = 0x9265FC
LOCAL_CALLER_CALL_OFFSET = 0x1680
LOCAL_CALLER_CALL_INSTRUCTION_HEX = "5526e997"
LOCAL_GROUP_MODULE_OFFSET = 0x3715D0
LOCAL_CASE22_TARGET_MODULE_OFFSET = 0x76BC54
LOCAL_CASE22_TARGET_FUNCTION = (
    "SwiftUI._AnyCAFilterProvider.sdfBackdropMargin.getter : CoreGraphics.CGFloat"
)

_case22_new_trace = case22._new_trace
_case22_selected_thread = case22._selected_thread
_pending_trace = {
    "processID": None,
    "threadID": None,
    "invocationIndex": None,
    "callsitePC": None,
}


def _set_local_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def copy_entry(frame, breakpoint_location, internal_dict):
    return group.copy_entry(frame, breakpoint_location, internal_dict)


def margin_setter(frame, breakpoint_location, internal_dict):
    return group.margin_setter(frame, breakpoint_location, internal_dict)


def copy_margin_store(frame, breakpoint_location, internal_dict):
    return group.copy_margin_store(frame, breakpoint_location, internal_dict)


def backdrop_bounds(frame, breakpoint_location, internal_dict):
    return group.backdrop_bounds(frame, breakpoint_location, internal_dict)


def producer_entry(frame, breakpoint_location, internal_dict):
    return group.producer_entry(frame, breakpoint_location, internal_dict)


def producer_stage(frame, breakpoint_location, internal_dict):
    return _deferred_producer_stage(frame, breakpoint_location, internal_dict)


def _deferred_producer_stage(frame, breakpoint_location, internal_dict):
    result = case22._group_producer_stage(frame, breakpoint_location, internal_dict)
    extension = case22._extension()
    try:
        gate = group._extension().get("producerCodeGate")
        if (
            gate is None
            or frame.GetPC() - gate["symbolStart"] != case22.CASE22_CALL_OFFSET
        ):
            return result
        thread = frame.GetThread()
        process_id = thread.GetProcess().GetProcessID()
        thread_id = thread.GetThreadID()
        stack = base._state["groupInvocationStacks"].get(thread_id, [])
        if not stack or stack[-1] is None:
            return result
        invocation_index = stack[-1]
        invocation = group._extension()["invocations"][invocation_index]
        last_stage = invocation["stages"][-1]
        if last_stage.get("discriminatorCase") is not None:
            raise RuntimeError(
                "case-22 call stage unexpectedly carries a discriminator"
            )
        if (
            invocation_index == case22.SELECTED_INVOCATION_INDEX
            and extension["status"] == "initialized"
        ):
            if [stage["instructionOffset"] for stage in invocation["stages"]] != [
                0x0BC,
                0x20C,
                0x268,
            ]:
                raise RuntimeError("selected invocation is not the case-22 path")
            _pending_trace["processID"] = process_id
            _pending_trace["threadID"] = thread_id
            _pending_trace["invocationIndex"] = invocation_index
            _pending_trace["callsitePC"] = frame.GetPC()
            extension["status"] = "instruction-trace-pending-top-level"
            extension["selectedInvocationIndex"] = invocation_index
            case22._write_trace()
            return True
    except Exception as error:
        extension["failures"].append(
            {"stage": "case22-deferred-selection", "message": str(error)}
        )
        extension["status"] = "instruction-trace-failed"
        group._failure("case22-deferred-selection", error)
        case22._write_trace()
    return result


def trace_selected_case22():
    extension = case22._extension()
    process_id = _pending_trace["processID"]
    thread_id = _pending_trace["threadID"]
    invocation_index = _pending_trace["invocationIndex"]
    callsite_pc = _pending_trace["callsitePC"]
    if (
        extension is None
        or process_id is None
        or thread_id is None
        or invocation_index is None
        or callsite_pc is None
    ):
        raise RuntimeError("no deferred case-22 trace is pending")
    if extension["status"] != "instruction-trace-pending-top-level":
        raise RuntimeError("deferred case-22 trace status differs")
    debugger = base._state.get("debugger")
    if debugger is None:
        raise RuntimeError("deferred case-22 trace lacks the debugger")
    process = debugger.GetSelectedTarget().GetProcess()
    case22._require_stopped(process, "deferred case-22 callsite")
    if process.GetProcessID() != process_id:
        raise RuntimeError("deferred case-22 process identity differs")
    thread = process.GetThreadByID(thread_id)
    if not thread.IsValid() or thread.GetThreadID() != thread_id:
        raise RuntimeError("deferred case-22 thread identity differs")
    frame = thread.GetFrameAtIndex(0)
    gate = group._extension().get("producerCodeGate")
    if (
        gate is None
        or frame.GetPC() != callsite_pc
        or callsite_pc != gate["symbolStart"] + case22.CASE22_CALL_OFFSET
    ):
        raise RuntimeError("deferred case-22 callsite identity differs")
    extension["status"] = "instruction-trace-active-top-level"
    case22._write_trace()
    try:
        case22._trace_case22(frame, invocation_index, gate)
    except Exception as error:
        extension["failures"].append(
            {"stage": "case22-callee-trace-top-level", "message": str(error)}
        )
        extension["status"] = "instruction-trace-failed"
        group._failure("case22-callee-trace-top-level", error)
        case22._write_trace()
        return False
    finally:
        _pending_trace["processID"] = None
        _pending_trace["threadID"] = None
        _pending_trace["invocationIndex"] = None
        _pending_trace["callsitePC"] = None
    return True


def _require_unchanged_structural_contract():
    expected = (
        (group.PRODUCER_BYTE_COUNT, 732, "Group byte count"),
        (group.PRODUCER_CODE_SHA256, LOCAL_GROUP_CODE_SHA256, "Group code hash"),
        (group.PRODUCER_MODULE_OFFSET, LOCAL_GROUP_MODULE_OFFSET, "Group offset"),
        (
            group.CALLER_RETURN_AFTER_PRODUCER_OFFSET,
            LOCAL_CALLER_CALL_OFFSET + 4,
            "caller return offset",
        ),
        (case22.CASE22_CALL_OFFSET, 0x268, "case-22 call offset"),
        (case22.CASE22_RETURN_OFFSET, 0x26C, "case-22 return offset"),
        (
            case22.CASE22_TARGET_MODULE_OFFSET,
            LOCAL_CASE22_TARGET_MODULE_OFFSET,
            "case-22 target offset",
        ),
        (case22.CASE22_INSTRUCTION_HEX, "910b3fd7", "case-22 instruction"),
        (base.COPY_BYTE_COUNT, 1640, "copy byte count"),
        (base.COPY_MARGIN_STORE_OFFSET, 0x3B4, "copy store offset"),
        (base.COPY_MARGIN_STORE_INSTRUCTION_HEX, "a02600bd", "copy store"),
        (base.SETTER_BYTE_COUNT, 96, "setter byte count"),
        (base.BOUNDS_BYTE_COUNT, 80, "bounds byte count"),
        (base.RENDER_MARGIN_OFFSET, 0x24, "render margin offset"),
    )
    for actual, required, label in expected:
        if actual != required:
            raise RuntimeError(label + " differs from the frozen adapter")


def _apply_local_host_profile():
    _require_unchanged_structural_contract()
    base.QUARTZCORE_UUID = LOCAL_QUARTZCORE_UUID
    base.COPY_CODE_SHA256 = LOCAL_COPY_CODE_SHA256
    base.SETTER_CODE_SHA256 = LOCAL_SETTER_CODE_SHA256
    base.BOUNDS_CODE_SHA256 = LOCAL_BOUNDS_CODE_SHA256
    group.SWIFTUICORE_UUID = LOCAL_SWIFTUICORE_UUID


def _new_trace():
    trace = _case22_new_trace()
    trace["classification"] = (
        "output-blind execution of the frozen case-22 diagnostic under the "
        "exact macOS 26.6.1 local-host code profile; no prospective public-input, "
        "optical, physical-output, production, or parity authority"
    )
    trace["localHostProfile"] = {
        "macOSProductVersion": "26.6.1",
        "macOSBuildVersion": "25G76",
        "swiftUICoreUUID": LOCAL_SWIFTUICORE_UUID,
        "quartzCoreUUID": LOCAL_QUARTZCORE_UUID,
        "groupCodeSHA256": LOCAL_GROUP_CODE_SHA256,
        "groupModuleOffset": LOCAL_GROUP_MODULE_OFFSET,
        "callerCodeSHA256": LOCAL_CALLER_CODE_SHA256,
        "callerModuleOffset": LOCAL_CALLER_MODULE_OFFSET,
        "callerCallOffset": LOCAL_CALLER_CALL_OFFSET,
        "callerCallInstructionHex": LOCAL_CALLER_CALL_INSTRUCTION_HEX,
        "case22TargetModuleOffset": LOCAL_CASE22_TARGET_MODULE_OFFSET,
        "case22TargetFunctionOpenedByStaticLookup": LOCAL_CASE22_TARGET_FUNCTION,
        "copyCodeSHA256": LOCAL_COPY_CODE_SHA256,
        "setterCodeSHA256": LOCAL_SETTER_CODE_SHA256,
        "boundsCodeSHA256": LOCAL_BOUNDS_CODE_SHA256,
        "retinaBaselineBackingScaleFactor": 2,
        "instructionTraceDispatch": (
            "breakpoint callback records the fixed structural selection and "
            "returns true without stepping; the frozen instruction loop runs "
            "from the next top-level LLDB script command on the exact stopped "
            "process, thread, and callsite"
        ),
        "capturedMarginUsedForRuntimeSelection": False,
        "capturedCropUsedForRuntimeSelection": False,
        "capturedImageUsedForRuntimeSelection": False,
        "capturedPixelUsedForRuntimeSelection": False,
    }
    return trace


def finalize():
    case22.finalize()


def __lldb_init_module(debugger, internal_dict):
    _apply_local_host_profile()
    group._set_callback = _set_local_callback
    case22._selected_thread = _case22_selected_thread
    case22._new_trace = _new_trace
    case22.__lldb_init_module(debugger, internal_dict)
    group.producer_stage = _deferred_producer_stage
