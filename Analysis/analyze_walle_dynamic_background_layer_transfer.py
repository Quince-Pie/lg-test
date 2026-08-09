#!/usr/bin/env python3
"""Prove Apple's natural background half-source and BGRA8 layer transfer."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
import platform
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray


type JsonObject = dict[str, Any]
type ByteImage = NDArray[np.uint8]
type HalfBitsImage = NDArray[np.uint16]

WIDTH = 1024
HEIGHT = 1024
CHANNELS = 4
SAMPLE_INDEX = 16
BGRA8_BYTES = WIDTH * HEIGHT * CHANNELS
RGBA16F_BYTES = WIDTH * HEIGHT * CHANNELS * 2


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def mapping(value: object, name: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping), f"{name} is not an object")
    return value


def sequence(value: object, name: str) -> Sequence[Any]:
    require(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)),
        f"{name} is not an array",
    )
    return value


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def capture_file(
    root: Path,
    untyped_output: object,
    *,
    label: str,
    pixel_format: int,
    byte_count: int,
) -> Path:
    output = mapping(untyped_output, f"{label} output")
    require(output.get("width") == WIDTH, f"{label} width differs")
    require(output.get("height") == HEIGHT, f"{label} height differs")
    require(
        output.get("pixelFormat") == pixel_format,
        f"{label} pixel format differs",
    )
    require(output.get("rawBytes") == byte_count, f"{label} byte count differs")
    relative = output.get("rawFile")
    require(isinstance(relative, str), f"{label} filename is absent")
    resolved_root = root.resolve()
    path = (root / relative).resolve()
    require(path.is_relative_to(resolved_root), f"{label} escapes capture root")
    require(path.is_file(), f"{label} is absent: {relative}")
    require(path.stat().st_size == byte_count, f"{label} file size differs")
    return path


def load_bgra8(path: Path) -> ByteImage:
    return np.fromfile(path, dtype=np.uint8).reshape(HEIGHT, WIDTH, CHANNELS)


def load_half_bits(path: Path) -> HalfBitsImage:
    return np.fromfile(path, dtype="<u2").reshape(HEIGHT, WIDTH, CHANNELS)


def half_blend_layer(
    destination_bgra8: ByteImage,
    source_rgba16_bits: HalfBitsImage,
) -> ByteImage:
    """Replay Apple's measured binary16 source-over BGRA8 fixed-function path."""
    require(
        destination_bgra8.shape == source_rgba16_bits.shape,
        "blend source and destination shapes differ",
    )
    destination_rgba8 = destination_bgra8[..., [2, 1, 0, 3]]
    source = source_rgba16_bits.view(np.float16)
    destination = (destination_rgba8.astype(np.float64) / np.float64(255)).astype(
        np.float16
    )
    destination_factor = (np.float64(1) - source[..., 3:4].astype(np.float64)).astype(
        np.float16
    )
    blended = (
        destination.astype(np.float64) * destination_factor.astype(np.float64)
        + source.astype(np.float64)
    ).astype(np.float16)
    output_rgba8 = np.clip(
        np.rint(blended.astype(np.float64) * np.float64(255)),
        0,
        255,
    ).astype(np.uint8)
    return np.ascontiguousarray(output_rgba8[..., [2, 1, 0, 3]])


def byte_metrics(reference: ByteImage, candidate: ByteImage) -> JsonObject:
    require(reference.shape == candidate.shape, "byte comparison shapes differ")
    delta = candidate.astype(np.int16) - reference.astype(np.int16)
    unequal = delta != 0
    unequal_pixels = np.any(unequal, axis=2)
    coordinates = np.argwhere(unequal_pixels)
    return {
        "comparedBytes": int(reference.size),
        "comparedPixels": int(reference.shape[0] * reference.shape[1]),
        "unequalBytes": int(np.count_nonzero(unequal)),
        "unequalPixels": int(np.count_nonzero(unequal_pixels)),
        "maximumChannelDelta": int(np.abs(delta).max(initial=0)),
        "exact": not bool(np.any(unequal)),
        "referenceSHA256": sha256_bytes(reference.tobytes()),
        "candidateSHA256": sha256_bytes(candidate.tobytes()),
        "firstMismatches": [
            {
                "x": int(x),
                "yTopLeft": int(y),
                "reference": reference[y, x].astype(int).tolist(),
                "candidate": candidate[y, x].astype(int).tolist(),
            }
            for y, x in coordinates[:16]
        ],
    }


def half_word_metrics(
    reference: HalfBitsImage,
    candidate: HalfBitsImage,
) -> JsonObject:
    require(reference.shape == candidate.shape, "half comparison shapes differ")
    unequal = reference != candidate
    unequal_pixels = np.any(unequal, axis=2)
    coordinates = np.argwhere(unequal_pixels)
    return {
        "comparedWords": int(reference.size),
        "comparedBytes": int(reference.nbytes),
        "comparedPixels": int(reference.shape[0] * reference.shape[1]),
        "unequalWords": int(np.count_nonzero(unequal)),
        "unequalPixels": int(np.count_nonzero(unequal_pixels)),
        "exact": not bool(np.any(unequal)),
        "referenceSHA256": sha256_bytes(reference.tobytes()),
        "candidateSHA256": sha256_bytes(candidate.tobytes()),
        "firstMismatches": [
            {
                "x": int(x),
                "yTopLeft": int(y),
                "referenceHex": [f"0x{int(value):04x}" for value in reference[y, x]],
                "candidateHex": [f"0x{int(value):04x}" for value in candidate[y, x]],
            }
            for y, x in coordinates[:16]
        ],
    }


def half_activity(values: HalfBitsImage) -> JsonObject:
    flattened = values.reshape(-1, CHANNELS)
    active = np.any(flattened != 0, axis=1)
    return {
        "activePixels": int(np.count_nonzero(active)),
        "distinctTuples": int(np.unique(flattened, axis=0).shape[0]),
        "distinctWordsByChannel": [
            int(np.unique(flattened[:, channel]).size) for channel in range(CHANNELS)
        ],
    }


def arithmetic_output(
    replay: Mapping[str, Any],
    *,
    name: str,
) -> Mapping[str, Any]:
    arithmetic = mapping(
        replay.get("backgroundArithmeticTrace"),
        "background arithmetic trace",
    )
    records = [
        mapping(value, "background arithmetic replay")
        for value in sequence(arithmetic.get("replays"), "arithmetic replays")
    ]
    matches = [record for record in records if record.get("name") == name]
    require(len(matches) == 1, f"arithmetic replay is not unique: {name}")
    numeric_replay = mapping(matches[0].get("replay"), f"{name} replay")
    require(numeric_replay.get("executed") is True, f"{name} did not execute")
    require(numeric_replay.get("glassDrawCount") == 1, f"{name} draw count differs")
    return mapping(numeric_replay.get("output"), f"{name} output")


def sample_replay(timeline: Mapping[str, Any]) -> Mapping[str, Any]:
    uniforms = mapping(
        timeline.get("dynamicBackgroundUniforms"),
        "dynamic background uniforms",
    )
    records = [
        mapping(value, "dynamic background record")
        for value in sequence(uniforms.get("records"), "dynamic background records")
    ]
    matches = [
        record for record in records if record.get("sampleIndex") == SAMPLE_INDEX
    ]
    require(len(matches) == 1, "sample 16 is not unique")
    render = mapping(matches[0].get("render"), "sample 16 render")
    return mapping(render.get("exactPassReplay"), "sample 16 exact pass replay")


def analyze(timeline_path: Path) -> JsonObject:
    timeline = mapping(
        json.loads(timeline_path.read_text(encoding="utf-8")),
        "timeline",
    )
    root = timeline_path.parent
    replay = sample_replay(timeline)
    private_layers = mapping(
        replay.get("backgroundPrivateLayerOutputs"),
        "private background layer outputs",
    )
    require(private_layers.get("schemaVersion") == 1, "private layer schema differs")
    require(private_layers.get("executed") is True, "private layers did not execute")
    require(
        private_layers.get("capturedAppleFunctionUnmodified") is True,
        "private Apple function was modified",
    )
    require(private_layers.get("targetPixelFormat") == 80, "private target differs")

    pre_path = capture_file(
        root,
        replay.get("preFinalPass"),
        label="pre-pass color",
        pixel_format=80,
        byte_count=BGRA8_BYTES,
    )
    private_main_path = capture_file(
        root,
        mapping(private_layers.get("main"), "private main").get("output"),
        label="private main BGRA8",
        pixel_format=80,
        byte_count=BGRA8_BYTES,
    )
    private_shadow_path = capture_file(
        root,
        mapping(private_layers.get("shadow"), "private shadow").get("output"),
        label="private shadow BGRA8",
        pixel_format=80,
        byte_count=BGRA8_BYTES,
    )
    independent = mapping(
        replay.get("independentGlassReplay"),
        "independent glass replay",
    )
    reference = mapping(independent.get("reference"), "glass-prefix reference")
    require(reference.get("glassDrawCount") == 2, "glass-prefix draw count differs")
    combined_path = capture_file(
        root,
        reference.get("output"),
        label="captured main-shadow sequence",
        pixel_format=80,
        byte_count=BGRA8_BYTES,
    )

    private_main_half_path = capture_file(
        root,
        arithmetic_output(replay, name="private-main-final-color"),
        label="private main half source",
        pixel_format=115,
        byte_count=RGBA16F_BYTES,
    )
    custom_main_half_path = capture_file(
        root,
        arithmetic_output(replay, name="final-color"),
        label="custom main half source",
        pixel_format=115,
        byte_count=RGBA16F_BYTES,
    )
    private_shadow_half_path = capture_file(
        root,
        arithmetic_output(replay, name="private-shadow-final-color"),
        label="private shadow half source",
        pixel_format=115,
        byte_count=RGBA16F_BYTES,
    )
    custom_shadow_half_path = capture_file(
        root,
        arithmetic_output(replay, name="custom-shadow-layer"),
        label="custom shadow half source",
        pixel_format=115,
        byte_count=RGBA16F_BYTES,
    )

    pre = load_bgra8(pre_path)
    captured_main = load_bgra8(private_main_path)
    captured_shadow = load_bgra8(private_shadow_path)
    captured_combined = load_bgra8(combined_path)
    private_main_half = load_half_bits(private_main_half_path)
    custom_main_half = load_half_bits(custom_main_half_path)
    private_shadow_half = load_half_bits(private_shadow_half_path)
    custom_shadow_half = load_half_bits(custom_shadow_half_path)

    source_comparisons = {
        "privateVsCustomMain": half_word_metrics(
            private_main_half,
            custom_main_half,
        ),
        "privateVsCustomShadow": half_word_metrics(
            private_shadow_half,
            custom_shadow_half,
        ),
    }
    predicted_main = half_blend_layer(pre, private_main_half)
    predicted_shadow = half_blend_layer(pre, private_shadow_half)
    predicted_combined = half_blend_layer(predicted_main, private_shadow_half)
    transfer_comparisons = {
        "isolatedMain": byte_metrics(captured_main, predicted_main),
        "isolatedShadow": byte_metrics(captured_shadow, predicted_shadow),
        "sequentialMainThenShadow": byte_metrics(
            captured_combined,
            predicted_combined,
        ),
    }
    source_activity = {
        "main": half_activity(private_main_half),
        "shadow": half_activity(private_shadow_half),
    }
    output_activity = {
        "mainVsPrePass": byte_metrics(pre, captured_main),
        "shadowVsPrePass": byte_metrics(pre, captured_shadow),
    }
    nonvacuous = (
        source_activity["main"]["activePixels"] >= 200_000
        and source_activity["main"]["distinctTuples"] >= 3_000
        and source_activity["shadow"]["activePixels"] >= 8_000
        and source_activity["shadow"]["distinctTuples"] >= 1_000
        and output_activity["mainVsPrePass"]["unequalPixels"] >= 200_000
        and output_activity["shadowVsPrePass"]["unequalPixels"] >= 8_000
    )
    exact = (
        all(
            comparison["exact"]
            for comparison in (
                *source_comparisons.values(),
                *transfer_comparisons.values(),
            )
        )
        and nonvacuous
    )
    paths = {
        "prePassBGRA8": pre_path,
        "capturedMainBGRA8": private_main_path,
        "capturedShadowBGRA8": private_shadow_path,
        "capturedCombinedBGRA8": combined_path,
        "privateMainRGBA16F": private_main_half_path,
        "customMainRGBA16F": custom_main_half_path,
        "privateShadowRGBA16F": private_shadow_half_path,
        "customShadowRGBA16F": custom_shadow_half_path,
    }
    return {
        "walleDynamicBackgroundLayerTransferSchemaVersion": 1,
        "classification": "same-run private/custom half-source and BGRA8 transfer closure",
        "source": {
            "timeline": str(timeline_path),
            "timelineSHA256": sha256_file(timeline_path),
            "sampleIndex": SAMPLE_INDEX,
            "sameRunPairingRequired": True,
            "rawFiles": {
                name: {
                    "file": path.name,
                    "sha256": sha256_file(path),
                }
                for name, path in paths.items()
            },
        },
        "implementation": {
            "file": Path(__file__).name,
            "sha256": sha256_file(Path(__file__).resolve()),
            "python": platform.python_version(),
            "numpy": np.__version__,
        },
        "measuredSemantics": {
            "destinationConversion": "binary16_RNE(BGRA8_UNORM / 255)",
            "destinationFactor": "binary16_RNE(binary16(1) - sourceAlpha)",
            "blend": "binary16_RNE_FMA(destination, destinationFactor, source)",
            "targetConversion": "clamp and binary16-to-UNORM8 round-to-nearest",
            "interLayerBoundary": "store BGRA8 after main, reload it before shadow",
            "tolerance": 0,
        },
        "sourceComparisons": source_comparisons,
        "transferComparisons": transfer_comparisons,
        "positiveControls": {
            "passed": bool(nonvacuous),
            "sourceActivity": source_activity,
            "outputActivity": output_activity,
            "minimums": {
                "mainActiveHalfPixels": 200_000,
                "mainDistinctHalfTuples": 3_000,
                "shadowActiveHalfPixels": 8_000,
                "shadowDistinctHalfTuples": 1_000,
                "mainChangedBGRA8Pixels": 200_000,
                "shadowChangedBGRA8Pixels": 8_000,
            },
        },
        "totalComparedBytes": sum(
            int(comparison["comparedBytes"])
            for comparison in (
                *source_comparisons.values(),
                *transfer_comparisons.values(),
            )
        ),
        "conclusion": {
            "exact": bool(exact),
            "remainingNaturalBackgroundPixelArithmeticUnknowns": 0 if exact else 1,
            "guardedWalleIntegrationAuthorized": bool(exact),
            "productionParityClaimed": False,
            "remainingProductProofGates": 2,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = analyze(arguments.timeline)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
        print(arguments.output)
    return 0 if result["conclusion"]["exact"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
