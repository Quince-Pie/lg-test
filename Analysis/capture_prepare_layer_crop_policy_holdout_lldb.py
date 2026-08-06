"""Capture the floating producer input for an unseen crop-policy holdout.

This extension keeps the schema-7 marker and crop-union capture unchanged.  It
adds the already-opened ``prepare_layer+0x55c0`` store and correlates it to the
last destination-matched union by marker interval and ``x28`` identity only.
Neither crop bytes nor public values participate in capture-time selection.

LLDB imports this module with macOS system Python, so the source deliberately
avoids syntax newer than that runtime.
"""

import hashlib

import capture_prepare_layer_crop_union_operand_lldb as union_base


EXTENSION_SCHEMA_VERSION = 1
STORE_NAME = "nestedCropStore"
STORE_OFFSET = 0x55C0
STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = "802f803d"
ROLE_WORKING_CROP_OFFSET = 0x270
ROLE_FLOAT_INPUT_OFFSET = 0x290
LAYER_SHAPES_NESTED_OFFSET = 0xB0
WORKING_CROP_BYTE_COUNT = 0x10
FLOAT_INPUT_BYTE_COUNT = 0x20
MAXIMUM_STORE_HIT_COUNT = 16384
MAXIMUM_QUALIFIED_STORE_RECORD_COUNT = 4096
STORE_REGISTER_NAMES = ("x19", "x28", "x29", "sp", "pc", "cpsr")
STORE_SIMD_REGISTER_NAMES = ("v0",)


def _fresh_state():
    return {
        "storeBreakpoint": None,
        "storeHitCount": 0,
        "rejectedStoreCount": 0,
        "lastQualifiedMarkerStoreIndex": 0,
        "installed": False,
    }


_state = _fresh_state()


def _reset_state():
    _state.clear()
    _state.update(_fresh_state())


def _extension_trace():
    trace = union_base.crop_base._state.get("trace")
    if trace is None:
        return None
    return trace.get("cropPolicyHoldoutExtension")


def _new_extension_trace():
    return {
        "cropPolicyHoldoutExtensionSchemaVersion": EXTENSION_SCHEMA_VERSION,
        "classification": (
            "prospective unseen public-crop-policy holdout; retain the exact "
            "opened +0x55c0 producer store and correlate by event order and "
            "LayerShapes pointer identity without reading crop values"
        ),
        "status": "initialized",
        "configuration": {
            "storeName": STORE_NAME,
            "storeOffset": STORE_OFFSET,
            "storeInstructionRawLittleEndianHex": (
                STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
            ),
            "roleWorkingCropOffset": ROLE_WORKING_CROP_OFFSET,
            "roleFloatInputOffset": ROLE_FLOAT_INPUT_OFFSET,
            "layerShapesNestedOffset": LAYER_SHAPES_NESTED_OFFSET,
            "workingCropByteCount": WORKING_CROP_BYTE_COUNT,
            "floatInputByteCount": FLOAT_INPUT_BYTE_COUNT,
            "maximumStoreHitCount": MAXIMUM_STORE_HIT_COUNT,
            "maximumQualifiedStoreRecordCount": (MAXIMUM_QUALIFIED_STORE_RECORD_COUNT),
            "storeRegisterNames": list(STORE_REGISTER_NAMES),
            "storeSIMDRegisterNames": list(STORE_SIMD_REGISTER_NAMES),
            "storeSelectionRule": (
                "retain every prepare_layer+0x55c0 store with the exact direct "
                "normal transition caller chain and no intervention caller; "
                "do not inspect role, SIMD, destination, or crop bytes before "
                "retaining"
            ),
            "unionSelectionRule": (
                "within each qualified marker interval select the last union "
                "whose x0 destination equals marker x19+0x290"
            ),
            "storeCorrelationRule": (
                "within the same marker interval select the store whose x28 "
                "LayerShapes base equals the selected union x28 base"
            ),
            "hardwareWatchpointsUsed": False,
            "instructionSteppingUsed": False,
        },
        "storeRecords": [],
        "markerLinks": [],
        "rejectionGroups": {},
    }


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


def _snapshot(process, address, byte_count, label):
    return union_base.crop_base.capture_base._memory_snapshot(
        process, address, byte_count, label
    )


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


def _install_extension(frame):
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    start = union_base.crop_base._state["prepareLayer"]["symbolStart"]
    instruction = union_base.crop_base.capture_base._read_memory(
        process,
        start + STORE_OFFSET,
        4,
        "nested crop store instruction",
    )
    if instruction.hex() != STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX:
        raise RuntimeError("nested crop store instruction differs")
    breakpoint = _address_breakpoint(
        target,
        start + STORE_OFFSET,
        "nested_crop_store",
        "nested crop store",
    )
    _set_callback(
        union_base.crop_base._state["markerBreakpoint"],
        "crop_transfer_marker",
        "wrapped crop policy marker",
    )
    _state["storeBreakpoint"] = breakpoint
    _state["installed"] = True
    extension = _extension_trace()
    extension["status"] = "crop-policy-store-active"
    extension["prepareLayerSymbolStart"] = start
    extension["storeBreakpointID"] = breakpoint.GetID()
    extension["storeInstructionSHA256"] = hashlib.sha256(instruction).hexdigest()


def prepare_layer_entry(frame, breakpoint_location, internal_dict):
    """Install the store only after both inherited entry gates have run."""
    result = union_base.prepare_layer_entry(frame, breakpoint_location, internal_dict)
    try:
        if (
            union_base._state.get("installed")
            and union_base.crop_base._state.get("prepareLayer")
            and not _state["installed"]
        ):
            _install_extension(frame)
            union_base.crop_base._write_trace()
    except Exception as error:
        union_base.crop_base._failure("crop-policy-extension-entry", error)
        breakpoint = _state.get("storeBreakpoint")
        if breakpoint is not None:
            breakpoint.SetEnabled(False)
    return result


def nested_crop_store(frame, breakpoint_location, _internal_dict):
    """Retain a structurally qualified pre-store producer state."""
    try:
        _state["storeHitCount"] += 1
        if _state["storeHitCount"] > MAXIMUM_STORE_HIT_COUNT:
            raise RuntimeError("nested crop store hit bound exceeded")
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        expected = (
            union_base.crop_base._state["prepareLayer"]["symbolStart"] + STORE_OFFSET
        )
        location = breakpoint_location.GetAddress().GetLoadAddress(target)
        if frame.GetPC() != expected or location != expected:
            raise RuntimeError("nested crop store PC differs")
        thread = frame.GetThread()
        backtrace = union_base.crop_base.capture_base._backtrace(thread)
        functions = union_base.crop_base._backtrace_functions(backtrace)
        exact_frames = union_base.crop_base._exact_prepare_frames(thread)
        depth = len(exact_frames)
        if not union_base.crop_base._direct_timeline_caller(functions):
            _state["rejectedStoreCount"] += 1
            _record_rejection("caller-chain-excluded", depth)
            return False

        extension = _extension_trace()
        if len(extension["storeRecords"]) >= MAXIMUM_QUALIFIED_STORE_RECORD_COUNT:
            raise RuntimeError("qualified nested crop store bound exceeded")
        registers = union_base.crop_base.capture_base._register_snapshot(
            frame, STORE_REGISTER_NAMES
        )
        values = union_base.crop_base._register_values(registers)
        role_base = values["x19"]
        layer_shapes_base = values["x28"]
        record = {
            "recordIndex": len(extension["storeRecords"]),
            "storeHitIndex": _state["storeHitCount"],
            "threadID": thread.GetThreadID(),
            "prepareRecursionDepth": depth,
            "frame": union_base.crop_base.capture_base._frame_record(frame, target),
            "backtrace": backtrace,
            "registers": registers,
            "simdSourceRegisters": (
                union_base.crop_base.capture_base._register_snapshot(
                    frame, STORE_SIMD_REGISTER_NAMES
                )
            ),
            "frameIdentity": {
                "threadID": thread.GetThreadID(),
                "roleBase": role_base,
                "framePointer": values["x29"],
                "layerShapesBase": layer_shapes_base,
                "destination": layer_shapes_base + LAYER_SHAPES_NESTED_OFFSET,
            },
            "roleState": _snapshot(
                process,
                role_base,
                union_base.crop_base.ROLE_STATE_BYTE_COUNT,
                "nested crop store role state",
            ),
            "destinationBefore": _snapshot(
                process,
                layer_shapes_base + LAYER_SHAPES_NESTED_OFFSET,
                WORKING_CROP_BYTE_COUNT,
                "nested crop store destination before",
            ),
        }
        extension["storeRecords"].append(record)
        if len(extension["storeRecords"]) % 32 == 0:
            union_base.crop_base._write_trace()
    except Exception as error:
        union_base.crop_base._failure("nested-crop-store", error)
        breakpoint = _state.get("storeBreakpoint")
        if breakpoint is not None:
            breakpoint.SetEnabled(False)
    return False


def crop_transfer_marker(frame, breakpoint_location, internal_dict):
    """Run both inherited marker gates, then add identity-only store linkage."""
    before = len(union_base.crop_base._state["trace"]["qualifiedRecords"])
    result = union_base.crop_transfer_marker(frame, breakpoint_location, internal_dict)
    try:
        markers = union_base.crop_base._state["trace"]["qualifiedRecords"]
        if len(markers) == before + 1:
            marker = markers[-1]
            union_extension = union_base._extension_trace()
            union_link = union_extension["markerLinks"][-1]
            union_indices = union_link["matchingUnionRecordIndices"]
            selected_union_index = union_indices[-1] if union_indices else None
            selected_layer_shapes = None
            if selected_union_index is not None:
                selected_layer_shapes = union_extension["unionRecords"][
                    selected_union_index
                ]["frameIdentity"]["layerShapesBase"]

            extension = _extension_trace()
            start = _state["lastQualifiedMarkerStoreIndex"]
            end = len(extension["storeRecords"])
            matching = [
                record["recordIndex"]
                for record in extension["storeRecords"][start:end]
                if record["frameIdentity"]["layerShapesBase"] == selected_layer_shapes
            ]
            marker["cropPolicyStoreWindow"] = {
                "startRecordIndex": start,
                "endRecordIndexExclusive": end,
                "selectedUnionRecordIndex": selected_union_index,
                "selectedLayerShapesBase": selected_layer_shapes,
                "matchingStoreRecordIndices": matching,
            }
            extension["markerLinks"].append(
                {
                    "markerRecordIndex": marker["recordIndex"],
                    "markerCallbackSequence": marker["callbackSequence"],
                    "startStoreRecordIndex": start,
                    "endStoreRecordIndexExclusive": end,
                    "selectedUnionRecordIndex": selected_union_index,
                    "selectedLayerShapesBase": selected_layer_shapes,
                    "matchingStoreRecordIndices": matching,
                }
            )
            _state["lastQualifiedMarkerStoreIndex"] = end
            union_base.crop_base._write_trace()
        elif len(markers) != before:
            raise RuntimeError("wrapped crop policy marker count differs")
    except Exception as error:
        union_base.crop_base._failure("crop-policy-marker-link", error)
    return result


def finalize():
    """Seal store accounting, then run both inherited finalizers."""
    extension = _extension_trace()
    if extension is not None:
        records = extension["storeRecords"]
        extension["statusBeforeFinalization"] = extension["status"]
        extension["status"] = "finalized"
        extension["finalStoreHitCount"] = _state["storeHitCount"]
        extension["finalQualifiedStoreRecordCount"] = len(records)
        extension["finalRejectedStoreCount"] = _state["rejectedStoreCount"]
        extension["finalMarkerLinkCount"] = len(extension["markerLinks"])
        extension["finalLinkedStoreRecordCount"] = sum(
            len(link["matchingStoreRecordIndices"]) for link in extension["markerLinks"]
        )
        extension["finalTrailingStoreRecordCount"] = (
            len(records) - _state["lastQualifiedMarkerStoreIndex"]
        )
        extension["rejectionGroups"] = sorted(
            extension["rejectionGroups"].values(),
            key=lambda item: (
                item["reason"],
                item["prepareRecursionDepth"],
            ),
        )
    union_base.finalize()


def __lldb_init_module(debugger, internal_dict):
    """Initialize both inherited probes and replace only their two wrappers."""
    _reset_state()
    union_base.__lldb_init_module(debugger, internal_dict)
    trace = union_base.crop_base._state.get("trace")
    if trace is None:
        return
    trace["cropPolicyHoldoutExtension"] = _new_extension_trace()
    entry = union_base.crop_base._state.get("prepareEntryBreakpoint")
    if entry is None:
        union_base.crop_base._failure(
            "crop-policy-extension-initialization",
            "base prepare entry breakpoint is absent",
        )
        return
    try:
        _set_callback(entry, "prepare_layer_entry", "wrapped prepare entry")
        union_base.crop_base._write_trace()
    except Exception as error:
        union_base.crop_base._failure("crop-policy-extension-initialization", error)
