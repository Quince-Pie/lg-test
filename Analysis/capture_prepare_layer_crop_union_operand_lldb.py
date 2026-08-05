"""Capture the exact integer rectangle merged into each selected crop state.

The successful schema-7 crop-transfer probe remains immutable.  This module
wraps it and adds paired stops around the already-opened
``prepare_layer+0x85dc`` call to ``LayerShapes::union_bounds``.  Union records
are selected only by the normal caller chain; after the existing marker is
accepted they are correlated by the destination address
``marker_role + 0x290``.  No crop value participates in selection.

This module is imported by LLDB's macOS system Python, so it deliberately uses
syntax supported by that runtime rather than the repository's analysis
baseline.
"""

import hashlib

import capture_prepare_layer_crop_transfer_lldb as crop_base


EXTENSION_SCHEMA_VERSION = 1
UNION_CALL_NAME = "cropUnionBoundsCall"
UNION_CALL_OFFSET = 0x85DC
UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = "e1dbff97"
UNION_RETURN_NAME = "cropUnionBoundsReturn"
UNION_RETURN_OFFSET = 0x85E0
UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = "686241f9"
UNION_INPUT_ROLE_OFFSET = 0x620
UNION_DESTINATION_ROLE_OFFSET = 0x290
LAYER_SHAPES_WINDOW_OFFSET = 0xA0
LAYER_SHAPES_WINDOW_BYTE_COUNT = 0x30
UNION_INPUT_BYTE_COUNT = 0x20
UNION_TARGET_BYTE_COUNT = 0x20
MAXIMUM_UNION_CALL_HIT_COUNT = 16384
MAXIMUM_QUALIFIED_UNION_RECORD_COUNT = 4096
UNION_REGISTER_NAMES = (
    "x0",
    "x1",
    "x2",
    "x19",
    "x28",
    "x29",
    "sp",
    "pc",
    "cpsr",
)


def _fresh_state():
    return {
        "unionCallBreakpoint": None,
        "unionReturnBreakpoint": None,
        "unionCallHitCount": 0,
        "unionReturnHitCount": 0,
        "qualifiedUnionRecordCount": 0,
        "rejectedUnionCallCount": 0,
        "rejectedUnionReturnCount": 0,
        "eventSequence": 0,
        "pendingByThread": {},
        "lastQualifiedMarkerUnionIndex": 0,
        "installed": False,
    }


_state = _fresh_state()


def _reset_state():
    _state.clear()
    _state.update(_fresh_state())


def _extension_trace():
    trace = crop_base._state.get("trace")
    if trace is None:
        return None
    return trace.get("cropUnionOperandExtension")


def _new_extension_trace():
    return {
        "cropUnionOperandExtensionSchemaVersion": EXTENSION_SCHEMA_VERSION,
        "classification": (
            "prospective exact crop-union operand capture layered on the "
            "immutable schema-7 structural marker; call selection is caller-"
            "structural and marker correlation uses only the union destination "
            "address, never rectangle values"
        ),
        "status": "initialized",
        "configuration": {
            "unionCallName": UNION_CALL_NAME,
            "unionCallOffset": UNION_CALL_OFFSET,
            "unionCallInstructionRawLittleEndianHex": (
                UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
            ),
            "unionReturnName": UNION_RETURN_NAME,
            "unionReturnOffset": UNION_RETURN_OFFSET,
            "unionReturnInstructionRawLittleEndianHex": (
                UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
            ),
            "unionInputRoleOffset": UNION_INPUT_ROLE_OFFSET,
            "unionDestinationRoleOffset": UNION_DESTINATION_ROLE_OFFSET,
            "layerShapesWindowOffset": LAYER_SHAPES_WINDOW_OFFSET,
            "layerShapesWindowByteCount": LAYER_SHAPES_WINDOW_BYTE_COUNT,
            "unionInputByteCount": UNION_INPUT_BYTE_COUNT,
            "unionTargetByteCount": UNION_TARGET_BYTE_COUNT,
            "maximumUnionCallHitCount": MAXIMUM_UNION_CALL_HIT_COUNT,
            "maximumQualifiedUnionRecordCount": (
                MAXIMUM_QUALIFIED_UNION_RECORD_COUNT
            ),
            "unionRegisterNames": list(UNION_REGISTER_NAMES),
            "callSelectionRule": (
                "retain every prepare_layer+0x85dc call with the exact direct "
                "normal transition caller chain and no intervention caller; "
                "do not inspect rectangle bytes before retaining"
            ),
            "markerCorrelationRule": (
                "within each interval ending at a qualified schema-7 marker, "
                "select the complete union call whose x0 destination equals "
                "marker x19 + 0x290; do not inspect input or output values"
            ),
            "hardwareWatchpointsUsed": False,
            "instructionSteppingUsed": False,
        },
        "unionRecords": [],
        "markerLinks": [],
        "rejectionGroups": {},
    }


def _next_event_sequence():
    _state["eventSequence"] += 1
    return _state["eventSequence"]


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _address_breakpoint(target, address, callback, label):
    breakpoint = target.BreakpointCreateByAddress(address)
    if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
        raise RuntimeError(label + " breakpoint is unresolved")
    _set_callback(breakpoint, callback, label)
    return breakpoint


def _record_rejection(reason, depth):
    extension = _extension_trace()
    if extension is None:
        return
    key = str(reason) + ":" + str(depth)
    group = extension["rejectionGroups"].get(key)
    if group is None:
        group = {
            "reason": str(reason),
            "prepareRecursionDepth": int(depth),
            "hitCount": 0,
        }
        extension["rejectionGroups"][key] = group
    group["hitCount"] += 1


def _snapshot(process, address, byte_count, label):
    return crop_base.capture_base._memory_snapshot(
        process, address, byte_count, label
    )


def _registers(frame):
    return crop_base.capture_base._register_snapshot(
        frame, UNION_REGISTER_NAMES
    )


def _install_extension(frame):
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    start = crop_base._state["prepareLayer"]["symbolStart"]
    code = crop_base.capture_base._read_memory(
        process,
        start + UNION_CALL_OFFSET,
        UNION_RETURN_OFFSET - UNION_CALL_OFFSET + 4,
        "crop union call window",
    )
    call_bytes = code[:4]
    return_bytes = code[-4:]
    if call_bytes.hex() != UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX:
        raise RuntimeError("crop union call instruction differs")
    if return_bytes.hex() != UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX:
        raise RuntimeError("crop union return instruction differs")
    call = _address_breakpoint(
        target,
        start + UNION_CALL_OFFSET,
        "crop_union_call",
        "crop union call",
    )
    returned = _address_breakpoint(
        target,
        start + UNION_RETURN_OFFSET,
        "crop_union_return",
        "crop union return",
    )
    _set_callback(
        crop_base._state["markerBreakpoint"],
        "crop_transfer_marker",
        "wrapped crop transfer marker",
    )
    _state["unionCallBreakpoint"] = call
    _state["unionReturnBreakpoint"] = returned
    _state["installed"] = True
    extension = _extension_trace()
    extension["status"] = "crop-union-breakpoints-active"
    extension["prepareLayerSymbolStart"] = start
    extension["unionCallBreakpointID"] = call.GetID()
    extension["unionReturnBreakpointID"] = returned.GetID()
    extension["unionCallInstructionSHA256"] = hashlib.sha256(call_bytes).hexdigest()
    extension["unionReturnInstructionSHA256"] = hashlib.sha256(
        return_bytes
    ).hexdigest()


def prepare_layer_entry(frame, breakpoint_location, internal_dict):
    """Run the immutable entry gate, then install the two opened union stops."""
    result = crop_base.prepare_layer_entry(
        frame, breakpoint_location, internal_dict
    )
    try:
        if crop_base._state.get("prepareLayer") and not _state["installed"]:
            _install_extension(frame)
            crop_base._write_trace()
    except Exception as error:
        crop_base._failure("crop-union-extension-entry", error)
        for name in ("unionCallBreakpoint", "unionReturnBreakpoint"):
            breakpoint = _state.get(name)
            if breakpoint is not None:
                breakpoint.SetEnabled(False)
    return result


def crop_union_call(frame, breakpoint_location, _internal_dict):
    """Retain each direct-normal union call before it executes."""
    try:
        _state["unionCallHitCount"] += 1
        if _state["unionCallHitCount"] > MAXIMUM_UNION_CALL_HIT_COUNT:
            raise RuntimeError("crop union call hit bound exceeded")
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        expected = (
            crop_base._state["prepareLayer"]["symbolStart"] + UNION_CALL_OFFSET
        )
        location = breakpoint_location.GetAddress().GetLoadAddress(target)
        if frame.GetPC() != expected or location != expected:
            raise RuntimeError("crop union call PC differs")
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        if thread_id in _state["pendingByThread"]:
            raise RuntimeError("crop union call nested before prior return")
        backtrace = crop_base.capture_base._backtrace(thread)
        functions = crop_base._backtrace_functions(backtrace)
        exact_frames = crop_base._exact_prepare_frames(thread)
        depth = len(exact_frames)
        if not crop_base._direct_timeline_caller(functions):
            _state["rejectedUnionCallCount"] += 1
            _record_rejection("caller-chain-excluded", depth)
            _state["pendingByThread"][thread_id] = None
            return False
        extension = _extension_trace()
        if len(extension["unionRecords"]) >= MAXIMUM_QUALIFIED_UNION_RECORD_COUNT:
            raise RuntimeError("qualified crop union record bound exceeded")
        registers = _registers(frame)
        values = crop_base._register_values(registers)
        destination = values["x0"]
        input_address = values["x1"]
        role_base = values["x19"]
        layer_shapes = values["x28"]
        if input_address != role_base + UNION_INPUT_ROLE_OFFSET:
            raise RuntimeError("crop union input pointer differs")
        if values["x2"] & 0xFFFF_FFFF:
            raise RuntimeError("crop union propagation gate differs")
        sequence = _next_event_sequence()
        record_index = len(extension["unionRecords"])
        record = {
            "recordIndex": record_index,
            "callEventSequence": sequence,
            "callHitIndex": _state["unionCallHitCount"],
            "threadID": thread_id,
            "prepareRecursionDepth": depth,
            "frame": crop_base.capture_base._frame_record(frame, target),
            "backtrace": backtrace,
            "registers": registers,
            "frameIdentity": {
                "threadID": thread_id,
                "roleBase": role_base,
                "framePointer": values["x29"],
                "layerShapesBase": layer_shapes,
                "destination": destination,
                "input": input_address,
            },
            "roleState": _snapshot(
                process,
                role_base,
                crop_base.ROLE_STATE_BYTE_COUNT,
                "crop union role state",
            ),
            "layerShapesState": _snapshot(
                process,
                layer_shapes + LAYER_SHAPES_WINDOW_OFFSET,
                LAYER_SHAPES_WINDOW_BYTE_COUNT,
                "crop union LayerShapes state",
            ),
            "inputState": _snapshot(
                process,
                input_address,
                UNION_INPUT_BYTE_COUNT,
                "crop union input state",
            ),
            "targetBefore": _snapshot(
                process,
                destination,
                UNION_TARGET_BYTE_COUNT,
                "crop union target before",
            ),
            "complete": False,
        }
        extension["unionRecords"].append(record)
        _state["pendingByThread"][thread_id] = record_index
        _state["qualifiedUnionRecordCount"] += 1
        if _state["qualifiedUnionRecordCount"] % 32 == 0:
            crop_base._write_trace()
    except Exception as error:
        crop_base._failure("crop-union-call", error)
        if _state["unionCallBreakpoint"] is not None:
            _state["unionCallBreakpoint"].SetEnabled(False)
        if _state["unionReturnBreakpoint"] is not None:
            _state["unionReturnBreakpoint"].SetEnabled(False)
    return False


def crop_union_return(frame, breakpoint_location, _internal_dict):
    """Close the matching synchronous union call with its exact output bytes."""
    try:
        _state["unionReturnHitCount"] += 1
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        expected = (
            crop_base._state["prepareLayer"]["symbolStart"]
            + UNION_RETURN_OFFSET
        )
        location = breakpoint_location.GetAddress().GetLoadAddress(target)
        if frame.GetPC() != expected or location != expected:
            raise RuntimeError("crop union return PC differs")
        thread_id = frame.GetThread().GetThreadID()
        if thread_id not in _state["pendingByThread"]:
            raise RuntimeError("crop union return lacks a pending call")
        record_index = _state["pendingByThread"].pop(thread_id)
        if record_index is None:
            _state["rejectedUnionReturnCount"] += 1
            return False
        extension = _extension_trace()
        record = extension["unionRecords"][record_index]
        destination = record["frameIdentity"]["destination"]
        record["returnEventSequence"] = _next_event_sequence()
        record["returnHitIndex"] = _state["unionReturnHitCount"]
        record["returnPC"] = frame.GetPC()
        record["targetAfter"] = _snapshot(
            process,
            destination,
            UNION_TARGET_BYTE_COUNT,
            "crop union target after",
        )
        record["complete"] = True
    except Exception as error:
        crop_base._failure("crop-union-return", error)
        if _state["unionCallBreakpoint"] is not None:
            _state["unionCallBreakpoint"].SetEnabled(False)
        if _state["unionReturnBreakpoint"] is not None:
            _state["unionReturnBreakpoint"].SetEnabled(False)
    return False


def crop_transfer_marker(frame, breakpoint_location, internal_dict):
    """Run the immutable marker selector and attach destination-only links."""
    before = len(crop_base._state["trace"]["qualifiedRecords"])
    result = crop_base.crop_transfer_marker(
        frame, breakpoint_location, internal_dict
    )
    try:
        records = crop_base._state["trace"]["qualifiedRecords"]
        if len(records) == before + 1:
            marker = records[-1]
            extension = _extension_trace()
            start = _state["lastQualifiedMarkerUnionIndex"]
            end = len(extension["unionRecords"])
            destination = (
                marker["frameIdentity"]["roleBase"]
                + UNION_DESTINATION_ROLE_OFFSET
            )
            matching = [
                record["recordIndex"]
                for record in extension["unionRecords"][start:end]
                if record.get("complete") is True
                and record["frameIdentity"]["destination"] == destination
            ]
            marker["cropUnionOperandWindow"] = {
                "startRecordIndex": start,
                "endRecordIndexExclusive": end,
                "destinationAddress": destination,
                "matchingRecordIndices": matching,
            }
            extension["markerLinks"].append(
                {
                    "markerRecordIndex": marker["recordIndex"],
                    "markerCallbackSequence": marker["callbackSequence"],
                    "startUnionRecordIndex": start,
                    "endUnionRecordIndexExclusive": end,
                    "destinationAddress": destination,
                    "matchingUnionRecordIndices": matching,
                }
            )
            _state["lastQualifiedMarkerUnionIndex"] = end
            crop_base._write_trace()
        elif len(records) != before:
            raise RuntimeError("wrapped crop marker record count differs")
    except Exception as error:
        crop_base._failure("crop-union-marker-link", error)
    return result


def finalize():
    """Seal extension accounting, then run the immutable base finalizer."""
    extension = _extension_trace()
    if extension is not None:
        if _state["pendingByThread"]:
            crop_base._failure(
                "crop-union-finalize",
                "crop union calls remain pending at finalization",
            )
        records = extension["unionRecords"]
        extension["statusBeforeFinalization"] = extension["status"]
        extension["status"] = "finalized"
        extension["finalEventSequence"] = _state["eventSequence"]
        extension["finalUnionCallHitCount"] = _state["unionCallHitCount"]
        extension["finalUnionReturnHitCount"] = _state["unionReturnHitCount"]
        extension["finalQualifiedUnionRecordCount"] = len(records)
        extension["finalCompleteUnionRecordCount"] = sum(
            record.get("complete") is True for record in records
        )
        extension["finalRejectedUnionCallCount"] = _state[
            "rejectedUnionCallCount"
        ]
        extension["finalRejectedUnionReturnCount"] = _state[
            "rejectedUnionReturnCount"
        ]
        extension["finalMarkerLinkCount"] = len(extension["markerLinks"])
        extension["finalLinkedUnionRecordCount"] = sum(
            len(link["matchingUnionRecordIndices"])
            for link in extension["markerLinks"]
        )
        extension["finalTrailingUnionRecordCount"] = (
            len(records) - _state["lastQualifiedMarkerUnionIndex"]
        )
        extension["rejectionGroups"] = sorted(
            extension["rejectionGroups"].values(),
            key=lambda item: (
                item["reason"],
                item["prepareRecursionDepth"],
            ),
        )
    crop_base.finalize()


def __lldb_init_module(debugger, internal_dict):
    """Initialize the immutable capture, then replace only its entry callback."""
    _reset_state()
    crop_base.__lldb_init_module(debugger, internal_dict)
    trace = crop_base._state.get("trace")
    if trace is None:
        return
    trace["cropUnionOperandExtension"] = _new_extension_trace()
    entry = crop_base._state.get("prepareEntryBreakpoint")
    if entry is None:
        crop_base._failure(
            "crop-union-extension-initialization",
            "base prepare entry breakpoint is absent",
        )
        return
    try:
        _set_callback(entry, "prepare_layer_entry", "wrapped prepare entry")
        crop_base._write_trace()
    except Exception as error:
        crop_base._failure("crop-union-extension-initialization", error)
