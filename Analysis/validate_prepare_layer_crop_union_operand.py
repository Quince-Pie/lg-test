#!/usr/bin/env python3
"""Validate exact crop-union operands joined to schema-7 marker records."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_prepare_layer_crop_transfer as crop_validator


VALIDATION_SCHEMA_VERSION = 1
EXTENSION_SCHEMA_VERSION = 1
UNION_CALL_NAME = "cropUnionBoundsCall"
UNION_CALL_OFFSET = 0x85DC
UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = "e1dbff97"
UNION_RETURN_NAME = "cropUnionBoundsReturn"
UNION_RETURN_OFFSET = 0x85E0
UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = "686241f9"
UNION_INPUT_ROLE_OFFSET = 0x620
UNION_DESTINATION_ROLE_OFFSET = 0x290
LAYER_SHAPES_WINDOW_OFFSET = 0xA0
LAYER_SHAPES_WINDOW_BYTE_COUNT = 0x30
UNION_INPUT_BYTE_COUNT = 0x20
UNION_TARGET_BYTE_COUNT = 0x20
MAXIMUM_UNION_CALL_HIT_COUNT = 16384
MAXIMUM_QUALIFIED_UNION_RECORD_COUNT = 4096
UNION_REGISTER_NAMES = (
    "x0",
    "x1",
    "x2",
    "x19",
    "x28",
    "x29",
    "sp",
    "pc",
    "cpsr",
)
EXPECTED_EXTENSION_CONFIGURATION = {
    "unionCallName": UNION_CALL_NAME,
    "unionCallOffset": UNION_CALL_OFFSET,
    "unionCallInstructionRawLittleEndianHex": (
        UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
    ),
    "unionReturnName": UNION_RETURN_NAME,
    "unionReturnOffset": UNION_RETURN_OFFSET,
    "unionReturnInstructionRawLittleEndianHex": (
        UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
    ),
    "unionInputRoleOffset": UNION_INPUT_ROLE_OFFSET,
    "unionDestinationRoleOffset": UNION_DESTINATION_ROLE_OFFSET,
    "layerShapesWindowOffset": LAYER_SHAPES_WINDOW_OFFSET,
    "layerShapesWindowByteCount": LAYER_SHAPES_WINDOW_BYTE_COUNT,
    "unionInputByteCount": UNION_INPUT_BYTE_COUNT,
    "unionTargetByteCount": UNION_TARGET_BYTE_COUNT,
    "maximumUnionCallHitCount": MAXIMUM_UNION_CALL_HIT_COUNT,
    "maximumQualifiedUnionRecordCount": MAXIMUM_QUALIFIED_UNION_RECORD_COUNT,
    "unionRegisterNames": list(UNION_REGISTER_NAMES),
    "callSelectionRule": (
        "retain every prepare_layer+0x85dc call with the exact direct normal "
        "transition caller chain and no intervention caller; do not inspect "
        "rectangle bytes before retaining"
    ),
    "markerCorrelationRule": (
        "within each interval ending at a qualified schema-7 marker, select "
        "the complete union call whose x0 destination equals marker x19 + "
        "0x290; do not inspect input or output values"
    ),
    "hardwareWatchpointsUsed": False,
    "instructionSteppingUsed": False,
}

type RectF64 = tuple[float, float, float, float]
type RectI32 = tuple[int, int, int, int]


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} is not an object")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        raise ValueError(f"{label} is not an array")
    return value


def integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} is not an integer")
    return value


def finite_rect(value: Any, label: str) -> RectF64:
    raw = sequence(value, label)
    if len(raw) != 4:
        raise ValueError(f"{label} component count differs")
    result = tuple(float(component) for component in raw)
    if not all(math.isfinite(component) for component in result):
        raise ValueError(f"{label} is not finite")
    return result  # type: ignore[return-value]


def f64_rect(payload: bytes, label: str) -> RectF64:
    if len(payload) != 32:
        raise ValueError(f"{label} byte count differs")
    result = struct.unpack("<4d", payload)
    if not all(math.isfinite(component) for component in result):
        raise ValueError(f"{label} is not finite")
    if result[2] < 0 or result[3] < 0:
        raise ValueError(f"{label} has a negative extent")
    return result


def i32_rect(payload: bytes, offset: int, label: str) -> RectI32:
    if offset < 0 or offset + 16 > len(payload):
        raise ValueError(f"{label} lies outside its payload")
    return struct.unpack_from("<4i", payload, offset)


def same_f64_rect(left: RectF64, right: RectF64) -> bool:
    return struct.pack("<4d", *left) == struct.pack("<4d", *right)


def replay_union(destination: RectF64, value: RectF64) -> RectF64:
    if value[2] <= 0 or value[3] <= 0:
        return destination
    if destination[2] <= 0 or destination[3] <= 0:
        return value
    destination_far_x = destination[0] + destination[2]
    destination_far_y = destination[1] + destination[3]
    value_far_x = value[0] + value[2]
    value_far_y = value[1] + value[3]
    origin_x = min(destination[0], value[0])
    origin_y = min(destination[1], value[1])
    far_x = max(destination_far_x, value_far_x)
    far_y = max(destination_far_y, value_far_y)
    return (origin_x, origin_y, far_x - origin_x, far_y - origin_y)


def transform_child(
    carrier_position: Sequence[Any], child: RectF64, canvas_height: float
) -> RectF64:
    if len(carrier_position) != 2:
        raise ValueError("carrier position component count differs")
    position_x = float(carrier_position[0])
    position_y = float(carrier_position[1])
    return (
        position_x + child[0],
        (canvas_height - position_y) - (child[1] + child[3]),
        child[2],
        child[3],
    )


def backtrace_functions(value: Any) -> list[str]:
    return [
        str(mapping(record, "backtrace record").get("function") or "")
        for record in sequence(value, "backtrace")
    ]


def direct_timeline_caller(functions: Sequence[str]) -> bool:
    return all(
        any(fragment in function for function in functions)
        for fragment in crop_validator.REQUIRED_CALLER_FRAGMENTS
    ) and not any(
        fragment in function
        for function in functions
        for fragment in crop_validator.EXCLUDED_CALLER_FRAGMENTS
    )


def validate_union_record(
    raw: Any, record_index: int, prepare_start: int
) -> dict[str, Any]:
    record = mapping(raw, f"union record {record_index}")
    if record.get("recordIndex") != record_index:
        raise ValueError("union record index differs")
    call_sequence = integer(record.get("callEventSequence"), "call sequence")
    return_sequence = integer(
        record.get("returnEventSequence"), "return sequence"
    )
    if call_sequence >= return_sequence or record.get("complete") is not True:
        raise ValueError("union call/return pairing differs")
    frame = mapping(record.get("frame"), "union frame")
    if (
        frame.get("function") != crop_validator.PREPARE_LAYER_FUNCTION
        or frame.get("symbolStart") != prepare_start
        or frame.get("symbolEnd")
        != prepare_start + crop_validator.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        or frame.get("symbolOffset") != UNION_CALL_OFFSET
        or frame.get("pc") != prepare_start + UNION_CALL_OFFSET
        or record.get("returnPC") != prepare_start + UNION_RETURN_OFFSET
    ):
        raise ValueError("union frame identity differs")
    backtrace = sequence(record.get("backtrace"), "backtrace")
    functions = backtrace_functions(backtrace)
    if not direct_timeline_caller(functions):
        raise ValueError("union record caller chain differs")
    structural_depth = sum(
        mapping(raw_frame, "backtrace frame").get("function")
        == crop_validator.PREPARE_LAYER_FUNCTION
        and mapping(raw_frame, "backtrace frame").get("symbolStart")
        == prepare_start
        and mapping(raw_frame, "backtrace frame").get("symbolEnd")
        == prepare_start + crop_validator.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        for raw_frame in backtrace
    )
    if record.get("prepareRecursionDepth") != structural_depth:
        raise ValueError("union record recursion depth differs")

    registers = crop_validator.register_values(
        record.get("registers"), UNION_REGISTER_NAMES, "union registers"
    )
    identity = mapping(record.get("frameIdentity"), "union frame identity")
    expected_identity = {
        "threadID": record.get("threadID"),
        "roleBase": registers["x19"],
        "framePointer": registers["x29"],
        "layerShapesBase": registers["x28"],
        "destination": registers["x0"],
        "input": registers["x1"],
    }
    if dict(identity) != expected_identity:
        raise ValueError("union register identity differs")
    if registers["x1"] != registers["x19"] + UNION_INPUT_ROLE_OFFSET:
        raise ValueError("union input pointer differs")
    if registers["x2"] & 0xFFFF_FFFF:
        raise ValueError("union propagation gate differs")

    role_address, role = crop_validator.memory_snapshot(
        record.get("roleState"),
        crop_validator.ROLE_STATE_BYTE_COUNT,
        "union role state",
        registers["x19"],
    )
    layer_address, layer = crop_validator.memory_snapshot(
        record.get("layerShapesState"),
        LAYER_SHAPES_WINDOW_BYTE_COUNT,
        "union LayerShapes state",
        registers["x28"] + LAYER_SHAPES_WINDOW_OFFSET,
    )
    input_address, input_payload = crop_validator.memory_snapshot(
        record.get("inputState"),
        UNION_INPUT_BYTE_COUNT,
        "union input state",
        registers["x1"],
    )
    before_address, before_payload = crop_validator.memory_snapshot(
        record.get("targetBefore"),
        UNION_TARGET_BYTE_COUNT,
        "union target before",
        registers["x0"],
    )
    after_address, after_payload = crop_validator.memory_snapshot(
        record.get("targetAfter"),
        UNION_TARGET_BYTE_COUNT,
        "union target after",
        registers["x0"],
    )
    if not (
        role_address == registers["x19"]
        and layer_address == registers["x28"] + LAYER_SHAPES_WINDOW_OFFSET
        and input_address == registers["x1"]
        and before_address == after_address == registers["x0"]
    ):
        raise ValueError("union memory address identity differs")

    previous_i32 = i32_rect(layer, 0, "preceding LayerShapes rectangle")
    nested_i32 = i32_rect(layer, 16, "nested LayerShapes rectangle")
    enclosure_i32 = i32_rect(layer, 32, "enclosed LayerShapes rectangle")
    if nested_i32[2] <= 0 or nested_i32[3] <= 0:
        raise ValueError("nested LayerShapes rectangle is empty")
    expected_input = struct.pack(
        "<4d", *(float(component) for component in nested_i32)
    )
    if input_payload != expected_input:
        raise ValueError("union signed-int conversion differs")
    if role[
        UNION_INPUT_ROLE_OFFSET : UNION_INPUT_ROLE_OFFSET + UNION_INPUT_BYTE_COUNT
    ] != input_payload:
        raise ValueError("union role input bytes differ")

    return {
        "recordIndex": record_index,
        "callEventSequence": call_sequence,
        "returnEventSequence": return_sequence,
        "prepareRecursionDepth": structural_depth,
        "destinationAddress": registers["x0"],
        "roleBase": registers["x19"],
        "layerShapesBase": registers["x28"],
        "previousLayerShapesI32": list(previous_i32),
        "nestedInputI32": list(nested_i32),
        "integerEnclosureI32": list(enclosure_i32),
        "inputF64": list(f64_rect(input_payload, "union input")),
        "targetBeforeF64": list(f64_rect(before_payload, "union target before")),
        "targetAfterF64": list(f64_rect(after_payload, "union target after")),
        "role": crop_validator.decode_role(role),
    }


def validate(trace_path: Path, timeline_path: Path, expected_geometry: str):
    base_result = crop_validator.validate(
        trace_path, timeline_path, expected_geometry
    )
    trace = mapping(
        crop_validator.load_json(trace_path, "trace"), "trace"
    )
    extension = mapping(
        trace.get("cropUnionOperandExtension"), "crop union extension"
    )
    if (
        extension.get("cropUnionOperandExtensionSchemaVersion")
        != EXTENSION_SCHEMA_VERSION
        or extension.get("configuration") != EXPECTED_EXTENSION_CONFIGURATION
        or extension.get("status") != "finalized"
        or extension.get("statusBeforeFinalization")
        != "crop-union-breakpoints-active"
    ):
        raise ValueError("crop union extension identity differs")

    prepare = mapping(trace.get("prepareLayer"), "prepare layer")
    prepare_start = integer(prepare.get("symbolStart"), "prepare layer start")
    if extension.get("prepareLayerSymbolStart") != prepare_start:
        raise ValueError("crop union prepare layer start differs")
    expected_call_digest = hashlib.sha256(
        bytes.fromhex(UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX)
    ).hexdigest()
    expected_return_digest = hashlib.sha256(
        bytes.fromhex(UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX)
    ).hexdigest()
    if (
        integer(extension.get("unionCallBreakpointID"), "union call breakpoint")
        <= 0
        or integer(
            extension.get("unionReturnBreakpointID"), "union return breakpoint"
        )
        <= 0
        or extension.get("unionCallInstructionSHA256") != expected_call_digest
        or extension.get("unionReturnInstructionSHA256")
        != expected_return_digest
    ):
        raise ValueError("crop union breakpoint code identity differs")
    records = sequence(extension.get("unionRecords"), "union records")
    if not 32 <= len(records) <= MAXIMUM_QUALIFIED_UNION_RECORD_COUNT:
        raise ValueError("qualified union record bounds differ")
    decoded = [
        validate_union_record(raw, index, prepare_start)
        for index, raw in enumerate(records)
    ]
    event_sequences = [
        sequence_number
        for record in decoded
        for sequence_number in (
            record["callEventSequence"],
            record["returnEventSequence"],
        )
    ]
    if sorted(event_sequences) != list(range(1, len(event_sequences) + 1)):
        raise ValueError("crop union event sequence differs")

    rejected_calls = integer(
        extension.get("finalRejectedUnionCallCount"), "rejected union calls"
    )
    rejected_returns = integer(
        extension.get("finalRejectedUnionReturnCount"), "rejected union returns"
    )
    rejection_groups = sequence(
        extension.get("rejectionGroups"), "union rejection groups"
    )
    grouped_rejections = 0
    for raw_group in rejection_groups:
        group = mapping(raw_group, "union rejection group")
        if group.get("reason") != "caller-chain-excluded":
            raise ValueError("union rejection reason differs")
        integer(group.get("prepareRecursionDepth"), "rejection recursion depth")
        grouped_rejections += integer(group.get("hitCount"), "rejection hit count")
    if (
        rejected_calls != rejected_returns
        or grouped_rejections != rejected_calls
        or extension.get("finalQualifiedUnionRecordCount") != len(records)
        or extension.get("finalCompleteUnionRecordCount") != len(records)
        or extension.get("finalEventSequence") != len(records) * 2
        or extension.get("finalUnionCallHitCount")
        != len(records) + rejected_calls
        or extension.get("finalUnionReturnHitCount")
        != len(records) + rejected_returns
    ):
        raise ValueError("crop union final accounting differs")

    links = sequence(extension.get("markerLinks"), "marker links")
    marker_records = sequence(trace.get("qualifiedRecords"), "marker records")
    public_records = sequence(base_result.get("records"), "public records")
    if (
        len(links) != 32
        or extension.get("finalMarkerLinkCount") != 32
        or len(marker_records) != 32
        or len(public_records) != 32
    ):
        raise ValueError("crop union marker-link inventory differs")

    canvas_height = float(
        mapping(base_result.get("geometry"), "geometry").get("windowHeight")
    )
    joined = []
    previous_end = 0
    for index, (raw_link, raw_marker, raw_public) in enumerate(
        zip(links, marker_records, public_records, strict=True)
    ):
        link = mapping(raw_link, f"marker link {index}")
        marker = mapping(raw_marker, f"marker record {index}")
        public = mapping(raw_public, f"public record {index}")
        start = integer(link.get("startUnionRecordIndex"), "link start")
        end = integer(link.get("endUnionRecordIndexExclusive"), "link end")
        destination = integer(link.get("destinationAddress"), "link destination")
        marker_identity = mapping(marker.get("frameIdentity"), "marker identity")
        expected_destination = (
            integer(marker_identity.get("roleBase"), "marker role base")
            + UNION_DESTINATION_ROLE_OFFSET
        )
        matching = list(
            sequence(link.get("matchingUnionRecordIndices"), "matching records")
        )
        recomputed = [
            record["recordIndex"]
            for record in decoded[start:end]
            if record["destinationAddress"] == expected_destination
        ]
        embedded = mapping(
            marker.get("cropUnionOperandWindow"), "embedded union window"
        )
        if (
            link.get("markerRecordIndex") != index
            or link.get("markerCallbackSequence") != marker.get("callbackSequence")
            or start != previous_end
            or not start <= end <= len(decoded)
            or destination != expected_destination
            or matching != recomputed
            or len(matching) != 1
            or embedded.get("startRecordIndex") != start
            or embedded.get("endRecordIndexExclusive") != end
            or embedded.get("destinationAddress") != destination
            or embedded.get("matchingRecordIndices") != matching
        ):
            raise ValueError("crop union destination correlation differs")
        selected = decoded[matching[0]]
        private = mapping(public.get("private"), "public private record")
        child = finite_rect(private.get("recursiveChildF64"), "recursive child")
        transformed = transform_child(
            sequence(public.get("carrierPosition"), "carrier position"),
            child,
            canvas_height,
        )
        before = finite_rect(selected["targetBeforeF64"], "target before")
        union_input = finite_rect(selected["inputF64"], "union input")
        after = finite_rect(selected["targetAfterF64"], "target after")
        observed = finite_rect(private.get("aggregateF64"), "observed aggregate")
        replayed = replay_union(before, union_input)
        if (
            not same_f64_rect(before, transformed)
            or not same_f64_rect(after, observed)
            or not same_f64_rect(replayed, after)
        ):
            raise ValueError("crop union semantic replay differs")
        joined.append(
            {
                "normalRenderOrdinal": index + 1,
                "sampleIndex": public.get("sampleIndex"),
                "markerRecordIndex": index,
                "unionRecordIndex": selected["recordIndex"],
                "prepareRecursionDepth": public.get("prepareRecursionDepth"),
                "carrierPosition": public.get("carrierPosition"),
                "transformedGlassDODF64": list(transformed),
                "nestedInputI32": selected["nestedInputI32"],
                "nestedInputF64": selected["inputF64"],
                "targetBeforeF64": selected["targetBeforeF64"],
                "targetAfterF64": selected["targetAfterF64"],
                "constructionRole": selected["role"],
                "previousLayerShapesI32": selected["previousLayerShapesI32"],
                "integerEnclosureI32": selected["integerEnclosureI32"],
            }
        )
        previous_end = end

    trailing = len(decoded) - previous_end
    if (
        extension.get("finalLinkedUnionRecordCount") != 32
        or extension.get("finalTrailingUnionRecordCount") != trailing
        or trailing != 0
    ):
        raise ValueError("crop union trailing record accounting differs")

    return {
        "prepareLayerCropUnionOperandValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            "prospective destination-correlated exact nested LayerShapes "
            "operand capture; all selected floating unions replay bit for bit, "
            "while the general operand-production law and product parity remain "
            "sealed"
        ),
        "conclusion": "success",
        "prospectiveCaptureIntegrityGatePassed": True,
        "inputs": base_result["inputs"],
        "geometry": base_result["geometry"],
        "recordCount": len(joined),
        "componentCount": len(joined) * 4,
        "unionRecordCount": len(decoded),
        "rejectedUnionCallCount": rejected_calls,
        "records": joined,
        "sealedConclusion": {
            "schemaSevenMarkerValidationRepassed": True,
            "exactUnionCallAndReturnCodePassed": True,
            "cropIndependentUnionCallSelectionPassed": True,
            "destinationOnlyMarkerCorrelationPassed": True,
            "oneExactNestedOperandPerNormalReplayPassed": True,
            "signedIntegerToBinary64ConversionPassed": True,
            "allSelectedFloatingUnionsReplayedBitForBit": True,
            "allFinalAggregateComponentsReplayedBitForBit": True,
            "generalCropPolicyRecovered": False,
            "unseenGeometryHoldoutPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--expected-geometry", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        result = validate(
            arguments.trace, arguments.timeline, arguments.expected_geometry
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
