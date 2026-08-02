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
    "preregistered-live-capture-backdrop-operand-and-primary-vertex-replay"
)
CAPTURE_BACKDROP_REGION_CLASSIFICATION = (
    "preregistered-live-capture-backdrop-selected-region-and-primary-vertex-replay"
)
CAPTURE_BACKDROP_OWNER_REGION_CLASSIFICATION = (
    "preregistered-live-capture-backdrop-owner-region-construction-and-callback-"
    "provenance-replay"
)
CAPTURE_BACKDROP_OWNER_RECORD_CLASSIFICATION = (
    "preregistered-live-capture-backdrop-owner-record-vector-and-source-key-replay"
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
CAPTURE_BACKDROP_REGION_ITERATE_CALL_OFFSET = 0x2334
CAPTURE_BACKDROP_REGION_ITERATE_SYMBOL = "_ZN2CA13ShapeIterator7iterateERNS_6BoundsE"
CAPTURE_BACKDROP_EXPECTED_REGION_ITERATE_PREFIX_SHA256 = (
    "faf2c7f536d2c76dbac26b3d7af7aeb7a498b1c50a20ecb152d8d896c616bcc6"
)
CAPTURE_BACKDROP_FRAME_POINTER_TO_STACK_POINTER = 0xA50
CAPTURE_BACKDROP_FIRST_REGISTER = 19
CAPTURE_BACKDROP_REGISTER_COUNT = 11
CAPTURE_BACKDROP_V1_REQUIRED_READ_MASK = 0xFF
CAPTURE_BACKDROP_V2_REQUIRED_READ_MASK = 0x1FFFF
CAPTURE_BACKDROP_REQUIRED_READ_MASK = 0xFFFFF
CAPTURE_BACKDROP_OWNER_RECORD_REQUIRED_READ_MASK = 0x7FFFFF
CAPTURE_BACKDROP_MEMORY_READ_MAXIMUM_ATTEMPT_COUNT = 3
CAPTURE_BACKDROP_CALLBACK_MAXIMUM_FRAME_COUNT = 32
CAPTURE_BACKDROP_CALLBACK_MAXIMUM_ATTEMPT_COUNT = 8
CAPTURE_BACKDROP_OPERAND_FRAGMENTS = frozenset({"A2Xghfc", "TimgA2Xhfc_Isrc"})
CAPTURE_BACKDROP_OWNER_REGION_METHOD = (
    "live-baseline-sample31-unit-scan-with-dual-owner-region-prefixes-bounded-"
    "callback-provenance-and-late-same-process-repeat-controls"
)
CAPTURE_BACKDROP_OWNER_RECORD_METHOD = (
    "live-baseline-sample31-unit-scan-with-dual-owner-region-prefixes-bounded-"
    "owner-record-vector-source-key-callback-provenance-and-late-same-process-"
    "repeat-controls"
)
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
    "rendererPointer": 0x228,
    "rect": 0x280,
    "regionHandle": 0x2A0,
    "affine": 0x390,
    "regionIterator": 0x3C0,
}
CAPTURE_BACKDROP_V1_STACK_OFFSETS = {
    key: CAPTURE_BACKDROP_STACK_OFFSETS[key]
    for key in (
        "originPointer",
        "shapePointer",
        "transformPointer",
        "contextPointer",
        "rect",
        "affine",
    )
}
CAPTURE_BACKDROP_CONTEXT_SCALE_OFFSET = 0x18
CAPTURE_BACKDROP_REGION_OWNER_OFFSETS = {"region248": 0x248, "region270": 0x270}
CAPTURE_BACKDROP_OWNER_REGION_WINDOW_OFFSET = 0x200
CAPTURE_BACKDROP_OWNER_RECORD_OFFSETS = {
    "begin": 0x50,
    "end": 0x58,
    "recordByteCount": 0xD0,
}
CAPTURE_BACKDROP_SOURCE_STATE_WINDOW_OFFSET = 0x18
CAPTURE_BACKDROP_RENDERER_OFFSETS = {"scale": 0x30, "regionControl": 0xD0}
CAPTURE_BACKDROP_REGION_PREFIX_BYTE_COUNT = 256
CAPTURE_BACKDROP_OWNER_REGION_PREFIX_BYTE_COUNT = 4096
CAPTURE_BACKDROP_OWNER_OBJECT_PREFIX_BYTE_COUNT = 768
CAPTURE_BACKDROP_OWNER_RECORD_BYTE_COUNT = 0xD0
CAPTURE_BACKDROP_OWNER_RECORD_MAXIMUM_COUNT = 64
CAPTURE_BACKDROP_OWNER_RECORD_EXPECTED_COUNT = 1
CAPTURE_BACKDROP_OWNER_RECORD_EXPECTED_MATCH_COUNT = 1
CAPTURE_BACKDROP_OWNER_RECORD_EXPECTED_SELECTED_INDEX = 0
CAPTURE_BACKDROP_OWNER_RECORD_VECTOR_BYTE_COUNT = (
    CAPTURE_BACKDROP_OWNER_RECORD_BYTE_COUNT
    * CAPTURE_BACKDROP_OWNER_RECORD_MAXIMUM_COUNT
)
CAPTURE_BACKDROP_SOURCE_STATE_WINDOW_BYTE_COUNT = 40
CAPTURE_BACKDROP_OPERAND_LAYOUTS = {
    "registers": (
        "little-endian x19-through-x29 words",
        8 * CAPTURE_BACKDROP_REGISTER_COUNT,
    ),
    "rect": ("four little-endian signed 32-bit rectangle words", 16),
    "affine": ("six little-endian binary64 affine words", 48),
    "origin": ("two little-endian signed 32-bit origin words", 8),
    "originBounds": (
        "four little-endian signed 32-bit origin-bound words",
        16,
    ),
    "scale": ("one little-endian binary32 scale word", 4),
    "rendererScale": (
        "one little-endian binary64 renderer scale word",
        8,
    ),
    "rendererRegionControl": (
        "bounded renderer region-control bytes at offset d0",
        16,
    ),
    "regionIterator": ("three little-endian region iterator words", 24),
    "ownerRegionWindow": (
        "bounded owner bytes at offsets 0x200 through 0x2ff",
        256,
    ),
    "ownerObjectPrefix": (
        "bounded owner object prefix bytes",
        CAPTURE_BACKDROP_OWNER_OBJECT_PREFIX_BYTE_COUNT,
    ),
    "sourceStateWindow": (
        "five little-endian source-state key words",
        CAPTURE_BACKDROP_SOURCE_STATE_WINDOW_BYTE_COUNT,
    ),
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


def capture_backdrop_operand_bytes(operands: Mapping[str, Any], field: str) -> bytes:
    class_name, expected_length = CAPTURE_BACKDROP_OPERAND_LAYOUTS[field]
    record = holdout.mapping(operands.get(field), f"capture_backdrop {field} operands")
    payload = hexadecimal_bytes(record, f"capture_backdrop {field} operands")
    if (
        record.get("class") != class_name
        or record.get("lengthBytes") != expected_length
        or len(payload) != expected_length
        or record.get("sha256") != hashlib.sha256(payload).hexdigest()
    ):
        raise ValueError(f"capture_backdrop {field} operand metadata differs")
    return payload


def capture_backdrop_owner_record_vector_bytes(
    operands: Mapping[str, Any],
) -> bytes:
    record = holdout.mapping(
        operands.get("ownerRecordVector"),
        "capture_backdrop ownerRecordVector operands",
    )
    payload = hexadecimal_bytes(record, "capture_backdrop ownerRecordVector operands")
    length = record.get("lengthBytes")
    if (
        record.get("class") != "bounded owner 0xd0-byte record vector"
        or not isinstance(length, int)
        or length != len(payload)
        or not CAPTURE_BACKDROP_OWNER_RECORD_BYTE_COUNT
        <= length
        <= CAPTURE_BACKDROP_OWNER_RECORD_VECTOR_BYTE_COUNT
        or length % CAPTURE_BACKDROP_OWNER_RECORD_BYTE_COUNT != 0
        or record.get("sha256") != hashlib.sha256(payload).hexdigest()
    ):
        raise ValueError("capture_backdrop ownerRecordVector operand metadata differs")
    return payload


def capture_backdrop_region_prefix_bytes(
    operands: Mapping[str, Any],
    *,
    field: str = "regionPrefix",
    class_name: str = "bounded selected-region prefix bytes",
    region_handle: int,
    prefix_byte_count: int = CAPTURE_BACKDROP_REGION_PREFIX_BYTE_COUNT,
    minimum_prefix_byte_count: int | None = None,
) -> bytes:
    record = holdout.mapping(operands.get(field), f"capture_backdrop {field} operands")
    payload = hexadecimal_bytes(record, f"capture_backdrop {field} operands")
    pointer_backed = region_handle != 0 and region_handle & 1 == 0
    minimum_length = (
        prefix_byte_count
        if minimum_prefix_byte_count is None
        else minimum_prefix_byte_count
    )
    length = record.get("lengthBytes")
    if (
        record.get("class") != class_name
        or not isinstance(length, int)
        or len(payload) != length
        or (
            pointer_backed
            and (
                not minimum_length <= length <= prefix_byte_count
                or length % CAPTURE_BACKDROP_REGION_PREFIX_BYTE_COUNT != 0
            )
        )
        or (not pointer_backed and length != 0)
        or record.get("sha256") != hashlib.sha256(payload).hexdigest()
    ):
        raise ValueError(f"capture_backdrop {field} operand metadata differs")
    return payload


def capture_backdrop_region_word(region_prefix: bytes, offset: int) -> int:
    end = offset + 4
    if offset < 0 or end > len(region_prefix):
        raise ValueError("capture_backdrop selected-region offset is out of bounds")
    return int.from_bytes(region_prefix[offset:end], "little", signed=True)


def capture_backdrop_int32(value: int) -> int:
    value &= 0xFFFF_FFFF
    return value - 0x1_0000_0000 if value & 0x8000_0000 else value


def capture_backdrop_packed_region_rect(region_handle: int) -> list[int]:
    lower_word = region_handle & 0xFFFF_FFFF
    x = (region_handle >> 48) & 0xFFFF
    y = (region_handle >> 32) & 0xFFFF
    if x & 0x8000:
        x -= 0x1_0000
    if y & 0x8000:
        y -= 0x1_0000
    return [x, y, lower_word >> 17, (lower_word >> 2) & 0x7FFF]


def capture_backdrop_pointer_region_iterate(
    region_handle: int,
    region_prefix: bytes,
    iterator: Sequence[int],
) -> tuple[list[int], list[int]] | None:
    offset = int(iterator[1])
    interval_index = int(iterator[2])
    if offset == 0:
        row = 12
        y = capture_backdrop_region_word(region_prefix, row)
        if y != 0x7FFF_FFFF and capture_backdrop_region_word(region_prefix, 16) == 2:
            while True:
                row += 8
                y = capture_backdrop_region_word(region_prefix, row)
                if (
                    y == 0x7FFF_FFFF
                    or capture_backdrop_region_word(region_prefix, row + 4) != 2
                ):
                    break
        coordinate = row + 8
        next_interval_index = 1
    else:
        row = offset * 4
        y = capture_backdrop_region_word(region_prefix, row)
        coordinate = row + interval_index * 8 + 8
        next_interval_index = interval_index + 1
    if y == 0x7FFF_FFFF:
        return None

    index = capture_backdrop_region_word(region_prefix, row + 4)
    x = capture_backdrop_region_word(region_prefix, coordinate)
    right = capture_backdrop_region_word(region_prefix, coordinate + 4)
    bottom = capture_backdrop_region_word(region_prefix, row + index * 4)
    next_offset = row // 4
    if next_interval_index == (index - 2) >> 1:
        cursor = row + index * 4
        while (
            capture_backdrop_region_word(region_prefix, cursor) != 0x7FFF_FFFF
            and capture_backdrop_region_word(region_prefix, cursor + 4) == 2
        ):
            cursor += 8
        next_offset = cursor // 4
        next_interval_index = 0
    return (
        [
            x,
            y,
            capture_backdrop_int32(right - x),
            capture_backdrop_int32(bottom - y),
        ],
        [region_handle, next_offset, next_interval_index],
    )


def capture_backdrop_region_rect_for_iterator(
    region_handle: int,
    region_prefix: bytes,
    post_iterator: Sequence[int],
) -> list[int]:
    if len(post_iterator) != 3 or int(post_iterator[0]) != region_handle:
        raise ValueError("capture_backdrop selected-region iterator differs")
    expected_post = [int(value) for value in post_iterator]
    if region_handle in {0, 1}:
        raise ValueError("capture_backdrop selected region is empty")
    if region_handle & 1:
        rect = capture_backdrop_packed_region_rect(region_handle)
        if expected_post != [region_handle, 1, 0]:
            raise ValueError("capture_backdrop selected-region iterator differs")
    else:
        iterator = [region_handle, 0, 0]
        maximum_iterations = CAPTURE_BACKDROP_REGION_PREFIX_BYTE_COUNT // 4
        for _ in range(maximum_iterations):
            result = capture_backdrop_pointer_region_iterate(
                region_handle, region_prefix, iterator
            )
            if result is None:
                break
            rect, iterator = result
            if iterator == expected_post:
                break
        else:
            raise ValueError("capture_backdrop selected-region iterator is unbounded")
        if result is None or iterator != expected_post:
            raise ValueError("capture_backdrop selected-region iterator differs")
    if rect[2] <= 0 or rect[3] <= 0:
        raise ValueError("capture_backdrop selected-region rectangle is empty")
    return rect


def capture_backdrop_first_region_rect(
    region_handle: int, region_prefix: bytes
) -> list[int]:
    if region_handle in {0, 1}:
        raise ValueError("capture_backdrop selected region is empty")
    if region_handle & 1:
        rect = capture_backdrop_packed_region_rect(region_handle)
    else:
        result = capture_backdrop_pointer_region_iterate(
            region_handle, region_prefix, [region_handle, 0, 0]
        )
        if result is None:
            raise ValueError("capture_backdrop selected region is empty")
        rect, _ = result
    if rect[2] <= 0 or rect[3] <= 0:
        raise ValueError("capture_backdrop selected-region rectangle is empty")
    return rect


def capture_backdrop_consumed_region_rect(
    region_rect: Sequence[int],
    origin_bounds: Sequence[int],
    *,
    shape_pointer: int,
    transform_pointer: int,
) -> list[int]:
    if len(region_rect) != 4 or len(origin_bounds) != 4:
        raise ValueError("capture_backdrop selected-region bounds differ")
    if transform_pointer != 0 or shape_pointer == 0:
        result = [int(value) for value in region_rect]
    else:
        region_x, region_y, region_width, region_height = region_rect
        bound_x, bound_y, bound_width, bound_height = origin_bounds
        lower_x = max(region_x, bound_x)
        lower_y = max(region_y, bound_y)
        upper_x = min(
            capture_backdrop_int32(region_x + region_width),
            capture_backdrop_int32(bound_x + bound_width),
        )
        upper_y = min(
            capture_backdrop_int32(region_y + region_height),
            capture_backdrop_int32(bound_y + bound_height),
        )
        result = [
            lower_x,
            lower_y,
            capture_backdrop_int32(upper_x - lower_x),
            capture_backdrop_int32(upper_y - lower_y),
        ]
    if result[2] <= 0 or result[3] <= 0:
        raise ValueError("capture_backdrop selected-region intersection is empty")
    return result


def float32_fma(multiplier: float, multiplicand: float, addend: float) -> float:
    return holdout.float32(math.fma(multiplier, multiplicand, addend))


def capture_backdrop_rounded_bounds(
    *,
    rect: Sequence[int],
    scale: float,
) -> tuple[list[float], list[float], list[float]]:
    if len(rect) != 4 or not math.isfinite(scale) or scale <= 0:
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
    return [float_x, float_y, float_right, float_bottom], rounded, snapped


def capture_backdrop_primary_position_bits(
    *,
    rect: Sequence[int],
    scale: float,
) -> list[int]:
    _, rounded, _ = capture_backdrop_rounded_bounds(rect=rect, scale=scale)
    x0, y0, x1, y1 = rounded
    return [holdout.float32_bits(value) for value in (x0, y0, x1, y0, x1, y1, x0, y1)]


def capture_backdrop_primary_source_bits(
    *,
    rect: Sequence[int],
    affine: Sequence[float],
    origin: Sequence[int],
    scale: float,
    transform_branch: bool,
) -> list[int]:
    if (
        len(affine) != 6
        or len(origin) != 2
        or not all(math.isfinite(value) for value in affine)
    ):
        raise ValueError("capture_backdrop source operands differ")

    unscaled, rounded, snapped = capture_backdrop_rounded_bounds(rect=rect, scale=scale)
    if not transform_branch:
        x, y, width, height = rect
        bases = [
            holdout.float32(float(x - origin[0])),
            holdout.float32(float(y - origin[1])),
            holdout.float32(float(x - origin[0] + width)),
            holdout.float32(float(y - origin[1] + height)),
        ]
        scale = holdout.float32(scale)
        inverse_scale = holdout.float32(1.0 / scale)
        residuals = [
            float32_fma(-scale, value, integral)
            for value, integral in zip(unscaled, rounded, strict=True)
        ]
        x0, y0, x1, y1 = [
            float32_fma(residual, inverse_scale, base)
            for residual, base in zip(residuals, bases, strict=True)
        ]
        return [
            holdout.float32_bits(value) for value in (x0, y0, x1, y0, x1, y1, x0, y1)
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
        source_x = holdout.float32(holdout.float32(transformed_x) - origin_x)
        source_y = holdout.float32(holdout.float32(transformed_y) - origin_y)
        result.extend((holdout.float32_bits(source_x), holdout.float32_bits(source_y)))
    return result


def validate_capture_backdrop_operands(
    untyped_operands: Any,
) -> dict[str, Any]:
    operands = holdout.mapping(untyped_operands, "capture_backdrop operand evidence")
    operand_schema = operands.get("schemaVersion")
    if operand_schema not in {1, 2, 3, 4}:
        raise ValueError("capture_backdrop operand schema differs")
    expected_read_mask = {
        1: CAPTURE_BACKDROP_V1_REQUIRED_READ_MASK,
        2: CAPTURE_BACKDROP_V2_REQUIRED_READ_MASK,
        3: CAPTURE_BACKDROP_REQUIRED_READ_MASK,
        4: CAPTURE_BACKDROP_OWNER_RECORD_REQUIRED_READ_MASK,
    }[operand_schema]
    expected_stack_offsets = (
        CAPTURE_BACKDROP_V1_STACK_OFFSETS
        if operand_schema == 1
        else CAPTURE_BACKDROP_STACK_OFFSETS
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
        operands.get("executed") is not True
        or operands.get("class") != "bounded live capture_backdrop unwind operands"
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
        or operands.get("stackOffsets") != expected_stack_offsets
        or operands.get("contextScaleOffset") != CAPTURE_BACKDROP_CONTEXT_SCALE_OFFSET
        or (
            operand_schema in {3, 4}
            and (
                operands.get("completeRead") is not True
                or operands.get("memoryReadMaximumAttemptCount")
                != CAPTURE_BACKDROP_MEMORY_READ_MAXIMUM_ATTEMPT_COUNT
            )
        )
        or read_mask != expected_read_mask
        or required_read_mask != expected_read_mask
        or registers[29 - CAPTURE_BACKDROP_FIRST_REGISTER] != frame_pointer
        or registers[26 - CAPTURE_BACKDROP_FIRST_REGISTER] != origin_pointer
        or registers[27 - CAPTURE_BACKDROP_FIRST_REGISTER] != context_pointer
        or origin_pointer == 0
        or shape_pointer == 0
        or context_pointer == 0
    ):
        raise ValueError("capture_backdrop operand metadata differs")
    region_summary: dict[str, Any] = {}
    if operand_schema in {2, 3, 4}:
        renderer_pointer = hexadecimal_address(
            operands.get("rendererPointer"),
            "capture_backdrop renderer pointer",
        )
        region_handle = hexadecimal_address(
            operands.get("regionHandle"), "capture_backdrop selected-region handle"
        )
        owner_region_248 = hexadecimal_address(
            operands.get("ownerRegion248"), "capture_backdrop owner region 248"
        )
        owner_region_270 = hexadecimal_address(
            operands.get("ownerRegion270"), "capture_backdrop owner region 270"
        )
        renderer_scale_payload = capture_backdrop_operand_bytes(
            operands, "rendererScale"
        )
        renderer_region_control_payload = capture_backdrop_operand_bytes(
            operands, "rendererRegionControl"
        )
        origin_bounds_payload = capture_backdrop_operand_bytes(operands, "originBounds")
        region_iterator_payload = capture_backdrop_operand_bytes(
            operands, "regionIterator"
        )
        region_prefix = capture_backdrop_region_prefix_bytes(
            operands, region_handle=region_handle
        )
        owner_region_248_prefix = (
            capture_backdrop_region_prefix_bytes(
                operands,
                field="ownerRegion248Prefix",
                class_name="bounded owner +0x248 region prefix bytes",
                region_handle=owner_region_248,
                prefix_byte_count=CAPTURE_BACKDROP_OWNER_REGION_PREFIX_BYTE_COUNT,
                minimum_prefix_byte_count=CAPTURE_BACKDROP_REGION_PREFIX_BYTE_COUNT,
            )
            if operand_schema in {3, 4}
            else b""
        )
        owner_region_270_prefix = (
            capture_backdrop_region_prefix_bytes(
                operands,
                field="ownerRegion270Prefix",
                class_name="bounded owner +0x270 region prefix bytes",
                region_handle=owner_region_270,
                prefix_byte_count=CAPTURE_BACKDROP_OWNER_REGION_PREFIX_BYTE_COUNT,
                minimum_prefix_byte_count=CAPTURE_BACKDROP_REGION_PREFIX_BYTE_COUNT,
            )
            if operand_schema in {3, 4}
            else b""
        )
        owner_region_window = (
            capture_backdrop_operand_bytes(operands, "ownerRegionWindow")
            if operand_schema in {3, 4}
            else b""
        )
        owner_record_summary: dict[str, Any] = {}
        if operand_schema == 4:
            owner_object_prefix = capture_backdrop_operand_bytes(
                operands, "ownerObjectPrefix"
            )
            owner_record_vector = capture_backdrop_owner_record_vector_bytes(operands)
            source_state_window = capture_backdrop_operand_bytes(
                operands, "sourceStateWindow"
            )
            record_begin, record_end = struct.unpack_from(
                "<2Q",
                owner_object_prefix,
                CAPTURE_BACKDROP_OWNER_RECORD_OFFSETS["begin"],
            )
            record_count = (
                len(owner_record_vector) // CAPTURE_BACKDROP_OWNER_RECORD_BYTE_COUNT
            )
            source_record_match_indices = [
                index
                for index in range(record_count)
                if owner_record_vector[
                    index * CAPTURE_BACKDROP_OWNER_RECORD_BYTE_COUNT : index
                    * CAPTURE_BACKDROP_OWNER_RECORD_BYTE_COUNT
                    + CAPTURE_BACKDROP_SOURCE_STATE_WINDOW_BYTE_COUNT
                ]
                == source_state_window
            ]
            selected_record_index = (
                min(source_record_match_indices) if source_record_match_indices else -1
            )
            cached_record_index = int.from_bytes(
                owner_object_prefix[0x220:0x228], "little"
            )
            if (
                operands.get("ownerRecordOffsets")
                != CAPTURE_BACKDROP_OWNER_RECORD_OFFSETS
                or operands.get("sourceStateWindowOffset")
                != CAPTURE_BACKDROP_SOURCE_STATE_WINDOW_OFFSET
                or owner_object_prefix[
                    CAPTURE_BACKDROP_OWNER_REGION_WINDOW_OFFSET : CAPTURE_BACKDROP_OWNER_REGION_WINDOW_OFFSET
                    + CAPTURE_BACKDROP_REGION_PREFIX_BYTE_COUNT
                ]
                != owner_region_window
                or registers[19 - CAPTURE_BACKDROP_FIRST_REGISTER] == 0
                or record_begin == 0
                or record_end <= record_begin
                or record_end - record_begin != len(owner_record_vector)
                or record_count != CAPTURE_BACKDROP_OWNER_RECORD_EXPECTED_COUNT
                or len(source_record_match_indices)
                != CAPTURE_BACKDROP_OWNER_RECORD_EXPECTED_MATCH_COUNT
                or selected_record_index
                != CAPTURE_BACKDROP_OWNER_RECORD_EXPECTED_SELECTED_INDEX
                or cached_record_index != selected_record_index
            ):
                raise ValueError("capture_backdrop owner record-vector replay differs")
            selected_record_offset = (
                selected_record_index * CAPTURE_BACKDROP_OWNER_RECORD_BYTE_COUNT
            )
            owner_record_summary = {
                "ownerObjectPrefixSHA256": hashlib.sha256(
                    owner_object_prefix
                ).hexdigest(),
                "ownerObjectPrefixByteCount": len(owner_object_prefix),
                "ownerRecordVectorSHA256": hashlib.sha256(
                    owner_record_vector
                ).hexdigest(),
                "ownerRecordVectorByteCount": len(owner_record_vector),
                "ownerRecordCount": record_count,
                "sourceStateWindowSHA256": hashlib.sha256(
                    source_state_window
                ).hexdigest(),
                "sourceStateWindowByteCount": len(source_state_window),
                "sourceRecordMatchIndices": source_record_match_indices,
                "selectedOwnerRecordIndex": selected_record_index,
                "selectedRecordInitialBoundsHex": owner_record_vector[
                    selected_record_offset + 0x30 : selected_record_offset + 0x50
                ].hex(),
                "ownerRegionWindowEmbeddedInPrefix": True,
            }
        region_iterator = list(struct.unpack("<3Q", region_iterator_payload))
        renderer_scale = struct.unpack("<d", renderer_scale_payload)[0]
        origin_bounds = list(struct.unpack("<4i", origin_bounds_payload))
        selected_region_rect = capture_backdrop_region_rect_for_iterator(
            region_handle, region_prefix, region_iterator
        )
        consumed_region_rect = capture_backdrop_consumed_region_rect(
            selected_region_rect,
            origin_bounds,
            shape_pointer=shape_pointer,
            transform_pointer=transform_pointer,
        )
        owner_region_248_rect = (
            capture_backdrop_first_region_rect(
                owner_region_248, owner_region_248_prefix
            )
            if operand_schema in {3, 4}
            else None
        )
        owner_region_270_rect = (
            capture_backdrop_first_region_rect(
                owner_region_270, owner_region_270_prefix
            )
            if operand_schema in {3, 4}
            else None
        )
        if (
            operands.get("regionOwnerOffsets") != CAPTURE_BACKDROP_REGION_OWNER_OFFSETS
            or (
                operand_schema in {3, 4}
                and (
                    operands.get("ownerRegionWindowOffset")
                    != CAPTURE_BACKDROP_OWNER_REGION_WINDOW_OFFSET
                    or int.from_bytes(owner_region_window[0x48:0x50], "little")
                    != owner_region_248
                    or int.from_bytes(owner_region_window[0x70:0x78], "little")
                    != owner_region_270
                )
            )
            or operands.get("rendererOffsets") != CAPTURE_BACKDROP_RENDERER_OFFSETS
            or registers[20 - CAPTURE_BACKDROP_FIRST_REGISTER] == 0
            or renderer_pointer == 0
            or not math.isfinite(renderer_scale)
            or renderer_scale <= 0
            or len(renderer_region_control_payload) != 16
            or origin_bounds[:2] != origin
            or consumed_region_rect != rect
            or (operand_schema in {3, 4} and region_handle != owner_region_248)
        ):
            raise ValueError("capture_backdrop selected-region replay differs")
        region_summary = {
            "rendererPointer": renderer_pointer,
            "rendererScale": renderer_scale,
            "rendererScaleBits": struct.unpack("<Q", renderer_scale_payload)[0],
            "rendererRegionControlHex": renderer_region_control_payload.hex(),
            "originBounds": origin_bounds,
            "regionHandle": region_handle,
            "regionHandleClass": "packed" if region_handle & 1 else "pointer",
            "ownerRegion248": owner_region_248,
            "ownerRegion270": owner_region_270,
            **(
                {
                    "ownerRegion248Class": (
                        "packed" if owner_region_248 & 1 else "pointer"
                    ),
                    "ownerRegion270Class": (
                        "packed" if owner_region_270 & 1 else "pointer"
                    ),
                    "ownerRegion248PrefixSHA256": hashlib.sha256(
                        owner_region_248_prefix
                    ).hexdigest(),
                    "ownerRegion248PrefixByteCount": len(owner_region_248_prefix),
                    "ownerRegion270PrefixSHA256": hashlib.sha256(
                        owner_region_270_prefix
                    ).hexdigest(),
                    "ownerRegion270PrefixByteCount": len(owner_region_270_prefix),
                    "ownerRegionWindowSHA256": hashlib.sha256(
                        owner_region_window
                    ).hexdigest(),
                    "ownerRegionWindowByteCount": len(owner_region_window),
                    "ownerRegion248FirstRect": owner_region_248_rect,
                    "ownerRegion270FirstRect": owner_region_270_rect,
                    "selectedEqualsOwner248": region_handle == owner_region_248,
                    "selectedEqualsOwner270": region_handle == owner_region_270,
                }
                if operand_schema in {3, 4}
                else {}
            ),
            "regionIterator": region_iterator,
            "regionPrefixSHA256": hashlib.sha256(region_prefix).hexdigest(),
            "selectedRegionRect": selected_region_rect,
            "consumedRegionRect": consumed_region_rect,
            "selectedRegionWasIntersected": consumed_region_rect
            != selected_region_rect,
            "consumedRegionRectExact": True,
            **owner_record_summary,
        }
    predicted_position_bits = capture_backdrop_primary_position_bits(
        rect=rect,
        scale=scale,
    )
    predicted_source_bits = capture_backdrop_primary_source_bits(
        rect=rect,
        affine=affine,
        origin=origin,
        scale=scale,
        transform_branch=transform_pointer != 0,
    )
    return {
        "schemaVersion": operand_schema,
        "symbolAddress": symbol_address,
        "instructionPointer": instruction_pointer,
        "canonicalFrameAddress": canonical_frame_address,
        "framePointer": frame_pointer,
        "stackPointer": stack_pointer,
        "shapePointerNonzero": shape_pointer != 0,
        "transformPointerNonzero": transform_pointer != 0,
        "transformBranch": "affine" if transform_pointer != 0 else "identity",
        "rect": rect,
        "affine": affine,
        "origin": origin,
        "scale": scale,
        "scaleBits": struct.unpack("<I", scale_payload)[0],
        "predictedPrimaryPositionBits": predicted_position_bits,
        "predictedPrimarySourceBits": predicted_source_bits,
        **region_summary,
    }


def validate_capture_backdrop_operand_attempt(
    untyped_attempt: Any,
) -> dict[str, Any]:
    attempt = holdout.mapping(untyped_attempt, "capture_backdrop callback attempt")
    frames = [
        holdout.mapping(frame, "capture_backdrop callback frame")
        for frame in fixed.sequence(
            attempt.get("frames"), "capture_backdrop callback frames"
        )
    ]
    offsets = list(
        fixed.sequence(
            attempt.get("captureBackdropSymbolOffsets"),
            "capture_backdrop callback symbol offsets",
        )
    )
    observed_offsets: list[str] = []
    previous_index = -1
    for frame in frames:
        index = frame.get("index")
        if (
            not isinstance(index, int)
            or not previous_index
            < index
            < CAPTURE_BACKDROP_CALLBACK_MAXIMUM_FRAME_COUNT
            or not set(frame).issubset({"index", "image", "symbol", "symbolOffset"})
            or ("image" in frame and not isinstance(frame["image"], str))
            or ("symbol" in frame and not isinstance(frame["symbol"], str))
            or ("symbolOffset" in frame and not isinstance(frame["symbolOffset"], str))
        ):
            raise ValueError("capture_backdrop callback frame differs")
        previous_index = index
        if "symbolOffset" in frame:
            hexadecimal_address(
                frame["symbolOffset"], "capture_backdrop callback symbol offset"
            )
        if frame.get("symbol") == CAPTURE_BACKDROP_SYMBOL:
            symbol_offset = frame.get("symbolOffset")
            if not isinstance(symbol_offset, str):
                raise ValueError("capture_backdrop callback symbol frame differs")
            observed_offsets.append(symbol_offset)
    if (
        attempt.get("schemaVersion") != 1
        or attempt.get("executed") is not True
        or attempt.get("class") != "bounded eligible producer callback stack provenance"
        or attempt.get("maximumFrameCount")
        != CAPTURE_BACKDROP_CALLBACK_MAXIMUM_FRAME_COUNT
        or attempt.get("frameCount") != len(frames)
        or len(frames) > CAPTURE_BACKDROP_CALLBACK_MAXIMUM_FRAME_COUNT
        or offsets != observed_offsets
        or not isinstance(attempt.get("attemptIndex"), int)
        or not 0
        <= attempt["attemptIndex"]
        < CAPTURE_BACKDROP_CALLBACK_MAXIMUM_ATTEMPT_COUNT
        or attempt.get("fragmentFunction") not in CAPTURE_BACKDROP_OPERAND_FRAGMENTS
    ):
        raise ValueError("capture_backdrop callback attempt differs")

    partial_summary: dict[str, Any] = {}
    if "partialOperands" in attempt:
        partial = holdout.mapping(
            attempt.get("partialOperands"),
            "capture_backdrop partial operands",
        )
        symbol_address = hexadecimal_address(
            partial.get("symbolAddress"),
            "capture_backdrop partial symbol address",
        )
        instruction_pointer = hexadecimal_address(
            partial.get("instructionPointer"),
            "capture_backdrop partial instruction pointer",
        )
        read_mask = hexadecimal_address(
            partial.get("readMask"), "capture_backdrop partial read mask"
        )
        required_read_mask = hexadecimal_address(
            partial.get("requiredReadMask"),
            "capture_backdrop partial required read mask",
        )
        partial_schema = partial.get("schemaVersion")
        expected_partial_read_mask = {
            3: CAPTURE_BACKDROP_REQUIRED_READ_MASK,
            4: CAPTURE_BACKDROP_OWNER_RECORD_REQUIRED_READ_MASK,
        }.get(partial_schema)
        if (
            expected_partial_read_mask is None
            or partial.get("executed") is not True
            or partial.get("completeRead") is not False
            or partial.get("class") != "bounded live capture_backdrop unwind operands"
            or partial.get("symbol") != CAPTURE_BACKDROP_SYMBOL
            or partial.get("returnSymbolOffset")
            != CAPTURE_BACKDROP_VERTEX_BINDING_RETURN_OFFSET
            or instruction_pointer
            != symbol_address + CAPTURE_BACKDROP_VERTEX_BINDING_RETURN_OFFSET
            or partial.get("memoryReadMaximumAttemptCount")
            != CAPTURE_BACKDROP_MEMORY_READ_MAXIMUM_ATTEMPT_COUNT
            or required_read_mask != expected_partial_read_mask
            or read_mask == required_read_mask
            or read_mask & ~required_read_mask
        ):
            raise ValueError("capture_backdrop partial operand attempt differs")
        partial_summary = {
            "partialReadMask": f"0x{read_mask:08x}",
            "partialRequiredReadMask": f"0x{required_read_mask:08x}",
        }
    return {
        "attemptIndex": attempt["attemptIndex"],
        "fragmentFunction": attempt["fragmentFunction"],
        "frameCount": len(frames),
        "captureBackdropSymbolOffsets": offsets,
        **partial_summary,
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
        or frame_symbol_offset != CAPTURE_BACKDROP_VERTEX_BINDING_CALL_OFFSET + 4
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
    call_summaries: list[dict[str, Any]] = []
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
        target_code_hash = hashlib.sha256(target_payload).hexdigest()
        target_code_hashes.append(target_code_hash)
        call_summaries.append(
            {
                "sourceInstructionOffset": offset,
                "targetCodeSHA256": target_code_hash,
                "targetSymbol": call.get("targetSymbol"),
                "targetSymbolOffset": call.get("targetSymbolOffset"),
            }
        )

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
        "directCalls": call_summaries,
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
    elif evidence_schema in {4, 5, 6, 7, 8}:
        classification = {
            4: SAMPLE31_REPEAT_CLASSIFICATION,
            5: CAPTURE_BACKDROP_OPERAND_CLASSIFICATION,
            6: CAPTURE_BACKDROP_REGION_CLASSIFICATION,
            7: CAPTURE_BACKDROP_OWNER_REGION_CLASSIFICATION,
            8: CAPTURE_BACKDROP_OWNER_RECORD_CLASSIFICATION,
        }[evidence_schema]
        result_schema = {4: 3, 5: 4, 6: 5, 7: 6, 8: 7}[evidence_schema]
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
    elif evidence_schema in {4, 5, 6, 7, 8} and (
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
        or (
            evidence_schema in {7, 8}
            and (
                evidence.get("captureBackdropOperandFragments")
                != sorted(CAPTURE_BACKDROP_OPERAND_FRAGMENTS)
                or evidence.get("captureBackdropCallbackMaximumAttemptCount")
                != CAPTURE_BACKDROP_CALLBACK_MAXIMUM_ATTEMPT_COUNT
                or evidence.get("captureBackdropCallbackMaximumFrameCount")
                != CAPTURE_BACKDROP_CALLBACK_MAXIMUM_FRAME_COUNT
                or evidence.get("captureBackdropMemoryReadMaximumAttemptCount")
                != CAPTURE_BACKDROP_MEMORY_READ_MAXIMUM_ATTEMPT_COUNT
                or evidence.get("captureBackdropOwnerPrefixMaximumByteCount")
                != CAPTURE_BACKDROP_OWNER_REGION_PREFIX_BYTE_COUNT
                or evidence.get("captureBackdropOwnerRegionWindowOffset")
                != CAPTURE_BACKDROP_OWNER_REGION_WINDOW_OFFSET
                or evidence.get("captureBackdropOwnerRegionWindowByteCount")
                != CAPTURE_BACKDROP_REGION_PREFIX_BYTE_COUNT
                or (
                    evidence_schema == 7
                    and (
                        evidence.get("captureBackdropRequiredReadMask") != "0x000fffff"
                        or evidence.get("method")
                        != CAPTURE_BACKDROP_OWNER_REGION_METHOD
                    )
                )
                or (
                    evidence_schema == 8
                    and (
                        evidence.get("captureBackdropOwnerObjectPrefixByteCount")
                        != CAPTURE_BACKDROP_OWNER_OBJECT_PREFIX_BYTE_COUNT
                        or evidence.get("captureBackdropOwnerRecordByteCount")
                        != CAPTURE_BACKDROP_OWNER_RECORD_BYTE_COUNT
                        or evidence.get("captureBackdropOwnerRecordMaximumCount")
                        != CAPTURE_BACKDROP_OWNER_RECORD_MAXIMUM_COUNT
                        or evidence.get(
                            "captureBackdropOwnerRecordVectorMaximumByteCount"
                        )
                        != CAPTURE_BACKDROP_OWNER_RECORD_VECTOR_BYTE_COUNT
                        or evidence.get("captureBackdropSourceStateWindowOffset")
                        != CAPTURE_BACKDROP_SOURCE_STATE_WINDOW_OFFSET
                        or evidence.get("captureBackdropSourceStateWindowByteCount")
                        != CAPTURE_BACKDROP_SOURCE_STATE_WINDOW_BYTE_COUNT
                        or evidence.get("captureBackdropRequiredReadMask")
                        != "0x007fffff"
                        or evidence.get("method")
                        != CAPTURE_BACKDROP_OWNER_RECORD_METHOD
                    )
                )
            )
        )
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
    capture_backdrop_source_components = 0
    capture_backdrop_source_mismatches = 0
    capture_backdrop_transform_branches: Counter[str] = Counter()
    capture_backdrop_region_replay_count = 0
    capture_backdrop_region_handle_classes: Counter[str] = Counter()
    capture_backdrop_owner_248_handle_classes: Counter[str] = Counter()
    capture_backdrop_owner_270_handle_classes: Counter[str] = Counter()
    capture_backdrop_owner_248_prefix_byte_counts: Counter[int] = Counter()
    capture_backdrop_owner_270_prefix_byte_counts: Counter[int] = Counter()
    capture_backdrop_owner_region_window_hashes: set[str] = set()
    capture_backdrop_selected_equals_owner_248 = 0
    capture_backdrop_selected_equals_owner_270 = 0
    capture_backdrop_owner_record_counts: Counter[int] = Counter()
    capture_backdrop_owner_record_vector_byte_counts: Counter[int] = Counter()
    capture_backdrop_owner_record_match_counts: Counter[int] = Counter()
    capture_backdrop_owner_selected_record_indices: Counter[int] = Counter()
    capture_backdrop_owner_object_prefix_hashes: set[str] = set()
    capture_backdrop_owner_record_vector_hashes: set[str] = set()
    capture_backdrop_source_state_window_hashes: set[str] = set()
    capture_backdrop_callback_attempt_count = 0
    capture_backdrop_callback_attempt_fragments: Counter[str] = Counter()
    capture_backdrop_callback_symbol_offsets: Counter[str] = Counter()
    capture_backdrop_partial_attempt_count = 0
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
        record_operand_attempt_payloads: list[Any] = []
        for untyped_snapshot in fixed.sequence(
            retained_buffers.get("snapshots"), "retained snapshots"
        ):
            snapshot = holdout.mapping(untyped_snapshot, "retained snapshot")
            if "producerGeometryCallSite" in snapshot:
                producer_geometry_call_sites.append(
                    snapshot["producerGeometryCallSite"]
                )
            if "captureBackdropOperands" in snapshot:
                record_operand_payloads.append(snapshot["captureBackdropOperands"])
            if "captureBackdropOperandAttempt" in snapshot:
                record_operand_attempt_payloads.append(
                    snapshot["captureBackdropOperandAttempt"]
                )
        if evidence_schema in {5, 6, 7, 8}:
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
        if evidence_schema in {7, 8}:
            capture_backdrop_operand_attempts = [
                validate_capture_backdrop_operand_attempt(payload)
                for payload in record_operand_attempt_payloads
            ]
            if len(
                capture_backdrop_operand_attempts
            ) > CAPTURE_BACKDROP_CALLBACK_MAXIMUM_ATTEMPT_COUNT or [
                attempt["attemptIndex"] for attempt in capture_backdrop_operand_attempts
            ] != list(range(len(capture_backdrop_operand_attempts))):
                raise ValueError("capture_backdrop callback attempt order differs")
            capture_backdrop_callback_attempt_count += len(
                capture_backdrop_operand_attempts
            )
            for attempt in capture_backdrop_operand_attempts:
                capture_backdrop_callback_attempt_fragments[
                    str(attempt["fragmentFunction"])
                ] += 1
                capture_backdrop_partial_attempt_count += "partialReadMask" in attempt
                for offset in attempt["captureBackdropSymbolOffsets"]:
                    capture_backdrop_callback_symbol_offsets[str(offset)] += 1
        elif record_operand_attempt_payloads:
            raise ValueError(
                "pre-schema-7 record unexpectedly contains callback attempts"
            )
        else:
            capture_backdrop_operand_attempts = []
        observed = holdout.observed_policy(record, scale=scale)
        mesh = holdout.mapping(observed.get("producerMesh"), "producer mesh")
        q_components += int(mesh["sourceScaleComponentCount"])
        q_mismatches += int(mesh["sourceScaleMismatchedComponents"])
        topology_counts[int(mesh["vertexCount"])] += 1
        phase_counts[str(intervention["phase"])] += 1

        if capture_backdrop_operands is not None:
            expected_operand_schema = evidence_schema - 4
            if capture_backdrop_operands["schemaVersion"] != expected_operand_schema:
                raise ValueError(
                    "capture_backdrop operand schema differs from outer gate"
                )
            primary_vertices = fixed.sequence(
                mesh.get("primaryVertices"), "primary producer vertices"
            )
            if len(primary_vertices) != 4:
                raise ValueError("primary producer vertex count differs")
            parsed_primary_vertices = [
                fixed.sequence(vertex, "primary vertex") for vertex in primary_vertices
            ]
            if any(len(vertex) < 6 for vertex in parsed_primary_vertices):
                raise ValueError("primary producer vertex is incomplete")
            observed_position_bits = [
                holdout.float32_bits(
                    holdout.numeric(component, "primary position component")
                )
                for vertex in parsed_primary_vertices
                for component in vertex[:2]
            ]
            observed_source_bits = [
                holdout.float32_bits(
                    holdout.numeric(component, "primary source component")
                )
                for vertex in parsed_primary_vertices
                for component in vertex[4:6]
            ]
            predicted_position_bits = capture_backdrop_operands[
                "predictedPrimaryPositionBits"
            ]
            predicted_source_bits = capture_backdrop_operands[
                "predictedPrimarySourceBits"
            ]
            if capture_backdrop_operands["scaleBits"] != holdout.float32_bits(scale):
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
            capture_backdrop_source_components += len(observed_source_bits)
            capture_backdrop_source_mismatches += sum(
                predicted != observed
                for predicted, observed in zip(
                    predicted_source_bits,
                    observed_source_bits,
                    strict=True,
                )
            )
            capture_backdrop_transform_branches[
                str(capture_backdrop_operands["transformBranch"])
            ] += 1
            if evidence_schema in {6, 7, 8}:
                if capture_backdrop_operands.get("consumedRegionRectExact") is not True:
                    raise ValueError("capture_backdrop selected-region replay differs")
                capture_backdrop_region_replay_count += 1
                capture_backdrop_region_handle_classes[
                    str(capture_backdrop_operands["regionHandleClass"])
                ] += 1
            if evidence_schema in {7, 8}:
                capture_backdrop_owner_248_handle_classes[
                    str(capture_backdrop_operands["ownerRegion248Class"])
                ] += 1
                capture_backdrop_owner_270_handle_classes[
                    str(capture_backdrop_operands["ownerRegion270Class"])
                ] += 1
                capture_backdrop_owner_248_prefix_byte_counts[
                    int(capture_backdrop_operands["ownerRegion248PrefixByteCount"])
                ] += 1
                capture_backdrop_owner_270_prefix_byte_counts[
                    int(capture_backdrop_operands["ownerRegion270PrefixByteCount"])
                ] += 1
                capture_backdrop_owner_region_window_hashes.add(
                    str(capture_backdrop_operands["ownerRegionWindowSHA256"])
                )
                capture_backdrop_selected_equals_owner_248 += bool(
                    capture_backdrop_operands["selectedEqualsOwner248"]
                )
                capture_backdrop_selected_equals_owner_270 += bool(
                    capture_backdrop_operands["selectedEqualsOwner270"]
                )
            if evidence_schema == 8:
                owner_record_count = int(capture_backdrop_operands["ownerRecordCount"])
                capture_backdrop_owner_record_counts[owner_record_count] += 1
                capture_backdrop_owner_record_vector_byte_counts[
                    int(capture_backdrop_operands["ownerRecordVectorByteCount"])
                ] += 1
                capture_backdrop_owner_record_match_counts[
                    len(capture_backdrop_operands["sourceRecordMatchIndices"])
                ] += 1
                capture_backdrop_owner_selected_record_indices[
                    int(capture_backdrop_operands["selectedOwnerRecordIndex"])
                ] += 1
                capture_backdrop_owner_object_prefix_hashes.add(
                    str(capture_backdrop_operands["ownerObjectPrefixSHA256"])
                )
                capture_backdrop_owner_record_vector_hashes.add(
                    str(capture_backdrop_operands["ownerRecordVectorSHA256"])
                )
                capture_backdrop_source_state_window_hashes.add(
                    str(capture_backdrop_operands["sourceStateWindowSHA256"])
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
                "observedPrimarySourceBits": observed_source_bits,
                "primarySourceExact": (predicted_source_bits == observed_source_bits),
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
                **(
                    {
                        "captureBackdropOperandAttempts": (
                            capture_backdrop_operand_attempts
                        )
                    }
                    if evidence_schema in {7, 8}
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
    if evidence_schema in {5, 6, 7, 8}:
        capture_backdrop_code = holdout.mapping(
            producer_geometry_call_site.get("captureBackdrop"),
            "capture_backdrop validated code summary",
        )
        region_iterate_calls = [
            holdout.mapping(value, "capture_backdrop region-iterate call")
            for value in fixed.sequence(
                capture_backdrop_code.get("directCalls"),
                "capture_backdrop validated direct calls",
            )
            if holdout.mapping(value, "capture_backdrop validated direct call").get(
                "sourceInstructionOffset"
            )
            == CAPTURE_BACKDROP_REGION_ITERATE_CALL_OFFSET
        ]
        region_iterate_exact = (
            len(region_iterate_calls) == 1
            and region_iterate_calls[0].get("targetCodeSHA256")
            == CAPTURE_BACKDROP_EXPECTED_REGION_ITERATE_PREFIX_SHA256
            and region_iterate_calls[0].get("targetSymbol")
            == CAPTURE_BACKDROP_REGION_ITERATE_SYMBOL
            and region_iterate_calls[0].get("targetSymbolOffset") == "0x0"
        )
        if (
            len(producer_geometry_call_sites) != 1
            or producer_geometry_call_site.get("schemaVersion") != 5
            or capture_backdrop_code.get("symbolPrefixSHA256")
            != CAPTURE_BACKDROP_EXPECTED_SYMBOL_PREFIX_SHA256
            or capture_backdrop_code.get("operandFramePrologueExact") is not True
            or capture_backdrop_operand_count != expected_count
            or capture_backdrop_position_mismatches != 0
            or capture_backdrop_source_mismatches != 0
            or (
                evidence_schema in {6, 7, 8}
                and (
                    capture_backdrop_region_replay_count != expected_count
                    or not region_iterate_exact
                )
            )
            or (
                evidence_schema in {7, 8}
                and (
                    capture_backdrop_owner_248_handle_classes
                    != Counter({"packed": 114})
                    or capture_backdrop_owner_270_handle_classes
                    != Counter({"packed": 112, "pointer": 2})
                    or capture_backdrop_selected_equals_owner_248 != expected_count
                    or capture_backdrop_selected_equals_owner_270 != 111
                )
            )
            or (
                evidence_schema == 8
                and (
                    capture_backdrop_owner_record_counts
                    != Counter(
                        {CAPTURE_BACKDROP_OWNER_RECORD_EXPECTED_COUNT: (expected_count)}
                    )
                    or capture_backdrop_owner_record_match_counts
                    != Counter(
                        {
                            CAPTURE_BACKDROP_OWNER_RECORD_EXPECTED_MATCH_COUNT: (
                                expected_count
                            )
                        }
                    )
                    or capture_backdrop_owner_selected_record_indices
                    != Counter(
                        {
                            CAPTURE_BACKDROP_OWNER_RECORD_EXPECTED_SELECTED_INDEX: (
                                expected_count
                            )
                        }
                    )
                )
            )
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
                "sources="
                f"{capture_backdrop_source_components - capture_backdrop_source_mismatches}/"
                f"{capture_backdrop_source_components}, "
                f"regions={capture_backdrop_region_replay_count}/{expected_count}, "
                "selectedOwner248="
                f"{capture_backdrop_selected_equals_owner_248}/{expected_count}, "
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
                        "primarySourceComponentCount": (
                            capture_backdrop_source_components
                        ),
                        "primarySourceMismatchedComponents": (
                            capture_backdrop_source_mismatches
                        ),
                        "primarySourceExact": (capture_backdrop_source_mismatches == 0),
                        "transformBranchCounts": {
                            name: capture_backdrop_transform_branches[name]
                            for name in sorted(capture_backdrop_transform_branches)
                        },
                        "singleMappedSymbolAddress": (
                            len(capture_backdrop_symbol_addresses) == 1
                        ),
                        "symbolPrefixSHA256": (
                            CAPTURE_BACKDROP_EXPECTED_SYMBOL_PREFIX_SHA256
                        ),
                        "allowNumericTolerance": False,
                    }
                }
                if evidence_schema in {5, 6, 7, 8}
                else {}
            ),
            **(
                {
                    "captureBackdropConsumedRegionReplay": {
                        "captureCount": capture_backdrop_region_replay_count,
                        "expectedCaptureCount": expected_count,
                        "consumedRegionRectExact": (
                            capture_backdrop_region_replay_count == expected_count
                        ),
                        "regionHandleClassCounts": {
                            name: capture_backdrop_region_handle_classes[name]
                            for name in sorted(capture_backdrop_region_handle_classes)
                        },
                        "byteGatedRegionIteratorExact": region_iterate_exact,
                        "regionIteratorCallOffset": (
                            CAPTURE_BACKDROP_REGION_ITERATE_CALL_OFFSET
                        ),
                        "regionIteratorSymbol": (
                            CAPTURE_BACKDROP_REGION_ITERATE_SYMBOL
                        ),
                        "regionIteratorPrefixSHA256": (
                            CAPTURE_BACKDROP_EXPECTED_REGION_ITERATE_PREFIX_SHA256
                        ),
                        "allowNumericTolerance": False,
                    }
                }
                if evidence_schema in {6, 7, 8}
                else {}
            ),
            **(
                {
                    "captureBackdropOwnerRegionReplay": {
                        "owner248HandleClassCounts": {
                            name: capture_backdrop_owner_248_handle_classes[name]
                            for name in sorted(
                                capture_backdrop_owner_248_handle_classes
                            )
                        },
                        "owner270HandleClassCounts": {
                            name: capture_backdrop_owner_270_handle_classes[name]
                            for name in sorted(
                                capture_backdrop_owner_270_handle_classes
                            )
                        },
                        "owner248PrefixByteCountStates": {
                            str(count): capture_backdrop_owner_248_prefix_byte_counts[
                                count
                            ]
                            for count in sorted(
                                capture_backdrop_owner_248_prefix_byte_counts
                            )
                        },
                        "owner270PrefixByteCountStates": {
                            str(count): capture_backdrop_owner_270_prefix_byte_counts[
                                count
                            ]
                            for count in sorted(
                                capture_backdrop_owner_270_prefix_byte_counts
                            )
                        },
                        "ownerRegionWindowByteCount": 256,
                        "distinctOwnerRegionWindowCount": len(
                            capture_backdrop_owner_region_window_hashes
                        ),
                        "embeddedOwnerHandlesExact": True,
                        "selectedEqualsOwner248Count": (
                            capture_backdrop_selected_equals_owner_248
                        ),
                        "selectedEqualsOwner270Count": (
                            capture_backdrop_selected_equals_owner_270
                        ),
                        "independentOwnerPrefixesCaptured": True,
                        "allowNumericTolerance": False,
                    },
                    "captureBackdropCallbackProvenance": {
                        "attemptCount": capture_backdrop_callback_attempt_count,
                        "partialOperandAttemptCount": (
                            capture_backdrop_partial_attempt_count
                        ),
                        "fragmentFunctionCounts": {
                            name: capture_backdrop_callback_attempt_fragments[name]
                            for name in sorted(
                                capture_backdrop_callback_attempt_fragments
                            )
                        },
                        "captureBackdropSymbolOffsetCounts": {
                            name: capture_backdrop_callback_symbol_offsets[name]
                            for name in sorted(capture_backdrop_callback_symbol_offsets)
                        },
                        "maximumAttemptsPerRecord": (
                            CAPTURE_BACKDROP_CALLBACK_MAXIMUM_ATTEMPT_COUNT
                        ),
                    },
                }
                if evidence_schema in {7, 8}
                else {}
            ),
            **(
                {
                    "captureBackdropOwnerRecordReplay": {
                        "ownerObjectPrefixByteCount": (
                            CAPTURE_BACKDROP_OWNER_OBJECT_PREFIX_BYTE_COUNT
                        ),
                        "ownerRecordCountStates": {
                            str(count): capture_backdrop_owner_record_counts[count]
                            for count in sorted(capture_backdrop_owner_record_counts)
                        },
                        "ownerRecordVectorByteCountStates": {
                            str(count): (
                                capture_backdrop_owner_record_vector_byte_counts[count]
                            )
                            for count in sorted(
                                capture_backdrop_owner_record_vector_byte_counts
                            )
                        },
                        "sourceRecordMatchCountStates": {
                            str(count): capture_backdrop_owner_record_match_counts[
                                count
                            ]
                            for count in sorted(
                                capture_backdrop_owner_record_match_counts
                            )
                        },
                        "selectedOwnerRecordIndexStates": {
                            str(index): (
                                capture_backdrop_owner_selected_record_indices[index]
                            )
                            for index in sorted(
                                capture_backdrop_owner_selected_record_indices
                            )
                        },
                        "distinctOwnerObjectPrefixCount": len(
                            capture_backdrop_owner_object_prefix_hashes
                        ),
                        "distinctOwnerRecordVectorCount": len(
                            capture_backdrop_owner_record_vector_hashes
                        ),
                        "distinctSourceStateWindowCount": len(
                            capture_backdrop_source_state_window_hashes
                        ),
                        "sourceStateWindowByteCount": (
                            CAPTURE_BACKDROP_SOURCE_STATE_WINDOW_BYTE_COUNT
                        ),
                        "ownerRegionWindowEmbeddedInPrefixExact": True,
                        "sourceKeyMatchedRecordEveryState": True,
                        "allowNumericTolerance": False,
                    }
                }
                if evidence_schema == 8
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
                6: "captureBackdropSelectedRegionsRequirePostOpeningPolicyMapping",
                7: "captureBackdropOwnerRegionsRequirePostOpeningConstructionMapping",
                8: "captureBackdropOwnerRecordsRequirePostOpeningConstructionReplay",
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
