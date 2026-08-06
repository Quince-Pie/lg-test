"""Trace the exact dynamic callee used by ``Group.margin`` case 22.

Run 31118243811 opened one stable authenticated target at SwiftUICore module
offset 0x76bc54.  This overlay keeps the complete Group execution capture and
selects invocation ordinal 20 only; the ordinal and profile are already opened,
so this is an arithmetic diagnostic with no transfer or product authority.

LLDB imports this file with the macOS system Python, so it avoids newer-only
syntax.
"""

import hashlib
import struct

import lldb

import capture_backdrop_margin_group_execution_lldb as group


CASE22_CALLEE_TRACE_SCHEMA_VERSION = 1
SELECTED_INVOCATION_INDEX = 20
CASE22_CALL_OFFSET = 0x268
CASE22_RETURN_OFFSET = 0x26C
CASE22_TARGET_MODULE_OFFSET = 0x76BC54
CASE22_INSTRUCTION_HEX = "910b3fd7"
OBJECT_BYTE_COUNT = 0x1000
STACK_BYTE_COUNT = 0x400
POINTER_PROBE_BYTE_COUNT = 0x200
MAXIMUM_POINTER_PROBE_COUNT = 128
MAXIMUM_INSTRUCTION_COUNT = 8192
MAXIMUM_OPAQUE_CALLEE_COUNT = 512
MAXIMUM_SYMBOL_BYTE_COUNT = 0x20000
MAXIMUM_TOTAL_OPAQUE_CODE_BYTE_COUNT = 8 * 1024 * 1024

GENERAL_REGISTER_NAMES = tuple("x%d" % index for index in range(31)) + (
    "sp",
    "pc",
    "cpsr",
)
SIMD_REGISTER_NAMES = tuple("v%d" % index for index in range(32)) + (
    "fpsr",
    "fpcr",
)

_group_new_trace = group._new_trace
_group_finalize = group.finalize
_group_producer_stage = group.producer_stage


def _new_trace():
    trace = _group_new_trace()
    trace["classification"] = (
        "retrospective output-blind instruction diagnostic of the already-opened "
        "Group.margin case-22 target; public-input transfer, optical parity, "
        "physical-output parity, and production authority remain closed"
    )
    trace["case22CalleeTrace"] = {
        "case22CalleeTraceSchemaVersion": CASE22_CALLEE_TRACE_SCHEMA_VERSION,
        "status": "initialized",
        "configuration": {
            "selectedInvocationIndex": SELECTED_INVOCATION_INDEX,
            "selection": (
                "fixed ordinal 20 among exact Group.margin invocations selected "
                "by the opened updateSDFEffects caller identity"
            ),
            "selectionCalibratedFromOpenedRun": 31118243811,
            "case22CallOffset": CASE22_CALL_OFFSET,
            "case22ReturnOffset": CASE22_RETURN_OFFSET,
            "case22TargetModuleOffset": CASE22_TARGET_MODULE_OFFSET,
            "case22InstructionHex": CASE22_INSTRUCTION_HEX,
            "objectByteCount": OBJECT_BYTE_COUNT,
            "stackByteCount": STACK_BYTE_COUNT,
            "pointerProbeByteCount": POINTER_PROBE_BYTE_COUNT,
            "maximumPointerProbeCount": MAXIMUM_POINTER_PROBE_COUNT,
            "maximumInstructionCount": MAXIMUM_INSTRUCTION_COUNT,
            "maximumOpaqueCalleeCount": MAXIMUM_OPAQUE_CALLEE_COUNT,
            "maximumSymbolByteCount": MAXIMUM_SYMBOL_BYTE_COUNT,
            "maximumTotalOpaqueCodeByteCount": (
                MAXIMUM_TOTAL_OPAQUE_CODE_BYTE_COUNT
            ),
            "capturedMarginUsedForRuntimeSelection": False,
            "capturedCropUsedForRuntimeSelection": False,
            "capturedImageUsedForRuntimeSelection": False,
            "capturedPixelUsedForRuntimeSelection": False,
        },
        "selectedInvocationIndex": None,
        "callerCall": {},
        "target": {},
        "entry": {},
        "instructionStates": [],
        "opaqueCallees": [],
        "executionEvents": [],
        "return": {},
        "failures": [],
    }
    return trace


def _extension():
    trace = group.writer.base._state.get("trace")
    if trace is None:
        return None
    return trace.get("case22CalleeTrace")


def _write_trace():
    group._write_trace()


def _register_record(frame, name):
    value = frame.FindRegister(name)
    if not value.IsValid():
        raise RuntimeError("missing register %s" % name)
    byte_count = value.GetByteSize()
    data = value.GetData()
    if byte_count <= 0 or not data.IsValid() or data.GetByteSize() != byte_count:
        raise RuntimeError("register %s data is unavailable" % name)
    error = lldb.SBError()
    payload = bytearray()
    for offset in range(byte_count):
        payload.append(data.GetUnsignedInt8(error, offset))
        if not error.Success():
            raise RuntimeError(
                "register %s byte %d failed: %s"
                % (name, offset, error.GetCString() or "unknown SBData error")
            )
    record = {
        "name": name,
        "byteCount": byte_count,
        "hex": bytes(payload).hex(),
        "valueString": value.GetValue(),
    }
    if byte_count <= 8:
        record["unsignedValue"] = value.GetValueAsUnsigned(0)
    return record


def _register_snapshot(frame, names):
    return [_register_record(frame, name) for name in names]


def _full_register_snapshot(frame):
    return {
        "general": _register_snapshot(frame, GENERAL_REGISTER_NAMES),
        "simd": _register_snapshot(frame, SIMD_REGISTER_NAMES),
    }


def _register_value(snapshot, name):
    for group_name in ("general", "simd"):
        for record in snapshot[group_name]:
            if record["name"] == name:
                value = record.get("unsignedValue")
                if value is None:
                    raise RuntimeError("register %s is not scalar" % name)
                return value
    raise RuntimeError("register %s is absent" % name)


def _snapshot(process, address, byte_count, label):
    return group._snapshot_or_empty(process, address, byte_count, label)


def _frame_record(frame):
    return group.writer.base._frame_record(
        frame, frame.GetThread().GetProcess().GetTarget()
    )


def _selected_thread(process, thread_id):
    thread = process.GetThreadByID(thread_id)
    if not thread.IsValid():
        raise RuntimeError("case-22 selected thread is unavailable")
    return thread


def _require_stopped(process, label):
    if process.GetState() != lldb.eStateStopped:
        raise RuntimeError(label + " did not stop the process")


def _capture_symbol(process, address, label, expected_module_offset=None):
    target = process.GetTarget()
    resolved = target.ResolveLoadAddress(address)
    if not resolved.IsValid():
        raise RuntimeError(label + " address is unresolved")
    module = group.writer.base._module_record(resolved.GetModule(), target)
    if not module.get("valid"):
        raise RuntimeError(label + " module is unresolved")
    if expected_module_offset is not None and (
        module.get("uuid") != group.SWIFTUICORE_UUID
        or address - module.get("loadAddress", 0) != expected_module_offset
    ):
        raise RuntimeError(label + " SwiftUICore identity differs")
    symbol = resolved.GetSymbol()
    if not symbol.IsValid():
        raise RuntimeError(label + " symbol is unresolved")
    start = symbol.GetStartAddress().GetLoadAddress(target)
    end = symbol.GetEndAddress().GetLoadAddress(target)
    if (
        start == lldb.LLDB_INVALID_ADDRESS
        or end == lldb.LLDB_INVALID_ADDRESS
        or not start <= address < end
        or not 0 < end - start <= MAXIMUM_SYMBOL_BYTE_COUNT
    ):
        raise RuntimeError(label + " symbol bounds differ")
    payload = group.writer.base._read_memory(
        process, start, end - start, label + " complete code"
    )
    return {
        "selectedAddress": address,
        "function": symbol.GetName() or "",
        "symbolStart": start,
        "symbolEnd": end,
        "symbolOffset": address - start,
        "symbolByteCount": len(payload),
        "codeSHA256": hashlib.sha256(payload).hexdigest(),
        "hex": payload.hex(),
        "module": module,
    }


def _capture_pointer_probes(process, snapshots):
    candidates = []
    seen = set()
    for source, snapshot in snapshots:
        payload = bytes.fromhex(snapshot["hex"])
        for offset in range(0, len(payload) - 7, 8):
            address = struct.unpack_from("<Q", payload, offset)[0]
            if (
                address in seen
                or address < 0x100000000
                or address >= 0x0001000000000000
                or address & 0x7
            ):
                continue
            seen.add(address)
            candidates.append((source, offset, address))
            if len(candidates) >= MAXIMUM_POINTER_PROBE_COUNT:
                break
        if len(candidates) >= MAXIMUM_POINTER_PROBE_COUNT:
            break
    records = []
    for source, offset, address in candidates:
        record = {
            "source": source,
            "sourceByteOffset": offset,
            "address": address,
            "snapshot": None,
            "failure": None,
        }
        try:
            record["snapshot"] = _snapshot(
                process,
                address,
                POINTER_PROBE_BYTE_COUNT,
                "case-22 pointer probe",
            )
        except Exception as error:
            record["failure"] = str(error)
        records.append(record)
    return records


def _capture_entry(process, frame, object_address):
    registers = _full_register_snapshot(frame)
    if _register_value(registers, "x0") != object_address:
        raise RuntimeError("case-22 target x0 differs from the projected object")
    stack = _snapshot(
        process,
        _register_value(registers, "sp"),
        STACK_BYTE_COUNT,
        "case-22 entry stack",
    )
    object_snapshot = _snapshot(
        process,
        object_address,
        OBJECT_BYTE_COUNT,
        "case-22 target object",
    )
    return {
        "frame": _frame_record(frame),
        "registers": registers,
        "stack": stack,
        "object": object_snapshot,
        "pointerProbes": _capture_pointer_probes(
            process, (("object", object_snapshot), ("stack", stack))
        ),
    }


def _capture_instruction(process, frame, target_record):
    extension = _extension()
    states = extension["instructionStates"]
    if len(states) >= MAXIMUM_INSTRUCTION_COUNT:
        raise RuntimeError("case-22 instruction bound exceeded")
    pc = frame.GetPC()
    if not target_record["symbolStart"] <= pc < target_record["symbolEnd"]:
        raise RuntimeError("case-22 instruction is outside the target symbol")
    instruction = group.writer.base._read_memory(
        process, pc, 4, "case-22 target instruction"
    )
    registers = _full_register_snapshot(frame)
    state = {
        "stateIndex": len(states),
        "eventIndex": len(extension["executionEvents"]),
        "pc": pc,
        "symbolOffset": pc - target_record["symbolStart"],
        "instructionHex": instruction.hex(),
        "frame": _frame_record(frame),
        "registersBefore": registers,
        "stackBefore": _snapshot(
            process,
            _register_value(registers, "sp"),
            STACK_BYTE_COUNT,
            "case-22 instruction stack",
        ),
    }
    thread = frame.GetThread()
    error = lldb.SBError()
    thread.StepInstruction(False, error)
    if not error.Success():
        raise RuntimeError(error.GetCString() or "case-22 instruction step failed")
    _require_stopped(process, "case-22 instruction")
    current = _selected_thread(process, thread.GetThreadID())
    result_frame = current.GetFrameAtIndex(0)
    state.update(
        {
            "resultPC": result_frame.GetPC(),
            "resultFunction": result_frame.GetFunctionName() or "",
            "resultFrame": _frame_record(result_frame),
        }
    )
    states.append(state)
    extension["executionEvents"].append(
        {"kind": "target-instruction", "recordIndex": state["stateIndex"]}
    )
    if len(states) % 32 == 0:
        _write_trace()
    return current, result_frame


def _capture_opaque_callee(process, thread, frame, expected_target_function):
    extension = _extension()
    boundaries = extension["opaqueCallees"]
    if len(boundaries) >= MAXIMUM_OPAQUE_CALLEE_COUNT:
        raise RuntimeError("case-22 opaque-callee bound exceeded")
    identity = _capture_symbol(process, frame.GetPC(), "case-22 opaque callee")
    previous_code_bytes = group.writer.base._state["case22OpaqueCodeBytes"]
    if previous_code_bytes + identity["symbolByteCount"] > (
        MAXIMUM_TOTAL_OPAQUE_CODE_BYTE_COUNT
    ):
        raise RuntimeError("case-22 opaque code-byte total exceeded")
    group.writer.base._state["case22OpaqueCodeBytes"] = (
        previous_code_bytes + identity["symbolByteCount"]
    )
    registers = _full_register_snapshot(frame)
    boundary = {
        "boundaryIndex": len(boundaries),
        "eventIndex": len(extension["executionEvents"]),
        "expectedReturnFunction": expected_target_function,
        "callee": identity,
        "entryFrame": _frame_record(frame),
        "registersAtEntry": registers,
        "stackAtEntry": _snapshot(
            process,
            _register_value(registers, "sp"),
            STACK_BYTE_COUNT,
            "case-22 opaque entry stack",
        ),
    }
    error = lldb.SBError()
    thread.StepOut(error)
    if not error.Success():
        raise RuntimeError(error.GetCString() or "case-22 opaque step-out failed")
    _require_stopped(process, "case-22 opaque callee")
    current = _selected_thread(process, thread.GetThreadID())
    return_frame = current.GetFrameAtIndex(0)
    return_registers = _full_register_snapshot(return_frame)
    boundary.update(
        {
            "returnFrame": _frame_record(return_frame),
            "registersAtReturn": return_registers,
            "stackAtReturn": _snapshot(
                process,
                _register_value(return_registers, "sp"),
                STACK_BYTE_COUNT,
                "case-22 opaque return stack",
            ),
        }
    )
    boundaries.append(boundary)
    extension["executionEvents"].append(
        {"kind": "opaque-callee", "recordIndex": boundary["boundaryIndex"]}
    )
    return current, return_frame


def _trace_case22(frame, invocation_index, gate):
    extension = _extension()
    process = frame.GetThread().GetProcess()
    thread_id = frame.GetThread().GetThreadID()
    target_address = group.writer.base._register_u64(frame, "x28")
    modifier = group.writer.base._register_u64(frame, "x17")
    object_address = group.writer.base._register_u64(frame, "x20")
    module_base = gate["module"]["loadAddress"]
    if target_address - module_base != CASE22_TARGET_MODULE_OFFSET:
        raise RuntimeError("case-22 authenticated target offset differs")
    instruction = group.writer.base._read_memory(
        process, frame.GetPC(), 4, "case-22 caller instruction"
    )
    if instruction.hex() != CASE22_INSTRUCTION_HEX:
        raise RuntimeError("case-22 caller instruction differs")

    extension["status"] = "instruction-trace-active"
    extension["selectedInvocationIndex"] = invocation_index
    extension["callerCall"] = {
        "frame": _frame_record(frame),
        "instructionOffset": CASE22_CALL_OFFSET,
        "instructionHex": instruction.hex(),
        "authenticatedTargetRaw": target_address,
        "authenticatedModifierRaw": modifier,
        "objectAddress": object_address,
        "registers": _full_register_snapshot(frame),
    }
    return_breakpoint = group.writer.base._state["groupStageBreakpoints"].get(
        CASE22_RETURN_OFFSET
    )
    if return_breakpoint is None or not return_breakpoint.IsValid():
        raise RuntimeError("case-22 return breakpoint is unavailable")
    return_was_enabled = return_breakpoint.IsEnabled()
    return_breakpoint.SetEnabled(False)
    try:
        error = lldb.SBError()
        frame.GetThread().StepInstruction(False, error)
        if not error.Success():
            raise RuntimeError(error.GetCString() or "case-22 call step failed")
        _require_stopped(process, "case-22 target entry")
        thread = _selected_thread(process, thread_id)
        target_frame = thread.GetFrameAtIndex(0)
        if target_frame.GetPC() != target_address:
            raise RuntimeError("case-22 authenticated branch target differs")
        target_record = _capture_symbol(
            process,
            target_address,
            "case-22 target",
            CASE22_TARGET_MODULE_OFFSET,
        )
        extension["target"] = target_record
        extension["entry"] = _capture_entry(process, target_frame, object_address)
        target_function = target_frame.GetFunctionName() or target_record["function"]
        group_return_pc = gate["symbolStart"] + CASE22_RETURN_OFFSET

        while len(extension["instructionStates"]) < MAXIMUM_INSTRUCTION_COUNT:
            current = _selected_thread(process, thread_id)
            current_frame = current.GetFrameAtIndex(0)
            pc = current_frame.GetPC()
            if target_record["symbolStart"] <= pc < target_record["symbolEnd"]:
                _capture_instruction(process, current_frame, target_record)
                continue
            if pc == group_return_pc:
                break
            _capture_opaque_callee(
                process, current, current_frame, target_function
            )
        else:
            raise RuntimeError("case-22 instruction bound exceeded")

        return_thread = _selected_thread(process, thread_id)
        return_frame = return_thread.GetFrameAtIndex(0)
        if return_frame.GetPC() != group_return_pc:
            raise RuntimeError("case-22 target did not return to Group.margin")
        return_registers = _full_register_snapshot(return_frame)
        return_object = _snapshot(
            process,
            object_address,
            OBJECT_BYTE_COUNT,
            "case-22 return object",
        )
        extension["return"] = {
            "frame": _frame_record(return_frame),
            "registers": return_registers,
            "stack": _snapshot(
                process,
                _register_value(return_registers, "sp"),
                STACK_BYTE_COUNT,
                "case-22 return stack",
            ),
            "object": return_object,
            "objectChanged": (
                return_object["hex"] != extension["entry"]["object"]["hex"]
            ),
        }

        # The normal +0x26c breakpoint was disabled while stepping.  Record the
        # exact inherited stage once at the stopped return PC, then execute that
        # instruction before restoring the breakpoint for later invocations.
        _group_producer_stage(return_frame, None, None)
        error = lldb.SBError()
        return_thread.StepInstruction(False, error)
        if not error.Success():
            raise RuntimeError(
                error.GetCString() or "case-22 Group return instruction failed"
            )
        _require_stopped(process, "case-22 Group return instruction")
        current = _selected_thread(process, thread_id)
        if current.GetFrameAtIndex(0).GetPC() != group_return_pc + 4:
            raise RuntimeError("case-22 Group return successor differs")
        extension["status"] = "instruction-trace-closed"
        _write_trace()
    finally:
        return_breakpoint.SetEnabled(return_was_enabled)


def producer_stage(frame, breakpoint_location, internal_dict):
    result = _group_producer_stage(frame, breakpoint_location, internal_dict)
    extension = _extension()
    try:
        gate = group._extension().get("producerCodeGate")
        if gate is None or frame.GetPC() - gate["symbolStart"] != CASE22_CALL_OFFSET:
            return result
        thread_id = frame.GetThread().GetThreadID()
        stack = group.writer.base._state["groupInvocationStacks"].get(thread_id, [])
        if not stack or stack[-1] is None:
            return result
        invocation_index = stack[-1]
        invocation = group._extension()["invocations"][invocation_index]
        last_stage = invocation["stages"][-1]
        if last_stage.get("discriminatorCase") is not None:
            raise RuntimeError("case-22 call stage unexpectedly carries a discriminator")
        if (
            invocation_index == SELECTED_INVOCATION_INDEX
            and extension["status"] == "initialized"
        ):
            if [stage["instructionOffset"] for stage in invocation["stages"]] != [
                0x0BC,
                0x20C,
                0x268,
            ]:
                raise RuntimeError("selected invocation is not the case-22 path")
            _trace_case22(frame, invocation_index, gate)
    except Exception as error:
        extension["failures"].append(
            {"stage": "case22-callee-trace", "message": str(error)}
        )
        extension["status"] = "instruction-trace-failed"
        group._failure("case22-callee-trace", error)
        _write_trace()
    return result


def finalize():
    _group_finalize()
    extension = _extension()
    if extension is None:
        return
    extension["statusBeforeFinalization"] = extension["status"]
    extension["status"] = "finalized"
    extension["finalInstructionStateCount"] = len(
        extension["instructionStates"]
    )
    extension["finalOpaqueCalleeCount"] = len(extension["opaqueCallees"])
    extension["finalExecutionEventCount"] = len(extension["executionEvents"])
    extension["finalFailureCount"] = len(extension["failures"])
    extension["finalOpaqueCodeByteCount"] = group.writer.base._state.get(
        "case22OpaqueCodeBytes", 0
    )
    _write_trace()


def __lldb_init_module(debugger, internal_dict):
    group.writer.base._state["case22OpaqueCodeBytes"] = 0
    group._new_trace = _new_trace
    group.producer_stage = producer_stage
    group.__lldb_init_module(debugger, internal_dict)
    extension = _extension()
    if extension is not None:
        extension["status"] = "initialized"
        _write_trace()
