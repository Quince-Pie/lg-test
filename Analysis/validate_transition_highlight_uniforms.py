#!/usr/bin/env python3
"""Validate transition-time Apple final-highlight uniform evidence."""

import argparse
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any


EXPECTED_SAMPLE_INDICES = (1, 4, 8, 12, 16, 20, 24, 28, 32)
HIGHLIGHT_TRACE_SAMPLE_INDICES = frozenset({1, 32})
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


def validate_highlight_trace(
    replay: Mapping[str, Any],
    *,
    root: Path,
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
        trace.get("schemaVersion") != 1
        or trace.get("executed") is not True
        or trace.get("diagnosticScope") != "alpha-only"
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
    uniforms = mapping(
        report.get("dynamicBackgroundUniforms"),
        "dynamicBackgroundUniforms",
    )
    if uniforms.get("schemaVersion") != 5 or uniforms.get("requested") is not requested:
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
        }

    records = uniforms.get("records")
    if (
        uniforms.get("executed") is not True
        or uniforms.get("sampleIndices") != list(EXPECTED_SAMPLE_INDICES)
        or uniforms.get("sampleCount") != len(EXPECTED_SAMPLE_INDICES)
        or uniforms.get("executedSampleCount") != len(EXPECTED_SAMPLE_INDICES)
        or uniforms.get("method")
        != "copied-presentation-background-filter-plus-compatible-"
        "layer-state-on-fresh-static-model-tree"
        or uniforms.get("presentationLayerAssignedToCARenderer") is not False
        or uniforms.get("freshStaticCarrier") is not True
        or uniforms.get("detachedLayerTreeCopies") is not False
        or uniforms.get("carrierCriticalPaths") != EXPECTED_CARRIER_CRITICAL_PATHS
        or uniforms.get("transitionForegroundFilterCaptured") is not True
        or uniforms.get("transitionForegroundFilterReplayedOnCarrier") is not False
        or not isinstance(uniforms.get("modelTargetPath"), list)
        or not isinstance(records, list)
        or len(records) != len(EXPECTED_SAMPLE_INDICES)
    ):
        raise ValueError("dynamic highlight evidence is incomplete")

    binding_count = 0
    highlight_trace_count = 0
    for sample_index, untyped_record in zip(
        EXPECTED_SAMPLE_INDICES,
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
        replay = mapping(render.get("exactPassReplay"), "exactPassReplay")
        trace_expected = (
            highlight_trace and sample_index in HIGHLIGHT_TRACE_SAMPLE_INDICES
        )
        if trace_expected:
            validate_highlight_trace(replay, root=path.parent)
            highlight_trace_count += 1
        elif "finalHighlightAlphaTrace" in replay:
            raise ValueError("an unrequested dynamic highlight trace executed")
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
