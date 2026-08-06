#!/usr/bin/env python3
"""Validate the opened SDF map-bounds instruction diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import analyze_prepare_layer_crop_policy_holdout_callback_retry as holdout
import validate_prepare_layer_crop_producer_callee as producer
import validate_prepare_layer_crop_transfer as crop_validator
import validate_prepare_layer_filter_map_bounds_regular_diagnostic as regular


VALIDATION_SCHEMA_VERSION = 1
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


EXPECTED_CONFIGURATION = {
    "material": "regular",
    "appearance": "light",
    "direction": "materialize",
    "geometry": regular.EXPECTED_GEOMETRY,
    "selectedSampleIndex": 2,
    "selectedMarkerInterval": 2,
    "selectedQualifiedHelperOrdinal": 14,
    "dynamicCallOffset": regular.frozen.DYNAMIC_CALL_OFFSET,
    "dynamicReturnOffset": regular.frozen.DYNAMIC_RETURN_OFFSET,
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
}


def validate_target(
    raw: Any, trace: Mapping[str, Any], prepare_start: int
) -> tuple[Mapping[str, Any], bytes]:
    target = holdout.mapping(raw, "SDF target")
    start = prepare_start + SDF_RELATIVE_TO_PREPARE_LAYER
    code = producer.payload(target.get("hex"), SDF_SYMBOL_BYTE_COUNT, "SDF code")
    digest = hashlib.sha256(code).hexdigest()
    module = holdout.mapping(target.get("module"), "SDF module")
    prepare_module = holdout.mapping(
        holdout.mapping(trace.get("prepareLayer"), "prepare layer").get("module"),
        "prepare layer module",
    )
    if (
        target.get("function") != SDF_FUNCTION
        or not isinstance(target.get("symbolName"), str)
        or not target.get("symbolName")
        or target.get("relativeToPrepareLayer") != SDF_RELATIVE_TO_PREPARE_LAYER
        or target.get("entryPC") != start
        or target.get("symbolStart") != start
        or target.get("symbolEnd") != start + SDF_SYMBOL_BYTE_COUNT
        or target.get("symbolByteCount") != SDF_SYMBOL_BYTE_COUNT
        or target.get("expectedSHA256") is not None
        or target.get("observedSHA256") != digest
        or module.get("valid") is not True
        or module.get("path") != prepare_module.get("path")
        or module.get("loadAddress") != prepare_module.get("loadAddress")
    ):
        raise ValueError("SDF target identity differs")
    return target, code


def validate_entry(
    raw: Any,
    target: Mapping[str, Any],
    output_address: int,
    role_base: int,
) -> tuple[bytes, bytes, Mapping[str, int]]:
    entry = holdout.mapping(raw, "SDF entry")
    entry_frame = producer.frame(entry.get("frame"), "SDF entry frame")
    registers = producer.registers(entry.get("registers"), "SDF entry registers")
    producer.memory(
        entry.get("stack"), registers["sp"], producer.STACK_BYTE_COUNT, "SDF stack"
    )
    producer.memory(
        entry.get("object"), registers["x0"], SDF_OBJECT_BYTE_COUNT, "SDF object"
    )
    producer.memory(
        entry.get("argumentX3"),
        registers["x3"],
        SDF_ARGUMENT_BYTE_COUNT,
        "SDF x3 argument",
    )
    output = producer.memory(
        entry.get("output"), output_address, producer.OUTPUT_BYTE_COUNT, "SDF output"
    )
    role = producer.memory(
        entry.get("callerRole"),
        role_base,
        producer.CALLER_ROLE_BYTE_COUNT,
        "SDF caller role",
    )
    if (
        entry_frame.get("function") != SDF_FUNCTION
        or entry_frame.get("pc") != target.get("entryPC")
        or registers["pc"] != target.get("entryPC")
        or registers["x1"] != output_address
        or registers["x2"] not in (0, 1)
        or output
        != role[
            producer.CALLER_OUTPUT_OFFSET : producer.CALLER_OUTPUT_OFFSET
            + producer.OUTPUT_BYTE_COUNT
        ]
    ):
        raise ValueError("SDF entry differs")
    return output, role, registers


def validate_opaque_identity(raw: Any) -> None:
    target = holdout.mapping(raw, "SDF opaque callee target")
    byte_count = holdout.integer(target.get("symbolByteCount"), "opaque byte count")
    if not 0 < byte_count <= 0x10000:
        raise ValueError("SDF opaque callee byte count differs")
    code = producer.payload(target.get("hex"), byte_count, "SDF opaque callee code")
    digest = hashlib.sha256(code).hexdigest()
    start = holdout.integer(target.get("symbolStart"), "opaque start")
    entry = holdout.integer(target.get("entryPC"), "opaque entry")
    module = holdout.mapping(target.get("module"), "opaque module")
    if (
        not isinstance(target.get("function"), str)
        or not target.get("function")
        or not isinstance(target.get("symbolName"), str)
        or not target.get("symbolName")
        or not start <= entry < start + byte_count
        or target.get("entryOffset") != entry - start
        or target.get("symbolEnd") != start + byte_count
        or target.get("expectedSHA256") is not None
        or target.get("observedSHA256") != digest
        or module.get("valid") is not True
        or not isinstance(module.get("path"), str)
        or not module.get("path")
        or not isinstance(module.get("loadAddress"), int)
    ):
        raise ValueError("SDF opaque callee identity differs")


def validate_execution(
    diagnostic: Mapping[str, Any],
    code: bytes,
    start: int,
    output_address: int,
    role_base: int,
    entry_output: bytes,
    entry_role: bytes,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, bytes, bytes]:
    states = list(
        holdout.sequence(diagnostic.get("instructionStates"), "SDF instructions")
    )
    raw_boundaries = list(
        holdout.sequence(
            diagnostic.get("opaqueCalleeBoundaries"), "SDF opaque boundaries"
        )
    )
    events = list(
        holdout.sequence(diagnostic.get("executionEvents"), "SDF execution events")
    )
    if (
        not 1 <= len(states) <= MAXIMUM_SDF_INSTRUCTION_COUNT
        or len(raw_boundaries) > MAXIMUM_SDF_OPAQUE_CALLEE_COUNT
        or len(events) != len(states) + len(raw_boundaries)
        or diagnostic.get("finalInstructionStateCount") != len(states)
        or diagnostic.get("finalOpaqueCalleeBoundaryCount") != len(raw_boundaries)
        or diagnostic.get("finalExecutionEventCount") != len(events)
    ):
        raise ValueError("SDF execution counts differ")
    decoded_states = [
        producer.validate_instruction_state(
            holdout.mapping(raw, f"SDF state {index}"),
            index,
            "sdfMapBounds",
            start,
            code,
            output_address,
            role_base,
            f"SDF state {index}",
        )
        for index, raw in enumerate(states)
    ]
    decoded_boundaries = []
    for index, raw in enumerate(raw_boundaries):
        boundary = holdout.mapping(raw, f"SDF opaque boundary {index}")
        validate_opaque_identity(boundary.get("callee"))
        decoded_boundaries.append(
            producer.validate_opaque_boundary(
                boundary,
                index,
                output_address,
                role_base,
                f"SDF opaque boundary {index}",
            )
        )

    collections = {
        "sdf-instruction": decoded_states,
        "opaque-callee": decoded_boundaries,
    }
    expected_indices = {kind: 0 for kind in collections}
    previous_output = entry_output
    previous_role = entry_role
    previous_pc = start
    for event_index, raw_event in enumerate(events):
        event = holdout.mapping(raw_event, f"SDF execution event {event_index}")
        kind = event.get("kind")
        if kind not in collections:
            raise ValueError("SDF execution event kind differs")
        expected_index = expected_indices[kind]
        if event.get("recordIndex") != expected_index:
            raise ValueError("SDF execution event index differs")
        record = collections[kind][expected_index]
        expected_indices[kind] += 1
        if (
            record["pc"] != previous_pc
            or record["outputBefore"] != previous_output
            or record["roleBefore"] != previous_role
        ):
            raise ValueError("SDF instruction chain differs")
        previous_pc = record["resultPC"]
        previous_output = record["outputAfter"]
        previous_role = record["roleAfter"]
    if any(expected_indices[kind] != len(collections[kind]) for kind in collections):
        raise ValueError("SDF execution event coverage differs")
    return (
        decoded_states,
        decoded_boundaries,
        previous_pc,
        previous_output,
        previous_role,
    )


def validate_return(
    raw: Any,
    prepare_start: int,
    output_address: int,
    role_base: int,
    expected_output: bytes,
    expected_role: bytes,
) -> None:
    returned = holdout.mapping(raw, "SDF return")
    return_frame = producer.frame(returned.get("frame"), "SDF return frame")
    registers = producer.registers(returned.get("registers"), "SDF return registers")
    producer.memory(
        returned.get("stack"),
        registers["sp"],
        producer.STACK_BYTE_COUNT,
        "SDF return stack",
    )
    output = producer.memory(
        returned.get("output"),
        output_address,
        producer.OUTPUT_BYTE_COUNT,
        "SDF return output",
    )
    role = producer.memory(
        returned.get("callerRole"),
        role_base,
        producer.CALLER_ROLE_BYTE_COUNT,
        "SDF return role",
    )
    expected_pc = prepare_start + regular.frozen.DYNAMIC_RETURN_OFFSET
    if (
        return_frame.get("function") != crop_validator.PREPARE_LAYER_FUNCTION
        or return_frame.get("pc") != expected_pc
        or return_frame.get("symbolOffset") != regular.frozen.DYNAMIC_RETURN_OFFSET
        or registers["pc"] != expected_pc
        or registers["x19"] != role_base
        or output != expected_output
        or role != expected_role
    ):
        raise ValueError("SDF return differs")


def validate(
    trace_path: Path, timeline_path: Path, inventory_path: Path
) -> dict[str, Any]:
    regular_result = regular.validate(trace_path, timeline_path, inventory_path)
    trace = holdout.mapping(crop_validator.load_json(trace_path, "trace"), "trace")
    prepare_start = holdout.integer(
        holdout.mapping(trace.get("prepareLayer"), "prepare layer").get("symbolStart"),
        "prepare layer start",
    )
    extension = holdout.mapping(
        trace.get("prepareLayerFilterMapBoundsExtension"), "Filter extension"
    )
    diagnostic = holdout.mapping(
        extension.get("sdfMapBoundsDiagnostic"), "SDF diagnostic"
    )
    if (
        diagnostic.get("prepareLayerSDFMapBoundsDiagnosticSchemaVersion")
        != DIAGNOSTIC_SCHEMA_VERSION
        or diagnostic.get("configuration") != EXPECTED_CONFIGURATION
        or diagnostic.get("status") != "finalized"
        or diagnostic.get("statusBeforeFinalization") != "sdf-instruction-trace-closed"
        or holdout.sequence(diagnostic.get("failures"), "SDF failures")
        or diagnostic.get("finalFailureCount") != 0
    ):
        raise ValueError("SDF diagnostic identity differs")

    target, code = validate_target(diagnostic.get("target"), trace, prepare_start)
    selection = holdout.mapping(regular_result.get("selection"), "selection")
    output_address = holdout.integer(selection.get("outputAddress"), "output address")
    role_base = holdout.integer(selection.get("callerRoleBase"), "role base")
    entry_output, entry_role, _entry_registers = validate_entry(
        diagnostic.get("entry"), target, output_address, role_base
    )
    (
        decoded,
        decoded_sdf_boundaries,
        final_pc,
        final_output,
        final_role,
    ) = validate_execution(
        diagnostic,
        code,
        holdout.integer(target.get("symbolStart"), "SDF start"),
        output_address,
        role_base,
        entry_output,
        entry_role,
    )
    expected_return_pc = prepare_start + regular.frozen.DYNAMIC_RETURN_OFFSET
    if final_pc != expected_return_pc:
        raise ValueError("SDF instruction return differs")
    validate_return(
        diagnostic.get("return"),
        prepare_start,
        output_address,
        role_base,
        final_output,
        final_role,
    )

    boundary_index = holdout.integer(
        diagnostic.get("opaqueBoundaryIndex"), "SDF opaque boundary index"
    )
    boundaries = holdout.sequence(
        extension.get("opaqueCalleeBoundaries"), "Filter opaque boundaries"
    )
    if not 0 <= boundary_index < len(boundaries):
        raise ValueError("SDF opaque boundary index differs")
    boundary = producer.validate_opaque_boundary(
        holdout.mapping(boundaries[boundary_index], "SDF opaque boundary"),
        boundary_index,
        output_address,
        role_base,
        "SDF opaque boundary",
    )
    if (
        boundary["pc"] != target.get("entryPC")
        or boundary["resultPC"] != expected_return_pc
        or boundary["outputBefore"] != entry_output
        or boundary["roleBefore"] != entry_role
        or boundary["outputAfter"] != final_output
        or boundary["roleAfter"] != final_role
    ):
        raise ValueError("SDF synthetic opaque boundary differs")

    entry_rectangle = entry_output[:32]
    return_rectangle = final_output[:32]
    changed_offsets = producer.changed_qwords(entry_rectangle, return_rectangle)
    if changed_offsets != [0, 8, 16, 24]:
        raise ValueError("SDF rectangle change differs")
    canonical_states = json.dumps(
        holdout.sequence(diagnostic.get("instructionStates"), "SDF states"),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    result = dict(regular_result)
    result["prepareLayerSDFMapBoundsDiagnosticValidationSchemaVersion"] = (
        VALIDATION_SCHEMA_VERSION
    )
    result["classification"] = (
        "prospective output-blind SDFOp instruction diagnostic layered over the "
        "authenticated regular FilterOp capture; the SDF code hash and arithmetic "
        "are discovery evidence and carry no transfer or production authority"
    )
    result["sdf"] = {
        "function": SDF_FUNCTION,
        "relativeToPrepareLayer": SDF_RELATIVE_TO_PREPARE_LAYER,
        "symbolByteCount": SDF_SYMBOL_BYTE_COUNT,
        "discoveredCodeSHA256": target.get("observedSHA256"),
        "instructionCount": len(decoded),
        "opaqueCalleeBoundaryCount": len(decoded_sdf_boundaries),
        "instructionStatesSHA256": hashlib.sha256(canonical_states).hexdigest(),
        "opaqueBoundaryIndex": boundary_index,
        "entryF64": list(struct.unpack("<4d", entry_rectangle)),
        "entryHex": entry_rectangle.hex(),
        "returnF64": list(struct.unpack("<4d", return_rectangle)),
        "returnHex": return_rectangle.hex(),
        "changedQwordOffsets": changed_offsets,
        "completeInstructionChainValidated": True,
        "cropValuesUsedForSelection": False,
        "outputValuesUsedForSelection": False,
    }
    sealed = result["sealedConclusion"]
    sealed["sdfMapBoundsDiagnosticPassed"] = True
    sealed["sdfCodeHashProspectivelyFrozen"] = False
    sealed["completeProfileMatrixPassed"] = False
    sealed["productionShaderAuthorized"] = False
    sealed["liquidGlassParityEstablished"] = False
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.trace, arguments.timeline, arguments.inventory)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
