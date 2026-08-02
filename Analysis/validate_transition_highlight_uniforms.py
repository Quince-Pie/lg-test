#!/usr/bin/env python3
"""Validate transition-time Apple final-highlight uniform evidence."""

import argparse
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any


EXPECTED_SAMPLE_INDICES = (1, 4, 8, 12, 16, 20, 24, 28, 32)


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
        and snapshot.get("mipmapLevelCount") == 2
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
    ] != [0, 1]:
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


def validate(path: Path, *, requested: bool) -> dict[str, int | bool]:
    report = mapping(
        json.loads(path.read_text(encoding="utf-8")),
        "transition report",
    )
    uniforms = mapping(
        report.get("dynamicBackgroundUniforms"),
        "dynamicBackgroundUniforms",
    )
    if uniforms.get("schemaVersion") != 3 or uniforms.get("requested") is not requested:
        raise ValueError("dynamic uniform highlight schema differs")
    if not requested:
        if uniforms.get("executed") is not False:
            raise ValueError("unrequested dynamic uniforms executed")
        return {
            "requested": False,
            "states": 0,
            "highlightBindings": 0,
        }

    records = uniforms.get("records")
    if (
        uniforms.get("executed") is not True
        or not isinstance(records, list)
        or len(records) != len(EXPECTED_SAMPLE_INDICES)
    ):
        raise ValueError("dynamic highlight evidence is incomplete")

    binding_count = 0
    for sample_index, untyped_record in zip(
        EXPECTED_SAMPLE_INDICES,
        records,
        strict=True,
    ):
        record = mapping(untyped_record, f"sample {sample_index}")
        if record.get("sampleIndex") != sample_index:
            raise ValueError("dynamic highlight sample order differs")
        if record.get("replayedLayerCount") != 16:
            raise ValueError("dynamic presentation layer replay is incomplete")
        source = record.get("snapshotLayerSource")
        if source != "presentation" and not (
            sample_index == 32
            and source == "model-endpoint-fallback"
            and record.get("remaining") == 1.0
        ):
            raise ValueError("dynamic snapshot layer source is invalid")
        remaining = numeric(record.get("remaining"), "remaining")
        foreground = mapping(
            record.get("foregroundFilter"),
            "foregroundFilter",
        )
        known = mapping(foreground.get("knownValues"), "knownValues")
        if (
            known.get("name") != "glassForeground"
            or known.get("type") != "glassForeground"
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
                    f"sample {sample_index} {name} differs: {observed} != {expected}"
                )

        render = mapping(record.get("render"), "render")
        validate_raw_render_evidence(render, root=path.parent)
        bindings = render.get("glassFragmentUniformBindings")
        if not isinstance(bindings, list):
            raise ValueError("glassFragmentUniformBindings is not a list")
        highlights = [
            mapping(binding, "highlight binding")
            for binding in bindings
            if isinstance(binding, Mapping) and fragment_name(binding) == "A2Xghfc"
        ]
        if not highlights:
            raise ValueError(f"sample {sample_index} has no A2Xghfc uniform binding")
        for binding in highlights:
            validate_highlight_binding(binding)
        binding_count += len(highlights)

    return {
        "requested": True,
        "states": len(records),
        "highlightBindings": binding_count,
        "rawBackdropPyramids": len(records),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--requested",
        action="store_true",
        help="require the uniform capture rather than its disabled record",
    )
    arguments = parser.parse_args()
    result = validate(arguments.report, requested=arguments.requested)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
