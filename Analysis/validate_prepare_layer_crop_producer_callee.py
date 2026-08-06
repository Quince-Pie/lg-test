#!/usr/bin/env python3
"""Validate the structurally selected post-mask crop-producer callee trace."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import analyze_prepare_layer_crop_policy_holdout_callback_retry as holdout_analysis
import analyze_prepare_layer_crop_union_operand_matrix as crop_analysis
import validate_prepare_layer_crop_transfer as crop_validator
import validate_prepare_layer_mask_instruction_trace as trace_validator
import validate_prepare_layer_mask_inventory_selected_trace as selected_validator


VALIDATION_SCHEMA_VERSION = 1
EXTENSION_SCHEMA_VERSION = 1
EXPECTED_GEOMETRY = "circle-1025-center"
TARGET_MARKER_INTERVAL = 2
TARGET_QUALIFIED_ORDINAL = 14
CALLER_CONTINUATION_START_OFFSET = 0xD94
PRODUCER_CALLEE_CALL_OFFSET = 0xF5C
PRODUCER_CALLEE_RETURN_OFFSET = 0xF60
PRODUCER_CALLEE_RELATIVE_TO_PREPARE_LAYER = -1_206_100
PRODUCER_CALLEE_CALL_RAW_LITTLE_ENDIAN_HEX = "5462fb97"
CALLER_LOCAL_STATE_OFFSET = 0x420
CALLER_OUTPUT_OFFSET = 0x290
STACK_BYTE_COUNT = 0x100
ARGUMENT_BYTE_COUNT = 0x400
CALLER_ROLE_BYTE_COUNT = 0x800
OUTPUT_BYTE_COUNT = 0x200
MAXIMUM_CALLER_INSTRUCTION_COUNT = 1_024
MAXIMUM_CALLEE_INSTRUCTION_COUNT = 16_384
MAXIMUM_OPAQUE_CALLEE_COUNT = 4_096
TRACE_CHECKPOINT_INSTRUCTION_INTERVAL = 128
TRACE_CHECKPOINT_BOUNDARY_INTERVAL = 16
EXPECTED_HELPER_MISMATCH = "helper output does not match structural producer"

EXPECTED_CONFIGURATION = {
    "selectedMarkerInterval": TARGET_MARKER_INTERVAL,
    "selectedQualifiedHelperOrdinal": TARGET_QUALIFIED_ORDINAL,
    "callerContinuationStartOffset": CALLER_CONTINUATION_START_OFFSET,
    "producerCalleeCallOffset": PRODUCER_CALLEE_CALL_OFFSET,
    "producerCalleeReturnOffset": PRODUCER_CALLEE_RETURN_OFFSET,
    "producerCalleeRelativeToPrepareLayer": (PRODUCER_CALLEE_RELATIVE_TO_PREPARE_LAYER),
    "producerCalleeCallRawLittleEndianHex": (
        PRODUCER_CALLEE_CALL_RAW_LITTLE_ENDIAN_HEX
    ),
    "callerLocalStateOffset": CALLER_LOCAL_STATE_OFFSET,
    "callerOutputOffset": CALLER_OUTPUT_OFFSET,
    "stackByteCount": STACK_BYTE_COUNT,
    "argumentByteCount": ARGUMENT_BYTE_COUNT,
    "callerRoleByteCount": CALLER_ROLE_BYTE_COUNT,
    "outputByteCount": OUTPUT_BYTE_COUNT,
    "maximumCallerInstructionCount": MAXIMUM_CALLER_INSTRUCTION_COUNT,
    "maximumCalleeInstructionCount": MAXIMUM_CALLEE_INSTRUCTION_COUNT,
    "maximumOpaqueCalleeCount": MAXIMUM_OPAQUE_CALLEE_COUNT,
    "traceCheckpointInstructionInterval": TRACE_CHECKPOINT_INSTRUCTION_INTERVAL,
    "traceCheckpointBoundaryInterval": TRACE_CHECKPOINT_BOUNDARY_INTERVAL,
    "selectionRule": (
        "reuse marker interval 2 prepare_layer_mask ordinal 14 from the frozen "
        "output-blind helper/store/marker inventory; after that call returns, "
        "follow only its exact thread, x19 role, and frame to static "
        "prepare_layer+0xf5c; read no rectangle or output bytes before selection"
    ),
    "callArgumentRule": (
        "at prepare_layer+0xf5c require x0 to equal the selected global state, "
        "x1=x19+0x420, x3=x19+0x290, and nonzero x2"
    ),
    "steppingRule": (
        "with every breakpoint disabled and LLDB synchronous, retain complete "
        "scalar/SIMD registers, 256 stack bytes, 2048 caller role bytes, and "
        "512 destination bytes before and after every caller and opened-callee "
        "instruction; step out of every other callee as an explicit boundary"
    ),
    "correlationRule": (
        "after normal capture resumes, require the selected caller role to "
        "equal the independently opened sample-two producer store role and "
        "require the post-callee first rectangle to equal its retained "
        "binary64 producer bits"
    ),
    "hardwareWatchpointsUsed": False,
    "cropValuesUsedForSelection": False,
    "calleeExpectedSHA256": None,
}


mapping = holdout_analysis.mapping
sequence = holdout_analysis.sequence
integer = holdout_analysis.integer


def payload(value: Any, byte_count: int, label: str) -> bytes:
    return trace_validator.payload(value, byte_count, label)


def memory(
    value: Any, expected_address: int, expected_byte_count: int, label: str
) -> bytes:
    return trace_validator.memory(value, expected_address, expected_byte_count, label)


def registers(value: Any, label: str) -> dict[str, int]:
    return trace_validator.full_registers(value, label)


def frame(value: Any, label: str) -> Mapping[str, Any]:
    return trace_validator.frame(value, label)


def changed_qwords(before: bytes, after: bytes) -> list[int]:
    if len(before) != len(after) or len(before) % 8:
        raise ValueError("qword comparison byte count differs")
    return [
        offset
        for offset in range(0, len(before), 8)
        if before[offset : offset + 8] != after[offset : offset + 8]
    ]


def validate_inventory_transport(
    trace: Mapping[str, Any], inventory_path: Path
) -> tuple[Mapping[str, Any], int, str]:
    inventory, inventory_sha, ordinal = selected_validator.load_inventory(
        inventory_path
    )
    if ordinal != TARGET_QUALIFIED_ORDINAL:
        raise ValueError("producer-callee inventory ordinal differs")
    helper_extension = mapping(
        trace.get("prepareLayerMaskInstructionExtension"), "helper extension"
    )
    transport = mapping(
        helper_extension.get("prepareLayerMaskInventoryCalibrationTransport"),
        "selected helper transport",
    )
    source = mapping(transport.get("inventoryValidationSource"), "inventory source")
    inputs = mapping(inventory.get("inputs"), "inventory inputs")
    if (
        transport.get("prepareLayerMaskInventoryCalibrationTransportSchemaVersion") != 1
        or transport.get("mode") != "selected"
        or transport.get("targetQualifiedOrdinal") != ordinal
        or transport.get("inventorySentinelOrdinal") != 4097
        or transport.get("knownHelperCodeSHA256")
        != "f78c5fd222dc429152882dffb0b88a5535050351e3a2a5d7102a5abeca5c4c0c"
        or source.get("fileName") != inventory_path.name
        or source.get("sha256") != inventory_sha
        or source.get("inventoryTraceSHA256") != inputs.get("traceSHA256")
        or source.get("inventoryTimelineSHA256") != inputs.get("timelineSHA256")
        or transport.get("cropOrOutputValuesReadByTransport") is not False
        or transport.get("newBreakpointAddedByTransport") is not False
        or transport.get("captureByteRangeChangedByTransport") is not False
        or transport.get("steppingRuleChangedByTransport") is not False
    ):
        raise ValueError("producer-callee selected transport differs")
    return inventory, ordinal, inventory_sha


def validate_antecedent(
    trace_path: Path,
    timeline_path: Path,
    inventory_path: Path,
    expected_geometry: str,
) -> tuple[
    Mapping[str, Any],
    Mapping[str, Any],
    list[dict[str, Any]],
    Mapping[str, Any],
    int,
    str,
]:
    try:
        selected_validator.validate(
            trace_path,
            timeline_path,
            inventory_path,
            expected_geometry,
        )
    except ValueError as error:
        if str(error) != EXPECTED_HELPER_MISMATCH:
            raise ValueError(f"selected-helper antecedent differs: {error}") from error
    else:
        raise ValueError("selected helper unexpectedly produced the crop")

    trace = mapping(crop_validator.load_json(trace_path, "trace"), "trace")
    timeline = mapping(crop_validator.load_json(timeline_path, "timeline"), "timeline")
    inventory, ordinal, inventory_sha = validate_inventory_transport(
        trace, inventory_path
    )
    base_result = crop_validator.validate(trace_path, timeline_path, expected_geometry)
    crop_records, _union_accounting = crop_analysis.validate_extension(
        trace, base_result, timeline, expected_geometry
    )
    opened_records, _store_accounting = holdout_analysis.validate_store_extension(
        trace, base_result, timeline, crop_records, expected_geometry
    )
    return (
        trace,
        timeline,
        opened_records,
        inventory,
        ordinal,
        inventory_sha,
    )


def validate_callee_identity(
    extension: Mapping[str, Any],
    trace: Mapping[str, Any],
    prepare_start: int,
) -> tuple[Mapping[str, Any], bytes]:
    callee = mapping(extension.get("callee"), "producer callee")
    entry = prepare_start + PRODUCER_CALLEE_RELATIVE_TO_PREPARE_LAYER
    start = integer(callee.get("symbolStart"), "callee symbol start")
    byte_count = integer(callee.get("symbolByteCount"), "callee byte count")
    if not 1 <= byte_count <= 0x10000:
        raise ValueError("producer callee byte count differs")
    code = payload(callee.get("hex"), byte_count, "producer callee code")
    digest = hashlib.sha256(code).hexdigest()
    call_digest = hashlib.sha256(
        bytes.fromhex(PRODUCER_CALLEE_CALL_RAW_LITTLE_ENDIAN_HEX)
    ).hexdigest()
    if (
        not isinstance(callee.get("function"), str)
        or not callee.get("function")
        or not isinstance(callee.get("symbolName"), (str, type(None)))
        or callee.get("relativeToPrepareLayer")
        != PRODUCER_CALLEE_RELATIVE_TO_PREPARE_LAYER
        or callee.get("entryPC") != entry
        or callee.get("entryOffset") != entry - start
        or callee.get("symbolRelativeToPrepareLayer") != start - prepare_start
        or not start <= entry < start + byte_count
        or callee.get("symbolStart") != start
        or callee.get("symbolEnd") != start + byte_count
        or callee.get("expectedSHA256") is not None
        or callee.get("observedSHA256") != digest
        or callee.get("callPC") != prepare_start + PRODUCER_CALLEE_CALL_OFFSET
        or callee.get("callReturnPC") != prepare_start + PRODUCER_CALLEE_RETURN_OFFSET
        or callee.get("callInstructionSHA256") != call_digest
    ):
        raise ValueError("producer callee identity differs")
    module = mapping(callee.get("module"), "producer callee module")
    prepare_module = mapping(
        mapping(trace.get("prepareLayer"), "prepare layer").get("module"),
        "prepare layer module",
    )
    if (
        module.get("valid") is not True
        or module.get("path") != prepare_module.get("path")
        or module.get("loadAddress") != prepare_module.get("loadAddress")
    ):
        raise ValueError("producer callee module differs")
    return callee, code


def validate_selected_caller(
    extension: Mapping[str, Any],
    helper_extension: Mapping[str, Any],
    prepare_start: int,
) -> tuple[int, int, int, bytes, bytes, dict[str, int]]:
    selected = mapping(extension.get("selectedCaller"), "selected caller")
    invocation = mapping(
        helper_extension.get("selectedInvocation"), "selected invocation"
    )
    role_base = integer(selected.get("callerRoleBase"), "caller role base")
    output_address = integer(selected.get("outputAddress"), "output address")
    thread_id = integer(selected.get("threadID"), "selected thread")
    helper_frame = frame(
        selected.get("helperReturnFrame"), "selected helper return frame"
    )
    helper_registers = registers(
        selected.get("helperReturnRegisters"), "helper return registers"
    )
    output = memory(
        selected.get("outputAtHelperReturn"),
        output_address,
        OUTPUT_BYTE_COUNT,
        "output at helper return",
    )
    role = memory(
        selected.get("callerRoleAtHelperReturn"),
        role_base,
        CALLER_ROLE_BYTE_COUNT,
        "role at helper return",
    )
    invocation_output = memory(
        invocation.get("outputLayerShapesAtReturn"),
        output_address,
        OUTPUT_BYTE_COUNT,
        "invocation output at return",
    )
    if (
        invocation.get("callerRoleBase") != role_base
        or invocation.get("outputAddress") != output_address
        or invocation.get("threadID") != thread_id
        or helper_frame.get("function") != crop_validator.PREPARE_LAYER_FUNCTION
        or helper_frame.get("symbolStart") != prepare_start
        or helper_frame.get("symbolOffset") != CALLER_CONTINUATION_START_OFFSET
        or helper_registers["pc"] != prepare_start + CALLER_CONTINUATION_START_OFFSET
        or helper_registers["x19"] != role_base
        or output != invocation_output
        or output
        != role[CALLER_OUTPUT_OFFSET : CALLER_OUTPUT_OFFSET + OUTPUT_BYTE_COUNT]
        or output[:32] != bytes(32)
    ):
        raise ValueError("selected post-mask caller differs")
    entry_registers = registers(
        invocation.get("entryRegisters"), "selected helper entry registers"
    )
    return thread_id, role_base, output_address, output, role, entry_registers


def validate_memory_pair(
    record: Mapping[str, Any],
    output_address: int,
    role_base: int,
    label: str,
) -> tuple[bytes, bytes, bytes, bytes]:
    output_before = memory(
        record.get("outputBefore"),
        output_address,
        OUTPUT_BYTE_COUNT,
        f"{label} output before",
    )
    output_after = memory(
        record.get("outputAfter"),
        output_address,
        OUTPUT_BYTE_COUNT,
        f"{label} output after",
    )
    role_before = memory(
        record.get("callerRoleBefore"),
        role_base,
        CALLER_ROLE_BYTE_COUNT,
        f"{label} role before",
    )
    role_after = memory(
        record.get("callerRoleAfter"),
        role_base,
        CALLER_ROLE_BYTE_COUNT,
        f"{label} role after",
    )
    output_changes = changed_qwords(output_before, output_after)
    role_changes = changed_qwords(role_before, role_after)
    if (
        record.get("outputChanged") != bool(output_changes)
        or record.get("changedOutputQwordOffsets") != output_changes
        or record.get("callerRoleChanged") != bool(role_changes)
        or record.get("changedCallerRoleQwordOffsets") != role_changes
        or output_before
        != role_before[CALLER_OUTPUT_OFFSET : CALLER_OUTPUT_OFFSET + OUTPUT_BYTE_COUNT]
        or output_after
        != role_after[CALLER_OUTPUT_OFFSET : CALLER_OUTPUT_OFFSET + OUTPUT_BYTE_COUNT]
    ):
        raise ValueError(f"{label} change accounting differs")
    return output_before, output_after, role_before, role_after


def validate_instruction_state(
    state: Mapping[str, Any],
    expected_index: int,
    expected_scope: str,
    scope_start: int,
    scope_code: bytes | None,
    output_address: int,
    role_base: int,
    label: str,
) -> dict[str, Any]:
    instruction = mapping(state.get("instruction"), f"{label} instruction")
    instruction_pc = integer(instruction.get("pc"), f"{label} pc")
    scope_offset = integer(instruction.get("scopeOffset"), f"{label} offset")
    raw = payload(
        instruction.get("rawLittleEndianHex"), 4, f"{label} instruction bytes"
    )
    before_registers = registers(state.get("registersBefore"), f"{label} registers")
    after_registers = registers(
        state.get("registersAfter"), f"{label} result registers"
    )
    memory(
        state.get("stackBefore"),
        before_registers["sp"],
        STACK_BYTE_COUNT,
        f"{label} stack",
    )
    memory(
        state.get("stackAfter"),
        after_registers["sp"],
        STACK_BYTE_COUNT,
        f"{label} result stack",
    )
    if (
        state.get("stateIndex") != expected_index
        or instruction.get("scopeName") != expected_scope
        or instruction_pc != scope_start + scope_offset
        or before_registers["pc"] != instruction_pc
        or after_registers["pc"] != state.get("resultPC")
        or (expected_scope == "prepareLayer" and before_registers["x19"] != role_base)
        or not isinstance(instruction.get("mnemonic"), str)
        or not isinstance(instruction.get("operands"), str)
        or not isinstance(instruction.get("comment"), str)
        or not isinstance(instruction.get("potentialCall"), bool)
        or not isinstance(instruction.get("potentialReturn"), bool)
    ):
        raise ValueError(f"{label} instruction identity differs")
    if scope_code is not None:
        if (
            scope_offset < 0
            or scope_offset + 4 > len(scope_code)
            or scope_code[scope_offset : scope_offset + 4] != raw
        ):
            raise ValueError(f"{label} instruction code differs")
    output_before, output_after, role_before, role_after = validate_memory_pair(
        state, output_address, role_base, label
    )
    return {
        "pc": instruction_pc,
        "resultPC": integer(state.get("resultPC"), f"{label} result PC"),
        "resultFunction": state.get("resultFunction"),
        "raw": raw,
        "outputBefore": output_before,
        "outputAfter": output_after,
        "roleBefore": role_before,
        "roleAfter": role_after,
    }


def validate_opaque_boundary(
    boundary: Mapping[str, Any],
    expected_index: int,
    output_address: int,
    role_base: int,
    label: str,
) -> dict[str, Any]:
    entry = frame(boundary.get("entryFrame"), f"{label} entry frame")
    returned = frame(boundary.get("returnFrame"), f"{label} return frame")
    entry_registers = registers(
        boundary.get("registersAtEntry"), f"{label} entry registers"
    )
    return_registers = registers(
        boundary.get("registersAtReturn"), f"{label} return registers"
    )
    memory(
        boundary.get("stackAtEntry"),
        entry_registers["sp"],
        STACK_BYTE_COUNT,
        f"{label} entry stack",
    )
    memory(
        boundary.get("stackAtReturn"),
        return_registers["sp"],
        STACK_BYTE_COUNT,
        f"{label} return stack",
    )
    output_before, output_after, role_before, role_after = validate_memory_pair(
        boundary, output_address, role_base, label
    )
    if (
        boundary.get("boundaryIndex") != expected_index
        or not isinstance(boundary.get("expectedReturnFunction"), str)
        or entry_registers["pc"] != entry.get("pc")
        or return_registers["pc"] != returned.get("pc")
        or returned.get("function") != boundary.get("expectedReturnFunction")
    ):
        raise ValueError(f"{label} identity differs")
    return {
        "pc": entry.get("pc"),
        "resultPC": returned.get("pc"),
        "resultFunction": returned.get("function"),
        "outputBefore": output_before,
        "outputAfter": output_after,
        "roleBefore": role_before,
        "roleAfter": role_after,
    }


def validate_execution(
    extension: Mapping[str, Any],
    callee: Mapping[str, Any],
    code: bytes,
    prepare_start: int,
    output_address: int,
    role_base: int,
    initial_output: bytes,
    initial_role: bytes,
) -> dict[str, Any]:
    caller_states = list(
        sequence(
            extension.get("callerContinuationStates"),
            "caller continuation states",
        )
    )
    callee_states = list(
        sequence(
            extension.get("calleeInstructionStates"),
            "callee instruction states",
        )
    )
    boundaries = list(
        sequence(extension.get("opaqueCalleeBoundaries"), "opaque boundaries")
    )
    events = list(sequence(extension.get("executionEvents"), "execution events"))
    if (
        not 1 <= len(caller_states) <= MAXIMUM_CALLER_INSTRUCTION_COUNT
        or not 1 <= len(callee_states) <= MAXIMUM_CALLEE_INSTRUCTION_COUNT
        or len(boundaries) > MAXIMUM_OPAQUE_CALLEE_COUNT
        or len(events) != len(caller_states) + len(callee_states) + len(boundaries)
        or extension.get("finalCallerContinuationStateCount") != len(caller_states)
        or extension.get("finalCalleeInstructionStateCount") != len(callee_states)
        or extension.get("finalOpaqueCalleeBoundaryCount") != len(boundaries)
        or extension.get("finalExecutionEventCount") != len(events)
    ):
        raise ValueError("producer callee execution counts differ")
    decoded_caller: list[dict[str, Any]] = []
    for index, raw in enumerate(caller_states):
        decoded_caller.append(
            validate_instruction_state(
                mapping(raw, f"caller state {index}"),
                index,
                "prepareLayer",
                prepare_start,
                None,
                output_address,
                role_base,
                f"caller state {index}",
            )
        )
    decoded_callee: list[dict[str, Any]] = []
    for index, raw in enumerate(callee_states):
        decoded_callee.append(
            validate_instruction_state(
                mapping(raw, f"callee state {index}"),
                index,
                "producerCallee",
                integer(callee.get("symbolStart"), "callee start"),
                code,
                output_address,
                role_base,
                f"callee state {index}",
            )
        )
    decoded_boundaries: list[dict[str, Any]] = []
    for index, raw in enumerate(boundaries):
        decoded_boundaries.append(
            validate_opaque_boundary(
                mapping(raw, f"opaque boundary {index}"),
                index,
                output_address,
                role_base,
                f"opaque boundary {index}",
            )
        )

    expected_indices = {
        "prepareLayer-instruction": 0,
        "producerCallee-instruction": 0,
        "opaque-callee": 0,
    }
    collections = {
        "prepareLayer-instruction": decoded_caller,
        "producerCallee-instruction": decoded_callee,
        "opaque-callee": decoded_boundaries,
    }
    previous_output = initial_output
    previous_role = initial_role
    previous_result_pc: int | None = None
    for event_index, raw_event in enumerate(events):
        event = mapping(raw_event, f"execution event {event_index}")
        kind = event.get("kind")
        if kind not in collections:
            raise ValueError("producer callee event kind differs")
        expected_index = expected_indices[kind]
        if event.get("recordIndex") != expected_index:
            raise ValueError("producer callee event index differs")
        record = collections[kind][expected_index]
        expected_indices[kind] += 1
        if (
            record["outputBefore"] != previous_output
            or record["roleBefore"] != previous_role
            or (previous_result_pc is not None and record["pc"] != previous_result_pc)
        ):
            raise ValueError("producer callee execution chain differs")
        previous_output = record["outputAfter"]
        previous_role = record["roleAfter"]
        previous_result_pc = record["resultPC"]
    if any(expected_indices[kind] != len(collections[kind]) for kind in collections):
        raise ValueError("producer callee event coverage differs")
    if (
        decoded_caller[0]["pc"] != prepare_start + CALLER_CONTINUATION_START_OFFSET
        or decoded_caller[0]["raw"] != bytes.fromhex("7fb201b9")
        or decoded_caller[-1]["pc"] != prepare_start + PRODUCER_CALLEE_CALL_OFFSET
        or decoded_caller[-1]["raw"]
        != bytes.fromhex(PRODUCER_CALLEE_CALL_RAW_LITTLE_ENDIAN_HEX)
        or decoded_caller[-1]["resultPC"] != callee.get("entryPC")
        or decoded_callee[0]["pc"] != callee.get("entryPC")
        or previous_result_pc != prepare_start + PRODUCER_CALLEE_RETURN_OFFSET
    ):
        raise ValueError("producer callee execution boundary differs")
    return {
        "callerInstructionCount": len(decoded_caller),
        "calleeInstructionCount": len(decoded_callee),
        "opaqueCalleeBoundaryCount": len(decoded_boundaries),
        "executionEventCount": len(events),
        "changedOpaqueCalleeBoundaryCount": sum(
            item["outputBefore"] != item["outputAfter"]
            or item["roleBefore"] != item["roleAfter"]
            for item in decoded_boundaries
        ),
        "outputAtReturn": previous_output,
        "roleAtReturn": previous_role,
    }


def validate_call_and_return(
    extension: Mapping[str, Any],
    callee: Mapping[str, Any],
    prepare_start: int,
    entry_registers: Mapping[str, int],
    role_base: int,
    output_address: int,
    execution: Mapping[str, Any],
) -> tuple[bytes, bytes]:
    call = mapping(extension.get("calleeCall"), "producer callee call")
    call_frame = frame(call.get("frame"), "producer callee call frame")
    call_registers = registers(call.get("registers"), "producer call registers")
    memory(
        call.get("argumentX2AtCall"),
        call_registers["x2"],
        ARGUMENT_BYTE_COUNT,
        "producer callee x2 argument",
    )
    output_at_call = memory(
        call.get("outputAtCall"),
        output_address,
        OUTPUT_BYTE_COUNT,
        "producer output at call",
    )
    role_at_call = memory(
        call.get("callerRoleAtCall"),
        role_base,
        CALLER_ROLE_BYTE_COUNT,
        "producer role at call",
    )
    if (
        call_frame.get("function") != crop_validator.PREPARE_LAYER_FUNCTION
        or call_frame.get("symbolOffset") != PRODUCER_CALLEE_CALL_OFFSET
        or call_registers["pc"] != prepare_start + PRODUCER_CALLEE_CALL_OFFSET
        or call_registers["x19"] != role_base
        or call_registers["x0"] != entry_registers["x0"]
        or call_registers["x1"] != role_base + CALLER_LOCAL_STATE_OFFSET
        or call_registers["x3"] != output_address
        or call_registers["x2"] == 0
        or call.get("cropValuesUsedForSelection") is not False
    ):
        raise ValueError("producer callee call differs")
    entry = mapping(extension.get("calleeEntry"), "producer callee entry")
    entry_frame = frame(entry.get("frame"), "producer callee entry frame")
    callee_entry_registers = registers(
        entry.get("registers"), "producer callee entry registers"
    )
    memory(
        entry.get("stack"),
        callee_entry_registers["sp"],
        STACK_BYTE_COUNT,
        "producer callee entry stack",
    )
    entry_output = memory(
        entry.get("output"),
        output_address,
        OUTPUT_BYTE_COUNT,
        "producer callee entry output",
    )
    entry_role = memory(
        entry.get("callerRole"),
        role_base,
        CALLER_ROLE_BYTE_COUNT,
        "producer callee entry role",
    )
    if (
        entry_frame.get("pc") != callee.get("entryPC")
        or entry_frame.get("function") != callee.get("function")
        or callee_entry_registers["pc"] != callee.get("entryPC")
        or callee_entry_registers["x0"] != call_registers["x0"]
        or callee_entry_registers["x1"] != call_registers["x1"]
        or callee_entry_registers["x2"] != call_registers["x2"]
        or callee_entry_registers["x3"] != call_registers["x3"]
        or entry_output != output_at_call
        or entry_role != role_at_call
    ):
        raise ValueError("producer callee entry differs")
    returned = mapping(extension.get("calleeReturn"), "producer callee return")
    return_frame = frame(returned.get("frame"), "producer callee return frame")
    return_registers = registers(
        returned.get("registers"), "producer callee return registers"
    )
    memory(
        returned.get("stack"),
        return_registers["sp"],
        STACK_BYTE_COUNT,
        "producer callee return stack",
    )
    output = memory(
        returned.get("output"),
        output_address,
        OUTPUT_BYTE_COUNT,
        "producer callee return output",
    )
    role = memory(
        returned.get("callerRole"),
        role_base,
        CALLER_ROLE_BYTE_COUNT,
        "producer callee return role",
    )
    if (
        return_frame.get("function") != crop_validator.PREPARE_LAYER_FUNCTION
        or return_frame.get("symbolStart") != prepare_start
        or return_frame.get("symbolOffset") != PRODUCER_CALLEE_RETURN_OFFSET
        or return_registers["pc"] != prepare_start + PRODUCER_CALLEE_RETURN_OFFSET
        or return_registers["x19"] != role_base
        or output != execution["outputAtReturn"]
        or role != execution["roleAtReturn"]
    ):
        raise ValueError("producer callee return differs")
    return output, role


def validate(
    trace_path: Path,
    timeline_path: Path,
    inventory_path: Path,
    expected_geometry: str = EXPECTED_GEOMETRY,
) -> dict[str, Any]:
    if expected_geometry != EXPECTED_GEOMETRY:
        raise ValueError("producer callee expected geometry differs")
    (
        trace,
        _timeline,
        opened_records,
        inventory,
        ordinal,
        inventory_sha,
    ) = validate_antecedent(
        trace_path, timeline_path, inventory_path, expected_geometry
    )
    prepare_start = integer(
        mapping(trace.get("prepareLayer"), "prepare layer").get("symbolStart"),
        "prepare layer start",
    )
    helper_extension = mapping(
        trace.get("prepareLayerMaskInstructionExtension"), "helper extension"
    )
    extension = mapping(
        trace.get("prepareLayerCropProducerCalleeExtension"),
        "producer callee extension",
    )
    if (
        extension.get("prepareLayerCropProducerCalleeExtensionSchemaVersion")
        != EXTENSION_SCHEMA_VERSION
        or extension.get("configuration") != EXPECTED_CONFIGURATION
        or extension.get("status") != "finalized"
        or extension.get("statusBeforeFinalization")
        != "producer-callee-instruction-trace-closed"
        or sequence(extension.get("failures"), "producer callee failures")
        or extension.get("finalFailureCount") != 0
        or helper_extension.get("manualTraceStarted") is not True
        or helper_extension.get("manualTraceFinished") is not True
        or helper_extension.get("finalFailureCount") != 0
    ):
        raise ValueError("producer callee extension identity differs")
    callee, code = validate_callee_identity(extension, trace, prepare_start)
    (
        thread_id,
        role_base,
        output_address,
        initial_output,
        initial_role,
        helper_entry_registers,
    ) = validate_selected_caller(extension, helper_extension, prepare_start)
    execution = validate_execution(
        extension,
        callee,
        code,
        prepare_start,
        output_address,
        role_base,
        initial_output,
        initial_role,
    )
    output, role = validate_call_and_return(
        extension,
        callee,
        prepare_start,
        helper_entry_registers,
        role_base,
        output_address,
        execution,
    )
    selected_sample = next(
        record for record in opened_records if record.get("sampleIndex") == 2
    )
    producer_role = integer(
        selected_sample.get("producerRoleBase"), "structural producer role"
    )
    producer = payload(
        selected_sample.get("observedProducerHex"),
        32,
        "structural producer rectangle",
    )
    if (
        role_base != producer_role
        or output_address != producer_role + CALLER_OUTPUT_OFFSET
        or output[:32] != producer
        or role[CALLER_OUTPUT_OFFSET : CALLER_OUTPUT_OFFSET + 32] != producer
    ):
        raise ValueError("post-mask callee output does not match structural producer")
    producer_f64 = struct.unpack("<4d", producer)
    canonical_states = json.dumps(
        sequence(extension.get("calleeInstructionStates"), "callee states"),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    inventory_inputs = mapping(inventory.get("inputs"), "inventory inputs")
    return {
        "prepareLayerCropProducerCalleeValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            "prospective output-blind capture of the post-mask callee at "
            "prepare_layer+0xf5c; its returned first rectangle is correlated "
            "bit for bit to the independent sample-two producer role"
        ),
        "conclusion": "success",
        "prospectiveCaptureIntegrityGatePassed": True,
        "inputs": {
            "trace": str(trace_path),
            "traceSHA256": crop_analysis.sha256_file(trace_path),
            "timeline": str(timeline_path),
            "timelineSHA256": crop_analysis.sha256_file(timeline_path),
            "inventory": str(inventory_path),
            "inventorySHA256": inventory_sha,
            "inventoryTraceSHA256": inventory_inputs.get("traceSHA256"),
            "inventoryTimelineSHA256": inventory_inputs.get("timelineSHA256"),
        },
        "selection": {
            "markerInterval": TARGET_MARKER_INTERVAL,
            "qualifiedHelperOrdinal": ordinal,
            "threadID": thread_id,
            "callerRoleBase": role_base,
            "outputAddress": output_address,
            "cropValuesUsedForSelection": False,
        },
        "antecedentCorrection": {
            "prepareLayerMaskReturnMatchesProducer": False,
            "prepareLayerMaskFirstRectangleAtReturnHex": initial_output[:32].hex(),
            "expectedStrictFailure": EXPECTED_HELPER_MISMATCH,
        },
        "callee": {
            "function": callee.get("function"),
            "symbolName": callee.get("symbolName"),
            "relativeToPrepareLayer": PRODUCER_CALLEE_RELATIVE_TO_PREPARE_LAYER,
            "symbolByteCount": len(code),
            "codeSHA256": hashlib.sha256(code).hexdigest(),
            "codeExpectedBeforeCapture": False,
            "instructionStatesSHA256": hashlib.sha256(canonical_states).hexdigest(),
            **{
                key: execution[key]
                for key in (
                    "callerInstructionCount",
                    "calleeInstructionCount",
                    "opaqueCalleeBoundaryCount",
                    "changedOpaqueCalleeBoundaryCount",
                    "executionEventCount",
                )
            },
        },
        "structuralCorrelation": {
            "sampleIndex": 2,
            "producerRoleBase": producer_role,
            "producerOutputOffset": CALLER_OUTPUT_OFFSET,
            "producerF64": list(producer_f64),
            "producerHex": producer.hex(),
            "calleeReturnMatchesProducerBitForBit": True,
            "cropValuesUsedForSelection": False,
        },
        "sealedConclusion": {
            "completeOutputBlindInventoryRevalidated": True,
            "freshOrdinalFourteenSelectionRevalidated": True,
            "prepareLayerMaskOwnershipFalsificationPreserved": True,
            "postMaskCalleeCodeAndCompleteExecutionCaptured": True,
            "postMaskCalleeOwnsSelectedProducer": True,
            "exactCalleeSemanticsDecoded": False,
            "unchangedRepeatPassed": False,
            "allCropHoldoutsBitExact": False,
            "materialAppearanceDirectionTransferPassed": False,
            "physicalRetina2xAndColorTransferPassed": False,
            "independentWalleZeroByteFrameParityPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--expected-geometry", default=EXPECTED_GEOMETRY)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = validate(
        arguments.trace,
        arguments.timeline,
        arguments.inventory,
        arguments.expected_geometry,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
