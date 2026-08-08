#!/usr/bin/env python3
"""Close off-center circle element staging in the opened geometry holdout."""

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
import json
import math
from pathlib import Path
from typing import Any

import analyze_combined_transition_geometry_holdout_falsification as opened
import analyze_transition_geometry_corpus_local_macos_26_6_1 as model


type JsonObject = dict[str, Any]

RESULT_SCHEMA_VERSION = 1
TARGET_LAYER_PATH = (1, 0, 1, 0, 0, 0, 0)

LOCAL_DIAGNOSTIC_EVIDENCE = {
    "cgrectConvertDisassemblySHA256": (
        "37c2b6dcf9d7870bc6d4900fa63d627c6bd12b4ba3982aef24db19ecae24d77d"
    ),
    "cgrectCornerReductionDisassemblySHA256": (
        "d7ab32898412f348c3311780c89cf114506664bec210d3fd464729bee27814eb"
    ),
    "shapePathDisassemblySHA256": (
        "b96023e18feff913b1f99c245e9f395bcf37222f2c257457180e6a35904f9018"
    ),
    "pathSetCalleeTraceSHA256": (
        "4a0efa90a5d266dfca42f73fa9d3a0e461e72f7d7697998a8962f516cf7a1780"
    ),
    "shapeSetStagingTraceSHA256": (
        "859563abb56062a7f723b26fbd8944d58a89ec7f7e2ec26b31e851db3546f44d"
    ),
    "sdfShapeGeometryTraceSHA256": (
        "8562fb84e94211c036d6adaf56e9fa5e6b056fe53ff670a6944a10fc21173795"
    ),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def affine_about_center(value: float, scale: float, half: float) -> float:
    translation = half + (-half * scale)
    return math.fma(scale, value, 0.0) + translation


def shape_set_axis(
    *,
    diameter: float,
    remaining: float,
    requested_center: float,
    window_extent: float,
) -> tuple[float, float]:
    """Replay ViewTransform and the two CGRect corner reductions in order."""
    half = diameter / 2.0
    progress = model.float32(1.0 - remaining)
    scale_limit = min((diameter + 16.0) / diameter, 1.2)
    transition_scale = 1.0 + progress * (scale_limit - 1.0)

    lower = affine_about_center(0.0, transition_scale, half)
    upper = affine_about_center(diameter, transition_scale, half)
    square_root = math.sqrt(scale_limit)
    for scale in (1.0 / square_root, square_root):
        lower = affine_about_center(lower, scale, half)
        upper = affine_about_center(upper, scale, half)

    carrier_extent = diameter * remaining
    carrier_position = window_extent / 2.0 - carrier_extent / 2.0
    snapped_extent = math.floor(carrier_extent + 0.5)
    adjustment = (snapped_extent - carrier_extent) / 2.0
    root_translation = opened.retina_snap(requested_center) - half + adjustment

    root_lower = lower + root_translation
    root_upper = upper + root_translation
    root_extent = root_upper - root_lower

    local_lower = root_lower - carrier_position
    local_upper = (root_lower + root_extent) - carrier_position
    return local_lower, local_upper - local_lower


def transformed_circle_rectangle(
    rectangle: Sequence[float],
) -> tuple[float, float, float, float]:
    """Replay Circle fitting followed by OffsetShape Path translation."""
    require(len(rectangle) == 4, "circle rectangle component count differs")
    x, y, width, height = rectangle
    diameter = min(width, height)
    inset_x = (width - diameter) * 0.5
    inset_y = (height - diameter) * 0.5

    lower_x = inset_x + x
    lower_y = inset_y + y
    upper_x = (inset_x + diameter) + x
    upper_y = (inset_y + diameter) + y
    return lower_x, lower_y, upper_x - lower_x, upper_y - lower_y


def expected_element(
    geometry: Mapping[str, Any], remaining: float
) -> tuple[float, float, float, float]:
    if remaining == 1.0:
        endpoint = opened.retrospective_layer_candidate(geometry, remaining)
        position = endpoint["elementPosition"]
        bounds = endpoint["elementBounds"]
        return position[0], position[1], bounds[2], bounds[3]

    width = model.finite(geometry.get("width"), "geometry width")
    height = model.finite(geometry.get("height"), "geometry height")
    require(width == height, "off-center staging closure is circle-only")
    require(geometry.get("shape") == "circle", "geometry is not a circle")
    x, staged_width = shape_set_axis(
        diameter=width,
        remaining=remaining,
        requested_center=model.finite(geometry.get("centerX"), "center x"),
        window_extent=model.finite(geometry.get("windowWidth"), "window width"),
    )
    y, staged_height = shape_set_axis(
        diameter=height,
        remaining=remaining,
        requested_center=model.finite(geometry.get("centerY"), "center y"),
        window_extent=model.finite(geometry.get("windowHeight"), "window height"),
    )
    return transformed_circle_rectangle((x, y, staged_width, staged_height))


def background_family(record: Mapping[str, Any], material: str) -> str:
    labels = opened.pipeline_tokens(record)
    if opened.CURRENT_CLEAR_BACKGROUND in labels:
        return "current-clear"
    if opened.CURRENT_REGULAR_BACKGROUND in labels:
        return "current-regular"
    if opened.SMALL_CLEAR_BACKGROUND in labels:
        return "small-clear"
    require(material == "clear", "regular state has no admitted background")
    return "clear-without-primary"


def mismatch_count(
    observed: Sequence[float], predicted: Sequence[float], *, binary32: bool
) -> int:
    require(len(observed) == len(predicted), "metric component count differs")
    if binary32:
        return sum(
            model.float32_bits(model.float32(left))
            != model.float32_bits(model.float32(right))
            for left, right in zip(observed, predicted, strict=True)
        )
    return sum(
        model.float64_bits(left) != model.float64_bits(right)
        for left, right in zip(observed, predicted, strict=True)
    )


def metric(counter: Counter[str]) -> JsonObject:
    return {
        "componentCount": counter["componentCount"],
        "mismatchedComponents": counter["mismatchedComponents"],
        "exact": (
            counter["componentCount"] > 0 and counter["mismatchedComponents"] == 0
        ),
    }


def analyze(capture_root: Path, preregistration: Path) -> JsonObject:
    require(
        opened.sha256_file(preregistration) == opened.PREREGISTRATION_SHA256,
        "preregistration SHA-256 differs",
    )
    opened.validate_capture_transport(capture_root)

    binary64 = Counter()
    binary32 = Counter()
    positions = Counter()
    extents = Counter()
    live = Counter()
    endpoints = Counter()
    family_metrics: dict[str, Counter[str]] = {}
    case_results = []

    for case_id, expected_sha256 in sorted(opened.TIMELINE_SHA256.items()):
        path = capture_root / case_id / "transition-timeline.json"
        observed_sha256 = opened.sha256_file(path)
        require(observed_sha256 == expected_sha256, f"{case_id} SHA-256 differs")
        timeline = opened.load_object(path, f"{case_id} timeline")
        expected_case = opened.expected_case(case_id)
        records = model.validate_envelope(timeline, expected_case)
        geometry = model.mapping(timeline.get("geometry"), "geometry")
        case_metric = Counter()

        for record in records:
            remaining = model.finite(record.get("remaining"), "remaining")
            states = model.layer_states(record)
            require(TARGET_LAYER_PATH in states, "target SDF element is absent")
            layer = states[TARGET_LAYER_PATH]
            position = model.vector(layer.get("position"), "element position", 2)
            bounds = model.vector(layer.get("bounds"), "element bounds", 4)
            observed = (*position, *bounds[2:])
            predicted = expected_element(geometry, remaining)

            mismatch64 = mismatch_count(observed, predicted, binary32=False)
            mismatch32 = mismatch_count(observed, predicted, binary32=True)
            binary64["componentCount"] += 4
            binary64["mismatchedComponents"] += mismatch64
            binary32["componentCount"] += 4
            binary32["mismatchedComponents"] += mismatch32
            positions["componentCount"] += 2
            positions["mismatchedComponents"] += mismatch_count(
                observed[:2], predicted[:2], binary32=False
            )
            extents["componentCount"] += 2
            extents["mismatchedComponents"] += mismatch_count(
                observed[2:], predicted[2:], binary32=False
            )

            domain = endpoints if remaining == 1.0 else live
            domain["stateCount"] += 1
            domain["componentCount"] += 4
            domain["mismatchedComponents"] += mismatch64
            family = background_family(record, str(expected_case["material"]))
            family_counter = family_metrics.setdefault(family, Counter())
            family_counter["stateCount"] += 1
            family_counter["componentCount"] += 4
            family_counter["mismatchedComponents"] += mismatch64
            case_metric["stateCount"] += 1
            case_metric["componentCount"] += 4
            case_metric["mismatchedComponents"] += mismatch64

        case_results.append(
            {
                "caseId": case_id,
                "timelineSHA256": observed_sha256,
                **case_metric,
                "exact": case_metric["mismatchedComponents"] == 0,
            }
        )

    require(binary64 == Counter(componentCount=1008), "binary64 closure differs")
    require(binary32 == Counter(componentCount=1008), "binary32 closure differs")
    require(live == Counter(stateCount=248, componentCount=992), "live closure differs")
    require(
        endpoints == Counter(stateCount=4, componentCount=16),
        "endpoint closure differs",
    )
    require(
        {name: counter["stateCount"] for name, counter in family_metrics.items()}
        == {
            "current-clear": 37,
            "current-regular": 126,
            "small-clear": 60,
            "clear-without-primary": 29,
        },
        "family inventory differs",
    )

    return {
        "offcenterCircleElementStagingSchemaVersion": RESULT_SCHEMA_VERSION,
        "classification": (
            "retrospective exact closure of one boundary in an immutable "
            "prospectively falsified corpus"
        ),
        "status": "exact-retrospective-closure",
        "captureCommit": opened.CAPTURE_COMMIT,
        "captureBinarySHA256": opened.CAPTURE_BINARY_SHA256,
        "preregistrationSHA256": opened.PREREGISTRATION_SHA256,
        "timelineCount": len(opened.TIMELINE_SHA256),
        "stateCount": live["stateCount"] + endpoints["stateCount"],
        "liveStateCount": live["stateCount"],
        "endpointStateCount": endpoints["stateCount"],
        "cases": case_results,
        "metrics": {
            "elementBinary64": metric(binary64),
            "elementBinary32": metric(binary32),
            "positionBinary64": metric(positions),
            "extentBinary64": metric(extents),
            "liveElementBinary64": metric(live),
            "endpointElementBinary64": metric(endpoints),
        },
        "familyMetrics": {
            name: {"stateCount": counter["stateCount"], **metric(counter)}
            for name, counter in sorted(family_metrics.items())
        },
        "operationOrder": [
            "apply the transition scale and compensating scales about the shape center",
            "translate into the snapped requested-center root coordinate",
            "reduce transformed corners to a CGRect",
            "translate that CGRect by the local carrier position and reduce corners again",
            "inscribe Circle with half the per-axis excess",
            "translate both square corners through OffsetShape Path.applying",
            "subtract translated lower corners from translated upper corners",
        ],
        "diagnosticEvidence": LOCAL_DIAGNOSTIC_EVIDENCE,
        "closedAlgorithmBoundary": (
            "exact binary64 off-center circle element extent and position staging"
        ),
        "remainingAlgorithmBoundaries": [
            "window clipping and alternate 24-vertex/96-index topology construction",
            "small-clear Tghn/Tmua/Tkfh/A2Xghfc construction and pixels",
        ],
        "walleIntegrationMayBeginBehindGates": True,
        "productionParityAuthorized": False,
        "productionShaderChanged": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-root", required=True, type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = analyze(arguments.capture_root, arguments.preregistration)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
