"""Join exact live provider calls to structural public timeline markers.

The provider chain is armed only after timeline sample marker zero and is
disarmed at marker 32.  Every selected call is retained; captured object
bytes, returns, public values, images, and pixels never select a call or a
marker.  Marker ordinal alone defines the 0...32 sample order.

LLDB imports this module with Apple's system Python 3.9.
"""

import hashlib

import capture_backdrop_margin_case22_provider_object_matrix_minimal_retry2_local_macos_26_6_1_lldb as frozen


TRACE_SCHEMA_VERSION = 1
MAIN_UUID = "F8B0B6E3-3270-3C94-817F-B4914852D04C"
MAIN_PATH_SUFFIX = "/glass-transition-introspect-721293f"
TIMELINE_MARKER_MANGLED = (
    "$s4main24transitionTimelineSample029_12232F587A4C5CD8B1EEDF696793F2FCLL"
    "6window9rootLayer7capture8progress15outputDirectorySDySSypGSo8NSWindowC_"
    "So7CALayerCSSSd10Foundation3URLVtF"
)
TIMELINE_MARKER_MODULE_OFFSET = 0x8BE38
TIMELINE_MARKER_BYTE_COUNT = 0x674
TIMELINE_MARKER_CODE_SHA256 = (
    "f17ee5eb93c3732cfca195760366e9b7107fb5053d4cff519c5de3092a83fc85"
)
TIMELINE_MARKER_COUNT = 33

retry = frozen.frozen
minimal = frozen.minimal
field = retry.field
case22 = retry.case22

_base_new_trace = frozen._new_trace
_state = {
    "timelineMarkerBreakpoint": None,
    "selectedCallsiteBreakpoint": None,
    "lastMarkerCallCount": 0,
}


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _new_trace():
    trace = _base_new_trace()
    trace["case22ProviderTimelineMarkerTransferLocalMacOSLldbTraceSchemaVersion"] = (
        TRACE_SCHEMA_VERSION
    )
    trace["classification"] = (
        "prospectively frozen value-blind provider capture segmented by the "
        "exact 33-entry public timeline sample marker; marker ordinal and "
        "event order select batches, never captured values or output"
    )
    trace["configuration"].update(
        {
            "mainUUID": MAIN_UUID,
            "timelineMarkerMangledName": TIMELINE_MARKER_MANGLED,
            "timelineMarkerModuleOffset": TIMELINE_MARKER_MODULE_OFFSET,
            "timelineMarkerByteCount": TIMELINE_MARKER_BYTE_COUNT,
            "timelineMarkerCodeSHA256": TIMELINE_MARKER_CODE_SHA256,
            "timelineMarkerCount": TIMELINE_MARKER_COUNT,
            "providerCaptureEnabledAfterMarkerIndex": 0,
            "providerCaptureDisabledAtMarkerIndex": 32,
            "markerOrdinalUsedForSampleSelection": True,
            "capturedPublicInputUsedForSelection": False,
            "capturedTimelineStateUsedForSelection": False,
        }
    )
    trace["timelineMarkerModule"] = {}
    trace["timelineMarkerFunction"] = {}
    trace["timelineMarkers"] = []
    trace["timelineEvents"] = []
    return trace


def _append_event(kind, record_index):
    events = minimal._state["trace"]["timelineEvents"]
    event = {
        "eventIndex": len(events),
        "kind": kind,
        "recordIndex": record_index,
    }
    events.append(event)
    return event["eventIndex"]


def _capture_marker_function(frame):
    trace = minimal._state["trace"]
    module = trace["timelineMarkerModule"]
    process = frame.GetThread().GetProcess()
    record = case22._capture_symbol(
        process,
        module["loadAddress"] + TIMELINE_MARKER_MODULE_OFFSET,
        "public timeline sample marker",
    )
    record_module = record.get("module", {})
    payload = bytes.fromhex(record.get("hex", ""))
    if (
        not isinstance(record.get("function"), str)
        or not record["function"]
        or record.get("selectedAddress") != frame.GetPC()
        or record.get("symbolStart")
        != module["loadAddress"] + TIMELINE_MARKER_MODULE_OFFSET
        or record.get("symbolOffset") != 0
        or record.get("symbolByteCount") != TIMELINE_MARKER_BYTE_COUNT
        or record.get("codeSHA256") != TIMELINE_MARKER_CODE_SHA256
        or hashlib.sha256(payload).hexdigest() != TIMELINE_MARKER_CODE_SHA256
        or record_module.get("uuid") != MAIN_UUID
        or record_module.get("loadAddress") != module["loadAddress"]
        or not str(record_module.get("path", "")).endswith(MAIN_PATH_SUFFIX)
    ):
        raise RuntimeError("public timeline sample marker exact identity differs")
    trace["timelineMarkerFunction"] = record


def timeline_marker(frame, _breakpoint_location, _internal_dict):
    try:
        trace = minimal._state["trace"]
        markers = trace["timelineMarkers"]
        marker_index = len(markers)
        if marker_index >= TIMELINE_MARKER_COUNT:
            raise RuntimeError("public timeline marker count exceeded")
        if frame.GetPC() != (
            trace["timelineMarkerModule"]["loadAddress"] + TIMELINE_MARKER_MODULE_OFFSET
        ):
            raise RuntimeError("public timeline marker PC differs")
        if minimal._state["pendingByThread"] or minimal._state["selectedByThread"]:
            raise RuntimeError("public timeline marker crossed an active provider call")
        if marker_index == 0:
            _capture_marker_function(frame)
        calls = trace["calls"]
        start = _state["lastMarkerCallCount"]
        end = len(calls)
        if not 0 <= start <= end:
            raise RuntimeError("public timeline marker call range differs")
        marker = {
            "markerIndex": marker_index,
            "sampleIndex": marker_index,
            "threadID": frame.GetThread().GetThreadID(),
            "frame": case22._frame_record(frame),
            "precedingCompletedCallStartIndex": start,
            "precedingCompletedCallEndIndexExclusive": end,
            "eventIndex": None,
        }
        markers.append(marker)
        marker["eventIndex"] = _append_event("timeline-marker", marker_index)
        _state["lastMarkerCallCount"] = end
        if marker_index == 0:
            _state["selectedCallsiteBreakpoint"].SetEnabled(True)
        elif marker_index == TIMELINE_MARKER_COUNT - 1:
            _state["selectedCallsiteBreakpoint"].SetEnabled(False)
        minimal._write_trace()
    except Exception as error:
        minimal._failure("timeline-marker", error)
    return False


def selected_callsite(frame, breakpoint_location, internal_dict):
    return frozen.selected_callsite(frame, breakpoint_location, internal_dict)


def wrapper_entry(frame, breakpoint_location, internal_dict):
    before = len(minimal._state["trace"]["calls"])
    result = frozen.wrapper_entry(frame, breakpoint_location, internal_dict)
    calls = minimal._state["trace"]["calls"]
    if len(calls) == before + 1:
        call = calls[before]
        call["timelineEntryEventIndex"] = _append_event("provider-call-entry", before)
    return result


provider_entry = frozen.provider_entry
provider_return = frozen.provider_return


def group_return(frame, breakpoint_location, internal_dict):
    thread_id = frame.GetThread().GetThreadID()
    pending = minimal._state["pendingByThread"].get(thread_id)
    call_index = None if pending is None else pending.get("callIndex")
    result = frozen.group_return(frame, breakpoint_location, internal_dict)
    if call_index is not None and thread_id not in minimal._state["pendingByThread"]:
        call = minimal._state["trace"]["calls"][call_index]
        call["timelineCompletionEventIndex"] = _append_event(
            "provider-call-complete", call_index
        )
    return result


selected_caller_return = frozen.selected_caller_return


def finalize():
    frozen.finalize()
    trace = minimal._state["trace"]
    trace["finalTimelineMarkerCount"] = len(trace["timelineMarkers"])
    trace["finalTimelineEventCount"] = len(trace["timelineEvents"])
    trace["finalMarkerAssignedCallCount"] = _state["lastMarkerCallCount"]
    trace["selectedCallsiteEnabledAtFinalization"] = _state[
        "selectedCallsiteBreakpoint"
    ].IsEnabled()
    minimal._write_trace()


def __lldb_init_module(debugger, internal_dict):
    frozen._set_callback = _set_callback
    frozen._new_trace = _new_trace
    frozen.__lldb_init_module(debugger, internal_dict)
    target = debugger.GetSelectedTarget()
    trace = minimal._state["trace"]
    main_module = field._module_by_uuid(
        target,
        MAIN_UUID,
        MAIN_PATH_SUFFIX,
        "main executable",
    )
    marker_address = main_module["loadAddress"] + TIMELINE_MARKER_MODULE_OFFSET
    marker_breakpoint = target.BreakpointCreateByAddress(marker_address)
    if not marker_breakpoint.IsValid() or marker_breakpoint.GetNumLocations() != 1:
        raise RuntimeError("public timeline marker breakpoint is unresolved")
    _set_callback(marker_breakpoint, "timeline_marker", "public timeline marker")
    selected_record = next(
        record
        for record in trace["breakpoints"]
        if record.get("name") == "selected_callsite"
    )
    selected_breakpoint = target.FindBreakpointByID(selected_record["id"])
    if not selected_breakpoint.IsValid():
        raise RuntimeError("selected provider callsite breakpoint is unavailable")
    selected_breakpoint.SetEnabled(False)
    _state["timelineMarkerBreakpoint"] = marker_breakpoint
    _state["selectedCallsiteBreakpoint"] = selected_breakpoint
    trace["timelineMarkerModule"] = main_module
    trace["breakpoints"].append(
        {
            "name": "timeline_marker",
            "label": "public timeline sample marker",
            "id": marker_breakpoint.GetID(),
            "address": marker_address,
            "selection": "exact main-module function entry and marker ordinal only",
        }
    )
    minimal._write_trace()
