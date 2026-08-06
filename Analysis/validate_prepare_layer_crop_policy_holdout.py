#!/usr/bin/env python3
"""Validate an unseen, exact public-state crop-policy holdout."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_prepare_layer_crop_union_operand_matrix as crop_analysis
import validate_prepare_layer_crop_transfer as crop_validator
import validate_prepare_layer_crop_union_operand as union_validator


VALIDATION_SCHEMA_VERSION = 1
EXTENSION_SCHEMA_VERSION = 1
STORE_NAME = "nestedCropStore"
STORE_OFFSET = 0x55C0
STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = "802f803d"
ROLE_WORKING_CROP_OFFSET = 0x270
ROLE_FLOAT_INPUT_OFFSET = 0x290
LAYER_SHAPES_NESTED_OFFSET = 0xB0
WORKING_CROP_BYTE_COUNT = 0x10
FLOAT_INPUT_BYTE_COUNT = 0x20
MAXIMUM_STORE_HIT_COUNT = 16384
MAXIMUM_QUALIFIED_STORE_RECORD_COUNT = 4096
STORE_REGISTER_NAMES = ("x19", "x28", "x29", "sp", "pc", "cpsr")
STORE_SIMD_REGISTER_NAMES = ("v0",)
EXPECTED_EXTENSION_CONFIGURATION = {
    "storeName": STORE_NAME,
    "storeOffset": STORE_OFFSET,
    "storeInstructionRawLittleEndianHex": (STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX),
    "roleWorkingCropOffset": ROLE_WORKING_CROP_OFFSET,
    "roleFloatInputOffset": ROLE_FLOAT_INPUT_OFFSET,
    "layerShapesNestedOffset": LAYER_SHAPES_NESTED_OFFSET,
    "workingCropByteCount": WORKING_CROP_BYTE_COUNT,
    "floatInputByteCount": FLOAT_INPUT_BYTE_COUNT,
    "maximumStoreHitCount": MAXIMUM_STORE_HIT_COUNT,
    "maximumQualifiedStoreRecordCount": MAXIMUM_QUALIFIED_STORE_RECORD_COUNT,
    "storeRegisterNames": list(STORE_REGISTER_NAMES),
    "storeSIMDRegisterNames": list(STORE_SIMD_REGISTER_NAMES),
    "storeSelectionRule": (
        "retain every prepare_layer+0x55c0 store with the exact direct normal "
        "transition caller chain and no intervention caller; do not inspect "
        "role, SIMD, destination, or crop bytes before retaining"
    ),
    "unionSelectionRule": (
        "within each qualified marker interval select the last union whose "
        "x0 destination equals marker x19+0x290"
    ),
    "storeCorrelationRule": (
        "within the same marker interval select the store whose x28 "
        "LayerShapes base equals the selected union x28 base"
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
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{label} is not an array")
    return value


def integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} is not an integer")
    return value


def snapshot_bytes(
    value: Any, expected_address: int, byte_count: int, label: str
) -> bytes:
    address, payload = crop_validator.memory_snapshot(
        value, byte_count, label, expected_address
    )
    if address != expected_address:
        raise ValueError(f"{label} address differs")
    return payload


def simd_payload(value: Any, label: str) -> bytes:
    records = sequence(value, label)
    if len(records) != 1:
        raise ValueError(f"{label} inventory differs")
    record = mapping(records[0], label)
    if record.get("name") != "v0" or record.get("byteCount") != 16:
        raise ValueError(f"{label} identity differs")
    encoded = record.get("hex")
    if not isinstance(encoded, str):
        raise ValueError(f"{label} is not hexadecimal")
    try:
        payload = bytes.fromhex(encoded)
    except ValueError as error:
        raise ValueError(f"{label} is not hexadecimal") from error
    if len(payload) != 16:
        raise ValueError(f"{label} byte count differs")
    return payload


def direct_caller(backtrace: Any) -> bool:
    functions = union_validator.backtrace_functions(backtrace)
    return union_validator.direct_timeline_caller(functions)


def validate_store_record(
    raw: Any, record_index: int, prepare_start: int
) -> dict[str, Any]:
    record = mapping(raw, f"store record {record_index}")
    if record.get("recordIndex") != record_index:
        raise ValueError("store record index differs")
    frame = mapping(record.get("frame"), "store frame")
    if (
        frame.get("function") != crop_validator.PREPARE_LAYER_FUNCTION
        or frame.get("symbolStart") != prepare_start
        or frame.get("symbolEnd")
        != prepare_start + crop_validator.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        or frame.get("symbolOffset") != STORE_OFFSET
        or frame.get("pc") != prepare_start + STORE_OFFSET
    ):
        raise ValueError("store frame identity differs")
    backtrace = sequence(record.get("backtrace"), "store backtrace")
    if not direct_caller(backtrace):
        raise ValueError("store caller chain differs")
    depth = sum(
        mapping(raw_frame, "store backtrace frame").get("function")
        == crop_validator.PREPARE_LAYER_FUNCTION
        and mapping(raw_frame, "store backtrace frame").get("symbolStart")
        == prepare_start
        and mapping(raw_frame, "store backtrace frame").get("symbolEnd")
        == prepare_start + crop_validator.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        for raw_frame in backtrace
    )
    if record.get("prepareRecursionDepth") != depth:
        raise ValueError("store recursion depth differs")

    registers = crop_validator.register_values(
        record.get("registers"), STORE_REGISTER_NAMES, "store registers"
    )
    identity = mapping(record.get("frameIdentity"), "store frame identity")
    expected_identity = {
        "threadID": record.get("threadID"),
        "roleBase": registers["x19"],
        "framePointer": registers["x29"],
        "layerShapesBase": registers["x28"],
        "destination": registers["x28"] + LAYER_SHAPES_NESTED_OFFSET,
    }
    if dict(identity) != expected_identity:
        raise ValueError("store register identity differs")
    role = snapshot_bytes(
        record.get("roleState"),
        registers["x19"],
        crop_validator.ROLE_STATE_BYTE_COUNT,
        "store role state",
    )
    snapshot_bytes(
        record.get("destinationBefore"),
        registers["x28"] + LAYER_SHAPES_NESTED_OFFSET,
        WORKING_CROP_BYTE_COUNT,
        "store destination before",
    )
    source = simd_payload(record.get("simdSourceRegisters"), "store SIMD source")
    working_bytes = role[
        ROLE_WORKING_CROP_OFFSET : ROLE_WORKING_CROP_OFFSET + WORKING_CROP_BYTE_COUNT
    ]
    if source != working_bytes:
        raise ValueError("store SIMD source differs from role working crop")
    working_crop = struct.unpack("<4i", working_bytes)
    floating_input = struct.unpack_from("<4d", role, ROLE_FLOAT_INPUT_OFFSET)
    if (
        not all(math.isfinite(component) for component in floating_input)
        or floating_input[2] < 0
        or floating_input[3] < 0
    ):
        raise ValueError("store floating input differs")
    return {
        "recordIndex": record_index,
        "storeHitIndex": integer(record.get("storeHitIndex"), "store hit index"),
        "prepareRecursionDepth": depth,
        "roleBase": registers["x19"],
        "layerShapesBase": registers["x28"],
        "destinationAddress": registers["x28"] + LAYER_SHAPES_NESTED_OFFSET,
        "floatingInputF64": list(floating_input),
        "floatingInputHex": struct.pack("<4d", *floating_input).hex(),
        "workingCropI32": list(working_crop),
        "workingCropHex": working_bytes.hex(),
    }


def validate(trace_path: Path, timeline_path: Path, expected_geometry: str):
    base_result = crop_validator.validate(trace_path, timeline_path, expected_geometry)
    trace = mapping(crop_validator.load_json(trace_path, "trace"), "trace")
    timeline = mapping(crop_validator.load_json(timeline_path, "timeline"), "timeline")

    crop_records, union_accounting = crop_analysis.validate_extension(
        trace, base_result, timeline, expected_geometry
    )
    union_extension = mapping(trace.get("cropUnionOperandExtension"), "union extension")
    raw_union_records = sequence(union_extension.get("unionRecords"), "union records")
    union_links = sequence(union_extension.get("markerLinks"), "union links")

    extension = mapping(
        trace.get("cropPolicyHoldoutExtension"), "crop policy extension"
    )
    if (
        extension.get("cropPolicyHoldoutExtensionSchemaVersion")
        != EXTENSION_SCHEMA_VERSION
        or extension.get("configuration") != EXPECTED_EXTENSION_CONFIGURATION
        or extension.get("status") != "finalized"
        or extension.get("statusBeforeFinalization") != "crop-policy-store-active"
    ):
        raise ValueError("crop policy extension identity differs")
    prepare_start = integer(
        mapping(trace.get("prepareLayer"), "prepare layer").get("symbolStart"),
        "prepare start",
    )
    instruction_digest = hashlib.sha256(
        bytes.fromhex(STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX)
    ).hexdigest()
    if (
        extension.get("prepareLayerSymbolStart") != prepare_start
        or integer(extension.get("storeBreakpointID"), "store breakpoint") <= 0
        or extension.get("storeInstructionSHA256") != instruction_digest
    ):
        raise ValueError("crop policy store instruction identity differs")

    raw_store_records = sequence(extension.get("storeRecords"), "store records")
    if not 32 <= len(raw_store_records) <= MAXIMUM_QUALIFIED_STORE_RECORD_COUNT:
        raise ValueError("qualified store record bounds differ")
    stores = [
        validate_store_record(raw, index, prepare_start)
        for index, raw in enumerate(raw_store_records)
    ]
    hit_indices = [record["storeHitIndex"] for record in stores]
    if hit_indices != sorted(hit_indices) or len(set(hit_indices)) != len(hit_indices):
        raise ValueError("qualified store hit order differs")

    rejected = integer(extension.get("finalRejectedStoreCount"), "rejected stores")
    grouped_rejections = 0
    for raw_group in sequence(extension.get("rejectionGroups"), "store rejections"):
        group = mapping(raw_group, "store rejection group")
        if group.get("reason") != "caller-chain-excluded":
            raise ValueError("store rejection reason differs")
        integer(group.get("prepareRecursionDepth"), "store rejection depth")
        grouped_rejections += integer(group.get("hitCount"), "store rejection count")
    if (
        rejected != grouped_rejections
        or extension.get("finalQualifiedStoreRecordCount") != len(stores)
        or extension.get("finalStoreHitCount") != len(stores) + rejected
    ):
        raise ValueError("store final accounting differs")

    links = sequence(extension.get("markerLinks"), "store marker links")
    marker_records = sequence(trace.get("qualifiedRecords"), "marker records")
    if (
        len(links) != 32
        or extension.get("finalMarkerLinkCount") != 32
        or len(marker_records) != 32
        or len(crop_records) != 32
        or len(union_links) != 32
    ):
        raise ValueError("store marker-link inventory differs")

    joined = []
    previous_end = 0
    for index, (raw_link, raw_marker, raw_union_link, crop_record) in enumerate(
        zip(links, marker_records, union_links, crop_records, strict=True)
    ):
        link = mapping(raw_link, f"store link {index}")
        marker = mapping(raw_marker, f"marker record {index}")
        union_link = mapping(raw_union_link, f"union link {index}")
        start = integer(link.get("startStoreRecordIndex"), "store link start")
        end = integer(link.get("endStoreRecordIndexExclusive"), "store link end")
        union_indices = list(
            sequence(
                union_link.get("matchingUnionRecordIndices"),
                "matching union records",
            )
        )
        if len(union_indices) != 2:
            raise ValueError("holdout two-union topology differs")
        selected_union_index = union_indices[-1]
        selected_union = mapping(
            raw_union_records[selected_union_index], "selected union record"
        )
        selected_layer_shapes = integer(
            mapping(selected_union.get("frameIdentity"), "selected union identity").get(
                "layerShapesBase"
            ),
            "selected union LayerShapes base",
        )
        matching = list(
            sequence(link.get("matchingStoreRecordIndices"), "matching stores")
        )
        recomputed = [
            store["recordIndex"]
            for store in stores[start:end]
            if store["layerShapesBase"] == selected_layer_shapes
        ]
        embedded = mapping(marker.get("cropPolicyStoreWindow"), "store window")
        if (
            start != previous_end
            or not start < end <= len(stores)
            or link.get("selectedUnionRecordIndex") != selected_union_index
            or link.get("selectedLayerShapesBase") != selected_layer_shapes
            or matching != recomputed
            or len(matching) != 1
            or embedded.get("startRecordIndex") != start
            or embedded.get("endRecordIndexExclusive") != end
            or embedded.get("selectedUnionRecordIndex") != selected_union_index
            or embedded.get("selectedLayerShapesBase") != selected_layer_shapes
            or embedded.get("matchingStoreRecordIndices") != matching
        ):
            raise ValueError("store pointer correlation differs")
        selected_store = stores[matching[0]]
        observed_crop = tuple(crop_record["observedNestedInputI32"])
        working_crop = tuple(selected_store["workingCropI32"])
        candidate_float = tuple(crop_record["candidateIntersectionF64"])
        floating_input = tuple(selected_store["floatingInputF64"])
        if working_crop != observed_crop or struct.pack(
            "<4d", *candidate_float
        ) != struct.pack("<4d", *floating_input):
            raise ValueError("public crop producer replay differs")
        joined.append(
            {
                **crop_record,
                "storeRecordIndex": selected_store["recordIndex"],
                "storeRoleBase": selected_store["roleBase"],
                "floatingInputF64": list(floating_input),
                "floatingInputHex": selected_store["floatingInputHex"],
                "workingCropI32": list(working_crop),
                "workingCropHex": selected_store["workingCropHex"],
            }
        )
        previous_end = end

    trailing = len(stores) - previous_end
    if (
        extension.get("finalLinkedStoreRecordCount") != 32
        or extension.get("finalTrailingStoreRecordCount") != trailing
    ):
        raise ValueError("store trailing accounting differs")
    return {
        "prepareLayerCropPolicyHoldoutValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            "prospective unseen exact public-crop-policy transfer; the frozen "
            "public formula replays Apple's pre-integer binary64 producer, "
            "signed integer crop, and final aggregate without tolerances"
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
        "recordCount": len(joined),
        "componentCount": len(joined) * 4,
        "unionRecordCount": union_accounting["unionRecordCount"],
        "storeRecordCount": len(stores),
        "rejectedStoreCount": rejected,
        "trailingStoreRecordCount": trailing,
        "records": joined,
        "sealedConclusion": {
            "schemaSevenMarkerValidationRepassed": True,
            "exactUnionCallAndReturnCodePassed": True,
            "twoDestinationMatchedUnionsPerMarkerPassed": True,
            "lastDestinationMatchedUnionSelectionPassed": True,
            "exactNestedCropStoreCodePassed": True,
            "cropIndependentStoreSelectionPassed": True,
            "layerShapesPointerCorrelationPassed": True,
            "allPreIntegerFloatingInputsReplayedBitForBit": True,
            "allSignedIntegerOperandsReplayedExactly": True,
            "allFinalAggregatesReplayedBitForBit": True,
            "unseenGeometryCropPolicyTransferPassed": True,
            "materialAppearanceDirectionTransferPassed": False,
            "physicalRetina2xTransferPassed": False,
            "endToEndWallePixelParityPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--expected-geometry", required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.trace, arguments.timeline, arguments.expected_geometry)
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")


if __name__ == "__main__":
    main()
