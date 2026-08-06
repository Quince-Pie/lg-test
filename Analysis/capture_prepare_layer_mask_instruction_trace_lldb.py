"""Trace one preregistered ``prepare_layer_mask`` invocation instruction by instruction.

Run 31059860458 retained the true floating crop producer two structural store
records before the downstream pointer-correlated mirror.  Older instruction
traces show that ``prepare_layer+0xd90`` calls ``prepare_layer_mask`` with that
producer destination at caller role ``+0x290``, but deliberately step over the
helper as opaque.  This extension selects one call by geometry-independent
event structure only: direct normal caller, second qualified marker interval,
eighth qualified helper call, and the statically opened x1/x3 role offsets.
No rectangle or output byte participates in selection.

LLDB imports this module with macOS system Python, so it avoids syntax newer
than that runtime.
"""

import hashlib
import os

import lldb

import capture_prepare_layer_crop_policy_holdout_callback_retry_lldb as holdout_retry


holdout_base = holdout_retry.holdout_base
union_base = holdout_base.union_base
crop_base = union_base.crop_base
capture_base = crop_base.capture_base

EXTENSION_SCHEMA_VERSION = 1
HELPER_FUNCTION = (
    "CA::Render::Updater::prepare_layer_mask("
    "CA::Render::Updater::GlobalState&, "
    "CA::Render::Updater::LocalState&, "
    "CA::Render::Updater::LayerShapes const&, "
    "CA::Render::Updater::LayerShapes&)"
)
HELPER_RELATIVE_TO_PREPARE_LAYER = -1209388
HELPER_SYMBOL_BYTE_COUNT = 2176
CALL_OFFSET = 0xD90
CALL_RETURN_OFFSET = 0xD94
CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = "915ffb97"
CALLER_LOCAL_STATE_OFFSET = 0x420
CALLER_OUTPUT_OFFSET = 0x290
TARGET_MARKER_INTERVAL = 2
TARGET_QUALIFIED_ORDINAL = 8
EXPECTED_GEOMETRY = "circle-1025-center"
MAXIMUM_HELPER_ENTRY_HIT_COUNT = 16384
MAXIMUM_QUALIFIED_HELPER_ENTRY_COUNT = 4096
MAXIMUM_HELPER_INSTRUCTION_COUNT = 8192
MAXIMUM_OPAQUE_CALLEE_COUNT = 2048
MAXIMUM_UNEXPECTED_TERMINAL_STOP_COUNT = 8
STACK_BYTE_COUNT = 0x100
ARGUMENT_BYTE_COUNT = 0x400
CALLER_ROLE_BYTE_COUNT = 0x800
OUTPUT_BYTE_COUNT = 0x200
ENTRY_REGISTER_NAMES = (
    "x0",
    "x1",
    "x2",
    "x3",
    "x19",
    "x29",
    "sp",
    "pc",
    "cpsr",
)


def _fresh_state():
    return {
        "debugger": None,
        "helperBreakpoint": None,
        "helperEntryHitCount": 0,
        "qualifiedHelperEntryCount": 0,
        "rejectedHelperEntryCount": 0,
        "qualifiedOrdinalWithinInterval": 0,
        "lastQualifiedMarkerHelperIndex": 0,
        "installed": False,
        "selected": None,
        "manualTraceStarted": False,
        "manualTraceFinished": False,
        "breakpointStates": [],
    }


_state = _fresh_state()


def _reset_state():
    _state.clear()
    _state.update(_fresh_state())


def _extension_trace():
    trace = crop_base._state.get("trace")
    if trace is None:
        return None
    return trace.get("prepareLayerMaskInstructionExtension")


def _new_extension_trace():
    return {
        "prepareLayerMaskInstructionExtensionSchemaVersion": (
            EXTENSION_SCHEMA_VERSION
        ),
        "classification": (
            "prospective structurally selected prepare_layer_mask helper-body "
            "calibration; code identity and every executed state are retained, "
            "while exact arithmetic replay, repeat transfer, production, and "
            "parity authority remain sealed"
        ),
        "status": "initialized",
        "configuration": {
            "helperFunction": HELPER_FUNCTION,
            "helperRelativeToPrepareLayer": HELPER_RELATIVE_TO_PREPARE_LAYER,
            "helperSymbolByteCount": HELPER_SYMBOL_BYTE_COUNT,
            "helperExpectedSHA256": None,
            "callOffset": CALL_OFFSET,
            "callReturnOffset": CALL_RETURN_OFFSET,
            "callInstructionRawLittleEndianHex": (
                CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
            ),
            "callerLocalStateOffset": CALLER_LOCAL_STATE_OFFSET,
            "callerOutputOffset": CALLER_OUTPUT_OFFSET,
            "targetMarkerInterval": TARGET_MARKER_INTERVAL,
            "targetQualifiedOrdinal": TARGET_QUALIFIED_ORDINAL,
            "expectedGeometry": EXPECTED_GEOMETRY,
            "maximumHelperEntryHitCount": MAXIMUM_HELPER_ENTRY_HIT_COUNT,
            "maximumQualifiedHelperEntryCount": (
                MAXIMUM_QUALIFIED_HELPER_ENTRY_COUNT
            ),
            "maximumHelperInstructionCount": MAXIMUM_HELPER_INSTRUCTION_COUNT,
            "maximumOpaqueCalleeCount": MAXIMUM_OPAQUE_CALLEE_COUNT,
            "maximumUnexpectedTerminalStopCount": (
                MAXIMUM_UNEXPECTED_TERMINAL_STOP_COUNT
            ),
            "stackByteCount": STACK_BYTE_COUNT,
            "argumentByteCount": ARGUMENT_BYTE_COUNT,
            "callerRoleByteCount": CALLER_ROLE_BYTE_COUNT,
            "outputByteCount": OUTPUT_BYTE_COUNT,
            "entryRegisterNames": list(ENTRY_REGISTER_NAMES),
            "entrySelectionRule": (
                "among exact direct-normal transition callers, select marker "
                "interval 2 ordinal 8, then require x1=x19+0x420 and "
                "x3=x19+0x290; do not inspect any rectangle or output bytes"
            ),
            "steppingRule": (
                "set LLDB synchronous, disable every software breakpoint, "
                "retain complete scalar/SIMD registers, stack, and output "
                "bytes before and after every helper instruction; step into "
                "the helper and step out of non-helper callees as explicit "
                "input/output boundaries"
            ),
            "correlationRule": (
                "after normal capture resumes, require selected x3 to equal "
                "the marker-2 structural predecessor store role+0x290 and "
                "require helper return bytes to equal that later producer"
            ),
            "hardwareWatchpointsUsed": False,
            "cropValuesUsedForSelection": False,
        },
        "helper": {},
        "helperEntryRecords": [],
        "markerLinks": [],
        "selectedInvocation": {},
        "executionEvents": [],
        "instructionStates": [],
        "opaqueCalleeBoundaries": [],
        "failures": [],
        "rejectionGroups": {},
        "terminalProcess": {},
    }


def _write_trace():
    crop_base._write_trace()


def _failure(stage, error):
    extension = _extension_trace()
    if extension is not None:
        extension["failures"].append(
            {"stage": str(stage), "message": str(error)}
        )
    crop_base._failure("prepare-layer-mask-" + str(stage), error)


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
    return capture_base._memory_snapshot(process, address, byte_count, label)


def _register_values(records):
    return {record["name"]: record["unsignedValue"] for record in records}


def _full_register_values(snapshot):
    return _register_values(snapshot["general"])


def _record_rejection(reason, depth):
    extension = _extension_trace()
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


def _module_record(module, target):
    record = capture_base._module_record(module, target)
    if record.get("valid") is True:
        uuid = module.GetUUIDString()
        record["uuid"] = uuid if uuid else None
    return record


def _instruction_record(frame, helper):
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    pc = frame.GetPC()
    raw = capture_base._read_memory(
        process, pc, 4, "prepare_layer_mask instruction"
    )
    mnemonic = ""
    operands = ""
    comment = ""
    try:
        instructions = target.ReadInstructions(frame.GetPCAddress(), 1)
        if instructions.GetSize() == 1:
            instruction = instructions.GetInstructionAtIndex(0)
            mnemonic = instruction.GetMnemonic(target) or ""
            operands = instruction.GetOperands(target) or ""
            comment = instruction.GetComment(target) or ""
    except Exception:
        pass
    lowered = mnemonic.lower()
    return {
        "pc": pc,
        "helperOffset": pc - helper["symbolStart"],
        "rawLittleEndianHex": raw.hex(),
        "mnemonic": mnemonic,
        "operands": operands,
        "comment": comment,
        "potentialCall": lowered.startswith("bl"),
        "potentialReturn": lowered.startswith("ret"),
    }


def _changed_qword_offsets(before, after):
    if len(before) != len(after) or len(before) % 8:
        raise RuntimeError("output comparison byte count differs")
    return [
        offset
        for offset in range(0, len(before), 8)
        if before[offset : offset + 8] != after[offset : offset + 8]
    ]


def _selected_thread(process):
    selected = _state["selected"]
    thread = process.GetThreadByID(selected["threadID"])
    if not thread.IsValid():
        raise RuntimeError("selected helper thread is unavailable")
    return thread


def _require_stopped(process, label):
    if process.GetState() != lldb.eStateStopped:
        raise RuntimeError(label + " did not stop the process")


def _install_callback_proxies():
    entry = crop_base._state.get("prepareEntryBreakpoint")
    marker = crop_base._state.get("markerBreakpoint")
    union_call = union_base._state.get("unionCallBreakpoint")
    union_return = union_base._state.get("unionReturnBreakpoint")
    store = holdout_base._state.get("storeBreakpoint")
    helper = _state.get("helperBreakpoint")
    callbacks = (
        (entry, "prepare_layer_entry", "prepare entry"),
        (marker, "crop_transfer_marker", "crop transfer marker"),
        (union_call, "crop_union_call", "crop union call"),
        (union_return, "crop_union_return", "crop union return"),
        (store, "nested_crop_store", "nested crop store"),
        (helper, "prepare_layer_mask_entry", "prepare_layer_mask entry"),
    )
    for breakpoint, callback, label in callbacks:
        if breakpoint is not None:
            _set_callback(breakpoint, callback, label)


def _install_extension(frame):
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    prepare_start = crop_base._state["prepareLayer"]["symbolStart"]
    if os.environ.get("LG_GLASS_GEOMETRY") != EXPECTED_GEOMETRY:
        raise RuntimeError("prepare_layer_mask geometry differs")
    call = capture_base._read_memory(
        process,
        prepare_start + CALL_OFFSET,
        4,
        "prepare_layer_mask call instruction",
    )
    if call.hex() != CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX:
        raise RuntimeError("prepare_layer_mask call instruction differs")
    helper_start = prepare_start + HELPER_RELATIVE_TO_PREPARE_LAYER
    resolved = target.ResolveLoadAddress(helper_start)
    symbol = resolved.GetSymbol()
    if not symbol.IsValid():
        raise RuntimeError("prepare_layer_mask symbol is invalid")
    symbol_start = symbol.GetStartAddress().GetLoadAddress(target)
    symbol_end = symbol.GetEndAddress().GetLoadAddress(target)
    function_name = resolved.GetFunction().GetName()
    symbol_name = symbol.GetName()
    if (
        HELPER_FUNCTION not in (function_name, symbol_name)
        or symbol_start != helper_start
        or symbol_end - symbol_start != HELPER_SYMBOL_BYTE_COUNT
    ):
        raise RuntimeError("prepare_layer_mask symbol identity differs")
    code = capture_base._read_memory(
        process,
        helper_start,
        HELPER_SYMBOL_BYTE_COUNT,
        "prepare_layer_mask complete code",
    )
    breakpoint = _address_breakpoint(
        target,
        helper_start,
        "prepare_layer_mask_entry",
        "prepare_layer_mask entry",
    )
    _state["helperBreakpoint"] = breakpoint
    _state["installed"] = True
    extension = _extension_trace()
    extension["status"] = "helper-entry-breakpoint-active"
    extension["helper"] = {
        "function": HELPER_FUNCTION,
        "relativeToPrepareLayer": HELPER_RELATIVE_TO_PREPARE_LAYER,
        "symbolStart": symbol_start,
        "symbolEnd": symbol_end,
        "symbolByteCount": len(code),
        "expectedSHA256": None,
        "observedSHA256": hashlib.sha256(code).hexdigest(),
        "hex": code.hex(),
        "module": _module_record(resolved.GetModule(), target),
        "entryBreakpointID": breakpoint.GetID(),
        "callPC": prepare_start + CALL_OFFSET,
        "callReturnPC": prepare_start + CALL_RETURN_OFFSET,
        "callInstructionSHA256": hashlib.sha256(call).hexdigest(),
    }
    _install_callback_proxies()


def prepare_layer_entry(frame, breakpoint_location, internal_dict):
    result = holdout_retry.prepare_layer_entry(
        frame, breakpoint_location, internal_dict
    )
    try:
        if (
            holdout_base._state.get("installed")
            and union_base._state.get("installed")
            and crop_base._state.get("prepareLayer")
            and not _state["installed"]
        ):
            _install_extension(frame)
        _install_callback_proxies()
        _write_trace()
    except Exception as error:
        _failure("entry", error)
        breakpoint = _state.get("helperBreakpoint")
        if breakpoint is not None:
            breakpoint.SetEnabled(False)
    return result


def crop_union_call(frame, breakpoint_location, internal_dict):
    return holdout_retry.crop_union_call(
        frame, breakpoint_location, internal_dict
    )


def crop_union_return(frame, breakpoint_location, internal_dict):
    return holdout_retry.crop_union_return(
        frame, breakpoint_location, internal_dict
    )


def nested_crop_store(frame, breakpoint_location, internal_dict):
    return holdout_retry.nested_crop_store(
        frame, breakpoint_location, internal_dict
    )


def crop_transfer_marker(frame, breakpoint_location, internal_dict):
    before = len(crop_base._state["trace"]["qualifiedRecords"])
    result = holdout_retry.crop_transfer_marker(
        frame, breakpoint_location, internal_dict
    )
    try:
        markers = crop_base._state["trace"]["qualifiedRecords"]
        if len(markers) == before + 1:
            extension = _extension_trace()
            start = _state["lastQualifiedMarkerHelperIndex"]
            end = len(extension["helperEntryRecords"])
            marker_index = len(markers)
            selected_indices = [
                record["recordIndex"]
                for record in extension["helperEntryRecords"][start:end]
                if record.get("selectedByFrozenRule") is True
            ]
            extension["markerLinks"].append(
                {
                    "markerRecordIndex": markers[-1]["recordIndex"],
                    "markerCallbackSequence": markers[-1]["callbackSequence"],
                    "markerIntervalIndex": marker_index,
                    "startHelperRecordIndex": start,
                    "endHelperRecordIndexExclusive": end,
                    "selectedHelperRecordIndices": selected_indices,
                    "helperCollectionStoppedAtTarget": (
                        _state["selected"] is not None
                    ),
                }
            )
            _state["lastQualifiedMarkerHelperIndex"] = end
            _state["qualifiedOrdinalWithinInterval"] = 0
            _write_trace()
        elif len(markers) != before:
            raise RuntimeError("wrapped helper marker count differs")
    except Exception as error:
        _failure("marker-link", error)
    return result


def prepare_layer_mask_entry(frame, breakpoint_location, _internal_dict):
    """Retain helper entries and stop only at the frozen structural target."""
    try:
        _state["helperEntryHitCount"] += 1
        if _state["helperEntryHitCount"] > MAXIMUM_HELPER_ENTRY_HIT_COUNT:
            raise RuntimeError("prepare_layer_mask entry hit bound exceeded")
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        helper = _extension_trace()["helper"]
        expected = helper["symbolStart"]
        location = breakpoint_location.GetAddress().GetLoadAddress(target)
        if (
            frame.GetPC() != expected
            or location != expected
            or frame.GetFunctionName() != HELPER_FUNCTION
        ):
            raise RuntimeError("prepare_layer_mask entry PC differs")
        thread = frame.GetThread()
        backtrace = capture_base._backtrace(thread)
        functions = crop_base._backtrace_functions(backtrace)
        exact_frames = crop_base._exact_prepare_frames(thread)
        depth = len(exact_frames)
        if not crop_base._direct_timeline_caller(functions):
            _state["rejectedHelperEntryCount"] += 1
            _record_rejection("caller-chain-excluded", depth)
            return False
        parent = thread.GetFrameAtIndex(1)
        if (
            not parent.IsValid()
            or parent.GetFunctionName() != crop_base.PREPARE_LAYER_FUNCTION
            or parent.GetPC()
            != crop_base._state["prepareLayer"]["symbolStart"] + CALL_RETURN_OFFSET
        ):
            raise RuntimeError("prepare_layer_mask direct caller differs")

        extension = _extension_trace()
        if len(extension["helperEntryRecords"]) >= (
            MAXIMUM_QUALIFIED_HELPER_ENTRY_COUNT
        ):
            raise RuntimeError("qualified prepare_layer_mask entry bound exceeded")
        _state["qualifiedHelperEntryCount"] += 1
        _state["qualifiedOrdinalWithinInterval"] += 1
        marker_interval = (
            len(crop_base._state["trace"]["qualifiedRecords"]) + 1
        )
        ordinal = _state["qualifiedOrdinalWithinInterval"]
        registers = capture_base._register_snapshot(frame, ENTRY_REGISTER_NAMES)
        values = _register_values(registers)
        role_offsets_match = (
            values["x1"] == values["x19"] + CALLER_LOCAL_STATE_OFFSET
            and values["x3"] == values["x19"] + CALLER_OUTPUT_OFFSET
        )
        selected_by_ordinal = (
            marker_interval == TARGET_MARKER_INTERVAL
            and ordinal == TARGET_QUALIFIED_ORDINAL
        )
        record = {
            "recordIndex": len(extension["helperEntryRecords"]),
            "entryHitIndex": _state["helperEntryHitCount"],
            "qualifiedEntryIndex": _state["qualifiedHelperEntryCount"],
            "markerIntervalIndex": marker_interval,
            "qualifiedOrdinalWithinMarkerInterval": ordinal,
            "threadID": thread.GetThreadID(),
            "prepareRecursionDepth": depth,
            "frame": capture_base._frame_record(frame, target),
            "callerFrame": capture_base._frame_record(parent, target),
            "backtrace": backtrace,
            "registers": registers,
            "frameIdentity": {
                "threadID": thread.GetThreadID(),
                "callerRoleBase": values["x19"],
                "callerFramePointer": values["x29"],
                "globalStateX0": values["x0"],
                "localStateX1": values["x1"],
                "sourceLayerShapesX2": values["x2"],
                "outputLayerShapesX3": values["x3"],
            },
            "roleOffsetsMatch": role_offsets_match,
            "selectedByFrozenOrdinal": selected_by_ordinal,
            "selectedByFrozenRule": selected_by_ordinal and role_offsets_match,
        }
        extension["helperEntryRecords"].append(record)
        if selected_by_ordinal:
            if not role_offsets_match:
                raise RuntimeError("selected helper role offsets differ")
            if _state["selected"] is not None:
                raise RuntimeError("prepare_layer_mask target is not unique")
            full_registers = capture_base._full_register_snapshot(frame)
            full_values = _full_register_values(full_registers)
            if any(full_values[name] != values[name] for name in ENTRY_REGISTER_NAMES):
                raise RuntimeError("selected helper register snapshots differ")
            selected = {
                "recordIndex": record["recordIndex"],
                "threadID": thread.GetThreadID(),
                "callerRoleBase": values["x19"],
                "outputAddress": values["x3"],
                "entrySP": full_values["sp"],
            }
            _state["selected"] = selected
            extension["selectedInvocation"] = {
                **selected,
                "entryPC": frame.GetPC(),
                "entryRegisters": full_registers,
                "entryStack": _snapshot(
                    process,
                    full_values["sp"],
                    STACK_BYTE_COUNT,
                    "prepare_layer_mask entry stack",
                ),
                "globalStateAtEntry": _snapshot(
                    process,
                    values["x0"],
                    ARGUMENT_BYTE_COUNT,
                    "prepare_layer_mask global state",
                ),
                "localStateAtEntry": _snapshot(
                    process,
                    values["x1"],
                    ARGUMENT_BYTE_COUNT,
                    "prepare_layer_mask local state",
                ),
                "sourceLayerShapesAtEntry": _snapshot(
                    process,
                    values["x2"],
                    ARGUMENT_BYTE_COUNT,
                    "prepare_layer_mask source LayerShapes",
                ),
                "outputLayerShapesAtEntry": _snapshot(
                    process,
                    values["x3"],
                    OUTPUT_BYTE_COUNT,
                    "prepare_layer_mask output at entry",
                ),
                "callerRoleAtEntry": _snapshot(
                    process,
                    values["x19"],
                    CALLER_ROLE_BYTE_COUNT,
                    "prepare_layer_mask caller role at entry",
                ),
            }
            extension["status"] = "selected-helper-entry-stopped"
            _write_trace()
            return True
        if len(extension["helperEntryRecords"]) % 16 == 0:
            _write_trace()
    except Exception as error:
        _failure("helper-entry", error)
        breakpoint = _state.get("helperBreakpoint")
        if breakpoint is not None:
            breakpoint.SetEnabled(False)
    return False


def _disable_breakpoints(target):
    if target.GetNumWatchpoints() != 0:
        raise RuntimeError("prepare_layer_mask target contains a watchpoint")
    states = []
    for index in range(target.GetNumBreakpoints()):
        breakpoint = target.GetBreakpointAtIndex(index)
        states.append(
            {
                "breakpointID": breakpoint.GetID(),
                "enabledBefore": breakpoint.IsEnabled(),
                "locationCount": breakpoint.GetNumLocations(),
            }
        )
    if not states or not target.DisableAllBreakpoints():
        raise RuntimeError("prepare_layer_mask breakpoint disablement failed")
    for index in range(target.GetNumBreakpoints()):
        if target.GetBreakpointAtIndex(index).IsEnabled():
            raise RuntimeError("prepare_layer_mask breakpoint remained enabled")
    _state["breakpointStates"] = states
    _extension_trace()["breakpointDisablement"] = {
        "watchpointCount": target.GetNumWatchpoints(),
        "breakpoints": states,
    }


def _restore_breakpoints(target):
    helper_id = _state["helperBreakpoint"].GetID()
    expected = {
        item["breakpointID"]: item["enabledBefore"]
        for item in _state["breakpointStates"]
    }
    restored = []
    for index in range(target.GetNumBreakpoints()):
        breakpoint = target.GetBreakpointAtIndex(index)
        identifier = breakpoint.GetID()
        enabled = bool(expected.get(identifier, False) and identifier != helper_id)
        breakpoint.SetEnabled(enabled)
        restored.append(
            {
                "breakpointID": identifier,
                "enabledAfterRestore": breakpoint.IsEnabled(),
                "helperEntryDeliberatelyDisabled": identifier == helper_id,
            }
        )
    if any(
        item["enabledAfterRestore"]
        != bool(
            expected.get(item["breakpointID"], False)
            and not item["helperEntryDeliberatelyDisabled"]
        )
        for item in restored
    ):
        raise RuntimeError("prepare_layer_mask breakpoint restoration differs")
    _extension_trace()["breakpointRestoration"] = {
        "helperEntryBreakpointID": helper_id,
        "breakpoints": restored,
    }


def _trace_helper_instruction(thread, frame, helper):
    process = thread.GetProcess()
    extension = _extension_trace()
    states = extension["instructionStates"]
    if len(states) >= MAXIMUM_HELPER_INSTRUCTION_COUNT:
        raise RuntimeError("prepare_layer_mask instruction bound exceeded")
    instruction = _instruction_record(frame, helper)
    registers = capture_base._full_register_snapshot(frame)
    values = _full_register_values(registers)
    output_address = _state["selected"]["outputAddress"]
    output_before = capture_base._read_memory(
        process,
        output_address,
        OUTPUT_BYTE_COUNT,
        "prepare_layer_mask output before instruction",
    )
    state = {
        "stateIndex": len(states),
        "instruction": instruction,
        "registersBefore": registers,
        "stackBefore": _snapshot(
            process,
            values["sp"],
            STACK_BYTE_COUNT,
            "prepare_layer_mask instruction stack",
        ),
        "outputBefore": {
            "address": output_address,
            "byteCount": len(output_before),
            "sha256": hashlib.sha256(output_before).hexdigest(),
            "hex": output_before.hex(),
        },
    }
    error = lldb.SBError()
    thread.StepInstruction(False, error)
    if not error.Success():
        raise RuntimeError(error.GetCString() or "helper instruction step failed")
    _require_stopped(process, "helper instruction")
    current = _selected_thread(process)
    result_frame = current.GetFrameAtIndex(0)
    output_after = capture_base._read_memory(
        process,
        output_address,
        OUTPUT_BYTE_COUNT,
        "prepare_layer_mask output after instruction",
    )
    state.update(
        {
            "resultPC": result_frame.GetPC(),
            "resultFunction": result_frame.GetFunctionName(),
            "outputAfter": {
                "address": output_address,
                "byteCount": len(output_after),
                "sha256": hashlib.sha256(output_after).hexdigest(),
                "hex": output_after.hex(),
            },
            "outputChanged": output_before != output_after,
            "changedOutputQwordOffsets": _changed_qword_offsets(
                output_before, output_after
            ),
        }
    )
    states.append(state)
    extension["executionEvents"].append(
        {"kind": "helper-instruction", "recordIndex": state["stateIndex"]}
    )
    if state["outputChanged"] or len(states) % 32 == 0:
        _write_trace()
    return current, result_frame


def _trace_opaque_callee(thread, frame):
    process = thread.GetProcess()
    extension = _extension_trace()
    boundaries = extension["opaqueCalleeBoundaries"]
    if len(boundaries) >= MAXIMUM_OPAQUE_CALLEE_COUNT:
        raise RuntimeError("prepare_layer_mask opaque callee bound exceeded")
    output_address = _state["selected"]["outputAddress"]
    before_registers = capture_base._full_register_snapshot(frame)
    before_values = _full_register_values(before_registers)
    output_before = capture_base._read_memory(
        process,
        output_address,
        OUTPUT_BYTE_COUNT,
        "prepare_layer_mask opaque output before",
    )
    boundary = {
        "boundaryIndex": len(boundaries),
        "entryFrame": capture_base._frame_record(frame, process.GetTarget()),
        "registersAtEntry": before_registers,
        "stackAtEntry": _snapshot(
            process,
            before_values["sp"],
            STACK_BYTE_COUNT,
            "prepare_layer_mask opaque stack at entry",
        ),
        "outputBefore": {
            "address": output_address,
            "byteCount": len(output_before),
            "sha256": hashlib.sha256(output_before).hexdigest(),
            "hex": output_before.hex(),
        },
    }
    error = lldb.SBError()
    thread.StepOut(error)
    if not error.Success():
        raise RuntimeError(error.GetCString() or "helper opaque callee step-out failed")
    _require_stopped(process, "helper opaque callee")
    current = _selected_thread(process)
    result_frame = current.GetFrameAtIndex(0)
    after_registers = capture_base._full_register_snapshot(result_frame)
    after_values = _full_register_values(after_registers)
    output_after = capture_base._read_memory(
        process,
        output_address,
        OUTPUT_BYTE_COUNT,
        "prepare_layer_mask opaque output after",
    )
    boundary.update(
        {
            "returnFrame": capture_base._frame_record(
                result_frame, process.GetTarget()
            ),
            "registersAtReturn": after_registers,
            "stackAtReturn": _snapshot(
                process,
                after_values["sp"],
                STACK_BYTE_COUNT,
                "prepare_layer_mask opaque stack at return",
            ),
            "outputAfter": {
                "address": output_address,
                "byteCount": len(output_after),
                "sha256": hashlib.sha256(output_after).hexdigest(),
                "hex": output_after.hex(),
            },
            "outputChanged": output_before != output_after,
            "changedOutputQwordOffsets": _changed_qword_offsets(
                output_before, output_after
            ),
        }
    )
    boundaries.append(boundary)
    extension["executionEvents"].append(
        {"kind": "opaque-callee", "recordIndex": boundary["boundaryIndex"]}
    )
    _write_trace()
    return current, result_frame


def _continue_to_terminal(process):
    unexpected = []
    for _attempt in range(MAXIMUM_UNEXPECTED_TERMINAL_STOP_COUNT):
        state = process.GetState()
        if state in (lldb.eStateExited, lldb.eStateDetached):
            break
        error = process.Continue()
        if error is not None and hasattr(error, "Success") and not error.Success():
            raise RuntimeError(error.GetCString() or "terminal continue failed")
        state = process.GetState()
        if state in (lldb.eStateExited, lldb.eStateDetached):
            break
        unexpected.append(
            {
                "state": int(state),
                "selectedThreadStopReason": int(
                    process.GetSelectedThread().GetStopReason()
                ),
            }
        )
    state = process.GetState()
    terminal = {
        "state": int(state),
        "exited": state == lldb.eStateExited,
        "detached": state == lldb.eStateDetached,
        "exitStatus": process.GetExitStatus() if state == lldb.eStateExited else None,
        "unexpectedStops": unexpected,
    }
    _extension_trace()["terminalProcess"] = terminal
    if state != lldb.eStateExited or process.GetExitStatus() != 0 or unexpected:
        raise RuntimeError("prepare_layer_mask target did not exit normally")


def trace_selected_helper():
    """Drive the frozen helper entry through its exact return, then resume capture."""
    extension = _extension_trace()
    if extension is None:
        return
    process = _state["debugger"].GetSelectedTarget().GetProcess()
    try:
        if _state["manualTraceStarted"]:
            raise RuntimeError("prepare_layer_mask trace was invoked twice")
        if _state["selected"] is None:
            raise RuntimeError("prepare_layer_mask target entry was not reached")
        _require_stopped(process, "selected prepare_layer_mask entry")
        _state["manualTraceStarted"] = True
        _state["debugger"].SetAsync(False)
        if _state["debugger"].GetAsync():
            raise RuntimeError("debugger remained asynchronous")
        _disable_breakpoints(process.GetTarget())
        extension["manualTraceStart"] = {
            "selectedRecordIndex": _state["selected"]["recordIndex"],
            "threadID": _state["selected"]["threadID"],
            "entryPC": extension["helper"]["symbolStart"],
            "debuggerAsyncAfterSynchronousSet": _state["debugger"].GetAsync(),
        }
        extension["status"] = "selected-helper-instruction-trace-active"
        helper = extension["helper"]
        prepare_start = crop_base._state["prepareLayer"]["symbolStart"]
        return_pc = prepare_start + CALL_RETURN_OFFSET
        while len(extension["instructionStates"]) < MAXIMUM_HELPER_INSTRUCTION_COUNT:
            thread = _selected_thread(process)
            frame = thread.GetFrameAtIndex(0)
            pc = frame.GetPC()
            if (
                frame.GetFunctionName() == crop_base.PREPARE_LAYER_FUNCTION
                and pc == return_pc
            ):
                break
            if helper["symbolStart"] <= pc < helper["symbolEnd"]:
                thread, frame = _trace_helper_instruction(thread, frame, helper)
            else:
                thread, frame = _trace_opaque_callee(thread, frame)
        else:
            raise RuntimeError("prepare_layer_mask instruction bound exceeded")

        return_frame = _selected_thread(process).GetFrameAtIndex(0)
        return_registers = capture_base._full_register_snapshot(return_frame)
        return_values = _full_register_values(return_registers)
        selected = extension["selectedInvocation"]
        selected.update(
            {
                "returnPC": return_frame.GetPC(),
                "returnFrame": capture_base._frame_record(
                    return_frame, process.GetTarget()
                ),
                "returnRegisters": return_registers,
                "returnStack": _snapshot(
                    process,
                    return_values["sp"],
                    STACK_BYTE_COUNT,
                    "prepare_layer_mask return stack",
                ),
                "outputLayerShapesAtReturn": _snapshot(
                    process,
                    _state["selected"]["outputAddress"],
                    OUTPUT_BYTE_COUNT,
                    "prepare_layer_mask output at return",
                ),
                "callerRoleAtReturn": _snapshot(
                    process,
                    _state["selected"]["callerRoleBase"],
                    CALLER_ROLE_BYTE_COUNT,
                    "prepare_layer_mask caller role at return",
                ),
                "instructionStateCount": len(extension["instructionStates"]),
                "opaqueCalleeBoundaryCount": len(
                    extension["opaqueCalleeBoundaries"]
                ),
                "executionEventCount": len(extension["executionEvents"]),
            }
        )
        _state["manualTraceFinished"] = True
        extension["status"] = "selected-helper-instruction-trace-closed"
        _restore_breakpoints(process.GetTarget())
        _write_trace()
        _continue_to_terminal(process)
    except Exception as error:
        _failure("manual-trace", error)
        extension["status"] = "selected-helper-instruction-trace-failed"
        try:
            process.GetTarget().DisableAllBreakpoints()
            _continue_to_terminal(process)
        except Exception as terminal_error:
            _failure("terminal-process", terminal_error)
    _write_trace()


def finalize():
    extension = _extension_trace()
    if extension is not None:
        extension["statusBeforeFinalization"] = extension["status"]
        extension["status"] = "finalized"
        extension["finalHelperEntryHitCount"] = _state["helperEntryHitCount"]
        extension["finalQualifiedHelperEntryCount"] = _state[
            "qualifiedHelperEntryCount"
        ]
        extension["finalRejectedHelperEntryCount"] = _state[
            "rejectedHelperEntryCount"
        ]
        extension["finalHelperEntryRecordCount"] = len(
            extension["helperEntryRecords"]
        )
        extension["finalMarkerLinkCount"] = len(extension["markerLinks"])
        extension["finalInstructionStateCount"] = len(
            extension["instructionStates"]
        )
        extension["finalOpaqueCalleeBoundaryCount"] = len(
            extension["opaqueCalleeBoundaries"]
        )
        extension["finalExecutionEventCount"] = len(
            extension["executionEvents"]
        )
        extension["manualTraceStarted"] = _state["manualTraceStarted"]
        extension["manualTraceFinished"] = _state["manualTraceFinished"]
        extension["finalFailureCount"] = len(extension["failures"])
        extension["rejectionGroups"] = sorted(
            extension["rejectionGroups"].values(),
            key=lambda item: (item["reason"], item["prepareRecursionDepth"]),
        )
    holdout_retry.finalize()


def __lldb_init_module(debugger, internal_dict):
    holdout_retry.__lldb_init_module(debugger, internal_dict)
    _reset_state()
    _state["debugger"] = debugger
    trace = crop_base._state.get("trace")
    if trace is None:
        return
    trace["prepareLayerMaskInstructionExtension"] = _new_extension_trace()
    entry = crop_base._state.get("prepareEntryBreakpoint")
    if entry is None:
        _failure("initialization", "base prepare entry breakpoint is absent")
        return
    try:
        _set_callback(entry, "prepare_layer_entry", "wrapped prepare entry")
        _write_trace()
    except Exception as error:
        _failure("initialization", error)
