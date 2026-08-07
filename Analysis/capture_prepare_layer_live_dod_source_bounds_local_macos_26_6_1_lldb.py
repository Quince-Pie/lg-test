"""Capture every live GlassBackground DOD source rectangle structurally.

This calibration overlay adds one code-hashed breakpoint immediately after
the live DOD implementation loads q0 and q1 from its Layer source.  It records
all hits and marker ordering without reading either rectangle for selection.
LLDB imports this file with Apple's Python 3.9.
"""

import hashlib

import capture_prepare_layer_crop_policy_holdout_live_local_macos_26_6_1_lldb as live_base
import prepare_layer_live_transport_local_macos_26_6_1 as live


holdout_base = live_base.holdout_base
crop_base = holdout_base.union_base.crop_base
capture_base = crop_base.capture_base

EXTENSION_SCHEMA_VERSION = 1
DOD_FUNCTION = (
    "CA::OGL::GlassBackgroundFilter::DOD(CA::Render::Filter const*, "
    "CA::Render::Layer const*, CA::Rect&) const"
)
DOD_RELATIVE_TO_PREPARE_LAYER = -0x16220
DOD_SYMBOL_BYTE_COUNT = 1136
DOD_CODE_SHA256 = "d44b226f8edbfcb8fd37bc0f15a48b583df08063dc812e28cd06b1398d2f1678"
SOURCE_REGISTERS_OFFSET = 0x200
SOURCE_REGISTERS_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = "e00703ad"
DOD_RETURN_OFFSET = 0x448
DOD_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = "fd7b4fa9"
MAXIMUM_DOD_HIT_COUNT = 4096


_state = {
    "dodBreakpoint": None,
    "dodReturnBreakpoint": None,
    "dodHitCount": 0,
    "dodReturnCount": 0,
    "eventSequence": 0,
    "pendingByThread": {},
}


def _extension():
    trace = crop_base._state.get("trace")
    if trace is None:
        return None
    return trace.get("liveDODSourceBoundsExtension")


def _write_trace():
    crop_base._write_trace()


def _failure(stage, error):
    extension = _extension()
    if extension is not None:
        extension["failures"].append(
            {"stage": str(stage), "message": str(error)}
        )
    crop_base._failure("live-dod-source-" + str(stage), error)


def _next_event(kind):
    _state["eventSequence"] += 1
    event = {
        "sequence": _state["eventSequence"],
        "kind": str(kind),
    }
    _extension()["events"].append(event)
    return event


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _install_proxy_callbacks():
    entry = crop_base._state.get("prepareEntryBreakpoint")
    marker = crop_base._state.get("markerBreakpoint")
    union_call = holdout_base.union_base._state.get("unionCallBreakpoint")
    union_return = holdout_base.union_base._state.get("unionReturnBreakpoint")
    store = holdout_base._state.get("storeBreakpoint")
    callbacks = (
        (entry, "prepare_layer_entry", "prepare entry"),
        (marker, "crop_transfer_marker", "crop marker"),
        (union_call, "crop_union_call", "union call"),
        (union_return, "crop_union_return", "union return"),
        (store, "nested_crop_store", "crop store"),
    )
    for breakpoint, callback, label in callbacks:
        if breakpoint is not None:
            _set_callback(breakpoint, callback, label)


def _install_dod_breakpoint(frame):
    if _state["dodBreakpoint"] is not None:
        return
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    prepare_start = crop_base._state["prepareLayer"]["symbolStart"]
    start = prepare_start + DOD_RELATIVE_TO_PREPARE_LAYER
    end = start + DOD_SYMBOL_BYTE_COUNT
    resolved = target.ResolveLoadAddress(start)
    symbol = resolved.GetSymbol()
    if not symbol.IsValid():
        raise RuntimeError("live DOD symbol is invalid")
    function_name = resolved.GetFunction().GetName()
    if function_name != DOD_FUNCTION and symbol.GetName() != DOD_FUNCTION:
        raise RuntimeError("live DOD function differs")
    if (
        symbol.GetStartAddress().GetLoadAddress(target) != start
        or symbol.GetEndAddress().GetLoadAddress(target) != end
    ):
        raise RuntimeError("live DOD symbol bounds differ")
    if resolved.GetModule().GetUUIDString() != live.QUARTZCORE_UUID:
        raise RuntimeError("live DOD QuartzCore UUID differs")
    code = capture_base._read_memory(
        process, start, DOD_SYMBOL_BYTE_COUNT, "live DOD complete code"
    )
    digest = hashlib.sha256(code).hexdigest()
    if digest != DOD_CODE_SHA256:
        raise RuntimeError("live DOD complete code differs")
    instruction = code[
        SOURCE_REGISTERS_OFFSET : SOURCE_REGISTERS_OFFSET + 4
    ]
    if instruction.hex() != SOURCE_REGISTERS_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX:
        raise RuntimeError("live DOD source-register instruction differs")
    breakpoint = target.BreakpointCreateByAddress(
        start + SOURCE_REGISTERS_OFFSET
    )
    if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
        raise RuntimeError("live DOD source breakpoint is unresolved")
    _set_callback(breakpoint, "dod_source_bounds", "live DOD source")
    return_instruction = code[DOD_RETURN_OFFSET : DOD_RETURN_OFFSET + 4]
    if return_instruction.hex() != DOD_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX:
        raise RuntimeError("live DOD return instruction differs")
    return_breakpoint = target.BreakpointCreateByAddress(start + DOD_RETURN_OFFSET)
    if (
        not return_breakpoint.IsValid()
        or return_breakpoint.GetNumLocations() != 1
    ):
        raise RuntimeError("live DOD return breakpoint is unresolved")
    _set_callback(return_breakpoint, "dod_return", "live DOD return")
    _state["dodBreakpoint"] = breakpoint
    _state["dodReturnBreakpoint"] = return_breakpoint
    extension = _extension()
    extension["codeIdentity"] = {
        "function": DOD_FUNCTION,
        "relativeToPrepareLayer": DOD_RELATIVE_TO_PREPARE_LAYER,
        "symbolStart": start,
        "symbolEnd": end,
        "symbolByteCount": len(code),
        "codeSHA256": digest,
        "sourceRegistersOffset": SOURCE_REGISTERS_OFFSET,
        "sourceRegistersAddress": start + SOURCE_REGISTERS_OFFSET,
        "sourceRegistersInstructionRawLittleEndianHex": instruction.hex(),
        "breakpointID": breakpoint.GetID(),
        "returnOffset": DOD_RETURN_OFFSET,
        "returnAddress": start + DOD_RETURN_OFFSET,
        "returnInstructionRawLittleEndianHex": return_instruction.hex(),
        "returnBreakpointID": return_breakpoint.GetID(),
        "quartzCoreUUID": resolved.GetModule().GetUUIDString(),
    }
    extension["status"] = "live-dod-source-breakpoint-active"


def prepare_layer_entry(frame, breakpoint_location, internal_dict):
    result = live_base.prepare_layer_entry(
        frame, breakpoint_location, internal_dict
    )
    try:
        if crop_base._state.get("prepareLayer") is not None:
            _install_dod_breakpoint(frame)
        _install_proxy_callbacks()
        _write_trace()
    except Exception as error:
        _failure("prepare-entry", error)
    return result


def crop_transfer_marker(frame, breakpoint_location, internal_dict):
    result = live_base.crop_transfer_marker(
        frame, breakpoint_location, internal_dict
    )
    try:
        event = _next_event("qualified-marker-callback")
        event["qualifiedMarkerCountAfterCallback"] = len(
            crop_base._state["trace"]["qualifiedRecords"]
        )
    except Exception as error:
        _failure("marker-event", error)
    return result


def crop_union_call(frame, breakpoint_location, internal_dict):
    return live_base.crop_union_call(
        frame, breakpoint_location, internal_dict
    )


def crop_union_return(frame, breakpoint_location, internal_dict):
    return live_base.crop_union_return(
        frame, breakpoint_location, internal_dict
    )


def nested_crop_store(frame, breakpoint_location, internal_dict):
    return live_base.nested_crop_store(
        frame, breakpoint_location, internal_dict
    )


def dod_source_bounds(frame, breakpoint_location, _internal_dict):
    try:
        _state["dodHitCount"] += 1
        if _state["dodHitCount"] > MAXIMUM_DOD_HIT_COUNT:
            raise RuntimeError("live DOD source hit bound exceeded")
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        address = breakpoint_location.GetAddress().GetLoadAddress(target)
        expected = _extension()["codeIdentity"]["sourceRegistersAddress"]
        if frame.GetPC() != expected or address != expected:
            raise RuntimeError("live DOD source PC differs")
        event = _next_event("dod-source-registers")
        record = {
            "recordIndex": len(_extension()["records"]),
            "hitIndex": _state["dodHitCount"],
            "eventSequence": event["sequence"],
            "threadID": frame.GetThread().GetThreadID(),
            "pc": frame.GetPC(),
            "registers": capture_base._register_snapshot(
                frame, ("x19", "x21", "pc", "v0", "v1")
            ),
            "backtrace": capture_base._backtrace(frame.GetThread()),
            "complete": False,
        }
        _extension()["records"].append(record)
        event["recordIndex"] = record["recordIndex"]
        pending = _state["pendingByThread"].setdefault(record["threadID"], [])
        pending.append(record["recordIndex"])
    except Exception as error:
        _failure("source-registers", error)
    return False


def dod_return(frame, breakpoint_location, _internal_dict):
    try:
        _state["dodReturnCount"] += 1
        if _state["dodReturnCount"] > MAXIMUM_DOD_HIT_COUNT:
            raise RuntimeError("live DOD return hit bound exceeded")
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        address = breakpoint_location.GetAddress().GetLoadAddress(target)
        expected = _extension()["codeIdentity"]["returnAddress"]
        if frame.GetPC() != expected or address != expected:
            raise RuntimeError("live DOD return PC differs")
        thread_id = frame.GetThread().GetThreadID()
        pending = _state["pendingByThread"].get(thread_id, [])
        if not pending:
            raise RuntimeError("live DOD return has no pending entry")
        record_index = pending.pop()
        output_address = capture_base._register(frame, "x19")
        output = capture_base._memory_snapshot(
            process, output_address, 32, "live DOD return rectangle"
        )
        event = _next_event("dod-return")
        event["recordIndex"] = record_index
        record = _extension()["records"][record_index]
        record["returnEventSequence"] = event["sequence"]
        record["returnThreadID"] = thread_id
        record["outputAtReturn"] = output
        record["complete"] = True
    except Exception as error:
        _failure("return", error)
    return False


def finalize():
    live_base.finalize()
    extension = _extension()
    if extension is not None:
        extension["status"] = "finalized"
        extension["finalEventSequence"] = _state["eventSequence"]
        extension["finalDODHitCount"] = _state["dodHitCount"]
        extension["finalDODReturnCount"] = _state["dodReturnCount"]
        extension["finalRecordCount"] = len(extension["records"])
        extension["finalCompleteRecordCount"] = sum(
            record.get("complete") is True for record in extension["records"]
        )
        extension["finalPendingRecordCount"] = sum(
            len(records) for records in _state["pendingByThread"].values()
        )
        extension["finalFailureCount"] = len(extension["failures"])
    _write_trace()


def __lldb_init_module(debugger, internal_dict):
    live_base.__lldb_init_module(debugger, internal_dict)
    trace = crop_base._state.get("trace")
    if trace is None:
        return
    trace["liveDODSourceBoundsExtension"] = {
        "liveDODSourceBoundsExtensionSchemaVersion": EXTENSION_SCHEMA_VERSION,
        "classification": (
            "retrospective value-blind calibration inventory of every exact "
            "live GlassBackground DOD source-register site"
        ),
        "status": "initialized",
        "configuration": {
            "function": DOD_FUNCTION,
            "relativeToPrepareLayer": DOD_RELATIVE_TO_PREPARE_LAYER,
            "symbolByteCount": DOD_SYMBOL_BYTE_COUNT,
            "codeSHA256": DOD_CODE_SHA256,
            "sourceRegistersOffset": SOURCE_REGISTERS_OFFSET,
            "sourceRegistersInstructionRawLittleEndianHex": (
                SOURCE_REGISTERS_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
            ),
            "returnOffset": DOD_RETURN_OFFSET,
            "returnInstructionRawLittleEndianHex": (
                DOD_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
            ),
            "selectionRule": (
                "retain every exact code-hashed DOD+0x200 hit, pair its exact "
                "DOD+0x448 return by thread stack, and retain every crop marker "
                "callback in event order; inspect no rectangle value"
            ),
            "sourceValuesUsedForSelection": False,
            "cropOrProducerValuesUsedForSelection": False,
            "hardwareWatchpointsUsed": False,
            "instructionSteppingUsed": False,
            "maximumDODHitCount": MAXIMUM_DOD_HIT_COUNT,
        },
        "codeIdentity": {},
        "events": [],
        "records": [],
        "failures": [],
    }
    try:
        _install_proxy_callbacks()
        _write_trace()
    except Exception as error:
        _failure("initialization", error)
