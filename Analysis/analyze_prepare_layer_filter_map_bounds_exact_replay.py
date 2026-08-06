#!/usr/bin/env python3
"""Replay Apple's retained FilterOp arithmetic over the crop holdout corpus."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import struct
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_prepare_layer_crop_policy_holdout_callback_retry as holdout
import validate_prepare_layer_filter_map_bounds as filter_validator
import validate_prepare_layer_mask_instruction_trace as mask_validator


ANALYSIS_SCHEMA_VERSION = 1
HOLDOUT_RESULT_SHA256 = (
    "8161ff4797735ac4ffa206e4347569f85c18ca519833ca13c163233a06f04847"
)
ROLE_TRANSFORMED_DYNAMIC_BOUNDS_OFFSET = 0x580
ROLE_CARRIER_TRANSLATION_OFFSET = 0x5F0
ROLE_NOMINAL_SHAPE_OFFSET = 0x600
ROLE_SHADOW_OFFSET = 0x5E0
CALLER_ROLE_BYTE_COUNT = 0x800

FILTER_ARTIFACTS = {
    "circle-1025-center": {
        "runID": 31070080768,
        "headSHA": "38829224b269e747b77a5f09a464e659408df5a9",
        "artifactID": 8955408760,
        "artifactName": "liquid-glass-prepare-layer-filter-map-bounds-31070080768",
        "artifactSizeBytes": 104879790,
        "artifactDigest": "sha256:d5cfb2b82d7cf44e072c23bb247aa47fe1f0b7cf0266de92272b505d7a95cd4a",
        "traceSHA256": "37aefd5f2b21c2ef3b0c8b8b51778cfa670c3e5f71e76e526ade0c899dfed5a7",
        "timelineSHA256": "19dd416efbc301752c6bb8a777ec18e5256aea954b4f9c41a51de348139338a5",
        "instructionStatesSHA256": "9c05f09a1f306ff3ff65e02649ee601a4f4cbc7fc5efe7aef2f75b37a7e34886",
        "workflowConclusion": "success",
    },
    "circle-513-center": {
        "runID": 31071749739,
        "headSHA": "dca69c5c85046a186d416d95c2bc1b4e67108288",
        "artifactID": 8955982682,
        "artifactName": "liquid-glass-prepare-layer-filter-map-bounds-513-callback-retry-31071749739",
        "artifactSizeBytes": 94353542,
        "artifactDigest": "sha256:1ed1589245dc944777a2fe67777bb43a1a32d69012a471d590bc134c6e005b27",
        "traceSHA256": "fb2beb1c312abf59237e97822f1b15400238c7974e32536b2759da3413df0ac7",
        "timelineSHA256": "7058cbe598d2c274038167ebc058686f274b334896b77aefd40dfdce6418e662",
        "instructionStatesSHA256": "fefb958afb3f9bdd00ef9799f3d79dc7f85282dc4e9a49868259a9253777dbef",
        "workflowConclusion": "failure",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} is not an object")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{label} is not an array")
    return value


def finite(value: Any, label: str) -> float:
    result = float(value)
    if isinstance(value, bool) or not math.isfinite(result):
        raise ValueError(f"{label} is not finite")
    return result


def rect(value: Any, label: str) -> tuple[float, float, float, float]:
    values = sequence(value, label)
    if len(values) != 4:
        raise ValueError(f"{label} does not contain four components")
    return tuple(finite(component, label) for component in values)  # type: ignore[return-value]


def f64_hex(values: Sequence[float]) -> str:
    return struct.pack(f"<{len(values)}d", *values).hex()


def binary64_fma(left: float, right: float, addend: float) -> float:
    if hasattr(math, "fma"):
        return math.fma(left, right, addend)
    function = ctypes.CDLL(None).fma
    function.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double]
    function.restype = ctypes.c_double
    return float(function(left, right, addend))


def simd_pair(state: Mapping[str, Any], register: str) -> tuple[float, float]:
    registers = mapping(state.get("registersAfter"), "register state")
    matches = [
        mapping(raw, "SIMD register")
        for raw in sequence(registers.get("simd"), "SIMD registers")
        if mapping(raw, "SIMD register").get("name") == register
    ]
    if len(matches) != 1:
        raise ValueError(f"{register} is not unique")
    payload = bytes.fromhex(str(matches[0].get("hex")))
    if len(payload) != 16:
        raise ValueError(f"{register} byte count differs")
    return struct.unpack("<2d", payload)


def state_at(states: Sequence[Any], scope: str, offset: int) -> Mapping[str, Any]:
    matches = [
        mapping(raw, "instruction state")
        for raw in states
        if mapping(raw, "instruction state").get("openedScopeName") == scope
        and mapping(
            mapping(raw, "instruction state").get("instruction"), "instruction"
        ).get("scopeOffset")
        == offset
    ]
    if len(matches) != 1:
        raise ValueError(f"{scope}+{offset:#x} is not unique")
    return matches[0]


def validate_513(
    trace_path: Path, timeline_path: Path, inventory_path: Path
) -> dict[str, Any]:
    geometry = "circle-513-center"
    original_filter_geometry = filter_validator.EXPECTED_GEOMETRY
    original_mask_geometry = mask_validator.EXPECTED_GEOMETRY
    original_mask_configuration = mask_validator.EXPECTED_CONFIGURATION
    adapted_configuration = dict(original_mask_configuration)
    adapted_configuration["expectedGeometry"] = geometry
    filter_validator.EXPECTED_GEOMETRY = geometry
    mask_validator.EXPECTED_GEOMETRY = geometry
    mask_validator.EXPECTED_CONFIGURATION = adapted_configuration
    try:
        return filter_validator.validate(
            trace_path, timeline_path, inventory_path, geometry
        )
    finally:
        filter_validator.EXPECTED_GEOMETRY = original_filter_geometry
        mask_validator.EXPECTED_GEOMETRY = original_mask_geometry
        mask_validator.EXPECTED_CONFIGURATION = original_mask_configuration


def role_values(state: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = mapping(state.get("callerRoleBefore"), "caller role")
    payload = bytes.fromhex(str(snapshot.get("hex")))
    if len(payload) != CALLER_ROLE_BYTE_COUNT:
        raise ValueError("caller role byte count differs")
    return {
        "transformed": struct.unpack_from(
            "<4d", payload, ROLE_TRANSFORMED_DYNAMIC_BOUNDS_OFFSET
        ),
        "carrier": struct.unpack_from("<2d", payload, ROLE_CARRIER_TRANSLATION_OFFSET),
        "nominal": struct.unpack_from("<4d", payload, ROLE_NOMINAL_SHAPE_OFFSET),
        "shadow": struct.unpack_from("<d", payload, ROLE_SHADOW_OFFSET)[0],
    }


def filter_radius(record: Mapping[str, Any]) -> float:
    values = mapping(
        mapping(record.get("filter"), "filter").get("inputValues"), "inputs"
    )
    blur = finite(values.get("inputBlurRadius"), "blur radius")
    bleed = finite(values.get("inputBleedBlurRadius"), "bleed blur radius")
    return max(2.0 * blur, bleed)


def replay(
    entry: tuple[float, float, float, float],
    carrier: tuple[float, float],
    source_bounds: tuple[float, float, float, float],
    shadow_y: float,
    radius: float,
) -> tuple[float, float, float, float]:
    transform_x = -carrier[0]
    transform_y = carrier[1]
    local_origin = (
        entry[0] - transform_x,
        -((entry[1] - transform_y) + entry[3]),
    )
    local_size = entry[2:4]

    negative_expansion = radius * -2.8
    expanded_origin = (
        local_origin[0] + negative_expansion,
        local_origin[1] + negative_expansion,
    )
    expanded_size = (
        binary64_fma(radius, 5.6, local_size[0]),
        binary64_fma(radius, 5.6, local_size[1]),
    )
    shadow_origin = (local_origin[0], local_origin[1] + shadow_y)
    expanded_far = (
        expanded_origin[0] + expanded_size[0],
        expanded_origin[1] + expanded_size[1],
    )
    shadow_far = (
        shadow_origin[0] + local_size[0],
        shadow_origin[1] + local_size[1],
    )
    union_origin = (
        min(expanded_origin[0], shadow_origin[0]),
        min(expanded_origin[1], shadow_origin[1]),
    )
    union_far = (
        max(expanded_far[0], shadow_far[0]),
        max(expanded_far[1], shadow_far[1]),
    )
    union_size = (
        union_far[0] - union_origin[0],
        union_far[1] - union_origin[1],
    )

    source_origin = source_bounds[0:2]
    source_size = source_bounds[2:4]
    source_shadow_origin = (
        source_origin[0],
        source_origin[1] + shadow_y,
    )
    source_far = (
        source_origin[0] + source_size[0],
        source_origin[1] + source_size[1],
    )
    source_shadow_far = (
        source_shadow_origin[0] + source_size[0],
        source_shadow_origin[1] + source_size[1],
    )
    source_union_origin = (
        min(source_origin[0], source_shadow_origin[0]),
        min(source_origin[1], source_shadow_origin[1]),
    )
    source_union_far = (
        max(source_far[0], source_shadow_far[0]),
        max(source_far[1], source_shadow_far[1]),
    )

    replay_far = (
        union_origin[0] + union_size[0],
        union_origin[1] + union_size[1],
    )
    intersection_origin = (
        max(union_origin[0], source_union_origin[0]),
        max(union_origin[1], source_union_origin[1]),
    )
    intersection_far = (
        min(replay_far[0], source_union_far[0]),
        min(replay_far[1], source_union_far[1]),
    )
    intersection_size = (
        intersection_far[0] - intersection_origin[0],
        intersection_far[1] - intersection_origin[1],
    )

    world_y = -(intersection_origin[1] + intersection_size[1])
    return (
        intersection_origin[0] + transform_x,
        world_y + transform_y,
        intersection_size[0],
        intersection_size[1],
    )


def analyze_filter_artifact(
    geometry: str, directory: Path, inventory_path: Path
) -> tuple[dict[str, Any], tuple[float, float, float, float]]:
    specification = FILTER_ARTIFACTS[geometry]
    trace_path = directory / "prepare-layer-filter-map-bounds-trace.json"
    timeline_path = directory / "transition-timeline.json"
    if (
        sha256(trace_path) != specification["traceSHA256"]
        or sha256(timeline_path) != specification["timelineSHA256"]
    ):
        raise ValueError(f"{geometry} Filter artifact hash differs")

    if geometry == "circle-513-center":
        validation = validate_513(trace_path, timeline_path, inventory_path)
    else:
        validation = filter_validator.validate(
            trace_path, timeline_path, inventory_path, geometry
        )
    if (
        validation.get("conclusion") != "success"
        or mapping(validation.get("filter"), "filter validation").get(
            "instructionStatesSHA256"
        )
        != specification["instructionStatesSHA256"]
    ):
        raise ValueError(f"{geometry} Filter validation differs")

    trace = mapping(json.loads(trace_path.read_text(encoding="utf-8")), "trace")
    extension = mapping(
        trace.get("prepareLayerFilterMapBoundsExtension"), "Filter extension"
    )
    states = sequence(extension.get("filterInstructionStates"), "Filter states")
    source_origin = simd_pair(state_at(states, "glassBackgroundDOD", 0x1F8), "v0")
    source_size = simd_pair(state_at(states, "glassBackgroundDOD", 0x1FC), "v1")
    source_bounds = (*source_origin, *source_size)

    first_state = mapping(states[0], "first Filter state")
    role = role_values(first_state)
    correlation = mapping(
        validation.get("structuralCorrelation"), "structural correlation"
    )
    entry = rect(correlation.get("entryF64"), "Filter entry")
    producer = rect(correlation.get("producerF64"), "Filter producer")
    timeline = mapping(
        json.loads(timeline_path.read_text(encoding="utf-8")), "timeline"
    )
    records = sequence(
        mapping(timeline.get("dynamicBackgroundUniforms"), "dynamic uniforms").get(
            "records"
        ),
        "timeline records",
    )
    radius = filter_radius(mapping(records[1], "sample-two timeline record"))
    live_replay = replay(
        entry,
        tuple(role["carrier"]),  # type: ignore[arg-type]
        source_bounds,
        finite(role["shadow"], "shadow offset"),
        radius,
    )
    if f64_hex(live_replay) != f64_hex(producer):
        raise ValueError(f"{geometry} live instruction replay differs")
    return (
        {
            **specification,
            "geometry": geometry,
            "sourceBoundsF64": list(source_bounds),
            "sourceBoundsHex": f64_hex(source_bounds),
            "entryF64": list(entry),
            "entryHex": f64_hex(entry),
            "producerF64": list(producer),
            "producerHex": f64_hex(producer),
            "liveReplayF64": list(live_replay),
            "liveReplayHex": f64_hex(live_replay),
            "liveReplayExact": True,
            "filterInstructionCount": mapping(
                validation.get("filter"), "filter validation"
            ).get("filterInstructionCount"),
            "executionEventCount": mapping(
                validation.get("filter"), "filter validation"
            ).get("executionEventCount"),
            "opaqueCalleeBoundaryCount": mapping(
                validation.get("filter"), "filter validation"
            ).get("opaqueCalleeBoundaryCount"),
            "filterReturnMatchesProducerBitForBit": correlation.get(
                "filterReturnMatchesProducerBitForBit"
            ),
        },
        source_bounds,
    )


def analyze(
    holdout_result_path: Path,
    holdout_root: Path,
    inventory_path: Path,
    filter_1025_root: Path,
    filter_513_root: Path,
) -> dict[str, Any]:
    if sha256(holdout_result_path) != HOLDOUT_RESULT_SHA256:
        raise ValueError("holdout result hash differs")
    holdout_result = mapping(
        json.loads(holdout_result_path.read_text(encoding="utf-8")),
        "holdout result",
    )
    live_results: list[dict[str, Any]] = []
    measured_bounds: dict[str, tuple[float, float, float, float]] = {}
    for geometry, root in (
        ("circle-1025-center", filter_1025_root),
        ("circle-513-center", filter_513_root),
    ):
        live, source_bounds = analyze_filter_artifact(geometry, root, inventory_path)
        live_results.append(live)
        measured_bounds[geometry] = source_bounds

    holdout_records = [
        mapping(raw, "holdout record")
        for raw in sequence(holdout_result.get("records"), "holdout records")
    ]
    terminal_bounds: dict[str, tuple[float, float, float, float]] = {}
    for record in holdout_records:
        if int(record.get("sampleIndex")) != 32:
            continue
        geometry = str(record.get("geometry"))
        role = mapping(record.get("roleIntermediates"), "role intermediates")
        transform = sequence(role.get("transformF64"), "terminal transform")
        if len(transform) != 16:
            raise ValueError(f"{geometry} terminal transform size differs")
        nominal = rect(role.get("nominalShapeF64"), "terminal nominal shape")
        terminal_bounds[geometry] = (
            finite(transform[12], "terminal transform x"),
            finite(transform[13], "terminal transform y"),
            nominal[2],
            nominal[3],
        )
    if len(terminal_bounds) != 8:
        raise ValueError("terminal source-bound inventory differs")
    for geometry, source_bounds in measured_bounds.items():
        if f64_hex(source_bounds) != f64_hex(terminal_bounds[geometry]):
            raise ValueError(f"{geometry} live source bound differs from terminal role")

    timelines: dict[str, Sequence[Any]] = {}
    for label in holdout.EXPECTED_ARTIFACTS:
        timeline_path = holdout_root / label / holdout.TIMELINE_FILE_NAME
        timeline = mapping(
            json.loads(timeline_path.read_text(encoding="utf-8")),
            f"{label} timeline",
        )
        timelines[label] = sequence(
            mapping(timeline.get("dynamicBackgroundUniforms"), "dynamic uniforms").get(
                "records"
            ),
            f"{label} records",
        )

    metric = holdout.ExactMetric()
    geometry_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"recordCount": 0, "exactRectangleCount": 0}
    )
    records: list[dict[str, Any]] = []
    for record in holdout_records:
        geometry = str(record.get("geometry"))
        label = str(record.get("label"))
        sample_index = int(record.get("sampleIndex"))
        role = mapping(record.get("roleIntermediates"), "role intermediates")
        transformed = rect(
            role.get("transformedDynamicBoundsF64"), "transformed dynamic bounds"
        )
        entry = (
            transformed[0] - 9.0,
            transformed[1] - 9.0,
            transformed[2] + 18.0,
            transformed[3] + 18.0,
        )
        carrier_values = sequence(role.get("carrierTranslationF64"), "carrier")
        carrier = (
            finite(carrier_values[0], "carrier x"),
            finite(carrier_values[1], "carrier y"),
        )
        source_bounds = terminal_bounds[geometry]
        timeline_record = mapping(timelines[label][sample_index - 1], "timeline record")
        candidate = replay(
            entry,
            carrier,
            source_bounds,
            finite(role.get("shadowOffsetF64"), "shadow offset"),
            filter_radius(timeline_record),
        )
        observed = rect(record.get("observedProducerF64"), "observed producer")
        exact = metric.add(observed, candidate)
        geometry_counts[geometry]["recordCount"] += 1
        geometry_counts[geometry]["exactRectangleCount"] += int(exact)
        records.append(
            {
                "label": label,
                "geometry": geometry,
                "sampleIndex": sample_index,
                "sourceBoundsF64": list(source_bounds),
                "sourceBoundsHex": f64_hex(source_bounds),
                "entryF64": list(entry),
                "entryHex": f64_hex(entry),
                "observedProducerF64": list(observed),
                "observedProducerHex": f64_hex(observed),
                "replayF64": list(candidate),
                "replayHex": f64_hex(candidate),
                "exact": exact,
            }
        )

    metric_result = metric.result()
    if (
        metric_result["rectangleCount"] != 256
        or metric_result["exactRectangleCount"] != 256
        or metric_result["exactComponentCount"] != 1024
    ):
        raise ValueError("exact holdout replay differs")
    return {
        "prepareLayerFilterMapBoundsExactReplayAnalysisSchemaVersion": (
            ANALYSIS_SCHEMA_VERSION
        ),
        "classification": (
            "retrospective exact binary64 replay: executed FilterOp operation "
            "order comes from complete instruction traces, source bounds are "
            "derived uniformly from each geometry's structurally retained "
            "terminal transform and nominal size, two targeted live traces "
            "confirm that relation, and every archived comparison is bitwise "
            "with no tolerance"
        ),
        "inputs": {
            "holdoutResult": str(holdout_result_path),
            "holdoutResultSHA256": HOLDOUT_RESULT_SHA256,
            "holdoutArtifactRoot": str(holdout_root),
            "inventory": str(inventory_path),
        },
        "liveFilterResults": live_results,
        "sourceBoundsPolicy": {
            "rule": (
                "for each geometry, take x/y from terminal sample 32 "
                "transformF64[12:14] and width/height from terminal sample 32 "
                "nominalShapeF64[2:4]"
            ),
            "terminalSampleIndex": 32,
            "cropOrProducerValuesUsed": False,
            "geometryCount": len(terminal_bounds),
            "liveInstructionTraceConfirmationCount": len(measured_bounds),
            "liveInstructionTraceConfirmationsExact": True,
            "geometryBounds": [
                {
                    "geometry": geometry,
                    "sourceBoundsF64": list(source_bounds),
                    "sourceBoundsHex": f64_hex(source_bounds),
                    "confirmedByLiveInstructionTrace": geometry in measured_bounds,
                }
                for geometry, source_bounds in sorted(terminal_bounds.items())
            ],
        },
        "operationOrder": [
            "construct Filter entry from transformed dynamic bounds with signed 9-point SDF expansion",
            "unapply x translation and y-reflecting SimpleTransform",
            "multiply max(2*blur, bleedBlur) by exact -2.8",
            "expand width and height with binary64 fused multiply-add using exact 5.6",
            "union the expanded rectangle with the unexpanded rectangle shifted by [0,8]",
            "construct and shadow-union the source-layer bounds",
            "intersect by endpoint min/max, then subtract origin from far edge",
            "reapply the y-reflecting transform in the executed add/negate order",
        ],
        "holdoutReplay": {
            **metric_result,
            "geometryResults": [
                {"geometry": geometry, **counts}
                for geometry, counts in sorted(geometry_counts.items())
            ],
            "allRectanglesExact": True,
            "allComponentsExact": True,
            "records": records,
        },
        "downstreamBoundary": {
            "holdoutIntegerCropCount": 256,
            "holdoutMismatchedIntegerCropCount": 0,
            "calibrationAndHoldoutIntegerCropCount": 512,
            "calibrationAndHoldoutMismatchedIntegerCropCount": 0,
        },
        "conclusion": {
            "filterMapBoundsOwnerEstablished": True,
            "selectedLiveInstructionReplaysExact": True,
            "archivedHoldoutFloatingReplayExact": True,
            "archivedHoldoutFloatingRectangleCount": 256,
            "archivedHoldoutFloatingComponentCount": 1024,
            "sourceBoundsDerivedWithoutCropOrProducerValues": True,
            "unchangedBlindRepeatPassed": False,
            "generalUnseenGeometryPolicyEstablished": False,
            "materialAppearanceDirectionTransferPassed": False,
            "physicalRetina2xAndColorTransferPassed": False,
            "independentWalleZeroByteFrameParityPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
        "nextExactGate": {
            "target": "unchanged output-blind crop replay over preregistered unseen geometries",
            "requiresNewAppleCapture": True,
            "reason": (
                "the decoder is retrospectively exact over all 256 retained "
                "holdouts and uses one uniform source-bound rule, but that "
                "rule was decoded after inspecting the retained corpus"
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("holdout_result", type=Path)
    parser.add_argument("holdout_root", type=Path)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("filter_1025_root", type=Path)
    parser.add_argument("filter_513_root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = analyze(
        arguments.holdout_result,
        arguments.holdout_root,
        arguments.inventory,
        arguments.filter_1025_root,
        arguments.filter_513_root,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
