#!/usr/bin/env python3
"""Validate the structurally selected FilterOp map-bounds execution trace."""

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
import validate_prepare_layer_crop_producer_callee as producer_validator
import validate_prepare_layer_crop_transfer as crop_validator


VALIDATION_SCHEMA_VERSION = 1
EXTENSION_SCHEMA_VERSION = 1
EXPECTED_GEOMETRY = "circle-1025-center"
CALLER_CONTINUATION_START_OFFSET = 0xD94
DYNAMIC_CALL_OFFSET = 0x2864
DYNAMIC_RETURN_OFFSET = 0x2868
DYNAMIC_CALL_RAW_LITTLE_ENDIAN_HEX = "10093fd7"
TARGET_DISPATCH_ORDINAL = 4
FILTER_FUNCTION = (
    "CA::Render::Updater::FilterOp::map_bounds(CA::Render::Updater::LayerShapes&, bool)"
)
FILTER_RELATIVE_TO_PREPARE_LAYER = -61056
FILTER_SYMBOL_BYTE_COUNT = 788
FILTER_CODE_SHA256 = "e8766dcefdadc0074f7bb4e2bf62955072891858009dca6c72a7eef1c96789d0"
OPENED_SCOPE_SPECS = [
    {
        "name": "rectApplyTransform",
        "function": "CA::Rect::apply_transform(CA::SimpleTransform const&)",
        "relativeToPrepareLayer": -1207212,
        "symbolByteCount": 216,
        "codeSHA256": (
            "33690a5426ab0ea58626fd32bac7793953f0b9d4bf5a2b9de070701c2b3f1905"
        ),
    },
    {
        "name": "rectUnapplyTransform",
        "function": "CA::Rect::unapply_transform(CA::SimpleTransform const&)",
        "relativeToPrepareLayer": -1202648,
        "symbolByteCount": 216,
        "codeSHA256": (
            "6cfb69c5706fce5a48b722499d708ea7e76ffdcaba41b8b5ec77ad2e4481b046"
        ),
    },
    {
        "name": "glassBackgroundDOD",
        "function": (
            "CA::OGL::GlassBackgroundFilter::DOD(CA::Render::Filter const*, "
            "CA::Render::Layer const*, CA::Rect&) const"
        ),
        "relativeToPrepareLayer": -90584,
        "symbolByteCount": 1136,
        "codeSHA256": (
            "8ac014e4a0e296c28b5ada0444a281d7609e93a239f4201f748d758defe6955e"
        ),
    },
    {
        "name": "filterApplyDOD",
        "function": (
            "CA::Render::Filter::apply_dod(CA::Render::Layer const*, CA::Rect&) const"
        ),
        "relativeToPrepareLayer": -609324,
        "symbolByteCount": 1092,
        "codeSHA256": (
            "1fbe87e96831c11eee633b58c2b0a39968d75ea29a48673aa95ccb761eaa30dd"
        ),
    },
    {
        "name": "filterApply",
        "function": "CA::Render::Updater::FilterOp::apply_filter(CA::Rect&, bool)",
        "relativeToPrepareLayer": -61476,
        "symbolByteCount": 292,
        "codeSHA256": (
            "855b03e09d815f83985994344be2867e6ac40938e80897183bcd06afc89f252f"
        ),
    },
    {
        "name": "filterMapBounds",
        "function": FILTER_FUNCTION,
        "relativeToPrepareLayer": FILTER_RELATIVE_TO_PREPARE_LAYER,
        "symbolByteCount": FILTER_SYMBOL_BYTE_COUNT,
        "codeSHA256": FILTER_CODE_SHA256,
    },
    {
        "name": "unionBounds",
        "function": (
            "CA::Render::Updater::LayerShapes::union_bounds(CA::Rect const&, bool)"
        ),
        "relativeToPrepareLayer": -2720,
        "symbolByteCount": 404,
        "codeSHA256": (
            "246257a9bc1a608f59dbc07345397a8851b49528c59407eb775e9b9895a2c4b7"
        ),
    },
]
EXPECTED_DISPATCH_FUNCTIONS = [
    "CA::Render::Updater::FlattenZOp::map_bounds("
    "CA::Render::Updater::LayerShapes&, bool)",
    "CA::Render::Updater::SDFOp::map_bounds(CA::Render::Updater::LayerShapes&, bool)",
    "CA::Render::Updater::FlattenZOp::map_bounds("
    "CA::Render::Updater::LayerShapes&, bool)",
    FILTER_FUNCTION,
]
EXPECTED_DISPATCH_CALLER_STATE_INDICES = [343, 359, 375, 391]
STACK_BYTE_COUNT = producer_validator.STACK_BYTE_COUNT
CALLER_ROLE_BYTE_COUNT = producer_validator.CALLER_ROLE_BYTE_COUNT
OUTPUT_BYTE_COUNT = producer_validator.OUTPUT_BYTE_COUNT
CALLER_OUTPUT_OFFSET = producer_validator.CALLER_OUTPUT_OFFSET
FILTER_OBJECT_BYTE_COUNT = 0x400
MAXIMUM_CALLER_INSTRUCTION_COUNT = 768
MAXIMUM_FILTER_INSTRUCTION_COUNT = 4096
MAXIMUM_OPAQUE_CALLEE_COUNT = producer_validator.MAXIMUM_OPAQUE_CALLEE_COUNT
TRACE_CHECKPOINT_INSTRUCTION_INTERVAL = (
    producer_validator.TRACE_CHECKPOINT_INSTRUCTION_INTERVAL
)
TRACE_CHECKPOINT_BOUNDARY_INTERVAL = (
    producer_validator.TRACE_CHECKPOINT_BOUNDARY_INTERVAL
)

EXPECTED_CONFIGURATION = {
    "selectedMarkerInterval": producer_validator.TARGET_MARKER_INTERVAL,
    "selectedQualifiedHelperOrdinal": (producer_validator.TARGET_QUALIFIED_ORDINAL),
    "callerContinuationStartOffset": CALLER_CONTINUATION_START_OFFSET,
    "dynamicCallOffset": DYNAMIC_CALL_OFFSET,
    "dynamicReturnOffset": DYNAMIC_RETURN_OFFSET,
    "dynamicCallRawLittleEndianHex": DYNAMIC_CALL_RAW_LITTLE_ENDIAN_HEX,
    "targetDispatchOrdinal": TARGET_DISPATCH_ORDINAL,
    "expectedDispatchFunctions": EXPECTED_DISPATCH_FUNCTIONS,
    "filterFunction": FILTER_FUNCTION,
    "filterRelativeToPrepareLayer": FILTER_RELATIVE_TO_PREPARE_LAYER,
    "filterSymbolByteCount": FILTER_SYMBOL_BYTE_COUNT,
    "filterCodeSHA256": FILTER_CODE_SHA256,
    "openedScopeSpecifications": OPENED_SCOPE_SPECS,
    "callerOutputOffset": CALLER_OUTPUT_OFFSET,
    "stackByteCount": STACK_BYTE_COUNT,
    "callerRoleByteCount": CALLER_ROLE_BYTE_COUNT,
    "outputByteCount": OUTPUT_BYTE_COUNT,
    "filterObjectByteCount": FILTER_OBJECT_BYTE_COUNT,
    "maximumCallerInstructionCount": MAXIMUM_CALLER_INSTRUCTION_COUNT,
    "maximumFilterInstructionCount": MAXIMUM_FILTER_INSTRUCTION_COUNT,
    "maximumOpaqueCalleeCount": MAXIMUM_OPAQUE_CALLEE_COUNT,
    "traceCheckpointInstructionInterval": (TRACE_CHECKPOINT_INSTRUCTION_INTERVAL),
    "traceCheckpointBoundaryInterval": TRACE_CHECKPOINT_BOUNDARY_INTERVAL,
    "selectionRule": (
        "reuse marker interval 2 prepare_layer_mask ordinal 14 from the frozen "
        "output-blind helper/store/marker inventory; follow only its exact "
        "thread, x19 role, and frame; at prepare_layer+0x2864 require the "
        "frozen raw instruction and the exact first four dynamic function "
        "identities; select only ordinal 4 after its relative start, byte "
        "count, and complete code SHA-256 match; read no crop or output value"
    ),
    "steppingRule": (
        "with every breakpoint disabled and LLDB synchronous, retain complete "
        "scalar/SIMD registers, 256 stack bytes, 2048 caller role bytes, and "
        "512 destination bytes before and after every caller instruction and "
        "every instruction in the seven previously code-hashed FilterOp "
        "arithmetic scopes; step out of every other callee as an explicit "
        "boundary"
    ),
    "correlationRule": (
        "after the FilterOp returns and normal capture resumes, require its "
        "first rectangle to equal the independent sample-two producer on the "
        "same caller role bit for bit"
    ),
    "hardwareWatchpointsUsed": False,
    "cropValuesUsedForSelection": False,
    "outputValuesUsedForSelection": False,
}


mapping = holdout_analysis.mapping
sequence = holdout_analysis.sequence
integer = holdout_analysis.integer
payload = producer_validator.payload
memory = producer_validator.memory
registers = producer_validator.registers
frame = producer_validator.frame


def validate_opened_scopes(
    extension: Mapping[str, Any], trace: Mapping[str, Any], prepare_start: int
) -> dict[str, tuple[Mapping[str, Any], bytes]]:
    records = list(sequence(extension.get("openedScopes"), "opened scopes"))
    if len(records) != len(OPENED_SCOPE_SPECS):
        raise ValueError("opened scope count differs")
    prepare_module = mapping(
        mapping(trace.get("prepareLayer"), "prepare layer").get("module"),
        "prepare layer module",
    )
    opened: dict[str, tuple[Mapping[str, Any], bytes]] = {}
    for index, spec in enumerate(OPENED_SCOPE_SPECS):
        record = mapping(records[index], f"opened scope {index}")
        start = prepare_start + spec["relativeToPrepareLayer"]
        code = payload(
            record.get("hex"),
            spec["symbolByteCount"],
            f"{spec['name']} complete code",
        )
        digest = hashlib.sha256(code).hexdigest()
        module = mapping(record.get("module"), f"{spec['name']} module")
        if (
            record.get("name") != spec["name"]
            or record.get("function") != spec["function"]
            or record.get("relativeToPrepareLayer") != spec["relativeToPrepareLayer"]
            or record.get("symbolStart") != start
            or record.get("symbolEnd") != start + spec["symbolByteCount"]
            or record.get("symbolByteCount") != spec["symbolByteCount"]
            or record.get("expectedSHA256") != spec["codeSHA256"]
            or record.get("observedSHA256") != spec["codeSHA256"]
            or digest != spec["codeSHA256"]
            or module.get("valid") is not True
            or module.get("path") != prepare_module.get("path")
            or module.get("loadAddress") != prepare_module.get("loadAddress")
        ):
            raise ValueError(f"{spec['name']} opened scope differs")
        opened[spec["name"]] = (record, code)
    return opened


def validate_filter_identity(
    extension: Mapping[str, Any], trace: Mapping[str, Any], prepare_start: int
) -> tuple[Mapping[str, Any], bytes]:
    target = mapping(extension.get("filter"), "FilterOp identity")
    start = integer(target.get("symbolStart"), "FilterOp symbol start")
    code = payload(
        target.get("hex"), FILTER_SYMBOL_BYTE_COUNT, "FilterOp complete code"
    )
    digest = hashlib.sha256(code).hexdigest()
    entry = prepare_start + FILTER_RELATIVE_TO_PREPARE_LAYER
    call_digest = hashlib.sha256(
        bytes.fromhex(DYNAMIC_CALL_RAW_LITTLE_ENDIAN_HEX)
    ).hexdigest()
    if (
        target.get("function") != FILTER_FUNCTION
        or not isinstance(target.get("symbolName"), str)
        or not target.get("symbolName")
        or target.get("relativeToPrepareLayer") != FILTER_RELATIVE_TO_PREPARE_LAYER
        or target.get("entryPC") != entry
        or target.get("entryOffset") != 0
        or target.get("symbolRelativeToPrepareLayer")
        != FILTER_RELATIVE_TO_PREPARE_LAYER
        or start != entry
        or target.get("symbolEnd") != start + FILTER_SYMBOL_BYTE_COUNT
        or target.get("symbolByteCount") != FILTER_SYMBOL_BYTE_COUNT
        or target.get("expectedSHA256") != FILTER_CODE_SHA256
        or target.get("observedSHA256") != FILTER_CODE_SHA256
        or digest != FILTER_CODE_SHA256
        or target.get("callPC") != prepare_start + DYNAMIC_CALL_OFFSET
        or target.get("callReturnPC") != prepare_start + DYNAMIC_RETURN_OFFSET
        or target.get("callInstructionSHA256") != call_digest
    ):
        raise ValueError("FilterOp code identity differs")
    module = mapping(target.get("module"), "FilterOp module")
    prepare_module = mapping(
        mapping(trace.get("prepareLayer"), "prepare layer").get("module"),
        "prepare layer module",
    )
    if (
        module.get("valid") is not True
        or module.get("path") != prepare_module.get("path")
        or module.get("loadAddress") != prepare_module.get("loadAddress")
    ):
        raise ValueError("FilterOp module differs")
    return target, code


def validate_dispatches(
    extension: Mapping[str, Any],
    caller_states: list[dict[str, Any]],
    events: list[Mapping[str, Any]],
    boundaries: list[dict[str, Any]],
    prepare_start: int,
    filter_target: Mapping[str, Any],
) -> None:
    raw_dispatches = list(
        sequence(extension.get("dynamicDispatches"), "dynamic dispatches")
    )
    if len(raw_dispatches) != TARGET_DISPATCH_ORDINAL:
        raise ValueError("dynamic dispatch count differs")
    for index, raw in enumerate(raw_dispatches):
        dispatch = mapping(raw, f"dynamic dispatch {index}")
        ordinal = index + 1
        caller_index = EXPECTED_DISPATCH_CALLER_STATE_INDICES[index]
        caller = caller_states[caller_index]
        instruction = mapping(
            caller.get("instruction"), f"dynamic dispatch caller {index}"
        )
        expected_function = EXPECTED_DISPATCH_FUNCTIONS[index]
        if (
            dispatch.get("dispatchOrdinal") != ordinal
            or dispatch.get("callerStateIndex") != caller_index
            or dispatch.get("function") != expected_function
            or dispatch.get("entryPC") != caller.get("resultPC")
            or instruction.get("scopeOffset") != DYNAMIC_CALL_OFFSET
            or instruction.get("rawLittleEndianHex")
            != DYNAMIC_CALL_RAW_LITTLE_ENDIAN_HEX
            or caller.get("resultFunction") != expected_function
            or dispatch.get("cropValuesUsedForSelection") is not False
            or dispatch.get("outputValuesUsedForSelection") is not False
        ):
            raise ValueError("dynamic dispatch identity differs")
        event_index = next(
            i
            for i, event in enumerate(events)
            if event.get("kind") == "prepareLayer-instruction"
            and event.get("recordIndex") == caller_index
        )
        if ordinal < TARGET_DISPATCH_ORDINAL:
            following = events[event_index + 1]
            if following.get("kind") != "opaque-callee":
                raise ValueError("pre-FilterOp dispatch was not opaque")
            boundary = boundaries[
                integer(following.get("recordIndex"), "dispatch boundary index")
            ]
            if (
                mapping(boundary.get("entryFrame"), "dispatch entry").get("function")
                != expected_function
                or mapping(boundary.get("returnFrame"), "dispatch return").get(
                    "symbolOffset"
                )
                != DYNAMIC_RETURN_OFFSET
            ):
                raise ValueError("pre-FilterOp opaque boundary differs")
        else:
            following = events[event_index + 1]
            if (
                following.get("kind") != "producerCallee-instruction"
                or following.get("recordIndex") != 0
                or dispatch.get("symbolRelativeToPrepareLayer")
                != FILTER_RELATIVE_TO_PREPARE_LAYER
                or dispatch.get("symbolByteCount") != FILTER_SYMBOL_BYTE_COUNT
                or dispatch.get("symbolStart") != filter_target.get("symbolStart")
            ):
                raise ValueError("FilterOp dispatch opening differs")


def validate_execution(
    extension: Mapping[str, Any],
    filter_target: Mapping[str, Any],
    opened_scopes: Mapping[str, tuple[Mapping[str, Any], bytes]],
    prepare_start: int,
    output_address: int,
    role_base: int,
    initial_output: bytes,
    initial_role: bytes,
) -> dict[str, Any]:
    raw_callers = list(
        sequence(extension.get("callerContinuationStates"), "caller continuation")
    )
    raw_filter = list(
        sequence(extension.get("filterInstructionStates"), "FilterOp states")
    )
    raw_boundaries = list(
        sequence(extension.get("opaqueCalleeBoundaries"), "opaque boundaries")
    )
    raw_events = list(sequence(extension.get("executionEvents"), "events"))
    if (
        not 1 <= len(raw_callers) <= MAXIMUM_CALLER_INSTRUCTION_COUNT
        or not 1 <= len(raw_filter) <= MAXIMUM_FILTER_INSTRUCTION_COUNT
        or len(raw_boundaries) > MAXIMUM_OPAQUE_CALLEE_COUNT
        or len(raw_events) != len(raw_callers) + len(raw_filter) + len(raw_boundaries)
        or extension.get("finalCallerContinuationStateCount") != len(raw_callers)
        or extension.get("finalDynamicDispatchCount") != TARGET_DISPATCH_ORDINAL
        or extension.get("finalFilterInstructionStateCount") != len(raw_filter)
        or extension.get("finalOpaqueCalleeBoundaryCount") != len(raw_boundaries)
        or extension.get("finalExecutionEventCount") != len(raw_events)
    ):
        raise ValueError("FilterOp execution counts differ")

    callers = [
        producer_validator.validate_instruction_state(
            mapping(raw, f"caller state {index}"),
            index,
            "prepareLayer",
            prepare_start,
            None,
            output_address,
            role_base,
            f"caller state {index}",
        )
        for index, raw in enumerate(raw_callers)
    ]
    filters = []
    scope_counts = {name: 0 for name in opened_scopes}
    for index, raw in enumerate(raw_filter):
        state = mapping(raw, f"FilterOp state {index}")
        scope_name = state.get("openedScopeName")
        if scope_name not in opened_scopes:
            raise ValueError("FilterOp opened instruction scope differs")
        scope, scope_code = opened_scopes[scope_name]
        if state.get("openedScopeFunction") != scope.get("function") or state.get(
            "openedScopeCodeSHA256"
        ) != scope.get("observedSHA256"):
            raise ValueError("FilterOp opened instruction identity differs")
        filters.append(
            producer_validator.validate_instruction_state(
                state,
                index,
                "producerCallee",
                integer(scope.get("symbolStart"), f"{scope_name} start"),
                scope_code,
                output_address,
                role_base,
                f"FilterOp state {index}",
            )
        )
        scope_counts[scope_name] += 1
    boundaries = [
        producer_validator.validate_opaque_boundary(
            mapping(raw, f"opaque boundary {index}"),
            index,
            output_address,
            role_base,
            f"opaque boundary {index}",
        )
        for index, raw in enumerate(raw_boundaries)
    ]

    expected_indices = {
        "prepareLayer-instruction": 0,
        "producerCallee-instruction": 0,
        "opaque-callee": 0,
    }
    collections = {
        "prepareLayer-instruction": callers,
        "producerCallee-instruction": filters,
        "opaque-callee": boundaries,
    }
    previous_output = initial_output
    previous_role = initial_role
    previous_result_pc: int | None = None
    events = [mapping(raw, f"event {index}") for index, raw in enumerate(raw_events)]
    for event in events:
        kind = event.get("kind")
        if kind not in collections:
            raise ValueError("FilterOp event kind differs")
        expected_index = expected_indices[kind]
        if event.get("recordIndex") != expected_index:
            raise ValueError("FilterOp event index differs")
        record = collections[kind][expected_index]
        expected_indices[kind] += 1
        if (
            record["outputBefore"] != previous_output
            or record["roleBefore"] != previous_role
            or (previous_result_pc is not None and record["pc"] != previous_result_pc)
        ):
            raise ValueError("FilterOp execution chain differs")
        previous_output = record["outputAfter"]
        previous_role = record["roleAfter"]
        previous_result_pc = record["resultPC"]
    if any(expected_indices[kind] != len(collections[kind]) for kind in collections):
        raise ValueError("FilterOp event coverage differs")
    if (
        callers[0]["pc"] != prepare_start + CALLER_CONTINUATION_START_OFFSET
        or callers[0]["raw"] != bytes.fromhex("7fb201b9")
        or callers[-1]["pc"] != prepare_start + DYNAMIC_CALL_OFFSET
        or callers[-1]["raw"] != bytes.fromhex(DYNAMIC_CALL_RAW_LITTLE_ENDIAN_HEX)
        or callers[-1]["resultPC"] != filter_target.get("entryPC")
        or filters[0]["pc"] != filter_target.get("entryPC")
        or previous_result_pc != prepare_start + DYNAMIC_RETURN_OFFSET
    ):
        raise ValueError("FilterOp execution boundary differs")
    validate_dispatches(
        extension,
        raw_callers,
        events,
        raw_boundaries,
        prepare_start,
        filter_target,
    )
    return {
        "callerInstructionCount": len(callers),
        "filterInstructionCount": len(filters),
        "openedScopeInstructionCounts": scope_counts,
        "opaqueCalleeBoundaryCount": len(boundaries),
        "executionEventCount": len(events),
        "outputAtEntry": filters[0]["outputBefore"],
        "roleAtEntry": filters[0]["roleBefore"],
        "outputAtReturn": previous_output,
        "roleAtReturn": previous_role,
    }


def validate_entry_and_return(
    extension: Mapping[str, Any],
    filter_target: Mapping[str, Any],
    prepare_start: int,
    role_base: int,
    output_address: int,
    execution: Mapping[str, Any],
) -> tuple[bytes, bytes]:
    entry = mapping(extension.get("filterEntry"), "FilterOp entry")
    entry_frame = frame(entry.get("frame"), "FilterOp entry frame")
    entry_registers = registers(entry.get("registers"), "FilterOp entry registers")
    memory(
        entry.get("stack"),
        entry_registers["sp"],
        STACK_BYTE_COUNT,
        "FilterOp entry stack",
    )
    memory(
        entry.get("filterObject"),
        entry_registers["x0"],
        FILTER_OBJECT_BYTE_COUNT,
        "FilterOp object",
    )
    output_at_entry = memory(
        entry.get("output"), output_address, OUTPUT_BYTE_COUNT, "FilterOp entry output"
    )
    role_at_entry = memory(
        entry.get("callerRole"),
        role_base,
        CALLER_ROLE_BYTE_COUNT,
        "FilterOp entry role",
    )
    if (
        entry_frame.get("function") != FILTER_FUNCTION
        or entry_frame.get("pc") != filter_target.get("entryPC")
        or entry_registers["pc"] != filter_target.get("entryPC")
        or entry_registers["x1"] != output_address
        or entry_registers["x2"] not in (0, 1)
        or entry.get("cropValuesUsedForSelection") is not False
        or entry.get("outputValuesUsedForSelection") is not False
        or output_at_entry != execution["outputAtEntry"]
        or role_at_entry != execution["roleAtEntry"]
    ):
        raise ValueError("FilterOp entry differs")

    returned = mapping(extension.get("filterReturn"), "FilterOp return")
    return_frame = frame(returned.get("frame"), "FilterOp return frame")
    return_registers = registers(returned.get("registers"), "FilterOp return registers")
    memory(
        returned.get("stack"),
        return_registers["sp"],
        STACK_BYTE_COUNT,
        "FilterOp return stack",
    )
    output = memory(
        returned.get("output"),
        output_address,
        OUTPUT_BYTE_COUNT,
        "FilterOp return output",
    )
    role = memory(
        returned.get("callerRole"),
        role_base,
        CALLER_ROLE_BYTE_COUNT,
        "FilterOp return role",
    )
    if (
        return_frame.get("function") != crop_validator.PREPARE_LAYER_FUNCTION
        or return_frame.get("symbolStart") != prepare_start
        or return_frame.get("symbolOffset") != DYNAMIC_RETURN_OFFSET
        or return_registers["pc"] != prepare_start + DYNAMIC_RETURN_OFFSET
        or return_registers["x19"] != role_base
        or output != execution["outputAtReturn"]
        or role != execution["roleAtReturn"]
    ):
        raise ValueError("FilterOp return differs")
    return output, role


def validate(
    trace_path: Path,
    timeline_path: Path,
    inventory_path: Path,
    expected_geometry: str = EXPECTED_GEOMETRY,
) -> dict[str, Any]:
    if expected_geometry != EXPECTED_GEOMETRY:
        raise ValueError("FilterOp expected geometry differs")
    (
        trace,
        _timeline,
        opened_records,
        inventory,
        ordinal,
        inventory_sha,
    ) = producer_validator.validate_antecedent(
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
        trace.get("prepareLayerFilterMapBoundsExtension"), "FilterOp extension"
    )
    if (
        extension.get("prepareLayerFilterMapBoundsExtensionSchemaVersion")
        != EXTENSION_SCHEMA_VERSION
        or extension.get("configuration") != EXPECTED_CONFIGURATION
        or extension.get("status") != "finalized"
        or extension.get("statusBeforeFinalization")
        != "filter-map-bounds-instruction-trace-closed"
        or sequence(extension.get("failures"), "FilterOp failures")
        or extension.get("finalFailureCount") != 0
        or helper_extension.get("manualTraceStarted") is not True
        or helper_extension.get("manualTraceFinished") is not True
        or helper_extension.get("finalFailureCount") != 0
        or trace.get("prepareLayerCropProducerCalleeExtension") is not None
    ):
        raise ValueError("FilterOp extension identity differs")
    opened_scopes = validate_opened_scopes(extension, trace, prepare_start)
    filter_target, code = validate_filter_identity(extension, trace, prepare_start)
    opened_filter, opened_filter_code = opened_scopes["filterMapBounds"]
    if (
        code != opened_filter_code
        or filter_target.get("symbolStart") != opened_filter.get("symbolStart")
        or filter_target.get("observedSHA256") != opened_filter.get("observedSHA256")
    ):
        raise ValueError("FilterOp selected identity differs from opened scope")
    (
        thread_id,
        role_base,
        output_address,
        initial_output,
        initial_role,
        _helper_entry_registers,
    ) = producer_validator.validate_selected_caller(
        extension, helper_extension, prepare_start
    )
    execution = validate_execution(
        extension,
        filter_target,
        opened_scopes,
        prepare_start,
        output_address,
        role_base,
        initial_output,
        initial_role,
    )
    output, role = validate_entry_and_return(
        extension,
        filter_target,
        prepare_start,
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
    entry_rectangle = execution["outputAtEntry"][:32]
    return_rectangle = output[:32]
    changed_offsets = producer_validator.changed_qwords(
        entry_rectangle, return_rectangle
    )
    if (
        role_base != producer_role
        or output_address != producer_role + CALLER_OUTPUT_OFFSET
        or return_rectangle != producer
        or role[CALLER_OUTPUT_OFFSET : CALLER_OUTPUT_OFFSET + 32] != producer
        or entry_rectangle == producer
        or changed_offsets != [0, 8, 16, 24]
    ):
        raise ValueError("FilterOp output does not match structural producer")
    canonical_states = json.dumps(
        sequence(extension.get("filterInstructionStates"), "FilterOp states"),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    inventory_inputs = mapping(inventory.get("inputs"), "inventory inputs")
    return {
        "prepareLayerFilterMapBoundsValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            "prospective output-blind complete execution trace of the fourth "
            "prepare_layer+0x2864 dispatch; exact FilterOp identity selects "
            "the call and its returned first rectangle is correlated bit for "
            "bit to the independent sample-two producer"
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
            "markerInterval": producer_validator.TARGET_MARKER_INTERVAL,
            "qualifiedHelperOrdinal": ordinal,
            "threadID": thread_id,
            "callerRoleBase": role_base,
            "outputAddress": output_address,
            "dynamicCallOffset": DYNAMIC_CALL_OFFSET,
            "dispatchOrdinal": TARGET_DISPATCH_ORDINAL,
            "dispatchFunctions": EXPECTED_DISPATCH_FUNCTIONS,
            "cropValuesUsedForSelection": False,
            "outputValuesUsedForSelection": False,
        },
        "filter": {
            "function": FILTER_FUNCTION,
            "relativeToPrepareLayer": FILTER_RELATIVE_TO_PREPARE_LAYER,
            "symbolByteCount": FILTER_SYMBOL_BYTE_COUNT,
            "codeSHA256": FILTER_CODE_SHA256,
            "instructionStatesSHA256": hashlib.sha256(canonical_states).hexdigest(),
            "openedScopeCodeSHA256": {
                name: scope.get("observedSHA256")
                for name, (scope, _scope_code) in opened_scopes.items()
            },
            **{
                key: execution[key]
                for key in (
                    "callerInstructionCount",
                    "filterInstructionCount",
                    "openedScopeInstructionCounts",
                    "opaqueCalleeBoundaryCount",
                    "executionEventCount",
                )
            },
        },
        "structuralCorrelation": {
            "sampleIndex": 2,
            "producerRoleBase": producer_role,
            "producerOutputOffset": CALLER_OUTPUT_OFFSET,
            "entryF64": list(struct.unpack("<4d", entry_rectangle)),
            "entryHex": entry_rectangle.hex(),
            "producerF64": list(struct.unpack("<4d", producer)),
            "producerHex": producer.hex(),
            "changedQwordOffsets": changed_offsets,
            "filterReturnMatchesProducerBitForBit": True,
            "cropValuesUsedForSelection": False,
            "outputValuesUsedForSelection": False,
        },
        "sealedConclusion": {
            "completeOutputBlindInventoryRevalidated": True,
            "freshOrdinalFourteenSelectionRevalidated": True,
            "prepareLayerMaskOwnershipFalsificationPreserved": True,
            "staticPlusF5CCalleeHypothesisFalsificationPreserved": True,
            "filterMapBoundsCodeAndCompleteExecutionCaptured": True,
            "filterMapBoundsOwnsSelectedFloatingProducer": True,
            "exactFilterMapBoundsSemanticsDecoded": False,
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
