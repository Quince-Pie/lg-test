#!/usr/bin/env python3
"""Validate the frozen regular-material controlled-backdrop capture."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path
from typing import Any


type JSONObject = dict[str, Any]

EXPECTED_SAMPLES = (1, 4, 8, 12, 16, 20, 24, 28)
CONTROLLED_SIDE = 1_024
CONTROLLED_BYTES = CONTROLLED_SIDE * CONTROLLED_SIDE * 4
CONTROLLED_SHA256 = "3ac65697c38c44ed6332911c83e2f13a0b4b6958df49fa88365fbe6327cc1f88"
COPY_BASE_PIPELINE = "com.apple.coreanimation.variable_blur_copy_base_mip_compute"
PRODUCER_FRAGMENTS = frozenset({"downsample_4_frag_lph", "TimgA2Xhfc_Isrc"})


def mapping(value: object, name: str) -> JSONObject:
    if not isinstance(value, dict):
        raise ValueError(f"{name} is not an object")
    return value


def sequence(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{name} is not an array")
    return value


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def controlled_input() -> bytes:
    result = bytearray(CONTROLLED_BYTES)
    for y in range(CONTROLLED_SIDE):
        for x in range(CONTROLLED_SIDE):
            offset = (y * CONTROLLED_SIDE + x) * 4
            result[offset] = (x * 37 + y * 17 + 13) & 0xFF
            result[offset + 1] = ((x * 11) ^ (y * 29) ^ 0x5A) & 0xFF
            result[offset + 2] = (x * 3 + y * 5 + (x * y) % 251) & 0xFF
            result[offset + 3] = 0xFF
    return bytes(result)


def raw_path(root: Path, snapshot: JSONObject, name: str) -> Path:
    filename = snapshot.get("rawFile")
    if snapshot.get("rawCapture") is not True or not isinstance(filename, str):
        raise ValueError(f"{name} has no retained raw file")
    resolved_root = root.resolve()
    result = (resolved_root / filename).resolve()
    if not result.is_relative_to(resolved_root):
        raise ValueError(f"{name} raw path escapes the capture root")
    return result


def raw_bgra8(root: Path, snapshot: JSONObject, name: str) -> tuple[bytes, Path]:
    width = snapshot.get("width")
    height = snapshot.get("height")
    if (
        not isinstance(width, int)
        or not isinstance(height, int)
        or width <= 0
        or height <= 0
        or snapshot.get("pixelFormat") != 80
        or snapshot.get("bytesPerRow") != width * 4
        or snapshot.get("rawBytes") != width * height * 4
    ):
        raise ValueError(f"{name} is not tightly packed BGRA8")
    path = raw_path(root, snapshot, name)
    payload = path.read_bytes()
    if len(payload) != width * height * 4:
        raise ValueError(f"{name} raw byte count differs")
    return payload, path


def unique_bgra8_pixels(payload: bytes) -> int:
    if len(payload) % 4:
        raise ValueError("BGRA8 payload length is not a multiple of four")
    return len({pixel[0] for pixel in struct.iter_unpack("<I", payload)})


def pipeline_label(record: JSONObject) -> str:
    pipeline = record.get("pipeline")
    if not isinstance(pipeline, dict):
        return ""
    label = pipeline.get("label")
    return label if isinstance(label, str) else ""


def pipeline_fragment(record: JSONObject) -> str:
    pipeline = record.get("pipeline")
    if not isinstance(pipeline, dict):
        return ""
    descriptor = pipeline.get("creationDescriptor")
    if not isinstance(descriptor, dict):
        return ""
    fragment = descriptor.get("fragmentFunction")
    return fragment if isinstance(fragment, str) else ""


def texture_descriptor(record: JSONObject) -> JSONObject:
    texture = record.get("texture")
    if not isinstance(texture, dict):
        raise ValueError("texture binding has no descriptor")
    return texture


def producer_fragment(records: list[JSONObject], encoder: str) -> str:
    fragments = {
        pipeline_fragment(record)
        for record in records
        if record.get("kind") == "pipeline"
        and record.get("encoder") == encoder
        and pipeline_fragment(record) in PRODUCER_FRAGMENTS
    }
    if len(fragments) != 1:
        raise ValueError(
            f"producer encoder has unexpected fragments: {sorted(fragments)}"
        )
    return fragments.pop()


def single(records: list[JSONObject], name: str) -> JSONObject:
    if len(records) != 1:
        raise ValueError(f"expected one {name}; found {len(records)}")
    return records[0]


def validate_state(
    root: Path,
    record: JSONObject,
    expected_input: bytes,
) -> JSONObject:
    sample = record.get("sampleIndex")
    remaining = record.get("remaining")
    if sample not in EXPECTED_SAMPLES or not isinstance(remaining, (int, float)):
        raise ValueError("dynamic state identity differs")
    render = mapping(record.get("render"), f"sample {sample} render")
    uniforms = mapping(render.get("metalUniformProbe"), "metalUniformProbe")
    records = [
        mapping(value, "Metal record")
        for value in sequence(uniforms.get("records"), "Metal records")
    ]
    evidence = mapping(
        render.get("dynamicBackdropProducerBoundary"),
        "dynamicBackdropProducerBoundary",
    )
    boundaries = sequence(evidence.get("records"), "producer boundaries")
    if evidence.get("schemaVersion") != 2 or evidence.get("boundaryCount") != 1:
        raise ValueError(f"sample {sample} producer boundary is incomplete")
    boundary = mapping(
        single([mapping(v, "boundary") for v in boundaries], "boundary"), "boundary"
    )
    intervention = mapping(boundary.get("inputIntervention"), "input intervention")
    if (
        intervention.get("schemaVersion") != 1
        or intervention.get("name") != "opaque-coordinate-hash-v1"
        or intervention.get("applied") is not True
        or intervention.get("sha256") != CONTROLLED_SHA256
        or boundary.get("capturePoint")
        != "controlled-input-before-producer-draw-and-blit-after-"
        "producer-render-before-copy-base-compute"
    ):
        raise ValueError(f"sample {sample} controlled intervention differs")

    producer_encoder = boundary.get("producerEncoder")
    if not isinstance(producer_encoder, str):
        raise ValueError(f"sample {sample} producer encoder is absent")
    fragment = producer_fragment(records, producer_encoder)

    producer_input, input_path = raw_bgra8(
        root,
        mapping(boundary.get("input"), "producer input"),
        f"sample {sample} producer input",
    )
    if (
        producer_input != expected_input
        or sha256_bytes(producer_input) != CONTROLLED_SHA256
    ):
        raise ValueError(f"sample {sample} controlled input bytes differ")
    producer_output_snapshot = mapping(boundary.get("output"), "producer output")
    producer_output, output_path = raw_bgra8(
        root,
        producer_output_snapshot,
        f"sample {sample} producer output",
    )
    producer_unique = unique_bgra8_pixels(producer_output)
    if producer_unique < 4_096:
        raise ValueError(f"sample {sample} producer output is degenerate")

    copy_source = single(
        [
            value
            for value in records
            if value.get("kind") == "texture"
            and value.get("stage") == "compute"
            and value.get("index") == 0
            and pipeline_label(value) == COPY_BASE_PIPELINE
        ],
        "copy-base source",
    )
    copy_destination = single(
        [
            value
            for value in records
            if value.get("kind") == "texture"
            and value.get("stage") == "compute"
            and value.get("index") == 1
            and pipeline_label(value) == COPY_BASE_PIPELINE
        ],
        "copy-base destination",
    )
    source_texture = texture_descriptor(copy_source)
    destination_texture = texture_descriptor(copy_destination)
    if (
        source_texture.get("address") != boundary.get("producerOutputAddress")
        or copy_source.get("encoder") != boundary.get("copyBaseEncoder")
        or copy_source.get("sequence") != boundary.get("copyBaseBindingSequence")
        or not isinstance(boundary.get("producerRenderPassSequence"), int)
        or not isinstance(boundary.get("producerInputBindingSequence"), int)
        or not (
            boundary["producerRenderPassSequence"]
            < boundary["producerInputBindingSequence"]
            < boundary["copyBaseBindingSequence"]
        )
    ):
        raise ValueError(f"sample {sample} producer/copy-base join differs")

    textures = mapping(render.get("metalTextureSnapshots"), "texture snapshots")
    snapshots = [
        mapping(value, "texture snapshot")
        for value in sequence(textures.get("snapshots"), "texture snapshots")
    ]
    pyramids = [
        value
        for value in snapshots
        if value.get("index") == 3
        and pipeline_fragment(value).startswith("glass_background")
        and value.get("pixelFormat") == 80
    ]
    pyramid = single(pyramids, "glass backdrop pyramid")
    if (
        pyramid.get("width") != destination_texture.get("width")
        or pyramid.get("height") != destination_texture.get("height")
        or not isinstance(pyramid.get("mipmapLevelCount"), int)
        or pyramid["mipmapLevelCount"] < 2
    ):
        raise ValueError(f"sample {sample} backdrop pyramid descriptor differs")
    levels = [
        mapping(value, "mip snapshot")
        for value in sequence(pyramid.get("mipSnapshots"), "mip snapshots")
    ]
    if [value.get("level") for value in levels] != list(range(len(levels))):
        raise ValueError(f"sample {sample} mip sequence differs")
    if len(levels) != pyramid["mipmapLevelCount"]:
        raise ValueError(f"sample {sample} mip count differs")

    mip_records: list[JSONObject] = []
    for level in levels:
        payload, path = raw_bgra8(
            root,
            {**level, "pixelFormat": pyramid.get("pixelFormat")},
            f"sample {sample} mip {level['level']}",
        )
        unique = unique_bgra8_pixels(payload)
        if level["level"] == 0 and unique < 4_096:
            raise ValueError(f"sample {sample} copy-base output is degenerate")
        mip_records.append(
            {
                "level": level["level"],
                "extent": [level["width"], level["height"]],
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
                "uniqueBGRA8Pixels": unique,
                "rawFile": str(path.relative_to(root.resolve())),
            }
        )

    return {
        "sampleIndex": sample,
        "remaining": float(remaining),
        "producerFragment": fragment,
        "producerExtent": [
            producer_output_snapshot["width"],
            producer_output_snapshot["height"],
        ],
        "producerInput": {
            "rawFile": str(input_path.relative_to(root.resolve())),
            "bytes": len(producer_input),
            "sha256": CONTROLLED_SHA256,
        },
        "producerOutput": {
            "rawFile": str(output_path.relative_to(root.resolve())),
            "bytes": len(producer_output),
            "sha256": sha256_bytes(producer_output),
            "uniqueBGRA8Pixels": producer_unique,
        },
        "mips": mip_records,
    }


def validate(capture: Path) -> JSONObject:
    root = capture.resolve()
    timeline = root / "transition-timeline.json"
    report = mapping(json.loads(timeline.read_text(encoding="utf-8")), "timeline")
    if (
        report.get("material") != "regular"
        or report.get("appearance") != "dark"
        or report.get("direction") != "dematerialize"
        or mapping(report.get("geometry"), "geometry").get("name")
        != "circle-480-center"
    ):
        raise ValueError("capture profile differs from the frozen Walle case")
    dynamic = mapping(report.get("dynamicBackgroundUniforms"), "dynamic uniforms")
    records = [
        mapping(value, "dynamic state")
        for value in sequence(dynamic.get("records"), "dynamic states")
    ]
    if dynamic.get("schemaVersion") != 7:
        raise ValueError("dynamic-uniform schema differs")
    if tuple(value.get("sampleIndex") for value in records) != EXPECTED_SAMPLES:
        raise ValueError("dynamic sample inventory differs")

    expected_input = controlled_input()
    if sha256_bytes(expected_input) != CONTROLLED_SHA256:
        raise AssertionError("controlled-input implementation hash differs")
    states = [validate_state(root, value, expected_input) for value in records]
    fragments = Counter(state["producerFragment"] for state in states)
    if set(fragments) != PRODUCER_FRAGMENTS:
        raise ValueError("capture does not exercise both regular producer branches")

    return {
        "schemaVersion": 1,
        "status": "accepted-regular-controlled-backdrop-capture",
        "capture": str(root),
        "timelineSHA256": sha256_file(timeline),
        "stateCount": len(states),
        "sampleIndices": list(EXPECTED_SAMPLES),
        "producerFragmentCounts": dict(sorted(fragments.items())),
        "controlledInputSHA256": CONTROLLED_SHA256,
        "states": states,
        "acceptance": {
            "allControlledInputsExact": True,
            "allProducerOutputsNondegenerate": True,
            "allCopyBaseMipZeroOutputsNondegenerate": True,
            "producerAndCopyBaseJoinsExact": True,
            "directAndDownsampleProducerBranchesObserved": True,
            "pixelTolerance": 0,
        },
        "claimBoundary": {
            "captureValidated": True,
            "producerArithmeticReconstructed": False,
            "productionParityEstablished": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.capture)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
