#!/usr/bin/env python3
"""Validate exact-state producer-allocation translation interventions."""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import validate_dynamic_allocation_holdout as holdout


EXPECTED_GEOMETRY = "circle-640-center"
EXPECTED_SAMPLE_INDICES = tuple(range(1, 33))
EXPECTED_SOURCE_SAMPLE_INDICES = (18, 23, 25, 28, 31)
EXPECTED_TRANSLATIONS = (
    ("base", (0, 0)),
    ("x-negative-91", (-91, 0)),
    ("x-negative-90", (-90, 0)),
    ("x-negative-89", (-89, 0)),
    ("x-negative-1", (-1, 0)),
    ("x-positive-1", (1, 0)),
    ("x-positive-89", (89, 0)),
    ("x-positive-90", (90, 0)),
    ("x-positive-91", (91, 0)),
    ("x-positive-92", (92, 0)),
    ("y-negative-135", (0, -135)),
    ("y-negative-134", (0, -134)),
    ("y-negative-133", (0, -133)),
    ("y-negative-132", (0, -132)),
    ("y-negative-1", (0, -1)),
    ("y-positive-1", (0, 1)),
    ("y-positive-133", (0, 133)),
    ("y-positive-134", (0, 134)),
    ("y-positive-135", (0, 135)),
    ("y-positive-136", (0, 136)),
    ("target-integer", (90, -134)),
    ("target-half-even", (91, -133)),
    ("target-half-signed", (-90, 135)),
)
EXPECTED_BOUNDS_AND_POSITION_PATHS = (
    (1, 0, 1),
    (1, 0, 1, 0),
    (1, 0, 1, 0, 0),
    (1, 0, 1, 1),
    (1, 0, 1, 1, 0),
    (1, 0, 1, 1, 0, 0),
    (1, 0, 1, 2),
)
EXPECTED_POSITION_ONLY_PATHS = ((1, 0, 1, 0, 0, 0, 0),)
CLASSIFICATION = (
    "preregistered-fixed-apple-filter-and-layer-state-translation-calibration"
)


def sequence(value: object, name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{name} is not an array")
    return value


def translated_layer_states(
    states: Sequence[Any], delta: tuple[int, int]
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for untyped_state in states:
        state = copy.deepcopy(dict(holdout.mapping(untyped_state, "layer state")))
        path = tuple(int(value) for value in sequence(state.get("path"), "layer path"))
        translates_bounds = path in EXPECTED_BOUNDS_AND_POSITION_PATHS
        translates_position = translates_bounds or path in EXPECTED_POSITION_ONLY_PATHS
        if translates_bounds:
            bounds = list(sequence(state.get("bounds"), "layer bounds"))
            if len(bounds) != 4:
                raise ValueError("translated layer bounds are not a rectangle")
            bounds[0] = holdout.numeric(bounds[0], "bounds X") + delta[0]
            bounds[1] = holdout.numeric(bounds[1], "bounds Y") + delta[1]
            state["bounds"] = bounds
        if translates_position:
            position = list(sequence(state.get("position"), "layer position"))
            if len(position) != 2:
                raise ValueError("translated layer position is not a point")
            position[0] = holdout.numeric(position[0], "position X") + delta[0]
            position[1] = holdout.numeric(position[1], "position Y") + delta[1]
            state["position"] = position
        result.append(state)
    return result


def validate(path: Path) -> dict[str, Any]:
    base = holdout.validate(
        path,
        expected_geometry=EXPECTED_GEOMETRY,
        expected_sample_indices=EXPECTED_SAMPLE_INDICES,
        classification=CLASSIFICATION,
        allowed_geometries=frozenset({EXPECTED_GEOMETRY}),
    )
    report = holdout.mapping(
        json.loads(path.read_text(encoding="utf-8")),
        "transition report",
    )
    uniforms = holdout.mapping(
        report.get("dynamicBackgroundUniforms"),
        "dynamic background uniforms",
    )
    fixed = holdout.mapping(
        uniforms.get("fixedStateInterventions"),
        "fixed-state interventions",
    )
    expected_record_count = len(EXPECTED_SOURCE_SAMPLE_INDICES) * len(
        EXPECTED_TRANSLATIONS
    )
    if (
        fixed.get("schemaVersion") != 1
        or fixed.get("requested") is not True
        or fixed.get("executed") is not True
        or fixed.get("sourceSampleIndices") != list(EXPECTED_SOURCE_SAMPLE_INDICES)
        or fixed.get("translationCount") != len(EXPECTED_TRANSLATIONS)
        or fixed.get("expectedRecordCount") != expected_record_count
        or fixed.get("executedRecordCount") != expected_record_count
        or fixed.get("translatedBoundsAndPositionPaths")
        != [list(path_value) for path_value in EXPECTED_BOUNDS_AND_POSITION_PATHS]
        or fixed.get("translatedPositionOnlyPaths")
        != [list(path_value) for path_value in EXPECTED_POSITION_ONLY_PATHS]
        or not holdout.no_raw_stage_dumps(fixed)
    ):
        raise ValueError("fixed-state intervention header differs")
    untyped_fixed_records = sequence(fixed.get("records"), "fixed-state records")
    if len(untyped_fixed_records) != expected_record_count:
        raise ValueError("fixed-state record count differs")

    normal_records = {
        int(
            holdout.mapping(value, "normal dynamic record")["sampleIndex"]
        ): holdout.mapping(value, "normal dynamic record")
        for value in sequence(uniforms.get("records"), "normal dynamic records")
    }
    base_states = {
        int(holdout.mapping(value, "base state")["sampleIndex"]): holdout.mapping(
            value, "base state"
        )
        for value in sequence(base.get("states"), "base validated states")
    }
    expected_order = [
        (sample_index, translation_index, name, delta)
        for sample_index in EXPECTED_SOURCE_SAMPLE_INDICES
        for translation_index, (name, delta) in enumerate(EXPECTED_TRANSLATIONS)
    ]
    validated_records: list[dict[str, Any]] = []
    source_layer_hashes: dict[int, str] = {}
    source_filter_hashes: dict[int, str] = {}
    topology_counts: Counter[int] = Counter()

    for untyped_record, expected in zip(
        untyped_fixed_records, expected_order, strict=True
    ):
        sample_index, translation_index, translation_name, delta = expected
        record = holdout.mapping(untyped_record, "fixed-state record")
        translation = tuple(
            int(value) for value in sequence(record.get("translation"), "translation")
        )
        if (
            record.get("sampleIndex") != sample_index
            or record.get("translationIndex") != translation_index
            or record.get("translationName") != translation_name
            or translation != delta
            or record.get("executed") is not True
            or record.get("originalProducerInput") is not True
            or record.get("filterInputValuesUnchanged") is not True
            or record.get("missingCriticalCarrierPaths") != []
        ):
            raise ValueError(
                f"fixed-state record differs at {sample_index}/{translation_name}"
            )
        normal = normal_records[sample_index]
        remaining = holdout.numeric(record.get("remaining"), "remaining")
        if remaining != holdout.numeric(normal.get("remaining"), "normal remaining"):
            raise ValueError("fixed and normal remaining values differ")
        source_layer_hash = record.get("sourceLayerStatesSHA256")
        source_filter_hash = record.get("sourceFilterInputValuesSHA256")
        replayed_filter_hash = record.get("replayedFilterInputValuesSHA256")
        if (
            not isinstance(source_layer_hash, str)
            or len(source_layer_hash) != 64
            or not isinstance(source_filter_hash, str)
            or len(source_filter_hash) != 64
            or source_filter_hash != replayed_filter_hash
        ):
            raise ValueError("fixed-state source identity differs")
        if (
            source_layer_hashes.setdefault(sample_index, source_layer_hash)
            != source_layer_hash
        ):
            raise ValueError("source layer state changed within one sample")
        if (
            source_filter_hashes.setdefault(sample_index, source_filter_hash)
            != source_filter_hash
        ):
            raise ValueError("source filter changed within one sample")

        normal_layer_states = sequence(
            normal.get("capturedLayerStates"), "normal captured layer states"
        )
        expected_states = translated_layer_states(normal_layer_states, delta)
        translated_states = sequence(
            record.get("translatedLayerStates"), "translated layer states"
        )
        captured_states = sequence(
            record.get("capturedLayerStates"), "replayed captured layer states"
        )
        if (
            list(translated_states) != expected_states
            or list(captured_states) != expected_states
        ):
            raise ValueError("fixed-state replay changed undeclared layer state")

        scale, layer_state_count = holdout.captured_scale(record)
        expected_scale = 1.0 - remaining / 2.0
        if scale != expected_scale:
            raise ValueError("fixed-state backdrop scale differs")
        observed = holdout.observed_policy(record, scale=scale)
        mesh = holdout.mapping(observed.get("producerMesh"), "producer mesh")
        topology_counts[int(mesh["vertexCount"])] += 1
        if (
            translation_name == "base"
            and observed != base_states[sample_index]["observed"]
        ):
            raise ValueError("zero-translation replay differs from normal replay")
        validated_records.append(
            {
                "sampleIndex": sample_index,
                "remaining": remaining,
                "runtimeScale": scale,
                "translationIndex": translation_index,
                "translationName": translation_name,
                "translation": list(delta),
                "capturedLayerStateCount": layer_state_count,
                "sourceLayerStatesSHA256": source_layer_hash,
                "sourceFilterInputValuesSHA256": source_filter_hash,
                "observed": observed,
            }
        )

    return {
        "dynamicAllocationFixedStateResultSchemaVersion": 1,
        "classification": CLASSIFICATION,
        "timeline": str(path),
        "timelineSHA256": holdout.sha256_file(path),
        "geometry": report.get("geometry"),
        "sourceSampleIndices": list(EXPECTED_SOURCE_SAMPLE_INDICES),
        "translations": [
            {"name": name, "delta": list(delta)}
            for name, delta in EXPECTED_TRANSLATIONS
        ],
        "aggregate": {
            "recordCount": len(validated_records),
            "sourceStateCount": len(EXPECTED_SOURCE_SAMPLE_INDICES),
            "translationCount": len(EXPECTED_TRANSLATIONS),
            "producerVertexCountStates": {
                str(count): topology_counts[count] for count in sorted(topology_counts)
            },
            "sameRemainingWithinEachSourceState": True,
            "sameFilterInputsWithinEachSourceState": True,
            "onlyPreregisteredLayerFieldsTranslated": True,
            "zeroTranslationReplayExact": True,
            "originalProducerInputEveryState": True,
            "rawStageDumpsAbsent": True,
        },
        "records": validated_records,
        "conclusion": {
            "captureIntegrityPassed": True,
            "causalCalibrationOnly": True,
            "independentProducerMeshPolicyRecovered": False,
            "requiresUnseenHoldout": True,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.report)
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
        print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
