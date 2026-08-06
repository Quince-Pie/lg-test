"""Trace the exact DesignLibrary provider reached by case-22 on the local host.

The fixed case-22 ordinal and all inherited code gates remain unchanged.  The
already-opened four-byte DesignLibrary dispatch thunk is expanded into a
bounded instruction trace of its exact branch target.  No captured render
value participates in selection or control of the diagnostic.
"""

import hashlib
import struct

import lldb

import capture_backdrop_margin_case22_callee_local_macos_26_6_1_lldb as local


case22 = local.case22
group = local.group
base = local.base

PROVIDER_TRACE_SCHEMA_VERSION = 1
DESIGN_LIBRARY_UUID = "1E980802-69F5-3E69-89EF-50088297FCF5"

THUNK_MODULE_OFFSET = 0xB7F4C
THUNK_FUNCTION = "___lldb_unnamed_symbol_240918f4c"
THUNK_BYTE_COUNT = 4
THUNK_CODE_SHA256 = "a4bd0b217d6f1355f73bffde7d725de4a4b3eaf5d4cd3f3c5915da27bc44add3"
THUNK_INSTRUCTION_HEX = "5afcff17"
THUNK_BRANCH_DISPLACEMENT = -3736

PROVIDER_MODULE_OFFSET = 0xB70B4
PROVIDER_FUNCTION = "___lldb_unnamed_symbol_2409180b4"
PROVIDER_BYTE_COUNT = 984
PROVIDER_CODE_SHA256 = (
    "a76c6f0b03cc6b64c6b040220f495c5f22d7e1e5322efb3cb139554dd397c10b"
)
PROVIDER_OBJECT_BYTE_COUNT = 0x180
PROVIDER_RETURN_TO_WRAPPER_OFFSET = 0x68

HELPER_MODULE_OFFSET = 0xC682C
HELPER_FUNCTION = "___lldb_unnamed_symbol_24092782c"
HELPER_BYTE_COUNT = 276
HELPER_CODE_SHA256 = "f58da9879a4b367144e8acaf1ad099161b3e27f00e0769dd4fa6e18e9ef9edc1"

MAXIMUM_PROVIDER_INSTRUCTION_COUNT = 512
MAXIMUM_PROVIDER_HELPER_COUNT = 8
MAXIMUM_PROVIDER_HELPER_CODE_BYTE_COUNT = 4096

_local_new_trace = local._new_trace
_case22_capture_opaque_callee = case22._capture_opaque_callee


def _extension():
    trace = base._state.get("trace")
    if trace is None:
        return None
    return trace.get("case22ProviderTrace")


def _write_trace():
    case22._write_trace()


def _new_trace():
    trace = _local_new_trace()
    trace["classification"] = (
        "output-blind nested instruction diagnostic of the exact DesignLibrary "
        "provider reached by the already-opened case-22 ordinal; no public-input "
        "transfer, optical, physical-output, production, or parity authority"
    )
    trace["case22ProviderTrace"] = {
        "case22ProviderTraceSchemaVersion": PROVIDER_TRACE_SCHEMA_VERSION,
        "status": "initialized",
        "configuration": {
            "selection": (
                "the exact four-byte DesignLibrary thunk reached by the frozen "
                "case-22 ordinal and authenticated SwiftUI wrapper"
            ),
            "designLibraryUUID": DESIGN_LIBRARY_UUID,
            "thunkModuleOffset": THUNK_MODULE_OFFSET,
            "thunkFunction": THUNK_FUNCTION,
            "thunkByteCount": THUNK_BYTE_COUNT,
            "thunkCodeSHA256": THUNK_CODE_SHA256,
            "thunkInstructionHex": THUNK_INSTRUCTION_HEX,
            "thunkBranchDisplacement": THUNK_BRANCH_DISPLACEMENT,
            "providerModuleOffset": PROVIDER_MODULE_OFFSET,
            "providerFunction": PROVIDER_FUNCTION,
            "providerByteCount": PROVIDER_BYTE_COUNT,
            "providerCodeSHA256": PROVIDER_CODE_SHA256,
            "providerObjectByteCount": PROVIDER_OBJECT_BYTE_COUNT,
            "providerReturnToWrapperOffset": (PROVIDER_RETURN_TO_WRAPPER_OFFSET),
            "helperModuleOffset": HELPER_MODULE_OFFSET,
            "helperFunction": HELPER_FUNCTION,
            "helperByteCount": HELPER_BYTE_COUNT,
            "helperCodeSHA256": HELPER_CODE_SHA256,
            "maximumProviderInstructionCount": (MAXIMUM_PROVIDER_INSTRUCTION_COUNT),
            "maximumProviderHelperCount": MAXIMUM_PROVIDER_HELPER_COUNT,
            "maximumProviderHelperCodeByteCount": (
                MAXIMUM_PROVIDER_HELPER_CODE_BYTE_COUNT
            ),
            "capturedMarginUsedForRuntimeSelection": False,
            "capturedCropUsedForRuntimeSelection": False,
            "capturedImageUsedForRuntimeSelection": False,
            "capturedPixelUsedForRuntimeSelection": False,
        },
        "dispatchThunk": {},
        "provider": {},
        "entry": {},
        "instructionStates": [],
        "helperCallees": [],
        "executionEvents": [],
        "return": {},
        "failures": [],
    }
    return trace


def _require_design_module(module, label):
    if (
        module.get("valid") is not True
        or module.get("uuid") != DESIGN_LIBRARY_UUID
        or not str(module.get("path", "")).endswith("/DesignLibrary")
        or not isinstance(module.get("loadAddress"), int)
        or module["loadAddress"] <= 0
    ):
        raise RuntimeError(label + " DesignLibrary identity differs")
    return module


def _capture_design_symbol(
    process,
    address,
    label,
    module_offset,
    function,
    byte_count,
    code_sha256,
):
    target = process.GetTarget()
    resolved = target.ResolveLoadAddress(address)
    if not resolved.IsValid():
        raise RuntimeError(label + " address is unresolved")
    module = _require_design_module(
        base._module_record(resolved.GetModule(), target), label
    )
    symbol = resolved.GetSymbol()
    if not symbol.IsValid():
        raise RuntimeError(label + " symbol is unresolved")
    start = symbol.GetStartAddress().GetLoadAddress(target)
    end = symbol.GetEndAddress().GetLoadAddress(target)
    if (
        address - module["loadAddress"] != module_offset
        or (symbol.GetName() or "") != function
        or start != address
        or end - start != byte_count
    ):
        raise RuntimeError(label + " exact symbol identity differs")
    payload = base._read_memory(process, start, byte_count, label + " code")
    digest = hashlib.sha256(payload).hexdigest()
    if digest != code_sha256:
        raise RuntimeError(label + " complete-code SHA-256 differs")
    return {
        "selectedAddress": address,
        "function": function,
        "symbolStart": start,
        "symbolEnd": end,
        "symbolOffset": 0,
        "symbolByteCount": byte_count,
        "codeSHA256": digest,
        "hex": payload.hex(),
        "module": module,
    }


def _require_dispatch_thunk(identity):
    module = _require_design_module(identity.get("module", {}), "dispatch thunk")
    if (
        identity.get("function") != THUNK_FUNCTION
        or identity.get("selectedAddress") - module["loadAddress"]
        != THUNK_MODULE_OFFSET
        or identity.get("symbolByteCount") != THUNK_BYTE_COUNT
        or identity.get("symbolOffset") != 0
        or identity.get("codeSHA256") != THUNK_CODE_SHA256
        or identity.get("hex") != THUNK_INSTRUCTION_HEX
    ):
        raise RuntimeError("case-22 DesignLibrary dispatch thunk differs")
    return module


def _decode_thunk_target(identity):
    payload = bytes.fromhex(identity["hex"])
    word = struct.unpack("<I", payload)[0]
    if word & 0xFC000000 != 0x14000000:
        raise RuntimeError("DesignLibrary dispatch thunk is not B")
    displacement = word & 0x03FFFFFF
    if displacement & 0x02000000:
        displacement -= 0x04000000
    byte_displacement = displacement * 4
    if byte_displacement != THUNK_BRANCH_DISPLACEMENT:
        raise RuntimeError("DesignLibrary thunk displacement differs")
    return identity["selectedAddress"] + byte_displacement


def _capture_provider_instruction(process, frame, provider):
    extension = _extension()
    states = extension["instructionStates"]
    if len(states) >= MAXIMUM_PROVIDER_INSTRUCTION_COUNT:
        raise RuntimeError("provider instruction bound exceeded")
    pc = frame.GetPC()
    if not provider["symbolStart"] <= pc < provider["symbolEnd"]:
        raise RuntimeError("provider instruction is outside the symbol")
    instruction = base._read_memory(process, pc, 4, "provider instruction")
    registers = case22._full_register_snapshot(frame)
    state = {
        "stateIndex": len(states),
        "eventIndex": len(extension["executionEvents"]),
        "pc": pc,
        "symbolOffset": pc - provider["symbolStart"],
        "instructionHex": instruction.hex(),
        "frame": case22._frame_record(frame),
        "registersBefore": registers,
        "stackBefore": case22._snapshot(
            process,
            case22._register_value(registers, "sp"),
            case22.STACK_BYTE_COUNT,
            "provider instruction stack",
        ),
    }
    thread = frame.GetThread()
    thread_id = thread.GetThreadID()
    error = lldb.SBError()
    thread.StepInstruction(False, error)
    if not error.Success():
        raise RuntimeError(error.GetCString() or "provider instruction step failed")
    case22._require_stopped(process, "provider instruction")
    current = case22._selected_thread(process, thread_id)
    result_frame = current.GetFrameAtIndex(0)
    state.update(
        {
            "resultPC": result_frame.GetPC(),
            "resultFunction": result_frame.GetFunctionName() or "",
            "resultFrame": case22._frame_record(result_frame),
        }
    )
    states.append(state)
    extension["executionEvents"].append(
        {"kind": "provider-instruction", "recordIndex": state["stateIndex"]}
    )
    if len(states) % 32 == 0:
        _write_trace()
    return current, result_frame


def _capture_provider_helper(process, thread, frame, provider_function):
    extension = _extension()
    boundaries = extension["helperCallees"]
    if len(boundaries) >= MAXIMUM_PROVIDER_HELPER_COUNT:
        raise RuntimeError("provider helper bound exceeded")
    identity = _capture_design_symbol(
        process,
        frame.GetPC(),
        "provider helper",
        HELPER_MODULE_OFFSET,
        HELPER_FUNCTION,
        HELPER_BYTE_COUNT,
        HELPER_CODE_SHA256,
    )
    previous_bytes = sum(
        boundary["callee"]["symbolByteCount"] for boundary in boundaries
    )
    if previous_bytes + HELPER_BYTE_COUNT > MAXIMUM_PROVIDER_HELPER_CODE_BYTE_COUNT:
        raise RuntimeError("provider helper code-byte bound exceeded")
    registers = case22._full_register_snapshot(frame)
    boundary = {
        "boundaryIndex": len(boundaries),
        "eventIndex": len(extension["executionEvents"]),
        "expectedReturnFunction": provider_function,
        "callee": identity,
        "entryFrame": case22._frame_record(frame),
        "registersAtEntry": registers,
        "stackAtEntry": case22._snapshot(
            process,
            case22._register_value(registers, "sp"),
            case22.STACK_BYTE_COUNT,
            "provider helper entry stack",
        ),
    }
    thread_id = thread.GetThreadID()
    error = lldb.SBError()
    thread.StepOut(error)
    if not error.Success():
        raise RuntimeError(error.GetCString() or "provider helper step-out failed")
    case22._require_stopped(process, "provider helper")
    current = case22._selected_thread(process, thread_id)
    return_frame = current.GetFrameAtIndex(0)
    return_registers = case22._full_register_snapshot(return_frame)
    boundary.update(
        {
            "returnFrame": case22._frame_record(return_frame),
            "registersAtReturn": return_registers,
            "stackAtReturn": case22._snapshot(
                process,
                case22._register_value(return_registers, "sp"),
                case22.STACK_BYTE_COUNT,
                "provider helper return stack",
            ),
        }
    )
    boundaries.append(boundary)
    extension["executionEvents"].append(
        {"kind": "provider-helper", "recordIndex": boundary["boundaryIndex"]}
    )
    return current, return_frame


def _trace_provider(process, thread, frame, thunk_identity):
    extension = _extension()
    target_address = _decode_thunk_target(thunk_identity)
    module = _require_design_module(thunk_identity["module"], "dispatch thunk")
    if target_address - module["loadAddress"] != PROVIDER_MODULE_OFFSET:
        raise RuntimeError("DesignLibrary provider target offset differs")
    extension["status"] = "provider-trace-active"
    extension["dispatchThunk"] = thunk_identity
    _write_trace()

    thread_id = thread.GetThreadID()
    error = lldb.SBError()
    thread.StepInstruction(False, error)
    if not error.Success():
        raise RuntimeError(error.GetCString() or "provider thunk step failed")
    case22._require_stopped(process, "provider entry")
    current = case22._selected_thread(process, thread_id)
    provider_frame = current.GetFrameAtIndex(0)
    if provider_frame.GetPC() != target_address:
        raise RuntimeError("DesignLibrary provider branch target differs")
    provider = _capture_design_symbol(
        process,
        target_address,
        "case-22 provider",
        PROVIDER_MODULE_OFFSET,
        PROVIDER_FUNCTION,
        PROVIDER_BYTE_COUNT,
        PROVIDER_CODE_SHA256,
    )
    extension["provider"] = provider
    entry_registers = case22._full_register_snapshot(provider_frame)
    provider_object = case22._register_value(entry_registers, "x20")
    extension["entry"] = {
        "frame": case22._frame_record(provider_frame),
        "registers": entry_registers,
        "stack": case22._snapshot(
            process,
            case22._register_value(entry_registers, "sp"),
            case22.STACK_BYTE_COUNT,
            "provider entry stack",
        ),
        "object": case22._snapshot(
            process,
            provider_object,
            PROVIDER_OBJECT_BYTE_COUNT,
            "provider object",
        ),
    }
    wrapper = case22._extension()["target"]
    wrapper_return_pc = wrapper["symbolStart"] + PROVIDER_RETURN_TO_WRAPPER_OFFSET

    while len(extension["instructionStates"]) < MAXIMUM_PROVIDER_INSTRUCTION_COUNT:
        current = case22._selected_thread(process, thread_id)
        current_frame = current.GetFrameAtIndex(0)
        pc = current_frame.GetPC()
        if provider["symbolStart"] <= pc < provider["symbolEnd"]:
            _capture_provider_instruction(process, current_frame, provider)
            continue
        if pc == wrapper_return_pc:
            break
        _capture_provider_helper(process, current, current_frame, provider["function"])
    else:
        raise RuntimeError("provider instruction bound exceeded")

    return_thread = case22._selected_thread(process, thread_id)
    return_frame = return_thread.GetFrameAtIndex(0)
    if return_frame.GetPC() != wrapper_return_pc:
        raise RuntimeError("provider did not return to the SwiftUI wrapper")
    return_registers = case22._full_register_snapshot(return_frame)
    return_object = case22._snapshot(
        process,
        provider_object,
        PROVIDER_OBJECT_BYTE_COUNT,
        "provider return object",
    )
    extension["return"] = {
        "frame": case22._frame_record(return_frame),
        "registers": return_registers,
        "stack": case22._snapshot(
            process,
            case22._register_value(return_registers, "sp"),
            case22.STACK_BYTE_COUNT,
            "provider return stack",
        ),
        "object": return_object,
        "objectChanged": return_object["hex"] != extension["entry"]["object"]["hex"],
    }
    extension["status"] = "provider-trace-closed"
    _write_trace()
    return return_thread, return_frame


def _capture_provider_dispatch(process, thread, frame, expected_target_function):
    extension = _extension()
    try:
        target = process.GetTarget()
        resolved = target.ResolveLoadAddress(frame.GetPC())
        module = (
            base._module_record(resolved.GetModule(), target)
            if resolved.IsValid()
            else {"valid": False}
        )
        if (
            module.get("uuid") != DESIGN_LIBRARY_UUID
            or frame.GetPC() - module.get("loadAddress", 0) != THUNK_MODULE_OFFSET
        ):
            return _case22_capture_opaque_callee(
                process, thread, frame, expected_target_function
            )

        outer_extension = case22._extension()
        boundaries = outer_extension["opaqueCallees"]
        if len(boundaries) >= case22.MAXIMUM_OPAQUE_CALLEE_COUNT:
            raise RuntimeError("case-22 opaque-callee bound exceeded")
        identity = case22._capture_symbol(
            process, frame.GetPC(), "case-22 provider dispatch thunk"
        )
        _require_dispatch_thunk(identity)
        previous_code_bytes = base._state["case22OpaqueCodeBytes"]
        if previous_code_bytes + THUNK_BYTE_COUNT > (
            case22.MAXIMUM_TOTAL_OPAQUE_CODE_BYTE_COUNT
        ):
            raise RuntimeError("case-22 opaque code-byte total exceeded")
        base._state["case22OpaqueCodeBytes"] = previous_code_bytes + THUNK_BYTE_COUNT
        entry_registers = case22._full_register_snapshot(frame)
        boundary = {
            "boundaryIndex": len(boundaries),
            "eventIndex": len(outer_extension["executionEvents"]),
            "expectedReturnFunction": expected_target_function,
            "callee": identity,
            "entryFrame": case22._frame_record(frame),
            "registersAtEntry": entry_registers,
            "stackAtEntry": case22._snapshot(
                process,
                case22._register_value(entry_registers, "sp"),
                case22.STACK_BYTE_COUNT,
                "case-22 provider dispatch entry stack",
            ),
        }
        current, return_frame = _trace_provider(process, thread, frame, identity)
        return_registers = case22._full_register_snapshot(return_frame)
        boundary.update(
            {
                "returnFrame": case22._frame_record(return_frame),
                "registersAtReturn": return_registers,
                "stackAtReturn": case22._snapshot(
                    process,
                    case22._register_value(return_registers, "sp"),
                    case22.STACK_BYTE_COUNT,
                    "case-22 provider dispatch return stack",
                ),
            }
        )
        boundaries.append(boundary)
        outer_extension["executionEvents"].append(
            {"kind": "opaque-callee", "recordIndex": boundary["boundaryIndex"]}
        )
        return current, return_frame
    except Exception as error:
        if extension is not None:
            extension["failures"].append(
                {"stage": "case22-provider-trace", "message": str(error)}
            )
            extension["status"] = "provider-trace-failed"
            _write_trace()
        raise


def trace_selected_case22():
    return local.trace_selected_case22()


def finalize():
    local.finalize()
    extension = _extension()
    if extension is None:
        return
    extension["statusBeforeFinalization"] = extension["status"]
    extension["status"] = "finalized"
    extension["finalInstructionStateCount"] = len(extension["instructionStates"])
    extension["finalHelperCalleeCount"] = len(extension["helperCallees"])
    extension["finalExecutionEventCount"] = len(extension["executionEvents"])
    extension["finalFailureCount"] = len(extension["failures"])
    extension["finalHelperCodeByteCount"] = sum(
        boundary["callee"]["symbolByteCount"] for boundary in extension["helperCallees"]
    )
    _write_trace()


def __lldb_init_module(debugger, internal_dict):
    local._new_trace = _new_trace
    case22._capture_opaque_callee = _capture_provider_dispatch
    local.__lldb_init_module(debugger, internal_dict)
