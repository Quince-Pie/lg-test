"""Trace the post-mask callee that first receives the crop destination.

The output-blind helper inventory maps sample two to ``prepare_layer_mask``
ordinal fourteen.  The fresh trace from run 31065907932 proved that call keeps
the first rectangle at ``x19+0x290`` empty.  Frozen ``prepare_layer`` code then
shows a second direct call at ``+0xf5c`` with the same destination register.

This extension reuses the exact ordinal-fourteen selection.  From the first
helper's return it single-steps the same caller to ``+0xf5c``, captures that
callee's complete symbol and execution, and resumes the inherited structural
store/marker capture.  Rectangle bytes are retained only after the structural
selection has stopped the process; they never participate in selection.

LLDB imports this module with macOS system Python, so it avoids syntax newer
than that runtime.
"""

import hashlib

import lldb

import capture_prepare_layer_mask_inventory_calibration_lldb as selected_base


base = selected_base.base
capture_base = base.capture_base
crop_base = base.crop_base

EXTENSION_SCHEMA_VERSION = 1
CALLER_CONTINUATION_START_OFFSET = 0xD94
PRODUCER_CALLEE_CALL_OFFSET = 0xF5C
PRODUCER_CALLEE_RETURN_OFFSET = 0xF60
PRODUCER_CALLEE_RELATIVE_TO_PREPARE_LAYER = -1206100
PRODUCER_CALLEE_CALL_RAW_LITTLE_ENDIAN_HEX = "5462fb97"
CALLER_LOCAL_STATE_OFFSET = 0x420
CALLER_OUTPUT_OFFSET = 0x290
STACK_BYTE_COUNT = 0x100
ARGUMENT_BYTE_COUNT = 0x400
CALLER_ROLE_BYTE_COUNT = 0x800
OUTPUT_BYTE_COUNT = 0x200
MAXIMUM_CALLER_INSTRUCTION_COUNT = 1024
MAXIMUM_CALLEE_INSTRUCTION_COUNT = 16384
MAXIMUM_OPAQUE_CALLEE_COUNT = 4096
TRACE_CHECKPOINT_INSTRUCTION_INTERVAL = 128
TRACE_CHECKPOINT_BOUNDARY_INTERVAL = 16


def _new_extension_trace():
    return {
        "prepareLayerCropProducerCalleeExtensionSchemaVersion": (
            EXTENSION_SCHEMA_VERSION
        ),
        "classification": (
            "prospective output-blind trace of the second x3=x19+0x290 "
            "callee after the structurally mapped prepare_layer_mask call; "
            "first-run callee identity and semantics remain calibration-only"
        ),
        "status": "initialized",
        "configuration": {
            "selectedMarkerInterval": base.TARGET_MARKER_INTERVAL,
            "selectedQualifiedHelperOrdinal": (selected_base._target_ordinal),
            "callerContinuationStartOffset": (CALLER_CONTINUATION_START_OFFSET),
            "producerCalleeCallOffset": PRODUCER_CALLEE_CALL_OFFSET,
            "producerCalleeReturnOffset": PRODUCER_CALLEE_RETURN_OFFSET,
            "producerCalleeRelativeToPrepareLayer": (
                PRODUCER_CALLEE_RELATIVE_TO_PREPARE_LAYER
            ),
            "producerCalleeCallRawLittleEndianHex": (
                PRODUCER_CALLEE_CALL_RAW_LITTLE_ENDIAN_HEX
            ),
            "callerLocalStateOffset": CALLER_LOCAL_STATE_OFFSET,
            "callerOutputOffset": CALLER_OUTPUT_OFFSET,
            "stackByteCount": STACK_BYTE_COUNT,
            "argumentByteCount": ARGUMENT_BYTE_COUNT,
            "callerRoleByteCount": CALLER_ROLE_BYTE_COUNT,
            "outputByteCount": OUTPUT_BYTE_COUNT,
            "maximumCallerInstructionCount": (MAXIMUM_CALLER_INSTRUCTION_COUNT),
            "maximumCalleeInstructionCount": (MAXIMUM_CALLEE_INSTRUCTION_COUNT),
            "maximumOpaqueCalleeCount": MAXIMUM_OPAQUE_CALLEE_COUNT,
            "traceCheckpointInstructionInterval": (
                TRACE_CHECKPOINT_INSTRUCTION_INTERVAL
            ),
            "traceCheckpointBoundaryInterval": TRACE_CHECKPOINT_BOUNDARY_INTERVAL,
            "selectionRule": (
                "reuse marker interval 2 prepare_layer_mask ordinal 14 from "
                "the frozen output-blind helper/store/marker inventory; after "
                "that call returns, follow only its exact thread, x19 role, "
                "and frame to static prepare_layer+0xf5c; read no rectangle "
                "or output bytes before selection"
            ),
            "callArgumentRule": (
                "at prepare_layer+0xf5c require x0 to equal the selected "
                "global state, x1=x19+0x420, x3=x19+0x290, and nonzero x2"
            ),
            "steppingRule": (
                "with every breakpoint disabled and LLDB synchronous, retain "
                "complete scalar/SIMD registers, 256 stack bytes, 2048 caller "
                "role bytes, and 512 destination bytes before and after every "
                "caller and opened-callee instruction; step out of every "
                "other callee as an explicit boundary"
            ),
            "correlationRule": (
                "after normal capture resumes, require the selected caller "
                "role to equal the independently opened sample-two producer "
                "store role and require the post-callee first rectangle to "
                "equal its retained binary64 producer bits"
            ),
            "hardwareWatchpointsUsed": False,
            "cropValuesUsedForSelection": False,
            "calleeExpectedSHA256": None,
        },
        "callerContinuationStates": [],
        "callee": {},
        "calleeInstructionStates": [],
        "opaqueCalleeBoundaries": [],
        "executionEvents": [],
        "failures": [],
    }


def _extension_trace():
    trace = crop_base._state.get("trace")
    if trace is None:
        return None
    return trace.get("prepareLayerCropProducerCalleeExtension")


def _write_trace():
    base._write_trace()


def _failure(stage, error):
    extension = _extension_trace()
    if extension is not None:
        extension["failures"].append({"stage": str(stage), "message": str(error)})
    base._failure("crop-producer-callee-" + str(stage), error)


def _output_bytes(process):
    return capture_base._read_memory(
        process,
        base._state["selected"]["outputAddress"],
        OUTPUT_BYTE_COUNT,
        "crop producer callee destination",
    )


def _role_bytes(process):
    return capture_base._read_memory(
        process,
        base._state["selected"]["callerRoleBase"],
        CALLER_ROLE_BYTE_COUNT,
        "crop producer callee caller role",
    )


def _memory_record(address, payload):
    return {
        "address": address,
        "byteCount": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "hex": payload.hex(),
    }


def _instruction_record(frame, scope_name, scope_start):
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    pc = frame.GetPC()
    raw = capture_base._read_memory(process, pc, 4, scope_name + " instruction")
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
        "scopeName": scope_name,
        "scopeOffset": pc - scope_start,
        "rawLittleEndianHex": raw.hex(),
        "mnemonic": mnemonic,
        "operands": operands,
        "comment": comment,
        "potentialCall": lowered.startswith("bl"),
        "potentialReturn": lowered.startswith("ret"),
    }


def _trace_instruction(thread, frame, scope_name, scope_start, states):
    process = thread.GetProcess()
    if scope_name == "prepareLayer" and len(states) >= MAXIMUM_CALLER_INSTRUCTION_COUNT:
        raise RuntimeError("crop producer caller instruction bound exceeded")
    if (
        scope_name == "producerCallee"
        and len(states) >= MAXIMUM_CALLEE_INSTRUCTION_COUNT
    ):
        raise RuntimeError("crop producer callee instruction bound exceeded")
    registers = capture_base._full_register_snapshot(frame)
    values = base._full_register_values(registers)
    output_before = _output_bytes(process)
    role_before = _role_bytes(process)
    state = {
        "stateIndex": len(states),
        "instruction": _instruction_record(frame, scope_name, scope_start),
        "registersBefore": registers,
        "stackBefore": base._snapshot(
            process,
            values["sp"],
            STACK_BYTE_COUNT,
            "crop producer instruction stack",
        ),
        "outputBefore": _memory_record(
            base._state["selected"]["outputAddress"], output_before
        ),
        "callerRoleBefore": _memory_record(
            base._state["selected"]["callerRoleBase"], role_before
        ),
    }
    error = lldb.SBError()
    thread.StepInstruction(False, error)
    if not error.Success():
        raise RuntimeError(
            error.GetCString() or "crop producer instruction step failed"
        )
    base._require_stopped(process, "crop producer instruction")
    current = base._selected_thread(process)
    result_frame = current.GetFrameAtIndex(0)
    return_registers = capture_base._full_register_snapshot(result_frame)
    return_values = base._full_register_values(return_registers)
    output_after = _output_bytes(process)
    role_after = _role_bytes(process)
    state.update(
        {
            "resultPC": result_frame.GetPC(),
            "resultFunction": result_frame.GetFunctionName(),
            "registersAfter": return_registers,
            "stackAfter": base._snapshot(
                process,
                return_values["sp"],
                STACK_BYTE_COUNT,
                "crop producer instruction result stack",
            ),
            "outputAfter": _memory_record(
                base._state["selected"]["outputAddress"], output_after
            ),
            "callerRoleAfter": _memory_record(
                base._state["selected"]["callerRoleBase"], role_after
            ),
            "outputChanged": output_before != output_after,
            "changedOutputQwordOffsets": base._changed_qword_offsets(
                output_before, output_after
            ),
            "callerRoleChanged": role_before != role_after,
            "changedCallerRoleQwordOffsets": base._changed_qword_offsets(
                role_before, role_after
            ),
        }
    )
    states.append(state)
    _extension_trace()["executionEvents"].append(
        {
            "kind": scope_name + "-instruction",
            "recordIndex": state["stateIndex"],
        }
    )
    if len(states) % TRACE_CHECKPOINT_INSTRUCTION_INTERVAL == 0:
        _write_trace()
    return current, result_frame


def _trace_opaque_callee(thread, frame, expected_return_function):
    process = thread.GetProcess()
    extension = _extension_trace()
    boundaries = extension["opaqueCalleeBoundaries"]
    if len(boundaries) >= MAXIMUM_OPAQUE_CALLEE_COUNT:
        raise RuntimeError("crop producer opaque callee bound exceeded")
    registers = capture_base._full_register_snapshot(frame)
    values = base._full_register_values(registers)
    output_before = _output_bytes(process)
    role_before = _role_bytes(process)
    boundary = {
        "boundaryIndex": len(boundaries),
        "expectedReturnFunction": expected_return_function,
        "entryFrame": capture_base._frame_record(frame, process.GetTarget()),
        "registersAtEntry": registers,
        "stackAtEntry": base._snapshot(
            process,
            values["sp"],
            STACK_BYTE_COUNT,
            "crop producer opaque entry stack",
        ),
        "outputBefore": _memory_record(
            base._state["selected"]["outputAddress"], output_before
        ),
        "callerRoleBefore": _memory_record(
            base._state["selected"]["callerRoleBase"], role_before
        ),
    }
    error = lldb.SBError()
    thread.StepOut(error)
    if not error.Success():
        raise RuntimeError(error.GetCString() or "crop producer opaque step-out failed")
    base._require_stopped(process, "crop producer opaque callee")
    current = base._selected_thread(process)
    result_frame = current.GetFrameAtIndex(0)
    return_registers = capture_base._full_register_snapshot(result_frame)
    return_values = base._full_register_values(return_registers)
    output_after = _output_bytes(process)
    role_after = _role_bytes(process)
    boundary.update(
        {
            "returnFrame": capture_base._frame_record(
                result_frame, process.GetTarget()
            ),
            "registersAtReturn": return_registers,
            "stackAtReturn": base._snapshot(
                process,
                return_values["sp"],
                STACK_BYTE_COUNT,
                "crop producer opaque return stack",
            ),
            "outputAfter": _memory_record(
                base._state["selected"]["outputAddress"], output_after
            ),
            "callerRoleAfter": _memory_record(
                base._state["selected"]["callerRoleBase"], role_after
            ),
            "outputChanged": output_before != output_after,
            "changedOutputQwordOffsets": base._changed_qword_offsets(
                output_before, output_after
            ),
            "callerRoleChanged": role_before != role_after,
            "changedCallerRoleQwordOffsets": base._changed_qword_offsets(
                role_before, role_after
            ),
        }
    )
    boundaries.append(boundary)
    extension["executionEvents"].append(
        {"kind": "opaque-callee", "recordIndex": boundary["boundaryIndex"]}
    )
    if len(boundaries) % TRACE_CHECKPOINT_BOUNDARY_INTERVAL == 0:
        _write_trace()
    return current, result_frame


def _record_helper_return(process, prepare_start):
    return_frame = base._selected_thread(process).GetFrameAtIndex(0)
    return_registers = capture_base._full_register_snapshot(return_frame)
    return_values = base._full_register_values(return_registers)
    selected = base._extension_trace()["selectedInvocation"]
    selected.update(
        {
            "returnPC": return_frame.GetPC(),
            "returnFrame": capture_base._frame_record(
                return_frame, process.GetTarget()
            ),
            "returnRegisters": return_registers,
            "returnStack": base._snapshot(
                process,
                return_values["sp"],
                STACK_BYTE_COUNT,
                "prepare_layer_mask return stack",
            ),
            "outputLayerShapesAtReturn": base._snapshot(
                process,
                base._state["selected"]["outputAddress"],
                OUTPUT_BYTE_COUNT,
                "prepare_layer_mask output at return",
            ),
            "callerRoleAtReturn": base._snapshot(
                process,
                base._state["selected"]["callerRoleBase"],
                CALLER_ROLE_BYTE_COUNT,
                "prepare_layer_mask caller role at return",
            ),
            "instructionStateCount": len(base._extension_trace()["instructionStates"]),
            "opaqueCalleeBoundaryCount": len(
                base._extension_trace()["opaqueCalleeBoundaries"]
            ),
            "executionEventCount": len(base._extension_trace()["executionEvents"]),
        }
    )
    if (
        return_frame.GetFunctionName() != crop_base.PREPARE_LAYER_FUNCTION
        or return_frame.GetPC() != prepare_start + CALLER_CONTINUATION_START_OFFSET
        or return_values["x19"] != base._state["selected"]["callerRoleBase"]
    ):
        raise RuntimeError("post-mask caller identity differs")
    return return_frame, return_registers


def _capture_callee_identity(process, frame, prepare_start):
    target = process.GetTarget()
    entry_pc = frame.GetPC()
    expected = prepare_start + PRODUCER_CALLEE_RELATIVE_TO_PREPARE_LAYER
    if entry_pc != expected:
        raise RuntimeError("crop producer callee entry address differs")
    resolved = target.ResolveLoadAddress(entry_pc)
    symbol = resolved.GetSymbol()
    if not symbol.IsValid():
        raise RuntimeError("crop producer callee symbol is invalid")
    start = symbol.GetStartAddress().GetLoadAddress(target)
    end = symbol.GetEndAddress().GetLoadAddress(target)
    if not start <= entry_pc < end or end - start > 0x10000:
        raise RuntimeError("crop producer callee symbol range differs")
    code = capture_base._read_memory(
        process, start, end - start, "crop producer callee complete code"
    )
    function_name = frame.GetFunctionName()
    symbol_name = symbol.GetName()
    if not function_name and not symbol_name:
        raise RuntimeError("crop producer callee name is absent")
    return {
        "function": function_name or symbol_name,
        "symbolName": symbol_name,
        "relativeToPrepareLayer": entry_pc - prepare_start,
        "entryPC": entry_pc,
        "entryOffset": entry_pc - start,
        "symbolRelativeToPrepareLayer": start - prepare_start,
        "symbolStart": start,
        "symbolEnd": end,
        "symbolByteCount": len(code),
        "expectedSHA256": None,
        "observedSHA256": hashlib.sha256(code).hexdigest(),
        "hex": code.hex(),
        "module": base._module_record(resolved.GetModule(), target),
        "callPC": prepare_start + PRODUCER_CALLEE_CALL_OFFSET,
        "callReturnPC": prepare_start + PRODUCER_CALLEE_RETURN_OFFSET,
        "callInstructionSHA256": hashlib.sha256(
            bytes.fromhex(PRODUCER_CALLEE_CALL_RAW_LITTLE_ENDIAN_HEX)
        ).hexdigest(),
    }


def trace_selected_producer_callee():
    """Trace ordinal fourteen, its exact caller continuation, and the next callee."""
    extension = _extension_trace()
    if extension is None:
        return
    process = base._state["debugger"].GetSelectedTarget().GetProcess()
    try:
        if selected_base._mode != selected_base.SELECTED_MODE:
            raise RuntimeError("crop producer callee requires selected mode")
        if base._state["manualTraceStarted"]:
            raise RuntimeError("crop producer callee trace was invoked twice")
        if base._state["selected"] is None:
            raise RuntimeError("structurally selected mask call was not reached")
        base._require_stopped(process, "selected prepare_layer_mask entry")
        base._state["manualTraceStarted"] = True
        base._state["debugger"].SetAsync(False)
        if base._state["debugger"].GetAsync():
            raise RuntimeError("debugger remained asynchronous")
        base._disable_breakpoints(process.GetTarget())
        prepare_start = crop_base._state["prepareLayer"]["symbolStart"]
        helper_extension = base._extension_trace()
        helper = helper_extension["helper"]
        helper_extension["manualTraceStart"] = {
            "selectedRecordIndex": base._state["selected"]["recordIndex"],
            "threadID": base._state["selected"]["threadID"],
            "entryPC": helper["symbolStart"],
            "debuggerAsyncAfterSynchronousSet": (base._state["debugger"].GetAsync()),
        }
        helper_extension["status"] = "selected-helper-instruction-trace-active"
        helper_return_pc = prepare_start + CALLER_CONTINUATION_START_OFFSET
        while (
            len(helper_extension["instructionStates"])
            < base.MAXIMUM_HELPER_INSTRUCTION_COUNT
        ):
            thread = base._selected_thread(process)
            frame = thread.GetFrameAtIndex(0)
            pc = frame.GetPC()
            if (
                frame.GetFunctionName() == crop_base.PREPARE_LAYER_FUNCTION
                and pc == helper_return_pc
            ):
                break
            if helper["symbolStart"] <= pc < helper["symbolEnd"]:
                base._trace_helper_instruction(thread, frame, helper)
            else:
                base._trace_opaque_callee(thread, frame)
        else:
            raise RuntimeError("prepare_layer_mask instruction bound exceeded")

        caller_frame, helper_return_registers = _record_helper_return(
            process, prepare_start
        )
        helper_extension["status"] = "selected-helper-instruction-trace-closed"
        extension["status"] = "caller-continuation-trace-active"
        extension["selectedCaller"] = {
            "threadID": base._state["selected"]["threadID"],
            "callerRoleBase": base._state["selected"]["callerRoleBase"],
            "outputAddress": base._state["selected"]["outputAddress"],
            "helperReturnFrame": capture_base._frame_record(
                caller_frame, process.GetTarget()
            ),
            "helperReturnRegisters": helper_return_registers,
            "outputAtHelperReturn": base._snapshot(
                process,
                base._state["selected"]["outputAddress"],
                OUTPUT_BYTE_COUNT,
                "crop producer output at helper return",
            ),
            "callerRoleAtHelperReturn": base._snapshot(
                process,
                base._state["selected"]["callerRoleBase"],
                CALLER_ROLE_BYTE_COUNT,
                "crop producer role at helper return",
            ),
        }
        _write_trace()

        call_pc = prepare_start + PRODUCER_CALLEE_CALL_OFFSET
        while (
            len(extension["callerContinuationStates"])
            < MAXIMUM_CALLER_INSTRUCTION_COUNT
        ):
            thread = base._selected_thread(process)
            frame = thread.GetFrameAtIndex(0)
            if (
                frame.GetFunctionName() == crop_base.PREPARE_LAYER_FUNCTION
                and frame.GetPC() == call_pc
            ):
                break
            if frame.GetFunctionName() == crop_base.PREPARE_LAYER_FUNCTION:
                _trace_instruction(
                    thread,
                    frame,
                    "prepareLayer",
                    prepare_start,
                    extension["callerContinuationStates"],
                )
            else:
                _trace_opaque_callee(thread, frame, crop_base.PREPARE_LAYER_FUNCTION)
        else:
            raise RuntimeError("crop producer call site was not reached")

        call_frame = base._selected_thread(process).GetFrameAtIndex(0)
        call_registers = capture_base._full_register_snapshot(call_frame)
        call_values = base._full_register_values(call_registers)
        selected_invocation = base._extension_trace()["selectedInvocation"]
        selected_entry_values = base._full_register_values(
            selected_invocation["entryRegisters"]
        )
        raw_call = capture_base._read_memory(
            process, call_pc, 4, "crop producer callee call"
        )
        if (
            raw_call.hex() != PRODUCER_CALLEE_CALL_RAW_LITTLE_ENDIAN_HEX
            or call_values["x19"] != base._state["selected"]["callerRoleBase"]
            or call_values["x0"] != selected_entry_values["x0"]
            or call_values["x1"] != call_values["x19"] + CALLER_LOCAL_STATE_OFFSET
            or call_values["x3"] != base._state["selected"]["outputAddress"]
            or call_values["x2"] == 0
        ):
            raise RuntimeError("crop producer callee call arguments differ")
        extension["calleeCall"] = {
            "frame": capture_base._frame_record(call_frame, process.GetTarget()),
            "registers": call_registers,
            "argumentX2AtCall": base._snapshot(
                process,
                call_values["x2"],
                ARGUMENT_BYTE_COUNT,
                "crop producer callee x2 argument",
            ),
            "outputAtCall": base._snapshot(
                process,
                call_values["x3"],
                OUTPUT_BYTE_COUNT,
                "crop producer output at callee call",
            ),
            "callerRoleAtCall": base._snapshot(
                process,
                call_values["x19"],
                CALLER_ROLE_BYTE_COUNT,
                "crop producer caller role at callee call",
            ),
            "cropValuesUsedForSelection": False,
        }
        thread, callee_frame = _trace_instruction(
            base._selected_thread(process),
            call_frame,
            "prepareLayer",
            prepare_start,
            extension["callerContinuationStates"],
        )
        extension["callee"] = _capture_callee_identity(
            process, callee_frame, prepare_start
        )
        callee_registers = capture_base._full_register_snapshot(callee_frame)
        callee_values = base._full_register_values(callee_registers)
        extension["calleeEntry"] = {
            "frame": capture_base._frame_record(callee_frame, process.GetTarget()),
            "registers": callee_registers,
            "stack": base._snapshot(
                process,
                callee_values["sp"],
                STACK_BYTE_COUNT,
                "crop producer callee entry stack",
            ),
            "output": base._snapshot(
                process,
                base._state["selected"]["outputAddress"],
                OUTPUT_BYTE_COUNT,
                "crop producer callee entry output",
            ),
            "callerRole": base._snapshot(
                process,
                base._state["selected"]["callerRoleBase"],
                CALLER_ROLE_BYTE_COUNT,
                "crop producer callee entry role",
            ),
        }
        _write_trace()
        extension["status"] = "producer-callee-instruction-trace-active"
        callee = extension["callee"]
        return_pc = prepare_start + PRODUCER_CALLEE_RETURN_OFFSET
        while (
            len(extension["calleeInstructionStates"]) < MAXIMUM_CALLEE_INSTRUCTION_COUNT
        ):
            thread = base._selected_thread(process)
            frame = thread.GetFrameAtIndex(0)
            pc = frame.GetPC()
            if (
                frame.GetFunctionName() == crop_base.PREPARE_LAYER_FUNCTION
                and pc == return_pc
            ):
                break
            if callee["symbolStart"] <= pc < callee["symbolEnd"]:
                _trace_instruction(
                    thread,
                    frame,
                    "producerCallee",
                    callee["symbolStart"],
                    extension["calleeInstructionStates"],
                )
            else:
                _trace_opaque_callee(thread, frame, callee["function"])
        else:
            raise RuntimeError("crop producer callee instruction bound exceeded")

        return_frame = base._selected_thread(process).GetFrameAtIndex(0)
        return_registers = capture_base._full_register_snapshot(return_frame)
        return_values = base._full_register_values(return_registers)
        if (
            return_frame.GetFunctionName() != crop_base.PREPARE_LAYER_FUNCTION
            or return_frame.GetPC() != return_pc
            or return_values["x19"] != base._state["selected"]["callerRoleBase"]
        ):
            raise RuntimeError("crop producer callee return identity differs")
        extension["calleeReturn"] = {
            "frame": capture_base._frame_record(return_frame, process.GetTarget()),
            "registers": return_registers,
            "stack": base._snapshot(
                process,
                return_values["sp"],
                STACK_BYTE_COUNT,
                "crop producer callee return stack",
            ),
            "output": base._snapshot(
                process,
                base._state["selected"]["outputAddress"],
                OUTPUT_BYTE_COUNT,
                "crop producer callee return output",
            ),
            "callerRole": base._snapshot(
                process,
                base._state["selected"]["callerRoleBase"],
                CALLER_ROLE_BYTE_COUNT,
                "crop producer callee return role",
            ),
        }
        extension["status"] = "producer-callee-instruction-trace-closed"
        base._state["manualTraceFinished"] = True
        base._restore_breakpoints(process.GetTarget())
        _write_trace()
        base._continue_to_terminal(process)
    except Exception as error:
        _failure("manual-trace", error)
        extension["status"] = "producer-callee-instruction-trace-failed"
        try:
            process.GetTarget().DisableAllBreakpoints()
            base._continue_to_terminal(process)
        except Exception as terminal_error:
            _failure("terminal-process", terminal_error)
    _write_trace()


def finalize():
    extension = _extension_trace()
    if extension is not None:
        extension["statusBeforeFinalization"] = extension["status"]
        extension["status"] = "finalized"
        extension["finalCallerContinuationStateCount"] = len(
            extension["callerContinuationStates"]
        )
        extension["finalCalleeInstructionStateCount"] = len(
            extension["calleeInstructionStates"]
        )
        extension["finalOpaqueCalleeBoundaryCount"] = len(
            extension["opaqueCalleeBoundaries"]
        )
        extension["finalExecutionEventCount"] = len(extension["executionEvents"])
        extension["finalFailureCount"] = len(extension["failures"])
    selected_base.finalize()


def __lldb_init_module(debugger, internal_dict):
    selected_base.__lldb_init_module(debugger, internal_dict)
    trace = crop_base._state.get("trace")
    if trace is None:
        return
    trace["prepareLayerCropProducerCalleeExtension"] = _new_extension_trace()
    try:
        if (
            selected_base._mode != selected_base.SELECTED_MODE
            or selected_base._target_ordinal != 14
        ):
            raise RuntimeError("crop producer callee structural selector differs")
        _write_trace()
    except Exception as error:
        _failure("initialization", error)
