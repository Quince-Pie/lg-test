#!/usr/bin/env python3
"""Analyze retained small-clear Tghn construction without claiming pixels."""

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
import hashlib
import json
import math
from pathlib import Path
import struct
from typing import Any

import analyze_combined_transition_geometry_holdout_falsification as opened
import analyze_transition_geometry_corpus_local_macos_26_6_1 as model
import analyze_transition_uniform_profile_calibration as profile
import validate_variable_blur_selected_region_origin as selected


type JsonObject = dict[str, Any]

RESULT_SCHEMA_VERSION = 1
TARGET_LAYER_PATH = (1, 0, 1, 0, 0, 0, 0)
PIPELINE = f"com.apple.coreanimation.{opened.SMALL_CLEAR_BACKGROUND}"
TMUA_PIPELINE = (
    "com.apple.coreanimation.PRGhABsovXm_TmuaA2Xhfcu_Isrc_Isqr"
)
INDEX_BYTES = bytes.fromhex("000001000200020003000000")
FRAGMENT_TWO_BYTES = bytes(8)
FRAGMENT_SIX_BYTES = bytes.fromhex("003c000000000000")
HALF_ONE = 0x3C00

TIMELINES = (
    (
        "clear-dark-dematerialize-06",
        "0fb1572ce1822fa3a00da0cf37357ba7d923d60d21da85b6a14207bf20c3fe31",
    ),
    (
        "clear-light-materialize-01",
        "85dc1f54a54f86852ee46b1c611f8968b470c0551a4647c0f7b8a59030ccb016",
    ),
)

EXPECTED_RECORD_LAYOUT = (
    ("pipeline", None, None),
    ("scissorRect", None, None),
    ("buffer", "fragment", 1),
    ("texture", "fragment", 3),
    ("sampler", "fragment", 0),
    ("texture", "fragment", 4),
    ("sampler", "fragment", 1),
    ("buffer", "fragment", 2),
    ("buffer", "fragment", 6),
    ("buffer", "vertex", 3),
    ("buffer", "vertex", 2),
    ("buffer", "vertex", 1),
    ("drawIndexedPrimitives", None, None),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def load_object(path: Path, label: str) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{label} is not an object")
    return value


def f32_from_bits(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def binary32_halfway(value: float) -> bool:
    """Return whether finite binary64 value is midway between two floats."""
    rounded = model.float32(value)
    if value == rounded:
        return False
    bits = model.float32_bits(rounded)
    adjacent = f32_from_bits(bits + (-1 if value < rounded else 1))
    return value == (float(rounded) + float(adjacent)) / 2.0


def metric_add_f32(
    metrics: dict[str, Counter[str]],
    streams: dict[str, tuple[bytearray, bytearray]],
    name: str,
    actual: Sequence[float],
    predicted: Sequence[float],
) -> None:
    require(len(actual) == len(predicted), f"{name} component count differs")
    counter = metrics.setdefault(name, Counter())
    actual_stream, predicted_stream = streams.setdefault(
        name, (bytearray(), bytearray())
    )
    for left, right in zip(actual, predicted, strict=True):
        left_bytes = struct.pack("<f", model.float32(left))
        right_bytes = struct.pack("<f", model.float32(right))
        actual_stream.extend(left_bytes)
        predicted_stream.extend(right_bytes)
        counter["componentCount"] += 1
        counter["mismatchedComponents"] += left_bytes != right_bytes


def metric_add_int(
    metrics: dict[str, Counter[str]],
    streams: dict[str, tuple[bytearray, bytearray]],
    name: str,
    actual: Sequence[int],
    predicted: Sequence[int],
) -> None:
    require(len(actual) == len(predicted), f"{name} component count differs")
    counter = metrics.setdefault(name, Counter())
    actual_stream, predicted_stream = streams.setdefault(
        name, (bytearray(), bytearray())
    )
    for left, right in zip(actual, predicted, strict=True):
        require(0 <= left <= 0xFFFFFFFF, f"{name} actual integer exceeds uint32")
        require(0 <= right <= 0xFFFFFFFF, f"{name} predicted integer exceeds uint32")
        actual_stream.extend(struct.pack("<I", left))
        predicted_stream.extend(struct.pack("<I", right))
        counter["componentCount"] += 1
        counter["mismatchedComponents"] += left != right


def metric_results(
    metrics: Mapping[str, Counter[str]],
    streams: Mapping[str, tuple[bytearray, bytearray]],
) -> JsonObject:
    result: JsonObject = {}
    for name, counter in sorted(metrics.items()):
        actual, predicted = streams[name]
        components = counter["componentCount"]
        mismatches = counter["mismatchedComponents"]
        result[name] = {
            "componentCount": components,
            "mismatchedComponents": mismatches,
            "exact": components > 0 and mismatches == 0,
            "observedSHA256": hashlib.sha256(actual).hexdigest(),
            "predictedSHA256": hashlib.sha256(predicted).hexdigest(),
        }
    return result


def target_records(record: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    render = model.mapping(record.get("render"), "dynamic render")
    probe = model.mapping(render.get("metalUniformProbe"), "Metal uniform probe")
    records = [
        model.mapping(value, "Metal record")
        for value in model.sequence(probe.get("records"), "Metal records")
    ]
    return [item for item in records if model.pipeline_label(item) == PIPELINE]


def snapshots(record: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    render = model.mapping(record.get("render"), "dynamic render")
    buffers = model.mapping(
        render.get("metalBufferSnapshots"), "Metal buffer snapshots"
    )
    return [
        model.mapping(value, "Metal buffer snapshot")
        for value in model.sequence(buffers.get("snapshots"), "buffer snapshots")
    ]


def one_snapshot(
    record: Mapping[str, Any],
    *,
    pipeline: str,
    stage: str,
    index: int,
) -> Mapping[str, Any]:
    matches = [
        item
        for item in snapshots(record)
        if model.pipeline_label(item) == pipeline
        and item.get("stage") == stage
        and item.get("index") == index
    ]
    require(
        len(matches) == 1,
        f"expected one {pipeline} {stage}[{index}] snapshot; found {len(matches)}",
    )
    return matches[0]


def small_profile_fields(
    record: Mapping[str, Any],
    *,
    appearance: str,
    diameter: int,
) -> dict[str, float]:
    """Construct all 46 non-clamp public numeric inputs for small clear."""
    remaining = model.float32(model.finite(record.get("remaining"), "remaining"))
    states = model.layer_states(record)
    element = model.mapping(states.get(TARGET_LAYER_PATH), "element layer state")
    extent_x, _ = model.vector(
        element.get("bounds"), "element bounds", 4
    )[2:4]
    extent = extent_x
    geometry = float(remaining) * float(extent)

    predicted = profile.predict_numeric_fields(
        material="clear",
        appearance=appearance,
        diameter=diameter,
        fraction=remaining,
    )
    predicted.update(
        inputBlurDistance0=-geometry / 2.0,
        inputOuterRefractionAmount=geometry / 5.0,
        inputOuterRefractionHeight=geometry / 8.0,
        inputShadowHeight=2.0 * geometry / 5.0,
        inputInnerRefractionAmount=-min(
            model.multiply32(60.0, remaining), geometry
        ),
        inputInnerRefractionHeight=min(
            model.multiply32(20.0, remaining), 0.36 * geometry
        ),
        inputShadowAmount=min(
            model.multiply32(75.0, remaining), 0.625 * geometry
        ),
    )
    clipped_extent = min(max(extent, 48.0), 160.0)
    endpoint_fraction = model.float32((clipped_extent - 48.0) / 112.0)
    endpoint = model.add32(
        model.float32(0.08),
        model.multiply32(
            model.subtract32(0.24, 0.08), endpoint_fraction
        ),
    )
    predicted["inputSDRShadowOpacity"] = profile.float32_mix(
        0.0, endpoint, remaining
    )
    require(
        tuple(predicted) == profile.PREDICTED_PYTHON_FIELDS,
        "small-clear profile field order differs",
    )
    return predicted


def selected_region_bounds(
    record: Mapping[str, Any], *, scale: float
) -> tuple[list[int], Mapping[str, Any]]:
    policy = selected.observed_policy(record, scale=scale)
    clamp = [
        model.integer(value, "copy clamp")
        for value in model.sequence(
            policy.get("textureCoordinateClamp"), "copy clamp"
        )
    ]
    active_extent = [clamp[2] + 1, clamp[3] + 1]
    crop_origin = [
        model.integer(value, "crop origin")
        for value in model.sequence(policy.get("cropOrigin"), "crop origin")
    ]
    inputs = model.mapping(
        model.mapping(record.get("filter"), "background filter").get(
            "inputValues"
        ),
        "background filter inputs",
    )
    radius1 = selected.predict_radius1(
        blur_radius=model.finite(inputs.get("inputBlurRadius"), "blur radius"),
        bleed_blur_radius=model.finite(
            inputs.get("inputBleedBlurRadius"), "bleed blur radius"
        ),
        backdrop_scale=scale,
    )
    mip = selected.predict_mip_policy(
        radius1=radius1, source_extent=active_extent
    )
    bounds = selected.predict_integer_bounds(
        bounds=[*crop_origin, *active_extent],
        radius1=radius1,
        alignment_scale=model.integer(
            mip.get("alignmentScale"), "alignment scale"
        ),
    )
    effective_origin = [
        model.integer(value, "effective origin")
        for value in model.sequence(
            policy.get("effectiveOrigin"), "effective origin"
        )
    ]
    require(bounds[:2] == effective_origin, "selected-region origin differs")
    return bounds, policy


def quad_terms(
    *, scale: float, bounds: Sequence[int]
) -> tuple[float, float, float, float, float]:
    require(len(bounds) == 4, "selected-region bounds length differs")
    origin_x, origin_y, extent_x, extent_y = bounds
    reciprocal = model.float32(1.0 / scale)
    base_x = model.multiply32(origin_x, reciprocal)
    base_y = model.multiply32(origin_y, reciprocal)
    delta_x = model.multiply32(extent_x, reciprocal)
    delta_y = model.multiply32(extent_y, reciprocal)
    return reciprocal, base_x, base_y, delta_x, delta_y


def predicted_position_and_backdrop_uv(
    *, scale: float, bounds: Sequence[int]
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    reciprocal, base_x, base_y, delta_x, delta_y = quad_terms(
        scale=scale, bounds=bounds
    )
    origin_x, origin_y, _, _ = bounds
    positions = [
        (base_x, model.subtract32(base_y, 8.0)),
        (
            model.add32(base_x, delta_x),
            model.subtract32(base_y, 8.0),
        ),
        (
            model.add32(base_x, delta_x),
            model.add32(base_y, delta_y),
        ),
        (base_x, model.add32(base_y, delta_y)),
    ]
    inverse_reciprocal = 1.0 / float(reciprocal)
    low_x = model.float32(
        math.fma(float(base_x), inverse_reciprocal, -float(origin_x))
    )
    high_x = model.float32(
        math.fma(
            float(base_x) + float(delta_x),
            inverse_reciprocal,
            -float(origin_x),
        )
    )
    low_y = model.float32(
        math.fma(
            float(base_y) - 8.0,
            inverse_reciprocal,
            -float(origin_y),
        )
    )
    high_y = model.float32(
        math.fma(
            float(base_y) + float(delta_y),
            inverse_reciprocal,
            -float(origin_y),
        )
    )
    backdrop_uv = [
        (low_x, low_y),
        (high_x, low_y),
        (high_x, high_y),
        (low_x, high_y),
    ]
    return positions, backdrop_uv


def decoded_tmua_origin(
    record: Mapping[str, Any], *, width: int, height: int
) -> tuple[float, float, tuple[float, ...]]:
    snapshot = one_snapshot(
        record, pipeline=TMUA_PIPELINE, stage="vertex", index=2
    )
    payload = model.payload(snapshot)
    require(len(payload) >= 64, "Tmua MVP snapshot is truncated")
    matrix = struct.unpack_from("<16f", payload)
    expected_fixed = (
        model.float32(2.0 / width),
        0.0,
        0.0,
        0.0,
        0.0,
        model.float32(-2.0 / height),
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    )
    require(
        tuple(model.float32_bits(value) for value in matrix[:12])
        == tuple(model.float32_bits(value) for value in expected_fixed),
        "Tmua MVP scale/basis differs",
    )
    require(
        matrix[14] == 0.0 and matrix[15] == 1.0,
        "Tmua MVP tail differs",
    )
    origin_x = -(float(matrix[12]) + 1.0) * (width / 2.0)
    origin_y = (float(matrix[13]) - 1.0) * (height / 2.0)
    require(
        origin_x.is_integer() and origin_y.is_integer(),
        "Tmua surface origin is not integral",
    )
    require(
        model.float32_bits(matrix[12])
        == model.float32_bits(-1.0 - 2.0 * origin_x / width)
        and model.float32_bits(matrix[13])
        == model.float32_bits(1.0 + 2.0 * origin_y / height),
        "Tmua surface origin does not recompose its MVP",
    )
    return origin_x, origin_y, matrix


def predicted_secondary_uv(
    *,
    scale: float,
    bounds: Sequence[int],
    origin_x: float,
    origin_y: float,
) -> tuple[list[tuple[float, float]], tuple[float, float]]:
    _, base_x, base_y, delta_x, delta_y = quad_terms(
        scale=scale, bounds=bounds
    )
    low_x = model.float32(float(base_x) - origin_x)
    high_x_raw = float(base_x) + float(delta_x) - origin_x
    low_y = model.float32(float(base_y) - 8.0 - origin_y)
    high_y_raw = float(base_y) + float(delta_y) - origin_y
    high_x = model.float32(high_x_raw)
    high_y = model.float32(high_y_raw)
    return (
        [
            (low_x, low_y),
            (high_x, low_y),
            (high_x, high_y),
            (low_x, high_y),
        ],
        (high_x_raw, high_y_raw),
    )


def analyze(capture_root: Path) -> JsonObject:
    require(capture_root.is_dir(), "capture root is not a directory")
    opened.validate_capture_transport(capture_root)
    metrics: dict[str, Counter[str]] = {}
    streams: dict[str, tuple[bytearray, bytearray]] = {}
    state_count = 0
    profile_words = 0
    fragment_tail_bytes = 0
    excluded_vertex_padding_bytes = 0
    secondary_high = Counter()
    texture3_inventory: Counter[str] = Counter()
    texture4_inventory: Counter[str] = Counter()
    case_results: list[JsonObject] = []

    with opened.opened_producer_fragments():
        for case_id, expected_sha256 in TIMELINES:
            path = capture_root / case_id / "transition-timeline.json"
            require(path.is_file(), f"missing timeline: {case_id}")
            require(
                sha256_file(path) == expected_sha256,
                f"timeline SHA-256 differs: {case_id}",
            )
            timeline = load_object(path, "transition timeline")
            geometry = model.mapping(timeline.get("geometry"), "timeline geometry")
            diameter = model.integer(geometry.get("width"), "geometry diameter")
            require(
                geometry.get("height") == diameter,
                "small-clear geometry is not circular",
            )
            appearance = timeline.get("appearance")
            require(
                appearance in {"light", "dark"},
                "small-clear appearance differs",
            )
            records = model.sequence(
                model.mapping(
                    timeline.get("dynamicBackgroundUniforms"),
                    "dynamic background uniforms",
                ).get("records"),
                "dynamic records",
            )
            case_states = 0
            for untyped_record in records:
                record = model.mapping(untyped_record, "dynamic record")
                metal = target_records(record)
                if not metal:
                    continue
                require(
                    len(metal) == len(EXPECTED_RECORD_LAYOUT),
                    "Tghn record count differs",
                )
                observed_layout = tuple(
                    (item.get("kind"), item.get("stage"), item.get("index"))
                    for item in metal
                )
                require(
                    observed_layout == EXPECTED_RECORD_LAYOUT,
                    "Tghn binding topology differs",
                )
                by_binding = {
                    (item.get("stage"), item.get("index")): item
                    for item in metal
                    if item.get("kind") == "buffer"
                }
                fragment1 = by_binding[("fragment", 1)]
                fragment2 = by_binding[("fragment", 2)]
                fragment6 = by_binding[("fragment", 6)]
                vertex3 = by_binding[("vertex", 3)]
                vertex2 = by_binding[("vertex", 2)]
                vertex1 = by_binding[("vertex", 1)]
                draw = metal[-1]
                offsets = (
                    model.integer(fragment1.get("offset"), "fragment1 offset"),
                    model.integer(fragment2.get("offset"), "fragment2 offset"),
                    model.integer(fragment6.get("offset"), "fragment6 offset"),
                    model.integer(vertex3.get("offset"), "vertex3 offset"),
                    model.integer(vertex2.get("offset"), "vertex2 offset"),
                    model.integer(vertex1.get("offset"), "vertex1 offset"),
                    model.integer(
                        draw.get("indexBufferOffset"), "index buffer offset"
                    ),
                )
                require(
                    tuple(
                        right - left
                        for left, right in zip(offsets, offsets[1:])
                    )
                    == (256, 8, 8, 32, 64, 192),
                    "Tghn allocation strides differ",
                )
                require(
                    draw.get("indexCount") == 6
                    and draw.get("indexType") == 0
                    and draw.get("primitiveType") == 3,
                    "Tghn indexed draw differs",
                )

                fragment1_bytes = model.payload(
                    one_snapshot(
                        record, pipeline=PIPELINE, stage="fragment", index=1
                    )
                )
                fragment2_bytes = model.payload(
                    one_snapshot(
                        record, pipeline=PIPELINE, stage="fragment", index=2
                    )
                )
                fragment6_bytes = model.payload(
                    one_snapshot(
                        record, pipeline=PIPELINE, stage="fragment", index=6
                    )
                )
                vertex3_bytes = model.payload(
                    one_snapshot(
                        record, pipeline=PIPELINE, stage="vertex", index=3
                    )
                )
                vertex2_bytes = model.payload(
                    one_snapshot(
                        record, pipeline=PIPELINE, stage="vertex", index=2
                    )
                )
                vertex1_bytes = model.payload(
                    one_snapshot(
                        record, pipeline=PIPELINE, stage="vertex", index=1
                    )
                )
                index_bytes = model.payload(
                    one_snapshot(
                        record, pipeline=PIPELINE, stage="index", index=-1
                    )
                )
                require(
                    all(
                        len(payload) >= minimum
                        for payload, minimum in (
                            (fragment1_bytes, 210),
                            (fragment2_bytes, 8),
                            (fragment6_bytes, 8),
                            (vertex3_bytes, 32),
                            (vertex2_bytes, 64),
                            (vertex1_bytes, 192),
                            (index_bytes, 12),
                        )
                    ),
                    "Tghn snapshot is truncated",
                )
                require(
                    fragment2_bytes[:8] == FRAGMENT_TWO_BYTES,
                    "Tghn fragment[2] differs",
                )
                require(
                    fragment6_bytes[:8] == FRAGMENT_SIX_BYTES,
                    "Tghn fragment[6] differs",
                )
                require(index_bytes[:12] == INDEX_BYTES, "Tghn indices differ")
                fragment_tail_bytes += 210

                texture3 = model.single(
                    [
                        item
                        for item in metal
                        if item.get("kind") == "texture"
                        and item.get("stage") == "fragment"
                        and item.get("index") == 3
                    ],
                    "Tghn texture[3]",
                )
                texture4 = model.single(
                    [
                        item
                        for item in metal
                        if item.get("kind") == "texture"
                        and item.get("stage") == "fragment"
                        and item.get("index") == 4
                    ],
                    "Tghn texture[4]",
                )
                width3 = model.integer(texture3.get("width"), "texture3 width")
                height3 = model.integer(
                    texture3.get("height"), "texture3 height"
                )
                width4 = model.integer(texture4.get("width"), "texture4 width")
                height4 = model.integer(
                    texture4.get("height"), "texture4 height"
                )
                require(
                    (width3, height3) == (64, 64)
                    and texture3.get("pixelFormat") == 80
                    and texture3.get("mipmapLevelCount") == 2
                    and texture3.get("storageMode") == 2
                    and texture3.get("usage") == 81927,
                    "Tghn texture[3] descriptor differs",
                )
                require(
                    (width4, height4) in {(128, 128), (64, 128)}
                    and texture4.get("pixelFormat") == 115
                    and texture4.get("mipmapLevelCount") == 1
                    and texture4.get("storageMode") == 2
                    and texture4.get("usage") == 5,
                    "Tghn texture[4] descriptor differs",
                )
                texture3_inventory[f"{width3}x{height3}"] += 1
                texture4_inventory[f"{width4}x{height4}"] += 1
                expected_vertex3 = struct.pack(
                    "<8f",
                    model.float32(1.0 / width3),
                    model.float32(1.0 / height3),
                    0.0,
                    0.0,
                    model.float32(1.0 / width4),
                    model.float32(1.0 / height4),
                    0.0,
                    0.0,
                )
                require(
                    vertex3_bytes[:32] == expected_vertex3,
                    "Tghn reciprocal texture dimensions differ",
                )
                expected_vertex2 = struct.pack(
                    "<16f",
                    1.0 / 512.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    -1.0 / 512.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    -1.0,
                    1.0,
                    0.0,
                    1.0,
                )
                require(
                    vertex2_bytes[:64] == expected_vertex2,
                    "Tghn final-pass MVP differs",
                )

                inputs = model.mapping(
                    model.mapping(record.get("filter"), "background filter").get(
                        "inputValues"
                    ),
                    "background filter inputs",
                )
                predicted_fields = small_profile_fields(
                    record, appearance=appearance, diameter=diameter
                )
                actual_profile = [
                    model.finite(inputs.get(name), name)
                    for name in profile.PREDICTED_PYTHON_FIELDS
                ]
                predicted_profile = [
                    predicted_fields[name]
                    for name in profile.PREDICTED_PYTHON_FIELDS
                ]
                metric_add_f32(
                    metrics,
                    streams,
                    "publicProfileNumericFields",
                    actual_profile,
                    predicted_profile,
                )
                profile_words += len(actual_profile)

                scale, _ = selected.allocation.captured_scale(record)
                remaining = model.float32(
                    model.finite(record.get("remaining"), "remaining")
                )
                reciprocal = model.float32(1.0 / scale)
                metric_add_f32(
                    metrics,
                    streams,
                    "dynamicResamplingScale",
                    [reciprocal],
                    [model.float32(2.0 / (2.0 - remaining))],
                )
                bounds, _ = selected_region_bounds(record, scale=scale)
                positions, backdrop_uv = predicted_position_and_backdrop_uv(
                    scale=scale, bounds=bounds
                )
                vertices = struct.unpack_from("<48f", vertex1_bytes)
                actual_position_xy: list[float] = []
                predicted_position_xy: list[float] = []
                actual_position_zw: list[float] = []
                predicted_position_zw: list[float] = []
                actual_backdrop_uv: list[float] = []
                predicted_backdrop_uv: list[float] = []
                actual_secondary_uv: list[float] = []
                actual_half: list[int] = []
                for vertex_index in range(4):
                    base = 12 * vertex_index
                    actual_position_xy.extend(vertices[base : base + 2])
                    predicted_position_xy.extend(positions[vertex_index])
                    actual_position_zw.extend(vertices[base + 2 : base + 4])
                    predicted_position_zw.extend((0.0, 1.0))
                    actual_backdrop_uv.extend(vertices[base + 4 : base + 6])
                    predicted_backdrop_uv.extend(backdrop_uv[vertex_index])
                    actual_secondary_uv.extend(vertices[base + 6 : base + 8])
                    actual_half.extend(
                        struct.unpack_from(
                            "<4H", vertex1_bytes, 48 * vertex_index + 32
                        )
                    )
                metric_add_f32(
                    metrics,
                    streams,
                    "positionXY",
                    actual_position_xy,
                    predicted_position_xy,
                )
                metric_add_f32(
                    metrics,
                    streams,
                    "positionZW",
                    actual_position_zw,
                    predicted_position_zw,
                )
                metric_add_f32(
                    metrics,
                    streams,
                    "backdropUV",
                    actual_backdrop_uv,
                    predicted_backdrop_uv,
                )
                metric_add_int(
                    metrics,
                    streams,
                    "activeColorHalf4",
                    actual_half,
                    [HALF_ONE] * 16,
                )
                excluded_vertex_padding_bytes += 4 * 8

                origin_x, origin_y, _ = decoded_tmua_origin(
                    record, width=width4, height=height4
                )
                secondary_uv, high_raw = predicted_secondary_uv(
                    scale=scale,
                    bounds=bounds,
                    origin_x=origin_x,
                    origin_y=origin_y,
                )
                predicted_secondary_components = [
                    component
                    for vertex in secondary_uv
                    for component in vertex
                ]
                metric_add_f32(
                    metrics,
                    streams,
                    "secondaryUVRetrospectiveCandidate",
                    actual_secondary_uv,
                    predicted_secondary_components,
                )
                actual_high = (vertices[18], vertices[31])
                duplicate_high = (vertices[30], vertices[43])
                require(
                    tuple(model.float32_bits(value) for value in actual_high)
                    == tuple(model.float32_bits(value) for value in duplicate_high),
                    "duplicated secondary-UV high edge differs",
                )
                for actual, predicted, raw in zip(
                    actual_high,
                    (secondary_uv[1][0], secondary_uv[2][1]),
                    high_raw,
                    strict=True,
                ):
                    halfway = binary32_halfway(raw)
                    differs = (
                        model.float32_bits(actual)
                        != model.float32_bits(predicted)
                    )
                    secondary_high["componentCount"] += 1
                    secondary_high["halfwayComponentCount"] += halfway
                    secondary_high["nonHalfwayComponentCount"] += not halfway
                    secondary_high["mismatchedComponents"] += differs
                    secondary_high["mismatchedHalfwayDecisions"] += (
                        halfway and differs
                    )
                    secondary_high["mismatchedNonHalfwayComponents"] += (
                        not halfway and differs
                    )

                scissor = metal[1]
                tmua_vertices = struct.unpack_from(
                    "<192f",
                    model.payload(
                        one_snapshot(
                            record,
                            pipeline=TMUA_PIPELINE,
                            stage="vertex",
                            index=1,
                        )
                    ),
                )
                tmua_x = [tmua_vertices[12 * index] for index in range(16)]
                tmua_y = [tmua_vertices[12 * index + 1] for index in range(16)]
                center_x = (min(tmua_x) + max(tmua_x)) / 2.0
                center_y = (min(tmua_y) + max(tmua_y)) / 2.0
                predicted_scissor = (
                    math.floor(center_x - diameter / 2.0 + 0.5),
                    math.floor(center_y - diameter / 2.0 - 8.0 + 0.5),
                    diameter,
                    diameter + 8,
                )
                actual_scissor = tuple(
                    model.integer(scissor.get(name), f"scissor {name}")
                    for name in ("x", "y", "width", "height")
                )
                metric_add_int(
                    metrics,
                    streams,
                    "scissor",
                    actual_scissor,
                    predicted_scissor,
                )

                displacement = struct.unpack_from("<4f", fragment1_bytes)
                metric_add_f32(
                    metrics,
                    streams,
                    "profileDisplacementMatrix",
                    displacement,
                    (
                        model.float32(scale / 64.0),
                        0.0,
                        0.0,
                        model.float32(-scale / 64.0),
                    ),
                )
                state_count += 1
                case_states += 1
            case_results.append(
                {
                    "caseId": case_id,
                    "appearance": appearance,
                    "diameter": diameter,
                    "stateCount": case_states,
                    "timelineSHA256": expected_sha256,
                }
            )

    results = metric_results(metrics, streams)
    require(state_count == 60, "Tghn state count differs")
    require(profile_words == 2_760, "small-clear profile word count differs")
    for name in (
        "activeColorHalf4",
        "backdropUV",
        "dynamicResamplingScale",
        "positionXY",
        "positionZW",
        "profileDisplacementMatrix",
        "publicProfileNumericFields",
        "scissor",
    ):
        require(results[name]["exact"] is True, f"exact metric differs: {name}")
    require(
        results["secondaryUVRetrospectiveCandidate"]["componentCount"] == 480
        and results["secondaryUVRetrospectiveCandidate"][
            "mismatchedComponents"
        ]
        == 24,
        "secondary-UV opened residual differs",
    )
    require(
        secondary_high
        == Counter(
            {
                "componentCount": 120,
                "nonHalfwayComponentCount": 89,
                "halfwayComponentCount": 31,
                "mismatchedComponents": 12,
                "mismatchedHalfwayDecisions": 12,
                "mismatchedNonHalfwayComponents": 0,
            }
        ),
        "secondary-UV unique halfway census differs",
    )
    require(
        texture3_inventory == Counter({"64x64": 60}),
        "Tghn texture[3] inventory differs",
    )
    require(
        texture4_inventory == Counter({"128x128": 58, "64x128": 2}),
        "Tghn texture[4] inventory differs",
    )

    return {
        "smallClearBackgroundAnalysisSchemaVersion": RESULT_SCHEMA_VERSION,
        "classification": (
            "retrospective exact construction over the retained combined "
            "holdout; secondary-UV tie policy and pixels remain fail-closed"
        ),
        "status": "exact-retained-Tghn-construction-with-open-ties-and-pixels",
        "stateCount": state_count,
        "cases": case_results,
        "bindingTopology": {
            "recordCountPerState": len(EXPECTED_RECORD_LAYOUT),
            "fragmentProfileMeaningfulBytesPerState": 210,
            "fragmentProfileMeaningfulByteCount": fragment_tail_bytes,
            "fragmentAllocationStrideBytes": 256,
            "vertexStrideBytes": 48,
            "vertexCountPerState": 4,
            "indexCountPerState": 6,
            "indexBytes": INDEX_BYTES.hex(),
            "excludedUnclassifiedVertexBytesPerVertex": 8,
            "excludedUnclassifiedVertexByteCount": excluded_vertex_padding_bytes,
        },
        "textureInventory": {
            "backdrop": dict(sorted(texture3_inventory.items())),
            "TmuaOutput": dict(sorted(texture4_inventory.items())),
        },
        "metrics": results,
        "secondaryUVTieBoundary": {
            **dict(secondary_high),
            "duplicatedVertexComponentMismatches": results[
                "secondaryUVRetrospectiveCandidate"
            ]["mismatchedComponents"],
            "retrospectiveCandidateHasTransferAuthority": False,
            "exactPolicyClosed": False,
        },
        "publicProfileNumericWordCount": profile_words,
        "publicProfileNumericLawClosed": True,
        "fragmentPayloadByteConstructorClosed": False,
        "TghnGeometryAndBackdropUVClosed": True,
        "TghnSecondaryUVClosed": False,
        "TghnPixelSemanticsClosed": False,
        "TghnBoundaryClosed": False,
        "remainingTghnWork": [
            "prospectively distinguish the 12 unique secondary-UV halfway decisions",
            "construct all 210 meaningful fragment payload bytes independently",
            "replay the exact Tghn pass on the physical Retina M1 Max and require zero unequal bytes",
        ],
        "remainingAppleAlgorithmFamilies": [
            "small-clear Tghn and Tmua/A2Xghfc construction and pixels"
        ],
        "remainingSmallClearSubBoundaries": [
            "Tghn secondary-UV/payload/pixels",
            "Tmua/A2Xghfc producer/composition construction and pixels",
        ],
        "remainingProductProofs": [
            "Walle-shaped physical Retina color/compositor transfer",
            "fresh production-Walle frame with zero unequal bytes",
        ],
        "appleUnknownsBlockingGatedWalleIntegration": 0,
        "walleIntegrationMayBeginBehindGates": True,
        "universalCircleDomainParity": False,
        "productionParityAuthorized": False,
        "productionShaderChanged": False,
        "productionFlakeChanged": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = analyze(arguments.capture_root)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
