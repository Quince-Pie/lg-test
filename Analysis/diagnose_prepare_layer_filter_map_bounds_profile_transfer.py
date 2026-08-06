#!/usr/bin/env python3
"""Diagnose structural FilterOp lanes in a failed profile-transfer run.

This is deliberately retrospective: observed store outputs and downstream crops
are used only to score structural lane signatures.  Its output may motivate a
new frozen validator, but it is never itself prospective parity evidence.
"""

from __future__ import annotations

import argparse
import json
import struct
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_prepare_layer_crop_policy_holdout_callback_retry as holdout
import analyze_prepare_layer_crop_union_operand_matrix as crop_analysis
import analyze_prepare_layer_filter_map_bounds_exact_replay as exact
import validate_prepare_layer_crop_policy_holdout as store_validator
import validate_prepare_layer_crop_transfer as crop_validator
import validate_prepare_layer_crop_union_operand as union_validator


PROFILE_PREFIX = "liquid-glass-filter-map-bounds-profile-"
PROFILE_SUFFIX = "-31074006001"
GEOMETRY = "circle-800-center"
MATERIALS = ("clear", "regular")
APPEARANCES = ("light", "dark")
DIRECTIONS = ("materialize", "dematerialize")


def same_f64(left: Sequence[float], right: Sequence[float]) -> bool:
    """Compare binary64 sequences without numerical tolerance."""

    return struct.pack(f"<{len(left)}d", *left) == struct.pack(
        f"<{len(right)}d", *right
    )


def profile_directory(
    root: Path, material: str, appearance: str, direction: str
) -> Path:
    return root / (
        f"{PROFILE_PREFIX}{material}-{appearance}-{direction}{PROFILE_SUFFIX}"
    )


def validate_base(
    trace_path: Path,
    timeline_path: Path,
    material: str,
    appearance: str,
    direction: str,
) -> Mapping[str, Any]:
    """Reuse the frozen base validator after authenticating profile metadata."""

    original_timeline_validator = crop_validator.validate_timeline
    original_topology = crop_validator.EXPECTED_NORMAL_PREPARE_RECURSION_DEPTHS

    def validate_profile_timeline(
        timeline: Mapping[str, Any], expected_geometry: str
    ) -> tuple[Mapping[str, Any], list[Any]]:
        if (
            timeline.get("material") != material
            or timeline.get("appearance") != appearance
            or timeline.get("direction") != direction
        ):
            raise ValueError("profile metadata differs")
        normalized = dict(timeline)
        normalized["material"] = "clear"
        normalized["appearance"] = "light"
        normalized["direction"] = "materialize"
        return original_timeline_validator(normalized, expected_geometry)

    crop_validator.validate_timeline = validate_profile_timeline
    if direction == "dematerialize":
        crop_validator.EXPECTED_NORMAL_PREPARE_RECURSION_DEPTHS = (3,) * 30 + (4, 4)
    try:
        return crop_validator.validate(trace_path, timeline_path, GEOMETRY)
    finally:
        crop_validator.validate_timeline = original_timeline_validator
        crop_validator.EXPECTED_NORMAL_PREPARE_RECURSION_DEPTHS = original_topology


def lane_key(store: Mapping[str, Any], mirror: Mapping[str, Any]) -> tuple[int, ...]:
    """Describe a store without reading its floating or integer output values."""

    return (
        int(store["recordIndex"]) - int(mirror["recordIndex"]),
        int(store["roleBase"]) - int(mirror["roleBase"]),
        int(store["prepareRecursionDepth"])
        - int(mirror["prepareRecursionDepth"]),
    )


def source_bounds(intermediates: Mapping[str, Any]) -> tuple[float, float, float, float]:
    transform = exact.sequence(intermediates.get("transformF64"), "lane transform")
    nominal = exact.rect(intermediates.get("nominalShapeF64"), "lane nominal shape")
    if len(transform) != 16:
        raise ValueError("lane transform component count differs")
    return (
        exact.finite(transform[12], "lane source x"),
        exact.finite(transform[13], "lane source y"),
        nominal[2],
        nominal[3],
    )


def replay_lane(
    intermediates: Mapping[str, Any],
    bounds: tuple[float, float, float, float],
    timeline_record: Mapping[str, Any],
) -> tuple[float, float, float, float]:
    transformed = exact.rect(
        intermediates.get("transformedDynamicBoundsF64"),
        "lane transformed dynamic bounds",
    )
    entry = (
        transformed[0] - 9.0,
        transformed[1] - 9.0,
        transformed[2] + 18.0,
        transformed[3] + 18.0,
    )
    carrier_values = exact.sequence(
        intermediates.get("carrierTranslationF64"), "lane carrier translation"
    )
    carrier = (
        exact.finite(carrier_values[0], "lane carrier x"),
        exact.finite(carrier_values[1], "lane carrier y"),
    )
    return exact.replay(
        entry,
        carrier,
        bounds,
        exact.finite(intermediates.get("shadowOffsetF64"), "lane shadow offset"),
        exact.filter_radius(timeline_record),
    )


def analyze_profile(
    directory: Path, material: str, appearance: str, direction: str
) -> dict[str, Any]:
    trace_path = directory / "prepare-layer-crop-policy-holdout-trace.json"
    timeline_path = directory / "transition-timeline.json"
    base_result = validate_base(
        trace_path, timeline_path, material, appearance, direction
    )
    trace = exact.mapping(
        json.loads(trace_path.read_text(encoding="utf-8")), "trace"
    )
    timeline = exact.mapping(
        json.loads(timeline_path.read_text(encoding="utf-8")), "timeline"
    )
    prepare_start = int(
        exact.mapping(trace.get("prepareLayer"), "prepare layer").get("symbolStart")
    )
    raw_stores = exact.sequence(
        exact.mapping(
            trace.get("cropPolicyHoldoutExtension"), "store extension"
        ).get("storeRecords"),
        "store records",
    )
    stores = [
        store_validator.validate_store_record(raw, index, prepare_start)
        for index, raw in enumerate(raw_stores)
    ]
    store_links = exact.sequence(
        exact.mapping(
            trace.get("cropPolicyHoldoutExtension"), "store extension"
        ).get("markerLinks"),
        "store links",
    )
    raw_unions = exact.sequence(
        exact.mapping(
            trace.get("cropUnionOperandExtension"), "union extension"
        ).get("unionRecords"),
        "union records",
    )
    unions = [
        union_validator.validate_union_record(raw, index, prepare_start)
        for index, raw in enumerate(raw_unions)
    ]
    union_links = exact.sequence(
        exact.mapping(
            trace.get("cropUnionOperandExtension"), "union extension"
        ).get("markerLinks"),
        "union links",
    )
    timeline_records = exact.sequence(
        exact.mapping(
            timeline.get("dynamicBackgroundUniforms"), "dynamic uniforms"
        ).get("records"),
        "timeline records",
    )
    public_records = exact.sequence(base_result.get("records"), "public records")
    if not (
        len(store_links)
        == len(union_links)
        == len(timeline_records)
        == len(public_records)
        == 32
    ):
        raise ValueError("profile sample inventory differs")

    occurrences: dict[tuple[int, ...], list[dict[str, Any]]] = defaultdict(list)
    sample_summaries: list[dict[str, Any]] = []
    for ordinal, (
        raw_store_link,
        raw_union_link,
        raw_timeline,
        raw_public,
    ) in enumerate(
        zip(
            store_links,
            union_links,
            timeline_records,
            public_records,
            strict=True,
        ),
        start=1,
    ):
        store_link = exact.mapping(raw_store_link, "store link")
        union_link = exact.mapping(raw_union_link, "union link")
        timeline_record = exact.mapping(raw_timeline, "timeline record")
        public = exact.mapping(raw_public, "public record")
        union_indices = [
            int(value)
            for value in exact.sequence(
                union_link.get("matchingUnionRecordIndices"), "matching unions"
            )
        ]
        if len(union_indices) != 2:
            raise ValueError(f"sample {ordinal} union topology differs")
        selected_union = unions[union_indices[-1]]
        selected_layer_shapes = int(selected_union["layerShapesBase"])
        start = int(store_link.get("startStoreRecordIndex"))
        end = int(store_link.get("endStoreRecordIndexExclusive"))
        mirror_indices = [
            store["recordIndex"]
            for store in stores[start:end]
            if int(store["layerShapesBase"]) == selected_layer_shapes
        ]
        if len(mirror_indices) != 1:
            raise ValueError(f"sample {ordinal} mirror store is not unique")
        mirror = stores[mirror_indices[0]]
        observed_crop = tuple(int(value) for value in selected_union["nestedInputI32"])
        viewport_values = exact.rect(
            exact.mapping(public.get("private"), "private record").get("viewportF64"),
            "viewport",
        )
        viewport = tuple(int(value) for value in viewport_values)
        keys: list[list[int]] = []
        for store in stores[start:end]:
            key = lane_key(store, mirror)
            payload = holdout.role_payload(
                raw_stores[store["recordIndex"]], store["roleBase"]
            )
            try:
                intermediates = holdout.role_intermediates(payload)
            except ValueError:
                intermediates = None
            occurrences[key].append(
                {
                    "sampleIndex": ordinal,
                    "store": store,
                    "intermediates": intermediates,
                    "timeline": timeline_record,
                    "observedCrop": observed_crop,
                    "viewport": viewport,
                    "layerShapesBaseDeltaFromMirror": (
                        int(store["layerShapesBase"])
                        - int(mirror["layerShapesBase"])
                    ),
                }
            )
            keys.append(list(key))
        sample_summaries.append(
            {
                "sampleIndex": ordinal,
                "storeWindow": [start, end],
                "storeCount": end - start,
                "mirrorStoreIndex": mirror["recordIndex"],
                "observedCropI32": list(observed_crop),
                "laneKeys": keys,
            }
        )

    lanes: list[dict[str, Any]] = []
    for key, records in sorted(occurrences.items()):
        terminal = [
            record
            for record in records
            if record["sampleIndex"] == 32
            and record["intermediates"] is not None
        ]
        bounds = (
            source_bounds(exact.mapping(terminal[0]["intermediates"], "terminal lane"))
            if len(terminal) == 1
            else None
        )
        exact_replay_samples: list[int] = []
        working_crop_samples: list[int] = []
        integerized_replay_samples: list[int] = []
        centered_child_replay_samples: list[int] = []
        centered_child_integerized_replay_samples: list[int] = []
        geometry_replay_samples: list[int] = []
        geometry_integerized_replay_samples: list[int] = []
        geometry_bounds = (0.0, 0.0, 800.0, 800.0)
        for record in records:
            if record["intermediates"] is None:
                continue
            store = exact.mapping(record["store"], "geometry lane store")
            candidate = replay_lane(
                exact.mapping(record["intermediates"], "geometry lane intermediates"),
                geometry_bounds,
                exact.mapping(record["timeline"], "geometry lane timeline"),
            )
            observed_float = exact.rect(
                store.get("floatingInputF64"), "geometry lane floating input"
            )
            sample_index = int(record["sampleIndex"])
            if same_f64(candidate, observed_float):
                geometry_replay_samples.append(sample_index)
            enclosure = crop_analysis.integer_crop(candidate)
            predicted_crop = crop_analysis.intersect_i32(
                enclosure, tuple(record["viewport"])
            )
            if predicted_crop == tuple(record["observedCrop"]):
                geometry_integerized_replay_samples.append(sample_index)
        if bounds is not None:
            terminal_intermediates = exact.mapping(
                terminal[0]["intermediates"], "terminal centered-child lane"
            )
            terminal_dynamic = exact.rect(
                terminal_intermediates.get("dynamicLocalBoundsF64"),
                "terminal dynamic-local bounds",
            )
            terminal_child = exact.rect(
                terminal_intermediates.get("recursiveChildF64"),
                "terminal recursive child",
            )
            centered_child_bounds = (
                terminal_dynamic[0]
                + (terminal_dynamic[2] - terminal_child[2]) * 0.5,
                terminal_dynamic[1]
                + (terminal_dynamic[3] - terminal_child[3]) * 0.5,
                terminal_child[2],
                terminal_child[3],
            )
            for record in records:
                if record["intermediates"] is None:
                    continue
                store = exact.mapping(record["store"], "lane store")
                candidate = replay_lane(
                    exact.mapping(record["intermediates"], "lane intermediates"),
                    bounds,
                    exact.mapping(record["timeline"], "lane timeline"),
                )
                observed_float = exact.rect(
                    store.get("floatingInputF64"), "lane floating input"
                )
                sample_index = int(record["sampleIndex"])
                if same_f64(candidate, observed_float):
                    exact_replay_samples.append(sample_index)
                observed_crop = tuple(record["observedCrop"])
                if tuple(store["workingCropI32"]) == observed_crop:
                    working_crop_samples.append(sample_index)
                enclosure = crop_analysis.integer_crop(candidate)
                predicted_crop = crop_analysis.intersect_i32(
                    enclosure, tuple(record["viewport"])
                )
                if predicted_crop == observed_crop:
                    integerized_replay_samples.append(sample_index)
                centered_candidate = replay_lane(
                    exact.mapping(
                        record["intermediates"], "centered-child lane intermediates"
                    ),
                    centered_child_bounds,
                    exact.mapping(record["timeline"], "centered-child lane timeline"),
                )
                if same_f64(centered_candidate, observed_float):
                    centered_child_replay_samples.append(sample_index)
                centered_enclosure = crop_analysis.integer_crop(centered_candidate)
                centered_crop = crop_analysis.intersect_i32(
                    centered_enclosure, tuple(record["viewport"])
                )
                if centered_crop == observed_crop:
                    centered_child_integerized_replay_samples.append(sample_index)
        else:
            centered_child_bounds = None
        lanes.append(
            {
                "structuralKey": {
                    "storeIndexDeltaFromMirror": key[0],
                    "roleBaseDeltaFromMirror": key[1],
                    "prepareDepthDeltaFromMirror": key[2],
                },
                "layerShapesBaseDeltasFromMirror": sorted(
                    {
                        int(record["layerShapesBaseDeltaFromMirror"])
                        for record in records
                    }
                ),
                "occurrenceCount": len(records),
                "decodableRoleCount": sum(
                    record["intermediates"] is not None for record in records
                ),
                "sampleIndices": [int(record["sampleIndex"]) for record in records],
                "terminalSourceBoundsF64": list(bounds) if bounds is not None else None,
                "terminalSourceBoundsHex": (
                    exact.f64_hex(bounds) if bounds is not None else None
                ),
                "exactFilterReplayCount": len(exact_replay_samples),
                "exactFilterReplaySampleIndices": exact_replay_samples,
                "workingCropMatchCount": len(working_crop_samples),
                "workingCropMatchSampleIndices": working_crop_samples,
                "integerizedReplayMatchCount": len(integerized_replay_samples),
                "integerizedReplayMatchSampleIndices": integerized_replay_samples,
                "centeredRecursiveChildSourceBoundsF64": (
                    list(centered_child_bounds)
                    if centered_child_bounds is not None
                    else None
                ),
                "centeredRecursiveChildExactFilterReplayCount": len(
                    centered_child_replay_samples
                ),
                "centeredRecursiveChildExactFilterReplaySampleIndices": (
                    centered_child_replay_samples
                ),
                "centeredRecursiveChildIntegerizedReplayMatchCount": len(
                    centered_child_integerized_replay_samples
                ),
                "centeredRecursiveChildIntegerizedReplayMatchSampleIndices": (
                    centered_child_integerized_replay_samples
                ),
                "geometrySourceBoundsF64": list(geometry_bounds),
                "geometryExactFilterReplayCount": len(geometry_replay_samples),
                "geometryExactFilterReplaySampleIndices": geometry_replay_samples,
                "geometryIntegerizedReplayMatchCount": len(
                    geometry_integerized_replay_samples
                ),
                "geometryIntegerizedReplayMatchSampleIndices": (
                    geometry_integerized_replay_samples
                ),
                "representativeRecords": [
                    {
                        "sampleIndex": int(record["sampleIndex"]),
                        "floatingInputF64": record["store"]["floatingInputF64"],
                        "workingCropI32": record["store"]["workingCropI32"],
                        "transformTranslationF64": (
                            record["intermediates"]["transformF64"][12:14]
                            if record["intermediates"] is not None
                            else None
                        ),
                        "transformedDynamicBoundsF64": (
                            record["intermediates"]["transformedDynamicBoundsF64"]
                            if record["intermediates"] is not None
                            else None
                        ),
                        "shadowOffsetF64": (
                            record["intermediates"]["shadowOffsetF64"]
                            if record["intermediates"] is not None
                            else None
                        ),
                        "carrierTranslationF64": (
                            record["intermediates"]["carrierTranslationF64"]
                            if record["intermediates"] is not None
                            else None
                        ),
                        "nominalShapeF64": (
                            record["intermediates"]["nominalShapeF64"]
                            if record["intermediates"] is not None
                            else None
                        ),
                        "dynamicLocalBoundsF64": (
                            record["intermediates"]["dynamicLocalBoundsF64"]
                            if record["intermediates"] is not None
                            else None
                        ),
                        "recursiveChildF64": (
                            record["intermediates"]["recursiveChildF64"]
                            if record["intermediates"] is not None
                            else None
                        ),
                    }
                    for record in records
                    if int(record["sampleIndex"]) in (1, 9, 23, 32)
                ],
            }
        )

    return {
        "profile": {
            "material": material,
            "appearance": appearance,
            "direction": direction,
        },
        "traceSHA256": crop_validator.sha256_file(trace_path),
        "timelineSHA256": crop_validator.sha256_file(timeline_path),
        "storeRecordCount": len(stores),
        "unionRecordCount": len(unions),
        "sampleCount": len(sample_summaries),
        "laneCount": len(lanes),
        "lanes": lanes,
        "samplesOfSpecialInterest": [
            sample_summaries[index - 1] for index in (9, 23, 32)
        ],
    }


def analyze(root: Path) -> dict[str, Any]:
    profiles = []
    for material in MATERIALS:
        for appearance in APPEARANCES:
            for direction in DIRECTIONS:
                directory = profile_directory(root, material, appearance, direction)
                profiles.append(
                    analyze_profile(directory, material, appearance, direction)
                )
    return {
        "classification": (
            "retrospective target-aware structural lane diagnosis of the failed "
            "profile-transfer run; this output is discovery evidence only"
        ),
        "runID": 31074006001,
        "geometry": GEOMETRY,
        "targetOutputsUsedToScoreCandidates": True,
        "prospectiveTransferEstablished": False,
        "profiles": profiles,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_root", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = analyze(arguments.artifact_root)
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    main()
