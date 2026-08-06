"""Open the SDF map-bounds call preceding the frozen FilterOp trace.

The regular-material FilterOp diagnostic already authenticates the first four
dynamic map-bounds dispatches without reading their rectangle values.  This
adapter keeps that selector and the complete FilterOp capture unchanged, but
records every instruction in the second dispatch (``SDFOp::map_bounds``).

The SDF code hash is deliberately discovered, not predicted, in this run.
Accordingly this is an arithmetic diagnostic and cannot establish transfer or
product parity.  LLDB imports this module with macOS system Python, so it
avoids syntax newer than that runtime.
"""

import hashlib

import lldb

import capture_prepare_layer_filter_map_bounds_regular_lldb as regular


frozen = regular.frozen
producer_base = frozen.producer_base
base = frozen.base
capture_base = frozen.capture_base
crop_base = frozen.crop_base

DIAGNOSTIC_SCHEMA_VERSION = 1
SDF_FUNCTION = (
    "CA::Render::Updater::SDFOp::map_bounds(CA::Render::Updater::LayerShapes&, bool)"
)
SDF_RELATIVE_TO_PREPARE_LAYER = -56012
SDF_SYMBOL_BYTE_COUNT = 160
SDF_DISPATCH_ORDINAL = 2
SDF_OBJECT_BYTE_COUNT = 0x200
SDF_ARGUMENT_BYTE_COUNT = 0x200
MAXIMUM_SDF_INSTRUCTION_COUNT = 256
MAXIMUM_SDF_OPAQUE_CALLEE_COUNT = 64


def _new_diagnostic():
    return {
        "prepareLayerSDFMapBoundsDiagnosticSchemaVersion": (DIAGNOSTIC_SCHEMA_VERSION),
        "classification": (
            "prospective output-blind instruction diagnostic of the second "
            "authenticated dynamic map-bounds dispatch; SDF code bytes and "
            "arithmetic are discovered while all parity authority remains closed"
        ),
        "status": "initialized",
        "configuration": {
            "material": "regular",
            "appearance": "light",
            "direction": "materialize",
            "geometry": regular.EXPECTED_GEOMETRY,
            "selectedSampleIndex": 2,
            "selectedMarkerInterval": base.TARGET_MARKER_INTERVAL,
            "selectedQualifiedHelperOrdinal": regular.selected_base._target_ordinal,
            "dynamicCallOffset": frozen.DYNAMIC_CALL_OFFSET,
            "dynamicReturnOffset": frozen.DYNAMIC_RETURN_OFFSET,
            "dispatchOrdinal": SDF_DISPATCH_ORDINAL,
            "function": SDF_FUNCTION,
            "relativeToPrepareLayer": SDF_RELATIVE_TO_PREPARE_LAYER,
            "symbolByteCount": SDF_SYMBOL_BYTE_COUNT,
            "expectedCodeSHA256": None,
            "objectByteCount": SDF_OBJECT_BYTE_COUNT,
            "argumentByteCount": SDF_ARGUMENT_BYTE_COUNT,
            "maximumInstructionCount": MAXIMUM_SDF_INSTRUCTION_COUNT,
            "maximumOpaqueCalleeCount": MAXIMUM_SDF_OPAQUE_CALLEE_COUNT,
            "cropValuesUsedForSelection": False,
            "outputValuesUsedForSelection": False,
            "filterCaptureChanged": False,
        },
        "target": {},
        "entry": {},
        "instructionStates": [],
        "opaqueCalleeBoundaries": [],
        "executionEvents": [],
        "return": {},
        "opaqueBoundaryIndex": None,
        "failures": [],
    }


def _diagnostic():
    extension = frozen._extension_trace()
    if extension is None:
        return None
    return extension.get("sdfMapBoundsDiagnostic")


def _write_trace():
    frozen._write_trace()


def _memory_record(address, payload):
    return producer_base._memory_record(address, payload)


def _capture_identity(process, frame, prepare_start):
    target = process.GetTarget()
    entry_pc = frame.GetPC()
    expected_start = prepare_start + SDF_RELATIVE_TO_PREPARE_LAYER
    resolved = target.ResolveLoadAddress(entry_pc)
    symbol = resolved.GetSymbol()
    if not symbol.IsValid():
        raise RuntimeError("SDFOp symbol is invalid")
    start = symbol.GetStartAddress().GetLoadAddress(target)
    end = symbol.GetEndAddress().GetLoadAddress(target)
    if (
        entry_pc != expected_start
        or start != expected_start
        or end - start != SDF_SYMBOL_BYTE_COUNT
        or frame.GetFunctionName() != SDF_FUNCTION
    ):
        raise RuntimeError("SDFOp symbol identity differs")
    code = capture_base._read_memory(process, start, end - start, "SDFOp complete code")
    return {
        "function": frame.GetFunctionName(),
        "symbolName": symbol.GetName(),
        "relativeToPrepareLayer": entry_pc - prepare_start,
        "entryPC": entry_pc,
        "symbolStart": start,
        "symbolEnd": end,
        "symbolByteCount": len(code),
        "expectedSHA256": None,
        "observedSHA256": hashlib.sha256(code).hexdigest(),
        "hex": code.hex(),
        "module": base._module_record(resolved.GetModule(), target),
    }


def _trace_sdf_instruction(thread, frame, symbol_start):
    process = thread.GetProcess()
    diagnostic = _diagnostic()
    states = diagnostic["instructionStates"]
    if len(states) >= MAXIMUM_SDF_INSTRUCTION_COUNT:
        raise RuntimeError("SDFOp instruction bound exceeded")
    registers = capture_base._full_register_snapshot(frame)
    values = base._full_register_values(registers)
    output_before = producer_base._output_bytes(process)
    role_before = producer_base._role_bytes(process)
    state = {
        "stateIndex": len(states),
        "instruction": producer_base._instruction_record(
            frame, "sdfMapBounds", symbol_start
        ),
        "registersBefore": registers,
        "stackBefore": base._snapshot(
            process,
            values["sp"],
            frozen.STACK_BYTE_COUNT,
            "SDFOp instruction stack",
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
        raise RuntimeError(error.GetCString() or "SDFOp instruction step failed")
    base._require_stopped(process, "SDFOp instruction")
    current = base._selected_thread(process)
    result_frame = current.GetFrameAtIndex(0)
    return_registers = capture_base._full_register_snapshot(result_frame)
    return_values = base._full_register_values(return_registers)
    output_after = producer_base._output_bytes(process)
    role_after = producer_base._role_bytes(process)
    state.update(
        {
            "resultPC": result_frame.GetPC(),
            "resultFunction": result_frame.GetFunctionName(),
            "registersAfter": return_registers,
            "stackAfter": base._snapshot(
                process,
                return_values["sp"],
                frozen.STACK_BYTE_COUNT,
                "SDFOp instruction result stack",
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
    diagnostic["executionEvents"].append(
        {"kind": "sdf-instruction", "recordIndex": state["stateIndex"]}
    )
    if len(states) % frozen.TRACE_CHECKPOINT_INSTRUCTION_INTERVAL == 0:
        _write_trace()
    return current, result_frame


def _capture_opaque_identity(process, frame):
    target = process.GetTarget()
    resolved = target.ResolveLoadAddress(frame.GetPC())
    symbol = resolved.GetSymbol()
    if not symbol.IsValid():
        raise RuntimeError("SDFOp opaque callee symbol is invalid")
    start = symbol.GetStartAddress().GetLoadAddress(target)
    end = symbol.GetEndAddress().GetLoadAddress(target)
    if not start <= frame.GetPC() < end or not 0 < end - start <= 0x10000:
        raise RuntimeError("SDFOp opaque callee range differs")
    code = capture_base._read_memory(
        process, start, end - start, "SDFOp opaque callee complete code"
    )
    function_name = frame.GetFunctionName()
    symbol_name = symbol.GetName()
    if not function_name and not symbol_name:
        raise RuntimeError("SDFOp opaque callee name is absent")
    return {
        "function": function_name or symbol_name,
        "symbolName": symbol_name,
        "entryPC": frame.GetPC(),
        "entryOffset": frame.GetPC() - start,
        "symbolStart": start,
        "symbolEnd": end,
        "symbolByteCount": len(code),
        "expectedSHA256": None,
        "observedSHA256": hashlib.sha256(code).hexdigest(),
        "hex": code.hex(),
        "module": base._module_record(resolved.GetModule(), target),
    }


def _trace_sdf_opaque_callee(thread, frame):
    process = thread.GetProcess()
    diagnostic = _diagnostic()
    boundaries = diagnostic["opaqueCalleeBoundaries"]
    if len(boundaries) >= MAXIMUM_SDF_OPAQUE_CALLEE_COUNT:
        raise RuntimeError("SDFOp opaque callee bound exceeded")
    registers = capture_base._full_register_snapshot(frame)
    values = base._full_register_values(registers)
    output_before = producer_base._output_bytes(process)
    role_before = producer_base._role_bytes(process)
    boundary = {
        "boundaryIndex": len(boundaries),
        "expectedReturnFunction": SDF_FUNCTION,
        "callee": _capture_opaque_identity(process, frame),
        "entryFrame": capture_base._frame_record(frame, process.GetTarget()),
        "registersAtEntry": registers,
        "stackAtEntry": base._snapshot(
            process,
            values["sp"],
            frozen.STACK_BYTE_COUNT,
            "SDFOp opaque callee entry stack",
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
        raise RuntimeError(error.GetCString() or "SDFOp opaque step-out failed")
    base._require_stopped(process, "SDFOp opaque callee")
    current = base._selected_thread(process)
    result_frame = current.GetFrameAtIndex(0)
    return_registers = capture_base._full_register_snapshot(result_frame)
    return_values = base._full_register_values(return_registers)
    output_after = producer_base._output_bytes(process)
    role_after = producer_base._role_bytes(process)
    boundary.update(
        {
            "returnFrame": capture_base._frame_record(
                result_frame, process.GetTarget()
            ),
            "registersAtReturn": return_registers,
            "stackAtReturn": base._snapshot(
                process,
                return_values["sp"],
                frozen.STACK_BYTE_COUNT,
                "SDFOp opaque callee return stack",
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
    if result_frame.GetFunctionName() != SDF_FUNCTION:
        raise RuntimeError("SDFOp opaque callee return differs")
    boundaries.append(boundary)
    diagnostic["executionEvents"].append(
        {"kind": "opaque-callee", "recordIndex": boundary["boundaryIndex"]}
    )
    return current, result_frame


def _trace_sdf_boundary(thread, frame, expected_return_function):
    process = thread.GetProcess()
    extension = frozen._extension_trace()
    diagnostic = _diagnostic()
    prepare_start = crop_base._state["prepareLayer"]["symbolStart"]
    target = _capture_identity(process, frame, prepare_start)
    diagnostic["target"] = target

    entry_registers = capture_base._full_register_snapshot(frame)
    entry_values = base._full_register_values(entry_registers)
    output_address = base._state["selected"]["outputAddress"]
    role_base = base._state["selected"]["callerRoleBase"]
    if entry_values["x1"] != output_address or entry_values["x2"] not in (0, 1):
        raise RuntimeError("SDFOp entry arguments differ")
    output_before = producer_base._output_bytes(process)
    role_before = producer_base._role_bytes(process)
    diagnostic["entry"] = {
        "frame": capture_base._frame_record(frame, process.GetTarget()),
        "registers": entry_registers,
        "stack": base._snapshot(
            process,
            entry_values["sp"],
            frozen.STACK_BYTE_COUNT,
            "SDFOp entry stack",
        ),
        "object": base._snapshot(
            process,
            entry_values["x0"],
            SDF_OBJECT_BYTE_COUNT,
            "SDFOp object",
        ),
        "argumentX3": base._snapshot(
            process,
            entry_values["x3"],
            SDF_ARGUMENT_BYTE_COUNT,
            "SDFOp x3 argument",
        ),
        "output": _memory_record(output_address, output_before),
        "callerRole": _memory_record(role_base, role_before),
    }
    boundary = {
        "boundaryIndex": len(extension["opaqueCalleeBoundaries"]),
        "expectedReturnFunction": expected_return_function,
        "entryFrame": diagnostic["entry"]["frame"],
        "registersAtEntry": entry_registers,
        "stackAtEntry": diagnostic["entry"]["stack"],
        "outputBefore": diagnostic["entry"]["output"],
        "callerRoleBefore": diagnostic["entry"]["callerRole"],
    }
    diagnostic["status"] = "sdf-instruction-trace-active"
    symbol_start = target["symbolStart"]
    symbol_end = target["symbolEnd"]
    while len(diagnostic["instructionStates"]) < MAXIMUM_SDF_INSTRUCTION_COUNT:
        current = base._selected_thread(process)
        current_frame = current.GetFrameAtIndex(0)
        pc = current_frame.GetPC()
        if symbol_start <= pc < symbol_end:
            thread, frame = _trace_sdf_instruction(current, current_frame, symbol_start)
            continue
        if current_frame.GetFunctionName() == crop_base.PREPARE_LAYER_FUNCTION:
            break
        thread, frame = _trace_sdf_opaque_callee(current, current_frame)
    else:
        raise RuntimeError("SDFOp instruction bound exceeded")

    return_thread = base._selected_thread(process)
    return_frame = return_thread.GetFrameAtIndex(0)
    return_registers = capture_base._full_register_snapshot(return_frame)
    return_values = base._full_register_values(return_registers)
    if (
        return_frame.GetFunctionName() != expected_return_function
        or return_frame.GetPC() != prepare_start + frozen.DYNAMIC_RETURN_OFFSET
        or return_values["x19"] != role_base
    ):
        raise RuntimeError("SDFOp return identity differs")
    output_after = producer_base._output_bytes(process)
    role_after = producer_base._role_bytes(process)
    diagnostic["return"] = {
        "frame": capture_base._frame_record(return_frame, process.GetTarget()),
        "registers": return_registers,
        "stack": base._snapshot(
            process,
            return_values["sp"],
            frozen.STACK_BYTE_COUNT,
            "SDFOp return stack",
        ),
        "output": _memory_record(output_address, output_after),
        "callerRole": _memory_record(role_base, role_after),
    }
    boundary.update(
        {
            "returnFrame": diagnostic["return"]["frame"],
            "registersAtReturn": return_registers,
            "stackAtReturn": diagnostic["return"]["stack"],
            "outputAfter": diagnostic["return"]["output"],
            "callerRoleAfter": diagnostic["return"]["callerRole"],
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
    extension["opaqueCalleeBoundaries"].append(boundary)
    extension["executionEvents"].append(
        {"kind": "opaque-callee", "recordIndex": boundary["boundaryIndex"]}
    )
    diagnostic["opaqueBoundaryIndex"] = boundary["boundaryIndex"]
    diagnostic["status"] = "sdf-instruction-trace-closed"
    _write_trace()
    return return_thread, return_frame


def trace_selected_sdf_filter_map_bounds():
    diagnostic = _diagnostic()
    if diagnostic is None:
        return
    original = producer_base._trace_opaque_callee

    def trace_or_delegate(thread, frame, expected_return_function):
        if (
            frame.GetFunctionName() == SDF_FUNCTION
            and diagnostic["status"] == "initialized"
        ):
            try:
                return _trace_sdf_boundary(thread, frame, expected_return_function)
            except Exception as error:
                diagnostic["failures"].append(
                    {"stage": "sdf-instruction-trace", "message": str(error)}
                )
                diagnostic["status"] = "sdf-instruction-trace-failed"
                _write_trace()
                raise
        return original(thread, frame, expected_return_function)

    producer_base._trace_opaque_callee = trace_or_delegate
    try:
        return regular.trace_selected_filter_map_bounds()
    finally:
        producer_base._trace_opaque_callee = original


def finalize():
    diagnostic = _diagnostic()
    if diagnostic is not None:
        diagnostic["statusBeforeFinalization"] = diagnostic["status"]
        diagnostic["status"] = "finalized"
        diagnostic["finalInstructionStateCount"] = len(diagnostic["instructionStates"])
        diagnostic["finalOpaqueCalleeBoundaryCount"] = len(
            diagnostic["opaqueCalleeBoundaries"]
        )
        diagnostic["finalExecutionEventCount"] = len(diagnostic["executionEvents"])
        diagnostic["finalFailureCount"] = len(diagnostic["failures"])
    regular.finalize()
    _write_trace()


def __lldb_init_module(debugger, internal_dict):
    regular.__lldb_init_module(debugger, internal_dict)
    extension = frozen._extension_trace()
    if extension is None:
        return
    extension["sdfMapBoundsDiagnostic"] = _new_diagnostic()
    _write_trace()
