#!/usr/bin/env python3
"""Validate the prospective Walle current-final topology-selector holdout."""

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Never

import analyze_transition_geometry_corpus_local_macos_26_6_1 as model


REPOSITORY = Path(__file__).resolve().parents[1]
TARGET_LAYER_PATH = (1, 0, 1, 0, 0, 0, 0)
SAMPLE_INDEX = 28
OPENED_TIMELINE_SHA256 = frozenset(
    {
        "609485e86b185358b0b762bd95143d3a29f3d1049b3a843997f0cf7b05fa9b0a",
        "9343c8d2e2edb3748869c35dac1f0e6c381bd58426d86d4d6f84ae4556eaeade",
    }
)

type JSONObject = dict[str, object]


def fail(message: str) -> Never:
    raise ValueError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def mapping(value: object, label: str) -> Mapping[str, object]:
    require(isinstance(value, Mapping), f"{label} is not an object")
    return value


def sequence(value: object, label: str) -> Sequence[object]:
    require(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes)),
        f"{label} is not an array",
    )
    return value


def load_json(path: Path) -> JSONObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path} is not a JSON object")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_context(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key and key.replace("_", "").isalnum():
            result[key] = value
    return result


def single[T](values: Sequence[T], label: str) -> T:
    require(len(values) == 1, f"expected one {label}, found {len(values)}")
    return values[0]


def numeric(value: object, label: str) -> float:
    require(
        isinstance(value, int | float) and not isinstance(value, bool),
        f"{label} is not numeric",
    )
    return float(value)


def topology_terms(width: float, height: float) -> tuple[float, float, float, float]:
    half_x = model.float32(width / 2.0)
    half_y = model.float32(height / 2.0)
    radius_x = model.float32(model.float32(half_x + 9.0) - 9.0)
    radius_y = model.float32(model.float32(half_y + 9.0) - 9.0)
    return half_x, half_y, radius_x, radius_y


def predicts_border(
    half_x: float,
    half_y: float,
    radius_x: float,
    radius_y: float,
) -> bool:
    return radius_x > half_x or radius_y > half_y or radius_x != radius_y


def validate_sources(preregistration: Mapping[str, object]) -> None:
    sources = mapping(preregistration.get("sourceSHA256"), "sourceSHA256")
    for relative, expected in sources.items():
        require(
            isinstance(relative, str) and isinstance(expected, str),
            "source hash entry is malformed",
        )
        source = REPOSITORY / relative
        require(source.is_file(), f"pinned source is absent: {relative}")
        require(sha256_file(source) == expected, f"pinned source differs: {relative}")


def validate_preflight(preflight: Mapping[str, object]) -> None:
    required = {
        "localRetinaCaptureSessionPreflightSchemaVersion": 2,
        "passed": True,
        "displayActive": True,
        "displayAsleep": False,
        "sessionLocked": False,
        "sessionLoginDone": True,
        "sessionOnConsole": True,
        "backingScaleFactor": 2,
        "expectedBackingScaleFactor": 2,
    }
    for field, expected in required.items():
        require(preflight.get(field) == expected, f"preflight {field} differs")
    require(
        preflight.get("physicalPixels") == [3456, 2234],
        "physical Retina dimensions differ",
    )
    require(
        preflight.get("logicalPoints") == [1728, 1117],
        "logical Retina dimensions differ",
    )


def validate_context(
    context: Mapping[str, str],
    *,
    expected_capture_commit: str,
    preregistration_sha256: str,
) -> None:
    required = {
        "CAPTURE_COMMIT": expected_capture_commit,
        "GITHUB_ACTIONS_USED": "0",
        "NATIVE_CAPTURE_DEBUGGER_USED": "0",
        "NIX_STORE_PATH_IN_NATIVE_BUILD_OR_CAPTURE": "0",
        "MACOS_PRODUCT_VERSION": "26.6.1",
        "MACOS_BUILD_VERSION": "25G76",
        "ARCHITECTURE": "arm64",
        "NATIVE_SDK_VERSION": "26.5",
        "PREREGISTRATION_SHA256": preregistration_sha256,
        "LG_GLASS_MATERIAL": "regular",
        "LG_GLASS_APPEARANCE": "dark",
        "LG_GLASS_GEOMETRY": "circle-480-center",
        "LG_TRANSITION_TIMELINE": "1",
        "LG_TRANSITION_UNIFORMS": "1",
        "LG_TRANSITION_DIRECTION": "dematerialize",
        "LG_TRANSITION_ISCD_BORDER_TRACE": "0",
        "LG_TRANSITION_ISCD_RADIUS_SHRINK_TRACE": "1",
        "LG_TRANSITION_HIGHLIGHT_TRACE": "0",
        "LG_ENABLE_UNSAFE_PRIVATE_INTERPOLANT_TRACE": "0",
    }
    for field, expected in required.items():
        require(context.get(field) == expected, f"capture context {field} differs")


def final_layer_state(record: Mapping[str, object]) -> Mapping[str, object]:
    render = mapping(record.get("render"), "render")
    before = mapping(render.get("liveRenderBoundaryBefore"), "boundary before")
    after = mapping(render.get("liveRenderBoundaryAfter"), "boundary after")
    require(before.get("executed") is True, "boundary before did not execute")
    require(after.get("executed") is True, "boundary after did not execute")
    require(
        before.get("layerStatesSHA256") == after.get("layerStatesSHA256"),
        "live layer state changed during render",
    )
    states = [
        mapping(value, "live layer state")
        for value in sequence(before.get("layerStates"), "live layer states")
    ]
    return single(
        [state for state in states if tuple(state.get("path", ())) == TARGET_LAYER_PATH],
        "target CASDFElementLayer state",
    )


def validate_capture(
    capture_directory: Path,
    preregistration: Mapping[str, object],
    *,
    expected_capture_commit: str,
) -> JSONObject:
    preregistration_path = capture_directory / "preregistration.json"
    preregistration_sha256 = sha256_file(preregistration_path)
    timeline_path = capture_directory / "transition-timeline.json"
    context_path = capture_directory / "capture-context.txt"
    preflight_path = capture_directory / "capture-session-preflight.json"
    timeline_sha256 = sha256_file(timeline_path)
    require(
        timeline_sha256 not in OPENED_TIMELINE_SHA256,
        "timeline is not a fresh prospective capture",
    )
    validate_sources(preregistration)
    validate_preflight(load_json(preflight_path))
    context = read_context(context_path)
    validate_context(
        context,
        expected_capture_commit=expected_capture_commit,
        preregistration_sha256=preregistration_sha256,
    )

    timeline = load_json(timeline_path)
    expected_timeline = {
        "schemaVersion": 5,
        "material": "regular",
        "appearance": "dark",
        "direction": "dematerialize",
        "windowBackingScaleFactor": 2,
        "captureBackend": "CGWindowListCreateImage",
        "failedSamples": 0,
    }
    for field, expected in expected_timeline.items():
        require(timeline.get(field) == expected, f"timeline {field} differs")
    geometry = mapping(timeline.get("geometry"), "geometry")
    require(geometry.get("name") == "circle-480-center", "geometry differs")
    dynamic = mapping(timeline.get("dynamicBackgroundUniforms"), "dynamic uniforms")
    records = [
        mapping(value, "dynamic record")
        for value in sequence(dynamic.get("records"), "dynamic records")
    ]
    record = single(records, "dynamic record")
    require(record.get("sampleIndex") == SAMPLE_INDEX, "sample index differs")
    require(
        record.get("targetedFinalHighlightRadiusShrinkSelection") is True,
        "radius-shrink acquisition was not requested",
    )
    require(
        record.get("retainedStateUsesFinalHighlightRadiusShrinkTopologyProbe")
        is True,
        "retained state does not satisfy the frozen shrink discriminator",
    )
    require(
        record.get("retainedStateUsesFinalHighlightBorderTopology") is False,
        "capture-side candidate classified the shrink state as border",
    )

    layer = final_layer_state(record)
    bounds = sequence(layer.get("bounds"), "target layer bounds")
    require(len(bounds) == 4, "target layer bounds length differs")
    width = numeric(bounds[2], "target width")
    height = numeric(bounds[3], "target height")
    half_x, half_y, radius_x, radius_y = topology_terms(width, height)
    require(
        model.float32_bits(half_x) == model.float32_bits(half_y),
        "target half-extents are not bitwise equal",
    )
    require(
        model.float32_bits(radius_x) == model.float32_bits(radius_y),
        "target round-trip radii are not bitwise equal",
    )
    require(radius_x < half_x and radius_y < half_y, "state is not radius-shrinking")

    old_border = radius_x != half_x or radius_y != half_y or radius_x != radius_y
    predicted_border = predicts_border(half_x, half_y, radius_x, radius_y)
    require(old_border, "old inequality predicate is not discriminated")
    require(not predicted_border, "frozen directional candidate predicts border")

    inventory = model.final_highlight_inventory(record)
    require(inventory["vertexCount"] == 4, "observed vertex count is not compact")
    require(inventory["indexCount"] == 6, "observed index count is not compact")
    require(
        inventory["indices"]
        == bytes().join(value.to_bytes(2, "little") for value in model.FINAL_QUAD_INDICES),
        "observed compact index stream differs",
    )
    render = mapping(record.get("render"), "render")
    replay = mapping(render.get("exactPassReplay"), "exact pass replay")
    require(replay.get("executed") is True, "exact pass replay did not execute")
    require(replay.get("exactByteMatch") is True, "Apple pass replay is not exact")
    require(replay.get("mismatchedByteCount") == 0, "Apple replay bytes differ")
    require(replay.get("mismatchedPixelCount") == 0, "Apple replay pixels differ")
    labels = {
        model.pipeline_label(mapping(value, "Metal record"))
        for value in sequence(
            mapping(render.get("metalUniformProbe"), "Metal probe").get("records"),
            "Metal records",
        )
    }
    require(model.FINAL_HIGHLIGHT_PIPELINE in labels, "current Iscd draw is absent")
    require(not any(label.endswith("_Irsd") for label in labels), "Irsd draw is present")

    return {
        "walleCurrentFinalTopologySelectorResultSchemaVersion": 1,
        "status": "prospective-negative-ulp-selector-exact",
        "classification": "fresh output-blind direct-Retina holdout",
        "capture": {
            "commit": expected_capture_commit,
            "timelineSHA256": timeline_sha256,
            "preregistrationSHA256": preregistration_sha256,
            "preflightSHA256": sha256_file(preflight_path),
            "contextSHA256": sha256_file(context_path),
            "host": "physical Retina M1 Max, macOS 26.6.1 build 25G76",
            "githubActionsUsed": False,
            "nativeCaptureDebuggerUsed": False,
            "nixStorePathInNativeBuildOrCapture": False,
        },
        "discriminator": {
            "sampleIndex": SAMPLE_INDEX,
            "remaining": record.get("remaining"),
            "extent": [width, height],
            "halfExtentFloat32Bits": [
                f"0x{model.float32_bits(half_x):08x}",
                f"0x{model.float32_bits(half_y):08x}",
            ],
            "radiusFloat32Bits": [
                f"0x{model.float32_bits(radius_x):08x}",
                f"0x{model.float32_bits(radius_y):08x}",
            ],
            "radiusUlpDelta": [
                model.float32_bits(radius_x) - model.float32_bits(half_x),
                model.float32_bits(radius_y) - model.float32_bits(half_y),
            ],
            "oldInequalityPredicatePredictedBorder": old_border,
            "directionalPredicatePredictedBorder": predicted_border,
            "observedVertexCount": inventory["vertexCount"],
            "observedIndexCount": inventory["indexCount"],
            "applePassReplayMismatchedBytes": replay.get("mismatchedByteCount"),
        },
        "promotedRule": (
            "hx=b32(width/2), hy=b32(height/2), "
            "rx=b32(b32(hx+9)-9), ry=b32(b32(hy+9)-9); "
            "border iff rx>hx or ry>hy or rx!=ry"
        ),
        "gate": {
            "prospectiveDiscriminatorExact": True,
            "oldPredicateFalsified": True,
            "selectorMayBeIntegratedIntoWalle": True,
            "remainingWalleAlgorithmUnknowns": 0,
            "productionWalleParityEstablished": False,
            "freshProductionWalleFrameRequired": True,
            "shaderQualityReductionAllowed": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture_directory", type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--expected-capture-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()

    capture_directory = arguments.capture_directory.resolve()
    preregistration_path = arguments.preregistration.resolve()
    require(capture_directory.is_dir(), "capture directory is absent")
    preregistration = load_json(preregistration_path)
    copied_preregistration = capture_directory / "preregistration.json"
    require(copied_preregistration.is_file(), "copied preregistration is absent")
    require(
        copied_preregistration.read_bytes() == preregistration_path.read_bytes(),
        "copied preregistration bytes differ",
    )
    result = validate_capture(
        capture_directory,
        preregistration,
        expected_capture_commit=arguments.expected_capture_commit,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
