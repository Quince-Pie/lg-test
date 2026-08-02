#!/usr/bin/env python3
"""Validate the reduced live-baseline deepest-SDF threshold experiment."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import struct
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_dynamic_allocation_fixed_state as fixed
import validate_dynamic_allocation_holdout as holdout
import validate_dynamic_allocation_path_isolation as original


EXPECTED_GEOMETRY = "circle-640-center"
EXPECTED_SAMPLE_INDICES = tuple(range(1, 33))
EXPECTED_SOURCE_SAMPLE_INDICES = (25, 31)
POSITION_PATH = original.POSITION_PATH
STRONG_DELTAS = original.STRONG_DELTAS
DENSE_X_VALUES = original.DENSE_X_VALUES
DENSE_Y_VALUES = original.DENSE_Y_VALUES
BUFFER_RETENTION_POLICY = original.BUFFER_RETENTION_POLICY
CLASSIFICATION = (
    "preregistered-live-baseline-deepest-sdf-position-threshold-calibration"
)
FINE_SCAN_CLASSIFICATION = (
    "preregistered-live-baseline-deepest-sdf-position-fine-threshold-and-"
    "cross-axis-calibration"
)
SAMPLE31_REPEAT_CLASSIFICATION = (
    "preregistered-live-baseline-sample31-unit-threshold-and-same-process-"
    "repeat-calibration"
)
CAPTURE_BACKDROP_OPERAND_CLASSIFICATION = (
    "preregistered-live-capture-backdrop-operand-and-primary-position-replay"
)
SAMPLE31_REPEAT_SOURCE_SAMPLE_INDICES = (31,)
FINE_X_VALUES = tuple(range(80, 89))
FINE_Y_VALUES = tuple(range(64, 97))
CROSS_AXIS_X_VALUES = DENSE_X_VALUES
CROSS_AXIS_Y_VALUES = DENSE_Y_VALUES
SAMPLE31_UNIT_X_VALUES = tuple(range(-12, 37))
SAMPLE31_UNIT_Y_VALUES = tuple(range(-4, 37))
SAMPLE31_REPEAT_X_VALUES = (-12, -8, -4, -1, 1, 4, 16, 17, 31, 32, 36)
SAMPLE31_REPEAT_Y_VALUES = (-4, -2, -1, 1, 4, 8, 16, 17, 31, 32, 36)
CAPTURE_BACKDROP_SYMBOL = "_ZN2CA3OGL16capture_backdropERNS0_8RendererEPKNS0_5LayerE"
CAPTURE_BACKDROP_CODE_BYTE_COUNT = 0x4000
CAPTURE_BACKDROP_DECISION_CALL_RANGE = (0x2000, 0x2B58)
CAPTURE_BACKDROP_VERTEX_BINDING_CALL_OFFSET = 0x2B54
CAPTURE_BACKDROP_DIRECT_CALL_TARGET_CODE_BYTE_COUNT = 0x400
CAPTURE_BACKDROP_VERTEX_BINDING_RETURN_OFFSET = 0x2B58
CAPTURE_BACKDROP_FRAME_POINTER_TO_STACK_POINTER = 0xA50
CAPTURE_BACKDROP_FIRST_REGISTER = 19
CAPTURE_BACKDROP_REGISTER_COUNT = 11
CAPTURE_BACKDROP_REQUIRED_READ_MASK = 0xFF
CAPTURE_BACKDROP_EXPECTED_SYMBOL_PREFIX_SHA256 = (
    "14f25960556bec9e88ba8ade176ee7f1d39b84726226ade3eb1b0f1be00b70d2"
)
CAPTURE_BACKDROP_EXPECTED_PROLOGUE = bytes.fromhex(
    "7f2303d5ef3bb66ded33016deb2b026de923036dfc6f04a9fa6705a9f85f06a9"
    "f65707a9f44f08a9fd7b09a9fd430291ff0327d1"
)
CAPTURE_BACKDROP_STACK_OFFSETS = {
    "originPointer": 0x190,
    "shapePointer": 0x1A0,
    "transformPointer": 0x1A8,
    "contextPointer": 0x220,
    "rect": 0x280,
    "affine": 0x390,
}
CAPTURE_BACKDROP_CONTEXT_SCALE_OFFSET = 0x18
CAPTURE_BACKDROP_OPERAND_LAYOUTS = {
    "registers": (
        "little-endian x19-through-x29 words",
        8 * CAPTURE_BACKDROP_REGISTER_COUNT,
    ),
    "rect": ("four little-endian signed 32-bit rectangle words", 16),
    "affine": ("six little-endian binary64 affine words", 48),
    "origin": ("two little-endian signed 32-bit origin words", 8),
    "scale": ("one little-endian binary32 scale word", 4),
}
SCAN_VALUES_BY_SAMPLE = {
    25: (FINE_X_VALUES, FINE_Y_VALUES),
    31: (CROSS_AXIS_X_VALUES, CROSS_AXIS_Y_VALUES),
}
SCAN_PHASES_BY_SAMPLE = {
    25: "fine-threshold",
    31: "cross-axis-scan",
}
INVARIANT_FIELDS = (
    "cropOrigin",
    "textureCoordinateClamp",
    "producerExtent",
    "destinationExtent",
    "copyOffset",
    "effectiveOrigin",
)
DECODED_MESH_FIELDS = (
    "fragmentFunction",
    "vertexCount",
    "indexCount",
    "primaryVertices",
    "quadBounds",
    "viewport",
    "scissor",
    "sourceScaleComponentCount",
    "sourceScaleMismatchedComponents",
    "allSourceScaleComponentCount",
    "allSourceScaleMismatchedComponents",
    "inputTexture",
)


def expected_interventions(sample_index: int) -> list[dict[str, Any]]:
    if sample_index not in EXPECTED_SOURCE_SAMPLE_INDICES:
        raise ValueError(f"unexpected source sample: {sample_index}")
    identifier = original.path_name(POSITION_PATH)
    result: list[dict[str, Any]] = [
        {
            "name": "base",
            "phase": "control",
            "path": (),
            "mutation": "base",
            "delta": (0, 0),
        }
    ]
    result.extend(
        {
            "name": f"strong-{identifier}-position-{name}",
            "phase": "path-isolation",
            "path": POSITION_PATH,
            "mutation": "position",
            "delta": delta,
        }
        for name, delta in STRONG_DELTAS
    )
    if sample_index != 25:
        return result
    result.extend(
        {
            "name": (f"dense-{identifier}-position-x-{original.signed_name(value)}"),
            "phase": "dense-threshold",
            "path": POSITION_PATH,
            "mutation": "position",
            "delta": (value, 0),
        }
        for value in DENSE_X_VALUES
    )
    result.extend(
        {
            "name": (f"dense-{identifier}-position-y-{original.signed_name(value)}"),
            "phase": "dense-threshold",
            "path": POSITION_PATH,
            "mutation": "position",
            "delta": (0, value),
        }
        for value in DENSE_Y_VALUES
    )
    return result


def fine_scan_interventions(sample_index: int) -> list[dict[str, Any]]:
    if sample_index not in EXPECTED_SOURCE_SAMPLE_INDICES:
        raise ValueError(f"unexpected source sample: {sample_index}")
    identifier = original.path_name(POSITION_PATH)
    x_values, y_values = SCAN_VALUES_BY_SAMPLE[sample_index]
    phase = SCAN_PHASES_BY_SAMPLE[sample_index]
    prefix = "fine" if sample_index == 25 else "cross-axis"
    result: list[dict[str, Any]] = [
        {
            "name": "base",
            "phase": "control",
            "path": (),
            "mutation": "base",
            "delta": (0, 0),
        }
    ]
    result.extend(
        {
            "name": (f"{prefix}-{identifier}-position-x-{original.signed_name(value)}"),
            "phase": phase,
            "path": POSITION_PATH,
            "mutation": "position",
            "delta": (value, 0),
        }
        for value in x_values
    )
    result.extend(
        {
            "name": (f"{prefix}-{identifier}-position-y-{original.signed_name(value)}"),
            "phase": phase,
            "path": POSITION_PATH,
            "mutation": "position",
            "delta": (0, value),
        }
        for value in y_values
    )
    return result


def sample31_repeat_interventions(sample_index: int) -> list[dict[str, Any]]:
    if sample_index not in SAMPLE31_REPEAT_SOURCE_SAMPLE_INDICES:
        raise ValueError(f"unexpected sample-31 repeat source: {sample_index}")
    identifier = original.path_name(POSITION_PATH)
    result: list[dict[str, Any]] = [
        {
            "name": "base",
            "phase": "control",
            "path": (),
            "mutation": "base",
            "delta": (0, 0),
        }
    ]
    result.extend(
        {
            "name": (
                f"sample31-unit-{identifier}-position-x-{original.signed_name(value)}"
            ),
            "phase": "sample31-unit-scan",
            "path": POSITION_PATH,
            "mutation": "position",
            "delta": (value, 0),
        }
        for value in SAMPLE31_UNIT_X_VALUES
    )
    result.extend(
        {
            "name": (
                f"sample31-unit-{identifier}-position-y-{original.signed_name(value)}"
            ),
            "phase": "sample31-unit-scan",
            "path": POSITION_PATH,
            "mutation": "position",
            "delta": (0, value),
        }
        for value in SAMPLE31_UNIT_Y_VALUES
    )
    result.append(
        {
            "name": "repeat-base",
            "phase": "repeat-control",
            "path": (),
            "mutation": "base",
            "delta": (0, 0),
        }
    )
    result.extend(
        {
            "name": (f"repeat-{identifier}-position-x-{original.signed_name(value)}"),
            "phase": "repeat-control",
            "path": POSITION_PATH,
            "mutation": "position",
            "delta": (value, 0),
        }
        for value in SAMPLE31_REPEAT_X_VALUES
    )
    result.extend(
        {
            "name": (f"repeat-{identifier}-position-y-{original.signed_name(value)}"),
            "phase": "repeat-control",
            "path": POSITION_PATH,
            "mutation": "position",
            "delta": (0, value),
        }
        for value in SAMPLE31_REPEAT_Y_VALUES
    )
    return result


def live_baseline_states(
    states: Sequence[Any], delta: tuple[int, int]
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    target_count = 0
    for value in states:
        state = copy.deepcopy(dict(holdout.mapping(value, "live layer state")))
        path = tuple(
            int(component)
            for component in fixed.sequence(state.get("path"), "live layer path")
        )
        if path == POSITION_PATH:
            position = list(fixed.sequence(state.get("position"), "live position"))
            if len(position) != 2:
                raise ValueError("deepest SDF position is not a point")
            position[0] = holdout.numeric(position[0], "position X") + delta[0]
            position[1] = holdout.numeric(position[1], "position Y") + delta[1]
            state["position"] = position
            target_count += 1
        result.append(state)
    if target_count != 1:
        raise ValueError("deepest SDF live target is not unique")
    return result


def decoded_policy_exact(
    expected: Mapping[str, Any], observed: Mapping[str, Any]
) -> bool:
    for field in INVARIANT_FIELDS:
        if expected.get(field) != observed.get(field):
            return False
    expected_mesh = holdout.mapping(expected.get("producerMesh"), "expected mesh")
    observed_mesh = holdout.mapping(observed.get("producerMesh"), "observed mesh")
    return all(
        expected_mesh.get(field) == observed_mesh.get(field)
        for field in DECODED_MESH_FIELDS
    )


def hexadecimal_bytes(record: Mapping[str, Any], label: str) -> bytes:
    hex_payload = record.get("hex")
    if not isinstance(hex_payload, str):
        raise ValueError(f"{label} payload differs")
    try:
        return bytes.fromhex(hex_payload)
    except ValueError as error:
        raise ValueError(f"{label} payload is not hexadecimal") from error


def hexadecimal_address(value: Any, label: str) -> int:
    if not isinstance(value, str):
        raise ValueError(f"{label} differs")
    try:
        address = int(value, 16)
    except ValueError as error:
        raise ValueError(f"{label} is not hexadecimal") from error
    if address < 0:
        raise ValueError(f"{label} is negative")
    return address


def capture_backdrop_operand_bytes(
    operands: Mapping[str, Any], field: str
) -> bytes:
    class_name, expected_length = CAPTURE_BACKDROP_OPERAND_LAYOUTS[field]
    record = holdout.mapping(
        operands.get(field), f"capture_backdrop {field} operands"
    )
    payload = hexadecimal_bytes(record, f"capture_backdrop {field} operands")
    if (
        record.get("class") != class_name
        or record.get("lengthBytes") != expected_length
        or len(payload) != expected_length
        or record.get("sha256") != hashlib.sha256(payload).hexdigest()
    ):
        raise ValueError(f"capture_backdrop {field} operand metadata differs")
    return payload


def float32_fma(multiplier: float, multiplicand: float, addend: float) -> float:
    return holdout.float32(math.fma(multiplier, multiplicand, addend))


def capture_backdrop_primary_position_bits(
    *,
    rect: Sequence[int],
    affine: Sequence[float],
    origin: Sequence[int],
    scale: float,
) -> list[int]:
    if (
        len(rect) != 4
        or len(affine) != 6
        or len(origin) != 2
        or not math.isfinite(scale)
        or scale <= 0
        or not all(math.isfinite(value) for value in affine)
    ):
        raise ValueError("capture_backdrop arithmetic operands differ")

    x, y, width, height = rect
    if width <= 0 or height <= 0:
        raise ValueError("capture_backdrop rectangle extent differs")
    float_x = holdout.float32(float(x))
    float_y = holdout.float32(float(y))
    float_right = holdout.float32(float(x + width))
    float_bottom = holdout.float32(float(y + height))
    scale = holdout.float32(scale)
    products = [
        holdout.float32(scale * value)
        for value in (float_x, float_y, float_right, float_bottom)
    ]
    rounded = [
        holdout.float32(math.floor(products[0])),
        holdout.float32(math.floor(products[1])),
        holdout.float32(math.ceil(products[2])),
        holdout.float32(math.ceil(products[3])),
    ]
    residuals = [
        float32_fma(-scale, value, integral)
        for value, integral in zip(
            (float_x, float_y, float_right, float_bottom),
            rounded,
            strict=True,
        )
    ]
    inverse_scale = holdout.float32(1.0 / scale)
    snapped = [
        holdout.float32(holdout.float32(residual * inverse_scale) + value)
        for residual, value in zip(
            residuals,
            (float_x, float_y, float_right, float_bottom),
            strict=True,
        )
    ]

    a, b, c, d, translate_x, translate_y = affine
    x0, y0, x1, y1 = snapped
    corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    origin_x = holdout.float32(float(origin[0]))
    origin_y = holdout.float32(float(origin[1]))
    result: list[int] = []
    for corner_x, corner_y in corners:
        transformed_x = math.fma(
            c,
            float(corner_y),
            math.fma(a, float(corner_x), translate_x),
        )
        transformed_y = math.fma(
            d,
            float(corner_y),
            math.fma(b, float(corner_x), translate_y),
        )
        position_x = holdout.float32(
            holdout.float32(transformed_x) - origin_x
        )
        position_y = holdout.float32(
            holdout.float32(transformed_y) - origin_y
        )
        result.extend(
            (holdout.float32_bits(position_x), holdout.float32_bits(position_y))
        )
    return result


def validate_capture_backdrop_operands(
    untyped_operands: Any,
) -> dict[str, Any]:
    operands = holdout.mapping(
        untyped_operands, "capture_backdrop operand evidence"
    )
    symbol_address = hexadecimal_address(
        operands.get("symbolAddress"), "capture_backdrop operand symbol address"
    )
    instruction_pointer = hexadecimal_address(
        operands.get("instructionPointer"),
        "capture_backdrop operand instruction pointer",
    )
    canonical_frame_address = hexadecimal_address(
        operands.get("canonicalFrameAddress"),
        "capture_backdrop canonical frame address",
    )
    frame_pointer = hexadecimal_address(
        operands.get("framePointer"), "capture_backdrop frame pointer"
    )
    stack_pointer = hexadecimal_address(
        operands.get("stackPointer"), "capture_backdrop stack pointer"
    )
    origin_pointer = hexadecimal_address(
        operands.get("originPointer"), "capture_backdrop origin pointer"
    )
    shape_pointer = hexadecimal_address(
        operands.get("shapePointer"), "capture_backdrop shape pointer"
    )
    transform_pointer = hexadecimal_address(
        operands.get("transformPointer"), "capture_backdrop transform pointer"
    )
    context_pointer = hexadecimal_address(
        operands.get("contextPointer"), "capture_backdrop context pointer"
    )
    registers_payload = capture_backdrop_operand_bytes(operands, "registers")
    registers = list(
        struct.unpack(f"<{CAPTURE_BACKDROP_REGISTER_COUNT}Q", registers_payload)
    )
    rect_payload = capture_backdrop_operand_bytes(operands, "rect")
    affine_payload = capture_backdrop_operand_bytes(operands, "affine")
    origin_payload = capture_backdrop_operand_bytes(operands, "origin")
    scale_payload = capture_backdrop_operand_bytes(operands, "scale")
    rect = list(struct.unpack("<4i", rect_payload))
    affine = list(struct.unpack("<6d", affine_payload))
    origin = list(struct.unpack("<2i", origin_payload))
    scale = struct.unpack("<f", scale_payload)[0]
    read_mask = hexadecimal_address(
        operands.get("readMask"), "capture_backdrop read mask"
    )
    required_read_mask = hexadecimal_address(
        operands.get("requiredReadMask"),
        "capture_backdrop required read mask",
    )
    if (
        operands.get("schemaVersion") != 1
        or operands.get("executed") is not True
        or operands.get("class")
        != "bounded live capture_backdrop unwind operands"
        or operands.get("symbol") != CAPTURE_BACKDROP_SYMBOL
        or operands.get("returnSymbolOffset")
        != CAPTURE_BACKDROP_VERTEX_BINDING_RETURN_OFFSET
        or instruction_pointer
        != symbol_address + CAPTURE_BACKDROP_VERTEX_BINDING_RETURN_OFFSET
        or operands.get("framePointerToStackPointerDelta")
        != CAPTURE_BACKDROP_FRAME_POINTER_TO_STACK_POINTER
        or frame_pointer
        != stack_pointer + CAPTURE_BACKDROP_FRAME_POINTER_TO_STACK_POINTER
        or stack_pointer & 0xF
        or canonical_frame_address == 0
        or not 1 <= operands.get("visitedFrameCount", 0) <= 32
        or operands.get("firstRegister") != CAPTURE_BACKDROP_FIRST_REGISTER
        or operands.get("registerCount") != CAPTURE_BACKDROP_REGISTER_COUNT
        or operands.get("stackOffsets") != CAPTURE_BACKDROP_STACK_OFFSETS
        or operands.get("contextScaleOffset")
        != CAPTURE_BACKDROP_CONTEXT_SCALE_OFFSET
        or read_mask != CAPTURE_BACKDROP_REQUIRED_READ_MASK
        or required_read_mask != CAPTURE_BACKDROP_REQUIRED_READ_MASK
        or registers[29 - CAPTURE_BACKDROP_FIRST_REGISTER] != frame_pointer
        or registers[26 - CAPTURE_BACKDROP_FIRST_REGISTER] != origin_pointer
        or registers[27 - CAPTURE_BACKDROP_FIRST_REGISTER] != context_pointer
        or origin_pointer == 0
        or context_pointer == 0
        or transform_pointer == 0
    ):
        raise ValueError("capture_backdrop operand metadata differs")
    predicted_position_bits = capture_backdrop_primary_position_bits(
        rect=rect,
        affine=affine,
        origin=origin,
        scale=scale,
    )
    return {
        "symbolAddress": symbol_address,
        "instructionPointer": instruction_pointer,
        "canonicalFrameAddress": canonical_frame_address,
        "framePointer": frame_pointer,
        "stackPointer": stack_pointer,
        "shapePointerNonzero": shape_pointer != 0,
        "transformPointerNonzero": transform_pointer != 0,
        "rect": rect,
        "affine": affine,
        "origin": origin,
        "scale": scale,
        "scaleBits": struct.unpack("<I", scale_payload)[0],
        "predictedPrimaryPositionBits": predicted_position_bits,
    }


def arm64_branch_link_target(instruction: int, address: int) -> int | None:
    if instruction & 0xFC00_0000 != 0x9400_0000:
        return None
    immediate = instruction & 0x03FF_FFFF
    if immediate & 0x0200_0000:
        immediate -= 0x0400_0000
    target = address + immediate * 4
    return target if target >= 0 else None


def validate_capture_backdrop_code(
    untyped_capture: Any,
    *,
    frame: Mapping[str, Any],
) -> dict[str, Any]:
    capture = holdout.mapping(untyped_capture, "capture_backdrop code evidence")
    payload = hexadecimal_bytes(capture, "capture_backdrop symbol-prefix")
    symbol_address = hexadecimal_address(
        capture.get("startAddress"), "capture_backdrop start address"
    )
    frame_symbol_address = hexadecimal_address(
        frame.get("symbolAddress"), "capture_backdrop frame symbol address"
    )
    frame_return_address = hexadecimal_address(
        frame.get("returnAddress"), "capture_backdrop frame return address"
    )
    frame_symbol_offset = hexadecimal_address(
        frame.get("symbolOffset"), "capture_backdrop frame symbol offset"
    )
    image_base = hexadecimal_address(
        frame.get("imageBase"), "capture_backdrop frame image base"
    )
    frame_image_offset = hexadecimal_address(
        frame.get("imageOffset"), "capture_backdrop frame image offset"
    )
    capture_image_offset = hexadecimal_address(
        capture.get("imageOffset"), "capture_backdrop code image offset"
    )
    call_range = tuple(
        int(value)
        for value in fixed.sequence(
            capture.get("decisionDirectCallRange"),
            "capture_backdrop decision call range",
        )
    )
    if (
        capture.get("class")
        != "mapped arm64e QuartzCore symbol prefix and direct calls"
        or capture.get("symbol") != CAPTURE_BACKDROP_SYMBOL
        or frame.get("symbol") != CAPTURE_BACKDROP_SYMBOL
        or symbol_address != frame_symbol_address
        or frame_symbol_address < image_base
        or frame_return_address < frame_symbol_address
        or frame_symbol_offset != frame_return_address - frame_symbol_address
        or frame_symbol_offset
        != CAPTURE_BACKDROP_VERTEX_BINDING_CALL_OFFSET + 4
        or frame_image_offset != frame_return_address - image_base
        or capture_image_offset != frame_symbol_address - image_base
        or capture.get("requestedByteCount") != CAPTURE_BACKDROP_CODE_BYTE_COUNT
        or capture.get("lengthBytes") != len(payload)
        or len(payload) != CAPTURE_BACKDROP_CODE_BYTE_COUNT
        or capture.get("sha256") != hashlib.sha256(payload).hexdigest()
        or call_range != CAPTURE_BACKDROP_DECISION_CALL_RANGE
    ):
        raise ValueError("capture_backdrop symbol-prefix metadata differs")

    lower, upper = call_range
    expected_calls: list[tuple[int, int, int]] = []
    for offset in range(lower, upper, 4):
        instruction = int.from_bytes(payload[offset : offset + 4], "little")
        target = arm64_branch_link_target(instruction, symbol_address + offset)
        if target is not None:
            expected_calls.append((offset, instruction, target))
    calls = [
        holdout.mapping(value, "capture_backdrop direct call")
        for value in fixed.sequence(
            capture.get("directCalls"), "capture_backdrop direct calls"
        )
    ]
    if capture.get("decisionDirectCallCount") != len(calls) or len(calls) != len(
        expected_calls
    ):
        raise ValueError("capture_backdrop direct-call count differs")

    target_code_hashes: list[str] = []
    call_offsets: list[int] = []
    for call, (offset, instruction, target) in zip(calls, expected_calls, strict=True):
        target_code = holdout.mapping(
            call.get("targetCode"), "capture_backdrop direct-call target code"
        )
        target_payload = hexadecimal_bytes(
            target_code, "capture_backdrop direct-call target code"
        )
        target_path = call.get("targetImagePath")
        if (
            call.get("sourceInstructionOffset") != offset
            or call.get("sourceInstruction") != f"{instruction:08x}"
            or hexadecimal_address(
                call.get("sourceInstructionAddress"),
                "capture_backdrop source instruction address",
            )
            != symbol_address + offset
            or hexadecimal_address(
                call.get("targetAddress"), "capture_backdrop target address"
            )
            != target
            or hexadecimal_address(
                call.get("targetImageBase"),
                "capture_backdrop target image base",
            )
            != image_base
            or hexadecimal_address(
                call.get("targetImageOffset"),
                "capture_backdrop target image offset",
            )
            != target - image_base
            or not isinstance(target_path, str)
            or "/QuartzCore.framework/" not in target_path
            or target_code.get("class")
            != "mapped arm64e QuartzCore direct-call target prefix"
            or hexadecimal_address(
                target_code.get("startAddress"),
                "capture_backdrop target-code start address",
            )
            != target
            or target_code.get("requestedByteCount")
            != CAPTURE_BACKDROP_DIRECT_CALL_TARGET_CODE_BYTE_COUNT
            or target_code.get("lengthBytes") != len(target_payload)
            or len(target_payload)
            != CAPTURE_BACKDROP_DIRECT_CALL_TARGET_CODE_BYTE_COUNT
            or target_code.get("sha256") != hashlib.sha256(target_payload).hexdigest()
        ):
            raise ValueError("capture_backdrop direct-call metadata differs")
        call_offsets.append(offset)
        target_code_hashes.append(hashlib.sha256(target_payload).hexdigest())

    if CAPTURE_BACKDROP_VERTEX_BINDING_CALL_OFFSET not in call_offsets:
        raise ValueError("capture_backdrop producer binding call is absent")
    return {
        "symbol": CAPTURE_BACKDROP_SYMBOL,
        "symbolAddress": symbol_address,
        "symbolPrefixSHA256": hashlib.sha256(payload).hexdigest(),
        "symbolPrefixByteCount": len(payload),
        "operandFramePrologueExact": payload.startswith(
            CAPTURE_BACKDROP_EXPECTED_PROLOGUE
        ),
        "decisionDirectCallRange": list(call_range),
        "decisionDirectCallCount": len(calls),
        "decisionDirectCallOffsets": call_offsets,
        "directCallTargetCodeCaptureCount": len(target_code_hashes),
        "directCallTargetCodeSHA256": target_code_hashes,
        "producerVertexBindingCallOffset": (
            CAPTURE_BACKDROP_VERTEX_BINDING_CALL_OFFSET
        ),
    }


def validate_producer_geometry_call_site(
    untyped_call_site: Any,
) -> dict[str, Any]:
    call_site = holdout.mapping(
        untyped_call_site, "producer geometry call-site evidence"
    )
    frames = [
        holdout.mapping(value, "producer geometry call-site frame")
        for value in fixed.sequence(call_site.get("frames"), "call-site frames")
    ]
    code_window_count = 0
    code_window_hashes: list[str] = []
    capture_backdrop_records: list[dict[str, Any]] = []
    for frame in frames:
        if "captureBackdropCode" in frame:
            capture_backdrop_records.append(
                validate_capture_backdrop_code(
                    frame["captureBackdropCode"], frame=frame
                )
            )
        if "codeWindow" not in frame:
            continue
        window = holdout.mapping(frame.get("codeWindow"), "call-site code window")
        payload = hexadecimal_bytes(window, "producer geometry code-window")
        digest = hashlib.sha256(payload).hexdigest()
        image_path = frame.get("imagePath")
        if (
            not isinstance(image_path, str)
            or "/QuartzCore.framework/" not in image_path
            or window.get("class") != "mapped arm64e call-site window"
            or window.get("returnInstructionOffset") != 0x400
            or window.get("lengthBytes") != len(payload)
            or window.get("lengthBytes") != 0x800
            or window.get("sha256") != digest
        ):
            raise ValueError("producer geometry code-window metadata differs")
        code_window_count += 1
        code_window_hashes.append(digest)
    schema_version = call_site.get("schemaVersion")
    if (
        schema_version not in {4, 5}
        or call_site.get("executed") is not True
        or call_site.get("capture") != "transition-path-isolation-31-000"
        or call_site.get("purpose") != "producer-primary-mesh-vertex-buffer-binding"
        or call_site.get("frameCount") != len(frames)
        or call_site.get("quartzCoreCodeWindowCount") != code_window_count
    ):
        raise ValueError("producer geometry call-site evidence differs")
    if schema_version == 5:
        if (
            len(capture_backdrop_records) != 1
            or call_site.get("captureBackdropCodeCaptureCount") != 1
            or call_site.get("captureBackdropDecisionDirectCallCount")
            != capture_backdrop_records[0]["decisionDirectCallCount"]
            or call_site.get("captureBackdropDirectCallTargetCodeCaptureCount")
            != capture_backdrop_records[0]["directCallTargetCodeCaptureCount"]
            or capture_backdrop_records[0]["decisionDirectCallCount"]
            != capture_backdrop_records[0]["directCallTargetCodeCaptureCount"]
        ):
            raise ValueError("capture_backdrop code-capture summary differs")
    elif capture_backdrop_records:
        raise ValueError("schema-4 call-site unexpectedly contains schema-5 code")
    return {
        "captured": True,
        "schemaVersion": schema_version,
        "frameCount": len(frames),
        "quartzCoreCodeWindowCount": code_window_count,
        "quartzCoreCodeWindowSHA256": code_window_hashes,
        "glassBackgroundRenderCodeCaptureCount": call_site.get(
            "glassBackgroundRenderCodeCaptureCount"
        ),
        "glassMatrixConstructorCodeCaptureCount": call_site.get(
            "glassMatrixConstructorCodeCaptureCount"
        ),
        "glassMatrixConstructorConstantDataCaptureCount": call_site.get(
            "glassMatrixConstructorConstantDataCaptureCount"
        ),
        "captureBackdrop": (
            capture_backdrop_records[0] if capture_backdrop_records else None
        ),
    }


def validate(path: Path) -> dict[str, Any]:
    report = holdout.mapping(
        json.loads(path.read_text(encoding="utf-8")), "transition report"
    )
    uniforms = holdout.mapping(
        report.get("dynamicBackgroundUniforms"), "dynamic background uniforms"
    )
    evidence = holdout.mapping(
        uniforms.get("pathIsolationInterventions"), "surviving-path evidence"
    )
    evidence_schema = evidence.get("schemaVersion")
    if evidence_schema == 2:
        classification = CLASSIFICATION
        result_schema = 1
        intervention_builder = expected_interventions
        source_sample_indices = EXPECTED_SOURCE_SAMPLE_INDICES
    elif evidence_schema == 3:
        classification = FINE_SCAN_CLASSIFICATION
        result_schema = 2
        intervention_builder = fine_scan_interventions
        source_sample_indices = EXPECTED_SOURCE_SAMPLE_INDICES
    elif evidence_schema in {4, 5}:
        classification = (
            SAMPLE31_REPEAT_CLASSIFICATION
            if evidence_schema == 4
            else CAPTURE_BACKDROP_OPERAND_CLASSIFICATION
        )
        result_schema = 3 if evidence_schema == 4 else 4
        intervention_builder = sample31_repeat_interventions
        source_sample_indices = SAMPLE31_REPEAT_SOURCE_SAMPLE_INDICES
    else:
        raise ValueError("surviving-path evidence schema differs")
    base = holdout.validate(
        path,
        expected_geometry=EXPECTED_GEOMETRY,
        expected_sample_indices=EXPECTED_SAMPLE_INDICES,
        classification=classification,
        allowed_geometries=frozenset({EXPECTED_GEOMETRY}),
        require_primary_source_q_exact=False,
    )
    expected_by_sample = {
        sample: intervention_builder(sample) for sample in source_sample_indices
    }
    expected_counts = {
        str(sample): len(interventions)
        for sample, interventions in expected_by_sample.items()
    }
    expected_count = sum(expected_counts.values())
    if (
        evidence.get("requested") is not True
        or evidence.get("executed") is not True
        or evidence.get("sourceSampleIndices") != list(source_sample_indices)
        or evidence.get("sourceInterventionCounts") != expected_counts
        or evidence.get("expectedRecordCount") != expected_count
        or evidence.get("executedRecordCount") != expected_count
        or evidence.get("liveRenderBoundaryReadback") is not True
        or evidence.get("maximumRenderAttemptCount") != 3
        or evidence.get("renderBufferRetentionPolicy") != BUFFER_RETENTION_POLICY
        or not holdout.no_raw_stage_dumps(evidence)
    ):
        raise ValueError("surviving-path evidence header differs")
    if evidence_schema == 2:
        if (
            evidence.get("strongPaths") != [list(POSITION_PATH)]
            or evidence.get("strongDeltas")
            != [{"name": name, "delta": list(delta)} for name, delta in STRONG_DELTAS]
            or evidence.get("denseSampleIndex") != 25
            or evidence.get("densePath") != list(POSITION_PATH)
            or evidence.get("denseMutation") != "position"
            or evidence.get("denseXValues") != list(DENSE_X_VALUES)
            or evidence.get("denseYValues") != list(DENSE_Y_VALUES)
        ):
            raise ValueError("surviving-path schema-2 matrix header differs")
    elif evidence_schema == 3 and (
        evidence.get("scanPath") != list(POSITION_PATH)
        or evidence.get("scanMutation") != "position"
        or evidence.get("scanPhasesBySample")
        != {str(sample): phase for sample, phase in SCAN_PHASES_BY_SAMPLE.items()}
        or evidence.get("scanXValuesBySample")
        != {
            str(sample): list(values[0])
            for sample, values in SCAN_VALUES_BY_SAMPLE.items()
        }
        or evidence.get("scanYValuesBySample")
        != {
            str(sample): list(values[1])
            for sample, values in SCAN_VALUES_BY_SAMPLE.items()
        }
    ):
        raise ValueError("surviving-path schema-3 matrix header differs")
    elif evidence_schema in {4, 5} and (
        evidence.get("scanPath") != list(POSITION_PATH)
        or evidence.get("scanMutation") != "position"
        or evidence.get("scanSampleIndex") != 31
        or evidence.get("scanPhase") != "sample31-unit-scan"
        or evidence.get("scanXValues") != list(SAMPLE31_UNIT_X_VALUES)
        or evidence.get("scanYValues") != list(SAMPLE31_UNIT_Y_VALUES)
        or evidence.get("repeatPhase") != "repeat-control"
        or evidence.get("repeatBase") is not True
        or evidence.get("repeatXValues") != list(SAMPLE31_REPEAT_X_VALUES)
        or evidence.get("repeatYValues") != list(SAMPLE31_REPEAT_Y_VALUES)
    ):
        raise ValueError("surviving-path schema-4 matrix header differs")

    records = [
        holdout.mapping(value, "surviving-path record")
        for value in fixed.sequence(evidence.get("records"), "surviving-path records")
    ]
    if len(records) != expected_count:
        raise ValueError("surviving-path record count differs")
    expected_order = [
        (sample, index, intervention)
        for sample in source_sample_indices
        for index, intervention in enumerate(expected_by_sample[sample])
    ]
    normal_records = {
        int(holdout.mapping(value, "normal record")["sampleIndex"]): holdout.mapping(
            value, "normal record"
        )
        for value in fixed.sequence(uniforms.get("records"), "normal records")
    }
    normal_states = {
        int(holdout.mapping(value, "normal state")["sampleIndex"]): holdout.mapping(
            value, "normal state"
        )
        for value in fixed.sequence(base.get("states"), "normal states")
    }

    source_layer_hashes: dict[int, str] = {}
    source_filter_hashes: dict[int, str] = {}
    live_bases: dict[int, list[Any]] = {}
    observed_bases: dict[int, Mapping[str, Any]] = {}
    selected_attempt_counts: Counter[int] = Counter()
    topology_counts: Counter[int] = Counter()
    phase_counts: Counter[str] = Counter()
    retained_buffer_count = 0
    q_components = 0
    q_mismatches = 0
    invariant_components = 0
    invariant_mismatches = 0
    base_decoded_matches = 0
    base_vertex_hash_matches = 0
    base_mvp_hash_matches = 0
    base_index_hash_matches = 0
    producer_geometry_call_sites: list[Any] = []
    capture_backdrop_operand_count = 0
    capture_backdrop_position_components = 0
    capture_backdrop_position_mismatches = 0
    capture_backdrop_symbol_addresses: set[int] = set()
    validated_records: list[dict[str, Any]] = []

    for record_index, (record, expected_item) in enumerate(
        zip(records, expected_order, strict=True)
    ):
        sample, intervention_index, intervention = expected_item
        mutation_path = tuple(
            int(value)
            for value in fixed.sequence(record.get("mutationPath"), "mutation path")
        )
        translation = tuple(
            int(value)
            for value in fixed.sequence(record.get("translation"), "translation")
        )
        if (
            record.get("recordIndex") != record_index
            or record.get("sampleIndex") != sample
            or record.get("interventionIndex") != intervention_index
            or record.get("interventionName") != intervention["name"]
            or record.get("phase") != intervention["phase"]
            or record.get("mutation") != intervention["mutation"]
            or mutation_path != intervention["path"]
            or translation != intervention["delta"]
            or record.get("mutationPathOccurrenceCount") != 1
            or record.get("executed") is not True
            or record.get("originalProducerInput") is not True
            or record.get("producerCopyBaseObserved") is not True
            or record.get("filterInputValuesUnchanged") is not True
            or record.get("liveLayerStatesStableAcrossRender") is not True
            or record.get("liveFilterInputsBeforeUnchanged") is not True
            or record.get("liveFilterInputsAfterUnchanged") is not True
            or record.get("missingCriticalCarrierPaths") != []
        ):
            raise ValueError(
                f"surviving-path record differs at {sample}/{intervention_index}"
            )

        normal = normal_records[sample]
        remaining = holdout.numeric(record.get("remaining"), "remaining")
        if remaining != holdout.numeric(normal.get("remaining"), "normal remaining"):
            raise ValueError("surviving-path remaining differs")
        source_layer_hash = record.get("sourceLayerStatesSHA256")
        source_filter_hash = record.get("sourceFilterInputValuesSHA256")
        requested_layer_hash = record.get("requestedLayerStatesSHA256")
        if (
            not isinstance(source_layer_hash, str)
            or len(source_layer_hash) != 64
            or not isinstance(source_filter_hash, str)
            or len(source_filter_hash) != 64
            or not isinstance(requested_layer_hash, str)
            or len(requested_layer_hash) != 64
            or record.get("replayedFilterInputValuesSHA256") != source_filter_hash
            or source_layer_hashes.setdefault(sample, source_layer_hash)
            != source_layer_hash
            or source_filter_hashes.setdefault(sample, source_filter_hash)
            != source_filter_hash
        ):
            raise ValueError("surviving-path source identity differs")

        expected_requested = original.requested_layer_states(
            fixed.sequence(normal.get("capturedLayerStates"), "normal layer states"),
            intervention,
        )
        requested_states = list(
            fixed.sequence(record.get("requestedLayerStates"), "requested states")
        )
        before = holdout.mapping(
            record.get("liveRenderBoundaryBefore"), "live boundary before"
        )
        after = holdout.mapping(
            record.get("liveRenderBoundaryAfter"), "live boundary after"
        )
        before_states = list(
            fixed.sequence(before.get("layerStates"), "live states before")
        )
        after_states = list(
            fixed.sequence(after.get("layerStates"), "live states after")
        )
        captured_states = list(
            fixed.sequence(record.get("capturedLayerStates"), "captured states")
        )
        if intervention["phase"] == "control":
            live_bases[sample] = before_states
        if sample not in live_bases:
            raise ValueError("surviving-path base does not precede intervention")
        expected_live = live_baseline_states(live_bases[sample], translation)
        if (
            requested_states != expected_requested
            or before_states != expected_live
            or after_states != expected_live
            or captured_states != before_states
            or before.get("schemaVersion") != 1
            or before.get("executed") is not True
            or after.get("schemaVersion") != 1
            or after.get("executed") is not True
            or before.get("layerStatesSHA256") != after.get("layerStatesSHA256")
            or before.get("backgroundFilterPath") != list(holdout.BACKDROP_LAYER_PATH)
            or after.get("backgroundFilterPath") != list(holdout.BACKDROP_LAYER_PATH)
            or before.get("backgroundFilterInputValuesSHA256") != source_filter_hash
            or after.get("backgroundFilterInputValuesSHA256") != source_filter_hash
        ):
            raise ValueError("surviving-path live baseline rule differs")

        original.validate_attempts(record)
        selected_attempt = int(record["selectedRenderAttemptIndex"])
        selected_attempt_counts[selected_attempt] += 1
        scale, layer_state_count = holdout.captured_scale(record)
        if scale != 1.0 - remaining / 2.0:
            raise ValueError("surviving-path backdrop scale differs")
        render = holdout.mapping(record.get("render"), "surviving-path render")
        retained_buffer_count += original.validate_retained_buffers(render)
        retained_buffers = holdout.mapping(
            render.get("metalBufferSnapshots"), "retained Metal buffers"
        )
        record_operand_payloads: list[Any] = []
        for untyped_snapshot in fixed.sequence(
            retained_buffers.get("snapshots"), "retained snapshots"
        ):
            snapshot = holdout.mapping(untyped_snapshot, "retained snapshot")
            if "producerGeometryCallSite" in snapshot:
                producer_geometry_call_sites.append(
                    snapshot["producerGeometryCallSite"]
                )
            if "captureBackdropOperands" in snapshot:
                record_operand_payloads.append(
                    snapshot["captureBackdropOperands"]
                )
        if evidence_schema == 5:
            if len(record_operand_payloads) != 1:
                raise ValueError(
                    "capture_backdrop operand capture count differs at "
                    f"{sample}/{intervention_index}"
                )
            capture_backdrop_operands = validate_capture_backdrop_operands(
                record_operand_payloads[0]
            )
        elif record_operand_payloads:
            raise ValueError(
                "schema-4 record unexpectedly contains capture_backdrop operands"
            )
        else:
            capture_backdrop_operands = None
        observed = holdout.observed_policy(record, scale=scale)
        mesh = holdout.mapping(observed.get("producerMesh"), "producer mesh")
        q_components += int(mesh["sourceScaleComponentCount"])
        q_mismatches += int(mesh["sourceScaleMismatchedComponents"])
        topology_counts[int(mesh["vertexCount"])] += 1
        phase_counts[str(intervention["phase"])] += 1

        if capture_backdrop_operands is not None:
            primary_vertices = fixed.sequence(
                mesh.get("primaryVertices"), "primary producer vertices"
            )
            if len(primary_vertices) != 4:
                raise ValueError("primary producer vertex count differs")
            observed_position_bits = [
                holdout.float32_bits(
                    holdout.numeric(component, "primary position component")
                )
                for vertex in primary_vertices
                for component in fixed.sequence(vertex, "primary vertex")[:2]
            ]
            predicted_position_bits = capture_backdrop_operands[
                "predictedPrimaryPositionBits"
            ]
            if capture_backdrop_operands["scaleBits"] != holdout.float32_bits(
                scale
            ):
                raise ValueError("capture_backdrop context scale differs")
            capture_backdrop_operand_count += 1
            capture_backdrop_position_components += len(observed_position_bits)
            capture_backdrop_position_mismatches += sum(
                predicted != observed
                for predicted, observed in zip(
                    predicted_position_bits,
                    observed_position_bits,
                    strict=True,
                )
            )
            capture_backdrop_symbol_addresses.add(
                int(capture_backdrop_operands["symbolAddress"])
            )
            capture_backdrop_operands = {
                **capture_backdrop_operands,
                "observedPrimaryPositionBits": observed_position_bits,
                "primaryPositionExact": (
                    predicted_position_bits == observed_position_bits
                ),
            }

        if intervention["phase"] == "control":
            observed_bases[sample] = observed
            normal_observed = holdout.mapping(
                normal_states[sample].get("observed"), "normal observed policy"
            )
            base_decoded_matches += decoded_policy_exact(normal_observed, observed)
            normal_mesh = holdout.mapping(
                normal_observed.get("producerMesh"), "normal producer mesh"
            )
            base_vertex_hash_matches += mesh.get(
                "vertexDrawConsumedPayloadSHA256"
            ) == normal_mesh.get("vertexDrawConsumedPayloadSHA256")
            base_mvp_hash_matches += mesh.get(
                "mvpDrawConsumedPayloadSHA256"
            ) == normal_mesh.get("mvpDrawConsumedPayloadSHA256")
            base_index_hash_matches += mesh.get(
                "indexDrawConsumedPayloadSHA256"
            ) == normal_mesh.get("indexDrawConsumedPayloadSHA256")
        reference = observed_bases.get(sample)
        if reference is None:
            raise ValueError("surviving-path observed base is missing")
        for field in INVARIANT_FIELDS:
            expected_values = fixed.sequence(reference.get(field), f"base {field}")
            actual_values = fixed.sequence(observed.get(field), f"observed {field}")
            if len(expected_values) != len(actual_values):
                raise ValueError(f"surviving-path invariant length differs: {field}")
            invariant_components += len(expected_values)
            invariant_mismatches += sum(
                expected != actual
                for expected, actual in zip(expected_values, actual_values, strict=True)
            )

        validated_records.append(
            {
                "recordIndex": record_index,
                "sampleIndex": sample,
                "remaining": remaining,
                "runtimeScale": scale,
                "interventionIndex": intervention_index,
                "interventionName": intervention["name"],
                "phase": intervention["phase"],
                "mutationPath": list(intervention["path"]),
                "mutation": intervention["mutation"],
                "translation": list(intervention["delta"]),
                "capturedLayerStateCount": layer_state_count,
                "selectedRenderAttemptIndex": selected_attempt,
                "observed": observed,
                **(
                    {"captureBackdropOperands": capture_backdrop_operands}
                    if capture_backdrop_operands is not None
                    else {}
                ),
            }
        )

    source_count = len(source_sample_indices)
    if (
        q_mismatches != 0
        or invariant_mismatches != 0
        or base_decoded_matches != source_count
        or base_mvp_hash_matches != source_count
        or base_index_hash_matches != source_count
    ):
        raise ValueError(
            "surviving-path exact integrity gate failed: "
            f"q={q_components - q_mismatches}/{q_components}, "
            "allocation="
            f"{invariant_components - invariant_mismatches}/"
            f"{invariant_components}, "
            f"baseDecoded={base_decoded_matches}/{source_count}, "
            f"baseMVP={base_mvp_hash_matches}/{source_count}, "
            f"baseIndex={base_index_hash_matches}/{source_count}"
        )
    if len(producer_geometry_call_sites) > 1:
        raise ValueError("multiple producer geometry call-site captures survived")
    producer_geometry_call_site = (
        validate_producer_geometry_call_site(producer_geometry_call_sites[0])
        if producer_geometry_call_sites
        else {"captured": False}
    )
    if evidence_schema == 5:
        capture_backdrop_code = holdout.mapping(
            producer_geometry_call_site.get("captureBackdrop"),
            "capture_backdrop validated code summary",
        )
        if (
            len(producer_geometry_call_sites) != 1
            or producer_geometry_call_site.get("schemaVersion") != 5
            or capture_backdrop_code.get("symbolPrefixSHA256")
            != CAPTURE_BACKDROP_EXPECTED_SYMBOL_PREFIX_SHA256
            or capture_backdrop_code.get("operandFramePrologueExact") is not True
            or capture_backdrop_operand_count != expected_count
            or capture_backdrop_position_mismatches != 0
            or len(capture_backdrop_symbol_addresses) != 1
            or capture_backdrop_code.get("symbolAddress")
            != next(iter(capture_backdrop_symbol_addresses))
        ):
            raise ValueError(
                "capture_backdrop operand replay gate failed: "
                f"captures={capture_backdrop_operand_count}/{expected_count}, "
                "positions="
                f"{capture_backdrop_position_components - capture_backdrop_position_mismatches}/"
                f"{capture_backdrop_position_components}, "
                f"symbolCount={len(capture_backdrop_symbol_addresses)}"
            )
    return {
        "dynamicAllocationSurvivingPathThresholdResultSchemaVersion": result_schema,
        "classification": classification,
        **(
            {"captureEvidenceSchemaVersion": evidence_schema}
            if evidence_schema >= 3
            else {}
        ),
        "timeline": str(path),
        "timelineSHA256": holdout.sha256_file(path),
        "geometry": report.get("geometry"),
        "sourceSampleIndices": list(source_sample_indices),
        "aggregate": {
            "recordCount": len(validated_records),
            "sourceStateCount": source_count,
            "sourceInterventionCounts": expected_counts,
            "phaseRecordCounts": {
                name: phase_counts[name] for name in sorted(phase_counts)
            },
            "primaryProducerSourceQ": {
                "componentCount": q_components,
                "mismatchedComponents": q_mismatches,
                "exact": q_mismatches == 0,
            },
            "allocationInvariants": {
                "componentCount": invariant_components,
                "mismatchedComponents": invariant_mismatches,
                "exact": invariant_mismatches == 0,
            },
            "producerVertexCountStates": {
                str(count): topology_counts[count] for count in sorted(topology_counts)
            },
            "selectedRenderAttemptCounts": {
                str(index): selected_attempt_counts[index]
                for index in sorted(selected_attempt_counts)
            },
            "retainedBufferSnapshotCount": retained_buffer_count,
            "producerGeometryCallSite": producer_geometry_call_site,
            **(
                {
                    "captureBackdropOperandReplay": {
                        "captureCount": capture_backdrop_operand_count,
                        "expectedCaptureCount": expected_count,
                        "primaryPositionComponentCount": (
                            capture_backdrop_position_components
                        ),
                        "primaryPositionMismatchedComponents": (
                            capture_backdrop_position_mismatches
                        ),
                        "primaryPositionExact": (
                            capture_backdrop_position_mismatches == 0
                        ),
                        "singleMappedSymbolAddress": (
                            len(capture_backdrop_symbol_addresses) == 1
                        ),
                        "symbolPrefixSHA256": (
                            CAPTURE_BACKDROP_EXPECTED_SYMBOL_PREFIX_SHA256
                        ),
                        "affineBranchEveryCapture": True,
                        "allowNumericTolerance": False,
                    }
                }
                if evidence_schema == 5
                else {}
            ),
            "liveBaselinePlusTargetPositionExact": True,
            "liveLayerStateStableAcrossRender": True,
            "liveFilterInputsBeforeAndAfterExact": True,
            "baseDecodedPolicyExact": True,
            "baseRawDrawHashes": {
                "vertexExactCount": base_vertex_hash_matches,
                "mvpExactCount": base_mvp_hash_matches,
                "indexExactCount": base_index_hash_matches,
            },
            "originalProducerInputEveryState": True,
            "rawStageDumpsAbsent": True,
        },
        "records": validated_records,
        "conclusion": {
            "captureIntegrityPassed": True,
            "causalCalibrationOnly": True,
            {
                2: "deepestSDFPositionThresholdRequiresPostOpeningAnalysis",
                3: "fineThresholdAndCrossAxisScanRequiresPostOpeningAnalysis",
                4: "sample31RepeatScanRequiresPostOpeningAnalysis",
                5: "captureBackdropOperandsRequirePostOpeningPolicyMapping",
            }[evidence_schema]: True,
            "requiresUnseenGeometryTransfer": True,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.report)
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
        print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
