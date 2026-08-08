#!/usr/bin/env python3
"""Close the small-clear final-highlight topology and position/SDF geometry."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
import struct
from typing import Any

import analyze_combined_transition_geometry_holdout_falsification as opened
import analyze_current_circle_topology_and_clipping as current
import analyze_transition_geometry_corpus_local_macos_26_6_1 as model


type JsonObject = dict[str, Any]
type VertexPrefix = tuple[float, float, float, float, float, float]

RESULT_SCHEMA_VERSION = 1
TARGET_LAYER_PATH = (1, 0, 1, 0, 0, 0, 0)
PIPELINE = f"com.apple.coreanimation.{opened.SMALL_CLEAR_FINAL_HIGHLIGHT}"

OPENED_HOLDOUT_RESULT_SHA256 = (
    "a70ce8c2880def7df27f7dc298487676a3e083d45feb1cadad33f86d21a6555d"
)
CURRENT_CIRCLE_RESULT_SHA256 = (
    "795f87b31d000e89ced56bb3df0a39f395229924266d9460f944565820df5fd0"
)
TRANSFORM_PREREGISTRATION_SHA256 = (
    "cb24cdfdeefbb2f22664f1acf2d1bb606039d0a6708a0c5695bd5a09f4e94f6c"
)
TRANSFORM_TRACE_SHA256 = (
    "abc7bb2674b4bebe1bca114326ca20f14f6dc483be7eb054ace7c50c2d73723e"
)
TRANSFORM_STDOUT_SHA256 = (
    "3f198b3aa384c6f57026424d726232e56756ae9d1abb2cd194e89ff10a49e64f"
)
RETROSPECTIVE_TRACE_STDOUT_SHA256 = (
    "2d723395b3161644a8e0aecff60ad4c28c926d19d6957cfe1dc1eab25c7117d6"
)
FUNCTION_CODE_SHA256 = (
    "22273ad45369658b8e97b91893a488071a049d0bbdb6cdd7353a69355a1e83d3"
)
QUARTZCORE_UUID = "F1BA3189-E95A-3ECA-B59A-5A6872754484"

TIMELINES: tuple[tuple[str, str, str | None], ...] = (
    (
        "clear-dark-dematerialize-06",
        "0fb1572ce1822fa3a00da0cf37357ba7d923d60d21da85b6a14207bf20c3fe31",
        "combined-transition-geometry-holdout-7432ffa-run1",
    ),
    (
        "clear-light-materialize-01",
        "85dc1f54a54f86852ee46b1c611f8968b470c0551a4647c0f7b8a59030ccb016",
        "combined-transition-geometry-holdout-7432ffa-run1",
    ),
    (
        "local-small-clear-trace-v1",
        "1a8f841c09505c2917333cbfbb59d575951ddcb7307809a5361c262babf2154c",
        None,
    ),
    (
        "local-small-clear-sdf-transform-v1",
        "616f1f8c55efd12edfa600a6b018f773438895984cd9bd03339e2638627e356c",
        None,
    ),
)

EXPECTED_VERTEX_ATTRIBUTES = (
    {"bufferIndex": 1, "format": 31, "index": 0, "offset": 0},
    {"bufferIndex": 1, "format": 29, "index": 1, "offset": 16},
    {"bufferIndex": 1, "format": 29, "index": 2, "offset": 24},
    {"bufferIndex": 1, "format": 27, "index": 3, "offset": 32},
)
EXPECTED_STAGE_INPUTS = (
    (True, 0, 6, "position"),
    (True, 1, 4, "texcoord0"),
    (False, 2, 4, "texcoord1"),
    (True, 3, 19, "color"),
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


def small_axis_terms(extent: float) -> tuple[float, float, float, float]:
    """Return half, expanded half, recovered radius, and inner placement."""
    half = model.float32(extent / 2.0)
    outer = model.float32((extent + 18.0) / 2.0)
    radius = model.float32(outer - 9.0)
    inner_outer = model.float32(half + 9.0)
    return half, outer, radius, inner_outer


def inner_coordinates(outer: float, inner_outer: float) -> tuple[float, float]:
    """Return both inner coordinates, preserving Apple's two positive zeros."""
    magnitude = model.float32(outer - inner_outer)
    if magnitude == 0.0:
        return magnitude, magnitude
    return -magnitude, magnitude


def border_axis(
    raw_low: float,
    raw_high: float,
    extent: float,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    _, outer, _, inner_outer = small_axis_terms(extent)
    low_coordinate, high_coordinate = inner_coordinates(outer, inner_outer)
    return (
        (
            model.float32(raw_low),
            model.float32(raw_low + inner_outer),
            model.float32(raw_high - inner_outer),
            model.float32(raw_high),
        ),
        (-outer, low_coordinate, high_coordinate, outer),
    )


def layer_axes(
    record: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any], float, float, float, float]:
    states = model.layer_states(record)
    root = states[()]
    carrier = states[(1,)]
    element = states[TARGET_LAYER_PATH]
    width, height = model.vector(element.get("bounds"), "element bounds", 4)[2:4]
    carrier_position = model.vector(
        carrier.get("position"), "carrier position", 2
    )
    element_position = model.vector(
        element.get("position"), "element position", 2
    )
    root_height = model.vector(root.get("bounds"), "root bounds", 4)[3]
    origin_x = carrier_position[0] + element_position[0]
    origin_y = root_height - carrier_position[1] - element_position[1]
    return root, element, origin_x, origin_y, width, height


def predicted_geometry(
    record: Mapping[str, Any],
) -> tuple[str, list[VertexPrefix], tuple[int, ...]]:
    root, _, origin_x, origin_y, width, height = layer_axes(record)
    half_x, outer_x, radius_x, _ = small_axis_terms(width)
    half_y, outer_y, radius_y, _ = small_axis_terms(height)
    border = radius_x > half_x or radius_y > half_y

    raw_left = origin_x - 9.0
    raw_right = (origin_x + width) + 9.0
    raw_top = origin_y + 9.0
    raw_bottom = (origin_y - height) - 9.0

    if border:
        positions_x, coordinates_x = border_axis(raw_left, raw_right, width)
        # border_axis is low-to-high.  Screen-space Y is top-to-bottom.
        reversed_positions_y, coordinates_y = border_axis(
            raw_bottom, raw_top, height
        )
        positions_y = tuple(reversed(reversed_positions_y))
        vertices = [
            (x, y, 0.0, 1.0, coordinates_x[x_index], coordinates_y[y_index])
            for y_index, y in enumerate(positions_y)
            for x_index, x in enumerate(positions_x)
        ]
        return "border", vertices, model.FINAL_BORDER_INDICES

    root_bounds = model.vector(root.get("bounds"), "root bounds", 4)
    left, right, left_coordinate, right_coordinate = current.clip_axis(
        raw_left,
        raw_right,
        -outer_x,
        outer_x,
        0,
        int(root_bounds[2]),
    )
    bottom, top, bottom_coordinate, top_coordinate = current.clip_axis(
        raw_bottom,
        raw_top,
        outer_y,
        -outer_y,
        0,
        int(root_bounds[3]),
    )
    return (
        "quad",
        [
            (left, bottom, 0.0, 1.0, left_coordinate, bottom_coordinate),
            (right, bottom, 0.0, 1.0, right_coordinate, bottom_coordinate),
            (right, top, 0.0, 1.0, right_coordinate, top_coordinate),
            (left, top, 0.0, 1.0, left_coordinate, top_coordinate),
        ],
        model.FINAL_QUAD_INDICES,
    )


def validate_pipeline_descriptor(draw: Mapping[str, Any]) -> None:
    pipeline = model.mapping(draw.get("pipeline"), "small-clear pipeline")
    descriptor = model.mapping(
        pipeline.get("creationDescriptor"), "small-clear pipeline descriptor"
    )
    attributes = tuple(
        dict(model.mapping(value, "vertex attribute"))
        for value in model.sequence(
            descriptor.get("vertexAttributes"), "vertex attributes"
        )
    )
    stage_inputs = tuple(
        (
            value.get("active"),
            value.get("attributeIndex"),
            value.get("attributeType"),
            value.get("name"),
        )
        for raw in model.sequence(
            descriptor.get("vertexFunctionStageInputAttributes"),
            "vertex stage inputs",
        )
        for value in (model.mapping(raw, "vertex stage input"),)
    )
    layouts = tuple(
        dict(model.mapping(value, "vertex layout"))
        for value in model.sequence(descriptor.get("vertexLayouts"), "vertex layouts")
    )
    require(pipeline.get("label") == PIPELINE, "small-clear pipeline label differs")
    require(
        descriptor.get("fragmentFunction") == "TkfhA2Xhfc_Iscd"
        and descriptor.get("vertexFunction") == "VfxU10Xh",
        "small-clear shader identity differs",
    )
    require(attributes == EXPECTED_VERTEX_ATTRIBUTES, "vertex attributes differ")
    require(stage_inputs == EXPECTED_STAGE_INPUTS, "active vertex inputs differ")
    require(
        layouts
        == ({"index": 1, "stepFunction": 1, "stepRate": 1, "stride": 48},),
        "small-clear vertex layout differs",
    )


def observed_geometry(
    record: Mapping[str, Any],
) -> tuple[str, list[VertexPrefix], tuple[int, ...], bytes]:
    render = model.mapping(record.get("render"), "render record")
    probe = model.mapping(render.get("metalUniformProbe"), "Metal uniform probe")
    snapshots_record = model.mapping(
        render.get("metalBufferSnapshots"), "Metal buffer snapshots"
    )
    records = [
        model.mapping(value, "Metal record")
        for value in model.sequence(probe.get("records"), "Metal records")
        if model.pipeline_label(model.mapping(value, "Metal record")) == PIPELINE
    ]
    require(records, "state has no small-clear final pipeline")
    draw = model.single(
        [value for value in records if value.get("kind") == "drawIndexedPrimitives"],
        "small-clear indexed draw",
    )
    binding = model.single(
        [
            value
            for value in records
            if value.get("kind") in {"buffer", "bufferOffset"}
            and value.get("stage") == "vertex"
            and value.get("index") == 1
        ],
        "small-clear vertex binding",
    )
    validate_pipeline_descriptor(draw)
    index_count = model.integer(draw.get("indexCount"), "small-clear index count")
    require(
        draw.get("primitiveType") == 3
        and draw.get("indexType") == 0
        and index_count in {6, 24},
        "small-clear draw topology differs",
    )
    snapshots = [
        model.mapping(value, "Metal snapshot")
        for value in model.sequence(snapshots_record.get("snapshots"), "snapshots")
    ]
    vertex_snapshot = model.snapshot_at(
        snapshots,
        sequence_number=model.integer(binding.get("sequence"), "binding sequence"),
        stage="vertex",
        index=1,
        label=PIPELINE,
    )
    index_snapshot = model.snapshot_at(
        snapshots,
        sequence_number=model.integer(draw.get("sequence"), "draw sequence"),
        stage="index",
        index=-1,
        label=PIPELINE,
    )
    vertex_raw = model.payload(vertex_snapshot)
    index_raw = model.payload(index_snapshot)
    vertex_count = 4 if index_count == 6 else 16
    require(
        len(vertex_raw) >= 48 * vertex_count
        and len(index_raw) >= 2 * index_count,
        "small-clear retained buffer is truncated",
    )
    vertices = [
        struct.unpack_from("<6f", vertex_raw, index * 48)
        for index in range(vertex_count)
    ]
    indices = struct.unpack_from(f"<{index_count}H", index_raw)
    colors = b"".join(
        vertex_raw[index * 48 + 32 : index * 48 + 40]
        for index in range(vertex_count)
    )
    topology = "quad" if vertex_count == 4 else "border"
    return topology, vertices, indices, colors


def timeline_path(artifact_root: Path, name: str, parent: str | None) -> Path:
    if parent is None:
        return artifact_root / name / "transition-timeline.json"
    return artifact_root / parent / name / "transition-timeline.json"


def expected_timeline_case(name: str) -> Mapping[str, Any]:
    if name in opened.TIMELINE_SHA256:
        return opened.expected_case(name)
    return {
        "material": "clear",
        "appearance": "light",
        "direction": "materialize",
        "geometry": "circle-047-center",
        "records": 32,
    }


def validate_prerequisites(repository_root: Path) -> None:
    analysis = repository_root / "Analysis"
    for path, expected, label in (
        (
            analysis
            / "combined_transition_geometry_holdout_7432ffa_falsification_result.json",
            OPENED_HOLDOUT_RESULT_SHA256,
            "opened holdout result",
        ),
        (
            analysis / "current_circle_topology_and_clipping_result.json",
            CURRENT_CIRCLE_RESULT_SHA256,
            "current-circle result",
        ),
        (
            analysis / "small_clear_sdf_transform_retry_preregistration.json",
            TRANSFORM_PREREGISTRATION_SHA256,
            "transform preregistration",
        ),
    ):
        require(path.is_file(), f"missing {label}")
        require(sha256_file(path) == expected, f"{label} SHA-256 differs")


def analyze_transform_trace(
    artifact_root: Path,
    transform_timeline: Mapping[str, Any],
) -> JsonObject:
    directory = artifact_root / "local-small-clear-sdf-transform-v1"
    trace_path = directory / "sdf-transform-trace.json"
    stdout_path = directory / "lldb-stdout.txt"
    require(
        sha256_file(trace_path) == TRANSFORM_TRACE_SHA256,
        "transform trace SHA-256 differs",
    )
    require(
        sha256_file(stdout_path) == TRANSFORM_STDOUT_SHA256,
        "transform stdout SHA-256 differs",
    )
    trace = load_object(trace_path, "transform trace")
    records = [
        model.mapping(value, "transform record")
        for value in model.sequence(trace.get("records"), "transform records")
    ]
    code_gate = model.mapping(trace.get("codeGate"), "transform code gate")
    require(
        trace.get("smallClearSDFTransformRetryTraceSchemaVersion") == 1
        and trace.get("breakpointLocationCount") == 1
        and trace.get("failures") == []
        and len(records) == 64,
        "transform trace envelope differs",
    )
    require(
        code_gate.get("moduleUUID") == QUARTZCORE_UUID
        and code_gate.get("sha256") == FUNCTION_CODE_SHA256
        and code_gate.get("byteCount") == 2932,
        "transform trace code gate differs",
    )
    require(
        all(
            value.get("transformAddress") == 0
            and value.get("transformPrefixHex") == ""
            for value in records
        ),
        "small-clear trace contains a nonidentity transform branch",
    )

    final_records: list[Mapping[str, Any]] = []
    background_records = 0
    for value in records:
        registers = model.mapping(value.get("vectorRegisters"), "vector registers")
        v0 = model.mapping(registers.get("v0"), "v0")
        lanes = model.sequence(v0.get("binary32"), "v0 lanes")
        first = model.finite(lanes[0], "v0 first lane")
        if first == 9.0:
            require(value.get("booleanArgument") == 1, "final SDF role differs")
            final_records.append(value)
        elif first == 4096.0:
            require(value.get("booleanArgument") == 0, "background SDF role differs")
            background_records += 1
        else:
            raise ValueError("unexpected SDF entry scalar")
    require(
        len(final_records) == 32 and background_records == 32,
        "small-clear SDF role census differs",
    )
    timeline_records = model.validate_envelope(
        transform_timeline,
        expected_timeline_case("local-small-clear-sdf-transform-v1"),
    )
    shape_mismatches = 0
    for trace_record, timeline_record in zip(
        final_records, timeline_records, strict=True
    ):
        shape = bytes.fromhex(str(trace_record.get("shapePrefixHex")))
        require(len(shape) == 320, "shape prefix length differs")
        observed_half = struct.unpack_from("<f", shape, 0x100)[0]
        _, _, _, _, width, _ = layer_axes(timeline_record)
        predicted_half = model.float32(width / 2.0)
        shape_mismatches += (
            model.float32_bits(observed_half)
            != model.float32_bits(predicted_half)
        )
    require(shape_mismatches == 0, "shape half-extent witness differs")
    return {
        "recordCount": len(records),
        "finalCallCount": len(final_records),
        "backgroundCallCount": background_records,
        "nullTransformCount": len(records),
        "shapeHalfExtentComponents": len(final_records),
        "shapeHalfExtentMismatches": shape_mismatches,
        "quartzCoreUUID": QUARTZCORE_UUID,
        "functionCodeSHA256": FUNCTION_CODE_SHA256,
        "exact": True,
    }


def analyze(repository_root: Path) -> JsonObject:
    validate_prerequisites(repository_root)
    artifact_root = repository_root / "artifacts"
    retrospective_stdout = (
        artifact_root / "local-small-clear-trace-v1" / "lldb-stdout.txt"
    )
    require(
        sha256_file(retrospective_stdout) == RETROSPECTIVE_TRACE_STDOUT_SHA256,
        "retrospective call trace SHA-256 differs",
    )

    metrics: Counter[str] = Counter()
    topology_inventory: Counter[str] = Counter()
    source_results: list[JsonObject] = []
    observed_geometry_digest = hashlib.sha256()
    predicted_geometry_digest = hashlib.sha256()
    observed_index_digest = hashlib.sha256()
    predicted_index_digest = hashlib.sha256()
    observed_color_digest = hashlib.sha256()
    transform_timeline: Mapping[str, Any] | None = None

    for name, expected_sha256, parent in TIMELINES:
        path = timeline_path(artifact_root, name, parent)
        require(path.is_file(), f"missing timeline: {name}")
        require(sha256_file(path) == expected_sha256, f"timeline SHA-256 differs: {name}")
        timeline = load_object(path, f"{name} timeline")
        records = model.validate_envelope(timeline, expected_timeline_case(name))
        if name == "local-small-clear-sdf-transform-v1":
            transform_timeline = timeline
        source_inventory: Counter[str] = Counter()

        for record in records:
            if opened.SMALL_CLEAR_FINAL_HIGHLIGHT not in opened.pipeline_tokens(record):
                continue
            observed_topology, observed, observed_indices, colors = observed_geometry(
                record
            )
            predicted_topology, predicted, predicted_indices = predicted_geometry(
                record
            )
            require(
                len(observed) == len(predicted)
                and len(observed_indices) == len(predicted_indices),
                "small-clear component count differs",
            )
            metrics["stateCount"] += 1
            metrics["topologyPredicates"] += 1
            metrics["topologyMismatches"] += observed_topology != predicted_topology
            topology_inventory[observed_topology] += 1
            source_inventory[observed_topology] += 1

            for actual_vertex, predicted_vertex in zip(
                observed, predicted, strict=True
            ):
                metrics["geometryComponents"] += len(actual_vertex)
                metrics["geometryMismatches"] += sum(
                    model.float32_bits(actual) != model.float32_bits(expected)
                    for actual, expected in zip(
                        actual_vertex, predicted_vertex, strict=True
                    )
                )
                observed_geometry_digest.update(
                    struct.pack("<6f", *actual_vertex)
                )
                predicted_geometry_digest.update(
                    struct.pack("<6f", *predicted_vertex)
                )
            metrics["indexComponents"] += len(observed_indices)
            metrics["indexMismatches"] += sum(
                actual != expected
                for actual, expected in zip(
                    observed_indices, predicted_indices, strict=True
                )
            )
            observed_index_digest.update(
                struct.pack(f"<{len(observed_indices)}H", *observed_indices)
            )
            predicted_index_digest.update(
                struct.pack(f"<{len(predicted_indices)}H", *predicted_indices)
            )
            observed_color_digest.update(colors)
            metrics["activeColorHalfComponents"] += len(colors) // 2
            if observed_topology == "quad" and colors == bytes(len(colors)):
                metrics["quadAllZeroColorStates"] += 1

            _, element, _, _, width, _ = layer_axes(record)
            del element
            observed_outer = max(
                abs(value)
                for vertex in observed
                for value in vertex[4:6]
            )
            observed_radius = model.float32(observed_outer - 9.0)
            half, outer, exact_radius, _ = small_axis_terms(width)
            naive_radius = model.float32(
                model.float32(model.float32(half + 9.0) - 9.0)
            )
            for metric, candidate in (
                ("expandedBeforeHalfRadiusMatches", exact_radius),
                ("halfBeforeExpandRadiusMatches", naive_radius),
                ("directHalfRadiusMatches", half),
            ):
                metrics[metric] += (
                    model.float32_bits(candidate)
                    == model.float32_bits(observed_radius)
                )
            require(
                model.float32_bits(outer)
                == model.float32_bits(observed_outer),
                "small-clear observed outer radius differs",
            )

        source_results.append(
            {
                "name": name,
                "timelineSHA256": expected_sha256,
                "smallClearStateCount": sum(source_inventory.values()),
                "topologyInventory": dict(sorted(source_inventory.items())),
            }
        )

    require(transform_timeline is not None, "transform timeline was not analyzed")
    trace_result = analyze_transform_trace(artifact_root, transform_timeline)
    require(
        metrics["stateCount"] == 123
        and topology_inventory == Counter({"quad": 89, "border": 34})
        and metrics["topologyPredicates"] == 123
        and metrics["topologyMismatches"] == 0
        and metrics["geometryComponents"] == 5400
        and metrics["geometryMismatches"] == 0
        and metrics["indexComponents"] == 1350
        and metrics["indexMismatches"] == 0
        and metrics["expandedBeforeHalfRadiusMatches"] == 123
        and metrics["halfBeforeExpandRadiusMatches"] == 91
        and metrics["directHalfRadiusMatches"] == 60
        and metrics["quadAllZeroColorStates"] == 89,
        "small-clear exact metric census differs",
    )
    require(
        observed_geometry_digest.digest() == predicted_geometry_digest.digest()
        and observed_index_digest.digest() == predicted_index_digest.digest(),
        "small-clear reconstructed stream differs",
    )

    return {
        "smallClearFinalGeometryResultSchemaVersion": RESULT_SCHEMA_VERSION,
        "classification": (
            "hash-pinned retrospective exact geometry closure with a separately "
            "preregistered identity-transform witness"
        ),
        "status": "exact-small-clear-final-geometry-closure",
        "pipeline": PIPELINE,
        "stateCount": metrics["stateCount"],
        "sources": source_results,
        "topology": {
            "quadStateCount": topology_inventory["quad"],
            "borderStateCount": topology_inventory["border"],
            "predicateComponents": metrics["topologyPredicates"],
            "predicateMismatches": metrics["topologyMismatches"],
            "predicate": (
                "binary32(binary32((extent+18)/2)-9) > binary32(extent/2)"
            ),
            "exact": True,
        },
        "radiusDiscrimination": {
            "stateCount": metrics["stateCount"],
            "expandedBeforeHalfMatchCount": metrics[
                "expandedBeforeHalfRadiusMatches"
            ],
            "halfBeforeExpandMatchCount": metrics["halfBeforeExpandRadiusMatches"],
            "directHalfMatchCount": metrics["directHalfRadiusMatches"],
            "exactLaw": "binary32(binary32((extent+18)/2)-9)",
        },
        "metrics": {
            "positionAndSDFGeometry": {
                "componentCount": metrics["geometryComponents"],
                "mismatchedComponents": metrics["geometryMismatches"],
                "observedSHA256": observed_geometry_digest.hexdigest(),
                "predictedSHA256": predicted_geometry_digest.hexdigest(),
                "exact": True,
            },
            "indices": {
                "componentCount": metrics["indexComponents"],
                "mismatchedComponents": metrics["indexMismatches"],
                "observedSHA256": observed_index_digest.hexdigest(),
                "predictedSHA256": predicted_index_digest.hexdigest(),
                "exact": True,
            },
        },
        "identityTransformWitness": trace_result,
        "vertexLayout": {
            "strideBytes": 48,
            "positionFloat4Offset": 0,
            "sdfFloat2Offset": 16,
            "inactiveTexcoord1Float2Offset": 24,
            "activeColorHalf4Offset": 32,
            "activeColorHalfComponentCount": metrics["activeColorHalfComponents"],
            "quadAllZeroColorStateCount": metrics["quadAllZeroColorStates"],
            "activeColorObservedSHA256": observed_color_digest.hexdigest(),
            "activeColorPixelSemanticsClosed": False,
        },
        "geometryFamilyClosed": True,
        "smallClearFamilyClosed": False,
        "appleUnknownsBlockingGatedWalleIntegration": 0,
        "remainingAppleAlgorithmFamilies": [
            "small-clear Tghn/Tmua/Tkfh/A2Xghfc active shader, background, producer, composition, and pixel semantics"
        ],
        "remainingSmallClearSubBoundaries": [
            "Tkfh/A2Xghfc active half4 color, fragment uniforms, and exact pixel influence",
            "Tghn background construction and pixels",
            "Tmua/A2Xghfc producer/composition construction and pixels",
        ],
        "remainingProductProofs": [
            "Walle-shaped physical Retina color/compositor transfer",
            "fresh production-Walle frame with zero unequal bytes",
        ],
        "walleIntegrationMayBeginBehindGates": True,
        "universalCircleDomainParity": False,
        "productionParityAuthorized": False,
        "productionShaderChanged": False,
        "productionFlakeChanged": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = analyze(arguments.repository_root)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
