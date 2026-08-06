#!/usr/bin/env python3
"""Fail-closed validation for Gaussian data and delegated backdrop code."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_prepare_layer_small_geometry_helper_code as frozen


VALIDATION_SCHEMA_VERSION = 1
GAUSSIAN_CODE_SHA256 = (
    "7834bbb95f84915a6544d34b4148f7f267fcc94d2ae730888644535ffc57c0dd"
)
BACKDROP_WRAPPER_CODE_SHA256 = (
    "85a99558cc08c2a693969b55c804cd811e8ef710ac2d02460830f8bf9d6ec85a"
)
QUARTZCORE_UUID = "4D34EB4E-2BBB-3751-A362-8E2EB74656E8"
GET_BACKDROP_BOUNDS_FUNCTION = (
    "CA::Render::BackdropLayer::get_backdrop_bounds("
    "CA::Render::Layer const*, CA::Rect&) const"
)
GET_BACKDROP_BOUNDS_RELATIVE = 364696
GET_BACKDROP_BOUNDS_MAXIMUM_BYTE_COUNT = 65536
CONSTANT_SPECS = (
    ("highThreshold", 0x394910),
    ("lowThreshold", 0x394928),
    ("activeShift", 0x394930),
    ("logIntercept", 0x394938),
    ("logSlope", 0x394940),
    ("highIntercept", 0x394918),
    ("highSlope", 0x394920),
    ("alternateModeReturn", 0x3944F8),
)


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} is not an object")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{label} is not an array")
    return value


def payload(value: Any, byte_count: int, label: str) -> bytes:
    try:
        result = bytes.fromhex(str(value))
    except ValueError as error:
        raise ValueError(f"{label} is not hexadecimal") from error
    if len(result) != byte_count:
        raise ValueError(f"{label} byte count differs")
    return result


def load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is unreadable: {error}") from error


def validate(
    trace_path: Path, timeline_path: Path, inventory_path: Path
) -> dict[str, Any]:
    inherited = frozen.validate(trace_path, timeline_path, inventory_path)
    trace = mapping(load_json(trace_path, "trace"), "trace")
    extension = mapping(
        trace.get("prepareLayerSmallGeometryHelperSemanticsExtension"),
        "helper-semantics extension",
    )
    configuration = mapping(extension.get("configuration"), "configuration")
    if (
        extension.get("status") != "finalized"
        or extension.get("statusBeforeFinalization")
        != "static-semantics-capture-closed"
        or extension.get("failures") != []
        or extension.get("finalFailureCount") != 0
    ):
        raise ValueError("helper-semantics extension did not finalize cleanly")
    if (
        configuration.get("gaussianCodeSHA256") != GAUSSIAN_CODE_SHA256
        or configuration.get("backdropWrapperCodeSHA256")
        != BACKDROP_WRAPPER_CODE_SHA256
        or configuration.get("quartzCoreUUID") != QUARTZCORE_UUID
        or configuration.get("constantValuesAcceptedBeforeCapture") is not None
        or configuration.get("globalModeFlagValueAcceptedBeforeCapture") is not None
        or configuration.get("getBackdropBoundsExpectedCodeSHA256") is not None
        or configuration.get("getBackdropBoundsRelativeToPrepareLayer")
        != GET_BACKDROP_BOUNDS_RELATIVE
        or configuration.get("getBackdropBoundsFunction")
        != GET_BACKDROP_BOUNDS_FUNCTION
        or configuration.get("getBackdropBoundsMaximumByteCount")
        != GET_BACKDROP_BOUNDS_MAXIMUM_BYTE_COUNT
        or configuration.get("staticMemoryReadsOnly") is not True
        or configuration.get("breakpointsAdded") != 0
        or configuration.get("instructionStepsAdded") != 0
        or configuration.get("cropValuesUsedForSelection") is not False
        or configuration.get("outputValuesUsedForSelection") is not False
        or configuration.get("inheritedCaptureChanged") is not False
    ):
        raise ValueError("helper-semantics configuration differs")

    gaussian = mapping(extension.get("gaussian"), "Gaussian capture")
    module = mapping(gaussian.get("module"), "Gaussian module")
    module_base = module.get("loadAddress")
    if (
        gaussian.get("codeSHA256") != GAUSSIAN_CODE_SHA256
        or module.get("uuid") != QUARTZCORE_UUID
        or not isinstance(module_base, int)
        or isinstance(module_base, bool)
    ):
        raise ValueError("Gaussian identity differs")
    global_flag = mapping(gaussian.get("globalModeFlag"), "global mode flag")
    global_raw = payload(global_flag.get("rawLittleEndianHex"), 1, "global mode flag")
    if (
        global_flag.get("instructionOffset") != 0
        or global_flag.get("loadOffset") != 0xA8B
        or global_flag.get("byteCount") != 1
        or global_flag.get("unsignedValue") != global_raw[0]
        or global_flag.get("valueAcceptedBeforeCapture") is not None
    ):
        raise ValueError("global mode flag capture differs")

    constants = sequence(gaussian.get("constants"), "Gaussian constants")
    if len(constants) != len(CONSTANT_SPECS):
        raise ValueError("Gaussian constant count differs")
    validated_constants: list[dict[str, Any]] = []
    for raw, (expected_name, expected_offset) in zip(
        constants, CONSTANT_SPECS, strict=True
    ):
        item = mapping(raw, "Gaussian constant")
        word = payload(item.get("rawLittleEndianHex"), 8, expected_name)
        value = struct.unpack("<d", word)[0]
        if (
            item.get("name") != expected_name
            or item.get("moduleRelativeOffset") != expected_offset
            or item.get("address") != module_base + expected_offset
            or item.get("byteCount") != 8
            or item.get("binary64Bits") != int.from_bytes(word, "little")
            or item.get("binary64") != value
            or item.get("binary64Hex") != value.hex()
            or item.get("valueAcceptedBeforeCapture") is not None
            or not math.isfinite(value)
        ):
            raise ValueError(f"{expected_name} capture differs")
        validated_constants.append(
            {
                "name": expected_name,
                "moduleRelativeOffset": expected_offset,
                "rawLittleEndianHex": word.hex(),
                "binary64Bits": int.from_bytes(word, "little"),
                "binary64": value,
                "binary64Hex": value.hex(),
                "valueAcceptedBeforeCapture": False,
            }
        )

    callee = mapping(extension.get("getBackdropBounds"), "get_backdrop_bounds")
    code_count = callee.get("symbolByteCount")
    if (
        callee.get("function") != GET_BACKDROP_BOUNDS_FUNCTION
        or callee.get("relativeToPrepareLayer") != GET_BACKDROP_BOUNDS_RELATIVE
        or not isinstance(code_count, int)
        or isinstance(code_count, bool)
        or code_count <= 0
        or code_count > GET_BACKDROP_BOUNDS_MAXIMUM_BYTE_COUNT
        or code_count % 4 != 0
        or callee.get("maximumAcceptedByteCount")
        != GET_BACKDROP_BOUNDS_MAXIMUM_BYTE_COUNT
        or callee.get("expectedCodeSHA256") is not None
        or callee.get("cropValuesUsedForSelection") is not False
        or callee.get("outputValuesUsedForSelection") is not False
        or mapping(callee.get("module"), "callee module") != module
    ):
        raise ValueError("get_backdrop_bounds identity differs")
    code = payload(callee.get("hex"), code_count, "get_backdrop_bounds code")
    code_hash = hashlib.sha256(code).hexdigest()
    if callee.get("observedCodeSHA256") != code_hash:
        raise ValueError("get_backdrop_bounds code hash differs")
    instructions = sequence(callee.get("instructions"), "callee instructions")
    if (
        callee.get("instructionCount") != code_count // 4
        or len(instructions) != code_count // 4
    ):
        raise ValueError("get_backdrop_bounds instruction coverage differs")
    start = callee.get("symbolStart")
    end = callee.get("symbolEnd")
    if (
        not isinstance(start, int)
        or isinstance(start, bool)
        or end != start + code_count
    ):
        raise ValueError("get_backdrop_bounds symbol bounds differ")
    for index, raw_instruction in enumerate(instructions):
        instruction = mapping(raw_instruction, "callee instruction")
        offset = index * 4
        if (
            instruction.get("offset") != offset
            or instruction.get("pc") != start + offset
            or payload(instruction.get("rawLittleEndianHex"), 4, "callee instruction")
            != code[offset : offset + 4]
        ):
            raise ValueError("get_backdrop_bounds instruction chain differs")

    inherited_sealed = mapping(
        inherited.get("sealedConclusion"), "inherited sealed conclusion"
    )
    return {
        "prepareLayerSmallGeometryHelperSemanticsValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            "prospective output-blind opening of all Gaussian data words and "
            "the complete delegated backdrop-bounds symbol"
        ),
        "conclusion": "success",
        "inputs": inherited["inputs"],
        "profile": inherited["profile"],
        "selection": {
            **inherited["selection"],
            "constantValuesAcceptedBeforeCapture": False,
            "globalModeFlagAcceptedBeforeCapture": False,
            "backdropCalleeCodeHashAcceptedBeforeCapture": False,
            "staticMemoryReadsOnly": True,
            "breakpointsAdded": 0,
            "instructionStepsAdded": 0,
        },
        "gaussian": {
            "codeSHA256": GAUSSIAN_CODE_SHA256,
            "globalModeFlagRawLittleEndianHex": global_raw.hex(),
            "globalModeFlagUnsignedValue": global_raw[0],
            "constants": validated_constants,
        },
        "getBackdropBounds": {
            "function": GET_BACKDROP_BOUNDS_FUNCTION,
            "relativeToPrepareLayer": GET_BACKDROP_BOUNDS_RELATIVE,
            "symbolByteCount": code_count,
            "codeSHA256": code_hash,
            "instructionCount": len(instructions),
            "codeHashAcceptedBeforeCapture": False,
        },
        "sealedConclusion": {
            **inherited_sealed,
            "smallGeometryHelperSemanticsStaticOpeningPassed": True,
            "gaussianConstantsOpened": True,
            "gaussianExpansionGeneralSemanticsDecoded": False,
            "backdropDelegatedCodeOpened": True,
            "backdropAllocationGeneralSemanticsDecoded": False,
            "regularGeometryTransferPassed": False,
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
