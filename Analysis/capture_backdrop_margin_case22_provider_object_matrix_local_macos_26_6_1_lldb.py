"""Capture every live case-22 provider object in one frozen transition.

The matrix selects all ``Group.margin`` case-22 calls by exact control-flow
offset and code identity.  It authenticates the wrapper and DesignLibrary
provider before retaining the 384-byte provider object at entry and return.
No object byte, return, margin, crop, image, or pixel selects a call.
"""

import capture_backdrop_margin_case22_callee_local_macos_26_6_1_lldb as local
import capture_backdrop_margin_case22_provider_local_macos_26_6_1_lldb as opened
import capture_case22_provider_field_matrix_local_macos_26_6_1_retry_lldb as retry


group = local.group
writer = group.writer
base = writer.base
field = retry.frozen

MATRIX_TRACE_SCHEMA_VERSION = 1
MAXIMUM_CALL_COUNT = 512
PROVIDER_OBJECT_OFFSET_FROM_WRAPPER = 0x10

_group_new_trace = group._new_trace
_state = {
    "providerBreakpoint": None,
    "returnBreakpoint": None,
    "pendingByThread": {},
}


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _new_trace():
    trace = _group_new_trace()
    trace["classification"] = (
        "output-blind all-invocation provider-object diagnostic on the exact "
        "local Group.margin case-22 path; no public-input transfer, optical, "
        "physical-output, production, or parity authority"
    )
    trace["case22ProviderObjectMatrix"] = {
        "case22ProviderObjectMatrixTraceSchemaVersion": MATRIX_TRACE_SCHEMA_VERSION,
        "status": "initialized",
        "configuration": {
            "macOSProductVersion": "26.6.1",
            "macOSBuildVersion": "25G76",
            "architecture": "arm64",
            "material": "regular",
            "appearance": "light",
            "geometry": "circle-127-center",
            "direction": "materialize",
            "selection": (
                "every structurally selected Group.margin case-22 indirect "
                "call at exact offset 0x268 in exact source order"
            ),
            "swiftUICoreUUID": local.LOCAL_SWIFTUICORE_UUID,
            "designLibraryUUID": opened.DESIGN_LIBRARY_UUID,
            "wrapperModuleOffset": field.WRAPPER_MODULE_OFFSET,
            "wrapperFunction": field.WRAPPER_FUNCTION,
            "wrapperByteCount": field.WRAPPER_BYTE_COUNT,
            "wrapperCodeSHA256": field.WRAPPER_CODE_SHA256,
            "wrapperReturnOffset": field.WRAPPER_RETURN_OFFSET,
            "providerModuleOffset": opened.PROVIDER_MODULE_OFFSET,
            "providerFunction": opened.PROVIDER_FUNCTION,
            "providerByteCount": opened.PROVIDER_BYTE_COUNT,
            "providerCodeSHA256": opened.PROVIDER_CODE_SHA256,
            "providerObjectByteCount": opened.PROVIDER_OBJECT_BYTE_COUNT,
            "providerObjectOffsetFromWrapper": PROVIDER_OBJECT_OFFSET_FROM_WRAPPER,
            "maximumCallCount": MAXIMUM_CALL_COUNT,
            "capturedObjectUsedForSelection": False,
            "capturedReturnUsedForSelection": False,
            "capturedMarginUsedForSelection": False,
            "capturedCropUsedForSelection": False,
            "capturedImageUsedForSelection": False,
            "capturedPixelUsedForSelection": False,
        },
        "modules": {},
        "wrapper": {},
        "provider": {},
        "breakpoints": [],
        "calls": [],
        "failures": [],
    }
    return trace


def _extension():
    trace = base._state.get("trace")
    if trace is None:
        return None
    return trace.get("case22ProviderObjectMatrix")


def _write_trace():
    base._write_trace()


def _failure(stage, error):
    extension = _extension()
    if extension is not None:
        extension["failures"].append(
            {"stage": str(stage), "message": str(error)}
        )
        extension["status"] = "failed"
    group._failure("provider-object-matrix-" + str(stage), error)
    _write_trace()


def _install_provider_breakpoints(frame):
    if _state["providerBreakpoint"] is not None:
        return
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    swift_module = field._module_by_uuid(
        target,
        local.LOCAL_SWIFTUICORE_UUID,
        "/SwiftUICore",
        "SwiftUICore",
    )
    design_module = field._module_by_uuid(
        target,
        opened.DESIGN_LIBRARY_UUID,
        "/DesignLibrary",
        "DesignLibrary",
    )
    wrapper = retry._capture_local_wrapper(process, swift_module)
    provider = field._capture_provider(process, design_module)
    provider_breakpoint = target.BreakpointCreateByAddress(provider["symbolStart"])
    return_breakpoint = target.BreakpointCreateByAddress(
        wrapper["symbolStart"] + field.WRAPPER_RETURN_OFFSET
    )
    for breakpoint, callback, label in (
        (provider_breakpoint, "provider_entry", "provider entry"),
        (return_breakpoint, "provider_return", "provider return"),
    ):
        if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
            raise RuntimeError(label + " breakpoint is unresolved")
        _set_callback(breakpoint, callback, label)
    _state["providerBreakpoint"] = provider_breakpoint
    _state["returnBreakpoint"] = return_breakpoint
    extension = _extension()
    extension["modules"] = {
        "swiftUICore": swift_module,
        "designLibrary": design_module,
    }
    extension["wrapper"] = wrapper
    extension["provider"] = provider
    extension["breakpoints"] = [
        {
            "name": "providerEntry",
            "id": provider_breakpoint.GetID(),
            "address": provider["symbolStart"],
            "selection": "exact provider symbol entry while a structural case-22 call is pending",
        },
        {
            "name": "providerReturn",
            "id": return_breakpoint.GetID(),
            "address": wrapper["symbolStart"] + field.WRAPPER_RETURN_OFFSET,
            "selection": "exact wrapper return offset while the matching provider call is pending",
        },
    ]
    extension["status"] = "provider-breakpoints-armed"
    _write_trace()


def _current_group_invocation(thread_id):
    stack = base._state["groupInvocationStacks"].get(thread_id, [])
    if not stack or stack[-1] is None:
        return None
    index = stack[-1]
    return index, group._extension()["invocations"][index]


def _last_stage(invocation, offset):
    stages = invocation.get("stages", [])
    if not stages or stages[-1].get("instructionOffset") != offset:
        raise RuntimeError("Group.margin stage record differs")
    return stages[-1]


def producer_stage(frame, breakpoint_location, internal_dict):
    result = group.producer_stage(frame, breakpoint_location, internal_dict)
    try:
        gate = group._extension().get("producerCodeGate")
        if gate is None:
            return result
        offset = frame.GetPC() - gate["symbolStart"]
        if offset not in (0x268, 0x26C):
            return result
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        selected = _current_group_invocation(thread_id)
        if selected is None:
            return result
        invocation_index, invocation = selected
        stage = _last_stage(invocation, offset)
        pending = _state["pendingByThread"]
        if offset == 0x268:
            if thread_id in pending:
                raise RuntimeError("case-22 provider call nested on one thread")
            if len(_extension()["calls"]) >= MAXIMUM_CALL_COUNT:
                raise RuntimeError("provider-object matrix call bound exceeded")
            _install_provider_breakpoints(frame)
            wrapper = _extension()["wrapper"]
            if stage.get("authenticatedIndirectTargetRaw") != wrapper["symbolStart"]:
                raise RuntimeError("case-22 authenticated wrapper target differs")
            wrapper_object = stage["registers"]["x20"]
            if stage["registers"]["x0"] != wrapper_object:
                raise RuntimeError("case-22 wrapper self registers differ")
            pending[thread_id] = {
                "invocationIndex": invocation_index,
                "wrapperObjectAddress": wrapper_object,
                "callIndex": None,
                "providerReturned": False,
            }
            _extension()["status"] = "case22-call-pending"
        else:
            state = pending.get(thread_id)
            if state is None or state["invocationIndex"] != invocation_index:
                raise RuntimeError("case-22 Group return lacks its pending provider call")
            if state["callIndex"] is None or not state["providerReturned"]:
                raise RuntimeError("case-22 Group returned before its provider return")
            call = _extension()["calls"][state["callIndex"]]
            group_raw = stage["vectors"]["v8"]["lowF64RawLittleEndianHex"]
            if group_raw != call["returnF64RawLittleEndianHex"]:
                raise RuntimeError("provider return differs from Group case-22 return")
            call["groupReturnStageIndex"] = stage["stageIndex"]
            call["groupReturnF64RawLittleEndianHex"] = group_raw
            call["providerReturnMatchesGroupBitwise"] = True
            del pending[thread_id]
            _extension()["status"] = "between-case22-calls"
            if len(_extension()["calls"]) % 16 == 0:
                _write_trace()
    except Exception as error:
        _failure("group-stage", error)
    return result


def provider_entry(frame, _breakpoint_location, _internal_dict):
    try:
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        state = _state["pendingByThread"].get(thread_id)
        if state is None:
            return False
        if state["callIndex"] is not None:
            raise RuntimeError("case-22 provider entered twice for one Group call")
        extension = _extension()
        provider = extension["provider"]
        if frame.GetPC() != provider["symbolStart"]:
            raise RuntimeError("provider entry PC differs")
        provider_object = base._register_u64(frame, "x20")
        expected_object = (
            state["wrapperObjectAddress"] + PROVIDER_OBJECT_OFFSET_FROM_WRAPPER
        )
        if provider_object != expected_object:
            raise RuntimeError("provider object is not wrapper self plus 0x10")
        calls = extension["calls"]
        call_index = len(calls)
        call = {
            "callIndex": call_index,
            "groupInvocationIndex": state["invocationIndex"],
            "threadID": thread_id,
            "wrapperObjectAddress": state["wrapperObjectAddress"],
            "providerObjectAddress": provider_object,
            "providerObjectOffsetFromWrapper": (
                provider_object - state["wrapperObjectAddress"]
            ),
            "entryFrame": field.case22._frame_record(frame),
            "entryObject": field.case22._snapshot(
                thread.GetProcess(),
                provider_object,
                opened.PROVIDER_OBJECT_BYTE_COUNT,
                "case-22 provider-object matrix entry",
            ),
            "returnFrame": None,
            "returnF64RawLittleEndianHex": None,
            "returnV0RawLittleEndianHex": None,
            "returnObject": None,
            "objectChanged": None,
            "groupReturnStageIndex": None,
            "groupReturnF64RawLittleEndianHex": None,
            "providerReturnMatchesGroupBitwise": False,
        }
        calls.append(call)
        state["callIndex"] = call_index
        extension["status"] = "provider-active"
    except Exception as error:
        _failure("provider-entry", error)
    return False


def provider_return(frame, _breakpoint_location, _internal_dict):
    try:
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        state = _state["pendingByThread"].get(thread_id)
        if state is None or state["callIndex"] is None:
            return False
        if state["providerReturned"]:
            raise RuntimeError("case-22 provider returned twice for one Group call")
        extension = _extension()
        wrapper = extension["wrapper"]
        if frame.GetPC() != wrapper["symbolStart"] + field.WRAPPER_RETURN_OFFSET:
            raise RuntimeError("provider return PC differs")
        call = extension["calls"][state["callIndex"]]
        v0 = base._register_bytes(frame, "v0")
        if len(v0) != 16:
            raise RuntimeError("provider return v0 byte count differs")
        return_object = field.case22._snapshot(
            thread.GetProcess(),
            call["providerObjectAddress"],
            opened.PROVIDER_OBJECT_BYTE_COUNT,
            "case-22 provider-object matrix return",
        )
        call["returnFrame"] = field.case22._frame_record(frame)
        call["returnV0RawLittleEndianHex"] = v0.hex()
        call["returnF64RawLittleEndianHex"] = v0[:8].hex()
        call["returnObject"] = return_object
        call["objectChanged"] = (
            return_object["hex"] != call["entryObject"]["hex"]
        )
        state["providerReturned"] = True
        extension["status"] = "provider-returned"
    except Exception as error:
        _failure("provider-return", error)
    return False


copy_entry = group.copy_entry
margin_setter = group.margin_setter
copy_margin_store = group.copy_margin_store
backdrop_bounds = group.backdrop_bounds
producer_entry = group.producer_entry


def finalize():
    group.finalize()
    extension = _extension()
    if extension is None:
        return
    extension["statusBeforeFinalization"] = extension["status"]
    extension["status"] = "finalized"
    extension["finalCallCount"] = len(extension["calls"])
    extension["finalReturnedCallCount"] = sum(
        call.get("returnF64RawLittleEndianHex") is not None
        for call in extension["calls"]
    )
    extension["finalGroupLinkedCallCount"] = sum(
        call.get("providerReturnMatchesGroupBitwise") is True
        for call in extension["calls"]
    )
    extension["finalUnchangedObjectCount"] = sum(
        call.get("objectChanged") is False for call in extension["calls"]
    )
    extension["finalPendingThreadCount"] = len(_state["pendingByThread"])
    extension["finalFailureCount"] = len(extension["failures"])
    _write_trace()


def __lldb_init_module(debugger, internal_dict):
    local._apply_local_host_profile()
    group._set_callback = _set_callback
    group._new_trace = _new_trace
    group.__lldb_init_module(debugger, internal_dict)
