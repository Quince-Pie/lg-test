#!/usr/bin/env python3
"""Gate the prospective static regular producer crop on direct Retina evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

import static_regular_producer_geometry as model
import validate_variable_blur_selected_region_origin as selected_region


type JsonObject = dict[str, Any]
type HalfArray = NDArray[np.float16]
type UInt8Array = NDArray[np.uint8]

EXPECTED_RUNTIME_SCHEMA = 75
EXPECTED_OS_VERSION = "Version 26.6.1 (Build 25G76)"
EXPECTED_METAL_DEVICE = "Apple M1 Max"
EXPECTED_GEOMETRY = "circle-377-fractional-holdout"
EXPECTED_FRAGMENT = "downsample_4_frag_lph"
COPY_BASE_PIPELINE = "com.apple.coreanimation.variable_blur_copy_base_mip_compute"
REGULAR_DOWNSAMPLE_WEIGHT = np.float16(0.25)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(name + " is not an object")
    return value


def sequence(value: object, name: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise ValueError(name + " is not an array")
    return value


def _pipeline_label(snapshot: Mapping[str, Any]) -> str:
    pipeline = snapshot.get("pipeline")
    return str(pipeline.get("label", "")) if isinstance(pipeline, Mapping) else ""


def _pipeline_fragment(snapshot: Mapping[str, Any]) -> str:
    pipeline = snapshot.get("pipeline")
    descriptor = (
        pipeline.get("creationDescriptor")
        if isinstance(pipeline, Mapping)
        else None
    )
    return (
        str(descriptor.get("fragmentFunction", ""))
        if isinstance(descriptor, Mapping)
        else ""
    )


def _single(records: list[Mapping[str, Any]], name: str) -> Mapping[str, Any]:
    if len(records) != 1:
        raise ValueError(f"expected one {name}; found {len(records)}")
    return records[0]


def _texture_snapshots(runtime: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    render = mapping(runtime.get("carendererEvidence"), "CARenderer evidence")
    textures = mapping(render.get("metalTextureSnapshots"), "texture snapshots")
    return [
        mapping(value, "texture snapshot")
        for value in sequence(textures.get("snapshots"), "texture snapshot array")
    ]


def _wallpaper_snapshot(runtime: Mapping[str, Any]) -> Mapping[str, Any]:
    return _single(
        [
            snapshot
            for snapshot in _texture_snapshots(runtime)
            if snapshot.get("index") == 3
            and snapshot.get("pixelFormat") == 70
            and snapshot.get("width") == 1_024
            and snapshot.get("height") == 1_024
            and _pipeline_fragment(snapshot) == "TimgA2Xhfc_Ixrg"
            and isinstance(snapshot.get("rawFile"), str)
        ],
        "raw 1024x1024 diagnostic wallpaper",
    )


def _producer_snapshot(runtime: Mapping[str, Any]) -> Mapping[str, Any]:
    return _single(
        [
            snapshot
            for snapshot in _texture_snapshots(runtime)
            if snapshot.get("index") == 0
            and _pipeline_label(snapshot) == COPY_BASE_PIPELINE
            and isinstance(snapshot.get("rawFile"), str)
        ],
        "raw copy-base producer",
    )


def _read_rgba8(path: Path, *, width: int, height: int) -> UInt8Array:
    values = np.fromfile(path, dtype=np.uint8)
    expected = width * height * 4
    if values.size != expected:
        raise ValueError(f"{path} has {values.size} bytes; expected {expected}")
    return values.reshape(height, width, 4)


def _half_round(value: NDArray[Any]) -> HalfArray:
    return np.asarray(value, dtype=np.float64).astype(np.float16)


def _half_fma(
    left: HalfArray,
    right: np.float16,
    addend: HalfArray,
) -> HalfArray:
    return _half_round(
        left.astype(np.float64) * np.float64(right)
        + addend.astype(np.float64)
    )


def _unorm8(value: NDArray[Any]) -> UInt8Array:
    return np.clip(
        np.rint(np.asarray(value, dtype=np.float64) * 255),
        0,
        255,
    ).astype(np.uint8)


def replay_regular_producer(wallpaper: UInt8Array) -> UInt8Array:
    if wallpaper.shape != (1_024, 1_024, 4) or wallpaper.dtype != np.uint8:
        raise ValueError("diagnostic wallpaper shape or type differs")
    source = wallpaper[::-1, :, :][..., (2, 1, 0, 3)]

    def quadrant(offset_y: int, offset_x: int) -> HalfArray:
        code_sum = sum(
            (
                source[
                    offset_y + delta_y :: 4,
                    offset_x + delta_x :: 4,
                ].astype(np.uint16)
                for delta_y in (0, 1)
                for delta_x in (0, 1)
            ),
            start=np.zeros((256, 256, 4), dtype=np.uint16),
        )
        return _half_round(code_sum.astype(np.float64) * (0.25 / 255))

    samples = (
        quadrant(2, 0),
        quadrant(2, 2),
        quadrant(0, 0),
        quadrant(0, 2),
    )
    result = np.zeros_like(samples[0])
    for sample in samples:
        result = _half_fma(sample, REGULAR_DOWNSAMPLE_WEIGHT, result)
    return _unorm8(result)


def _strip_raw_stage_values(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _strip_raw_stage_values(item)
            for key, item in value.items()
            if key not in {"rawFile", "rawCapture"}
        }
    if isinstance(value, list):
        return [_strip_raw_stage_values(item) for item in value]
    return value


def _observed_policy(runtime: Mapping[str, Any]) -> JsonObject:
    render = dict(
        mapping(
            _strip_raw_stage_values(runtime.get("carendererEvidence")),
            "sanitized CARenderer evidence",
        )
    )
    for name in ("output", "exactPassReplay", "dynamicBackdropProducerBoundary"):
        render.pop(name, None)
    allocation = selected_region.allocation
    original_fragments = allocation.PRODUCER_FRAGMENTS
    allocation.PRODUCER_FRAGMENTS = frozenset(
        set(original_fragments) | {EXPECTED_FRAGMENT}
    )
    try:
        return selected_region.observed_policy({"render": render}, scale=0.25)
    finally:
        allocation.PRODUCER_FRAGMENTS = original_fragments


def _compare_bytes(predicted: UInt8Array, observed: UInt8Array) -> JsonObject:
    if predicted.shape != observed.shape:
        raise ValueError(f"pixel shapes differ: {predicted.shape} != {observed.shape}")
    delta = predicted.astype(np.int16) - observed.astype(np.int16)
    changed = delta != 0
    return {
        "exact": not bool(np.any(changed)),
        "comparedBytes": int(delta.size),
        "mismatchedBytes": int(np.count_nonzero(changed)),
        "mismatchedPixels": int(np.count_nonzero(np.any(changed, axis=2))),
        "maximumCodeDelta": int(np.abs(delta).max(initial=0)),
        "predictedSHA256": hashlib.sha256(predicted.tobytes()).hexdigest(),
        "observedSHA256": hashlib.sha256(observed.tobytes()).hexdigest(),
    }


def _check_source_hashes(
    repository: Path,
    preregistration: Mapping[str, Any],
) -> JsonObject:
    expected = mapping(preregistration.get("sourceSHA256"), "source hashes")
    observed: JsonObject = {}
    for untyped_path, untyped_digest in expected.items():
        if not isinstance(untyped_path, str) or not isinstance(untyped_digest, str):
            raise ValueError("source hash entry differs")
        path = repository / untyped_path
        digest = sha256_file(path)
        if digest != untyped_digest:
            raise ValueError(f"source SHA-256 differs for {untyped_path}")
        observed[untyped_path] = digest
    return observed


def validate(
    capture: Path,
    preregistration_path: Path,
    preflight_path: Path,
) -> JsonObject:
    repository = Path(__file__).resolve().parent.parent
    preregistration = mapping(
        json.loads(preregistration_path.read_text(encoding="utf-8")),
        "preregistration",
    )
    if (
        preregistration.get(
            "staticRegularProducerGeometryHoldoutPreregistrationSchemaVersion"
        )
        != 1
    ):
        raise ValueError("preregistration schema differs")
    source_hashes = _check_source_hashes(repository, preregistration)

    preflight = mapping(
        json.loads(preflight_path.read_text(encoding="utf-8")),
        "Retina preflight",
    )
    if (
        preflight.get("localRetinaCaptureSessionPreflightSchemaVersion") != 2
        or preflight.get("passed") is not True
        or preflight.get("displayActive") is not True
        or preflight.get("displayAsleep") is not False
        or preflight.get("sessionOnConsole") is not True
        or preflight.get("backingScaleFactor") != 2
        or preflight.get("physicalPixels") != [3_456, 2_234]
        or preflight.get("logicalPoints") != [1_728, 1_117]
    ):
        raise ValueError("physical Retina session preflight differs")

    runtime_path = capture / "runtime.json"
    runtime = mapping(json.loads(runtime_path.read_text(encoding="utf-8")), "runtime")
    if runtime.get("schemaVersion") != EXPECTED_RUNTIME_SCHEMA:
        raise ValueError("runtime schema differs")
    if runtime.get("osVersion") != EXPECTED_OS_VERSION:
        raise ValueError("runtime OS build differs")
    metal = mapping(runtime.get("metalDevice"), "Metal device")
    if (
        metal.get("name") != EXPECTED_METAL_DEVICE
        or metal.get("hasUnifiedMemory") is not True
        or metal.get("isHeadless") is not False
    ):
        raise ValueError("physical Metal device differs")

    geometry = mapping(runtime.get("geometryEvidence"), "geometry evidence")
    expected_geometry = mapping(
        preregistration.get("geometry"),
        "preregistered geometry",
    )
    if dict(geometry) != dict(expected_geometry) or geometry.get("name") != EXPECTED_GEOMETRY:
        raise ValueError("holdout geometry differs")
    profile = mapping(runtime.get("materialProfileEvidence"), "material profile")
    if (
        profile.get("material") != "regular"
        or profile.get("requestedAppearance") != "light"
        or profile.get("effectiveAppearanceMatchesRequest") is not True
    ):
        raise ValueError("holdout material profile differs")
    background = mapping(
        runtime.get("diagnosticBackgroundEvidence"),
        "diagnostic background",
    )
    if (
        background.get("pattern") != "coordinate-hash-rgb-1x1-cells-v1"
        or background.get("columns") != 1_024
        or background.get("rows") != 1_024
    ):
        raise ValueError("diagnostic wallpaper differs")
    render = mapping(runtime.get("carendererEvidence"), "CARenderer evidence")
    exact_replay = mapping(render.get("exactPassReplay"), "exact pass replay")
    if (
        render.get("executed") is not True
        or exact_replay.get("executed") is not True
        or exact_replay.get("exactByteMatch") is not True
        or exact_replay.get("glassDrawCount") != 2
    ):
        raise ValueError("native Metal pass replay differs")

    predicted = model.predict(geometry)
    frozen_prediction = mapping(
        preregistration.get("predictedPolicy"),
        "preregistered prediction",
    )
    for name, expected_value in frozen_prediction.items():
        if predicted.get(name) != expected_value:
            raise ValueError(
                "model output differs from preregistered prediction for " + name
            )
    observed = _observed_policy(runtime)
    policy_fields = (
        "cropOrigin",
        "textureCoordinateClamp",
        "producerExtent",
        "destinationExtent",
        "copyOffset",
        "effectiveOrigin",
    )
    policy_comparison = {
        name: {
            "predicted": predicted[name],
            "observed": observed[name],
            "exact": predicted[name] == observed[name],
        }
        for name in policy_fields
    }
    if not all(value["exact"] for value in policy_comparison.values()):
        raise ValueError("prospective producer/copy geometry differs")

    wallpaper_snapshot = _wallpaper_snapshot(runtime)
    producer_snapshot = _producer_snapshot(runtime)
    producer_extent = predicted["producerExtent"]
    if [producer_snapshot.get("width"), producer_snapshot.get("height")] != producer_extent:
        raise ValueError("raw producer extent differs")
    wallpaper_path = capture / str(wallpaper_snapshot["rawFile"])
    producer_path = capture / str(producer_snapshot["rawFile"])
    wallpaper = _read_rgba8(wallpaper_path, width=1_024, height=1_024)
    producer = _read_rgba8(
        producer_path,
        width=int(producer_extent[0]),
        height=int(producer_extent[1]),
    )
    full_producer = replay_regular_producer(wallpaper)
    crop_x, crop_y = predicted["cropOrigin"]
    active_width, active_height = predicted["activeExtent"]
    predicted_active = full_producer[
        crop_y : crop_y + active_height,
        crop_x : crop_x + active_width,
    ]
    observed_active = producer[:active_height, :active_width]
    pixel_comparison = _compare_bytes(predicted_active, observed_active)
    if pixel_comparison["exact"] is not True:
        raise ValueError("prospective producer crop pixels differ")

    return {
        "staticRegularProducerGeometryHoldoutResultSchemaVersion": 1,
        "passed": True,
        "authority": "prospective direct-Retina transfer holdout",
        "runtimeSHA256": sha256_file(runtime_path),
        "preregistrationSHA256": sha256_file(preregistration_path),
        "preflightSHA256": sha256_file(preflight_path),
        "sourceSHA256": source_hashes,
        "geometry": dict(geometry),
        "predictedPolicy": predicted,
        "observedPolicy": {name: observed[name] for name in policy_fields},
        "policyComparison": policy_comparison,
        "producerActivePixelComparison": pixel_comparison,
        "wallpaperRawSHA256": sha256_file(wallpaper_path),
        "producerRawSHA256": sha256_file(producer_path),
        "retinaPreflight": dict(preflight),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        report = validate(
            arguments.capture,
            arguments.preregistration,
            arguments.preflight,
        )
    except Exception as error:
        report = {
            "staticRegularProducerGeometryHoldoutResultSchemaVersion": 1,
            "passed": False,
            "error": str(error),
        }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
