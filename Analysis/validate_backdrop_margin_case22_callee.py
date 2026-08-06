#!/usr/bin/env python3
"""Validate the bounded instruction trace of the case-22 margin callee."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import validate_backdrop_margin_group_execution as group
import validate_backdrop_margin_writer_execution as base
import validate_backdrop_margin_writer_execution_retry as writer_retry


VALIDATION_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
TRACE_EXTENSION_SCHEMA_VERSION = 1
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
GENERAL_REGISTER_NAMES = [f"x{index}" for index in range(31)] + [
    "sp",
    "pc",
    "cpsr",
]
SIMD_REGISTER_NAMES = [f"v{index}" for index in range(32)] + ["fpsr", "fpcr"]


def validate_preregistration(value: Any) -> dict[str, Any]:
    prereg = base.mapping(value, "case-22 preregistration")
    if (
        prereg.get("backdropMarginCase22CalleePreregistrationSchemaVersion")
        != PREREGISTRATION_SCHEMA_VERSION
    ):
        raise ValueError("case-22 preregistration schema differs")
    profile = base.mapping(prereg.get("profile"), "case-22 profile")
    if profile != {
        "material": "regular",
        "appearance": "light",
        "direction": "materialize",
        "geometry": "circle-127-center",
        "profilePreviouslyOpened": True,
        "case22TargetAddressPreviouslyOpened": True,
        "case22TargetCodePreviouslyOpened": False,
    }:
        raise ValueError("case-22 preregistration profile differs")
    selection = base.mapping(prereg.get("selection"), "case-22 selection")
    if selection != {
        "groupInvocationIndex": SELECTED_INVOCATION_INDEX,
        "calibratedFromOpenedRunID": 31118243811,
        "ordinalChoiceWasRetrospective": True,
        "openedOrdinalReturnF64": 17.778189659118652,
        "openedOrdinalReturnF64RawLittleEndianHex": "0000007037c73140",
        "runtimeSelector": "fixed structural invocation ordinal only",
        "runtimeSelectionReadsOpenedReturn": False,
        "capturedMarginUsedForRuntimeSelection": False,
        "capturedCropUsedForRuntimeSelection": False,
        "capturedImageUsedForRuntimeSelection": False,
        "capturedPixelUsedForRuntimeSelection": False,
        "prospectiveTransferAuthority": False,
    }:
        raise ValueError("case-22 preregistration selection differs")
    unknown = base.mapping(prereg.get("unknownBeforeCapture"), "case-22 unknowns")
    for key in (
        "targetFunction",
        "targetSymbolBounds",
        "targetCodeBytes",
        "targetCodeSHA256",
        "objectBytes",
        "pointerProbeBytes",
        "instructionSequence",
        "instructionRegisters",
        "instructionStacks",
        "opaqueCalleeIdentities",
        "opaqueCalleeCodeBytes",
        "returnWord",
        "exactArithmetic",
    ):
        if unknown.get(key) is not None:
            raise ValueError(f"case-22 unknown {key} was not sealed")
    acceptance = base.mapping(prereg.get("acceptance"), "case-22 acceptance")
    for key in (
        "requireUnchangedInheritedGroupValidation",
        "requireExactAuthenticatedTargetOffset",
        "requireCompleteTargetSymbolAndCode",
        "requireCompleteSelectedInstructionTrace",
        "requireFullGeneralAndSIMDRegisters",
        "requireBoundedStackAndObjectSnapshots",
        "requireOpaqueCalleeCodeAndBoundaries",
        "requireExactReturnToGroupStage",
        "requireNoValueBasedRuntimeSelection",
        "zeroTolerance",
    ):
        if acceptance.get(key) is not True:
            raise ValueError(f"case-22 acceptance field {key} differs")
    return prereg


def validate_register_snapshot(value: Any, label: str) -> dict[str, int]:
    snapshot = base.mapping(value, label)
    result: dict[str, int] = {}
    for key, names in (
        ("general", GENERAL_REGISTER_NAMES),
        ("simd", SIMD_REGISTER_NAMES),
    ):
        records = base.sequence(snapshot.get(key), f"{label} {key} registers")
        if len(records) != len(names):
            raise ValueError(f"{label} {key} register count differs")
        for index, name in enumerate(names):
            record = base.mapping(records[index], f"{label} {name}")
            byte_count = base.integer(record.get("byteCount"), f"{label} {name} size")
            payload = base.exact_hex(record.get("hex"), byte_count, f"{label} {name}")
            if record.get("name") != name or byte_count <= 0:
                raise ValueError(f"{label} {name} identity differs")
            if byte_count <= 8:
                expected = int.from_bytes(payload, "little")
                if record.get("unsignedValue") != expected:
                    raise ValueError(f"{label} {name} scalar value differs")
                result[name] = expected
            elif "unsignedValue" in record:
                raise ValueError(f"{label} {name} unexpectedly has a scalar value")
            if record.get("valueString") is not None and not isinstance(
                record.get("valueString"), str
            ):
                raise ValueError(f"{label} {name} value string differs")
    return result


def validate_frame(value: Any, label: str) -> dict[str, Any]:
    frame = base.mapping(value, label)
    base.integer(frame.get("frameIndex"), f"{label} index")
    base.integer(frame.get("pc"), f"{label} PC")
    if not isinstance(frame.get("function"), str):
        raise ValueError(f"{label} function differs")
    module = base.mapping(frame.get("module"), f"{label} module")
    if module.get("valid") is not True:
        raise ValueError(f"{label} module is invalid")
    if not isinstance(module.get("path"), str) or not isinstance(
        module.get("uuid"), str
    ):
        raise ValueError(f"{label} module metadata differs")
    base.integer(module.get("loadAddress"), f"{label} module base")
    return dict(frame)


def validate_snapshot(
    value: Any, address: int, byte_count: int, label: str
) -> bytes:
    return group.validate_snapshot(value, address, byte_count, label)


def validate_symbol(
    value: Any,
    label: str,
    expected_selected_address: int | None = None,
    expected_module_offset: int | None = None,
) -> tuple[dict[str, Any], bytes]:
    symbol = base.mapping(value, label)
    selected = base.integer(symbol.get("selectedAddress"), f"{label} address")
    start = base.integer(symbol.get("symbolStart"), f"{label} start")
    end = base.integer(symbol.get("symbolEnd"), f"{label} end")
    byte_count = base.integer(symbol.get("symbolByteCount"), f"{label} size")
    if (
        (expected_selected_address is not None and selected != expected_selected_address)
        or not 0 < byte_count <= MAXIMUM_SYMBOL_BYTE_COUNT
        or end - start != byte_count
        or not start <= selected < end
        or symbol.get("symbolOffset") != selected - start
        or not isinstance(symbol.get("function"), str)
        or not symbol.get("function")
    ):
        raise ValueError(f"{label} identity differs")
    payload = base.exact_hex(symbol.get("hex"), byte_count, f"{label} code")
    if symbol.get("codeSHA256") != hashlib.sha256(payload).hexdigest():
        raise ValueError(f"{label} code hash differs")
    module = base.mapping(symbol.get("module"), f"{label} module")
    if expected_module_offset is not None:
        validated_module = writer_retry.validate_swiftui_module(
            module, f"{label} SwiftUICore module"
        )
        if selected - validated_module["loadAddress"] != expected_module_offset:
            raise ValueError(f"{label} module offset differs")
    elif (
        module.get("valid") is not True
        or not isinstance(module.get("path"), str)
        or not isinstance(module.get("uuid"), str)
        or not isinstance(module.get("loadAddress"), int)
    ):
        raise ValueError(f"{label} module differs")
    return dict(symbol), payload


def register_raw(snapshot: Mapping[str, Any], name: str) -> bytes:
    for group_name in ("general", "simd"):
        for value in base.sequence(snapshot.get(group_name), "registers"):
            record = base.mapping(value, "register")
            if record.get("name") == name:
                byte_count = base.integer(record.get("byteCount"), "register size")
                return base.exact_hex(record.get("hex"), byte_count, "register")
    raise ValueError(f"register {name} is absent")


def validate_pointer_probes(
    value: Any, object_snapshot: Mapping[str, Any], stack_snapshot: Mapping[str, Any]
) -> dict[str, int]:
    probes = base.sequence(value, "pointer probes")
    if len(probes) > MAXIMUM_POINTER_PROBE_COUNT:
        raise ValueError("pointer probe count exceeds the bound")
    sources = {"object": object_snapshot, "stack": stack_snapshot}
    success_count = 0
    failure_count = 0
    addresses: set[int] = set()
    for index, probe_value in enumerate(probes):
        probe = base.mapping(probe_value, f"pointer probe {index}")
        source = probe.get("source")
        if source not in sources:
            raise ValueError("pointer probe source differs")
        offset = base.integer(probe.get("sourceByteOffset"), "pointer probe offset")
        source_payload = bytes.fromhex(str(sources[source]["hex"]))
        address = base.integer(probe.get("address"), "pointer probe address")
        if (
            offset < 0
            or offset + 8 > len(source_payload)
            or offset % 8
            or int.from_bytes(source_payload[offset : offset + 8], "little") != address
            or address in addresses
        ):
            raise ValueError("pointer probe provenance differs")
        addresses.add(address)
        snapshot = probe.get("snapshot")
        failure = probe.get("failure")
        if snapshot is not None and failure is None:
            validate_snapshot(
                snapshot, address, POINTER_PROBE_BYTE_COUNT, "pointer probe snapshot"
            )
            success_count += 1
        elif snapshot is None and isinstance(failure, str) and failure:
            failure_count += 1
        else:
            raise ValueError("pointer probe outcome differs")
    return {
        "pointerProbeCount": len(probes),
        "successfulPointerProbeCount": success_count,
        "failedPointerProbeCount": failure_count,
    }


def validate_trace_extension(
    trace: Mapping[str, Any], inherited: Mapping[str, Any]
) -> dict[str, Any]:
    extension = base.mapping(trace.get("case22CalleeTrace"), "case-22 extension")
    if (
        extension.get("case22CalleeTraceSchemaVersion")
        != TRACE_EXTENSION_SCHEMA_VERSION
        or extension.get("status") != "finalized"
        or extension.get("statusBeforeFinalization") != "instruction-trace-closed"
        or extension.get("failures") != []
        or extension.get("finalFailureCount") != 0
    ):
        raise ValueError("case-22 extension did not finalize cleanly")
    expected_configuration = {
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
        "maximumTotalOpaqueCodeByteCount": MAXIMUM_TOTAL_OPAQUE_CODE_BYTE_COUNT,
        "capturedMarginUsedForRuntimeSelection": False,
        "capturedCropUsedForRuntimeSelection": False,
        "capturedImageUsedForRuntimeSelection": False,
        "capturedPixelUsedForRuntimeSelection": False,
    }
    if base.mapping(extension.get("configuration"), "configuration") != (
        expected_configuration
    ):
        raise ValueError("case-22 configuration differs")
    if extension.get("selectedInvocationIndex") != SELECTED_INVOCATION_INDEX:
        raise ValueError("selected case-22 invocation differs")

    inherited_extension = base.mapping(
        trace.get("groupMarginExecution"), "group execution"
    )
    producer_gate = base.mapping(
        inherited_extension.get("producerCodeGate"), "producer gate"
    )
    group_start = base.integer(producer_gate.get("symbolStart"), "Group start")
    module_base = base.mapping(producer_gate.get("module"), "Group module").get(
        "loadAddress"
    )
    if not isinstance(module_base, int):
        raise ValueError("Group module base differs")
    target_address = module_base + CASE22_TARGET_MODULE_OFFSET

    caller = base.mapping(extension.get("callerCall"), "case-22 caller")
    caller_frame = validate_frame(caller.get("frame"), "case-22 caller frame")
    caller_registers = validate_register_snapshot(
        caller.get("registers"), "case-22 caller registers"
    )
    object_address = base.integer(caller.get("objectAddress"), "object address")
    modifier = base.integer(
        caller.get("authenticatedModifierRaw"), "authenticated modifier"
    )
    if (
        caller.get("instructionOffset") != CASE22_CALL_OFFSET
        or caller.get("instructionHex") != CASE22_INSTRUCTION_HEX
        or caller.get("authenticatedTargetRaw") != target_address
        or caller_frame["pc"] != group_start + CASE22_CALL_OFFSET
        or caller_registers["pc"] != caller_frame["pc"]
        or caller_registers["x28"] != target_address
        or caller_registers["x17"] != modifier
        or caller_registers["x20"] != object_address
        or caller_registers["x0"] != object_address
    ):
        raise ValueError("case-22 caller state differs")

    target, target_code = validate_symbol(
        extension.get("target"),
        "case-22 target",
        target_address,
        CASE22_TARGET_MODULE_OFFSET,
    )
    entry = base.mapping(extension.get("entry"), "case-22 entry")
    entry_frame = validate_frame(entry.get("frame"), "case-22 entry frame")
    entry_registers = validate_register_snapshot(
        entry.get("registers"), "case-22 entry registers"
    )
    if entry_frame["pc"] != target_address or entry_registers["x0"] != object_address:
        raise ValueError("case-22 entry identity differs")
    entry_stack = base.mapping(entry.get("stack"), "case-22 entry stack")
    validate_snapshot(
        entry_stack, entry_registers["sp"], STACK_BYTE_COUNT, "case-22 entry stack"
    )
    entry_object = base.mapping(entry.get("object"), "case-22 entry object")
    validate_snapshot(
        entry_object, object_address, OBJECT_BYTE_COUNT, "case-22 entry object"
    )
    probes = validate_pointer_probes(
        entry.get("pointerProbes"), entry_object, entry_stack
    )

    states = base.sequence(extension.get("instructionStates"), "instruction states")
    boundaries = base.sequence(extension.get("opaqueCallees"), "opaque callees")
    events = base.sequence(extension.get("executionEvents"), "execution events")
    if (
        not 0 < len(states) <= MAXIMUM_INSTRUCTION_COUNT
        or len(boundaries) > MAXIMUM_OPAQUE_CALLEE_COUNT
        or extension.get("finalInstructionStateCount") != len(states)
        or extension.get("finalOpaqueCalleeCount") != len(boundaries)
        or extension.get("finalExecutionEventCount") != len(events)
        or len(events) != len(states) + len(boundaries)
    ):
        raise ValueError("case-22 trace counts differ")

    validated_states = []
    for index, value in enumerate(states):
        state = base.mapping(value, f"instruction state {index}")
        pc = base.integer(state.get("pc"), "instruction PC")
        offset = base.integer(state.get("symbolOffset"), "instruction offset")
        if (
            state.get("stateIndex") != index
            or not target["symbolStart"] <= pc < target["symbolEnd"]
            or offset != pc - target["symbolStart"]
            or state.get("instructionHex") != target_code[offset : offset + 4].hex()
        ):
            raise ValueError(f"instruction state {index} identity differs")
        frame = validate_frame(state.get("frame"), f"instruction state {index} frame")
        registers = validate_register_snapshot(
            state.get("registersBefore"), f"instruction state {index} registers"
        )
        stack = base.mapping(state.get("stackBefore"), "instruction stack")
        validate_snapshot(
            stack, registers["sp"], STACK_BYTE_COUNT, "instruction stack"
        )
        result_frame = validate_frame(
            state.get("resultFrame"), f"instruction state {index} result frame"
        )
        result_pc = base.integer(state.get("resultPC"), "instruction result PC")
        if (
            frame["pc"] != pc
            or registers["pc"] != pc
            or result_frame["pc"] != result_pc
            or state.get("resultFunction") != result_frame["function"]
        ):
            raise ValueError(f"instruction state {index} machine state differs")
        validated_states.append(dict(state))

    opaque_code_bytes = 0
    validated_boundaries = []
    for index, value in enumerate(boundaries):
        boundary = base.mapping(value, f"opaque boundary {index}")
        callee, code = validate_symbol(
            boundary.get("callee"), f"opaque boundary {index} callee"
        )
        opaque_code_bytes += len(code)
        entry_frame_value = validate_frame(
            boundary.get("entryFrame"), f"opaque boundary {index} entry frame"
        )
        entry_register_values = validate_register_snapshot(
            boundary.get("registersAtEntry"),
            f"opaque boundary {index} entry registers",
        )
        validate_snapshot(
            boundary.get("stackAtEntry"),
            entry_register_values["sp"],
            STACK_BYTE_COUNT,
            f"opaque boundary {index} entry stack",
        )
        return_frame_value = validate_frame(
            boundary.get("returnFrame"), f"opaque boundary {index} return frame"
        )
        return_register_values = validate_register_snapshot(
            boundary.get("registersAtReturn"),
            f"opaque boundary {index} return registers",
        )
        validate_snapshot(
            boundary.get("stackAtReturn"),
            return_register_values["sp"],
            STACK_BYTE_COUNT,
            f"opaque boundary {index} return stack",
        )
        if (
            boundary.get("boundaryIndex") != index
            or entry_frame_value["pc"] != callee["selectedAddress"]
            or entry_register_values["pc"] != entry_frame_value["pc"]
            or return_register_values["pc"] != return_frame_value["pc"]
            or not isinstance(boundary.get("expectedReturnFunction"), str)
        ):
            raise ValueError(f"opaque boundary {index} identity differs")
        validated_boundaries.append(dict(boundary))
    if (
        opaque_code_bytes > MAXIMUM_TOTAL_OPAQUE_CODE_BYTE_COUNT
        or extension.get("finalOpaqueCodeByteCount") != opaque_code_bytes
    ):
        raise ValueError("opaque callee code-byte total differs")

    cursor = target_address
    for event_index, value in enumerate(events):
        event = base.mapping(value, f"execution event {event_index}")
        record_index = base.integer(event.get("recordIndex"), "event record index")
        if event.get("kind") == "target-instruction":
            if not 0 <= record_index < len(validated_states):
                raise ValueError("instruction event index differs")
            state = validated_states[record_index]
            if state.get("eventIndex") != event_index or state["pc"] != cursor:
                raise ValueError("instruction event chain differs")
            cursor = state["resultPC"]
        elif event.get("kind") == "opaque-callee":
            if not 0 <= record_index < len(validated_boundaries):
                raise ValueError("opaque event index differs")
            boundary = validated_boundaries[record_index]
            if (
                boundary.get("eventIndex") != event_index
                or boundary["entryFrame"]["pc"] != cursor
            ):
                raise ValueError("opaque event chain differs")
            cursor = boundary["returnFrame"]["pc"]
        else:
            raise ValueError("execution event kind differs")
    group_return_pc = group_start + CASE22_RETURN_OFFSET
    if cursor != group_return_pc:
        raise ValueError("case-22 execution does not end at the Group return site")

    returned = base.mapping(extension.get("return"), "case-22 return")
    return_frame = validate_frame(returned.get("frame"), "case-22 return frame")
    return_registers = validate_register_snapshot(
        returned.get("registers"), "case-22 return registers"
    )
    validate_snapshot(
        returned.get("stack"),
        return_registers["sp"],
        STACK_BYTE_COUNT,
        "case-22 return stack",
    )
    return_object = base.mapping(returned.get("object"), "case-22 return object")
    return_object_payload = validate_snapshot(
        return_object, object_address, OBJECT_BYTE_COUNT, "case-22 return object"
    )
    entry_object_payload = bytes.fromhex(str(entry_object["hex"]))
    object_changed = return_object_payload != entry_object_payload
    if (
        return_frame["pc"] != group_return_pc
        or return_registers["pc"] != group_return_pc
        or returned.get("objectChanged") is not object_changed
    ):
        raise ValueError("case-22 return identity differs")

    invocations = base.sequence(inherited_extension.get("invocations"), "invocations")
    invocation = base.mapping(
        invocations[SELECTED_INVOCATION_INDEX], "selected invocation"
    )
    stages = base.sequence(invocation.get("stages"), "selected invocation stages")
    if [stage.get("instructionOffset") for stage in stages] != [
        0x0BC,
        0x20C,
        0x268,
        0x26C,
        0x278,
        0x2B0,
    ]:
        raise ValueError("selected invocation stage sequence differs")
    case22_return = base.mapping(stages[3], "selected case-22 return stage")
    return_v0 = register_raw(base.mapping(returned.get("registers"), "registers"), "v0")
    stage_v0 = base.exact_hex(
        base.mapping(
            base.mapping(case22_return.get("vectors"), "stage vectors").get("v0"),
            "stage v0",
        ).get("rawLittleEndianHex"),
        16,
        "stage v0",
    )
    if (
        return_v0[:8] != stage_v0[:8]
        or invocation.get("returnF64RawLittleEndianHex") != stage_v0[:8].hex()
        or invocation.get("returnMatchesSetterBitwise") is not True
    ):
        raise ValueError("case-22 return word differs from the inherited chain")

    return {
        "selectedInvocationIndex": SELECTED_INVOCATION_INDEX,
        "targetFunction": target["function"],
        "targetModuleOffset": CASE22_TARGET_MODULE_OFFSET,
        "targetSymbolByteCount": target["symbolByteCount"],
        "targetCodeSHA256": target["codeSHA256"],
        "targetEntryOffset": target["symbolOffset"],
        "instructionStateCount": len(states),
        "opaqueCalleeCount": len(boundaries),
        "executionEventCount": len(events),
        "opaqueCodeByteCount": opaque_code_bytes,
        "returnF64RawLittleEndianHex": stage_v0[:8].hex(),
        "objectChanged": object_changed,
        "completeExecutionChain": True,
        **probes,
    }


def validate(
    trace_path: Path,
    group_preregistration_path: Path,
    case22_preregistration_path: Path,
) -> dict[str, Any]:
    validate_preregistration(
        base.load_json(case22_preregistration_path, "case-22 preregistration")
    )
    inherited = group.validate(trace_path, group_preregistration_path)
    trace = base.mapping(base.load_json(trace_path, "trace"), "trace")
    execution = validate_trace_extension(trace, inherited)
    return {
        "backdropMarginCase22CalleeValidationSchemaVersion": VALIDATION_SCHEMA_VERSION,
        "classification": (
            "retrospective exact instruction diagnostic of one structurally "
            "selected case-22 invocation on an already-opened profile; target "
            "arithmetic may be decoded, but public-input transfer and parity remain open"
        ),
        "conclusion": "success",
        "inputs": {
            "trace": str(trace_path),
            "groupPreregistration": str(group_preregistration_path),
            "case22Preregistration": str(case22_preregistration_path),
        },
        "inheritedGroupValidation": inherited,
        "case22Execution": execution,
        "sealedConclusion": {
            "completeCase22TargetCodeCaptured": True,
            "completeSelectedCase22InstructionTraceCaptured": True,
            "case22ArithmeticMayBeDecodedFromOpenedDiagnostic": True,
            "prospectiveUnseenProfileTransferPassed": False,
            "publicInputMarginLawDecoded": False,
            "independentTemporalInputGenerationPassed": False,
            "physicalOutputTransferPassed": False,
            "independentWalleZeroByteFrameParityPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("group_preregistration", type=Path)
    parser.add_argument("case22_preregistration", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(
        arguments.trace,
        arguments.group_preregistration,
        arguments.case22_preregistration,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
