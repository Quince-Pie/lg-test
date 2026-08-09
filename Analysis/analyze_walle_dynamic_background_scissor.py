#!/usr/bin/env python3
"""Reconstruct the natural Walle background scissor from public state."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
import math
from pathlib import Path
import struct
from typing import Any

import analyze_transition_geometry_corpus_local_macos_26_6_1 as geometry_model
import analyze_transition_uniform_profile_calibration as transition_profile


type JsonObject = dict[str, Any]
type RectF64 = tuple[float, float, float, float]
type RectI32 = tuple[int, int, int, int]

SAMPLE_INDICES = (1, 4, 8, 12, 16, 20, 24, 28)
SDF_RADIUS = 42.46388244628906
ROI_GAUSSIAN_RADIUS_FACTOR = 1.4
REGULAR_BLEED_RATIO = 0.35
EXPECTED_GEOMETRY = {
    "centerX": 512,
    "centerY": 512,
    "extendsBeyondWindow": False,
    "height": 480,
    "name": "circle-480-center",
    "shape": "circle",
    "width": 480,
    "windowHeight": 1024,
    "windowWidth": 1024,
}


def mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} is not an object")
    return value


def sequence(value: object, name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{name} is not a sequence")
    return value


def finite(value: object, name: str) -> float:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} is not finite")
    return float(value)


def integer(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} is not an integer")
    return value


def f64_bits(value: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", value))[0]


def exact_f64(left: float, right: float) -> bool:
    return f64_bits(left) == f64_bits(right)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def predict_scissor_state(
    geometry: Mapping[str, Any],
    remaining: float,
    *,
    sdf_radius: float = SDF_RADIUS,
    roi_radius_factor: float = ROI_GAUSSIAN_RADIUS_FACTOR,
) -> JsonObject:
    """Replay SDF enclosure, Glass ROI, DOD, and the final intersection."""
    if dict(geometry) != EXPECTED_GEOMETRY:
        raise ValueError("natural Walle geometry differs")
    remaining = geometry_model.float32(remaining)
    layer = geometry_model.expected_dynamic_layer_state(geometry, remaining)
    carrier_position = layer["carrierPosition"]
    element_position = layer["elementPosition"]
    element_extent = layer["elementBounds"][2]
    window_width = integer(geometry.get("windowWidth"), "window width")
    window_height = integer(geometry.get("windowHeight"), "window height")
    diameter = integer(geometry.get("width"), "diameter")

    transform_x = carrier_position[0] + element_position[0]
    transform_y = (
        float(window_height) - carrier_position[1] - element_position[1]
    )
    element_bottom = transform_y - element_extent
    base_low_x = math.floor(transform_x - sdf_radius)
    base_low_y = math.floor(element_bottom - sdf_radius)
    base_high_x = math.ceil((transform_x + element_extent) + sdf_radius)
    base_high_y = math.ceil(transform_y + sdf_radius)
    base_width = base_high_x - base_low_x
    base_height = base_high_y - base_low_y

    # These are QuartzCore Rect::unapply_transform operations for the observed
    # translate-plus-Y-flip transform, not algebraically simplified bounds.
    local_x = float(base_low_x) - transform_x
    local_y = -((float(base_low_y) - transform_y) + float(base_height))
    local_width = float(base_width)
    local_height = float(base_height)

    fields = transition_profile.predict_numeric_fields(
        material="regular",
        appearance="dark",
        diameter=diameter,
        fraction=remaining,
    )
    blur_radius = fields["inputBlurRadius"]
    bleed_blur_radius = fields["inputBleedBlurRadius"]
    roi_radius = roi_radius_factor * max(2.0 * blur_radius, bleed_blur_radius)
    roi_local_x = local_x - roi_radius
    roi_local_y = local_y - roi_radius
    roi_local_width = local_width + 2.0 * roi_radius
    roi_local_height = local_height + 2.0 * roi_radius

    # Preserve Rect::apply_transform's add-height-before-negate ordering.
    roi_world_x = roi_local_x + transform_x
    roi_world_y = -(roi_local_y + roi_local_height) + transform_y
    roi_world_far_x = (roi_local_x + roi_local_width) + transform_x
    roi_world_far_y = roi_world_y + roi_local_height
    roi_low_x = math.floor(roi_world_x)
    roi_low_y = math.floor(roi_world_y)
    roi_high_x = math.ceil(roi_world_far_x)
    roi_high_y = math.ceil(roi_world_far_y)

    terminal_bleed = geometry_model.float32(REGULAR_BLEED_RATIO * diameter)
    dod_extent_f64 = float(diameter) + 2.0 * terminal_bleed
    if not dod_extent_f64.is_integer():
        raise ValueError("filter DOD extent is not integral")
    dod_extent = int(dod_extent_f64)
    dod_low_x = math.floor((carrier_position[0] - terminal_bleed) + 0.5)
    dod_low_y = math.floor((carrier_position[1] - terminal_bleed) + 0.5)
    dod_high_x = dod_low_x + dod_extent
    dod_high_y = dod_low_y + dod_extent

    active_low_x = max(dod_low_x, roi_low_x, 0)
    active_low_y = max(dod_low_y, roi_low_y, 0)
    active_high_x = min(dod_high_x, roi_high_x, window_width)
    active_high_y = min(dod_high_y, roi_high_y, window_height)
    active_width = active_high_x - active_low_x
    active_height = active_high_y - active_low_y
    if active_width <= 0 or active_height <= 0:
        raise ValueError("predicted background scissor is empty")

    return {
        "remaining": remaining,
        "layer": {
            key: list(value) for key, value in layer.items()
        },
        "profile": {
            "inputBlurRadius": blur_radius,
            "inputBleedBlurRadius": bleed_blur_radius,
        },
        "sdf": {
            "radius": sdf_radius,
            "integerBounds": [
                base_low_x,
                base_low_y,
                base_width,
                base_height,
            ],
            "localRect": [local_x, local_y, local_width, local_height],
        },
        "transform": [
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            -1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            transform_x,
            transform_y,
            0.0,
            1.0,
        ],
        "roi": {
            "radiusFactor": roi_radius_factor,
            "radius": roi_radius,
            "localRect": [
                roi_local_x,
                roi_local_y,
                roi_local_width,
                roi_local_height,
            ],
            "integerBounds": [
                roi_low_x,
                roi_low_y,
                roi_high_x - roi_low_x,
                roi_high_y - roi_low_y,
            ],
        },
        "filterDOD": [dod_low_x, dod_low_y, dod_extent, dod_extent],
        "glBottomLeftScissor": [
            active_low_x,
            active_low_y,
            active_width,
            active_height,
        ],
        "metalTopLeftScissor": [
            active_low_x,
            window_height - active_high_y,
            active_width,
            active_height,
        ],
    }


def observed_background_scissor(record: Mapping[str, Any]) -> RectI32:
    render = mapping(record.get("render"), "dynamic render")
    probe = mapping(render.get("metalUniformProbe"), "Metal uniform probe")
    matches = [
        mapping(value, "Metal command")
        for value in sequence(probe.get("records"), "Metal commands")
        if isinstance(value, Mapping)
        and value.get("kind") == "scissorRect"
        and str(
            mapping(value.get("pipeline"), "scissor pipeline")
            .get("creationDescriptor", {})
            .get("fragmentFunction", "")
        ).startswith("glass_background")
    ]
    if len(matches) != 1:
        raise ValueError("expected exactly one background scissor")
    return tuple(
        integer(matches[0].get(name), f"scissor {name}")
        for name in ("x", "y", "width", "height")
    )


def observed_public_state(record: Mapping[str, Any]) -> JsonObject:
    render = mapping(record.get("render"), "dynamic render")
    boundary = mapping(
        render.get("liveRenderBoundaryAfter"), "live render boundary"
    )
    states = [
        mapping(value, "live layer state")
        for value in sequence(boundary.get("layerStates"), "live layer states")
    ]
    carrier = [state for state in states if state.get("path") == [1]]
    element = [state for state in states if state.get("class") == "CASDFElementLayer"]
    if len(carrier) != 1 or len(element) != 1:
        raise ValueError("natural carrier/element state is not unique")
    inputs = mapping(
        mapping(record.get("filter"), "background filter").get("inputValues"),
        "background inputs",
    )
    return {
        "carrierBounds": list(sequence(carrier[0].get("bounds"), "carrier bounds")),
        "carrierPosition": list(
            sequence(carrier[0].get("position"), "carrier position")
        ),
        "elementBounds": list(sequence(element[0].get("bounds"), "element bounds")),
        "elementPosition": list(
            sequence(element[0].get("position"), "element position")
        ),
        "inputBlurRadius": finite(inputs.get("inputBlurRadius"), "blur radius"),
        "inputBleedBlurRadius": finite(
            inputs.get("inputBleedBlurRadius"), "bleed blur radius"
        ),
    }


def trace_records(path: Path) -> list[Mapping[str, Any]]:
    root = mapping(json.loads(path.read_text(encoding="utf-8")), "ROI trace")
    records = [
        mapping(value, "ROI record")
        for value in sequence(root.get("records"), "ROI records")
    ]
    if len(records) != len(SAMPLE_INDICES):
        raise ValueError("ROI trace record count differs")
    return records


def compare_f64_vectors(
    actual: Sequence[Any], expected: Sequence[float], name: str
) -> tuple[int, int]:
    if len(actual) != len(expected):
        raise ValueError(f"{name} component count differs")
    mismatches = sum(
        not exact_f64(finite(left, name), right)
        for left, right in zip(actual, expected, strict=True)
    )
    return len(expected), mismatches


def analyze(
    timeline_path: Path,
    roi_trace_path: Path | None = None,
    calibration_result_path: Path | None = None,
) -> JsonObject:
    timeline = mapping(
        json.loads(timeline_path.read_text(encoding="utf-8")), "timeline"
    )
    if (
        timeline.get("schemaVersion") != 5
        or timeline.get("material") != "regular"
        or timeline.get("appearance") != "dark"
        or timeline.get("direction") != "dematerialize"
        or timeline.get("geometry") != EXPECTED_GEOMETRY
        or timeline.get("windowBackingScaleFactor") != 2
        or timeline.get("failedSamples") != 0
    ):
        raise ValueError("natural Walle timeline guard differs")
    dynamic = mapping(
        timeline.get("dynamicBackgroundUniforms"), "dynamic background uniforms"
    )
    if (
        dynamic.get("schemaVersion") != 9
        or dynamic.get("evidenceMode") != "controlled-replay-v1"
        or dynamic.get("executed") is not True
        or dynamic.get("executedSampleCount") != len(SAMPLE_INDICES)
        or dynamic.get("sampleCount") != len(SAMPLE_INDICES)
        or dynamic.get("sampleIndices") != list(SAMPLE_INDICES)
        or dynamic.get("requested") is not True
        or dynamic.get("freshStaticCarrier") is not True
        or dynamic.get("transitionForegroundFilterCaptured") is not True
        or dynamic.get("transitionForegroundFilterReplayedOnCarrier") is not False
    ):
        raise ValueError("natural Walle dynamic evidence guard differs")
    records = [
        mapping(value, "dynamic record")
        for value in sequence(dynamic.get("records"), "dynamic records")
    ]
    if [record.get("sampleIndex") for record in records] != list(SAMPLE_INDICES):
        raise ValueError("natural Walle sample inventory differs")
    traces = None if roi_trace_path is None else trace_records(roi_trace_path)

    metrics = {
        "publicLayerF64": [0, 0],
        "publicProfileF64": [0, 0],
        "scissorI32": [0, 0],
        "traceSDFBoundsI32": [0, 0],
        "traceTransformF64": [0, 0],
        "traceInputRectF64": [0, 0],
        "traceOutputRectF64": [0, 0],
    }
    cases: list[JsonObject] = []
    for ordinal, record in enumerate(records):
        sample_index = integer(record.get("sampleIndex"), "sample index")
        remaining = finite(record.get("remaining"), "remaining")
        if remaining != geometry_model.float32(remaining):
            raise ValueError("remaining is not binary32")
        prediction = predict_scissor_state(EXPECTED_GEOMETRY, remaining)
        observed_public = observed_public_state(record)

        for key in (
            "carrierBounds",
            "carrierPosition",
            "elementBounds",
            "elementPosition",
        ):
            count, mismatches = compare_f64_vectors(
                observed_public[key], prediction["layer"][key], key
            )
            metrics["publicLayerF64"][0] += count
            metrics["publicLayerF64"][1] += mismatches
        count, mismatches = compare_f64_vectors(
            [
                observed_public["inputBlurRadius"],
                observed_public["inputBleedBlurRadius"],
            ],
            [
                prediction["profile"]["inputBlurRadius"],
                prediction["profile"]["inputBleedBlurRadius"],
            ],
            "public profile",
        )
        metrics["publicProfileF64"][0] += count
        metrics["publicProfileF64"][1] += mismatches

        observed_scissor = observed_background_scissor(record)
        predicted_scissor = tuple(prediction["metalTopLeftScissor"])
        metrics["scissorI32"][0] += 4
        metrics["scissorI32"][1] += sum(
            left != right
            for left, right in zip(observed_scissor, predicted_scissor, strict=True)
        )

        if traces is not None:
            trace = traces[ordinal]
            observed_bounds = tuple(
                integer(value, "trace SDF bound")
                for value in sequence(
                    trace.get("integerLayerBounds"), "trace SDF bounds"
                )
            )
            predicted_bounds = tuple(prediction["sdf"]["integerBounds"])
            metrics["traceSDFBoundsI32"][0] += 4
            metrics["traceSDFBoundsI32"][1] += sum(
                left != right
                for left, right in zip(
                    observed_bounds, predicted_bounds, strict=True
                )
            )
            for metric, observed_key, predicted_value in (
                ("traceTransformF64", "transform", prediction["transform"]),
                ("traceInputRectF64", "inputRect", prediction["sdf"]["localRect"]),
                ("traceOutputRectF64", "outputRect", prediction["roi"]["localRect"]),
            ):
                count, mismatches = compare_f64_vectors(
                    sequence(trace.get(observed_key), observed_key),
                    predicted_value,
                    observed_key,
                )
                metrics[metric][0] += count
                metrics[metric][1] += mismatches

        cases.append(
            {
                "sampleIndex": sample_index,
                "remaining": remaining,
                "sdfIntegerBounds": prediction["sdf"]["integerBounds"],
                "roiRadius": prediction["roi"]["radius"],
                "roiIntegerBounds": prediction["roi"]["integerBounds"],
                "filterDOD": prediction["filterDOD"],
                "observedMetalScissor": list(observed_scissor),
                "predictedMetalScissor": list(predicted_scissor),
            }
        )

    metric_objects = {
        key: {"componentCount": value[0], "mismatchCount": value[1]}
        for key, value in metrics.items()
    }
    exact = all(value[1] == 0 for value in metrics.values())
    novelty = None
    if calibration_result_path is not None:
        calibration = mapping(
            json.loads(calibration_result_path.read_text(encoding="utf-8")),
            "calibration result",
        )
        calibration_inputs = mapping(
            calibration.get("inputs"), "calibration inputs"
        )
        calibration_cases = [
            mapping(value, "calibration case")
            for value in sequence(calibration.get("cases"), "calibration cases")
        ]
        if (
            calibration.get("classification")
            != "retrospective executing-ROI calibration"
            or calibration.get("exact") is not True
            or len(calibration_cases) != len(cases)
            or calibration_inputs.get("timelineSHA256")
            == sha256_file(timeline_path)
        ):
            raise ValueError("holdout calibration-separation guard differs")
        differing_remaining_words = sum(
            geometry_model.float32_bits(finite(left["remaining"], "holdout remaining"))
            != geometry_model.float32_bits(
                finite(right.get("remaining"), "calibration remaining")
            )
            for left, right in zip(cases, calibration_cases, strict=True)
        )
        if differing_remaining_words != len(cases):
            raise ValueError("holdout remaining stream is not fully unseen")
        novelty = {
            "calibrationResult": str(calibration_result_path),
            "calibrationResultSHA256": sha256_file(calibration_result_path),
            "timelineSHA256Differs": True,
            "differingRemainingBinary32Words": differing_remaining_words,
            "requiredDifferingRemainingBinary32Words": len(cases),
        }
    return {
        "schemaVersion": 1,
        "classification": (
            "retrospective executing-ROI calibration"
            if traces is not None
            else "prospective public-state scissor transfer"
        ),
        "inputs": {
            "timeline": str(timeline_path),
            "timelineSHA256": sha256_file(timeline_path),
            "roiTrace": None if roi_trace_path is None else str(roi_trace_path),
            "roiTraceSHA256": (
                None if roi_trace_path is None else sha256_file(roi_trace_path)
            ),
        },
        "model": {
            "sdfRadiusF32": SDF_RADIUS,
            "sdfRadiusF32Hex": struct.pack("<f", SDF_RADIUS).hex(),
            "roiRadius": "1.4 * max(2 * inputBlurRadius, inputBleedBlurRadius)",
            "filterDOD": (
                "integral translated [-binary32(0.35*D), "
                "-binary32(0.35*D), D+2e, D+2e]"
            ),
            "final": "viewport intersection of integral ROI and filter DOD",
        },
        "metrics": metric_objects,
        "novelty": novelty,
        "cases": cases,
        "exact": exact,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--roi-trace", type=Path)
    parser.add_argument("--calibration-result", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = analyze(
        arguments.timeline,
        arguments.roi_trace,
        arguments.calibration_result,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not result["exact"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
