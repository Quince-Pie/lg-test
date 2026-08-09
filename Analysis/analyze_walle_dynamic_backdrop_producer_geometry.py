#!/usr/bin/env python3
"""Join Apple's public crop policy to the dynamic backdrop producer mesh.

The crop trace and Metal mesh are terminal oracles.  The prediction uses only
the public transition state, the already-opened finite-enclosure rule, and the
already-validated background ROI constructor.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
from typing import Any

import analyze_prepare_layer_crop_union_operand_matrix as crop_policy
import analyze_transition_geometry_corpus_local_macos_26_6_1 as geometry_model
import analyze_walle_dynamic_background_scissor as scissor_model
import validate_dynamic_allocation_holdout as allocation
import validate_dynamic_allocation_surviving_path_threshold as capture_backdrop
import validate_prepare_layer_crop_transfer as crop_transfer


type JsonObject = dict[str, Any]
type RectF64 = tuple[float, float, float, float]
type RectI32 = tuple[int, int, int, int]

SCHEMA_VERSION = 1
SAMPLE_INDICES = (1, 4, 8, 12, 16, 20, 24, 28)
PRODUCER_FRAGMENTS = frozenset({"downsample_4_frag_lph", "TimgA2Xhfc_Isrc"})
RAW_RENDER_KEYS = ("output", "exactPassReplay", "dynamicBackdropProducerBoundary")


def mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} is not an object")
    return value


def sequence(value: object, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ValueError(f"{label} is not an array")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def f32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def f32_from_bits(value: int) -> float:
    return struct.unpack("<f", struct.pack("<I", value))[0]


def rect_union(left: Sequence[float], right: Sequence[float]) -> RectF64:
    if len(left) != 4 or len(right) != 4:
        raise ValueError("rectangle component count differs")
    lower_x = min(float(left[0]), float(right[0]))
    lower_y = min(float(left[1]), float(right[1]))
    far_x = max(float(left[0] + left[2]), float(right[0] + right[2]))
    far_y = max(float(left[1] + left[3]), float(right[1] + right[3]))
    return (lower_x, lower_y, far_x - lower_x, far_y - lower_y)


def rect_intersection(left: Sequence[float], right: Sequence[float]) -> RectF64:
    if len(left) != 4 or len(right) != 4:
        raise ValueError("rectangle component count differs")
    lower_x = max(float(left[0]), float(right[0]))
    lower_y = max(float(left[1]), float(right[1]))
    far_x = min(float(left[0] + left[2]), float(right[0] + right[2]))
    far_y = min(float(left[1] + left[3]), float(right[1] + right[3]))
    if far_x <= lower_x or far_y <= lower_y:
        raise ValueError("public producer rectangles do not intersect")
    return (lower_x, lower_y, far_x - lower_x, far_y - lower_y)


def predict_producer_guard(geometry: Mapping[str, Any], remaining: float) -> JsonObject:
    """Construct the exact integer guard consumed by capture_backdrop."""

    state = scissor_model.predict_scissor_state(geometry, remaining)
    layer = mapping(state.get("layer"), "predicted layer")
    carrier = sequence(layer.get("carrierPosition"), "carrier position")
    roi = mapping(state.get("roi"), "predicted ROI")
    local = sequence(roi.get("localRect"), "local ROI")
    transform = sequence(state.get("transform"), "ROI transform")
    if len(carrier) != 2 or len(local) != 4 or len(transform) != 16:
        raise ValueError("public producer state component count differs")

    window_width = int(geometry["windowWidth"])
    window_height = int(geometry["windowHeight"])
    diameter = int(geometry["width"])
    margin = geometry_model.float32(0.35 * diameter)
    roi_world = (
        float(local[0] + transform[12]),
        float(-(local[1] + local[3]) + transform[13]),
        float(local[2]),
        float(local[3]),
    )
    filter_dod = (
        float(carrier[0] - margin),
        float(window_height - carrier[1] - diameter - margin),
        float(diameter + 2.0 * margin),
        float(diameter + 2.0 * margin),
    )
    nested_f64 = rect_intersection(filter_dod, roi_world)
    nested_i32 = crop_policy.integer_crop(nested_f64)
    aggregate_f64 = rect_union(filter_dod, nested_i32)
    working_i32 = crop_policy.integer_crop(aggregate_f64)
    visible_i32 = crop_policy.intersect_i32(
        working_i32, (0, 0, window_width, window_height)
    )
    if visible_i32[2] <= 0 or visible_i32[3] <= 0:
        raise ValueError("public producer guard is empty")

    scale = geometry_model.expected_backdrop_scale("regular", float(remaining))
    position_bits = capture_backdrop.capture_backdrop_primary_position_bits(
        rect=visible_i32,
        scale=scale,
    )
    source_bits = [
        f32_bits(geometry_model.float32(float(f32_from_bits(value)) / scale))
        for value in position_bits
    ]
    return {
        "remainingF32": geometry_model.float32(float(remaining)),
        "backdropScaleF32": scale,
        "roiF64": list(roi_world),
        "filterDODF64": list(filter_dod),
        "nestedF64": list(nested_f64),
        "nestedI32": list(nested_i32),
        "aggregateF64": list(aggregate_f64),
        "workingI32": list(working_i32),
        "visibleI32": list(visible_i32),
        "primaryPositionF32Bits": position_bits,
        "primarySourceF32Bits": source_bits,
    }


def decoded_crop_records(path: Path) -> list[JsonObject]:
    trace = mapping(json.loads(path.read_text(encoding="utf-8")), "crop trace")
    records = sequence(trace.get("qualifiedRecords"), "qualified crop records")
    if len(records) != len(SAMPLE_INDICES):
        raise ValueError("qualified crop record count differs")
    result: list[JsonObject] = []
    for ordinal, raw in enumerate(records, start=1):
        record = mapping(raw, "qualified crop record")
        role = mapping(record.get("roleState"), "crop role state")
        raw_hex = role.get("hex")
        if not isinstance(raw_hex, str):
            raise ValueError("crop role payload is missing")
        payload = bytes.fromhex(raw_hex)
        if (
            role.get("byteCount") != len(payload)
            or role.get("sha256") != hashlib.sha256(payload).hexdigest()
            or record.get("recordIndex") != ordinal - 1
            or record.get("normalRenderOrdinal") != ordinal
        ):
            raise ValueError("crop role record integrity differs")
        result.append(crop_transfer.decode_role(payload))
    return result


@contextmanager
def producer_metadata_adapter() -> Iterator[None]:
    original_fragments = allocation.PRODUCER_FRAGMENTS
    original_raw_gate = allocation.no_raw_stage_dumps
    allocation.PRODUCER_FRAGMENTS = PRODUCER_FRAGMENTS
    allocation.no_raw_stage_dumps = lambda _render: True
    try:
        yield
    finally:
        allocation.PRODUCER_FRAGMENTS = original_fragments
        allocation.no_raw_stage_dumps = original_raw_gate


def timeline_records(path: Path) -> tuple[Mapping[str, Any], list[Mapping[str, Any]]]:
    timeline = mapping(json.loads(path.read_text(encoding="utf-8")), "timeline")
    geometry = mapping(timeline.get("geometry"), "timeline geometry")
    dynamic = mapping(timeline.get("dynamicBackgroundUniforms"), "dynamic records")
    records = [
        mapping(value, "dynamic record")
        for value in sequence(dynamic.get("records"), "dynamic record array")
    ]
    if (
        timeline.get("material") != "regular"
        or timeline.get("appearance") != "dark"
        or timeline.get("direction") != "dematerialize"
        or dict(geometry) != scissor_model.EXPECTED_GEOMETRY
        or [record.get("sampleIndex") for record in records] != list(SAMPLE_INDICES)
    ):
        raise ValueError("producer timeline identity differs")
    return timeline, records


def observed_backdrop_scale(record: Mapping[str, Any]) -> float:
    captured = record.get("capturedLayerStates")
    if captured is not None:
        value, _ = allocation.captured_scale(record)
        return value

    render = mapping(record.get("render"), "dynamic render")
    boundary = mapping(
        render.get("liveRenderBoundaryBefore"), "live render boundary before"
    )
    matches = [
        mapping(value, "live layer state")
        for value in sequence(boundary.get("layerStates"), "live layer states")
        if isinstance(value, Mapping) and value.get("class") == "CABackdropLayer"
    ]
    if len(matches) != 1:
        raise ValueError("live CABackdropLayer state is not unique")
    return float(matches[0]["backdropScale"])


def analyze_timeline(
    path: Path,
    *,
    crop_records: Sequence[Mapping[str, Any]] | None,
) -> tuple[list[JsonObject], Counter[str], dict[str, int]]:
    timeline, records = timeline_records(path)
    geometry = mapping(timeline.get("geometry"), "timeline geometry")
    if crop_records is not None and len(crop_records) != len(records):
        raise ValueError("crop and timeline record counts differ")

    metrics = {
        "visibleCropI32Components": 0,
        "visibleCropI32Mismatches": 0,
        "workingCropI32Components": 0,
        "workingCropI32Mismatches": 0,
        "primaryPositionF32Components": 0,
        "primaryPositionF32Mismatches": 0,
        "primarySourceF32Components": 0,
        "primarySourceF32Mismatches": 0,
    }
    fragments: Counter[str] = Counter()
    cases: list[JsonObject] = []
    with producer_metadata_adapter():
        for ordinal, raw_record in enumerate(records):
            record = deepcopy(raw_record)
            render = mapping(record.get("render"), "dynamic render")
            for key in RAW_RENDER_KEYS:
                render.pop(key, None)  # type: ignore[attr-defined]

            remaining = float(record["remaining"])
            predicted = predict_producer_guard(geometry, remaining)
            scale = float(predicted["backdropScaleF32"])
            observed_scale = observed_backdrop_scale(record)
            if f32_bits(observed_scale) != f32_bits(scale):
                raise ValueError("captured and public backdrop scales differ")
            policy = allocation.observed_policy(
                record,
                scale=scale,
                require_primary_source_q_exact=False,
            )
            mesh = mapping(policy.get("producerMesh"), "producer mesh")
            fragment = mesh.get("fragmentFunction")
            if fragment not in PRODUCER_FRAGMENTS:
                raise ValueError("producer fragment identity differs")
            fragments[str(fragment)] += 1
            vertices = sequence(mesh.get("primaryVertices"), "primary vertices")
            if len(vertices) != 4:
                raise ValueError("primary producer vertex count differs")
            observed_position_bits = [
                f32_bits(float(component))
                for vertex in vertices
                for component in sequence(vertex, "primary vertex")[:2]
            ]
            observed_source_bits = [
                f32_bits(float(component))
                for vertex in vertices
                for component in sequence(vertex, "primary vertex")[4:6]
            ]
            predicted_position_bits = list(predicted["primaryPositionF32Bits"])
            predicted_source_bits = list(predicted["primarySourceF32Bits"])
            position_mismatches = sum(
                left != right
                for left, right in zip(
                    observed_position_bits, predicted_position_bits, strict=True
                )
            )
            source_mismatches = sum(
                left != right
                for left, right in zip(
                    observed_source_bits, predicted_source_bits, strict=True
                )
            )
            metrics["primaryPositionF32Components"] += len(predicted_position_bits)
            metrics["primaryPositionF32Mismatches"] += position_mismatches
            metrics["primarySourceF32Components"] += len(predicted_source_bits)
            metrics["primarySourceF32Mismatches"] += source_mismatches

            crop_case: JsonObject | None = None
            if crop_records is not None:
                crop = crop_records[ordinal]
                observed_visible = tuple(
                    int(value)
                    for value in sequence(crop.get("visibleCropI32"), "visible crop")
                )
                observed_working = tuple(
                    int(value)
                    for value in sequence(crop.get("workingCropI32"), "working crop")
                )
                predicted_visible = tuple(predicted["visibleI32"])
                predicted_working = tuple(predicted["workingI32"])
                visible_mismatches = sum(
                    left != right
                    for left, right in zip(
                        observed_visible, predicted_visible, strict=True
                    )
                )
                working_mismatches = sum(
                    left != right
                    for left, right in zip(
                        observed_working, predicted_working, strict=True
                    )
                )
                metrics["visibleCropI32Components"] += 4
                metrics["visibleCropI32Mismatches"] += visible_mismatches
                metrics["workingCropI32Components"] += 4
                metrics["workingCropI32Mismatches"] += working_mismatches
                crop_case = {
                    "observedWorkingI32": list(observed_working),
                    "observedVisibleI32": list(observed_visible),
                    "workingI32Mismatches": working_mismatches,
                    "visibleI32Mismatches": visible_mismatches,
                }

            cases.append(
                {
                    "sampleIndex": record["sampleIndex"],
                    "fragmentFunction": fragment,
                    "prediction": predicted,
                    "cropOracle": crop_case,
                    "primaryPositionF32Mismatches": position_mismatches,
                    "primarySourceF32Mismatches": source_mismatches,
                }
            )
    return cases, fragments, metrics


def metric(component_count: int, mismatch_count: int) -> JsonObject:
    return {
        "componentCount": component_count,
        "mismatchCount": mismatch_count,
        "exact": mismatch_count == 0,
    }


def analyze(
    natural_timeline: Path,
    natural_crop_trace: Path,
    controlled_timeline: Path,
) -> JsonObject:
    crops = decoded_crop_records(natural_crop_trace)
    natural_cases, natural_fragments, natural_metrics = analyze_timeline(
        natural_timeline,
        crop_records=crops,
    )
    controlled_cases, controlled_fragments, controlled_metrics = analyze_timeline(
        controlled_timeline,
        crop_records=None,
    )
    metrics = {
        "naturalWorkingCropI32": metric(
            natural_metrics["workingCropI32Components"],
            natural_metrics["workingCropI32Mismatches"],
        ),
        "naturalVisibleCropI32": metric(
            natural_metrics["visibleCropI32Components"],
            natural_metrics["visibleCropI32Mismatches"],
        ),
        "naturalPrimaryPositionF32": metric(
            natural_metrics["primaryPositionF32Components"],
            natural_metrics["primaryPositionF32Mismatches"],
        ),
        "naturalPrimarySourceF32": metric(
            natural_metrics["primarySourceF32Components"],
            natural_metrics["primarySourceF32Mismatches"],
        ),
        "controlledPrimaryPositionF32": metric(
            controlled_metrics["primaryPositionF32Components"],
            controlled_metrics["primaryPositionF32Mismatches"],
        ),
        "controlledPrimarySourceF32": metric(
            controlled_metrics["primarySourceF32Components"],
            controlled_metrics["primarySourceF32Mismatches"],
        ),
    }
    exact = all(value["exact"] for value in metrics.values())
    if not exact:
        raise ValueError("public producer geometry differs from Apple")
    return {
        "walleDynamicBackdropProducerGeometrySchemaVersion": SCHEMA_VERSION,
        "classification": (
            "retrospective exact public-state producer-crop and primary-mesh "
            "calibration across two distinct Retina timing streams"
        ),
        "inputs": {
            "naturalTimeline": str(natural_timeline),
            "naturalTimelineSHA256": sha256_file(natural_timeline),
            "naturalCropTrace": str(natural_crop_trace),
            "naturalCropTraceSHA256": sha256_file(natural_crop_trace),
            "controlledTimeline": str(controlled_timeline),
            "controlledTimelineSHA256": sha256_file(controlled_timeline),
        },
        "model": {
            "nestedRectangle": "intersection(public Glass DOD, public ROI)",
            "nestedCrop": "opened finite enclosure plus fractional one-pixel border",
            "aggregate": "union(public Glass DOD, nested integer crop)",
            "workingCrop": "opened finite enclosure plus fractional one-pixel border",
            "visibleCrop": "working crop intersected with the public viewport",
            "primaryPosition": "floor(scale*lower), ceil(scale*far)",
            "primarySource": "binary32(primary position / binary32 scale)",
            "tolerance": 0,
        },
        "producerFragmentInventory": {
            "natural": dict(sorted(natural_fragments.items())),
            "controlled": dict(sorted(controlled_fragments.items())),
        },
        "metrics": metrics,
        "cases": {
            "natural": natural_cases,
            "controlled": controlled_cases,
        },
        "exact": True,
        "productionParityEstablished": False,
        "remainingBoundary": (
            "port the now-closed crop/mesh and already-measured producer, copy-base, "
            "and mip arithmetic into Walle, then pass nonzero full-frame and physical "
            "Retina presentation gates"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("natural_timeline", type=Path)
    parser.add_argument("natural_crop_trace", type=Path)
    parser.add_argument("controlled_timeline", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = analyze(
        arguments.natural_timeline,
        arguments.natural_crop_trace,
        arguments.controlled_timeline,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
