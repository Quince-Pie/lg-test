#!/usr/bin/env python3
"""Gate prospective Apple backdrop allocation and origin metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


EXPECTED_SAMPLE_INDICES = (
    1,
    4,
    8,
    12,
    15,
    16,
    17,
    20,
    24,
    27,
    28,
    29,
    31,
    32,
)
EXPECTED_GEOMETRIES = frozenset(
    {
        "circle-256-center",
        "circle-512-offset",
        "circle-640-fractional",
        "circle-1536-center",
    }
)
EXPECTED_METHOD = (
    "copied-presentation-background-filter-plus-compatible-"
    "layer-state-on-fresh-static-model-tree-with-original-"
    "producer-input-and-metadata-only-stage-capture"
)
EXPECTED_CARRIER_CRITICAL_PATHS = [
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
BACKDROP_LAYER_PATH = (1, 0, 1, 0)
COPY_BASE_PIPELINE = "com.apple.coreanimation.variable_blur_copy_base_mip_compute"
PRODUCER_FRAGMENTS = frozenset({"A2Xghfc", "TimgA2Xhfc_Isrc"})
ALLOCATION_QUANTUM = 64
ORIGIN_QUANTUM = 4
VERTEX_STRIDE = 48
QUAD_INDICES = (0, 1, 2, 2, 3, 0)


def mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} is not an object")
    return value


def numeric(value: object, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} is not finite")
    return result


def single(records: Sequence[Any], name: str) -> Mapping[str, Any]:
    if len(records) != 1:
        raise ValueError(f"expected one {name}; found {len(records)}")
    return mapping(records[0], name)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def float32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def align_up(value: float, alignment: int = ALLOCATION_QUANTUM) -> int:
    if not math.isfinite(value) or value <= 0 or alignment <= 0:
        raise ValueError("allocation extent must be finite and positive")
    return alignment * math.ceil(value / alignment)


def align_down(value: int, alignment: int = ORIGIN_QUANTUM) -> int:
    if alignment <= 0:
        raise ValueError("origin alignment must be positive")
    return alignment * (value // alignment)


def axis_policy(
    *,
    frame_minimum: float,
    frame_extent: float,
    window_extent: float,
    scale: float,
    invert: bool,
) -> dict[str, Any]:
    if (
        not all(
            math.isfinite(value)
            for value in (
                frame_minimum,
                frame_extent,
                window_extent,
                scale,
            )
        )
        or frame_extent <= 0
        or window_extent <= 0
        or scale <= 0
    ):
        raise ValueError("invalid nominal-frame axis")

    if invert:
        unclipped_lower = window_extent - (frame_minimum + frame_extent)
        unclipped_upper = window_extent - frame_minimum
    else:
        unclipped_lower = frame_minimum
        unclipped_upper = frame_minimum + frame_extent
    clipped_lower = max(0.0, unclipped_lower)
    clipped_upper = min(window_extent, unclipped_upper)
    if clipped_upper <= clipped_lower:
        raise ValueError("nominal frame does not intersect the window")

    scaled_lower = scale * clipped_lower
    scaled_upper = scale * clipped_upper
    crop_origin = math.ceil(scaled_lower) if invert else math.floor(scaled_lower) + 1
    clamp_maximum = math.floor(scaled_upper) - crop_origin - 1
    if clamp_maximum < 0:
        raise ValueError("predicted producer clamp is empty")
    return {
        "unclippedBounds": [unclipped_lower, unclipped_upper],
        "clippedBounds": [clipped_lower, clipped_upper],
        "scaledBounds": [scaled_lower, scaled_upper],
        "cropOrigin": crop_origin,
        "clampMaximum": clamp_maximum,
        "producerExtent": align_up(clamp_maximum + 1),
        "destinationExtent": align_up(scale * (clipped_upper - clipped_lower)),
    }


def predict_policy(
    geometry: Mapping[str, Any],
    *,
    remaining: float,
    scale: float,
) -> dict[str, Any]:
    if not 0.0 < remaining <= 1.0:
        raise ValueError("opened dynamic states require 0 < remaining <= 1")
    width = numeric(geometry.get("width"), "geometry width")
    height = numeric(geometry.get("height"), "geometry height")
    center_x = numeric(geometry.get("centerX"), "geometry centerX")
    center_y = numeric(geometry.get("centerY"), "geometry centerY")
    window_width = numeric(geometry.get("windowWidth"), "geometry windowWidth")
    window_height = numeric(geometry.get("windowHeight"), "geometry windowHeight")
    frame_x = center_x - width * remaining / 2.0
    frame_y = center_y - height * remaining / 2.0
    x_axis = axis_policy(
        frame_minimum=frame_x,
        frame_extent=width,
        window_extent=window_width,
        scale=scale,
        invert=False,
    )
    y_axis = axis_policy(
        frame_minimum=frame_y,
        frame_extent=height,
        window_extent=window_height,
        scale=scale,
        invert=True,
    )
    crop_origin = [x_axis["cropOrigin"], y_axis["cropOrigin"]]
    # This phase law was exact on all 216 opened circle-800 states but was
    # deliberately frozen before observing any geometry in this holdout.
    effective_origin = [
        align_down(crop_origin[0] - 1 - int(remaining >= 0.5)),
        align_down(crop_origin[1] - 1),
    ]
    return {
        "nominalFrameMinimum": [frame_x, frame_y],
        "cropOrigin": crop_origin,
        "textureCoordinateClamp": [
            0,
            0,
            x_axis["clampMaximum"],
            y_axis["clampMaximum"],
        ],
        "producerExtent": [
            x_axis["producerExtent"],
            y_axis["producerExtent"],
        ],
        "destinationExtent": [
            x_axis["destinationExtent"],
            y_axis["destinationExtent"],
        ],
        "effectiveOrigin": effective_origin,
        "axes": {"x": x_axis, "y": y_axis},
    }


def pipeline_label(record: Mapping[str, Any]) -> str:
    pipeline = record.get("pipeline")
    if not isinstance(pipeline, Mapping):
        return ""
    label = pipeline.get("label")
    return label if isinstance(label, str) else ""


def pipeline_fragment(record: Mapping[str, Any]) -> str:
    pipeline = record.get("pipeline")
    descriptor = (
        pipeline.get("creationDescriptor") if isinstance(pipeline, Mapping) else None
    )
    fragment = (
        descriptor.get("fragmentFunction") if isinstance(descriptor, Mapping) else None
    )
    return fragment if isinstance(fragment, str) else ""


def payload(record: Mapping[str, Any]) -> bytes:
    description = mapping(record.get("payload"), "buffer payload")
    encoded = description.get("hex")
    length = description.get("lengthBytes")
    if not isinstance(encoded, str):
        raise ValueError("captured buffer has no hexadecimal payload")
    value = bytes.fromhex(encoded)
    if not isinstance(length, int) or length != len(value):
        raise ValueError("captured payload length differs")
    return value


def texture(record: Mapping[str, Any]) -> Mapping[str, Any]:
    descriptor = record.get("texture")
    if isinstance(descriptor, Mapping):
        return descriptor
    if isinstance(record.get("address"), str):
        return record
    raise ValueError("texture binding has no descriptor")


def render_attachment_address(record: Mapping[str, Any]) -> str | None:
    attachments = record.get("colorAttachments")
    if not isinstance(attachments, list):
        return None
    for untyped_attachment in attachments:
        if not isinstance(untyped_attachment, Mapping):
            continue
        if untyped_attachment.get("index") != 0:
            continue
        descriptor = untyped_attachment.get("texture")
        address = descriptor.get("address") if isinstance(descriptor, Mapping) else None
        return address if isinstance(address, str) else None
    return None


def decode_copy_base_uniform(value: bytes) -> dict[str, Any]:
    if len(value) < 32:
        raise ValueError("copy-base uniform payload is shorter than 32 bytes")
    return {
        "textureCoordinateBase": list(struct.unpack_from("<2h", value, 0)),
        "textureCoordinateClamp": list(struct.unpack_from("<4h", value, 8)),
        "destinationLevel0Size": list(struct.unpack_from("<2H", value, 16)),
    }


def recover_crop_origin(
    mvp: tuple[float, ...],
    *,
    width: int,
    height: int,
) -> dict[str, Any]:
    if len(mvp) != 16 or width <= 0 or height <= 0:
        raise ValueError("invalid producer MVP or extent")
    raw_x = -(mvp[12] + 1.0) * width / 2.0
    raw_y = (mvp[13] - 1.0) * height / 2.0
    origin_x = round(raw_x)
    origin_y = round(raw_y)
    return {
        "origin": [origin_x, origin_y],
        "raw": [raw_x, raw_y],
        "maximumIntegralResidual": max(
            abs(raw_x - origin_x),
            abs(raw_y - origin_y),
        ),
        "orthographicScaleBitsExact": (
            float32_bits(mvp[0]) == float32_bits(2.0 / width)
            and float32_bits(mvp[5]) == float32_bits(-2.0 / height)
        ),
    }


def no_raw_stage_dumps(value: object) -> bool:
    if isinstance(value, Mapping):
        if "rawFile" in value or value.get("rawCapture") is True:
            return False
        return all(no_raw_stage_dumps(item) for item in value.values())
    if isinstance(value, list):
        return all(no_raw_stage_dumps(item) for item in value)
    return True


def independent_quad_indices(vertex_count: int) -> tuple[int, ...]:
    if vertex_count < 4 or vertex_count % 4 != 0:
        raise ValueError(f"unexpected producer vertex count: {vertex_count}")
    return tuple(
        base + index for base in range(0, vertex_count, 4) for index in QUAD_INDICES
    )


def producer_geometry(
    render: Mapping[str, Any],
    *,
    records: list[Mapping[str, Any]],
    snapshots: list[Mapping[str, Any]],
    source_address: str,
    source_width: int,
    source_height: int,
    scale: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    render_pass = single(
        [
            record
            for record in records
            if record.get("kind") == "renderPass"
            and render_attachment_address(record) == source_address
        ],
        "producer render pass",
    )
    encoder = render_pass.get("encoder")
    pass_sequence = int(render_pass["sequence"])
    draw = single(
        [
            record
            for record in records
            if record.get("encoder") == encoder
            and record.get("kind") == "drawIndexedPrimitives"
            and int(record.get("sequence", -1)) > pass_sequence
        ],
        "producer indexed draw",
    )
    draw_sequence = int(draw["sequence"])
    pipeline = single(
        [
            record
            for record in records
            if record.get("encoder") == encoder
            and record.get("kind") == "pipeline"
            and pass_sequence < int(record.get("sequence", -1)) < draw_sequence
        ],
        "producer pipeline",
    )
    fragment = pipeline_fragment(pipeline)
    if fragment not in PRODUCER_FRAGMENTS:
        raise ValueError(f"unexpected producer fragment: {fragment}")
    vertex_snapshot = single(
        [
            snapshot
            for snapshot in snapshots
            if snapshot.get("stage") == "vertex"
            and snapshot.get("index") == 1
            and pass_sequence < int(snapshot.get("sequence", -1)) < draw_sequence
        ],
        "producer vertex buffer",
    )
    mvp_snapshot = single(
        [
            snapshot
            for snapshot in snapshots
            if snapshot.get("stage") == "vertex"
            and snapshot.get("index") == 2
            and pass_sequence < int(snapshot.get("sequence", -1)) < draw_sequence
        ],
        "producer MVP buffer",
    )
    index_snapshot = single(
        [
            snapshot
            for snapshot in snapshots
            if snapshot.get("stage") == "index"
            and int(snapshot.get("sequence", -1)) == draw_sequence
        ],
        "producer index buffer",
    )
    index_count = int(draw["indexCount"])
    index_bytes = payload(index_snapshot)
    if len(index_bytes) < 2 * index_count:
        raise ValueError("producer index payload is truncated")
    indices = struct.unpack_from(f"<{index_count}H", index_bytes)
    vertex_count = max(indices) + 1
    expected_indices = independent_quad_indices(vertex_count)
    if indices != expected_indices:
        raise ValueError("producer quad topology differs")
    vertex_bytes = payload(vertex_snapshot)
    if len(vertex_bytes) < vertex_count * VERTEX_STRIDE:
        raise ValueError("producer vertex payload is truncated")
    vertices = [
        struct.unpack_from("<8f", vertex_bytes, index * VERTEX_STRIDE)
        for index in range(vertex_count)
    ]
    mvp_bytes = payload(mvp_snapshot)
    if len(mvp_bytes) < 64:
        raise ValueError("producer MVP payload is truncated")
    mvp = struct.unpack_from("<16f", mvp_bytes)
    crop = recover_crop_origin(
        mvp,
        width=source_width,
        height=source_height,
    )
    if (
        crop["orthographicScaleBitsExact"] is not True
        or crop["maximumIntegralResidual"] > 0.0001
    ):
        raise ValueError("producer crop MVP is not an integral orthographic crop")

    viewport = single(
        [
            record
            for record in records
            if record.get("encoder") == encoder
            and record.get("kind") == "viewport"
            and pass_sequence < int(record.get("sequence", -1)) < draw_sequence
        ],
        "producer viewport",
    )
    scissor = single(
        [
            record
            for record in records
            if record.get("encoder") == encoder
            and record.get("kind") == "scissorRect"
            and pass_sequence < int(record.get("sequence", -1)) < draw_sequence
        ],
        "producer scissor",
    )
    if (
        numeric(viewport.get("originX"), "viewport originX") != 0
        or numeric(viewport.get("originY"), "viewport originY") != 0
        or numeric(viewport.get("width"), "viewport width") != source_width
        or numeric(viewport.get("height"), "viewport height") != source_height
    ):
        raise ValueError("producer viewport differs from its attachment")
    scissor_values = [int(scissor[name]) for name in ("x", "y", "width", "height")]
    if (
        scissor_values[0] < 0
        or scissor_values[1] < 0
        or scissor_values[2] <= 0
        or scissor_values[3] <= 0
        or scissor_values[0] + scissor_values[2] > source_width
        or scissor_values[1] + scissor_values[3] > source_height
    ):
        raise ValueError("producer scissor exceeds its attachment")

    source_scale_mismatches = 0
    inverse_scale = 1.0 / scale
    for vertex in vertices[:4]:
        for axis in range(2):
            predicted = float32(vertex[axis] * inverse_scale)
            source_scale_mismatches += float32_bits(predicted) != float32_bits(
                vertex[4 + axis]
            )
    if source_scale_mismatches:
        raise ValueError("producer source-coordinate q law differs")
    all_source_scale_mismatches = 0
    for vertex in vertices:
        for axis in range(2):
            predicted = float32(vertex[axis] * inverse_scale)
            all_source_scale_mismatches += float32_bits(predicted) != float32_bits(
                vertex[4 + axis]
            )

    quad_bounds = []
    for base in range(0, vertex_count, 4):
        quad = vertices[base : base + 4]
        quad_bounds.append(
            {
                "position": [
                    min(vertex[0] for vertex in quad),
                    min(vertex[1] for vertex in quad),
                    max(vertex[0] for vertex in quad),
                    max(vertex[1] for vertex in quad),
                ],
                "source": [
                    min(vertex[4] for vertex in quad),
                    min(vertex[5] for vertex in quad),
                    max(vertex[4] for vertex in quad),
                    max(vertex[5] for vertex in quad),
                ],
            }
        )

    producer_input = single(
        [
            record
            for record in records
            if record.get("kind") == "texture"
            and record.get("stage") == "fragment"
            and record.get("index") == 3
            and record.get("encoder") == encoder
            and int(record.get("sequence", -1)) < draw_sequence
        ],
        "producer input texture",
    )
    input_texture = texture(producer_input)
    input_label = input_texture.get("label", "")
    if (
        input_texture.get("width") != 1_024
        or input_texture.get("height") != 1_024
        or input_texture.get("pixelFormat") != 80
        or "coordinate-hash" in str(input_label)
    ):
        raise ValueError("producer input was replaced or has unexpected geometry")

    return crop, {
        "fragmentFunction": fragment,
        "vertexCount": vertex_count,
        "indexCount": index_count,
        "vertexPayloadSHA256": hashlib.sha256(vertex_bytes).hexdigest(),
        "mvpPayloadSHA256": hashlib.sha256(mvp_bytes).hexdigest(),
        "primaryVertices": [list(vertex) for vertex in vertices[:4]],
        "quadBounds": quad_bounds,
        "viewport": [0, 0, source_width, source_height],
        "scissor": scissor_values,
        "sourceScaleComponentCount": 8,
        "sourceScaleMismatchedComponents": source_scale_mismatches,
        "allSourceScaleComponentCount": 2 * vertex_count,
        "allSourceScaleMismatchedComponents": all_source_scale_mismatches,
        "inputTexture": {
            "width": input_texture.get("width"),
            "height": input_texture.get("height"),
            "pixelFormat": input_texture.get("pixelFormat"),
            "label": input_label,
        },
    }


def observed_policy(
    record: Mapping[str, Any],
    *,
    scale: float,
) -> dict[str, Any]:
    render = mapping(record.get("render"), "dynamic render")
    if render.get("executed") is not True:
        raise ValueError("dynamic CARenderer state did not execute")
    if any(
        name in render
        for name in (
            "output",
            "exactPassReplay",
            "dynamicBackdropProducerBoundary",
        )
    ) or not no_raw_stage_dumps(render):
        raise ValueError("allocation holdout retained a raw stage dump")
    probe = mapping(render.get("metalUniformProbe"), "metalUniformProbe")
    untyped_records = probe.get("records")
    buffers = mapping(render.get("metalBufferSnapshots"), "metalBufferSnapshots")
    untyped_snapshots = buffers.get("snapshots")
    textures = mapping(render.get("metalTextureSnapshots"), "metalTextureSnapshots")
    if (
        not isinstance(untyped_records, list)
        or not isinstance(untyped_snapshots, list)
        or not isinstance(textures.get("snapshots"), list)
    ):
        raise ValueError("allocation metadata is incomplete")
    records = [mapping(value, "Metal record") for value in untyped_records]
    snapshots = [mapping(value, "Metal buffer snapshot") for value in untyped_snapshots]
    copy_source = single(
        [
            item
            for item in records
            if item.get("kind") == "texture"
            and item.get("stage") == "compute"
            and item.get("index") == 0
            and pipeline_label(item) == COPY_BASE_PIPELINE
        ],
        "copy-base source texture",
    )
    copy_destination = single(
        [
            item
            for item in records
            if item.get("kind") == "texture"
            and item.get("stage") == "compute"
            and item.get("index") == 1
            and pipeline_label(item) == COPY_BASE_PIPELINE
        ],
        "copy-base destination texture",
    )
    copy_uniform_snapshot = single(
        [
            item
            for item in snapshots
            if item.get("stage") == "compute"
            and item.get("index") == 0
            and pipeline_label(item) == COPY_BASE_PIPELINE
        ],
        "copy-base uniform buffer",
    )
    source = texture(copy_source)
    destination = texture(copy_destination)
    source_width = int(source["width"])
    source_height = int(source["height"])
    source_address = source.get("address")
    if not isinstance(source_address, str):
        raise ValueError("producer output has no Metal address")
    uniform = decode_copy_base_uniform(payload(copy_uniform_snapshot))
    destination_extent = [
        int(destination["width"]),
        int(destination["height"]),
    ]
    if uniform["destinationLevel0Size"] != destination_extent:
        raise ValueError("copy-base uniform and destination extent differ")
    crop, mesh = producer_geometry(
        render,
        records=records,
        snapshots=snapshots,
        source_address=source_address,
        source_width=source_width,
        source_height=source_height,
        scale=scale,
    )
    crop_origin = [int(value) for value in crop["origin"]]
    copy_offset = [int(value) for value in uniform["textureCoordinateBase"]]
    return {
        "cropOrigin": crop_origin,
        "textureCoordinateClamp": [
            int(value) for value in uniform["textureCoordinateClamp"]
        ],
        "producerExtent": [source_width, source_height],
        "destinationExtent": destination_extent,
        "copyOffset": copy_offset,
        "effectiveOrigin": [
            crop_origin[0] + copy_offset[0],
            crop_origin[1] + copy_offset[1],
        ],
        "producerCropMaximumIntegralResidual": crop["maximumIntegralResidual"],
        "producerMesh": mesh,
    }


def captured_scale(record: Mapping[str, Any]) -> tuple[float, int]:
    untyped_states = record.get("capturedLayerStates")
    if not isinstance(untyped_states, list):
        raise ValueError("captured layer states are missing")
    states = [mapping(value, "captured layer state") for value in untyped_states]
    paths = [tuple(state.get("path", ())) for state in states]
    if len(paths) != len(set(paths)):
        raise ValueError("captured layer-state paths are not unique")
    backdrop = single(
        [
            state
            for state, path in zip(states, paths, strict=True)
            if path == BACKDROP_LAYER_PATH and state.get("class") == "CABackdropLayer"
        ],
        "captured CABackdropLayer state",
    )
    return (
        numeric(backdrop.get("backdropScale"), "captured backdrop scale"),
        len(states),
    )


def comparison(
    prediction: Mapping[str, Any],
    observed: Mapping[str, Any],
) -> dict[str, Any]:
    fields = (
        "cropOrigin",
        "textureCoordinateClamp",
        "producerExtent",
        "destinationExtent",
        "effectiveOrigin",
    )
    result: dict[str, Any] = {}
    for name in fields:
        predicted_values = prediction[name]
        observed_values = observed[name]
        if not isinstance(predicted_values, list) or not isinstance(
            observed_values, list
        ):
            raise ValueError(f"{name} is not a vector")
        if len(predicted_values) != len(observed_values):
            raise ValueError(f"{name} vector length differs")
        mismatch_count = sum(
            left != right
            for left, right in zip(
                predicted_values,
                observed_values,
                strict=True,
            )
        )
        result[name] = {
            "componentCount": len(predicted_values),
            "mismatchedComponents": mismatch_count,
            "exact": mismatch_count == 0,
        }
    return result


def validate(
    path: Path,
    *,
    expected_geometry: str,
    expected_sample_indices: Sequence[int] = EXPECTED_SAMPLE_INDICES,
    classification: str = "prospective-unseen-geometry-holdout",
) -> dict[str, Any]:
    if expected_geometry not in EXPECTED_GEOMETRIES:
        raise ValueError(f"geometry is not a frozen holdout: {expected_geometry}")
    expected_samples = tuple(expected_sample_indices)
    if (
        not expected_samples
        or any(
            not isinstance(sample_index, int) or isinstance(sample_index, bool)
            for sample_index in expected_samples
        )
        or tuple(sorted(set(expected_samples))) != expected_samples
    ):
        raise ValueError("expected sample indices must be unique ascending integers")
    if not isinstance(classification, str) or not classification:
        raise ValueError("capture classification is empty")
    report = mapping(
        json.loads(path.read_text(encoding="utf-8")),
        "transition report",
    )
    geometry = mapping(report.get("geometry"), "geometry")
    uniforms = mapping(
        report.get("dynamicBackgroundUniforms"),
        "dynamicBackgroundUniforms",
    )
    untyped_records = uniforms.get("records")
    if (
        report.get("schemaVersion") != 5
        or report.get("material") != "clear"
        or report.get("appearance") != "light"
        or report.get("direction") != "materialize"
        or geometry.get("name") != expected_geometry
        or geometry.get("shape") != "circle"
        or uniforms.get("schemaVersion") != 7
        or uniforms.get("requested") is not True
        or uniforms.get("executed") is not True
        or uniforms.get("evidenceMode") != "allocation-metadata-v1"
        or uniforms.get("method") != EXPECTED_METHOD
        or uniforms.get("sampleIndices") != list(expected_samples)
        or uniforms.get("sampleCount") != len(expected_samples)
        or uniforms.get("executedSampleCount") != len(expected_samples)
        or uniforms.get("carrierCriticalPaths") != EXPECTED_CARRIER_CRITICAL_PATHS
        or not isinstance(untyped_records, list)
        or len(untyped_records) != len(expected_samples)
    ):
        raise ValueError("prospective allocation evidence is incomplete")
    matrix_basis = mapping(uniforms.get("matrixUniformBasis"), "matrixUniformBasis")
    if (
        matrix_basis.get("requested") is not False
        or matrix_basis.get("executed") is not False
    ):
        raise ValueError("allocation holdout executed matrix interventions")

    states: list[dict[str, Any]] = []
    for sample_index, untyped_record in zip(
        expected_samples,
        untyped_records,
        strict=True,
    ):
        record = mapping(untyped_record, f"sample {sample_index}")
        if (
            record.get("sampleIndex") != sample_index
            or record.get("freshStaticCarrier") is not True
            or record.get("detachedLayerTreeCopy") is not False
            or record.get("presentationLayerAssignedToCARenderer") is not False
            or record.get("backgroundFilterReplayedOnCarrier") is not True
            or record.get("foregroundFilterReplayedOnCarrier") is not False
            or record.get("installedCriticalCarrierPaths")
            != EXPECTED_CARRIER_CRITICAL_PATHS
            or record.get("missingCriticalCarrierPaths") != []
        ):
            raise ValueError(f"sample {sample_index} carrier replay differs")
        remaining = numeric(record.get("remaining"), "remaining")
        filter_values = mapping(
            mapping(record.get("filter"), "background filter").get("inputValues"),
            "background filter values",
        )
        if (
            numeric(filter_values.get("inputFaceOpacity"), "inputFaceOpacity")
            != remaining
        ):
            raise ValueError("remaining and inputFaceOpacity differ")
        scale, layer_state_count = captured_scale(record)
        expected_scale = 1.0 - remaining / 2.0
        scale_exact = scale == expected_scale
        prediction = predict_policy(
            geometry,
            remaining=remaining,
            scale=expected_scale,
        )
        observed = observed_policy(record, scale=scale)
        state_comparison = comparison(prediction, observed)
        states.append(
            {
                "sampleIndex": sample_index,
                "remaining": remaining,
                "runtimeScale": scale,
                "expectedRuntimeScale": expected_scale,
                "runtimeScaleLawExact": scale_exact,
                "capturedLayerStateCount": layer_state_count,
                "prediction": prediction,
                "observed": observed,
                "comparison": state_comparison,
            }
        )

    fields = (
        "cropOrigin",
        "textureCoordinateClamp",
        "producerExtent",
        "destinationExtent",
        "effectiveOrigin",
    )
    aggregate: dict[str, Any] = {}
    for name in fields:
        comparisons = [state["comparison"][name] for state in states]
        aggregate[name] = {
            "componentCount": sum(int(item["componentCount"]) for item in comparisons),
            "mismatchedComponents": sum(
                int(item["mismatchedComponents"]) for item in comparisons
            ),
            "exactEveryState": all(bool(item["exact"]) for item in comparisons),
        }
    runtime_scale_exact = all(bool(state["runtimeScaleLawExact"]) for state in states)
    allocation_exact = all(aggregate[name]["exactEveryState"] for name in fields[:-1])
    origin_exact = aggregate["effectiveOrigin"]["exactEveryState"]
    acceptance_passed = runtime_scale_exact and allocation_exact and origin_exact
    return {
        "dynamicAllocationHoldoutResultSchemaVersion": 1,
        "classification": classification,
        "timeline": str(path),
        "timelineSHA256": sha256_file(path),
        "geometry": dict(geometry),
        "sampleIndices": list(expected_samples),
        "states": states,
        "aggregate": {
            "stateCount": len(states),
            "runtimeScaleLawExactEveryState": runtime_scale_exact,
            **aggregate,
        },
        "acceptance": {
            "allowTolerance": False,
            "maximumMismatchedComponents": 0,
            "allocationPolicyExact": allocation_exact,
            "effectiveOriginPolicyExact": origin_exact,
            "passed": acceptance_passed,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--expected-geometry", required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = validate(
        arguments.report,
        expected_geometry=arguments.expected_geometry,
    )
    encoded = (
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
        print(arguments.output)
    return 0 if result["acceptance"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
