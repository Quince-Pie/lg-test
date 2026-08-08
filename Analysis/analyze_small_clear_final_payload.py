#!/usr/bin/env python3
"""Reconstruct the small-clear Tkfh fragment payload byte for byte."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
import struct
from typing import Any

import analyze_combined_transition_geometry_holdout_falsification as opened
import analyze_small_clear_final_geometry as geometry
import analyze_transition_geometry_corpus_local_macos_26_6_1 as model


type JsonObject = dict[str, Any]

RESULT_SCHEMA_VERSION = 1
FRAGMENT_PREFIX_BYTES = 248
PIPELINE = geometry.PIPELINE
GEOMETRY_RESULT_SHA256 = (
    "8600d81d693c316408064a868f100a3ead403e51c68aa994e10a8e154027ae00"
)
COLOR_INTERVENTION_RESULT_SHA256 = (
    "76f6da98693275e6c617aacdfa599fb8a9fa8ab3bf847eb0e5a1accd2a0e4f24"
)
FIXED_HALF_WORDS = (
    0x3C00,
    0x8001,
    0x0000,
    0xB9A8,
    0xB9A8,
    0x3C00,
    0x8001,
    0x0000,
    0x39A8,
    0x39A8,
    0x399A,
    0x0000,
    0x3C00,
    0x3C00,
    0x3C00,
    0x3C00,
    0x3C00,
    0x3C00,
    0x3C00,
    0x3C00,
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


def predicted_fragment_prefix(record: Mapping[str, Any]) -> bytes:
    _, _, _, _, width, height = geometry.layer_axes(record)
    half_x, _, radius_x, _ = geometry.small_axis_terms(width)
    half_y, _, radius_y, _ = geometry.small_axis_terms(height)
    require(
        model.float32_bits(half_x) == model.float32_bits(half_y),
        "small-clear half extents differ",
    )

    payload = bytearray(FRAGMENT_PREFIX_BYTES)
    struct.pack_into("<4f", payload, 0x00, radius_x, radius_y, 4.0, 0.0)
    struct.pack_into("<4f", payload, 0x10, 1.0, 0.0, 0.0, 1.0)
    struct.pack_into("<4f", payload, 0x20, 1.0, 1.0, half_x, 0.0)
    struct.pack_into(f"<{len(FIXED_HALF_WORDS)}H", payload, 0xD0, *FIXED_HALF_WORDS)
    return bytes(payload)


def observed_fragment_prefix(record: Mapping[str, Any]) -> bytes:
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
    binding = model.single(
        [
            value
            for value in records
            if value.get("kind") in {"buffer", "bufferOffset"}
            and value.get("stage") == "fragment"
            and value.get("index") == 1
        ],
        "small-clear fragment binding",
    )
    snapshots = [
        model.mapping(value, "Metal snapshot")
        for value in model.sequence(snapshots_record.get("snapshots"), "snapshots")
    ]
    snapshot = model.snapshot_at(
        snapshots,
        sequence_number=model.integer(binding.get("sequence"), "binding sequence"),
        stage="fragment",
        index=1,
        label=PIPELINE,
    )
    payload = model.payload(snapshot)
    require(
        len(payload) >= FRAGMENT_PREFIX_BYTES,
        "small-clear fragment payload is truncated",
    )
    return payload[:FRAGMENT_PREFIX_BYTES]


def validate_prerequisites(repository_root: Path) -> None:
    analysis = repository_root / "Analysis"
    for path, expected, label in (
        (
            analysis / "small_clear_final_geometry_result.json",
            GEOMETRY_RESULT_SHA256,
            "small-clear geometry result",
        ),
        (
            analysis / "small_clear_final_color_intervention_result.json",
            COLOR_INTERVENTION_RESULT_SHA256,
            "small-clear color intervention result",
        ),
    ):
        require(path.is_file(), f"missing {label}")
        require(sha256_file(path) == expected, f"{label} SHA-256 differs")


def analyze(repository_root: Path) -> JsonObject:
    validate_prerequisites(repository_root)
    artifact_root = repository_root / "artifacts"
    metrics: Counter[str] = Counter()
    source_results: list[JsonObject] = []
    observed_digest = hashlib.sha256()
    predicted_digest = hashlib.sha256()

    for name, expected_sha256, parent in geometry.TIMELINES:
        path = geometry.timeline_path(artifact_root, name, parent)
        require(path.is_file(), f"missing timeline: {name}")
        require(
            sha256_file(path) == expected_sha256,
            f"timeline SHA-256 differs: {name}",
        )
        timeline = json.loads(path.read_text(encoding="utf-8"))
        require(isinstance(timeline, dict), f"{name} timeline is not an object")
        records = model.validate_envelope(
            timeline,
            geometry.expected_timeline_case(name),
        )
        source_count = 0
        for record in records:
            if opened.SMALL_CLEAR_FINAL_HIGHLIGHT not in opened.pipeline_tokens(record):
                continue
            observed = observed_fragment_prefix(record)
            predicted = predicted_fragment_prefix(record)
            source_count += 1
            metrics["stateCount"] += 1
            metrics["byteCount"] += len(observed)
            metrics["mismatchedBytes"] += sum(
                actual != expected
                for actual, expected in zip(observed, predicted, strict=True)
            )
            observed_digest.update(observed)
            predicted_digest.update(predicted)
        source_results.append(
            {
                "name": name,
                "timelineSHA256": expected_sha256,
                "smallClearStateCount": source_count,
            }
        )

    require(metrics["stateCount"] == 123, "small-clear state census differs")
    require(metrics["byteCount"] == 30_504, "fragment byte census differs")
    require(metrics["mismatchedBytes"] == 0, "fragment payload differs")
    require(
        observed_digest.hexdigest()
        == "b5104c5c048679cd6a39d108d4239234af24bad229478b08852608b4083f012e",
        "observed fragment stream SHA-256 differs",
    )
    require(
        observed_digest.digest() == predicted_digest.digest(),
        "predicted fragment stream SHA-256 differs",
    )

    return {
        "smallClearFinalPayloadResultSchemaVersion": RESULT_SCHEMA_VERSION,
        "status": "exact-small-clear-final-payload-closure",
        "classification": (
            "hash-pinned retrospective fragment constructor plus prospective "
            "active-color pixel-irrelevance proof"
        ),
        "pipeline": PIPELINE,
        "stateCount": metrics["stateCount"],
        "sources": source_results,
        "fragmentPrefix": {
            "bytesPerState": FRAGMENT_PREFIX_BYTES,
            "comparedBytes": metrics["byteCount"],
            "mismatchedBytes": metrics["mismatchedBytes"],
            "observedSHA256": observed_digest.hexdigest(),
            "predictedSHA256": predicted_digest.hexdigest(),
            "zeroRegionOffset": 0x30,
            "zeroRegionBytes": 160,
            "fixedHalfRegionOffset": 0xD0,
            "fixedHalfWords": [f"0x{value:04x}" for value in FIXED_HALF_WORDS],
            "exact": True,
        },
        "constructor": {
            "radius": "binary32(binary32((extent+18)/2)-9)",
            "halfExtent": "binary32(extent/2)",
            "float4At0x00": ["radiusX", "radiusY", 4, 0],
            "float4At0x10": [1, 0, 0, 1],
            "float4At0x20": [1, 1, "halfExtentX", 0],
        },
        "activeColor": {
            "result": "Analysis/small_clear_final_color_intervention_result.json",
            "resultSHA256": COLOR_INTERVENTION_RESULT_SHA256,
            "declaredActive": True,
            "observationallyPixelRelevant": False,
            "comparedBytes": 131_072,
            "unequalBytes": 0,
        },
        "geometryResultSHA256": GEOMETRY_RESULT_SHA256,
        "tkfhInputConstructionClosed": True,
        "smallClearFamilyClosed": False,
        "appleUnknownsBlockingGatedWalleIntegration": 0,
        "remainingAppleAlgorithmFamilies": [
            "small-clear Tghn/Tmua/A2Xghfc background, producer, composition, and pixel semantics"
        ],
        "remainingSmallClearSubBoundaries": [
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
