#!/usr/bin/env python3
"""Validate the structurally selected ``prepare_layer_mask`` body trace."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_prepare_layer_crop_policy_holdout_callback_retry as holdout_analysis
import analyze_prepare_layer_crop_union_operand_matrix as crop_analysis
import validate_prepare_layer_crop_policy_holdout as holdout_validator
import validate_prepare_layer_crop_transfer as crop_validator
import validate_prepare_layer_crop_union_operand as union_validator
import validate_prepare_layer_instruction_trace as instruction_validator


VALIDATION_SCHEMA_VERSION = 1
EXTENSION_SCHEMA_VERSION = 1
HELPER_FUNCTION = (
    "CA::Render::Updater::prepare_layer_mask("
    "CA::Render::Updater::GlobalState&, "
    "CA::Render::Updater::LocalState&, "
    "CA::Render::Updater::LayerShapes const&, "
    "CA::Render::Updater::LayerShapes&)"
)
HELPER_RELATIVE_TO_PREPARE_LAYER = -1_209_388
HELPER_SYMBOL_BYTE_COUNT = 2_176
CALL_OFFSET = 0xD90
CALL_RETURN_OFFSET = 0xD94
CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = "915ffb97"
CALLER_LOCAL_STATE_OFFSET = 0x420
CALLER_OUTPUT_OFFSET = 0x290
TARGET_MARKER_INTERVAL = 2
TARGET_QUALIFIED_ORDINAL = 8
EXPECTED_GEOMETRY = "circle-1025-center"
MAXIMUM_HELPER_ENTRY_HIT_COUNT = 16_384
MAXIMUM_QUALIFIED_HELPER_ENTRY_COUNT = 4_096
MAXIMUM_HELPER_INSTRUCTION_COUNT = 8_192
MAXIMUM_OPAQUE_CALLEE_COUNT = 2_048
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
EXPECTED_CONFIGURATION = {
    "helperFunction": HELPER_FUNCTION,
    "helperRelativeToPrepareLayer": HELPER_RELATIVE_TO_PREPARE_LAYER,
    "helperSymbolByteCount": HELPER_SYMBOL_BYTE_COUNT,
    "helperExpectedSHA256": None,
    "callOffset": CALL_OFFSET,
    "callReturnOffset": CALL_RETURN_OFFSET,
    "callInstructionRawLittleEndianHex": CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX,
    "callerLocalStateOffset": CALLER_LOCAL_STATE_OFFSET,
    "callerOutputOffset": CALLER_OUTPUT_OFFSET,
    "targetMarkerInterval": TARGET_MARKER_INTERVAL,
    "targetQualifiedOrdinal": TARGET_QUALIFIED_ORDINAL,
    "expectedGeometry": EXPECTED_GEOMETRY,
    "maximumHelperEntryHitCount": MAXIMUM_HELPER_ENTRY_HIT_COUNT,
    "maximumQualifiedHelperEntryCount": MAXIMUM_QUALIFIED_HELPER_ENTRY_COUNT,
    "maximumHelperInstructionCount": MAXIMUM_HELPER_INSTRUCTION_COUNT,
    "maximumOpaqueCalleeCount": MAXIMUM_OPAQUE_CALLEE_COUNT,
    "maximumUnexpectedTerminalStopCount": MAXIMUM_UNEXPECTED_TERMINAL_STOP_COUNT,
    "stackByteCount": STACK_BYTE_COUNT,
    "argumentByteCount": ARGUMENT_BYTE_COUNT,
    "callerRoleByteCount": CALLER_ROLE_BYTE_COUNT,
    "outputByteCount": OUTPUT_BYTE_COUNT,
    "entryRegisterNames": list(ENTRY_REGISTER_NAMES),
    "entrySelectionRule": (
        "among exact direct-normal transition callers, select marker interval "
        "2 ordinal 8, then require x1=x19+0x420 and x3=x19+0x290; do not "
        "inspect any rectangle or output bytes"
    ),
    "steppingRule": (
        "set LLDB synchronous, disable every software breakpoint, retain "
        "complete scalar/SIMD registers, stack, and output bytes before and "
        "after every helper instruction; step into the helper and step out "
        "of non-helper callees as explicit input/output boundaries"
    ),
    "correlationRule": (
        "after normal capture resumes, require selected x3 to equal the "
        "marker-2 structural predecessor store role+0x290 and require helper "
        "return bytes to equal that later producer"
    ),
    "hardwareWatchpointsUsed": False,
    "cropValuesUsedForSelection": False,
}


mapping = holdout_analysis.mapping
sequence = holdout_analysis.sequence
integer = holdout_analysis.integer


def payload(value: Any, byte_count: int, label: str) -> bytes:
    if not isinstance(value, str) or len(value) != byte_count * 2:
        raise ValueError(f"{label} hexadecimal length differs")
    try:
        result = bytes.fromhex(value)
    except ValueError as error:
        raise ValueError(f"{label} is not hexadecimal") from error
    if len(result) != byte_count:
        raise ValueError(f"{label} byte count differs")
    return result


def memory(
    value: Any, expected_address: int, expected_byte_count: int, label: str
) -> bytes:
    address, result = crop_validator.memory_snapshot(
        value, expected_byte_count, label, expected_address
    )
    if address != expected_address:
        raise ValueError(f"{label} address differs")
    return result


def full_registers(value: Any, label: str) -> dict[str, int]:
    return instruction_validator._semantic_registers(value, label)


def frame(value: Any, label: str) -> Mapping[str, Any]:
    return crop_validator.frame_record(value, label)


def output_pair(
    before_value: Any,
    after_value: Any,
    output_address: int,
    label: str,
) -> tuple[bytes, bytes, list[int]]:
    before = memory(
        before_value, output_address, OUTPUT_BYTE_COUNT, f"{label} output before"
    )
    after = memory(
        after_value, output_address, OUTPUT_BYTE_COUNT, f"{label} output after"
    )
    changed = [
        offset
        for offset in range(0, OUTPUT_BYTE_COUNT, 8)
        if before[offset : offset + 8] != after[offset : offset + 8]
    ]
    return before, after, changed


def validate_helper_identity(
    extension: Mapping[str, Any], trace: Mapping[str, Any], prepare_start: int
) -> tuple[Mapping[str, Any], bytes]:
    helper = mapping(extension.get("helper"), "prepare_layer_mask helper")
    start = prepare_start + HELPER_RELATIVE_TO_PREPARE_LAYER
    end = start + HELPER_SYMBOL_BYTE_COUNT
    code = payload(helper.get("hex"), HELPER_SYMBOL_BYTE_COUNT, "helper code")
    digest = hashlib.sha256(code).hexdigest()
    call_digest = hashlib.sha256(
        bytes.fromhex(CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX)
    ).hexdigest()
    if (
        helper.get("function") != HELPER_FUNCTION
        or helper.get("relativeToPrepareLayer") != HELPER_RELATIVE_TO_PREPARE_LAYER
        or helper.get("symbolStart") != start
        or helper.get("symbolEnd") != end
        or helper.get("symbolByteCount") != HELPER_SYMBOL_BYTE_COUNT
        or helper.get("expectedSHA256") is not None
        or helper.get("observedSHA256") != digest
        or integer(helper.get("entryBreakpointID"), "helper breakpoint") <= 0
        or helper.get("callPC") != prepare_start + CALL_OFFSET
        or helper.get("callReturnPC") != prepare_start + CALL_RETURN_OFFSET
        or helper.get("callInstructionSHA256") != call_digest
    ):
        raise ValueError("prepare_layer_mask helper identity differs")
    module = mapping(helper.get("module"), "helper module")
    prepare_module = mapping(
        mapping(trace.get("prepareLayer"), "prepare layer").get("module"),
        "prepare module",
    )
    if (
        module.get("valid") is not True
        or module.get("path") != prepare_module.get("path")
        or module.get("loadAddress") != prepare_module.get("loadAddress")
        or not isinstance(module.get("uuid"), (str, type(None)))
    ):
        raise ValueError("prepare_layer_mask module differs")
    return helper, code


def validate_entry_records(
    extension: Mapping[str, Any], helper: Mapping[str, Any], prepare_start: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_records = list(
        sequence(extension.get("helperEntryRecords"), "helper entry records")
    )
    if not 1 <= len(raw_records) <= MAXIMUM_QUALIFIED_HELPER_ENTRY_COUNT:
        raise ValueError("helper entry inventory differs")
    records: list[dict[str, Any]] = []
    expected_ordinal_by_interval: dict[int, int] = {}
    for index, raw in enumerate(raw_records):
        label = f"helper entry {index}"
        record = mapping(raw, label)
        interval = integer(record.get("markerIntervalIndex"), f"{label} interval")
        expected_ordinal_by_interval[interval] = (
            expected_ordinal_by_interval.get(interval, 0) + 1
        )
        ordinal = expected_ordinal_by_interval[interval]
        helper_frame = frame(record.get("frame"), f"{label} frame")
        caller = frame(record.get("callerFrame"), f"{label} caller")
        if (
            record.get("recordIndex") != index
            or record.get("qualifiedEntryIndex") != index + 1
            or integer(record.get("entryHitIndex"), f"{label} hit") <= 0
            or interval <= 0
            or record.get("qualifiedOrdinalWithinMarkerInterval") != ordinal
            or helper_frame.get("function") != HELPER_FUNCTION
            or helper_frame.get("symbolStart") != helper.get("symbolStart")
            or helper_frame.get("symbolEnd") != helper.get("symbolEnd")
            or helper_frame.get("symbolOffset") != 0
            or helper_frame.get("pc") != helper.get("symbolStart")
            or caller.get("function") != crop_validator.PREPARE_LAYER_FUNCTION
            or caller.get("symbolStart") != prepare_start
            or caller.get("symbolEnd")
            != prepare_start + crop_validator.PREPARE_LAYER_SYMBOL_BYTE_COUNT
            or caller.get("symbolOffset") != CALL_RETURN_OFFSET
            or caller.get("pc") != prepare_start + CALL_RETURN_OFFSET
        ):
            raise ValueError(f"{label} structural identity differs")
        backtrace = sequence(record.get("backtrace"), f"{label} backtrace")
        functions = union_validator.backtrace_functions(backtrace)
        if not union_validator.direct_timeline_caller(functions):
            raise ValueError(f"{label} caller chain differs")
        depth = sum(
            mapping(raw_frame, f"{label} backtrace frame").get("function")
            == crop_validator.PREPARE_LAYER_FUNCTION
            and mapping(raw_frame, f"{label} backtrace frame").get("symbolStart")
            == prepare_start
            and mapping(raw_frame, f"{label} backtrace frame").get("symbolEnd")
            == prepare_start + crop_validator.PREPARE_LAYER_SYMBOL_BYTE_COUNT
            for raw_frame in backtrace
        )
        registers = crop_validator.register_values(
            record.get("registers"), ENTRY_REGISTER_NAMES, f"{label} registers"
        )
        identity = mapping(record.get("frameIdentity"), f"{label} identity")
        expected_identity = {
            "threadID": record.get("threadID"),
            "callerRoleBase": registers["x19"],
            "callerFramePointer": registers["x29"],
            "globalStateX0": registers["x0"],
            "localStateX1": registers["x1"],
            "sourceLayerShapesX2": registers["x2"],
            "outputLayerShapesX3": registers["x3"],
        }
        offsets_match = (
            registers["x1"] == registers["x19"] + CALLER_LOCAL_STATE_OFFSET
            and registers["x3"] == registers["x19"] + CALLER_OUTPUT_OFFSET
        )
        selected_ordinal = (
            interval == TARGET_MARKER_INTERVAL
            and ordinal == TARGET_QUALIFIED_ORDINAL
        )
        selected = selected_ordinal and offsets_match
        if (
            record.get("prepareRecursionDepth") != depth
            or dict(identity) != expected_identity
            or record.get("roleOffsetsMatch") is not offsets_match
            or record.get("selectedByFrozenOrdinal") is not selected_ordinal
            or record.get("selectedByFrozenRule") is not selected
        ):
            raise ValueError(f"{label} argument identity differs")
        records.append(
            {
                "recordIndex": index,
                "markerIntervalIndex": interval,
                "ordinal": ordinal,
                "threadID": integer(record.get("threadID"), f"{label} thread"),
                "prepareRecursionDepth": depth,
                "registers": registers,
                "selected": selected,
            }
        )
    selected_records = [record for record in records if record["selected"]]
    if len(selected_records) != 1:
        raise ValueError("selected helper entry is not unique")
    selected = selected_records[0]
    if selected["recordIndex"] != len(records) - 1:
        raise ValueError("helper entry collection did not stop at target")

    rejected = integer(
        extension.get("finalRejectedHelperEntryCount"), "rejected helper entries"
    )
    grouped = 0
    for raw_group in sequence(extension.get("rejectionGroups"), "helper rejections"):
        group = mapping(raw_group, "helper rejection")
        if group.get("reason") != "caller-chain-excluded":
            raise ValueError("helper rejection reason differs")
        integer(group.get("prepareRecursionDepth"), "helper rejection depth")
        grouped += integer(group.get("hitCount"), "helper rejection count")
    if (
        rejected != grouped
        or extension.get("finalQualifiedHelperEntryCount") != len(records)
        or extension.get("finalHelperEntryRecordCount") != len(records)
        or extension.get("finalHelperEntryHitCount") != len(records) + rejected
    ):
        raise ValueError("helper entry accounting differs")
    return records, selected


def validate_marker_links(
    extension: Mapping[str, Any], records: Sequence[Mapping[str, Any]], selected: Mapping[str, Any]
) -> None:
    links = list(sequence(extension.get("markerLinks"), "helper marker links"))
    if len(links) != 32 or extension.get("finalMarkerLinkCount") != 32:
        raise ValueError("helper marker-link inventory differs")
    previous_end = 0
    selected_seen = False
    for index, raw in enumerate(links, start=1):
        link = mapping(raw, f"helper marker link {index}")
        start = integer(link.get("startHelperRecordIndex"), "helper link start")
        end = integer(
            link.get("endHelperRecordIndexExclusive"), "helper link end"
        )
        expected_selected = [
            record["recordIndex"]
            for record in records[start:end]
            if record["selected"]
        ]
        if (
            link.get("markerRecordIndex") != index - 1
            or integer(link.get("markerCallbackSequence"), "marker callback") <= 0
            or link.get("markerIntervalIndex") != index
            or start != previous_end
            or not 0 <= start <= end <= len(records)
            or link.get("selectedHelperRecordIndices") != expected_selected
            or link.get("helperCollectionStoppedAtTarget") is not (index >= 2)
        ):
            raise ValueError(f"helper marker link {index} differs")
        if expected_selected:
            if index != TARGET_MARKER_INTERVAL or selected_seen:
                raise ValueError("selected helper marker link differs")
            selected_seen = True
        previous_end = end
    if previous_end != len(records) or not selected_seen:
        raise ValueError("helper marker links do not cover selected record")
    if selected["markerIntervalIndex"] != TARGET_MARKER_INTERVAL:
        raise ValueError("selected helper interval differs")


def validate_selected_entry(
    extension: Mapping[str, Any], selected: Mapping[str, Any]
) -> tuple[Mapping[str, Any], bytes, bytes]:
    invocation = mapping(extension.get("selectedInvocation"), "selected invocation")
    registers = full_registers(invocation.get("entryRegisters"), "entry registers")
    expected = selected["registers"]
    if (
        invocation.get("recordIndex") != selected["recordIndex"]
        or invocation.get("threadID") != selected["threadID"]
        or invocation.get("callerRoleBase") != expected["x19"]
        or invocation.get("outputAddress") != expected["x3"]
        or invocation.get("entrySP") != expected["sp"]
        or invocation.get("entryPC") != expected["pc"]
        or any(registers[name] != expected[name] for name in ENTRY_REGISTER_NAMES)
    ):
        raise ValueError("selected helper entry differs")
    memory(invocation.get("entryStack"), registers["sp"], STACK_BYTE_COUNT, "entry stack")
    memory(
        invocation.get("globalStateAtEntry"),
        registers["x0"],
        ARGUMENT_BYTE_COUNT,
        "entry global state",
    )
    memory(
        invocation.get("localStateAtEntry"),
        registers["x1"],
        ARGUMENT_BYTE_COUNT,
        "entry local state",
    )
    memory(
        invocation.get("sourceLayerShapesAtEntry"),
        registers["x2"],
        ARGUMENT_BYTE_COUNT,
        "entry source LayerShapes",
    )
    output = memory(
        invocation.get("outputLayerShapesAtEntry"),
        registers["x3"],
        OUTPUT_BYTE_COUNT,
        "entry output LayerShapes",
    )
    role = memory(
        invocation.get("callerRoleAtEntry"),
        registers["x19"],
        CALLER_ROLE_BYTE_COUNT,
        "entry caller role",
    )
    if output != role[CALLER_OUTPUT_OFFSET : CALLER_OUTPUT_OFFSET + OUTPUT_BYTE_COUNT]:
        raise ValueError("entry output does not alias caller role")
    return invocation, output, role


def validate_breakpoints(extension: Mapping[str, Any], helper: Mapping[str, Any]) -> None:
    disabled = mapping(extension.get("breakpointDisablement"), "breakpoint disablement")
    if disabled.get("watchpointCount") != 0:
        raise ValueError("helper trace used a watchpoint")
    before = [
        mapping(raw, "disabled breakpoint")
        for raw in sequence(disabled.get("breakpoints"), "disabled breakpoints")
    ]
    if not before:
        raise ValueError("breakpoint disablement inventory is empty")
    before_ids = [integer(item.get("breakpointID"), "breakpoint ID") for item in before]
    if len(set(before_ids)) != len(before_ids):
        raise ValueError("breakpoint disablement IDs repeat")
    for item in before:
        if (
            not isinstance(item.get("enabledBefore"), bool)
            or integer(item.get("locationCount"), "breakpoint locations") < 0
        ):
            raise ValueError("breakpoint disablement record differs")

    restoration = mapping(extension.get("breakpointRestoration"), "breakpoint restoration")
    helper_id = integer(helper.get("entryBreakpointID"), "helper breakpoint")
    if restoration.get("helperEntryBreakpointID") != helper_id:
        raise ValueError("helper restoration ID differs")
    after = [
        mapping(raw, "restored breakpoint")
        for raw in sequence(restoration.get("breakpoints"), "restored breakpoints")
    ]
    if [item.get("breakpointID") for item in after] != before_ids:
        raise ValueError("breakpoint restoration inventory differs")
    expected_by_id = {item["breakpointID"]: item["enabledBefore"] for item in before}
    for item in after:
        identifier = integer(item.get("breakpointID"), "restored breakpoint ID")
        is_helper = identifier == helper_id
        expected_enabled = bool(expected_by_id[identifier] and not is_helper)
        if (
            item.get("helperEntryDeliberatelyDisabled") is not is_helper
            or item.get("enabledAfterRestore") is not expected_enabled
        ):
            raise ValueError("breakpoint restoration state differs")


def validate_execution(
    extension: Mapping[str, Any],
    helper: Mapping[str, Any],
    code: bytes,
    invocation: Mapping[str, Any],
    prepare_start: int,
) -> dict[str, Any]:
    states = list(sequence(extension.get("instructionStates"), "instruction states"))
    boundaries = list(
        sequence(extension.get("opaqueCalleeBoundaries"), "opaque boundaries")
    )
    events = list(sequence(extension.get("executionEvents"), "execution events"))
    if not 1 <= len(states) <= MAXIMUM_HELPER_INSTRUCTION_COUNT:
        raise ValueError("helper instruction inventory differs")
    if len(boundaries) > MAXIMUM_OPAQUE_CALLEE_COUNT:
        raise ValueError("helper opaque boundary bound differs")
    if len(events) != len(states) + len(boundaries):
        raise ValueError("helper execution event count differs")
    output_address = integer(invocation.get("outputAddress"), "output address")
    decoded_states: list[dict[str, Any]] = []
    for index, raw in enumerate(states):
        label = f"helper instruction state {index}"
        state = mapping(raw, label)
        instruction = mapping(state.get("instruction"), f"{label} instruction")
        pc = integer(instruction.get("pc"), f"{label} PC")
        offset = integer(instruction.get("helperOffset"), f"{label} offset")
        raw_bytes = payload(
            instruction.get("rawLittleEndianHex"), 4, f"{label} instruction"
        )
        if (
            state.get("stateIndex") != index
            or pc != helper["symbolStart"] + offset
            or not 0 <= offset <= HELPER_SYMBOL_BYTE_COUNT - 4
            or offset % 4
            or raw_bytes != code[offset : offset + 4]
            or not isinstance(instruction.get("mnemonic"), str)
            or not isinstance(instruction.get("operands"), str)
            or not isinstance(instruction.get("comment"), str)
            or not isinstance(instruction.get("potentialCall"), bool)
            or not isinstance(instruction.get("potentialReturn"), bool)
        ):
            raise ValueError(f"{label} identity differs")
        registers = full_registers(state.get("registersBefore"), f"{label} registers")
        if registers["pc"] != pc:
            raise ValueError(f"{label} PC register differs")
        memory(
            state.get("stackBefore"),
            registers["sp"],
            STACK_BYTE_COUNT,
            f"{label} stack",
        )
        before, after, changed = output_pair(
            state.get("outputBefore"),
            state.get("outputAfter"),
            output_address,
            label,
        )
        if (
            state.get("outputChanged") is not (before != after)
            or state.get("changedOutputQwordOffsets") != changed
            or integer(state.get("resultPC"), f"{label} result PC") <= 0
            or not isinstance(state.get("resultFunction"), (str, type(None)))
        ):
            raise ValueError(f"{label} result differs")
        decoded_states.append(
            {
                "pc": pc,
                "resultPC": state["resultPC"],
                "potentialReturn": instruction["potentialReturn"],
                "outputBefore": before,
                "outputAfter": after,
            }
        )

    decoded_boundaries: list[dict[str, Any]] = []
    for index, raw in enumerate(boundaries):
        label = f"helper opaque boundary {index}"
        boundary = mapping(raw, label)
        entry = frame(boundary.get("entryFrame"), f"{label} entry")
        returned = frame(boundary.get("returnFrame"), f"{label} return")
        entry_registers = full_registers(
            boundary.get("registersAtEntry"), f"{label} entry registers"
        )
        return_registers = full_registers(
            boundary.get("registersAtReturn"), f"{label} return registers"
        )
        if (
            boundary.get("boundaryIndex") != index
            or entry_registers["pc"] != entry.get("pc")
            or return_registers["pc"] != returned.get("pc")
            or helper["symbolStart"] <= entry.get("pc") < helper["symbolEnd"]
        ):
            raise ValueError(f"{label} frame identity differs")
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
        before, after, changed = output_pair(
            boundary.get("outputBefore"),
            boundary.get("outputAfter"),
            output_address,
            label,
        )
        if (
            boundary.get("outputChanged") is not (before != after)
            or boundary.get("changedOutputQwordOffsets") != changed
        ):
            raise ValueError(f"{label} output differs")
        decoded_boundaries.append(
            {
                "entryPC": entry["pc"],
                "returnPC": returned["pc"],
                "outputBefore": before,
                "outputAfter": after,
            }
        )

    expected_pc = helper["symbolStart"]
    seen_states: list[int] = []
    seen_boundaries: list[int] = []
    previous_output: bytes | None = None
    for event_index, raw in enumerate(events):
        event = mapping(raw, f"execution event {event_index}")
        kind = event.get("kind")
        record_index = integer(event.get("recordIndex"), "execution record index")
        if kind == "helper-instruction":
            if not 0 <= record_index < len(decoded_states):
                raise ValueError("execution instruction index differs")
            record = decoded_states[record_index]
            seen_states.append(record_index)
            entry_pc = record["pc"]
            result_pc = record["resultPC"]
            before = record["outputBefore"]
            after = record["outputAfter"]
        elif kind == "opaque-callee":
            if not 0 <= record_index < len(decoded_boundaries):
                raise ValueError("execution boundary index differs")
            record = decoded_boundaries[record_index]
            seen_boundaries.append(record_index)
            entry_pc = record["entryPC"]
            result_pc = record["returnPC"]
            before = record["outputBefore"]
            after = record["outputAfter"]
        else:
            raise ValueError("execution event kind differs")
        if entry_pc != expected_pc or (previous_output is not None and before != previous_output):
            raise ValueError("helper execution chain is discontinuous")
        expected_pc = result_pc
        previous_output = after
    if (
        seen_states != list(range(len(decoded_states)))
        or seen_boundaries != list(range(len(decoded_boundaries)))
        or expected_pc != prepare_start + CALL_RETURN_OFFSET
    ):
        raise ValueError("helper execution closure differs")
    return {
        "instructionStateCount": len(decoded_states),
        "opaqueCalleeBoundaryCount": len(decoded_boundaries),
        "executionEventCount": len(events),
        "outputAtExecutionReturn": previous_output,
    }


def validate_return(
    invocation: Mapping[str, Any],
    execution: Mapping[str, Any],
    prepare_start: int,
) -> tuple[bytes, bytes]:
    output_address = integer(invocation.get("outputAddress"), "output address")
    role_base = integer(invocation.get("callerRoleBase"), "caller role base")
    returned = frame(invocation.get("returnFrame"), "helper return frame")
    registers = full_registers(invocation.get("returnRegisters"), "return registers")
    if (
        invocation.get("returnPC") != prepare_start + CALL_RETURN_OFFSET
        or returned.get("function") != crop_validator.PREPARE_LAYER_FUNCTION
        or returned.get("symbolStart") != prepare_start
        or returned.get("symbolEnd")
        != prepare_start + crop_validator.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        or returned.get("symbolOffset") != CALL_RETURN_OFFSET
        or returned.get("pc") != prepare_start + CALL_RETURN_OFFSET
        or registers["pc"] != prepare_start + CALL_RETURN_OFFSET
    ):
        raise ValueError("helper return identity differs")
    memory(
        invocation.get("returnStack"),
        registers["sp"],
        STACK_BYTE_COUNT,
        "helper return stack",
    )
    output = memory(
        invocation.get("outputLayerShapesAtReturn"),
        output_address,
        OUTPUT_BYTE_COUNT,
        "helper output at return",
    )
    role = memory(
        invocation.get("callerRoleAtReturn"),
        role_base,
        CALLER_ROLE_BYTE_COUNT,
        "helper caller role at return",
    )
    if (
        output != role[CALLER_OUTPUT_OFFSET : CALLER_OUTPUT_OFFSET + OUTPUT_BYTE_COUNT]
        or output != execution["outputAtExecutionReturn"]
        or invocation.get("instructionStateCount")
        != execution["instructionStateCount"]
        or invocation.get("opaqueCalleeBoundaryCount")
        != execution["opaqueCalleeBoundaryCount"]
        or invocation.get("executionEventCount") != execution["executionEventCount"]
    ):
        raise ValueError("helper return output differs")
    return output, role


def validate(
    trace_path: Path,
    timeline_path: Path,
    expected_geometry: str = EXPECTED_GEOMETRY,
) -> dict[str, Any]:
    if expected_geometry != EXPECTED_GEOMETRY:
        raise ValueError("prepare_layer_mask expected geometry differs")
    try:
        holdout_validator.validate(trace_path, timeline_path, expected_geometry)
    except ValueError as error:
        if str(error) != holdout_analysis.ORIGINAL_PROSPECTIVE_FLOAT_ERROR:
            raise ValueError(f"original prospective failure differs: {error}") from error
    else:
        raise ValueError("original crop-policy gate unexpectedly passed")

    base_result = crop_validator.validate(trace_path, timeline_path, expected_geometry)
    trace = mapping(crop_validator.load_json(trace_path, "trace"), "trace")
    timeline = mapping(crop_validator.load_json(timeline_path, "timeline"), "timeline")
    crop_records, _union_accounting = crop_analysis.validate_extension(
        trace, base_result, timeline, expected_geometry
    )
    opened_records, _store_accounting = holdout_analysis.validate_store_extension(
        trace, base_result, timeline, crop_records, expected_geometry
    )
    prepare_start = integer(
        mapping(trace.get("prepareLayer"), "prepare layer").get("symbolStart"),
        "prepare start",
    )
    extension = mapping(
        trace.get("prepareLayerMaskInstructionExtension"),
        "prepare_layer_mask extension",
    )
    if (
        extension.get("prepareLayerMaskInstructionExtensionSchemaVersion")
        != EXTENSION_SCHEMA_VERSION
        or extension.get("configuration") != EXPECTED_CONFIGURATION
        or extension.get("status") != "finalized"
        or extension.get("statusBeforeFinalization")
        != "selected-helper-instruction-trace-closed"
        or extension.get("manualTraceStarted") is not True
        or extension.get("manualTraceFinished") is not True
        or sequence(extension.get("failures"), "helper failures")
        or extension.get("finalFailureCount") != 0
    ):
        raise ValueError("prepare_layer_mask extension identity differs")
    terminal = mapping(extension.get("terminalProcess"), "helper terminal process")
    if (
        terminal.get("exited") is not True
        or terminal.get("detached") is not False
        or terminal.get("exitStatus") != 0
        or sequence(terminal.get("unexpectedStops"), "unexpected terminal stops")
    ):
        raise ValueError("prepare_layer_mask terminal process differs")

    helper, code = validate_helper_identity(extension, trace, prepare_start)
    entries, selected = validate_entry_records(extension, helper, prepare_start)
    validate_marker_links(extension, entries, selected)
    invocation, _entry_output, _entry_role = validate_selected_entry(
        extension, selected
    )
    validate_breakpoints(extension, helper)
    execution = validate_execution(
        extension, helper, code, invocation, prepare_start
    )
    output, role = validate_return(invocation, execution, prepare_start)

    selected_sample = next(
        record for record in opened_records if record.get("sampleIndex") == 2
    )
    producer_role = integer(
        selected_sample.get("producerRoleBase"), "structural producer role"
    )
    observed_hex = selected_sample.get("observedProducerHex")
    observed = payload(observed_hex, 32, "structural producer float")
    if (
        selected["registers"]["x3"] != producer_role + CALLER_OUTPUT_OFFSET
        or invocation.get("callerRoleBase") != producer_role
        or output[:32] != observed
        or role[CALLER_OUTPUT_OFFSET : CALLER_OUTPUT_OFFSET + 32] != observed
    ):
        raise ValueError("helper output does not match structural producer")
    producer_f64 = struct.unpack("<4d", observed)

    canonical_states = json.dumps(
        sequence(extension.get("instructionStates"), "instruction states"),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return {
        "prepareLayerMaskInstructionTraceValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            "prospectively selected prepare_layer_mask helper-body calibration; "
            "the call is selected without output values and its returned bytes "
            "are correlated to the independently opened structural producer"
        ),
        "conclusion": "success",
        "prospectiveCaptureIntegrityGatePassed": True,
        "inputs": {
            "trace": str(trace_path),
            "traceSHA256": crop_analysis.sha256_file(trace_path),
            "timeline": str(timeline_path),
            "timelineSHA256": crop_analysis.sha256_file(timeline_path),
        },
        "geometry": base_result["geometry"],
        "originalProspectiveGatePassed": False,
        "originalProspectiveFailure": (
            holdout_analysis.ORIGINAL_PROSPECTIVE_FLOAT_ERROR
        ),
        "helper": {
            "function": HELPER_FUNCTION,
            "relativeToPrepareLayer": HELPER_RELATIVE_TO_PREPARE_LAYER,
            "symbolByteCount": HELPER_SYMBOL_BYTE_COUNT,
            "codeSHA256": hashlib.sha256(code).hexdigest(),
            "codeExpectedBeforeCapture": False,
            "entryRecordCount": len(entries),
            "selectedMarkerInterval": selected["markerIntervalIndex"],
            "selectedQualifiedOrdinal": selected["ordinal"],
            **{
                key: execution[key]
                for key in (
                    "instructionStateCount",
                    "opaqueCalleeBoundaryCount",
                    "executionEventCount",
                )
            },
            "instructionStatesSHA256": hashlib.sha256(canonical_states).hexdigest(),
        },
        "structuralCorrelation": {
            "sampleIndex": 2,
            "selectedOutputAddress": selected["registers"]["x3"],
            "producerRoleBase": producer_role,
            "producerOutputOffset": CALLER_OUTPUT_OFFSET,
            "producerF64": list(producer_f64),
            "producerHex": observed.hex(),
            "helperReturnMatchesProducerBitForBit": True,
            "cropValuesUsedForSelection": False,
        },
        "sealedConclusion": {
            "allInheritedMarkerUnionAndStoreEvidenceRevalidated": True,
            "originalProspectiveFailurePreserved": True,
            "helperCodeAndSymbolCapturedExactly": True,
            "helperCallSelectedStructurally": True,
            "completeHelperInstructionStateSequenceCaptured": True,
            "helperReturnCorrelatedToTrueProducer": True,
            "exactHelperSemanticsDecoded": False,
            "unchangedRepeatPassed": False,
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
    parser.add_argument("--expected-geometry", default=EXPECTED_GEOMETRY)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = validate(
        arguments.trace, arguments.timeline, arguments.expected_geometry
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
