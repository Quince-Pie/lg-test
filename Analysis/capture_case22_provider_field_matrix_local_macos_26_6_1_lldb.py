"""Capture provider objects inside fixed filter-intervention render brackets.

Every intervention and marker interval is fixed before execution.  Provider
objects and returns are retained for all calls in every interval; no margin,
object field, return, crop, image, or pixel participates in selection.
"""

import json
import os
from pathlib import Path

import capture_backdrop_margin_case22_provider_local_macos_26_6_1_lldb as opened


TRACE_SCHEMA_VERSION = 1

SWIFTUICORE_UUID = "99606D45-C40A-3C69-AE51-5F0C4E32E531"
DESIGN_LIBRARY_UUID = opened.DESIGN_LIBRARY_UUID

MARKER_MANGLED = "$s4main27lgCase22ProviderProbeMarkeryys5Int32V_ADtF"
MARKER_FUNCTION = "main.lgCase22ProviderProbeMarker(Swift.Int32, Swift.Int32) -> ()"
MARKER_BEFORE = 0
MARKER_AFTER = 1

WRAPPER_MODULE_OFFSET = 0x76BC54
WRAPPER_FUNCTION = (
    "SwiftUI._AnyCAFilterProvider.sdfBackdropMargin.getter : CoreGraphics.CGFloat"
)
WRAPPER_BYTE_COUNT = 116
WRAPPER_CODE_SHA256 = "922147f9c8b9cecdc273065e6677312965449069e4cf076e65daa1aba0a9d0ee"
WRAPPER_RETURN_OFFSET = 0x68

PROVIDER_MODULE_OFFSET = opened.PROVIDER_MODULE_OFFSET
PROVIDER_FUNCTION = opened.PROVIDER_FUNCTION
PROVIDER_BYTE_COUNT = opened.PROVIDER_BYTE_COUNT
PROVIDER_CODE_SHA256 = opened.PROVIDER_CODE_SHA256
PROVIDER_OBJECT_BYTE_COUNT = opened.PROVIDER_OBJECT_BYTE_COUNT

INTERVENTION_NAMES = (
    "baseline",
    "blur-radius-3_25",
    "bleed-amount-11_25",
    "bleed-height-0_375",
    "bleed-blur-radius-4_5",
    "bleed-distance0-0_25",
    "bleed-distance1-0_75",
    "shadow-offset-neg3-pos5",
    "shadow-amount-13_5",
    "shadow-height-0_4375",
    "shadow-opacity-0_625",
    "shadow-distance-offset-2_25",
    "shadow-blur-radius-6_5",
    "shadow-radius-7_25",
    "inner-refraction-amount-0_3125",
    "inner-refraction-height-0_5625",
    "outer-refraction-amount-0_6875",
    "outer-refraction-height-0_8125",
    "refraction-distance0-0_1875",
    "refraction-distance1-0_9375",
    "refraction-opacity-0_40625",
    "face-opacity-0_5",
    "sdr-shadow-opacity-0_34375",
)

MAXIMUM_CALLS_PER_INTERVENTION = 128
MAXIMUM_TOTAL_CALLS = len(INTERVENTION_NAMES) * MAXIMUM_CALLS_PER_INTERVENTION

base = opened.base
case22 = opened.case22

_state = {
    "trace": None,
    "activeInterval": None,
    "pendingCalls": {},
    "providerBreakpoint": None,
    "returnBreakpoint": None,
}


def _trace_path():
    raw = os.environ.get("LG_CASE22_PROVIDER_FIELD_TRACE_OUTPUT")
    if not raw:
        raise RuntimeError("LG_CASE22_PROVIDER_FIELD_TRACE_OUTPUT is required")
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
        "case22ProviderFieldMatrixLocalMacOSLldbTraceSchemaVersion": (
            TRACE_SCHEMA_VERSION
        ),
        "classification": (
            "prospectively fixed output-blind provider-object capture across "
            "all filter intervention render brackets; captured values never "
            "select an intervention, call, field, return, crop, image, or pixel"
        ),
        "status": "initialized",
        "configuration": {
            "macOSProductVersion": "26.6.1",
            "macOSBuildVersion": "25G76",
            "architecture": "arm64",
            "material": "regular",
            "appearance": "light",
            "geometry": "circle-127-center",
            "markerMangledName": MARKER_MANGLED,
            "markerFunction": MARKER_FUNCTION,
            "markerBeforePhase": MARKER_BEFORE,
            "markerAfterPhase": MARKER_AFTER,
            "swiftUICoreUUID": SWIFTUICORE_UUID,
            "wrapperModuleOffset": WRAPPER_MODULE_OFFSET,
            "wrapperFunction": WRAPPER_FUNCTION,
            "wrapperByteCount": WRAPPER_BYTE_COUNT,
            "wrapperCodeSHA256": WRAPPER_CODE_SHA256,
            "wrapperReturnOffset": WRAPPER_RETURN_OFFSET,
            "designLibraryUUID": DESIGN_LIBRARY_UUID,
            "providerModuleOffset": PROVIDER_MODULE_OFFSET,
            "providerFunction": PROVIDER_FUNCTION,
            "providerByteCount": PROVIDER_BYTE_COUNT,
            "providerCodeSHA256": PROVIDER_CODE_SHA256,
            "providerObjectByteCount": PROVIDER_OBJECT_BYTE_COUNT,
            "interventionNames": list(INTERVENTION_NAMES),
            "maximumCallsPerIntervention": MAXIMUM_CALLS_PER_INTERVENTION,
            "maximumTotalCalls": MAXIMUM_TOTAL_CALLS,
            "capturedObjectUsedForSelection": False,
            "capturedReturnUsedForSelection": False,
            "capturedMarginUsedForSelection": False,
            "capturedCropUsedForSelection": False,
            "capturedImageUsedForSelection": False,
            "capturedPixelUsedForSelection": False,
        },
        "markerBreakpoint": {},
        "modules": {},
        "wrapper": {},
        "provider": {},
        "intervals": [],
        "calls": [],
        "events": [],
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


def _module_by_uuid(target, expected_uuid, path_suffix, label):
    matches = []
    for index in range(target.GetNumModules()):
        module = target.GetModuleAtIndex(index)
        record = base._module_record(module, target)
        if record.get("uuid") == expected_uuid:
            matches.append(record)
    if (
        len(matches) != 1
        or not str(matches[0].get("path", "")).endswith(path_suffix)
        or not isinstance(matches[0].get("loadAddress"), int)
        or matches[0]["loadAddress"] <= 0
    ):
        raise RuntimeError(label + " module identity differs")
    return matches[0]


def _capture_wrapper(process, module):
    address = module["loadAddress"] + WRAPPER_MODULE_OFFSET
    record = case22._capture_symbol(
        process,
        address,
        "case-22 provider wrapper",
        WRAPPER_MODULE_OFFSET,
    )
    if (
        record.get("function") != WRAPPER_FUNCTION
        or record.get("symbolStart") != address
        or record.get("symbolByteCount") != WRAPPER_BYTE_COUNT
        or record.get("codeSHA256") != WRAPPER_CODE_SHA256
    ):
        raise RuntimeError("case-22 provider wrapper exact identity differs")
    return record


def _capture_provider(process, module):
    return opened._capture_design_symbol(
        process,
        module["loadAddress"] + PROVIDER_MODULE_OFFSET,
        "case-22 field-matrix provider",
        PROVIDER_MODULE_OFFSET,
        PROVIDER_FUNCTION,
        PROVIDER_BYTE_COUNT,
        PROVIDER_CODE_SHA256,
    )


def _install_provider_breakpoints(frame):
    if _state["providerBreakpoint"] is not None:
        return
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    swift_module = _module_by_uuid(
        target, SWIFTUICORE_UUID, "/SwiftUICore", "SwiftUICore"
    )
    design_module = _module_by_uuid(
        target, DESIGN_LIBRARY_UUID, "/DesignLibrary", "DesignLibrary"
    )
    wrapper = _capture_wrapper(process, swift_module)
    provider = _capture_provider(process, design_module)
    provider_breakpoint = target.BreakpointCreateByAddress(provider["symbolStart"])
    return_breakpoint = target.BreakpointCreateByAddress(
        wrapper["symbolStart"] + WRAPPER_RETURN_OFFSET
    )
    for breakpoint, callback, label in (
        (provider_breakpoint, "provider_entry", "provider entry"),
        (return_breakpoint, "provider_return", "provider return"),
    ):
        if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
            raise RuntimeError(label + " breakpoint is unresolved")
        _set_callback(breakpoint, callback, label)
        breakpoint.SetEnabled(False)
    _state["providerBreakpoint"] = provider_breakpoint
    _state["returnBreakpoint"] = return_breakpoint
    trace = _state["trace"]
    trace["modules"] = {
        "swiftUICore": swift_module,
        "designLibrary": design_module,
    }
    trace["wrapper"] = wrapper
    trace["provider"] = provider


def _append_event(kind, record_index):
    events = _state["trace"]["events"]
    event = {
        "eventIndex": len(events),
        "kind": kind,
        "recordIndex": record_index,
    }
    events.append(event)
    return event["eventIndex"]


def marker(frame, _breakpoint_location, _internal_dict):
    try:
        trace = _state["trace"]
        index = base._register_u64(frame, "w0")
        phase = base._register_u64(frame, "w1")
        if not 0 <= index < len(INTERVENTION_NAMES):
            raise RuntimeError("marker intervention index is outside the contract")
        name = INTERVENTION_NAMES[index]
        if phase == MARKER_BEFORE:
            if _state["activeInterval"] is not None:
                raise RuntimeError("marker opened a nested intervention interval")
            if len(trace["intervals"]) != index:
                raise RuntimeError("marker intervention order differs")
            _install_provider_breakpoints(frame)
            interval = {
                "intervalIndex": index,
                "interventionIndex": index,
                "interventionName": name,
                "status": "active",
                "beforeMarkerEventIndex": None,
                "afterMarkerEventIndex": None,
                "callIndices": [],
            }
            trace["intervals"].append(interval)
            interval["beforeMarkerEventIndex"] = _append_event("marker-before", index)
            _state["activeInterval"] = index
            _state["providerBreakpoint"].SetEnabled(True)
            _state["returnBreakpoint"].SetEnabled(True)
            trace["status"] = "intervention-active"
        elif phase == MARKER_AFTER:
            if _state["activeInterval"] != index:
                raise RuntimeError("marker closed the wrong intervention interval")
            if _state["pendingCalls"]:
                raise RuntimeError("marker closed with an unfinished provider call")
            _state["providerBreakpoint"].SetEnabled(False)
            _state["returnBreakpoint"].SetEnabled(False)
            interval = trace["intervals"][index]
            interval["afterMarkerEventIndex"] = _append_event("marker-after", index)
            interval["status"] = "closed"
            interval["finalCallCount"] = len(interval["callIndices"])
            _state["activeInterval"] = None
            trace["status"] = (
                "all-intervals-closed"
                if index == len(INTERVENTION_NAMES) - 1
                else "between-interventions"
            )
        else:
            raise RuntimeError("marker phase differs")
        _write_trace()
    except Exception as error:
        _failure("marker", error)
    return False


def provider_entry(frame, _breakpoint_location, _internal_dict):
    try:
        trace = _state["trace"]
        interval_index = _state["activeInterval"]
        if interval_index is None:
            raise RuntimeError("provider entry occurred outside an active interval")
        interval = trace["intervals"][interval_index]
        if len(interval["callIndices"]) >= MAXIMUM_CALLS_PER_INTERVENTION:
            raise RuntimeError("provider call bound exceeded for intervention")
        calls = trace["calls"]
        if len(calls) >= MAXIMUM_TOTAL_CALLS:
            raise RuntimeError("total provider call bound exceeded")
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        if thread_id in _state["pendingCalls"]:
            raise RuntimeError("nested provider call occurred on one thread")
        process = thread.GetProcess()
        provider = trace["provider"]
        if frame.GetPC() != provider["symbolStart"]:
            raise RuntimeError("provider entry PC differs")
        object_address = base._register_u64(frame, "x20")
        call_index = len(calls)
        call = {
            "callIndex": call_index,
            "intervalIndex": interval_index,
            "interventionIndex": interval["interventionIndex"],
            "interventionName": interval["interventionName"],
            "intervalCallIndex": len(interval["callIndices"]),
            "threadID": thread_id,
            "entryEventIndex": None,
            "returnEventIndex": None,
            "entryFrame": case22._frame_record(frame),
            "providerObject": case22._snapshot(
                process,
                object_address,
                PROVIDER_OBJECT_BYTE_COUNT,
                "case-22 field-matrix provider object",
            ),
            "providerObjectAddress": object_address,
            "returnFrame": None,
            "returnV0RawLittleEndianHex": None,
            "returnF64RawLittleEndianHex": None,
            "returnObject": None,
            "objectChanged": None,
        }
        calls.append(call)
        interval["callIndices"].append(call_index)
        call["entryEventIndex"] = _append_event("provider-entry", call_index)
        _state["pendingCalls"][thread_id] = call_index
        if len(calls) % 16 == 0:
            _write_trace()
    except Exception as error:
        _failure("provider-entry", error)
    return False


def provider_return(frame, _breakpoint_location, _internal_dict):
    try:
        trace = _state["trace"]
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        call_index = _state["pendingCalls"].pop(thread_id, None)
        if call_index is None:
            return False
        call = trace["calls"][call_index]
        wrapper = trace["wrapper"]
        if frame.GetPC() != wrapper["symbolStart"] + WRAPPER_RETURN_OFFSET:
            raise RuntimeError("provider return PC differs")
        v0 = base._register_bytes(frame, "v0")
        if len(v0) != 16:
            raise RuntimeError("provider return v0 byte count differs")
        process = thread.GetProcess()
        returned_object = case22._snapshot(
            process,
            call["providerObjectAddress"],
            PROVIDER_OBJECT_BYTE_COUNT,
            "case-22 field-matrix returned provider object",
        )
        call["returnFrame"] = case22._frame_record(frame)
        call["returnV0RawLittleEndianHex"] = v0.hex()
        call["returnF64RawLittleEndianHex"] = v0[:8].hex()
        call["returnObject"] = returned_object
        call["objectChanged"] = returned_object["hex"] != call["providerObject"]["hex"]
        call["returnEventIndex"] = _append_event("provider-return", call_index)
    except Exception as error:
        _failure("provider-return", error)
    return False


def finalize():
    trace = _state["trace"]
    if trace is None:
        return
    trace["statusBeforeFinalization"] = trace["status"]
    trace["status"] = "finalized"
    trace["finalIntervalCount"] = len(trace["intervals"])
    trace["finalCallCount"] = len(trace["calls"])
    trace["finalEventCount"] = len(trace["events"])
    trace["finalFailureCount"] = len(trace["failures"])
    trace["finalPendingCallCount"] = len(_state["pendingCalls"])
    trace["allIntervalsClosed"] = len(trace["intervals"]) == len(
        INTERVENTION_NAMES
    ) and all(interval.get("status") == "closed" for interval in trace["intervals"])
    _write_trace()


def __lldb_init_module(debugger, _internal_dict):
    _state["trace"] = _new_trace()
    _write_trace()
    target = debugger.GetSelectedTarget()
    breakpoint = target.BreakpointCreateByName(MARKER_MANGLED)
    if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
        raise RuntimeError("case-22 provider marker breakpoint is unresolved")
    _set_callback(breakpoint, "marker", "provider marker")
    _state["trace"]["markerBreakpoint"] = {
        "id": breakpoint.GetID(),
        "requestedName": MARKER_MANGLED,
        "locationCount": breakpoint.GetNumLocations(),
        "selection": "every before/after marker in fixed source order",
    }
    _state["trace"]["status"] = "marker-armed"
    _write_trace()
