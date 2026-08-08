#!/usr/bin/env python3
"""Close current-circle alternate topology and general-transform clipping."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
import ctypes
import hashlib
import json
from pathlib import Path
import struct
from typing import Any

import analyze_combined_transition_geometry_holdout_falsification as opened
import analyze_transition_geometry_corpus_local_macos_26_6_1 as model
import validate_variable_blur_selected_region_origin as selected


type JsonObject = dict[str, Any]
type Vertex = tuple[float, ...]

RESULT_SCHEMA_VERSION = 1
TARGET_LAYER_PATH = (1, 0, 1, 0, 0, 0, 0)
OFFCENTER_RESULT_SHA256 = (
    "d396ee0f72cda4c8e787ee8cd3be9e9cde567a8c24a4a141fa4e84c34acbcfad"
)
OPENED_HOLDOUT_RESULT_SHA256 = (
    "a70ce8c2880def7df27f7dc298487676a3e083d45feb1cadad33f86d21a6555d"
)
SOURCE_INTERVENTION_RESULT_SHA256 = (
    "5f9525ab234c90ff7f7d0b3446726e90461b9bd0611cc523a938e7ad5d8a5748"
)
DIAGNOSTIC_SHA256 = {
    "emit-one-exact-7432ffa-live-trace.txt": (
        "1cdc810dec30f95494b1a8bd38cd4f112ccb34ff34a68517746ae307207fc5db"
    ),
    "emit-one-exact-7432ffa-transition-timeline.json": (
        "e5f36f5b8e40bb85ae51f362a4a806898e93749835f4d39039ee93e598cf7d07"
    ),
    "emit-one-part-helper-disassembly.txt": (
        "8109f32d9d8aa3f226a57c635c22ba37156ffaf427de165e4e648177cf67d758"
    ),
    "emit-one-part-rect-disassembly.txt": (
        "7c9fd60a2b45f8de2673d5ef84c8e625baf555049e086d26d092b837590ec538"
    ),
    "emit-sdf-bounds-disassembly.txt": (
        "4faa520cce7b378c70f08812777115300bb4a3a93ca720e3cda941c4f0d7108a"
    ),
}
SHADOW_SPLIT_INDICES = (
    2,
    3,
    9,
    9,
    8,
    2,
    26,
    27,
    33,
    33,
    32,
    26,
    12,
    13,
    19,
    19,
    18,
    12,
    16,
    17,
    23,
    23,
    22,
    16,
    0,
    1,
    7,
    7,
    6,
    0,
    1,
    2,
    8,
    8,
    7,
    1,
    6,
    7,
    13,
    13,
    12,
    6,
    4,
    5,
    11,
    11,
    10,
    4,
    3,
    4,
    10,
    10,
    9,
    3,
    10,
    11,
    17,
    17,
    16,
    10,
    28,
    29,
    35,
    35,
    34,
    28,
    27,
    28,
    34,
    34,
    33,
    27,
    22,
    23,
    29,
    29,
    28,
    22,
    24,
    25,
    31,
    31,
    30,
    24,
    25,
    26,
    32,
    32,
    31,
    25,
    18,
    19,
    25,
    25,
    24,
    18,
)

_LIBC = ctypes.CDLL(None)
_LIBC.fmaf.argtypes = (ctypes.c_float, ctypes.c_float, ctypes.c_float)
_LIBC.fmaf.restype = ctypes.c_float


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def fmaf32(multiplier: float, multiplicand: float, addend: float) -> float:
    return float(_LIBC.fmaf(multiplier, multiplicand, addend))


def clip_axis(
    low_position: float,
    high_position: float,
    low_value: float,
    high_value: float,
    clip_low: int,
    clip_high: int,
) -> tuple[float, float, float, float]:
    """Replay ClippedArray's binary64 fraction and binary32 FMA sequence."""
    if low_position <= clip_low:
        fraction = model.float32(
            (float(clip_low) - low_position) / (high_position - low_position)
        )
        low_value = fmaf32(model.float32(high_value - low_value), fraction, low_value)
        low_position = float(clip_low)
    if clip_high <= high_position:
        fraction = model.float32(
            (high_position - float(clip_high)) / (high_position - low_position)
        )
        high_value = fmaf32(model.float32(low_value - high_value), fraction, high_value)
        high_position = float(clip_high)
    return (
        model.float32(low_position),
        model.float32(high_position),
        low_value,
        high_value,
    )


def layer_axes(
    record: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], float, float]:
    states = model.layer_states(record)
    root = states[()]
    carrier = states[(1,)]
    element = states[TARGET_LAYER_PATH]
    origin_x = carrier["position"][0] + element["position"][0]
    origin_y = root["bounds"][3] - carrier["position"][1] - element["position"][1]
    return root, carrier, element, origin_x, origin_y


def final_axes(
    record: Mapping[str, Any],
) -> tuple[
    bool,
    tuple[float, ...],
    tuple[float, ...],
    tuple[float, ...],
    tuple[float, ...],
]:
    root, _, element, origin_x, origin_y = layer_axes(record)
    width, height = element["bounds"][2:4]
    half_x = model.float32(width / 2.0)
    half_y = model.float32(height / 2.0)
    radius_x = model.float32(model.float32(half_x + 9.0) - 9.0)
    radius_y = model.float32(model.float32(half_y + 9.0) - 9.0)
    radius = min(radius_x, radius_y)
    outer_x = model.float32(radius_x + 9.0)
    outer_y = model.float32(radius_y + 9.0)
    border = radius_x != half_x or radius_y != half_y or radius_x != radius_y
    if border:
        positions_x = (
            model.float32(origin_x - 9.0),
            model.float32(origin_x + radius),
            model.float32((origin_x + width) - radius),
            model.float32((origin_x + width) + 9.0),
        )
        positions_y = (
            model.float32(origin_y + 9.0),
            model.float32(origin_y - radius),
            model.float32((origin_y - height) + radius),
            model.float32((origin_y - height) - 9.0),
        )
        coordinates_x = (
            -outer_x,
            model.float32(-radius_x + radius),
            model.float32(radius_x - radius),
            outer_x,
        )
        coordinates_y = (
            -outer_y,
            model.float32(-radius_y + radius),
            model.float32(radius_y - radius),
            outer_y,
        )
        return border, positions_x, positions_y, coordinates_x, coordinates_y

    local_lower = -9.0
    local_upper_x = local_lower + (width + 18.0)
    local_upper_y = local_lower + (height + 18.0)
    raw_left = origin_x + local_lower
    raw_right = origin_x + local_upper_x
    raw_top = origin_y - local_lower
    raw_bottom = origin_y - local_upper_y
    left, right, left_coordinate, right_coordinate = clip_axis(
        raw_left,
        raw_right,
        -outer_x,
        outer_x,
        0,
        int(root["bounds"][2]),
    )
    bottom, top, bottom_coordinate, top_coordinate = clip_axis(
        raw_bottom,
        raw_top,
        outer_y,
        -outer_y,
        0,
        int(root["bounds"][3]),
    )
    return (
        border,
        (left, right),
        (top, bottom),
        (left_coordinate, right_coordinate),
        (top_coordinate, bottom_coordinate),
    )


def source_coordinates(
    record: Mapping[str, Any], material: str
) -> list[tuple[float, float]]:
    _, _, element, origin_x, origin_y = layer_axes(record)
    width, height = element["bounds"][2:4]
    half_x = model.float32(width / 2.0)
    half_y = model.float32(height / 2.0)
    shape_radius = min(half_x, half_y)
    remaining = model.float32(record["remaining"])
    margin = 0.0 if material == "clear" else model.float32(48.0 * remaining)
    top_margin = max(margin - 8.0, 0.0)
    extended_width = model.float32(width + margin)
    extended_height = model.float32((height + margin) + 8.0)
    if half_x != half_y:
        positions_x = (
            model.float32(origin_x - margin),
            model.float32(origin_x),
            model.float32(origin_x + shape_radius),
            model.float32((origin_x + width) - shape_radius),
            model.float32(origin_x + width),
            model.float32(origin_x + extended_width),
        )
        positions_y = (
            model.float32(origin_y + top_margin),
            model.float32(origin_y),
            model.float32(origin_y - shape_radius),
            model.float32((origin_y - height) + shape_radius),
            model.float32(origin_y - height),
            model.float32(origin_y - extended_height),
        )
    else:
        positions_x = (
            model.float32(origin_x - margin),
            model.float32(origin_x),
            model.float32(origin_x + width),
            model.float32(origin_x + extended_width),
        )
        positions_y = (
            model.float32(origin_y + top_margin),
            model.float32(origin_y),
            model.float32(origin_y - height),
            model.float32(origin_y - extended_height),
        )
    scale, _ = selected.allocation.captured_scale(record)
    policy = selected.observed_policy(record, scale=scale)
    return [
        (
            model.source_coordinate(
                x,
                backdrop_scale=scale,
                crop_origin=policy["cropOrigin"][0],
                copy_offset=policy["copyOffset"][0],
                allocation_extent=policy["destinationExtent"][0],
            ),
            model.source_coordinate(
                y,
                backdrop_scale=scale,
                crop_origin=policy["cropOrigin"][1],
                copy_offset=policy["copyOffset"][1],
                allocation_extent=policy["destinationExtent"][1],
            ),
        )
        for y in positions_y
        for x in positions_x
    ]


def predict_final(
    record: Mapping[str, Any], material: str
) -> tuple[list[Vertex], tuple[int, ...]]:
    border, positions_x, positions_y, coordinates_x, coordinates_y = final_axes(record)
    sources = source_coordinates(record, material)
    if material == "regular" and record["remaining"] == 1.0:
        sources[:4] = [
            (-1.5, -1.5),
            (0.0, -1.5),
            (0.0, -1.5),
            (1.5, -1.5),
        ]
    if border:
        vertices = [
            (
                x,
                y,
                0.0,
                1.0,
                coordinates_x[x_index],
                coordinates_y[y_index],
                *sources[index],
            )
            for index, (y_index, y, x_index, x) in enumerate(
                (y_index, y, x_index, x)
                for y_index, y in enumerate(positions_y)
                for x_index, x in enumerate(positions_x)
            )
        ]
        return vertices, model.FINAL_BORDER_INDICES
    vertices = [
        (
            positions_x[0],
            positions_y[1],
            0.0,
            1.0,
            coordinates_x[0],
            coordinates_y[1],
            *sources[0],
        ),
        (
            positions_x[1],
            positions_y[1],
            0.0,
            1.0,
            coordinates_x[1],
            coordinates_y[1],
            *sources[1],
        ),
        (
            positions_x[1],
            positions_y[0],
            0.0,
            1.0,
            coordinates_x[1],
            coordinates_y[0],
            *sources[2],
        ),
        (
            positions_x[0],
            positions_y[0],
            0.0,
            1.0,
            coordinates_x[0],
            coordinates_y[0],
            *sources[3],
        ),
    ]
    return vertices, model.FINAL_QUAD_INDICES


def current_background_pipeline(record: Mapping[str, Any]) -> str | None:
    labels = opened.pipeline_tokens(record)
    if opened.CURRENT_CLEAR_BACKGROUND in labels:
        return f"com.apple.coreanimation.{opened.CURRENT_CLEAR_BACKGROUND}"
    if opened.CURRENT_REGULAR_BACKGROUND in labels:
        return f"com.apple.coreanimation.{opened.CURRENT_REGULAR_BACKGROUND}"
    return None


def current_background_vertex_count(record: Mapping[str, Any], pipeline: str) -> int:
    records = record["render"]["metalUniformProbe"]["records"]
    candidates = [
        int(item["vertexCount"])
        for item in records
        if model.pipeline_label(item) == pipeline
        and item.get("kind") == "drawPrimitivesInstanced"
        and item.get("vertexCount") in {6, 24}
    ]
    require(len(candidates) == 1, "current background main topology differs")
    return candidates[0]


def background_split_predicate(record: Mapping[str, Any]) -> bool:
    _, _, element, _, _ = layer_axes(record)
    width, height = element["bounds"][2:4]
    return model.float32(width / 2.0) != model.float32(height / 2.0)


def snapshot_payload(
    record: Mapping[str, Any],
    *,
    pipeline: str,
    sequence_number: int,
    stage: str,
    index: int,
) -> bytes:
    snapshots = record["render"]["metalBufferSnapshots"]["snapshots"]
    snapshot = model.snapshot_at(
        snapshots,
        sequence_number=sequence_number,
        stage=stage,
        index=index,
        label=pipeline,
    )
    return model.payload(snapshot)


def observed_split_background(
    record: Mapping[str, Any], pipeline: str
) -> tuple[list[Vertex], list[Vertex], list[Vertex], tuple[int, ...]]:
    records = [
        item
        for item in record["render"]["metalUniformProbe"]["records"]
        if model.pipeline_label(item) == pipeline
    ]
    draws = [item for item in records if str(item.get("kind", "")).startswith("draw")]
    bindings = [
        item
        for item in records
        if item.get("stage") == "vertex" and item.get("index") == 1
    ]
    require(len(draws) == 3 and len(bindings) == 3, "split draw inventory differs")
    main_draw, shadow_draw, seam_draw = draws
    main_binding, shadow_binding, seam_binding = bindings
    require(
        main_draw.get("vertexCount") == 24
        and shadow_draw.get("indexCount") == 96
        and seam_draw.get("vertexCount") == 30,
        "split draw topology differs",
    )

    def decode(binding: Mapping[str, Any], count: int) -> list[Vertex]:
        raw = snapshot_payload(
            record,
            pipeline=pipeline,
            sequence_number=int(binding["sequence"]),
            stage="vertex",
            index=1,
        )
        return [
            struct.unpack_from("<8f", raw, index * model.VERTEX_STRIDE)
            for index in range(count)
        ]

    index_raw = snapshot_payload(
        record,
        pipeline=pipeline,
        sequence_number=int(shadow_draw["sequence"]),
        stage="index",
        index=-1,
    )
    return (
        decode(main_binding, 24),
        decode(shadow_binding, 36),
        decode(seam_binding, 30),
        struct.unpack_from("<96H", index_raw),
    )


def quad_indices(x0: int, x1: int, y0: int, y1: int) -> list[tuple[int, int]]:
    return [
        (x0, y0),
        (x1, y0),
        (x1, y1),
        (x1, y1),
        (x0, y1),
        (x0, y0),
    ]


def predicted_split_background(
    record: Mapping[str, Any], material: str
) -> tuple[list[Vertex], list[Vertex], list[Vertex], tuple[int, ...]]:
    _, _, element, origin_x, origin_y = layer_axes(record)
    width, height = element["bounds"][2:4]
    half_x = model.float32(width / 2.0)
    half_y = model.float32(height / 2.0)
    radius = min(half_x, half_y)
    inner_x = (
        model.float32(origin_x),
        model.float32(origin_x + radius),
        model.float32((origin_x + width) - radius),
        model.float32(origin_x + width),
    )
    inner_y = (
        model.float32(origin_y),
        model.float32(origin_y - radius),
        model.float32((origin_y - height) + radius),
        model.float32(origin_y - height),
    )
    coordinate_x = (
        -half_x,
        model.float32(-half_x + radius),
        model.float32(half_x - radius),
        half_x,
    )
    coordinate_y = (
        -half_y,
        model.float32(-half_y + radius),
        model.float32(half_y - radius),
        half_y,
    )
    remaining = model.float32(record["remaining"])
    margin = 0.0 if material == "clear" else model.float32(48.0 * remaining)
    top_margin = max(margin - 8.0, 0.0)
    extended_width = model.float32(width + margin)
    extended_height = model.float32((height + margin) + 8.0)
    shadow_x = (
        model.float32(origin_x - margin),
        *inner_x,
        model.float32(origin_x + extended_width),
    )
    shadow_y = (
        model.float32(origin_y + top_margin),
        *inner_y,
        model.float32(origin_y - extended_height),
    )
    shadow_coordinate_x = (
        model.float32(float(-half_x) + float(model.float32(-margin))),
        *coordinate_x,
        model.float32(float(half_x) + (float(extended_width) - width)),
    )
    shadow_coordinate_y = (
        model.float32(float(-half_y) + float(model.float32(-top_margin))),
        *coordinate_y,
        model.float32(float(half_y) + (float(extended_height) - height)),
    )
    scale, _ = selected.allocation.captured_scale(record)
    policy = selected.observed_policy(record, scale=scale)

    def vertex(x_index: int, y_index: int, *, shadow: bool = False) -> Vertex:
        positions_x = shadow_x if shadow else inner_x
        positions_y = shadow_y if shadow else inner_y
        coordinates_x = shadow_coordinate_x if shadow else coordinate_x
        coordinates_y = shadow_coordinate_y if shadow else coordinate_y
        x = positions_x[x_index]
        y = positions_y[y_index]
        return (
            x,
            y,
            0.0,
            1.0,
            coordinates_x[x_index],
            coordinates_y[y_index],
            model.source_coordinate(
                x,
                backdrop_scale=scale,
                crop_origin=policy["cropOrigin"][0],
                copy_offset=policy["copyOffset"][0],
                allocation_extent=policy["destinationExtent"][0],
            ),
            model.source_coordinate(
                y,
                backdrop_scale=scale,
                crop_origin=policy["cropOrigin"][1],
                copy_offset=policy["copyOffset"][1],
                allocation_extent=policy["destinationExtent"][1],
            ),
        )

    main_cells = ((0, 1, 0, 1), (2, 3, 0, 1), (2, 3, 2, 3), (0, 1, 2, 3))
    main = [
        vertex(x, y)
        for x0, x1, y0, y1 in main_cells
        for x, y in quad_indices(x0, x1, y0, y1)
    ]
    shadow = [vertex(x, y, shadow=True) for y in range(6) for x in range(6)]
    seam_cells = (
        (1, 2, 1, 2),
        (1, 2, 0, 1),
        (1, 2, 2, 3),
        (0, 1, 1, 2),
        (2, 3, 1, 2),
    )
    seam = [
        vertex(x, y)
        for x0, x1, y0, y1 in seam_cells
        for x, y in quad_indices(x0, x1, y0, y1)
    ]
    return main, shadow, seam, SHADOW_SPLIT_INDICES


def compare_float_values(
    counter: Counter[str],
    observed: Sequence[float],
    predicted: Sequence[float],
    observed_stream: bytearray,
    predicted_stream: bytearray,
) -> None:
    require(len(observed) == len(predicted), "float component count differs")
    for actual, expected in zip(observed, predicted, strict=True):
        counter["componentCount"] += 1
        counter["mismatchedComponents"] += model.float32_bits(
            actual
        ) != model.float32_bits(expected)
        observed_stream.extend(struct.pack("<f", actual))
        predicted_stream.extend(struct.pack("<f", expected))


def compare_indices(
    counter: Counter[str],
    observed: Sequence[int],
    predicted: Sequence[int],
    observed_stream: bytearray,
    predicted_stream: bytearray,
) -> None:
    require(len(observed) == len(predicted), "index component count differs")
    for actual, expected in zip(observed, predicted, strict=True):
        counter["componentCount"] += 1
        counter["mismatchedComponents"] += actual != expected
        observed_stream.extend(struct.pack("<H", actual))
        predicted_stream.extend(struct.pack("<H", expected))


def stream_metric(
    counter: Counter[str], observed: bytearray, predicted: bytearray
) -> JsonObject:
    return {
        "componentCount": counter["componentCount"],
        "mismatchedComponents": counter["mismatchedComponents"],
        "observedStreamSHA256": hashlib.sha256(observed).hexdigest(),
        "predictedStreamSHA256": hashlib.sha256(predicted).hexdigest(),
        "exact": (
            counter["componentCount"] > 0
            and counter["mismatchedComponents"] == 0
            and observed == predicted
        ),
    }


def transform_trace_bounds(
    trace: Mapping[str, Any],
) -> tuple[float, float, float, float]:
    x, y, width, height = trace["bounds"]
    matrix = struct.unpack("<20d", bytes.fromhex(str(trace["transformHex"])))
    points = [
        (
            point_x * matrix[0] + point_y * matrix[4] + matrix[12],
            point_x * matrix[1] + point_y * matrix[5] + matrix[13],
        )
        for point_x, point_y in (
            (x, y),
            (x + width, y),
            (x + width, y + height),
            (x, y + height),
        )
    ]
    return (
        min(point[0] for point in points),
        max(point[0] for point in points),
        min(point[1] for point in points),
        max(point[1] for point in points),
    )


def validate_live_trace(root: Path) -> JsonObject:
    for name, expected in DIAGNOSTIC_SHA256.items():
        require(sha256_file(root / name) == expected, f"{name} SHA-256 differs")
    sdf_disassembly = (root / "emit-sdf-bounds-disassembly.txt").read_text(
        encoding="utf-8"
    )
    rect_disassembly = (root / "emit-one-part-rect-disassembly.txt").read_text(
        encoding="utf-8"
    )
    helper_disassembly = (root / "emit-one-part-helper-disassembly.txt").read_text(
        encoding="utf-8"
    )
    require("emit_sdf_bounds_internal" in sdf_disassembly, "SDF caller is absent")
    for token in (
        "emit_one_part_rect",
        "Context::ClippedArray::next_rect",
        "CA::OGL::emit_quad",
    ):
        require(token in rect_disassembly, f"clipping call path lacks {token}")
    require(
        "fdiv   d" in helper_disassembly
        and "fcvt   s" in helper_disassembly
        and "fmadd  s" in helper_disassembly,
        "general-transform clipping instructions differ",
    )

    prefix = "LG_EMIT_ONE_TRACE "
    traces = [
        json.loads(line.removeprefix(prefix))
        for line in (root / "emit-one-exact-7432ffa-live-trace.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.startswith(prefix)
    ]
    timeline = json.loads(
        (root / "emit-one-exact-7432ffa-transition-timeline.json").read_text(
            encoding="utf-8"
        )
    )
    records = timeline["dynamicBackgroundUniforms"]["records"]
    require(len(traces) == len(records) == 32, "live trace record count differs")
    geometry = Counter()
    public_raw = Counter()
    public_outer = Counter()

    for trace, record in zip(traces, records, strict=True):
        final = model.final_highlight_inventory(record)
        require(final["vertexCount"] == 4, "live trace contains non-quad final mesh")
        vertices = [
            struct.unpack_from("<8f", final["vertices"], index * model.VERTEX_STRIDE)
            for index in range(4)
        ]
        left, right, bottom, top = transform_trace_bounds(trace)
        coordinate_0, coordinate_1, coordinate_2, coordinate_3 = trace["coordinates"]
        predicted_x = clip_axis(left, right, coordinate_0, coordinate_2, 0, 1024)
        predicted_y = clip_axis(bottom, top, coordinate_3, coordinate_1, 0, 1024)
        predicted_vertices = (
            (
                predicted_x[0],
                predicted_y[0],
                0.0,
                1.0,
                predicted_x[2],
                predicted_y[2],
            ),
            (
                predicted_x[1],
                predicted_y[0],
                0.0,
                1.0,
                predicted_x[3],
                predicted_y[2],
            ),
            (
                predicted_x[1],
                predicted_y[1],
                0.0,
                1.0,
                predicted_x[3],
                predicted_y[3],
            ),
            (
                predicted_x[0],
                predicted_y[1],
                0.0,
                1.0,
                predicted_x[2],
                predicted_y[3],
            ),
        )
        for actual, expected in zip(vertices, predicted_vertices, strict=True):
            geometry["componentCount"] += 6
            geometry["mismatchedComponents"] += sum(
                model.float32_bits(left_value) != model.float32_bits(right_value)
                for left_value, right_value in zip(actual[:6], expected, strict=True)
            )

        _, _, element, origin_x, origin_y = layer_axes(record)
        public_bounds = (
            model.float32(origin_x - 9.0),
            model.float32(origin_x + (-9.0 + element["bounds"][2] + 18.0)),
            model.float32(origin_y - (-9.0 + element["bounds"][3] + 18.0)),
            model.float32(origin_y + 9.0),
        )
        for actual, expected in zip(
            map(model.float32, (left, right, bottom, top)),
            public_bounds,
            strict=True,
        ):
            public_raw["componentCount"] += 1
            public_raw["mismatchedComponents"] += model.float32_bits(
                actual
            ) != model.float32_bits(expected)
        half_x = model.float32(element["bounds"][2] / 2.0)
        half_y = model.float32(element["bounds"][3] / 2.0)
        public_outer_values = (
            model.float32(model.float32(model.float32(half_x + 9.0) - 9.0) + 9.0),
            model.float32(model.float32(model.float32(half_y + 9.0) - 9.0) + 9.0),
        )
        for actual, expected in zip(
            (abs(coordinate_2), abs(coordinate_3)),
            public_outer_values,
            strict=True,
        ):
            public_outer["componentCount"] += 1
            public_outer["mismatchedComponents"] += model.float32_bits(
                actual
            ) != model.float32_bits(expected)

    require(geometry == Counter(componentCount=768), "live geometry trace is not exact")
    require(public_raw == Counter(componentCount=128), "live raw bounds are not exact")
    require(
        public_outer == Counter(componentCount=64), "live outer radii are not exact"
    )
    return {
        "recordCount": 32,
        "geometryComponents": 768,
        "geometryMismatches": 0,
        "publicRawComponents": 128,
        "publicRawMismatches": 0,
        "publicOuterComponents": 64,
        "publicOuterMismatches": 0,
        "artifactSHA256": DIAGNOSTIC_SHA256,
        "exact": True,
    }


def validate_prerequisites(repository: Path) -> JsonObject:
    paths = {
        "offcenterCircleElementStaging": (
            "Analysis/offcenter_circle_element_staging_result.json",
            OFFCENTER_RESULT_SHA256,
            "exact-retrospective-closure",
        ),
        "openedCombinedHoldout": (
            "Analysis/combined_transition_geometry_holdout_7432ffa_falsification_result.json",
            OPENED_HOLDOUT_RESULT_SHA256,
            "prospectively-falsified",
        ),
        "sourcePixelInfluence": (
            "Analysis/final_highlight_source_intervention_local_macos_26_6_1_result.json",
            SOURCE_INTERVENTION_RESULT_SHA256,
            "exact-pixel-noninfluence",
        ),
    }
    result: JsonObject = {}
    for name, (relative, expected_sha256, status) in paths.items():
        path = repository / relative
        require(sha256_file(path) == expected_sha256, f"{name} result SHA-256 differs")
        value = json.loads(path.read_text(encoding="utf-8"))
        require(value.get("status") == status, f"{name} status differs")
        result[name] = {"path": relative, "sha256": expected_sha256, "status": status}
    source = json.loads(
        (repository / paths["sourcePixelInfluence"][0]).read_text(encoding="utf-8")
    )
    require(
        source.get("totalComparedBytes") == 8_388_608
        and source.get("totalUnequalBytes") == 0
        and source.get("totalUnequalPixels") == 0
        and source.get("maximumChannelDelta") == 0,
        "source pixel-influence result differs",
    )
    return result


def analyze(
    capture_root: Path,
    preregistration: Path,
    diagnostic_root: Path,
    repository: Path,
) -> JsonObject:
    require(
        opened.sha256_file(preregistration) == opened.PREREGISTRATION_SHA256,
        "preregistration SHA-256 differs",
    )
    opened.validate_capture_transport(capture_root)
    prerequisites = validate_prerequisites(repository)
    live_trace = validate_live_trace(diagnostic_root)

    background_topology = Counter()
    split_vertices = Counter()
    split_indices = Counter()
    final_topology = Counter()
    final_indices = Counter()
    final_geometry = Counter()
    final_source = Counter()
    excluded_source = Counter()
    family_inventory = Counter()
    endpoint_inventory = Counter()
    streams = {
        name: (bytearray(), bytearray())
        for name in (
            "splitVertices",
            "splitIndices",
            "finalIndices",
            "finalGeometry",
            "finalSource",
        )
    }
    excluded_source_stream = bytearray()
    cases = []

    for case_id, expected_sha256 in sorted(opened.TIMELINE_SHA256.items()):
        path = capture_root / case_id / "transition-timeline.json"
        require(sha256_file(path) == expected_sha256, f"{case_id} SHA-256 differs")
        timeline = json.loads(path.read_text(encoding="utf-8"))
        material = str(timeline["material"])
        current_background_states = 0
        current_final_states = 0
        for record in timeline["dynamicBackgroundUniforms"]["records"]:
            pipeline = current_background_pipeline(record)
            if pipeline is not None:
                current_background_states += 1
                observed_count = current_background_vertex_count(record, pipeline)
                expected_count = 24 if background_split_predicate(record) else 6
                background_topology["stateCount"] += 1
                background_topology["splitStateCount"] += observed_count == 24
                background_topology["ordinaryStateCount"] += observed_count == 6
                background_topology["mismatchedStates"] += (
                    observed_count != expected_count
                )
                if observed_count == 24:
                    observed_streams = observed_split_background(record, pipeline)
                    predicted_streams = predicted_split_background(record, material)
                    for observed_vertices, predicted_vertices in zip(
                        observed_streams[:3], predicted_streams[:3], strict=True
                    ):
                        for observed_vertex, predicted_vertex in zip(
                            observed_vertices, predicted_vertices, strict=True
                        ):
                            compare_float_values(
                                split_vertices,
                                observed_vertex,
                                predicted_vertex,
                                *streams["splitVertices"],
                            )
                    compare_indices(
                        split_indices,
                        observed_streams[3],
                        predicted_streams[3],
                        *streams["splitIndices"],
                    )

            labels = opened.pipeline_tokens(record)
            if opened.CURRENT_FINAL_HIGHLIGHT not in labels:
                continue
            current_final_states += 1
            final = model.final_highlight_inventory(record)
            observed_vertices = [
                struct.unpack_from(
                    "<8f", final["vertices"], index * model.VERTEX_STRIDE
                )
                for index in range(final["vertexCount"])
            ]
            predicted_vertices, predicted_indices = predict_final(record, material)
            observed_border = len(observed_vertices) == 16
            predicted_border = len(predicted_vertices) == 16
            final_topology["stateCount"] += 1
            final_topology["borderStateCount"] += observed_border
            final_topology["quadStateCount"] += not observed_border
            final_topology["mismatchedStates"] += observed_border != predicted_border
            require(
                len(observed_vertices) == len(predicted_vertices),
                "final vertex count differs",
            )
            observed_indices = struct.unpack(
                f"<{final['indexCount']}H", final["indices"]
            )
            compare_indices(
                final_indices,
                observed_indices,
                predicted_indices,
                *streams["finalIndices"],
            )
            has_background = pipeline is not None
            family_name = (
                "with-current-background/"
                if has_background
                else "without-current-background/"
            ) + ("border" if observed_border else "quad")
            family_inventory[family_name] += 1
            if record["remaining"] == 1.0:
                endpoint_inventory[
                    f"{material}/"
                    + ("with-background" if has_background else "without-background")
                ] += 1

            for observed_vertex, predicted_vertex in zip(
                observed_vertices, predicted_vertices, strict=True
            ):
                compare_float_values(
                    final_geometry,
                    observed_vertex[:6],
                    predicted_vertex[:6],
                    *streams["finalGeometry"],
                )
                if has_background:
                    compare_float_values(
                        final_source,
                        observed_vertex[6:8],
                        predicted_vertex[6:8],
                        *streams["finalSource"],
                    )
                else:
                    excluded_source["componentCount"] += 2
                    excluded_source_stream.extend(
                        struct.pack("<2f", *observed_vertex[6:8])
                    )

        cases.append(
            {
                "caseId": case_id,
                "timelineSHA256": expected_sha256,
                "currentBackgroundStateCount": current_background_states,
                "currentFinalStateCount": current_final_states,
            }
        )

    require(
        background_topology
        == Counter(stateCount=163, splitStateCount=2, ordinaryStateCount=161),
        "current background topology gate differs",
    )
    require(
        split_vertices == Counter(componentCount=1440),
        "split background vertex gate differs",
    )
    require(
        split_indices == Counter(componentCount=192),
        "split background index gate differs",
    )
    require(
        final_topology
        == Counter(stateCount=191, borderStateCount=5, quadStateCount=186),
        "current final topology gate differs",
    )
    require(
        final_indices == Counter(componentCount=1236),
        "current final index gate differs",
    )
    require(
        final_geometry == Counter(componentCount=4944),
        "current final geometry gate differs",
    )
    require(
        final_source == Counter(componentCount=1344),
        "current final source gate differs",
    )
    require(
        excluded_source == Counter(componentCount=304),
        "excluded source inventory differs",
    )
    require(
        family_inventory
        == Counter(
            {
                "with-current-background/quad": 160,
                "with-current-background/border": 2,
                "without-current-background/quad": 26,
                "without-current-background/border": 3,
            }
        ),
        "current final family inventory differs",
    )

    metrics = {
        "splitBackgroundVertices": stream_metric(
            split_vertices, *streams["splitVertices"]
        ),
        "splitBackgroundIndices": stream_metric(
            split_indices, *streams["splitIndices"]
        ),
        "finalIndices": stream_metric(final_indices, *streams["finalIndices"]),
        "finalGeometry": stream_metric(final_geometry, *streams["finalGeometry"]),
        "finalPixelInfluentialSource": stream_metric(
            final_source, *streams["finalSource"]
        ),
    }
    require(all(value["exact"] for value in metrics.values()), "stream gate differs")

    return {
        "currentCircleTopologyAndClippingResultSchemaVersion": RESULT_SCHEMA_VERSION,
        "classification": (
            "retrospective bitwise closure chained to prospective pixel-influence evidence"
        ),
        "status": "exact-current-family-closure",
        "captureCommit": opened.CAPTURE_COMMIT,
        "captureBinarySHA256": opened.CAPTURE_BINARY_SHA256,
        "preregistrationSHA256": opened.PREREGISTRATION_SHA256,
        "prerequisites": prerequisites,
        "timelineCount": len(opened.TIMELINE_SHA256),
        "cases": cases,
        "currentBackgroundTopology": {
            "stateCount": background_topology["stateCount"],
            "ordinarySixVertexStateCount": background_topology["ordinaryStateCount"],
            "splitTwentyFourVertexStateCount": background_topology["splitStateCount"],
            "mismatchedStates": background_topology["mismatchedStates"],
            "predicate": "binary32(width / 2) != binary32(height / 2)",
            "exact": background_topology["mismatchedStates"] == 0,
        },
        "currentFinalTopology": {
            "stateCount": final_topology["stateCount"],
            "quadStateCount": final_topology["quadStateCount"],
            "borderStateCount": final_topology["borderStateCount"],
            "mismatchedStates": final_topology["mismatchedStates"],
            "predicate": (
                "rX=b32(b32(b32(width/2)+9)-9), "
                "rY=b32(b32(b32(height/2)+9)-9); border iff "
                "rX!=b32(width/2) or rY!=b32(height/2) or rX!=rY"
            ),
            "exact": final_topology["mismatchedStates"] == 0,
        },
        "familyInventory": dict(sorted(family_inventory.items())),
        "endpointInventory": dict(sorted(endpoint_inventory.items())),
        "metrics": metrics,
        "excludedNoBackgroundSource": {
            "componentCount": excluded_source["componentCount"],
            "observedStreamSHA256": hashlib.sha256(excluded_source_stream).hexdigest(),
            "reason": (
                "the preregistered complete-frame intervention proves current Iscd "
                "attribute-2 source bytes are pixel-irrelevant when no current "
                "background draw exists"
            ),
            "interventionResultSHA256": SOURCE_INTERVENTION_RESULT_SHA256,
        },
        "liveGeneralTransformTrace": live_trace,
        "generalTransformClippingLaw": {
            "callPath": [
                "CA::OGL::emit_sdf_bounds_internal",
                "CA::OGL::emit_one_part_rect",
                "CA::OGL::Context::ClippedArray::next_rect",
                "CA::OGL::emit_quad",
            ],
            "positionArithmetic": "raw transformed bounds and clip division are binary64",
            "fractionStore": "round division result once to binary32",
            "varyingArithmetic": (
                "round high-minus-low to binary32, then use one binary32 FMA"
            ),
            "edgeOrder": (
                "clip the low edge first; the high-edge fraction and interpolation "
                "consume the updated low position and varying"
            ),
            "positionStore": "replace clipped positions by the integer edge, then binary32",
        },
        "closedAlgorithmBoundary": (
            "current Tghz/Tghs split meshes and current TkfhBvcm topology, "
            "general-transform clipping, geometry, indices, and pixel-influential source"
        ),
        "remainingAppleAlgorithmBoundaries": [
            "small-clear Tghn/Tmua/Tkfh/A2Xghfc construction and pixels"
        ],
        "appleUnknownsBlockingGatedWalleIntegration": 0,
        "remainingProductProofs": [
            "Walle-shaped physical Retina color/compositor transfer",
            "fresh production-Walle frame with zero unequal bytes",
        ],
        "walleIntegrationMayBeginBehindGates": True,
        "productionParityAuthorized": False,
        "productionShaderChanged": False,
        "productionFlakeChanged": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-root", required=True, type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--diagnostic-root", required=True, type=Path)
    parser.add_argument(
        "--repository", default=Path(__file__).resolve().parents[1], type=Path
    )
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = analyze(
        arguments.capture_root,
        arguments.preregistration,
        arguments.diagnostic_root,
        arguments.repository,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
