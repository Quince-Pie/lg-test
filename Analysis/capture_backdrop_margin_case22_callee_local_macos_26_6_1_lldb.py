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
_active_callback_threads = {}


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
    thread = frame.GetThread()
    thread_id = thread.GetThreadID()
    _active_callback_threads[thread_id] = thread
    try:
        return group.producer_stage(frame, breakpoint_location, internal_dict)
    finally:
        _active_callback_threads.pop(thread_id, None)


def _selected_thread(process, thread_id):
    active = _active_callback_threads.get(thread_id)
    if (
        active is not None
        and active.IsValid()
        and active.GetThreadID() == thread_id
        and active.GetProcess().GetProcessID() == process.GetProcessID()
    ):
        return active
    debugger = base._state.get("debugger")
    if debugger is None:
        raise RuntimeError("local thread reacquisition lacks the debugger")
    fresh_process = debugger.GetSelectedTarget().GetProcess()
    if (
        not fresh_process.IsValid()
        or fresh_process.GetProcessID() != process.GetProcessID()
    ):
        raise RuntimeError("local thread reacquisition changed the process")
    thread = fresh_process.GetThreadByID(thread_id)
    selected = fresh_process.GetSelectedThread()
    if (
        not thread.IsValid()
        and selected.IsValid()
        and selected.GetThreadID() == thread_id
    ):
        thread = selected
    if not thread.IsValid():
        for index in range(fresh_process.GetNumThreads()):
            candidate = fresh_process.GetThreadAtIndex(index)
            if candidate.IsValid() and candidate.GetThreadID() == thread_id:
                thread = candidate
                break
    if not thread.IsValid() or thread.GetThreadID() != thread_id:
        raise RuntimeError("case-22 selected thread is unavailable")
    return thread


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
        "threadReacquisition": (
            "active callback SBThread across synchronous steps, then fresh "
            "selected-target process fallback; every path requires unchanged "
            "process ID and exact thread ID"
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
    case22._selected_thread = _selected_thread
    case22._new_trace = _new_trace
    case22.__lldb_init_module(debugger, internal_dict)
