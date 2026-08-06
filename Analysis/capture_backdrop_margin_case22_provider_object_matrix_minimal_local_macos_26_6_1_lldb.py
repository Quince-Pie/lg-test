"""Capture the live provider-object matrix with four exact stops per call.

The inherited writer/Group diagnostic is intentionally not initialized: its
unrelated copy, setter, bounds, entry, and branch-stage breakpoints consume the
fixed presentation-animation clock.  Selection remains structural.  A wrapper
entry is retained only when its immediate caller is exact ``Group.margin``
offset ``0x26c``; the matching exact provider entry, wrapper return, and Group
return are then joined on thread identity without reading an output value.
"""

import json
import os
from pathlib import Path

import capture_backdrop_margin_case22_callee_local_macos_26_6_1_lldb as local
import capture_backdrop_margin_case22_provider_local_macos_26_6_1_lldb as opened
import capture_case22_provider_field_matrix_local_macos_26_6_1_retry_lldb as retry


field = retry.frozen
case22 = field.case22
base = field.base
group = local.group

TRACE_SCHEMA_VERSION = 1
TRACE_OUTPUT_ENVIRONMENT = "LG_CASE22_PROVIDER_OBJECT_MATRIX_MINIMAL_TRACE_OUTPUT"
MAXIMUM_CALL_COUNT = 512
PROVIDER_OBJECT_OFFSET_FROM_WRAPPER = 0x10
GROUP_RETURN_OFFSET = 0x26C

_state = {
    "trace": None,
    "pendingByThread": {},
    "providerBreakpoint": None,
    "wrapperReturnBreakpoint": None,
    "groupReturnBreakpoint": None,
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
        "case22ProviderObjectMatrixMinimalLocalMacOSLldbTraceSchemaVersion": (
            TRACE_SCHEMA_VERSION
        ),
        "classification": (
            "output-blind minimal all-live-call provider-object capture; exact "
            "Group caller, wrapper, provider, and return control flow select "
            "calls, never an object byte, return, margin, crop, image, or pixel"
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
            "swiftUICoreUUID": local.LOCAL_SWIFTUICORE_UUID,
            "designLibraryUUID": opened.DESIGN_LIBRARY_UUID,
            "groupModuleOffset": local.LOCAL_GROUP_MODULE_OFFSET,
            "groupFunction": group.PRODUCER_FUNCTION,
            "groupByteCount": group.PRODUCER_BYTE_COUNT,
            "groupCodeSHA256": local.LOCAL_GROUP_CODE_SHA256,
            "groupReturnOffset": GROUP_RETURN_OFFSET,
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
            "activeBreakpointCountPerSelectedCall": 4,
            "inheritedWriterOrGroupBreakpointsInstalled": False,
            "capturedObjectUsedForSelection": False,
            "capturedReturnUsedForSelection": False,
            "capturedMarginUsedForSelection": False,
            "capturedCropUsedForSelection": False,
            "capturedImageUsedForSelection": False,
            "capturedPixelUsedForSelection": False,
        },
        "modules": {},
        "group": {},
        "wrapper": {},
        "provider": {},
        "breakpoints": [],
        "calls": [],
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


def _capture_local_group(process, module):
    address = module["loadAddress"] + local.LOCAL_GROUP_MODULE_OFFSET
    record = case22._capture_symbol(process, address, "local Group.margin")
    identity = record.get("module", {})
    if (
        identity.get("uuid") != local.LOCAL_SWIFTUICORE_UUID
        or not str(identity.get("path", "")).endswith("/SwiftUICore")
        or identity.get("loadAddress") != module["loadAddress"]
        or address - identity.get("loadAddress", 0)
        != local.LOCAL_GROUP_MODULE_OFFSET
        or record.get("function") != group.PRODUCER_FUNCTION
        or record.get("symbolStart") != address
        or record.get("symbolByteCount") != group.PRODUCER_BYTE_COUNT
        or record.get("codeSHA256") != local.LOCAL_GROUP_CODE_SHA256
    ):
        raise RuntimeError("local Group.margin exact identity differs")
    return record


def _install_exact_breakpoints(frame):
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
    group_record = _capture_local_group(process, swift_module)
    wrapper = retry._capture_local_wrapper(process, swift_module)
    provider = field._capture_provider(process, design_module)
    specifications = (
        (provider["symbolStart"], "provider_entry", "provider entry"),
        (
            wrapper["symbolStart"] + field.WRAPPER_RETURN_OFFSET,
            "provider_return",
            "provider return",
        ),
        (
            group_record["symbolStart"] + GROUP_RETURN_OFFSET,
            "group_return",
            "Group return",
        ),
    )
    installed = []
    for address, callback, label in specifications:
        breakpoint = target.BreakpointCreateByAddress(address)
        if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
            raise RuntimeError(label + " breakpoint is unresolved")
        _set_callback(breakpoint, callback, label)
        installed.append(breakpoint)
    (
        _state["providerBreakpoint"],
        _state["wrapperReturnBreakpoint"],
        _state["groupReturnBreakpoint"],
    ) = installed
    trace = _state["trace"]
    trace["modules"] = {
        "swiftUICore": swift_module,
        "designLibrary": design_module,
    }
    trace["group"] = group_record
    trace["wrapper"] = wrapper
    trace["provider"] = provider
    for breakpoint, (address, callback, label) in zip(installed, specifications):
        trace["breakpoints"].append(
            {
                "name": callback,
                "label": label,
                "id": breakpoint.GetID(),
                "address": address,
                "selection": "fixed offset in exact authenticated code",
            }
        )
    trace["status"] = "exact-breakpoints-armed"


def _immediate_caller(frame, group_record):
    thread = frame.GetThread()
    if thread.GetNumFrames() < 2:
        return None
    caller = thread.GetFrameAtIndex(1)
    if caller.GetPC() != group_record["symbolStart"] + GROUP_RETURN_OFFSET:
        return None
    if (caller.GetFunctionName() or "") != group.PRODUCER_FUNCTION:
        return None
    return caller


def wrapper_entry(frame, _breakpoint_location, _internal_dict):
    try:
        process = frame.GetThread().GetProcess()
        if _state["providerBreakpoint"] is None:
            _install_exact_breakpoints(frame)
        trace = _state["trace"]
        wrapper = trace["wrapper"]
        if frame.GetPC() != wrapper["symbolStart"]:
            raise RuntimeError("wrapper entry PC differs")
        caller = _immediate_caller(frame, trace["group"])
        if caller is None:
            return False
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        pending = _state["pendingByThread"]
        if thread_id in pending:
            raise RuntimeError("minimal provider call nested on one thread")
        calls = trace["calls"]
        if len(calls) >= MAXIMUM_CALL_COUNT:
            raise RuntimeError("minimal provider-object matrix call bound exceeded")
        wrapper_object = base._register_u64(frame, "x0")
        provider_object = wrapper_object + PROVIDER_OBJECT_OFFSET_FROM_WRAPPER
        call_index = len(calls)
        call = {
            "callIndex": call_index,
            "threadID": thread_id,
            "wrapperObjectAddress": wrapper_object,
            "providerObjectAddress": provider_object,
            "providerObjectOffsetFromWrapper": PROVIDER_OBJECT_OFFSET_FROM_WRAPPER,
            "wrapperEntryFrame": case22._frame_record(frame),
            "groupCallerFrame": case22._frame_record(caller),
            "wrapperEntryObject": case22._snapshot(
                process,
                provider_object,
                opened.PROVIDER_OBJECT_BYTE_COUNT,
                "minimal wrapper-entry provider object",
            ),
            "providerEntryFrame": None,
            "providerEntryObject": None,
            "providerEntryMatchesWrapperObjectBitwise": False,
            "wrapperReturnFrame": None,
            "returnV0RawLittleEndianHex": None,
            "returnF64RawLittleEndianHex": None,
            "returnObject": None,
            "objectChanged": None,
            "groupReturnFrame": None,
            "groupReturnV0RawLittleEndianHex": None,
            "providerReturnMatchesGroupBitwise": False,
        }
        calls.append(call)
        pending[thread_id] = {
            "callIndex": call_index,
            "providerEntered": False,
            "providerReturned": False,
        }
        trace["status"] = "wrapper-active"
        if call_index == 0:
            _write_trace()
    except Exception as error:
        _failure("wrapper-entry", error)
    return False


def provider_entry(frame, _breakpoint_location, _internal_dict):
    try:
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        state = _state["pendingByThread"].get(thread_id)
        if state is None:
            return False
        if state["providerEntered"]:
            raise RuntimeError("minimal provider entered twice for one wrapper")
        trace = _state["trace"]
        provider = trace["provider"]
        if frame.GetPC() != provider["symbolStart"]:
            raise RuntimeError("minimal provider entry PC differs")
        call = trace["calls"][state["callIndex"]]
        provider_object = base._register_u64(frame, "x20")
        if provider_object != call["providerObjectAddress"]:
            raise RuntimeError("minimal provider object is not wrapper self plus 0x10")
        snapshot = case22._snapshot(
            thread.GetProcess(),
            provider_object,
            opened.PROVIDER_OBJECT_BYTE_COUNT,
            "minimal provider-entry object",
        )
        if snapshot["hex"] != call["wrapperEntryObject"]["hex"]:
            raise RuntimeError("provider entry object differs from wrapper-entry object")
        call["providerEntryFrame"] = case22._frame_record(frame)
        call["providerEntryObject"] = snapshot
        call["providerEntryMatchesWrapperObjectBitwise"] = True
        state["providerEntered"] = True
        trace["status"] = "provider-active"
    except Exception as error:
        _failure("provider-entry", error)
    return False


def provider_return(frame, _breakpoint_location, _internal_dict):
    try:
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        state = _state["pendingByThread"].get(thread_id)
        if state is None:
            return False
        if not state["providerEntered"] or state["providerReturned"]:
            raise RuntimeError("minimal provider return state differs")
        trace = _state["trace"]
        wrapper = trace["wrapper"]
        if frame.GetPC() != wrapper["symbolStart"] + field.WRAPPER_RETURN_OFFSET:
            raise RuntimeError("minimal wrapper return PC differs")
        call = trace["calls"][state["callIndex"]]
        v0 = base._register_bytes(frame, "v0")
        if len(v0) != 16:
            raise RuntimeError("minimal provider return v0 byte count differs")
        return_object = case22._snapshot(
            thread.GetProcess(),
            call["providerObjectAddress"],
            opened.PROVIDER_OBJECT_BYTE_COUNT,
            "minimal provider-return object",
        )
        call["wrapperReturnFrame"] = case22._frame_record(frame)
        call["returnV0RawLittleEndianHex"] = v0.hex()
        call["returnF64RawLittleEndianHex"] = v0[:8].hex()
        call["returnObject"] = return_object
        call["objectChanged"] = (
            return_object["hex"] != call["providerEntryObject"]["hex"]
        )
        state["providerReturned"] = True
        trace["status"] = "provider-returned"
    except Exception as error:
        _failure("provider-return", error)
    return False


def group_return(frame, _breakpoint_location, _internal_dict):
    try:
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        state = _state["pendingByThread"].get(thread_id)
        if state is None:
            return False
        if not state["providerReturned"]:
            raise RuntimeError("Group returned before the minimal provider return")
        trace = _state["trace"]
        group_record = trace["group"]
        if frame.GetPC() != group_record["symbolStart"] + GROUP_RETURN_OFFSET:
            raise RuntimeError("minimal Group return PC differs")
        call = trace["calls"][state["callIndex"]]
        v0 = base._register_bytes(frame, "v0")
        if len(v0) != 16 or v0.hex() != call["returnV0RawLittleEndianHex"]:
            raise RuntimeError("provider return differs from Group input bitwise")
        call["groupReturnFrame"] = case22._frame_record(frame)
        call["groupReturnV0RawLittleEndianHex"] = v0.hex()
        call["providerReturnMatchesGroupBitwise"] = True
        del _state["pendingByThread"][thread_id]
        trace["status"] = "between-calls"
        if len(trace["calls"]) % 16 == 0:
            _write_trace()
    except Exception as error:
        _failure("group-return", error)
    return False


def finalize():
    trace = _state["trace"]
    if trace is None:
        return
    trace["statusBeforeFinalization"] = trace["status"]
    trace["status"] = "finalized"
    trace["finalCallCount"] = len(trace["calls"])
    trace["finalProviderEnteredCallCount"] = sum(
        call.get("providerEntryMatchesWrapperObjectBitwise") is True
        for call in trace["calls"]
    )
    trace["finalReturnedCallCount"] = sum(
        call.get("returnF64RawLittleEndianHex") is not None
        for call in trace["calls"]
    )
    trace["finalGroupLinkedCallCount"] = sum(
        call.get("providerReturnMatchesGroupBitwise") is True
        for call in trace["calls"]
    )
    trace["finalUnchangedObjectCount"] = sum(
        call.get("objectChanged") is False for call in trace["calls"]
    )
    trace["finalPendingThreadCount"] = len(_state["pendingByThread"])
    trace["finalFailureCount"] = len(trace["failures"])
    _write_trace()


def __lldb_init_module(debugger, _internal_dict):
    _state["trace"] = _new_trace()
    _write_trace()
    target = debugger.GetSelectedTarget()
    breakpoint = target.BreakpointCreateByName(field.WRAPPER_FUNCTION)
    if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
        raise RuntimeError("minimal wrapper-entry breakpoint is unresolved")
    _set_callback(breakpoint, "wrapper_entry", "wrapper entry")
    _state["trace"]["breakpoints"].append(
        {
            "name": "wrapper_entry",
            "label": "wrapper entry",
            "id": breakpoint.GetID(),
            "requestedFunction": field.WRAPPER_FUNCTION,
            "selection": "exact wrapper symbol entry with exact Group return-address caller",
        }
    )
    _state["trace"]["status"] = "wrapper-breakpoint-armed"
    _write_trace()
