#!/usr/bin/env python3
"""Validate transition-time Apple final-highlight uniform evidence."""

import argparse
import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any


EXPECTED_SAMPLE_INDICES = (1, 4, 8, 12, 16, 20, 24, 28, 32)
DYNAMIC_PRODUCER_OUTPUT_EXTENTS = {
    1: frozenset({(576, 576)}),
    4: frozenset({(576, 576)}),
    8: frozenset({(576, 576)}),
    12: frozenset({(576, 576)}),
    16: frozenset({(576, 576)}),
    20: frozenset({(576, 576)}),
    24: frozenset({(512, 512)}),
    # Run 30746489805 landed just below k=7/8 and retained 512x512;
    # run 30745630876 landed just above it and allocated 512x448.
    28: frozenset({(512, 512), (512, 448)}),
    32: frozenset({(448, 448)}),
}
DYNAMIC_PRODUCER_INPUT_SHA256 = (
    "3ac65697c38c44ed6332911c83e2f13a0b4b6958df49fa88365fbe6327cc1f88"
)
DYNAMIC_PRODUCER_INPUT_FNV1A64 = "7e51eae7957578dd"
DYNAMIC_PRODUCER_MINIMUM_OUTPUT_PIXELS = 4_096
HIGHLIGHT_TRACE_SAMPLE_INDICES = frozenset({1, 12, 32})
BACKGROUND_ARITHMETIC_TRACES = {
    "sdf-float": ("sdf-float", 123, 1024 * 1024 * 16, 1, False),
    "sdf-geometry": ("sdf-geometry", 123, 1024 * 1024 * 16, 1, False),
    "sdf-oval": ("sdf-oval", 123, 1024 * 1024 * 16, 1, False),
    "sdf-normal": ("sdf-normal", 123, 1024 * 1024 * 16, 1, False),
    "sdf-coverage": ("sdf-coverage", 123, 1024 * 1024 * 16, 1, False),
    "sdf": ("sdf", 115, 1024 * 1024 * 8, 1, False),
    "color-stages-a": ("color-stages-a", 123, 1024 * 1024 * 16, 1, False),
    "color-stages-b": ("color-stages-b", 123, 1024 * 1024 * 16, 1, False),
    "final-color": ("final-color", 115, 1024 * 1024 * 8, 1, False),
}
BACKGROUND_ARITHMETIC_TRACES_BY_SAMPLE = {
    12: {
        **{
            name: BACKGROUND_ARITHMETIC_TRACES[name]
            for name in ("color-stages-a", "color-stages-b")
        },
        "holding-operands": (
            "holding-operands",
            123,
            1024 * 1024 * 16,
            1,
            False,
        ),
    },
    16: {
        **BACKGROUND_ARITHMETIC_TRACES,
        "private-main-final-color": (
            "captured-final-color",
            115,
            1024 * 1024 * 8,
            1,
            True,
        ),
        "private-shadow-final-color": (
            "captured-final-color",
            115,
            1024 * 1024 * 8,
            2,
            True,
        ),
        "custom-shadow-layer": (
            "shadow-layer",
            115,
            1024 * 1024 * 8,
            2,
            False,
        ),
        "custom-shadow-sample": (
            "shadow-sample",
            115,
            1024 * 1024 * 8,
            2,
            False,
        ),
    },
    24: {
        **BACKGROUND_ARITHMETIC_TRACES,
        "private-main-final-color": (
            "captured-final-color",
            115,
            1024 * 1024 * 8,
            1,
            True,
        ),
        "private-shadow-final-color": (
            "captured-final-color",
            115,
            1024 * 1024 * 8,
            2,
            True,
        ),
        "custom-shadow-layer": (
            "shadow-layer",
            115,
            1024 * 1024 * 8,
            2,
            False,
        ),
        "custom-shadow-sample": (
            "shadow-sample",
            115,
            1024 * 1024 * 8,
            2,
            False,
        ),
    },
}
HIGHLIGHT_SDF_DIAGNOSTIC_TRACES = {
    "sdf": (115, 1024 * 1024 * 8),
    "sdf-float": (123, 1024 * 1024 * 16),
    "sdf-geometry": (123, 1024 * 1024 * 16),
    "sdf-oval": (123, 1024 * 1024 * 16),
    "sdf-normal": (123, 1024 * 1024 * 16),
}
ALPHA_TOMOGRAPHY_CASES = frozenset(
    {
        "positive-normal-x",
        "negative-normal-x",
        "positive-normal-y",
        "negative-normal-y",
        "normalized-normal-x",
        "normalized-normal-y",
        "original-directional",
        "shifted-scaled-distance",
        "leading-coverage",
        "original-coverage",
    }
)
COMPOSITOR_TOMOGRAPHY_CASES = frozenset(
    {
        "zero-rgb-unit-alpha",
        "unit-rgb-unit-alpha",
        "identity-rgb-unit-alpha",
        "permuted-rgb-unit-alpha",
        "identity-rgb-destination-alpha",
        "asymmetric-constant-unit-alpha",
        "natural-rgb-unit-alpha",
    }
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


def mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} is not an object")
    return value


def numeric(value: object, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} is not numeric")
    return float(value)


def expected_foreground(remaining: float) -> dict[str, float]:
    removed = 1.0 - remaining
    return {
        "inputAberrationAmount": -5.0 * removed,
        "inputAberrationAngle": 0.5 * math.pi * removed,
        "inputAberrationHeight": 0.0,
        "inputAberrationOffset": 0.0,
        "inputEdgeEnd": 0.0,
        "inputEdgeOpacityEnd": removed,
        "inputEdgeOpacityStart": 0.0,
        "inputEdgeStart": 0.0,
        "inputRefractionAmount": 0.0,
        "inputRefractionHeight": 16.0 * removed,
        "inputRefractionOffset": -3.3 * removed,
    }


def fragment_name(binding: Mapping[str, Any]) -> str:
    pipeline = mapping(binding.get("pipeline"), "pipeline")
    descriptor = mapping(
        pipeline.get("creationDescriptor"),
        "pipeline creation descriptor",
    )
    return str(descriptor.get("fragmentFunction", ""))


def pipeline_label(binding: Mapping[str, Any]) -> str:
    pipeline = mapping(binding.get("pipeline"), "pipeline")
    return str(pipeline.get("label", ""))


def validate_highlight_binding(binding: Mapping[str, Any]) -> None:
    if binding.get("stage") != "fragment" or binding.get("index") != 1:
        raise ValueError("A2Xghfc binding uses an unexpected slot")
    payload = mapping(binding.get("payload"), "A2Xghfc payload")
    length = payload.get("lengthBytes")
    encoded = payload.get("hex")
    if (
        not isinstance(length, int)
        or length < 248
        or not isinstance(encoded, str)
        or len(encoded) != 2 * length
    ):
        raise ValueError("A2Xghfc payload is incomplete")


def validate_raw_file(
    record: Mapping[str, Any],
    *,
    root: Path,
    name: str,
) -> None:
    filename = record.get("rawFile")
    byte_count = record.get("rawBytes")
    if (
        record.get("rawCapture") is not True
        or not isinstance(filename, str)
        or not isinstance(byte_count, int)
        or byte_count <= 0
    ):
        raise ValueError(f"{name} raw capture is incomplete")
    path = root / filename
    if not path.is_file() or path.stat().st_size != byte_count:
        raise ValueError(f"{name} raw file differs: {path}")


def validate_interpolant_coverage(
    record: Mapping[str, Any],
    *,
    root: Path,
) -> None:
    filename = record.get("rawFile")
    if not isinstance(filename, str):
        raise ValueError("dynamic exactInterpolant filename differs")
    words = memoryview((root / filename).read_bytes()).cast("I")
    expected_pixels = 1024 * 1024
    if len(words) != expected_pixels * 4:
        raise ValueError("dynamic exactInterpolant word count differs")
    active = [
        pixel
        for pixel in range(expected_pixels)
        if any(words[pixel * 4 + channel] for channel in range(4))
    ]
    if not active:
        raise ValueError("dynamic exactInterpolant is empty")
    minimum_x = min(pixel % 1024 for pixel in active)
    maximum_x = max(pixel % 1024 for pixel in active)
    minimum_y = min(pixel // 1024 for pixel in active)
    maximum_y = max(pixel // 1024 for pixel in active)
    if (
        len(active) < 600_000
        or maximum_x - minimum_x + 1 < 760
        or maximum_y - minimum_y + 1 < 760
    ):
        raise ValueError(
            "dynamic exactInterpolant coverage is degenerate: "
            f"{len(active)} pixels, "
            f"x={minimum_x}...{maximum_x}, "
            f"y={minimum_y}...{maximum_y}"
        )


def validate_interpolant_pull_trace(
    record: Mapping[str, Any],
    *,
    root: Path,
) -> None:
    tile_count = 32
    axis_count = 2
    primitive_count = 2
    pull_count = 16
    component_count = 4
    record_words = 3 + pull_count * component_count
    expected_words = tile_count * axis_count * primitive_count * record_words
    if (
        record.get("schemaVersion") != 1
        or record.get("tileCount") != tile_count
        or record.get("axisCount") != axis_count
        or record.get("primitiveCount") != primitive_count
        or record.get("pullCount") != pull_count
        or record.get("componentCount") != component_count
        or record.get("recordWords") != record_words
        or record.get("recordOrdering") != "axis-major,primitive-major,tile-major"
        or record.get("rawBytes") != expected_words * 4
    ):
        raise ValueError("dynamic interpolant pull-trace layout differs")
    validate_raw_file(
        record,
        root=root,
        name="dynamic interpolant pull trace",
    )
    filename = record.get("rawFile")
    if not isinstance(filename, str):
        raise ValueError("dynamic interpolant pull-trace filename differs")
    words = memoryview((root / filename).read_bytes()).cast("I")
    if len(words) != expected_words:
        raise ValueError("dynamic interpolant pull-trace word count differs")

    captured_by_axis_primitive = [[0, 0], [0, 0]]
    for axis in range(axis_count):
        for primitive in range(primitive_count):
            for tile in range(tile_count):
                slot = (axis * primitive_count + primitive) * tile_count + tile
                base = slot * record_words
                state = words[base]
                if state == 0xFFFF_FFFF:
                    continue
                if state == 0xFFFF_FFFE:
                    raise ValueError("dynamic interpolant pull trace retained a lock")
                x = words[base + 1]
                y = words[base + 2]
                coordinate = x if axis == 0 else y
                payload = words[base + 3 : base + record_words]
                if (
                    x >= 1024
                    or y >= 1024
                    or state != y * 1024 + x
                    or coordinate // 32 != tile
                    or any(word & 0x7F80_0000 == 0x7F80_0000 for word in payload)
                ):
                    raise ValueError("dynamic interpolant pull-trace record differs")
                captured_by_axis_primitive[axis][primitive] += 1
    if any(
        count < 24
        for axis_counts in captured_by_axis_primitive
        for count in axis_counts
    ):
        raise ValueError(
            "dynamic interpolant pull-trace coverage is incomplete: "
            f"{captured_by_axis_primitive}"
        )


def validate_interpolant_trace(
    trace: Mapping[str, Any],
    *,
    root: Path,
) -> None:
    interpolant = mapping(
        trace.get("exactInterpolant"),
        "exactInterpolant",
    )
    interpolant_output = mapping(
        interpolant.get("output"),
        "exactInterpolant output",
    )
    if (
        interpolant.get("executed") is not True
        or interpolant_output.get("width") != 1024
        or interpolant_output.get("height") != 1024
        or interpolant_output.get("pixelFormat") != 123
        or interpolant_output.get("rawBytes") != 1024 * 1024 * 16
        or "auxiliaryOutput" in interpolant
    ):
        raise ValueError("dynamic exactInterpolant layout differs")
    validate_raw_file(
        interpolant_output,
        root=root,
        name="dynamic exactInterpolant",
    )
    validate_interpolant_coverage(
        interpolant_output,
        root=root,
    )
    validate_interpolant_pull_trace(
        mapping(
            interpolant.get("pullTrace"),
            "exactInterpolant pullTrace",
        ),
        root=root,
    )
    pipeline = mapping(
        trace.get("interpolantPipeline"),
        "interpolantPipeline",
    )
    candidates = pipeline.get("candidates")
    expected_candidate_order = ["custom-stage-in-vertex"]
    if (
        pipeline.get("executed") is not True
        or not isinstance(pipeline.get("selectedCandidate"), str)
        or not isinstance(candidates, list)
        or not candidates
        or len(candidates) != len(expected_candidate_order)
        or any(not isinstance(candidate, Mapping) for candidate in candidates)
    ):
        raise ValueError("dynamic interpolant pipeline differs")
    typed_candidates = [
        mapping(candidate, "interpolant candidate") for candidate in candidates
    ]
    if (
        [candidate.get("name") for candidate in typed_candidates]
        != expected_candidate_order
        or any(
            not isinstance(candidate.get("descriptor"), Mapping)
            for candidate in typed_candidates
        )
        or any(
            candidate.get("built") is not False for candidate in typed_candidates[:-1]
        )
        or typed_candidates[-1].get("built") is not True
        or pipeline.get("selectedCandidate") != typed_candidates[-1].get("name")
        or pipeline.get("selectedLabel")
        != "lg.final-highlight-interpolant-" + str(pipeline.get("selectedCandidate"))
    ):
        raise ValueError("dynamic interpolant pipeline differs")
    selected_name = str(pipeline["selectedCandidate"])
    selected_descriptor = mapping(
        typed_candidates[-1].get("descriptor"),
        "selected interpolant descriptor",
    )
    private_vertex_selected = selected_name.startswith("captured-private-vertex-")
    if (
        pipeline.get("capturedPrivateVertexUnmodified") is not private_vertex_selected
        or (
            private_vertex_selected
            and (
                selected_descriptor.get("vertexFunction") != "VfxXgh"
                or selected_descriptor.get("vertexAttributes") != []
                or selected_descriptor.get("vertexLayouts") != []
            )
        )
        or (
            not private_vertex_selected
            and (
                selected_name != "custom-stage-in-vertex"
                or selected_descriptor.get("vertexAttributes")
                != [
                    {"bufferIndex": 1, "format": 31, "index": 0, "offset": 0},
                    {"bufferIndex": 1, "format": 29, "index": 1, "offset": 16},
                    {"bufferIndex": 1, "format": 29, "index": 2, "offset": 24},
                ]
                or selected_descriptor.get("vertexLayouts")
                != [
                    {
                        "index": 1,
                        "stepFunction": 1,
                        "stepRate": 1,
                        "stride": 48,
                    }
                ]
            )
        )
    ):
        raise ValueError("dynamic interpolant pipeline differs")


def validate_interpolant_only_trace(
    replay: Mapping[str, Any],
    *,
    root: Path,
) -> None:
    trace = mapping(
        replay.get("finalHighlightInterpolantTrace"),
        "finalHighlightInterpolantTrace",
    )
    if (
        trace.get("schemaVersion") != 1
        or trace.get("executed") is not True
        or trace.get("scope") != "custom-stage-in-interpolant-only"
        or trace.get("capturedPrivateVertexUnmodified") is not False
        or trace.get("selectedLastA2XghfcDraw") is not True
    ):
        raise ValueError("dynamic interpolant-only trace differs")
    validate_interpolant_trace(trace, root=root)


def validate_background_interpolant_trace(
    replay: Mapping[str, Any],
    *,
    root: Path,
    sample_index: int,
) -> None:
    trace = mapping(
        replay.get("backgroundInterpolantTrace"),
        "backgroundInterpolantTrace",
    )
    main = mapping(trace.get("mainReplay"), "background main interpolant replay")
    main_output = mapping(
        main.get("output"),
        "background main interpolant output",
    )
    combined = mapping(
        trace.get("combinedReplay"),
        "background combined interpolant replay",
    )
    combined_output = mapping(
        combined.get("output"),
        "background combined interpolant output",
    )
    build = mapping(trace.get("pipelineBuild"), "background pipeline build")
    numeric_traces = build.get("numericTraces")
    expected_numeric_traces = {
        "interpolant": 123,
        **(
            {
                metadata[0]: metadata[1]
                for metadata in (
                    BACKGROUND_ARITHMETIC_TRACES_BY_SAMPLE.get(
                        sample_index,
                        {},
                    ).values()
                )
            }
            if sample_index in BACKGROUND_ARITHMETIC_TRACES_BY_SAMPLE
            else {}
        ),
    }
    observed_numeric_traces = (
        {item.get("name"): item for item in numeric_traces if isinstance(item, Mapping)}
        if isinstance(numeric_traces, list)
        else {}
    )
    if (
        trace.get("schemaVersion") != 1
        or trace.get("executed") is not True
        or trace.get("scope") != "all-dynamic-background-states"
        or trace.get("capturedAppleFunctionUnmodified") is not False
        or trace.get("customStageInVertex") is not True
        or trace.get("prospectiveReplay") != "main-only"
        or trace.get("diagnosticReplay") != "main-plus-shadow"
        or main.get("executed") is not True
        or main.get("glassDrawCount") != 1
        or combined.get("executed") is not True
        or combined.get("glassDrawCount") != 2
        or not isinstance(numeric_traces, list)
        or len(numeric_traces) != len(expected_numeric_traces)
        or set(observed_numeric_traces) != set(expected_numeric_traces)
        or any(
            observed_numeric_traces[name].get("built") is not True
            or observed_numeric_traces[name].get("pixelFormat") != pixel_format
            for name, pixel_format in expected_numeric_traces.items()
        )
    ):
        raise ValueError("dynamic background interpolant trace differs")
    for output, name in (
        (main_output, "dynamic background main interpolant"),
        (combined_output, "dynamic background combined interpolant"),
    ):
        if (
            output.get("width") != 1024
            or output.get("height") != 1024
            or output.get("pixelFormat") != 123
            or output.get("rawBytes") != 1024 * 1024 * 16
        ):
            raise ValueError(f"{name} layout differs")
        validate_raw_file(output, root=root, name=name)


def validate_background_arithmetic_trace(
    replay: Mapping[str, Any],
    *,
    root: Path,
    sample_index: int,
) -> int:
    expected_traces = BACKGROUND_ARITHMETIC_TRACES_BY_SAMPLE.get(sample_index)
    if expected_traces is None:
        if "backgroundArithmeticTrace" in replay:
            raise ValueError("an unrequested background arithmetic trace executed")
        return 0

    trace = mapping(
        replay.get("backgroundArithmeticTrace"),
        "backgroundArithmeticTrace",
    )
    replays = trace.get("replays")
    expected_contains_private = any(
        metadata[4] for metadata in expected_traces.values()
    )
    if (
        trace.get("schemaVersion") != 2
        or trace.get("executed") is not True
        or trace.get("scope")
        != "selected-dynamic-states-main-and-shadow-stage-isolation"
        or trace.get("containsCapturedAppleFunctionUnmodified")
        is not expected_contains_private
        or trace.get("containsCustomStageInVertex") is not True
        or trace.get("classification")
        != "diagnostic private/custom Metal arithmetic replay"
        or not isinstance(replays, list)
        or len(replays) != len(expected_traces)
    ):
        raise ValueError("dynamic background arithmetic trace differs")

    observed = {item.get("name"): item for item in replays if isinstance(item, Mapping)}
    if set(observed) != set(expected_traces):
        raise ValueError("dynamic background arithmetic trace names differ")
    for name, metadata in expected_traces.items():
        pipeline_name, pixel_format, byte_count, draw_ordinal, captured = metadata
        wrapper = mapping(observed[name], f"background arithmetic {name}")
        numeric_replay = mapping(
            wrapper.get("replay"),
            f"background arithmetic {name} replay",
        )
        output = mapping(
            numeric_replay.get("output"),
            f"background arithmetic {name} output",
        )
        if (
            wrapper.get("pipelineName") != pipeline_name
            or wrapper.get("drawOrdinal") != draw_ordinal
            or wrapper.get("capturedAppleFunctionUnmodified") is not captured
            or wrapper.get("customStageInVertex") is not (not captured)
            or wrapper.get("pixelFormat") != pixel_format
            or numeric_replay.get("executed") is not True
            or numeric_replay.get("glassDrawCount") != 1
            or output.get("width") != 1024
            or output.get("height") != 1024
            or output.get("pixelFormat") != pixel_format
            or output.get("rawBytes") != byte_count
            or "auxiliaryOutput" in numeric_replay
        ):
            raise ValueError(f"dynamic background arithmetic {name} differs")
        validate_raw_file(
            output,
            root=root,
            name=f"dynamic background arithmetic {name}",
        )
    return len(expected_traces)


def validate_background_private_layer_outputs(
    replay: Mapping[str, Any],
    *,
    root: Path,
    sample_index: int,
) -> int:
    if sample_index not in {16, 24}:
        if "backgroundPrivateLayerOutputs" in replay:
            raise ValueError("an unrequested private background layer replay executed")
        return 0

    layers = mapping(
        replay.get("backgroundPrivateLayerOutputs"),
        "backgroundPrivateLayerOutputs",
    )
    if (
        layers.get("schemaVersion") != 1
        or layers.get("executed") is not True
        or layers.get("capturedAppleFunctionUnmodified") is not True
        or layers.get("targetPixelFormat") != 80
        or layers.get("initialColor") != "captured pre-glass color"
    ):
        raise ValueError("private background layer replay differs")

    raw_files: set[str] = set()
    for name in ("main", "shadow"):
        layer = mapping(layers.get(name), f"private background {name}")
        output = mapping(
            layer.get("output"),
            f"private background {name} output",
        )
        if (
            layer.get("executed") is not True
            or layer.get("glassDrawCount") != 1
            or not isinstance(layer.get("encodedCommandCount"), int)
            or layer["encodedCommandCount"] <= 0
            or layer.get("stoppedAfterGlass") is not False
            or output.get("width") != 1024
            or output.get("height") != 1024
            or output.get("pixelFormat") != 80
            or output.get("rawBytes") != 1024 * 1024 * 4
        ):
            raise ValueError(f"private background {name} replay differs")
        validate_raw_file(
            output,
            root=root,
            name=f"private background {name}",
        )
        raw_file = output.get("rawFile")
        if not isinstance(raw_file, str):
            raise ValueError(f"private background {name} filename is absent")
        raw_files.add(raw_file)
    if len(raw_files) != 2:
        raise ValueError("private background layer outputs are not independent")
    return 2


def validate_raw_render_evidence(
    render: Mapping[str, Any],
    *,
    root: Path,
) -> None:
    output = mapping(render.get("output"), "CARenderer output")
    validate_raw_file(output, root=root, name="CARenderer output")
    replay = mapping(render.get("exactPassReplay"), "exactPassReplay")
    if (
        replay.get("executed") is not True
        or replay.get("exactByteMatch") is not True
        or replay.get("mismatchedByteCount") != 0
        or replay.get("mismatchedPixelCount") != 0
        or replay.get("maximumChannelDelta") != 0
        or not isinstance(replay.get("commandCount"), int)
        or replay["commandCount"] <= 0
        or not isinstance(replay.get("encodedCommandCount"), int)
        or replay["encodedCommandCount"] != replay["commandCount"]
        or not isinstance(replay.get("glassDrawCount"), int)
        or replay["glassDrawCount"] != 2
    ):
        raise ValueError("exact final-pass replay differs")
    validate_raw_file(
        mapping(replay.get("preFinalPass"), "preFinalPass"),
        root=root,
        name="pre-final-pass",
    )
    validate_raw_file(
        mapping(replay.get("replayOutput"), "replayOutput"),
        root=root,
        name="exact-pass replay output",
    )
    final_input = mapping(
        replay.get("finalHighlightInputReference"),
        "finalHighlightInputReference",
    )
    if (
        final_input.get("executed") is not True
        or final_input.get("glassDrawCount") != 2
        or final_input.get("stoppedAfterGlass") is not False
    ):
        raise ValueError("pre-final-highlight replay differs")
    final_input_output = mapping(
        final_input.get("output"),
        "finalHighlightInput output",
    )
    if (
        final_input_output.get("width") != 1024
        or final_input_output.get("height") != 1024
        or final_input_output.get("pixelFormat") != 80
        or final_input_output.get("rawBytes") != 1024 * 1024 * 4
    ):
        raise ValueError("pre-final-highlight output layout differs")
    validate_raw_file(
        final_input_output,
        root=root,
        name="pre-final-highlight output",
    )
    independent = mapping(
        replay.get("independentGlassReplay"),
        "independentGlassReplay",
    )
    glass_prefix = mapping(independent.get("reference"), "glass-prefix reference")
    glass_prefix_output = mapping(
        glass_prefix.get("output"),
        "glass-prefix output",
    )
    validate_raw_file(
        glass_prefix_output,
        root=root,
        name="glass-prefix output",
    )
    glass_prefix_path = root / str(glass_prefix_output["rawFile"])
    final_input_path = root / str(final_input_output["rawFile"])
    if glass_prefix_path.read_bytes() != final_input_path.read_bytes():
        raise ValueError("commands between glass and highlight changed attachment zero")
    textures = mapping(
        render.get("metalTextureSnapshots"),
        "metalTextureSnapshots",
    )
    snapshots = textures.get("snapshots")
    if not isinstance(snapshots, list):
        raise ValueError("texture snapshots are not a list")
    sources = [
        mapping(snapshot, "source texture")
        for snapshot in snapshots
        if isinstance(snapshot, Mapping)
        and snapshot.get("pixelFormat") == 80
        and type(snapshot.get("mipmapLevelCount")) is int
        and snapshot["mipmapLevelCount"] >= 2
        and snapshot.get("index") == 3
        and fragment_name(snapshot).startswith("glass_background")
    ]
    if len(sources) != 1:
        raise ValueError("the complete backdrop pyramid is not unique")
    source = sources[0]
    width = source.get("width")
    height = source.get("height")
    if (
        not isinstance(width, int)
        or not isinstance(height, int)
        or width <= 0
        or height <= 0
    ):
        raise ValueError("backdrop pyramid dimensions are invalid")
    validate_raw_file(source, root=root, name="backdrop mip zero")
    base_raw = (root / str(source["rawFile"])).read_bytes()
    if (
        not any(base_raw)
        or len(set(memoryview(base_raw).cast("I")))
        < DYNAMIC_PRODUCER_MINIMUM_OUTPUT_PIXELS
    ):
        raise ValueError("controlled backdrop mip zero is degenerate")
    mips = source.get("mipSnapshots")
    if not isinstance(mips, list) or [
        mip.get("level") for mip in mips if isinstance(mip, Mapping)
    ] != list(range(source["mipmapLevelCount"])):
        raise ValueError("backdrop pyramid levels differ")
    for mip in mips:
        typed_mip = mapping(mip, "backdrop mip")
        level = typed_mip.get("level")
        expected_width = max(1, width >> int(level))
        expected_height = max(1, height >> int(level))
        if (
            typed_mip.get("width") != expected_width
            or typed_mip.get("height") != expected_height
            or typed_mip.get("bytesPerRow") != 4 * expected_width
            or typed_mip.get("rawBytes") != 4 * expected_width * expected_height
        ):
            raise ValueError(f"backdrop mip {level} layout differs")
        validate_raw_file(
            typed_mip,
            root=root,
            name=f"backdrop mip {level}",
        )


def validate_dynamic_backdrop_producer(
    render: Mapping[str, Any],
    *,
    root: Path,
    sample_index: int,
) -> None:
    evidence = mapping(
        render.get("dynamicBackdropProducerBoundary"),
        "dynamicBackdropProducerBoundary",
    )
    untyped_boundaries = evidence.get("records")
    if (
        evidence.get("schemaVersion") != 2
        or evidence.get("boundaryCount") != 1
        or not isinstance(untyped_boundaries, list)
        or len(untyped_boundaries) != 1
    ):
        raise ValueError("dynamic backdrop producer boundary is incomplete")
    boundary = mapping(
        untyped_boundaries[0],
        "dynamic backdrop producer boundary",
    )
    expected_capture = f"transition-background-uniform-{sample_index:02d}"
    if (
        render.get("capture") != expected_capture
        or evidence.get("capture") != expected_capture
        or boundary.get("index") != 0
        or boundary.get("capturePoint")
        != "controlled-input-before-producer-draw-and-blit-after-"
        "producer-render-before-copy-base-compute"
    ):
        raise ValueError("dynamic backdrop capture point differs")

    intervention = mapping(
        boundary.get("inputIntervention"),
        "dynamic backdrop producer input intervention",
    )
    original_input_address = intervention.get("originalInputAddress")
    replacement_input_address = intervention.get("replacementInputAddress")
    if (
        intervention.get("schemaVersion") != 1
        or intervention.get("name") != "opaque-coordinate-hash-v1"
        or intervention.get("applied") is not True
        or not isinstance(original_input_address, str)
        or replacement_input_address != boundary.get("producerInputAddress")
        or original_input_address == replacement_input_address
        or intervention.get("pixelFormat") != 80
        or intervention.get("width") != 1024
        or intervention.get("height") != 1024
        or intervention.get("bytesPerRow") != 4096
        or intervention.get("rawBytes") != 1024 * 1024 * 4
        or intervention.get("sha256") != DYNAMIC_PRODUCER_INPUT_SHA256
        or intervention.get("fnv1a64") != DYNAMIC_PRODUCER_INPUT_FNV1A64
        or intervention.get("alpha") != 255
        or intervention.get("channelOrder") != "BGRA"
    ):
        raise ValueError("dynamic backdrop input intervention differs")

    probe = mapping(render.get("metalUniformProbe"), "metalUniformProbe")
    records = probe.get("records")
    if not isinstance(records, list):
        raise ValueError("Metal uniform records are incomplete")
    typed_records = [mapping(record, "Metal uniform record") for record in records]
    copy_sources = [
        record
        for record in typed_records
        if record.get("kind") == "texture"
        and record.get("stage") == "compute"
        and record.get("index") == 0
        and pipeline_label(record)
        == "com.apple.coreanimation.variable_blur_copy_base_mip_compute"
    ]
    if len(copy_sources) != 1:
        raise ValueError("copy-base producer output binding is not unique")
    copy_source = copy_sources[0]
    copy_source_texture = mapping(
        copy_source.get("texture"),
        "copy-base producer output texture",
    )
    source_address = copy_source_texture.get("address")
    if (
        not isinstance(source_address, str)
        or boundary.get("copyBaseEncoder") != copy_source.get("encoder")
        or boundary.get("copyBaseBindingSequence") != copy_source.get("sequence")
        or boundary.get("producerOutputAddress") != source_address
    ):
        raise ValueError("copy-base producer output has no address")

    def color_zero_attachment(
        record: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        attachments = record.get("colorAttachments")
        if not isinstance(attachments, list):
            return None
        for untyped_attachment in attachments:
            attachment = mapping(
                untyped_attachment,
                "render-pass color attachment",
            )
            if attachment.get("index") != 0:
                continue
            return attachment
        return None

    def color_zero_address(record: Mapping[str, Any]) -> object:
        attachment = color_zero_attachment(record)
        if attachment is None:
            return None
        texture = mapping(
            attachment.get("texture"),
            "render-pass color texture",
        )
        return texture.get("address")

    producer_passes = [
        record
        for record in typed_records
        if record.get("kind") == "renderPass"
        and color_zero_address(record) == source_address
    ]
    if len(producer_passes) != 1:
        raise ValueError("render pass producing copy-base input is not unique")
    producer_pass = producer_passes[0]
    producer_encoder = producer_pass.get("encoder")
    producer_attachment = color_zero_attachment(producer_pass)
    producer_command_buffer = producer_pass.get("commandBuffer")
    copy_base_command_buffers = {
        record.get("commandBuffer")
        for record in typed_records
        if record.get("kind") == "computeEncoder"
        and record.get("encoder") == copy_source.get("encoder")
        and isinstance(record.get("commandBuffer"), str)
    }
    if (
        producer_attachment is None
        or producer_attachment.get("loadAction") != 2
        or producer_attachment.get("storeAction") != 1
        or not isinstance(producer_command_buffer, str)
        or copy_base_command_buffers != {producer_command_buffer}
        or boundary.get("producerEncoder") != producer_encoder
        or boundary.get("producerRenderPassSequence") != producer_pass.get("sequence")
    ):
        raise ValueError("dynamic backdrop producer pass join differs")
    producer_inputs = [
        record
        for record in typed_records
        if record.get("kind") == "texture"
        and record.get("stage") == "fragment"
        and record.get("index") == 3
        and record.get("encoder") == producer_encoder
    ]
    if len(producer_inputs) != 1:
        raise ValueError("dynamic backdrop producer input is not unique")
    producer_input = producer_inputs[0]
    input_address = producer_input.get("address")
    producer_input_sequence = producer_input.get("sequence")
    producer_pass_sequence = producer_pass.get("sequence")
    copy_base_sequence = copy_source.get("sequence")
    if (
        fragment_name(producer_input) not in {"A2Xghfc", "TimgA2Xhfc_Isrc"}
        or not isinstance(input_address, str)
        or boundary.get("producerInputAddress") != input_address
        or boundary.get("producerInputBindingSequence") != producer_input_sequence
        or not isinstance(producer_pass_sequence, int)
        or not isinstance(producer_input_sequence, int)
        or not isinstance(copy_base_sequence, int)
        or not (producer_pass_sequence < producer_input_sequence < copy_base_sequence)
    ):
        raise ValueError("dynamic backdrop producer input join differs")

    producer_output_snapshot = mapping(
        boundary.get("output"),
        "dynamic backdrop producer output snapshot",
    )
    producer_input_snapshot = mapping(
        boundary.get("input"),
        "dynamic backdrop producer input snapshot",
    )
    if (
        (producer_input.get("width"), producer_input.get("height")) != (1024, 1024)
        or producer_input.get("storageMode") != 0
        or (
            copy_source_texture.get("width"),
            copy_source_texture.get("height"),
        )
        not in DYNAMIC_PRODUCER_OUTPUT_EXTENTS[sample_index]
    ):
        raise ValueError("dynamic backdrop producer extent differs")
    for name, snapshot, descriptor in (
        (
            "dynamic backdrop producer output",
            producer_output_snapshot,
            copy_source_texture,
        ),
        (
            "dynamic backdrop producer input",
            producer_input_snapshot,
            producer_input,
        ),
    ):
        width = descriptor.get("width")
        height = descriptor.get("height")
        if (
            not isinstance(width, int)
            or not isinstance(height, int)
            or not 0 < width <= 1024
            or not 0 < height <= 1024
            or descriptor.get("pixelFormat") != 80
            or descriptor.get("mipmapLevelCount") != 1
            or descriptor.get("depth") != 1
            or descriptor.get("arrayLength") != 1
            or descriptor.get("sampleCount") != 1
            or snapshot.get("width") != width
            or snapshot.get("height") != height
            or snapshot.get("pixelFormat") != 80
            or snapshot.get("mipmapLevelCount") != 1
            or snapshot.get("depth") != 1
            or snapshot.get("arrayLength") != 1
            or snapshot.get("sampleCount") != 1
            or snapshot.get("rawBytes") != width * height * 4
            or snapshot.get("bytesPerRow") != width * 4
        ):
            raise ValueError(f"{name} layout differs")
        validate_raw_file(snapshot, root=root, name=name)
        raw_path = root / str(snapshot["rawFile"])
        raw = raw_path.read_bytes()
        if name == "dynamic backdrop producer input":
            if hashlib.sha256(raw).hexdigest() != DYNAMIC_PRODUCER_INPUT_SHA256:
                raise ValueError("dynamic backdrop controlled input differs")
        elif (
            not any(raw)
            or len(set(memoryview(raw).cast("I")))
            < DYNAMIC_PRODUCER_MINIMUM_OUTPUT_PIXELS
        ):
            raise ValueError("dynamic backdrop producer output is degenerate")


def validate_highlight_trace(
    replay: Mapping[str, Any],
    *,
    root: Path,
    sample_index: int,
) -> None:
    trace = mapping(
        replay.get("finalHighlightAlphaTrace"),
        "finalHighlightAlphaTrace",
    )
    comparison = mapping(
        trace.get("capturedVsRebuiltBGRA8"),
        "capturedVsRebuiltBGRA8",
    )
    if (
        trace.get("schemaVersion") != 2
        or trace.get("executed") is not True
        or trace.get("diagnosticScope") != "full"
        or trace.get("capturedAppleFunctionUnmodified") is not True
        or trace.get("selectedLastA2XghfcDraw") is not True
        or comparison.get("compared") is not True
        or comparison.get("exactByteMatch") is not True
        or comparison.get("mismatchedByteCount") != 0
        or comparison.get("mismatchedPixelCount") != 0
        or comparison.get("maximumChannelDelta") != 0
    ):
        raise ValueError("dynamic final-highlight trace differs")
    for key, pixel_format, byte_count in (
        ("capturedBGRA8", 80, 1024 * 1024 * 4),
        ("rebuiltBGRA8", 80, 1024 * 1024 * 4),
        ("exactHalfAlpha", 115, 1024 * 1024 * 8),
    ):
        render = mapping(trace.get(key), key)
        output = mapping(render.get("output"), f"{key} output")
        if (
            render.get("executed") is not True
            or output.get("width") != 1024
            or output.get("height") != 1024
            or output.get("pixelFormat") != pixel_format
            or output.get("rawBytes") != byte_count
            or "auxiliaryOutput" in render
        ):
            raise ValueError(f"dynamic {key} layout differs")
        validate_raw_file(output, root=root, name=f"dynamic {key}")
    validate_interpolant_trace(trace, root=root)

    for key in ("exactKeyHalfAlpha", "exactFillHalfAlpha"):
        render = mapping(trace.get(key), key)
        output = mapping(render.get("output"), f"{key} output")
        if (
            render.get("executed") is not True
            or output.get("width") != 1024
            or output.get("height") != 1024
            or output.get("pixelFormat") != 115
            or output.get("rawBytes") != 1024 * 1024 * 8
            or "auxiliaryOutput" in render
        ):
            raise ValueError(f"dynamic {key} layout differs")
        validate_raw_file(output, root=root, name=f"dynamic {key}")
    tomography = mapping(
        trace.get("stageTomography"),
        "highlight stageTomography",
    )
    cases = tomography.get("cases")
    if (
        tomography.get("schemaVersion") != 1
        or tomography.get("executed") is not True
        or tomography.get("capturedAppleFunctionUnmodified") is not True
        or tomography.get("caseCount") != len(ALPHA_TOMOGRAPHY_CASES)
        or not isinstance(cases, list)
        or {case.get("name") for case in cases if isinstance(case, Mapping)}
        != ALPHA_TOMOGRAPHY_CASES
    ):
        raise ValueError("dynamic highlight tomography differs")
    for untyped_case in cases:
        case = mapping(untyped_case, "highlight tomography case")
        replay = mapping(case.get("replay"), "highlight tomography replay")
        output = mapping(replay.get("output"), "highlight tomography output")
        if (
            case.get("executed") is not True
            or not isinstance(case.get("edits"), list)
            or not case["edits"]
            or replay.get("executed") is not True
            or output.get("width") != 1024
            or output.get("height") != 1024
            or output.get("pixelFormat") != 115
            or output.get("rawBytes") != 1024 * 1024 * 8
            or "auxiliaryOutput" in replay
        ):
            raise ValueError("dynamic highlight tomography case differs")
        validate_raw_file(
            output,
            root=root,
            name="dynamic highlight tomography",
        )

    sdf_diagnostics = mapping(
        trace.get("customHighlightSDFDiagnostics"),
        "customHighlightSDFDiagnostics",
    )
    pipelines = sdf_diagnostics.get("pipelines")
    replays = sdf_diagnostics.get("replays")
    if (
        sdf_diagnostics.get("schemaVersion") != 1
        or sdf_diagnostics.get("executed") is not True
        or sdf_diagnostics.get("classification") != "diagnostic custom-Metal SDF replay"
        or sdf_diagnostics.get("capturedAppleFunctionUnmodified") is not False
        or sdf_diagnostics.get("customStageInVertex") is not True
        or not isinstance(sdf_diagnostics.get("uniformRecordOffset"), int)
        or sdf_diagnostics["uniformRecordOffset"] < 0
        or sdf_diagnostics.get("pipelineCount") != len(HIGHLIGHT_SDF_DIAGNOSTIC_TRACES)
        or sdf_diagnostics.get("replayCount") != len(HIGHLIGHT_SDF_DIAGNOSTIC_TRACES)
        or not isinstance(pipelines, list)
        or not isinstance(replays, list)
        or {item.get("name") for item in pipelines if isinstance(item, Mapping)}
        != HIGHLIGHT_SDF_DIAGNOSTIC_TRACES.keys()
        or {item.get("name") for item in replays if isinstance(item, Mapping)}
        != HIGHLIGHT_SDF_DIAGNOSTIC_TRACES.keys()
    ):
        raise ValueError("dynamic custom-highlight SDF diagnostics differ")
    for untyped_pipeline in pipelines:
        pipeline = mapping(
            untyped_pipeline,
            "custom-highlight SDF pipeline",
        )
        name = pipeline.get("name")
        if not isinstance(name, str):
            raise ValueError("custom-highlight SDF pipeline name differs")
        expected_pixel_format, _ = HIGHLIGHT_SDF_DIAGNOSTIC_TRACES[name]
        if (
            pipeline.get("pixelFormat") != expected_pixel_format
            or pipeline.get("label") != f"lg.final-highlight-{name}"
            or not isinstance(pipeline.get("descriptor"), Mapping)
        ):
            raise ValueError(f"dynamic custom-highlight {name} pipeline differs")
    for untyped_replay in replays:
        replay_record = mapping(
            untyped_replay,
            "custom-highlight SDF replay record",
        )
        name = replay_record.get("name")
        if not isinstance(name, str):
            raise ValueError("custom-highlight SDF replay name differs")
        expected_pixel_format, expected_bytes = HIGHLIGHT_SDF_DIAGNOSTIC_TRACES[name]
        diagnostic_replay = mapping(
            replay_record.get("replay"),
            f"custom-highlight {name} replay",
        )
        output = mapping(
            diagnostic_replay.get("output"),
            f"custom-highlight {name} output",
        )
        if (
            replay_record.get("executed") is not True
            or replay_record.get("pixelFormat") != expected_pixel_format
            or diagnostic_replay.get("executed") is not True
            or output.get("width") != 1024
            or output.get("height") != 1024
            or output.get("pixelFormat") != expected_pixel_format
            or output.get("rawBytes") != expected_bytes
            or "auxiliaryOutput" in diagnostic_replay
        ):
            raise ValueError(f"dynamic custom-highlight {name} layout differs")
        validate_raw_file(
            output,
            root=root,
            name=f"dynamic custom-highlight {name}",
        )

    if sample_index != 32:
        if "exactCompositorTrace" in trace:
            raise ValueError("fractional alpha trace captured a compositor probe")
        return

    compositor = mapping(
        trace.get("exactCompositorTrace"),
        "exactCompositorTrace",
    )
    if (
        compositor.get("schemaVersion") != 2
        or compositor.get("executed") is not True
        or compositor.get("capturedAppleFunctionUnmodified") is not True
    ):
        raise ValueError("dynamic exact-compositor trace differs")
    for key in (
        "capturedVsReference",
        "rebuiltVsReference",
        "capturedVsRebuilt",
    ):
        comparison = mapping(compositor.get(key), key)
        if (
            comparison.get("compared") is not True
            or comparison.get("exactByteMatch") is not True
            or comparison.get("mismatchedByteCount") != 0
            or comparison.get("mismatchedPixelCount") != 0
            or comparison.get("maximumChannelDelta") != 0
        ):
            raise ValueError(f"dynamic exact-compositor {key} differs")
    for key, pixel_format, byte_count in (
        ("capturedBGRA8", 80, 1024 * 1024 * 4),
        ("rebuiltBGRA8", 80, 1024 * 1024 * 4),
        ("exactHalfComposite", 115, 1024 * 1024 * 8),
    ):
        render = mapping(compositor.get(key), key)
        output = mapping(render.get("output"), f"{key} output")
        if (
            render.get("executed") is not True
            or output.get("width") != 1024
            or output.get("height") != 1024
            or output.get("pixelFormat") != pixel_format
            or output.get("rawBytes") != byte_count
            or "auxiliaryOutput" in render
        ):
            raise ValueError(f"dynamic compositor {key} layout differs")
        validate_raw_file(output, root=root, name=f"dynamic compositor {key}")
    for key in ("input", "reference"):
        wrapper = mapping(compositor.get(key), f"compositor {key}")
        output = mapping(wrapper.get("output"), f"compositor {key} output")
        if (
            output.get("width") != 1024
            or output.get("height") != 1024
            or output.get("pixelFormat") != 80
            or output.get("rawBytes") != 1024 * 1024 * 4
        ):
            raise ValueError(f"dynamic compositor {key} layout differs")
        validate_raw_file(
            output,
            root=root,
            name=f"dynamic compositor {key}",
        )
    tomography = mapping(
        compositor.get("stageTomography"),
        "compositor stageTomography",
    )
    cases = tomography.get("cases")
    if (
        tomography.get("schemaVersion") != 1
        or tomography.get("executed") is not True
        or tomography.get("capturedAppleFunctionUnmodified") is not True
        or tomography.get("caseCount") != len(COMPOSITOR_TOMOGRAPHY_CASES)
        or not isinstance(cases, list)
        or {case.get("name") for case in cases if isinstance(case, Mapping)}
        != COMPOSITOR_TOMOGRAPHY_CASES
    ):
        raise ValueError("dynamic compositor tomography differs")
    for untyped_case in cases:
        case = mapping(untyped_case, "compositor tomography case")
        replay = mapping(case.get("replay"), "compositor tomography replay")
        output = mapping(replay.get("output"), "compositor tomography output")
        if (
            case.get("executed") is not True
            or not isinstance(case.get("edits"), list)
            or not case["edits"]
            or replay.get("executed") is not True
            or output.get("width") != 1024
            or output.get("height") != 1024
            or output.get("pixelFormat") != 115
            or output.get("rawBytes") != 1024 * 1024 * 8
            or "auxiliaryOutput" in replay
        ):
            raise ValueError("dynamic compositor tomography layout differs")
        validate_raw_file(
            output,
            root=root,
            name=f"dynamic compositor tomography {case.get('name')}",
        )


def validate(
    path: Path,
    *,
    requested: bool,
    highlight_trace: bool,
) -> dict[str, int | bool]:
    report = mapping(
        json.loads(path.read_text(encoding="utf-8")),
        "transition report",
    )
    direction = report.get("direction")
    if direction not in {"materialize", "dematerialize"}:
        raise ValueError("transition direction differs")
    expected_sample_indices = (
        EXPECTED_SAMPLE_INDICES
        if direction == "materialize"
        else EXPECTED_SAMPLE_INDICES[:-1]
    )
    uniforms = mapping(
        report.get("dynamicBackgroundUniforms"),
        "dynamicBackgroundUniforms",
    )
    if uniforms.get("schemaVersion") != 9 or uniforms.get("requested") is not requested:
        raise ValueError("dynamic uniform highlight schema differs")
    if uniforms.get("presentationLayerReplayed") is not requested:
        raise ValueError("dynamic presentation replay metadata differs")
    if not requested:
        if uniforms.get("executed") is not False:
            raise ValueError("unrequested dynamic uniforms executed")
        return {
            "requested": False,
            "states": 0,
            "highlightBindings": 0,
            "highlightTraces": 0,
            "interpolantTraces": 0,
            "backgroundInterpolantTraces": 0,
            "backgroundArithmeticTraces": 0,
            "backgroundPrivateLayerOutputs": 0,
            "intermediateTextures": 0,
            "dynamicBackdropProducerInputs": 0,
            "dynamicBackdropProducerOutputs": 0,
        }

    records = uniforms.get("records")
    if (
        uniforms.get("executed") is not True
        or uniforms.get("sampleIndices") != list(expected_sample_indices)
        or uniforms.get("sampleCount") != len(expected_sample_indices)
        or uniforms.get("executedSampleCount") != len(expected_sample_indices)
        or uniforms.get("method")
        != "copied-presentation-background-filter-plus-compatible-"
        "layer-state-on-fresh-static-model-tree-with-controlled-"
        "producer-input"
        or uniforms.get("evidenceMode") != "controlled-replay-v1"
        or uniforms.get("presentationLayerAssignedToCARenderer") is not False
        or uniforms.get("freshStaticCarrier") is not True
        or uniforms.get("detachedLayerTreeCopies") is not False
        or uniforms.get("carrierCriticalPaths") != EXPECTED_CARRIER_CRITICAL_PATHS
        or uniforms.get("transitionForegroundFilterCaptured") is not True
        or uniforms.get("transitionForegroundFilterReplayedOnCarrier") is not False
        or not isinstance(uniforms.get("modelTargetPath"), list)
        or not isinstance(records, list)
        or len(records) != len(expected_sample_indices)
    ):
        raise ValueError("dynamic highlight evidence is incomplete")

    binding_count = 0
    highlight_trace_count = 0
    interpolant_trace_count = 0
    background_interpolant_trace_count = 0
    background_arithmetic_trace_count = 0
    background_private_layer_output_count = 0
    intermediate_texture_count = 0
    dynamic_backdrop_producer_input_count = 0
    dynamic_backdrop_producer_output_count = 0
    for sample_index, untyped_record in zip(
        expected_sample_indices,
        records,
        strict=True,
    ):
        record = mapping(untyped_record, f"sample {sample_index}")
        if record.get("sampleIndex") != sample_index:
            raise ValueError("dynamic highlight sample order differs")
        if (
            record.get("freshStaticCarrier") is not True
            or record.get("detachedLayerTreeCopy") is not False
            or record.get("presentationLayerAssignedToCARenderer") is not False
            or record.get("backgroundFilterReplayedOnCarrier") is not True
            or record.get("foregroundFilterReplayedOnCarrier") is not False
            or record.get("installedCriticalCarrierPaths")
            != EXPECTED_CARRIER_CRITICAL_PATHS
            or record.get("missingCriticalCarrierPaths") != []
            or not isinstance(record.get("skippedCarrierPaths"), list)
            or not isinstance(record.get("installedCarrierLayerCount"), int)
            or record["installedCarrierLayerCount"]
            < len(EXPECTED_CARRIER_CRITICAL_PATHS)
        ):
            raise ValueError("dynamic render carrier replay is incomplete")
        if sample_index != 32 and record.get("replayedLayerCount") != 16:
            raise ValueError("dynamic presentation layer replay is incomplete")
        source = record.get("snapshotLayerSource")
        if source != "presentation" and not (
            sample_index == 32
            and source
            in {
                "model-endpoint-fallback",
                "static-carrier-endpoint",
            }
            and record.get("remaining") == 1.0
        ):
            raise ValueError("dynamic snapshot layer source is invalid")
        remaining = numeric(record.get("remaining"), "remaining")
        foreground = mapping(
            record.get("foregroundFilter"),
            "foregroundFilter",
        )
        if sample_index == 32 and source == "static-carrier-endpoint":
            if (
                foreground.get("source") != "static-glass-endpoint"
                or foreground.get("filterPresent") is not False
                or foreground.get("replayedOnCarrier") is not False
                or remaining != 1.0
            ):
                raise ValueError("static endpoint foreground evidence differs")
        else:
            known = mapping(foreground.get("knownValues"), "knownValues")
            if (
                known.get("name") != "glassForeground"
                or known.get("type") != "glassForeground"
                or foreground.get("capturedPath") != [1, 0, 1, 1, 0]
                or foreground.get("replayedOnCarrier") is not False
            ):
                raise ValueError("copied foreground is not glassForeground")
            inputs = mapping(foreground.get("inputValues"), "inputValues")
            for name, expected in expected_foreground(remaining).items():
                observed = numeric(inputs.get(name), name)
                if not math.isclose(
                    observed,
                    expected,
                    rel_tol=0.0,
                    abs_tol=2e-6,
                ):
                    raise ValueError(
                        f"sample {sample_index} {name} differs: "
                        f"{observed} != {expected}"
                    )

        render = mapping(record.get("render"), "render")
        duration = numeric(render.get("durationSeconds"), "render duration")
        if (
            render.get("executed") is not True
            or duration > 30.0
            or not isinstance(render.get("metalBufferSnapshots"), Mapping)
        ):
            raise ValueError(f"sample {sample_index} render is incomplete")
        validate_raw_render_evidence(render, root=path.parent)
        validate_dynamic_backdrop_producer(
            render,
            root=path.parent,
            sample_index=sample_index,
        )
        dynamic_backdrop_producer_input_count += 1
        dynamic_backdrop_producer_output_count += 1
        replay = mapping(render.get("exactPassReplay"), "exactPassReplay")
        if highlight_trace:
            validate_background_interpolant_trace(
                replay,
                root=path.parent,
                sample_index=sample_index,
            )
            background_interpolant_trace_count += 1
            background_arithmetic_trace_count += validate_background_arithmetic_trace(
                replay,
                root=path.parent,
                sample_index=sample_index,
            )
            background_private_layer_output_count += (
                validate_background_private_layer_outputs(
                    replay,
                    root=path.parent,
                    sample_index=sample_index,
                )
            )
        elif "backgroundInterpolantTrace" in replay:
            raise ValueError("an unrequested background interpolant trace executed")
        elif "backgroundArithmeticTrace" in replay:
            raise ValueError("an unrequested background arithmetic trace executed")
        elif "backgroundPrivateLayerOutputs" in replay:
            raise ValueError("an unrequested private background layer replay executed")
        trace_expected = (
            highlight_trace and sample_index in HIGHLIGHT_TRACE_SAMPLE_INDICES
        )
        if trace_expected:
            validate_highlight_trace(
                replay,
                root=path.parent,
                sample_index=sample_index,
            )
            highlight_trace_count += 1
            interpolant_trace_count += 1
        elif highlight_trace:
            if "finalHighlightAlphaTrace" in replay:
                raise ValueError("an unrequested full highlight trace executed")
            validate_interpolant_only_trace(
                replay,
                root=path.parent,
            )
            interpolant_trace_count += 1
        elif "finalHighlightAlphaTrace" in replay:
            raise ValueError("an unrequested dynamic highlight trace executed")
        elif "finalHighlightInterpolantTrace" in replay:
            raise ValueError("an unrequested dynamic interpolant trace executed")
        texture_snapshots = mapping(
            render.get("metalTextureSnapshots"),
            "metalTextureSnapshots",
        ).get("snapshots")
        if not isinstance(texture_snapshots, list):
            raise ValueError("metalTextureSnapshots are incomplete")
        intermediate_textures = [
            mapping(snapshot, "intermediate texture")
            for snapshot in texture_snapshots
            if isinstance(snapshot, Mapping)
            and snapshot.get("index") == 3
            and fragment_name(snapshot) == "TimgA2Xhfc_Isrc"
        ]
        for texture in intermediate_textures:
            width = texture.get("width")
            height = texture.get("height")
            if (
                not isinstance(width, int)
                or not isinstance(height, int)
                or not 0 < width <= 1024
                or not 0 < height <= 1024
                or texture.get("pixelFormat") != 80
                or texture.get("mipmapLevelCount") != 1
                or texture.get("rawBytes") != width * height * 4
            ):
                raise ValueError("intermediate texture layout differs")
            validate_raw_file(
                texture,
                root=path.parent,
                name="intermediate texture",
            )
            intermediate_texture_count += 1
        bindings = render.get("glassFragmentUniformBindings")
        if not isinstance(bindings, list):
            raise ValueError("glassFragmentUniformBindings is not a list")
        if render.get("glassFragmentUniformBindingCount") != len(bindings):
            raise ValueError("glassFragmentUniformBindingCount differs")
        typed_bindings = [mapping(binding, "fragment binding") for binding in bindings]
        for binding in typed_bindings:
            payload = mapping(binding.get("payload"), "fragment payload")
            encoded = payload.get("hex")
            length = payload.get("lengthBytes")
            if (
                binding.get("stage") != "fragment"
                or binding.get("index") != 1
                or not isinstance(length, int)
                or length < 258
                or not isinstance(encoded, str)
                or len(encoded) != 2 * length
            ):
                raise ValueError("transition fragment binding is incomplete")
        backgrounds = [
            binding
            for binding in typed_bindings
            if fragment_name(binding).startswith("glass_background")
        ]
        if len(backgrounds) != 2:
            raise ValueError("transition background binding count differs")
        highlights = [
            binding for binding in typed_bindings if fragment_name(binding) == "A2Xghfc"
        ]
        if not highlights:
            raise ValueError(f"sample {sample_index} has no A2Xghfc uniform binding")
        for binding in highlights:
            validate_highlight_binding(binding)
        filter_values = mapping(
            mapping(record.get("filter"), "background filter").get("inputValues"),
            "background filter inputValues",
        )
        if filter_values.get("inputFaceOpacity") != record.get("remaining"):
            raise ValueError("background face opacity differs from remaining")
        binding_count += len(highlights)

    return {
        "requested": True,
        "states": len(records),
        "highlightBindings": binding_count,
        "rawBackdropPyramids": len(records),
        "rawPreFinalPasses": len(records),
        "highlightTraces": highlight_trace_count,
        "interpolantTraces": interpolant_trace_count,
        "backgroundInterpolantTraces": background_interpolant_trace_count,
        "backgroundArithmeticTraces": background_arithmetic_trace_count,
        "backgroundPrivateLayerOutputs": (background_private_layer_output_count),
        "intermediateTextures": intermediate_texture_count,
        "dynamicBackdropProducerInputs": (dynamic_backdrop_producer_input_count),
        "dynamicBackdropProducerOutputs": (dynamic_backdrop_producer_output_count),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--requested",
        action="store_true",
        help="require the uniform capture rather than its disabled record",
    )
    parser.add_argument(
        "--highlight-trace",
        action="store_true",
        help="require alpha-only traces for the fractional and settled states",
    )
    arguments = parser.parse_args()
    result = validate(
        arguments.report,
        requested=arguments.requested,
        highlight_trace=arguments.highlight_trace,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
