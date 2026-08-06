#!/usr/bin/env python3
"""Fail-closed validation for live BackdropLayer state and writer discovery."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import validate_prepare_layer_crop_producer_callee as producer_validator
import validate_prepare_layer_small_geometry_helper_semantics as frozen


VALIDATION_SCHEMA_VERSION = 1
BACKDROP_WRAPPER_FUNCTION = (
    "CA::Render::BackdropLayer::get_bounds("
    "CA::Render::Layer const*, CA::Rect&, CA::Rect*) const"
)
BACKDROP_WRAPPER_RELATIVE_TO_PREPARE_LAYER = 364616
BACKDROP_WRAPPER_BYTE_COUNT = 80
BACKDROP_WRAPPER_CODE_SHA256 = (
    "85a99558cc08c2a693969b55c804cd811e8ef710ac2d02460830f8bf9d6ec85a"
)
GET_BACKDROP_BOUNDS_CODE_SHA256 = (
    "3296daa4d858acc2a259be7771e48c312ff7010fa3d7cd590a9f28bd17a4ff17"
)
QUARTZCORE_UUID = "4D34EB4E-2BBB-3751-A362-8E2EB74656E8"
BACKDROP_OBJECT_BYTE_COUNT = 0x90
LAYER_OBJECT_BYTE_COUNT = 0x140
RECT_BYTE_COUNT = 0x20
BACKDROP_MARGIN_OFFSET = 0x24
BACKDROP_ORIGIN_OFFSET = 0x60
BACKDROP_SIZE_OFFSET = 0x70
LAYER_ORIGIN_OFFSET = 0x48
LAYER_SIZE_OFFSET = 0x58
SYMBOL_NAME_SUBSTRING = "BackdropLayer"
MAXIMUM_MATCHED_CODE_SYMBOL_COUNT = 256
MAXIMUM_INDIVIDUAL_SYMBOL_BYTE_COUNT = 65536
MAXIMUM_TOTAL_SYMBOL_BYTE_COUNT = 2 * 1024 * 1024
DBL_MAX = float.fromhex("0x1.fffffffffffffp+1023")


mapping = frozen.mapping
sequence = frozen.sequence


def load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is unreadable: {error}") from error


def integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} is not an integer")
    return value


def snapshot(
    value: Any, expected_address: int, expected_byte_count: int, label: str
) -> bytes:
    record = mapping(value, label)
    if (
        integer(record.get("address"), f"{label} address") != expected_address
        or integer(record.get("byteCount"), f"{label} byte count")
        != expected_byte_count
    ):
        raise ValueError(f"{label} bounds differ")
    try:
        result = bytes.fromhex(str(record.get("hex")))
    except ValueError as error:
        raise ValueError(f"{label} is not hexadecimal") from error
    if len(result) != expected_byte_count:
        raise ValueError(f"{label} payload length differs")
    if record.get("sha256") != hashlib.sha256(result).hexdigest():
        raise ValueError(f"{label} SHA-256 differs")
    return result


def binary64_fma(left: float, right: float, addend: float) -> float:
    if hasattr(math, "fma"):
        return math.fma(left, right, addend)
    function = ctypes.CDLL(None).fma
    function.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double]
    function.restype = ctypes.c_double
    return float(function(left, right, addend))


def arm_minimum(left: float, right: float) -> float:
    """Replay FCMP followed by FCSEL MI."""
    return left if left < right else right


def arm_maximum(left: float, right: float) -> float:
    """Replay FCMP followed by FCSEL GT."""
    return left if left > right else right


def selected_base(
    backdrop: bytes, layer: bytes
) -> tuple[str, bytes, tuple[float, float, float, float]]:
    self_sizes = struct.unpack_from("<2d", backdrop, BACKDROP_SIZE_OFFSET)
    if arm_minimum(*self_sizes) > 0.0:
        raw = (
            backdrop[BACKDROP_ORIGIN_OFFSET : BACKDROP_ORIGIN_OFFSET + 16]
            + backdrop[BACKDROP_SIZE_OFFSET : BACKDROP_SIZE_OFFSET + 16]
        )
        return "backdrop", raw, struct.unpack("<4d", raw)
    raw = (
        layer[LAYER_ORIGIN_OFFSET : LAYER_ORIGIN_OFFSET + 16]
        + layer[LAYER_SIZE_OFFSET : LAYER_SIZE_OFFSET + 16]
    )
    return "layer", raw, struct.unpack("<4d", raw)


def replay_get_backdrop_bounds(
    backdrop: bytes, layer: bytes
) -> tuple[str, bytes, tuple[float, float, float, float], float]:
    source, base_raw, base = selected_base(backdrop, layer)
    maximum = arm_maximum(base[2], base[3])
    minimum = arm_minimum(base[2], base[3])
    if not maximum < DBL_MAX or not minimum > 0.0:
        return (
            source,
            base_raw,
            base,
            struct.unpack_from("<f", backdrop, BACKDROP_MARGIN_OFFSET)[0],
        )

    margin = struct.unpack_from("<f", backdrop, BACKDROP_MARGIN_OFFSET)[0]
    negative_margin = -margin
    origin_x = base[0] + negative_margin
    origin_y = base[1] + negative_margin
    doubled_negative = negative_margin + negative_margin
    width = base[2] - doubled_negative
    height = binary64_fma(negative_margin, -2.0, base[3])
    if (not math.isnan(width) and width <= 0.0) or (
        not math.isnan(height) and height <= 0.0
    ):
        width = 0.0
        height = 0.0
    result = (origin_x, origin_y, width, height)
    return source, struct.pack("<4d", *result), result, margin


def validate_symbol_inventory(
    value: Any, prepare_module: Mapping[str, Any]
) -> dict[str, Any]:
    inventory = mapping(value, "BackdropLayer symbol inventory")
    module = mapping(inventory.get("module"), "inventory module")
    module_base = integer(module.get("loadAddress"), "inventory module base")
    module_without_uuid = dict(module)
    module_without_uuid.pop("uuid", None)
    if (
        module.get("uuid") != QUARTZCORE_UUID
        or module_without_uuid != prepare_module
        or inventory.get("symbolNameSubstring") != SYMBOL_NAME_SUBSTRING
        or inventory.get("expectedMatchedNameCount") is not None
        or inventory.get("expectedUniqueRangeCount") is not None
        or inventory.get("expectedNames") is not None
        or inventory.get("expectedCodeSHA256") is not None
    ):
        raise ValueError("BackdropLayer symbol-inventory identity differs")

    ranges = sequence(inventory.get("ranges"), "BackdropLayer symbol ranges")
    if not ranges or len(ranges) > MAXIMUM_MATCHED_CODE_SYMBOL_COUNT:
        raise ValueError("BackdropLayer symbol-range count differs")
    previous_key: tuple[int, int] | None = None
    matched_names = 0
    total_bytes = 0
    canonical = hashlib.sha256()
    decoded_ranges: list[dict[str, Any]] = []
    for index, raw_range in enumerate(ranges):
        label = f"BackdropLayer symbol range {index}"
        item = mapping(raw_range, label)
        start = integer(item.get("symbolStart"), f"{label} start")
        end = integer(item.get("symbolEnd"), f"{label} end")
        byte_count = integer(item.get("symbolByteCount"), f"{label} byte count")
        key = (start, end)
        names = sequence(item.get("names"), f"{label} names")
        if (
            previous_key is not None
            and key <= previous_key
            or end <= start
            or byte_count != end - start
            or byte_count % 4 != 0
            or byte_count > MAXIMUM_INDIVIDUAL_SYMBOL_BYTE_COUNT
            or item.get("moduleRelativeStart") != start - module_base
            or not names
            or list(names) != sorted(names)
            or any(
                not isinstance(name, str) or SYMBOL_NAME_SUBSTRING not in name
                for name in names
            )
            or item.get("expectedCodeSHA256") is not None
            or item.get("fieldOrOutputValuesUsedForSelection") is not False
        ):
            raise ValueError(f"{label} structure differs")
        try:
            code = bytes.fromhex(str(item.get("hex")))
        except ValueError as error:
            raise ValueError(f"{label} code is not hexadecimal") from error
        digest = hashlib.sha256(code).hexdigest()
        if len(code) != byte_count or item.get("observedCodeSHA256") != digest:
            raise ValueError(f"{label} code differs")
        instructions = sequence(item.get("instructions"), f"{label} instructions")
        if (
            item.get("instructionCount") != byte_count // 4
            or len(instructions) != byte_count // 4
        ):
            raise ValueError(f"{label} instruction coverage differs")
        for instruction_index, raw_instruction in enumerate(instructions):
            instruction = mapping(raw_instruction, f"{label} instruction")
            offset = instruction_index * 4
            if (
                instruction.get("offset") != offset
                or instruction.get("pc") != start + offset
                or instruction.get("rawLittleEndianHex")
                != code[offset : offset + 4].hex()
            ):
                raise ValueError(f"{label} instruction chain differs")
        previous_key = key
        matched_names += len(names)
        total_bytes += byte_count
        canonical.update(struct.pack("<QQ", start - module_base, byte_count))
        for name in names:
            encoded = name.encode("utf-8")
            canonical.update(struct.pack("<I", len(encoded)))
            canonical.update(encoded)
        canonical.update(code)
        decoded_ranges.append(
            {
                "moduleRelativeStart": start - module_base,
                "symbolByteCount": byte_count,
                "names": list(names),
                "codeSHA256": digest,
            }
        )

    if (
        total_bytes > MAXIMUM_TOTAL_SYMBOL_BYTE_COUNT
        or inventory.get("matchedNameCount") != matched_names
        or inventory.get("uniqueRangeCount") != len(ranges)
        or inventory.get("totalCodeByteCount") != total_bytes
    ):
        raise ValueError("BackdropLayer symbol-inventory totals differ")
    return {
        "matchedNameCount": matched_names,
        "uniqueRangeCount": len(ranges),
        "totalCodeByteCount": total_bytes,
        "canonicalSHA256": canonical.hexdigest(),
        "ranges": decoded_ranges,
    }


def validate(
    trace_path: Path, timeline_path: Path, inventory_path: Path
) -> dict[str, Any]:
    inherited = frozen.validate(trace_path, timeline_path, inventory_path)
    trace = mapping(load_json(trace_path, "trace"), "trace")
    extension = mapping(
        trace.get("prepareLayerBackdropStateWriterDiscoveryExtension"),
        "backdrop-state extension",
    )
    configuration = mapping(extension.get("configuration"), "configuration")
    if (
        extension.get("status") != "finalized"
        or extension.get("statusBeforeFinalization") != "writer-discovery-closed"
        or extension.get("failures") != []
        or extension.get("finalFailureCount") != 0
        or extension.get("finalBoundaryObjectCount") != 1
    ):
        raise ValueError("backdrop-state extension did not finalize cleanly")
    if (
        configuration.get("backdropWrapperFunction") != BACKDROP_WRAPPER_FUNCTION
        or configuration.get("backdropWrapperRelativeToPrepareLayer")
        != BACKDROP_WRAPPER_RELATIVE_TO_PREPARE_LAYER
        or configuration.get("backdropWrapperCodeSHA256")
        != BACKDROP_WRAPPER_CODE_SHA256
        or configuration.get("getBackdropBoundsCodeSHA256")
        != GET_BACKDROP_BOUNDS_CODE_SHA256
        or configuration.get("quartzCoreUUID") != QUARTZCORE_UUID
        or configuration.get("backdropObjectByteCount") != BACKDROP_OBJECT_BYTE_COUNT
        or configuration.get("layerObjectByteCount") != LAYER_OBJECT_BYTE_COUNT
        or configuration.get("primaryRectByteCount") != RECT_BYTE_COUNT
        or configuration.get("selfLayerPointerDeltaAcceptedBeforeCapture") is not None
        or configuration.get("backdropFieldValuesAcceptedBeforeCapture") is not None
        or configuration.get("layerFieldValuesAcceptedBeforeCapture") is not None
        or configuration.get("symbolNameSubstring") != SYMBOL_NAME_SUBSTRING
        or configuration.get("maximumMatchedCodeSymbolCount")
        != MAXIMUM_MATCHED_CODE_SYMBOL_COUNT
        or configuration.get("maximumIndividualSymbolByteCount")
        != MAXIMUM_INDIVIDUAL_SYMBOL_BYTE_COUNT
        or configuration.get("maximumTotalSymbolByteCount")
        != MAXIMUM_TOTAL_SYMBOL_BYTE_COUNT
        or configuration.get("symbolInventoryCountAcceptedBeforeCapture") is not None
        or configuration.get("symbolNamesAcceptedBeforeCapture") is not None
        or configuration.get("symbolCodeHashesAcceptedBeforeCapture") is not None
        or configuration.get("newBreakpointsAdded") != 0
        or configuration.get("newInstructionStepsAdded") != 0
        or configuration.get("existingOpaqueBoundaryStepWrapped") is not True
        or configuration.get("cropValuesUsedForSelection") is not False
        or configuration.get("outputValuesUsedForSelection") is not False
        or configuration.get("inheritedCaptureChanged") is not False
    ):
        raise ValueError("backdrop-state configuration differs")

    prepare = mapping(trace.get("prepareLayer"), "prepare_layer identity")
    prepare_start = integer(prepare.get("symbolStart"), "prepare_layer start")
    prepare_module = mapping(prepare.get("module"), "prepare_layer module")
    if (
        prepare_module.get("valid") is not True
        or not isinstance(prepare_module.get("path"), str)
        or integer(prepare_module.get("loadAddress"), "prepare_layer module base") <= 0
    ):
        raise ValueError("prepare_layer module differs")
    symbol_inventory = validate_symbol_inventory(
        extension.get("symbolInventory"), prepare_module
    )

    boundaries = sequence(extension.get("boundaryObjects"), "boundary objects")
    if len(boundaries) != 1:
        raise ValueError("backdrop wrapper boundary is not unique")
    boundary = mapping(boundaries[0], "backdrop wrapper boundary")
    registers = producer_validator.registers(
        boundary.get("registersAtEntry"), "backdrop wrapper entry registers"
    )
    self_address = integer(boundary.get("selfAddress"), "self address")
    layer_address = integer(boundary.get("layerAddress"), "layer address")
    output_address = integer(boundary.get("outputAddress"), "output address")
    pointer_delta = self_address - layer_address
    if (
        boundary.get("boundaryIndex") != 0
        or registers["x0"] != self_address
        or registers["x1"] != layer_address
        or registers["x2"] != output_address
        or boundary.get("selfMinusLayer") != pointer_delta
        or boundary.get("selfLayerPointerDeltaAcceptedBeforeCapture") is not None
        or boundary.get("fieldValuesAcceptedBeforeCapture") is not None
        or boundary.get("cropValuesUsedForSelection") is not False
        or boundary.get("outputValuesUsedForSelection") is not False
    ):
        raise ValueError("backdrop wrapper boundary selection differs")

    frame = mapping(boundary.get("wrapperFrame"), "backdrop wrapper frame")
    wrapper_start = prepare_start + BACKDROP_WRAPPER_RELATIVE_TO_PREPARE_LAYER
    if (
        frame.get("function") != BACKDROP_WRAPPER_FUNCTION
        or frame.get("pc") != wrapper_start
        or frame.get("symbolStart") != wrapper_start
        or frame.get("symbolEnd") != wrapper_start + BACKDROP_WRAPPER_BYTE_COUNT
        or frame.get("symbolOffset") != 0
        or mapping(frame.get("module"), "wrapper module") != prepare_module
    ):
        raise ValueError("backdrop wrapper frame identity differs")

    backdrop_before = snapshot(
        boundary.get("backdropBefore"),
        self_address,
        BACKDROP_OBJECT_BYTE_COUNT,
        "BackdropLayer before",
    )
    backdrop_after = snapshot(
        boundary.get("backdropAfter"),
        self_address,
        BACKDROP_OBJECT_BYTE_COUNT,
        "BackdropLayer after",
    )
    layer_before = snapshot(
        boundary.get("layerBefore"),
        layer_address,
        LAYER_OBJECT_BYTE_COUNT,
        "Layer before",
    )
    layer_after = snapshot(
        boundary.get("layerAfter"),
        layer_address,
        LAYER_OBJECT_BYTE_COUNT,
        "Layer after",
    )
    primary_before = snapshot(
        boundary.get("primaryRectBefore"),
        output_address,
        RECT_BYTE_COUNT,
        "primary Rect before",
    )
    primary_after = snapshot(
        boundary.get("primaryRectAfter"),
        output_address,
        RECT_BYTE_COUNT,
        "primary Rect after",
    )
    if backdrop_before != backdrop_after or layer_before != layer_after:
        raise ValueError("backdrop wrapper mutated an input object")
    source, replay_raw, replay, margin = replay_get_backdrop_bounds(
        backdrop_before, layer_before
    )
    if replay_raw != primary_after:
        raise ValueError("live-field backdrop-bounds replay differs")

    self_rect = struct.unpack_from("<4d", backdrop_before, BACKDROP_ORIGIN_OFFSET)
    layer_rect = (
        *struct.unpack_from("<2d", layer_before, LAYER_ORIGIN_OFFSET),
        *struct.unpack_from("<2d", layer_before, LAYER_SIZE_OFFSET),
    )
    inherited_sealed = mapping(
        inherited.get("sealedConclusion"), "inherited sealed conclusion"
    )
    return {
        "prepareLayerBackdropStateWriterDiscoveryValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            "prospective output-blind live BackdropLayer/Layer field capture "
            "with bit-exact selected replay and complete class-scoped code inventory"
        ),
        "conclusion": "success",
        "inputs": inherited["inputs"],
        "profile": inherited["profile"],
        "selection": {
            **inherited["selection"],
            "liveFieldValuesAcceptedBeforeCapture": False,
            "selfLayerPointerDeltaAcceptedBeforeCapture": False,
            "symbolInventoryAcceptedBeforeCapture": False,
            "newBreakpointsAdded": 0,
            "newInstructionStepsAdded": 0,
        },
        "liveBackdropState": {
            "selfAddress": self_address,
            "layerAddress": layer_address,
            "selfMinusLayer": pointer_delta,
            "outputAddress": output_address,
            "marginOffset": BACKDROP_MARGIN_OFFSET,
            "marginF32": margin,
            "marginRawLittleEndianHex": backdrop_before[
                BACKDROP_MARGIN_OFFSET : BACKDROP_MARGIN_OFFSET + 4
            ].hex(),
            "backdropRectF64": list(self_rect),
            "backdropRectRawLittleEndianHex": backdrop_before[
                BACKDROP_ORIGIN_OFFSET : BACKDROP_SIZE_OFFSET + 16
            ].hex(),
            "layerRectF64": list(layer_rect),
            "layerRectRawLittleEndianHex": (
                layer_before[LAYER_ORIGIN_OFFSET : LAYER_ORIGIN_OFFSET + 16]
                + layer_before[LAYER_SIZE_OFFSET : LAYER_SIZE_OFFSET + 16]
            ).hex(),
            "selectedBaseSource": source,
            "primaryRectBeforeF64": list(struct.unpack("<4d", primary_before)),
            "primaryRectAfterF64": list(struct.unpack("<4d", primary_after)),
            "replayF64": list(replay),
            "replayRawLittleEndianHex": replay_raw.hex(),
            "bitExact": True,
            "inputObjectsUnchanged": True,
        },
        "backdropLayerSymbolInventory": symbol_inventory,
        "sealedConclusion": {
            **inherited_sealed,
            "liveBackdropBaseAndMarginFieldsCaptured": True,
            "selectedBackdropBoundsReplayBitExact": True,
            "classScopedBackdropWriterCodeInventoryOpened": True,
            "backdropMarginWriterDecoded": False,
            "dynamicTopologyLawDecoded": False,
            "prospectiveUnseenGeometryTransferPassed": False,
            "capturedInputOpticalParityPassed": False,
            "independentPrivateInputGenerationPassed": False,
            "physicalOutputTransferPassed": False,
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
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.trace, arguments.timeline, arguments.inventory)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
