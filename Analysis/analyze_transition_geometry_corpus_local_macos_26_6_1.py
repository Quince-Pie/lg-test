#!/usr/bin/env python3
"""Gate retained macOS 26.6.1 transition geometry and backdrop evidence."""

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
import hashlib
import json
import math
from pathlib import Path
import struct
from typing import Any, TypedDict

import validate_variable_blur_selected_region_origin as selected


RESULT_SCHEMA_VERSION = 3
TIMELINE_SCHEMA_VERSION = 5
DYNAMIC_UNIFORM_SCHEMA_VERSION = 9
EXPECTED_CAPTURE_METHOD = (
    "copied-presentation-background-filter-plus-compatible-layer-state-on-"
    "fresh-static-model-tree-with-original-producer-input-and-metadata-only-"
    "stage-capture"
)
EXPECTED_CRITICAL_PATHS = [
    [],
    [0],
    [1],
    [1, 0],
    [1, 0, 0],
    [1, 0, 1],
    [1, 0, 1, 0],
    [1, 0, 1, 0, 0],
    [1, 0, 1, 0, 0, 0],
    [1, 0, 1, 0, 0, 0, 0],
    [1, 0, 1, 2],
    [1, 0, 1, 2, 0],
]
BACKGROUND_PIPELINES = frozenset(
    {
        "com.apple.coreanimation.PBGRABsovXm_TghzA2Xhf_Isrc",
        "com.apple.coreanimation.PBGRABsovXm_TghsA2Xhf_Isrc",
    }
)
FINAL_HIGHLIGHT_PIPELINE = "com.apple.coreanimation.PBGRAXm_TkfhBvcmA2Xhfc_Iscd"
VERTEX_STRIDE = 48
MAIN_VERTEX_COUNT = 6
SHADOW_VERTEX_COUNT = 16
SHADOW_INDICES = (
    0,
    1,
    5,
    5,
    4,
    0,
    3,
    7,
    6,
    6,
    2,
    3,
    10,
    11,
    15,
    15,
    14,
    10,
    9,
    13,
    12,
    12,
    8,
    9,
    1,
    2,
    6,
    6,
    5,
    1,
    4,
    5,
    9,
    9,
    8,
    4,
    6,
    7,
    11,
    11,
    10,
    6,
    9,
    10,
    14,
    14,
    13,
    9,
)
FINAL_QUAD_INDICES = (0, 1, 2, 2, 3, 0)
FINAL_BORDER_INDICES = SHADOW_INDICES[:24]

type JsonObject = dict[str, Any]
type Vertex = tuple[float, float, float, float, float, float, float, float]


class ProducerCrop(TypedDict):
    allocationMargin: float
    cropOrigin: tuple[int, int]
    activeExtent: tuple[int, int]
    storageExtent: tuple[int, int]


EXPECTED_INPUTS: dict[str, dict[str, Any]] = {
    "dematerialize-clear-dark.json": {
        "sha256": "45f912caa7f52c4e0ef7fef96ccf71726c9c5014b5c5d0386b92fab3ef11e86a",
        "material": "clear",
        "appearance": "dark",
        "direction": "dematerialize",
        "geometry": "circle-464-center",
        "records": 31,
    },
    "dematerialize-clear-light.json": {
        "sha256": "8a49dee85c59135f6c63279576ad66af2b69935a0fb2a6c82a08e09b8c2c2c49",
        "material": "clear",
        "appearance": "light",
        "direction": "dematerialize",
        "geometry": "circle-456-center",
        "records": 31,
    },
    "dematerialize-regular-dark.json": {
        "sha256": "d4c4e2721003efa0e4e58712a681e6898ba60819ad3f16923d833cc7c945ae69",
        "material": "regular",
        "appearance": "dark",
        "direction": "dematerialize",
        "geometry": "circle-480-center",
        "records": 31,
    },
    "dematerialize-regular-light.json": {
        "sha256": "dd28332a6fda069c3657da4d0a38e1df53d24233b8bcef68f0d39cd7f4b4d8ec",
        "material": "regular",
        "appearance": "light",
        "direction": "dematerialize",
        "geometry": "circle-472-center",
        "records": 31,
    },
    "materialize-clear-dark.json": {
        "sha256": "51be1573be9aade902a0c3630f7d1fae6a2b0d4be9f7886d28b07976fc7d2aa2",
        "material": "clear",
        "appearance": "dark",
        "direction": "materialize",
        "geometry": "circle-463-center",
        "records": 32,
    },
    "materialize-clear-light.json": {
        "sha256": "a037ea8c762f0ba7db875a04944f50d81127e7036a6c4b2509292ee75c4ca4cd",
        "material": "clear",
        "appearance": "light",
        "direction": "materialize",
        "geometry": "circle-455-center",
        "records": 32,
    },
    "materialize-regular-dark.json": {
        "sha256": "2c0416417b4bc5b21752d13344a9ee44e6ceda801b2d9693e9fa0c4786282b90",
        "material": "regular",
        "appearance": "dark",
        "direction": "materialize",
        "geometry": "circle-479-center",
        "records": 32,
    },
    "materialize-regular-light.json": {
        "sha256": "d50f0ee922edbd2e0c1c1fc03f7e0a9d4e83e05d3e3e340e92ae0ea197318c29",
        "material": "regular",
        "appearance": "light",
        "direction": "materialize",
        "geometry": "circle-471-center",
        "records": 32,
    },
}


def mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} is not an object")
    return value


def sequence(value: object, name: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{name} is not an array")
    return value


def integer(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} is not an integer")
    return value


def finite(value: object, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} is not finite")
    return result


def single(values: Sequence[Any], name: str) -> Mapping[str, Any]:
    if len(values) != 1:
        raise ValueError(f"expected one {name}; found {len(values)}")
    return mapping(values[0], name)


def float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def float32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def float64_bits(value: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", value))[0]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def pipeline_label(record: Mapping[str, Any]) -> str:
    pipeline = record.get("pipeline")
    if not isinstance(pipeline, Mapping):
        return ""
    label = pipeline.get("label")
    return label if isinstance(label, str) else ""


def payload(record: Mapping[str, Any]) -> bytes:
    description = mapping(record.get("payload"), "buffer payload")
    encoded = description.get("hex")
    length = description.get("lengthBytes")
    if not isinstance(encoded, str):
        raise ValueError("buffer payload has no hexadecimal bytes")
    result = bytes.fromhex(encoded)
    if not isinstance(length, int) or length != len(result):
        raise ValueError("buffer payload length differs")
    return result


def expected_backdrop_scale(material: str, remaining: float) -> float:
    coefficient = {"clear": 0.5, "regular": 0.75}.get(material)
    if coefficient is None:
        raise ValueError(f"unsupported material: {material!r}")
    remaining32 = float32(remaining)
    if float32_bits(remaining) != float32_bits(remaining32):
        raise ValueError("remaining is not representable as captured binary32")
    return float32(1.0 - coefficient * remaining32)


def expected_producer_crop(
    geometry: Mapping[str, Any],
    *,
    material: str,
    carrier_position: Sequence[float],
    backdrop_scale: float,
) -> ProducerCrop:
    """Construct Apple's retained full-shape backdrop producer crop."""
    if len(carrier_position) != 2:
        raise ValueError("producer carrier position component count differs")
    width = finite(geometry.get("width"), "geometry width")
    height = finite(geometry.get("height"), "geometry height")
    window_width = finite(geometry.get("windowWidth"), "window width")
    window_height = finite(geometry.get("windowHeight"), "window height")
    position_x = finite(carrier_position[0], "carrier position x")
    position_y = finite(carrier_position[1], "carrier position y")
    scale = finite(backdrop_scale, "backdrop scale")
    if (
        geometry.get("shape") != "circle"
        or width <= 0.0
        or width != height
        or window_width <= 0.0
        or window_height <= 0.0
        or scale <= 0.0
    ):
        raise ValueError("producer crop geometry differs")
    if material == "clear":
        margin = 0.0
    elif material == "regular":
        margin = float32(0.35 * width)
    else:
        raise ValueError(f"unsupported material: {material!r}")

    intervals = (
        (
            max(0.0, position_x - margin),
            min(window_width, position_x + width + margin),
        ),
        (
            max(0.0, window_height - (position_y + height) - margin),
            min(window_height, window_height - position_y + margin),
        ),
    )
    crop_origin: list[int] = []
    active_extent: list[int] = []
    storage_extent: list[int] = []
    for axis, (lower, upper) in enumerate(intervals):
        if not 0.0 <= lower < upper:
            raise ValueError("producer crop does not intersect the window")
        scaled_lower = scale * lower
        scaled_upper = scale * upper
        if lower == 0.0:
            origin = 0
        elif axis == 0:
            origin = math.floor(scaled_lower) + 1
        else:
            origin = math.ceil(scaled_lower)
        extent = math.floor(scaled_upper) - origin
        if extent <= 0:
            raise ValueError("producer crop is empty")
        crop_origin.append(origin)
        active_extent.append(extent)
        storage_extent.append(selected.align_up(extent))
    return {
        "allocationMargin": margin,
        "cropOrigin": (crop_origin[0], crop_origin[1]),
        "activeExtent": (active_extent[0], active_extent[1]),
        "storageExtent": (storage_extent[0], storage_extent[1]),
    }


def source_coordinate(
    position: float,
    *,
    backdrop_scale: float,
    crop_origin: int,
    copy_offset: int,
    allocation_extent: int,
) -> float:
    if allocation_extent <= 0:
        raise ValueError("allocation extent must be positive")
    staged = float32(
        float(position) * float(backdrop_scale) - crop_origin - copy_offset
    )
    return float32(staged * float32(1.0 / allocation_extent))


def layer_states(record: Mapping[str, Any]) -> dict[tuple[int, ...], Mapping[str, Any]]:
    states = [
        mapping(value, "captured layer state")
        for value in sequence(
            record.get("capturedLayerStates"), "captured layer states"
        )
    ]
    result: dict[tuple[int, ...], Mapping[str, Any]] = {}
    for state in states:
        path_values = sequence(state.get("path"), "captured layer path")
        path = tuple(
            integer(value, "captured layer path component") for value in path_values
        )
        if path in result:
            raise ValueError(f"duplicate captured layer path: {path}")
        result[path] = state
    return result


def expected_dynamic_layer_state(
    geometry: Mapping[str, Any], remaining: float
) -> dict[str, tuple[float, ...]]:
    """Reproduce the observed SwiftUI/CoreGraphics dynamic circle geometry."""
    width = finite(geometry.get("width"), "geometry width")
    height = finite(geometry.get("height"), "geometry height")
    center_x = finite(geometry.get("centerX"), "geometry center x")
    center_y = finite(geometry.get("centerY"), "geometry center y")
    remaining32 = float32(remaining)
    if (
        geometry.get("shape") != "circle"
        or width <= 0.0
        or width != height
        or remaining != remaining32
        or not 0.0 < remaining32 <= 1.0
    ):
        raise ValueError("dynamic circle geometry differs")

    carrier_extent = width * remaining32
    carrier_position = (
        center_x - carrier_extent / 2.0,
        center_y - carrier_extent / 2.0,
    )

    progress32 = float32(1.0 - remaining32)
    scale_limit = min((width + 16.0) / width, 1.2)
    transition_scale = 1.0 + progress32 * (scale_limit - 1.0)
    half = width / 2.0

    def centered_affine(value: float, scale: float) -> float:
        translation = half + (-half * scale)
        # CGPointApplyAffineTransform uses FMUL, FMLA, then a separate FADD
        # for the translation. Keep that final add outside the fused operation.
        return math.fma(scale, value, 0.0) + translation

    lower = centered_affine(0.0, transition_scale)
    upper = centered_affine(width, transition_scale)
    square_root = math.sqrt(scale_limit)
    for scale in (1.0 / square_root, square_root):
        lower = centered_affine(lower, scale)
        upper = centered_affine(upper, scale)

    integral_carrier_extent = math.floor(carrier_extent)
    if carrier_extent - integral_carrier_extent == 0.5:
        raise ValueError("dynamic carrier half-tie rule is not measured")
    snapped_carrier_extent = math.floor(carrier_extent + 0.5)
    root_translation_x = (
        center_x - half + (snapped_carrier_extent - carrier_extent) / 2.0
    )
    root_translation_y = (
        center_y - half + (snapped_carrier_extent - carrier_extent) / 2.0
    )
    root_lower = lower + root_translation_x
    root_upper = upper + root_translation_x
    element_extent = root_upper - root_lower
    # This subtraction is observably different from the algebraically
    # equivalent (snapped_carrier_extent - element_extent) / 2.
    element_position_x = root_lower - carrier_position[0]
    element_position_y = (lower + root_translation_y) - carrier_position[1]
    return {
        "carrierBounds": (0.0, 0.0, carrier_extent, carrier_extent),
        "carrierPosition": carrier_position,
        "elementBounds": (0.0, 0.0, element_extent, element_extent),
        "elementPosition": (element_position_x, element_position_y),
    }


def vector(
    value: object,
    name: str,
    count: int,
) -> tuple[float, ...]:
    values = sequence(value, name)
    if len(values) != count:
        raise ValueError(f"{name} component count differs")
    return tuple(finite(component, f"{name} component") for component in values)


def expected_main_vertices(record: Mapping[str, Any]) -> list[Vertex]:
    states = layer_states(record)
    root = mapping(states.get(()), "root layer state")
    carrier = mapping(states.get((1,)), "carrier layer state")
    element = mapping(
        states.get((1, 0, 1, 0, 0, 0, 0)),
        "background SDF element layer state",
    )
    if (
        root.get("class") != "NSViewBackingLayer"
        or carrier.get("class") != "CALayer"
        or element.get("class") != "CASDFElementLayer"
    ):
        raise ValueError("main geometry layer classes differ")
    root_bounds = vector(root.get("bounds"), "root bounds", 4)
    carrier_position = vector(carrier.get("position"), "carrier position", 2)
    element_position = vector(element.get("position"), "element position", 2)
    element_bounds = vector(element.get("bounds"), "element bounds", 4)
    if (
        root_bounds[0:2] != (0.0, 0.0)
        or element_bounds[0:2] != (0.0, 0.0)
        or element_bounds[2] <= 0.0
        or element_bounds[2] != element_bounds[3]
    ):
        raise ValueError("main geometry bounds differ")
    extent = element_bounds[2]
    left = float32(carrier_position[0] + element_position[0])
    right = float32((carrier_position[0] + element_position[0]) + extent)
    top = float32((root_bounds[3] - carrier_position[1]) - element_position[1])
    bottom = float32(
        ((root_bounds[3] - carrier_position[1]) - element_position[1]) - extent
    )
    local_minimum = float32(-extent / 2.0)
    local_maximum = float32(extent / 2.0)
    return [
        (left, top, 0.0, 1.0, local_minimum, local_minimum, 0.0, 0.0),
        (right, top, 0.0, 1.0, local_maximum, local_minimum, 0.0, 0.0),
        (right, bottom, 0.0, 1.0, local_maximum, local_maximum, 0.0, 0.0),
        (right, bottom, 0.0, 1.0, local_maximum, local_maximum, 0.0, 0.0),
        (left, bottom, 0.0, 1.0, local_minimum, local_maximum, 0.0, 0.0),
        (left, top, 0.0, 1.0, local_minimum, local_minimum, 0.0, 0.0),
    ]


def expected_shadow_vertices(
    record: Mapping[str, Any],
    *,
    material: str,
) -> list[Vertex]:
    states = layer_states(record)
    root = mapping(states.get(()), "root layer state")
    carrier = mapping(states.get((1,)), "carrier layer state")
    element = mapping(
        states.get((1, 0, 1, 0, 0, 0, 0)),
        "background SDF element layer state",
    )
    root_bounds = vector(root.get("bounds"), "root bounds", 4)
    carrier_position = vector(carrier.get("position"), "carrier position", 2)
    element_position = vector(element.get("position"), "element position", 2)
    element_bounds = vector(element.get("bounds"), "element bounds", 4)
    if (
        root_bounds[0:2] != (0.0, 0.0)
        or element_bounds[0:2] != (0.0, 0.0)
        or element_bounds[2] <= 0.0
        or element_bounds[2] != element_bounds[3]
    ):
        raise ValueError("shadow geometry bounds differ")
    remaining = finite(record.get("remaining"), "remaining")
    if material == "clear":
        margin = 0.0
    elif material == "regular":
        margin = float32(48.0 * float32(remaining))
    else:
        raise ValueError(f"unsupported material: {material}")

    extent = element_bounds[2]
    horizontal_origin = carrier_position[0] + element_position[0]
    vertical_origin = (root_bounds[3] - carrier_position[1]) - element_position[1]
    top_margin = max(margin - 8.0, 0.0)
    extended_width = float32(extent + margin)
    extended_height = float32((extent + margin) + 8.0)
    positions_x = (
        float32(horizontal_origin - margin),
        float32(horizontal_origin),
        float32(horizontal_origin + extent),
        float32(horizontal_origin + extended_width),
    )
    positions_y = (
        float32(vertical_origin + top_margin),
        float32(vertical_origin),
        float32(vertical_origin - extent),
        float32(vertical_origin - extended_height),
    )

    local_minimum = float32(-extent / 2.0)
    local_maximum = float32(extent / 2.0)
    # QuartzCore rounds the outer bounds to binary32, converts them back to
    # binary64, measures them against the unrounded inner bounds, and only then
    # rounds the adjusted SDF coordinate. Replacing this with half+margin is
    # observably one ULP wrong in the retained corpus.
    coordinates_x = (
        float32(float(local_minimum) + float(float32(-margin))),
        local_minimum,
        local_maximum,
        float32(float(local_maximum) + (float(extended_width) - extent)),
    )
    coordinates_y = (
        float32(float(local_minimum) + float(float32(-top_margin))),
        local_minimum,
        local_maximum,
        float32(float(local_maximum) + (float(extended_height) - extent)),
    )
    return [
        (
            position_x,
            position_y,
            0.0,
            1.0,
            coordinate_x,
            coordinate_y,
            0.0,
            0.0,
        )
        for position_y, coordinate_y in zip(positions_y, coordinates_y, strict=True)
        for position_x, coordinate_x in zip(positions_x, coordinates_x, strict=True)
    ]


def decode_vertices(snapshot: Mapping[str, Any], count: int) -> list[Vertex]:
    raw = payload(snapshot)
    required = count * VERTEX_STRIDE
    if len(raw) < required:
        raise ValueError("vertex payload is truncated")
    return [
        struct.unpack_from("<8f", raw, index * VERTEX_STRIDE) for index in range(count)
    ]


def snapshot_at(
    snapshots: Sequence[Mapping[str, Any]],
    *,
    sequence_number: int,
    stage: str,
    index: int,
    label: str,
) -> Mapping[str, Any]:
    return single(
        [
            snapshot
            for snapshot in snapshots
            if snapshot.get("sequence") == sequence_number
            and snapshot.get("stage") == stage
            and snapshot.get("index") == index
            and pipeline_label(snapshot) == label
        ],
        f"{label} {stage} buffer {index} at sequence {sequence_number}",
    )


def background_geometry(record: Mapping[str, Any]) -> tuple[list[Vertex], list[Vertex]]:
    render = mapping(record.get("render"), "dynamic render")
    probe = mapping(render.get("metalUniformProbe"), "Metal uniform probe")
    buffers = mapping(render.get("metalBufferSnapshots"), "Metal buffer snapshots")
    records = [
        mapping(value, "Metal record")
        for value in sequence(probe.get("records"), "Metal records")
    ]
    snapshots = [
        mapping(value, "Metal snapshot")
        for value in sequence(buffers.get("snapshots"), "Metal snapshots")
    ]
    pivot = single(
        [
            item
            for item in records
            if pipeline_label(item) in BACKGROUND_PIPELINES
            and item.get("kind") == "buffer"
            and item.get("stage") == "fragment"
            and item.get("index") == 6
        ],
        "current background profile binding",
    )
    background_pipeline = pipeline_label(pivot)
    encoder = pivot.get("encoder")
    pivot_sequence = integer(pivot.get("sequence"), "background pivot sequence")
    branch = [
        item
        for item in records
        if pipeline_label(item) == background_pipeline
        and item.get("encoder") == encoder
        and integer(item.get("sequence"), "background record sequence")
        >= pivot_sequence
    ]
    main_binding = single(
        [
            item
            for item in branch
            if item.get("kind") == "buffer"
            and item.get("stage") == "vertex"
            and item.get("index") == 1
        ],
        "background main vertex binding",
    )
    main_draw = single(
        [
            item
            for item in branch
            if item.get("kind") == "drawPrimitivesInstanced"
            and item.get("vertexCount") == MAIN_VERTEX_COUNT
        ],
        "background main draw",
    )
    main_draw_sequence = integer(main_draw.get("sequence"), "main draw sequence")
    shadow_binding = single(
        [
            item
            for item in branch
            if item.get("kind") == "bufferOffset"
            and item.get("stage") == "vertex"
            and item.get("index") == 1
            and integer(item.get("sequence"), "shadow binding sequence")
            > main_draw_sequence
        ],
        "background shadow vertex binding",
    )
    shadow_binding_sequence = integer(
        shadow_binding.get("sequence"), "shadow binding sequence"
    )
    shadow_draw = single(
        [
            item
            for item in branch
            if item.get("kind") == "drawIndexedPrimitives"
            and item.get("indexCount") == len(SHADOW_INDICES)
            and integer(item.get("sequence"), "shadow draw sequence")
            > shadow_binding_sequence
        ],
        "background shadow draw",
    )
    if (
        main_draw.get("primitiveType") != 3
        or main_draw.get("instanceCount") != 1
        or shadow_draw.get("primitiveType") != 3
        or shadow_draw.get("indexType") != 0
    ):
        raise ValueError("background draw topology differs")
    main_snapshot = snapshot_at(
        snapshots,
        sequence_number=integer(main_binding.get("sequence"), "main binding sequence"),
        stage="vertex",
        index=1,
        label=background_pipeline,
    )
    shadow_snapshot = snapshot_at(
        snapshots,
        sequence_number=shadow_binding_sequence,
        stage="vertex",
        index=1,
        label=background_pipeline,
    )
    shadow_index_snapshot = snapshot_at(
        snapshots,
        sequence_number=integer(shadow_draw.get("sequence"), "shadow draw sequence"),
        stage="index",
        index=-1,
        label=background_pipeline,
    )
    index_raw = payload(shadow_index_snapshot)
    required = 2 * len(SHADOW_INDICES)
    if len(index_raw) < required:
        raise ValueError("background shadow index payload is truncated")
    if struct.unpack_from(f"<{len(SHADOW_INDICES)}H", index_raw) != SHADOW_INDICES:
        raise ValueError("background shadow index topology differs")
    return (
        decode_vertices(main_snapshot, MAIN_VERTEX_COUNT),
        decode_vertices(shadow_snapshot, SHADOW_VERTEX_COUNT),
    )


def final_highlight_inventory(record: Mapping[str, Any]) -> dict[str, Any]:
    render = mapping(record.get("render"), "dynamic render")
    probe = mapping(render.get("metalUniformProbe"), "Metal uniform probe")
    buffers = mapping(render.get("metalBufferSnapshots"), "Metal buffer snapshots")
    records = [
        mapping(value, "Metal record")
        for value in sequence(probe.get("records"), "Metal records")
        if pipeline_label(mapping(value, "Metal record")) == FINAL_HIGHLIGHT_PIPELINE
    ]
    snapshots = [
        mapping(value, "Metal snapshot")
        for value in sequence(buffers.get("snapshots"), "Metal snapshots")
    ]
    draw = single(
        [item for item in records if item.get("kind") == "drawIndexedPrimitives"],
        "final-highlight indexed draw",
    )
    index_count = integer(draw.get("indexCount"), "final-highlight index count")
    if draw.get("primitiveType") != 3 or draw.get("indexType") != 0:
        raise ValueError("final-highlight draw topology differs")
    fragment_binding = single(
        [
            item
            for item in records
            if item.get("kind") in {"buffer", "bufferOffset"}
            and item.get("stage") == "fragment"
            and item.get("index") == 1
        ],
        "final-highlight fragment binding",
    )
    vertex_binding = single(
        [
            item
            for item in records
            if item.get("kind") in {"buffer", "bufferOffset"}
            and item.get("stage") == "vertex"
            and item.get("index") == 1
        ],
        "final-highlight vertex binding",
    )
    fragment_snapshot = snapshot_at(
        snapshots,
        sequence_number=integer(
            fragment_binding.get("sequence"), "final-highlight fragment sequence"
        ),
        stage="fragment",
        index=1,
        label=FINAL_HIGHLIGHT_PIPELINE,
    )
    vertex_snapshot = snapshot_at(
        snapshots,
        sequence_number=integer(
            vertex_binding.get("sequence"), "final-highlight vertex sequence"
        ),
        stage="vertex",
        index=1,
        label=FINAL_HIGHLIGHT_PIPELINE,
    )
    index_snapshot = snapshot_at(
        snapshots,
        sequence_number=integer(draw.get("sequence"), "final-highlight draw sequence"),
        stage="index",
        index=-1,
        label=FINAL_HIGHLIGHT_PIPELINE,
    )
    index_raw = payload(index_snapshot)
    if len(index_raw) < 2 * index_count:
        raise ValueError("final-highlight index payload is truncated")
    indices = struct.unpack_from(f"<{index_count}H", index_raw)
    if indices not in {FINAL_QUAD_INDICES, FINAL_BORDER_INDICES}:
        raise ValueError("final-highlight index topology is not in the retained corpus")
    vertex_count = max(indices) + 1
    vertex_raw = payload(vertex_snapshot)
    fragment_raw = payload(fragment_snapshot)
    if len(vertex_raw) < vertex_count * VERTEX_STRIDE or len(fragment_raw) < 248:
        raise ValueError("final-highlight retained buffer is truncated")
    return {
        "indexCount": index_count,
        "vertexCount": vertex_count,
        "fragmentPrefix": fragment_raw[:248],
        "vertices": vertex_raw[: vertex_count * VERTEX_STRIDE],
        "indices": index_raw[: 2 * index_count],
    }


def add_float_metric(
    metrics: dict[str, Counter[str]],
    name: str,
    observed: Sequence[float],
    predicted: Sequence[float],
) -> None:
    if len(observed) != len(predicted):
        raise ValueError(f"{name} component count differs")
    metric = metrics.setdefault(name, Counter())
    metric["componentCount"] += len(observed)
    metric["mismatchedComponents"] += sum(
        float32_bits(left) != float32_bits(right)
        for left, right in zip(observed, predicted, strict=True)
    )


def add_float64_metric(
    metrics: dict[str, Counter[str]],
    name: str,
    observed: Sequence[float],
    predicted: Sequence[float],
) -> None:
    if len(observed) != len(predicted):
        raise ValueError(f"{name} component count differs")
    metric = metrics.setdefault(name, Counter())
    metric["componentCount"] += len(observed)
    metric["mismatchedComponents"] += sum(
        float64_bits(left) != float64_bits(right)
        for left, right in zip(observed, predicted, strict=True)
    )


def add_integer_metric(
    metrics: dict[str, Counter[str]],
    name: str,
    observed: Sequence[int],
    predicted: Sequence[int],
) -> None:
    if len(observed) != len(predicted):
        raise ValueError(f"{name} component count differs")
    metric = metrics.setdefault(name, Counter())
    metric["componentCount"] += len(observed)
    metric["mismatchedComponents"] += sum(
        left != right for left, right in zip(observed, predicted, strict=True)
    )


def metric_result(counter: Counter[str]) -> dict[str, Any]:
    component_count = counter["componentCount"]
    mismatches = counter["mismatchedComponents"]
    return {
        "componentCount": component_count,
        "mismatchedComponents": mismatches,
        "exact": component_count > 0 and mismatches == 0,
    }


def validate_envelope(
    timeline: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    geometry = mapping(timeline.get("geometry"), "timeline geometry")
    record_count = integer(expected.get("records"), "expected record count")
    if (
        timeline.get("schemaVersion") != TIMELINE_SCHEMA_VERSION
        or timeline.get("material") != expected.get("material")
        or timeline.get("appearance") != expected.get("appearance")
        or timeline.get("direction") != expected.get("direction")
        or geometry.get("name") != expected.get("geometry")
        or timeline.get("windowBackingScaleFactor") != 2
        or timeline.get("sampleCount") != 33
        or timeline.get("failedSamples") != 0
        or timeline.get("expectedWindowPixels") != [2048, 2048]
        or timeline.get("captureBackend") != "CGWindowListCreateImage"
    ):
        raise ValueError("timeline envelope differs")
    uniforms = mapping(
        timeline.get("dynamicBackgroundUniforms"), "dynamic background uniforms"
    )
    records = [
        mapping(value, "dynamic record")
        for value in sequence(uniforms.get("records"), "dynamic records")
    ]
    expected_indices = list(range(1, record_count + 1))
    if (
        uniforms.get("schemaVersion") != DYNAMIC_UNIFORM_SCHEMA_VERSION
        or uniforms.get("evidenceMode") != "allocation-metadata-v1"
        or uniforms.get("method") != EXPECTED_CAPTURE_METHOD
        or uniforms.get("executed") is not True
        or uniforms.get("executedSampleCount") != record_count
        or uniforms.get("sampleCount") != record_count
        or uniforms.get("sampleIndices") != expected_indices
        or uniforms.get("carrierCriticalPaths") != EXPECTED_CRITICAL_PATHS
        or uniforms.get("transitionForegroundFilterCaptured") is not True
        or uniforms.get("transitionForegroundFilterReplayedOnCarrier") is not False
        or [record.get("sampleIndex") for record in records] != expected_indices
    ):
        raise ValueError("dynamic timeline envelope differs")
    return records


def analyze(artifact_root: Path) -> JsonObject:
    metrics: dict[str, Counter[str]] = {}
    producer_fragments: Counter[str] = Counter()
    producer_vertex_counts: Counter[int] = Counter()
    destination_mip_counts: Counter[int] = Counter()
    final_topologies: Counter[str] = Counter()
    foreground_filter_states = 0
    foreground_endpoint_states = 0
    input_records: list[JsonObject] = []
    matrix_results: list[JsonObject] = []
    actual_main_digest = hashlib.sha256()
    predicted_main_digest = hashlib.sha256()
    actual_shadow_digest = hashlib.sha256()
    predicted_shadow_digest = hashlib.sha256()
    actual_uv_digest = hashlib.sha256()
    predicted_uv_digest = hashlib.sha256()
    actual_producer_crop_digest = hashlib.sha256()
    predicted_producer_crop_digest = hashlib.sha256()
    final_fragment_digest = hashlib.sha256()
    final_vertex_digest = hashlib.sha256()
    final_index_digest = hashlib.sha256()
    state_count = 0

    for filename, expected in EXPECTED_INPUTS.items():
        path = artifact_root / filename
        if not path.is_file():
            raise ValueError(f"missing pinned transition timeline: {path}")
        actual_sha256 = sha256_file(path)
        if actual_sha256 != expected["sha256"]:
            raise ValueError(f"transition timeline SHA-256 differs: {filename}")
        timeline = mapping(
            json.loads(path.read_text(encoding="utf-8")), "transition timeline"
        )
        geometry = mapping(timeline.get("geometry"), "timeline geometry")
        records = validate_envelope(timeline, expected)
        matrix_state_count = 0
        matrix_final_topologies: Counter[str] = Counter()

        for record in records:
            remaining = finite(record.get("remaining"), "remaining")
            if not 0.0 < remaining <= 1.0 or remaining != float32(remaining):
                raise ValueError("dynamic remaining value differs from binary32")
            scale, layer_state_count = selected.allocation.captured_scale(record)
            expected_layer_state_count = 13 if remaining == 1.0 else 16
            if layer_state_count != expected_layer_state_count:
                raise ValueError("captured layer-state count differs")

            states = layer_states(record)
            carrier = mapping(states.get((1,)), "carrier layer state")
            element = mapping(
                states.get((1, 0, 1, 0, 0, 0, 0)),
                "background SDF element layer state",
            )
            if (
                carrier.get("class") != "CALayer"
                or element.get("class") != "CASDFElementLayer"
            ):
                raise ValueError("dynamic geometry layer classes differ")
            predicted_layer_state = expected_dynamic_layer_state(geometry, remaining)
            add_float64_metric(
                metrics,
                "dynamicCarrierBounds",
                vector(carrier.get("bounds"), "carrier bounds", 4),
                predicted_layer_state["carrierBounds"],
            )
            add_float64_metric(
                metrics,
                "dynamicCarrierPosition",
                vector(carrier.get("position"), "carrier position", 2),
                predicted_layer_state["carrierPosition"],
            )
            add_float64_metric(
                metrics,
                "dynamicElementBounds",
                vector(element.get("bounds"), "element bounds", 4),
                predicted_layer_state["elementBounds"],
            )
            add_float64_metric(
                metrics,
                "dynamicElementPosition",
                vector(element.get("position"), "element position", 2),
                predicted_layer_state["elementPosition"],
            )

            predicted_scale = expected_backdrop_scale(
                str(expected["material"]), remaining
            )
            add_float_metric(metrics, "backdropScale", [scale], [predicted_scale])

            observed = selected.observed_policy(record, scale=scale)
            mesh = mapping(observed.get("producerMesh"), "producer mesh")
            fragment = mesh.get("fragmentFunction")
            if not isinstance(fragment, str) or not fragment:
                raise ValueError("producer fragment identity is missing")
            producer_fragments[fragment] += 1
            producer_vertex_counts[
                integer(mesh.get("vertexCount"), "producer vertex count")
            ] += 1

            crop_origin = [
                integer(value, "producer crop origin")
                for value in sequence(observed.get("cropOrigin"), "crop origin")
            ]
            clamp = [
                integer(value, "copy clamp")
                for value in sequence(
                    observed.get("textureCoordinateClamp"), "copy clamp"
                )
            ]
            copy_offset = [
                integer(value, "copy offset")
                for value in sequence(observed.get("copyOffset"), "copy offset")
            ]
            effective_origin = [
                integer(value, "effective origin")
                for value in sequence(
                    observed.get("effectiveOrigin"), "effective origin"
                )
            ]
            producer_extent = [
                integer(value, "producer extent")
                for value in sequence(observed.get("producerExtent"), "producer extent")
            ]
            destination_extent = [
                integer(value, "destination extent")
                for value in sequence(
                    observed.get("destinationExtent"), "destination extent"
                )
            ]
            if len(crop_origin) != 2 or len(clamp) != 4 or len(copy_offset) != 2:
                raise ValueError("copy-base geometry vector length differs")
            active_extent = [clamp[2] + 1, clamp[3] + 1]
            predicted_producer = expected_producer_crop(
                geometry,
                material=str(expected["material"]),
                carrier_position=predicted_layer_state["carrierPosition"],
                backdrop_scale=predicted_scale,
            )
            predicted_crop_origin = list(predicted_producer["cropOrigin"])
            predicted_active_extent = list(predicted_producer["activeExtent"])
            predicted_storage_extent = list(predicted_producer["storageExtent"])
            add_integer_metric(
                metrics,
                "producerCropOrigin",
                crop_origin,
                predicted_crop_origin,
            )
            add_integer_metric(
                metrics,
                "producerActiveExtent",
                active_extent,
                predicted_active_extent,
            )
            add_integer_metric(
                metrics,
                "producerStorageExtent",
                producer_extent,
                predicted_storage_extent,
            )
            actual_producer_crop_digest.update(
                struct.pack("<4i", *crop_origin, *active_extent)
            )
            predicted_producer_crop_digest.update(
                struct.pack("<4i", *predicted_crop_origin, *predicted_active_extent)
            )
            add_integer_metric(
                metrics,
                "producerAllocationFromActiveCrop",
                producer_extent,
                [selected.align_up(value) for value in active_extent],
            )
            filter_record = mapping(record.get("filter"), "background filter")
            inputs = mapping(filter_record.get("inputValues"), "background inputs")
            radius1 = selected.predict_radius1(
                blur_radius=finite(inputs.get("inputBlurRadius"), "blur radius"),
                bleed_blur_radius=finite(
                    inputs.get("inputBleedBlurRadius"), "bleed blur radius"
                ),
                backdrop_scale=scale,
            )
            mip = selected.predict_mip_policy(
                radius1=radius1,
                source_extent=active_extent,
            )
            helper_bounds = selected.predict_integer_bounds(
                bounds=[*crop_origin, *active_extent],
                radius1=radius1,
                alignment_scale=integer(
                    mip.get("alignmentScale"), "selected-region alignment scale"
                ),
            )
            add_integer_metric(
                metrics,
                "selectedRegionOrigin",
                effective_origin,
                helper_bounds[:2],
            )
            add_integer_metric(
                metrics,
                "selectedRegionAllocation",
                destination_extent,
                [selected.align_up(value) for value in helper_bounds[2:]],
            )
            add_integer_metric(
                metrics,
                "copyBaseOriginComposition",
                effective_origin,
                [
                    crop_origin[0] + copy_offset[0],
                    crop_origin[1] + copy_offset[1],
                ],
            )
            observed_mips = selected.copy_destination_mipmap_count(record)
            destination_mip_counts[observed_mips] += 1
            add_integer_metric(
                metrics,
                "destinationMipCount",
                [observed_mips],
                [integer(mip.get("levelCount"), "predicted mip count")],
            )

            main, shadow = background_geometry(record)
            predicted_main = expected_main_vertices(record)
            for observed_vertex, predicted_vertex in zip(
                main, predicted_main, strict=True
            ):
                add_float_metric(
                    metrics,
                    "mainLayerStateGeometry",
                    [
                        observed_vertex[0],
                        observed_vertex[1],
                        observed_vertex[4],
                        observed_vertex[5],
                    ],
                    [
                        predicted_vertex[0],
                        predicted_vertex[1],
                        predicted_vertex[4],
                        predicted_vertex[5],
                    ],
                )
                add_float_metric(
                    metrics,
                    "mainHomogeneousComponents",
                    [observed_vertex[2], observed_vertex[3]],
                    [0.0, 1.0],
                )
                actual_main_digest.update(struct.pack("<6f", *observed_vertex[:6]))
                predicted_main_digest.update(struct.pack("<6f", *predicted_vertex[:6]))

            predicted_shadow = expected_shadow_vertices(
                record,
                material=str(expected["material"]),
            )
            for observed_vertex, predicted_vertex in zip(
                shadow, predicted_shadow, strict=True
            ):
                add_float_metric(
                    metrics,
                    "shadowLayerStateGeometry",
                    [
                        observed_vertex[0],
                        observed_vertex[1],
                        observed_vertex[4],
                        observed_vertex[5],
                    ],
                    [
                        predicted_vertex[0],
                        predicted_vertex[1],
                        predicted_vertex[4],
                        predicted_vertex[5],
                    ],
                )
                add_float_metric(
                    metrics,
                    "shadowHomogeneousComponents",
                    [observed_vertex[2], observed_vertex[3]],
                    [0.0, 1.0],
                )
                actual_shadow_digest.update(struct.pack("<6f", *observed_vertex[:6]))
                predicted_shadow_digest.update(
                    struct.pack("<6f", *predicted_vertex[:6])
                )

            for vertex in [*main, *shadow]:
                predicted_uv = [
                    source_coordinate(
                        vertex[axis],
                        backdrop_scale=scale,
                        crop_origin=crop_origin[axis],
                        copy_offset=copy_offset[axis],
                        allocation_extent=destination_extent[axis],
                    )
                    for axis in range(2)
                ]
                observed_uv = [vertex[6], vertex[7]]
                add_float_metric(
                    metrics, "backgroundSourceCoordinates", observed_uv, predicted_uv
                )
                actual_uv_digest.update(struct.pack("<2f", *observed_uv))
                predicted_uv_digest.update(struct.pack("<2f", *predicted_uv))

            foreground = mapping(record.get("foregroundFilter"), "foreground filter")
            if "inputValues" in foreground:
                foreground_filter_states += 1
            elif foreground.get("filterPresent") is False:
                foreground_endpoint_states += 1
            else:
                raise ValueError("foreground-filter retained state differs")

            final = final_highlight_inventory(record)
            topology = f"{final['indexCount']}-indices/{final['vertexCount']}-vertices"
            final_topologies[topology] += 1
            matrix_final_topologies[topology] += 1
            final_fragment_digest.update(final["fragmentPrefix"])
            final_vertex_digest.update(final["vertices"])
            final_index_digest.update(final["indices"])
            matrix_state_count += 1
            state_count += 1

        input_records.append(
            {
                "filename": filename,
                "sha256": actual_sha256,
                "bytes": path.stat().st_size,
            }
        )
        matrix_results.append(
            {
                "material": expected["material"],
                "appearance": expected["appearance"],
                "direction": expected["direction"],
                "geometry": expected["geometry"],
                "stateCount": matrix_state_count,
                "finalHighlightTopologies": dict(
                    sorted(matrix_final_topologies.items())
                ),
            }
        )

    metric_results = {
        name: metric_result(counter) for name, counter in sorted(metrics.items())
    }
    if state_count != 252 or not all(
        metric["exact"] for metric in metric_results.values()
    ):
        raise ValueError("transition geometry corpus gate did not pass exactly")
    if actual_main_digest.digest() != predicted_main_digest.digest():
        raise ValueError("main geometry streams differ")
    if actual_shadow_digest.digest() != predicted_shadow_digest.digest():
        raise ValueError("shadow geometry streams differ")
    if actual_uv_digest.digest() != predicted_uv_digest.digest():
        raise ValueError("background source-coordinate streams differ")
    if actual_producer_crop_digest.digest() != predicted_producer_crop_digest.digest():
        raise ValueError("producer crop streams differ")
    if foreground_filter_states != 248 or foreground_endpoint_states != 4:
        raise ValueError("foreground-filter branch counts differ")

    return {
        "transitionGeometryCorpusLocalMacOS2661ResultSchemaVersion": (
            RESULT_SCHEMA_VERSION
        ),
        "classification": (
            "retrospective, hash-pinned current-build transition corpus gate; "
            "no pixel, crop, copy, or final output was used to select a state"
        ),
        "status": "passed",
        "inputCount": len(input_records),
        "stateCount": state_count,
        "matrix": matrix_results,
        "inputs": input_records,
        "closedLaws": {
            "backdropScale": (
                "binary32(1 - 0.5*k) for clear; binary32(1 - 0.75*k) "
                "for regular, where k is the captured binary32 remaining value"
            ),
            "selectedRegion": (
                "authenticated variable-blur helper radius/mip/integer-bounds "
                "replay composed with producer crop, copy-base offset, 64-pixel "
                "allocation, and destination mip count"
            ),
            "producerCrop": (
                "full requested circle at the independently constructed carrier "
                "position, expanded by zero for clear or binary32(0.35*diameter) "
                "for regular, clipped in window space, scaled by the predicted "
                "material backdrop scale, then X-lower floor-plus-one and "
                "Metal-Y-lower ceil with floor upper-exclusive edges"
            ),
            "mainGeometry": (
                "independently constructed dynamic carrier and CASDFElementLayer "
                "state transformed to six vertices in Apple's binary64 grouping, "
                "then binary32"
            ),
            "dynamicLayerState": (
                "binary32 remaining/progress, centered interpolated scale, "
                "centered reciprocal sqrt((D+16)/D) pair, CoreGraphics fused "
                "multiply plus separate translation add, observed non-half "
                "nearest-integer carrier snap, and staged "
                "root-lower-minus-carrier-position subtraction"
            ),
            "shadowGeometry": (
                "captured public layer state plus material shadow margin transformed "
                "to a four-by-four grid; outer bounds round to binary32 before "
                "binary64 deltas from the unrounded inner bounds adjust binary32 "
                "SDF coordinates"
            ),
            "backgroundSourceCoordinates": (
                "binary32(binary32(binary64(position)*binary64(scale) - cropOrigin "
                "- copyOffset) * binary32(1/allocationExtent))"
            ),
        },
        "metrics": metric_results,
        "streamSHA256": {
            "mainObserved": actual_main_digest.hexdigest(),
            "mainPredicted": predicted_main_digest.hexdigest(),
            "shadowObserved": actual_shadow_digest.hexdigest(),
            "shadowPredicted": predicted_shadow_digest.hexdigest(),
            "sourceCoordinatesObserved": actual_uv_digest.hexdigest(),
            "sourceCoordinatesPredicted": predicted_uv_digest.hexdigest(),
            "producerCropObserved": actual_producer_crop_digest.hexdigest(),
            "producerCropPredicted": predicted_producer_crop_digest.hexdigest(),
        },
        "producerBranchInventory": {
            "fragmentFunctions": dict(sorted(producer_fragments.items())),
            "vertexCounts": {
                str(key): value for key, value in sorted(producer_vertex_counts.items())
            },
            "destinationMipCounts": {
                str(key): value for key, value in sorted(destination_mip_counts.items())
            },
        },
        "retainedTransitionForeground": {
            "inputFilterStateCount": foreground_filter_states,
            "endpointWithoutFilterStateCount": foreground_endpoint_states,
            "finalHighlightStateCount": state_count,
            "finalHighlightTopologies": dict(sorted(final_topologies.items())),
            "fragment248BytePrefixStreamSHA256": final_fragment_digest.hexdigest(),
            "vertexStreamSHA256": final_vertex_digest.hexdigest(),
            "indexStreamSHA256": final_index_digest.hexdigest(),
            "constructionLawExact": False,
        },
        "remainingAlgorithmBoundaries": [
            "transition foreground and final-highlight production",
        ],
        "prospectiveUnseenGeometryTransferPassed": False,
        "physicalRetinaColorCompositorTransferPassed": False,
        "independentFreshWalleZeroByteFramePassed": False,
        "liquidGlassParityEstablished": False,
        "productionShaderChanged": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = analyze(arguments.artifact_root)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
