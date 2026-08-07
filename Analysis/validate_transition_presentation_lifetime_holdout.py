#!/usr/bin/env python3
"""Validate observer-independent Liquid Glass presentation lifetime."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
from typing import Any


VALIDATION_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
TIMELINE_SCHEMA_VERSION = 5
PREFLIGHT_SCHEMA_VERSION = 2
SAMPLE_COUNT = 33
DYNAMIC_INDICES = range(1, SAMPLE_COUNT - 1)
BACKGROUND_PATH = [1, 0, 1, 0]
FOREGROUND_PATH = [1, 0, 1, 1, 0]
EXPECTED_WINDOW_PIXELS = [2048, 2048]
EXPECTED_PHYSICAL_PIXELS = [3456, 2234]
EXPECTED_LOGICAL_POINTS = [1728, 1117]
MAXIMUM_STATE_BRACKET_SECONDS = 0.1
MAXIMUM_WINDOW_CAPTURE_SECONDS = 0.1
MAXIMUM_PROGRESS_ERROR = 0.01
MAXIMUM_ENDPOINT_PROGRESS_ERROR = 0.02
CALIBRATION_RESULT = Path(__file__).with_name(
    "transition_presentation_lifetime_calibration_result.json"
)

CASES = {
    ("clear", "light", "materialize", "circle-452-center"),
    ("clear", "light", "dematerialize", "circle-453-center"),
    ("clear", "dark", "materialize", "circle-460-center"),
    ("clear", "dark", "dematerialize", "circle-461-center"),
    ("regular", "light", "materialize", "circle-468-center"),
    ("regular", "light", "dematerialize", "circle-469-center"),
    ("regular", "dark", "materialize", "circle-476-center"),
    ("regular", "dark", "dematerialize", "circle-477-center"),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def mapping(value: Any, label: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{label} is not an object")
    return value


def sequence(value: Any, label: str) -> list[Any]:
    require(isinstance(value, list), f"{label} is not an array")
    return value


def integer(value: Any, label: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool), f"{label} differs")
    return value


def finite_number(value: Any, label: str) -> float:
    require(
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(value),
        f"{label} is not finite",
    )
    return float(value)


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        return mapping(json.loads(path.read_text(encoding="utf-8")), label)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        error.add_note(f"while reading {path}")
        raise


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_preregistration(
    path: Path,
    identity: tuple[str, str, str, str],
) -> tuple[dict[str, Any], str]:
    preregistration = load_json(path, "preregistration")
    require(
        preregistration.get(
            "transitionPresentationLifetimeHoldoutPreregistrationSchemaVersion"
        )
        == PREREGISTRATION_SCHEMA_VERSION,
        "preregistration schema differs",
    )
    cases = sequence(preregistration.get("caseMatrix"), "case matrix")
    observed_cases = {
        (
            case.get("material"),
            case.get("appearance"),
            case.get("direction"),
            case.get("geometry"),
        )
        for value in cases
        for case in [mapping(value, "case")]
    }
    require(observed_cases == CASES and len(cases) == len(CASES), "case matrix differs")
    selected = [
        case
        for value in cases
        for case in [mapping(value, "case")]
        if (
            case.get("material"),
            case.get("appearance"),
            case.get("direction"),
            case.get("geometry"),
        )
        == identity
    ]
    require(len(selected) == 1, "runtime profile is not one frozen case")
    case = selected[0]
    require(
        case.get("role") == "prospective-holdout"
        and case.get("appleOutputAvailableAtFreeze") is False
        and case.get("expectedTimelineSHA256") is None
        and case.get("expectedImageSHA256") is None
        and case.get("expectedFaceOpacityValues") is None,
        "holdout case was not sealed output-blind",
    )
    candidate = mapping(preregistration.get("frozenCandidate"), "candidate")
    require(
        candidate.get("sampleCount") == SAMPLE_COUNT
        and candidate.get("dynamicSampleIndices") == list(DYNAMIC_INDICES)
        and candidate.get("backgroundPath") == BACKGROUND_PATH
        and candidate.get("foregroundPath") == FOREGROUND_PATH
        and candidate.get("dynamicLayerCount") == 16
        and candidate.get("materializedEndpointLayerCount") == 13
        and candidate.get("absentEndpointLayerCount") == 2
        and candidate.get("maximumStateBracketSeconds") == MAXIMUM_STATE_BRACKET_SECONDS
        and candidate.get("maximumWindowCaptureSeconds")
        == MAXIMUM_WINDOW_CAPTURE_SECONDS
        and candidate.get("maximumAbsoluteRequestedProgressError")
        == MAXIMUM_PROGRESS_ERROR,
        "frozen topology candidate differs",
    )
    acceptance = mapping(preregistration.get("acceptance"), "acceptance")
    for key in (
        "requireNoDebugger",
        "requireNoDynamicUniformReplay",
        "requireExactRetinaSession",
        "requireAllThirtyThreeWindowServerFrames",
        "requireAllFramesPixelDistinct",
        "requireBothPresentationBrackets",
        "requireExactEndpointTopology",
        "requireExactDynamicTopology",
        "requireStrictFaceOpacityMonotonicity",
        "requireEveryPngDigest",
        "zeroToleranceForTopologyAndEndpointValues",
    ):
        require(acceptance.get(key) is True, "acceptance contract differs")
    calibration = mapping(preregistration.get("calibrationEvidence"), "calibration")
    require(
        calibration.get("path")
        == "Analysis/transition_presentation_lifetime_calibration_result.json"
        and CALIBRATION_RESULT.is_file()
        and sha256(CALIBRATION_RESULT) == calibration.get("sha256"),
        "calibration evidence differs",
    )
    implementation = mapping(
        preregistration.get("frozenImplementation"), "frozen implementation"
    )
    require(
        implementation.get("validator")
        == "Analysis/validate_transition_presentation_lifetime_holdout.py"
        and sha256(Path(__file__)) == implementation.get("validatorSHA256"),
        "validator identity differs",
    )
    return preregistration, str(case.get("caseId"))


def validate_preflight(path: Path) -> dict[str, Any]:
    value = load_json(path, "Retina preflight")
    require(
        value.get("localRetinaCaptureSessionPreflightSchemaVersion")
        == PREFLIGHT_SCHEMA_VERSION
        and value.get("passed") is True
        and value.get("displayActive") is True
        and value.get("displayAsleep") is False
        and value.get("sessionLocked") is False
        and value.get("sessionLoginDone") is True
        and value.get("sessionOnConsole") is True
        and value.get("backingScaleFactor") == 2
        and value.get("physicalPixels") == EXPECTED_PHYSICAL_PIXELS
        and value.get("logicalPoints") == EXPECTED_LOGICAL_POINTS,
        "physical Retina session differs",
    )
    return value


def validate_capture_context(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        error.add_note(f"while reading {path}")
        raise
    fields: dict[str, str] = {}
    for line in lines:
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key] = value
    commit = fields.get("CAPTURE_COMMIT", "")
    require(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "capture commit differs")
    require(
        fields.get("NATIVE_CAPTURE_DEBUGGER_USED") == "0"
        and fields.get("LG_TRANSITION_UNIFORMS") == "0"
        and fields.get("LG_TRANSITION_TIMELINE") == "1"
        and fields.get("LG_TRANSITION_CONTROLLED_BACKDROP") == "0",
        "capture context is not observer-independent",
    )
    return commit


def filter_type(value: dict[str, Any]) -> str | None:
    known = value.get("knownValues")
    if isinstance(known, dict) and isinstance(known.get("type"), str):
        return known["type"]
    description = value.get("description")
    return description if isinstance(description, str) else None


def glass_filters(state: dict[str, Any], label: str) -> list[dict[str, Any]]:
    records = sequence(state.get("records"), f"{label} records")
    require(
        integer(state.get("layerCount"), f"{label} layer count") == len(records),
        f"{label} layer count differs",
    )
    result: list[dict[str, Any]] = []
    for record_index, value in enumerate(records):
        record = mapping(value, f"{label} record {record_index}")
        path = sequence(record.get("path"), f"{label} record path")
        for collection_name in ("filters", "backgroundFilters"):
            filters = record.get(collection_name, [])
            for filter_index, filter_value in enumerate(
                sequence(filters, f"{label} {collection_name}")
            ):
                filter_object = mapping(
                    filter_value,
                    f"{label} {collection_name} {filter_index}",
                )
                kind = filter_type(filter_object)
                if kind in {"glassBackground", "glassForeground"}:
                    result.append(
                        {
                            "type": kind,
                            "path": path,
                            "layerClass": record.get("class"),
                            "collection": collection_name,
                            "filter": filter_object,
                        }
                    )
    return result


def expected_topology(direction: str, sample_index: int) -> tuple[bool, bool, int]:
    dynamic = sample_index in DYNAMIC_INDICES
    if dynamic:
        return True, True, 16
    materialized = (direction == "materialize") == (sample_index == SAMPLE_COUNT - 1)
    if materialized:
        return True, False, 13
    return False, False, 2


def validate_state(
    value: Any,
    direction: str,
    sample_index: int,
    label: str,
) -> float | None:
    state = mapping(value, label)
    background_expected, foreground_expected, layer_count = expected_topology(
        direction, sample_index
    )
    require(state.get("layerCount") == layer_count, f"{label} topology size differs")
    filters = glass_filters(state, label)
    backgrounds = [item for item in filters if item["type"] == "glassBackground"]
    foregrounds = [item for item in filters if item["type"] == "glassForeground"]
    require(
        len(backgrounds) == int(background_expected),
        f"{label} glassBackground lifetime differs",
    )
    require(
        len(foregrounds) == int(foreground_expected),
        f"{label} glassForeground lifetime differs",
    )
    if foreground_expected:
        foreground = foregrounds[0]
        require(
            foreground["path"] == FOREGROUND_PATH
            and foreground["collection"] == "filters",
            f"{label} glassForeground topology differs",
        )
    if not background_expected:
        return None
    background = backgrounds[0]
    require(
        background["path"] == BACKGROUND_PATH
        and background["layerClass"] == "CABackdropLayer"
        and background["collection"] == "filters",
        f"{label} glassBackground topology differs",
    )
    inputs = mapping(background["filter"].get("inputValues"), f"{label} inputs")
    face_opacity = finite_number(inputs.get("inputFaceOpacity"), f"{label} opacity")
    if sample_index in DYNAMIC_INDICES:
        require(0.0 < face_opacity < 1.0, f"{label} dynamic opacity differs")
    else:
        require(
            struct.pack("<d", face_opacity) == struct.pack("<d", 1.0),
            f"{label} endpoint opacity differs",
        )
    return face_opacity


def validate_window_capture(
    value: Any,
    directory: Path,
    direction: str,
    sample_index: int,
) -> tuple[str, str, float]:
    capture = mapping(value, f"sample {sample_index} window capture")
    expected_name = f"transition-{direction}-{sample_index:02d}-rgba8.png"
    require(
        capture.get("backend") == "CGWindowListCreateImage"
        and capture.get("width") == EXPECTED_WINDOW_PIXELS[0]
        and capture.get("height") == EXPECTED_WINDOW_PIXELS[1]
        and capture.get("bytesPerRow") == EXPECTED_WINDOW_PIXELS[0] * 4
        and capture.get("pixelBytes")
        == EXPECTED_WINDOW_PIXELS[0] * EXPECTED_WINDOW_PIXELS[1] * 4
        and capture.get("pixelFormat") == "RGBA8 premultiplied-last sRGB top-left"
        and capture.get("pngFile") == expected_name,
        f"sample {sample_index} window capture identity differs",
    )
    duration = finite_number(
        capture.get("captureDurationSeconds"),
        f"sample {sample_index} capture duration",
    )
    require(
        0.0 <= duration <= MAXIMUM_WINDOW_CAPTURE_SECONDS,
        f"sample {sample_index} capture duration differs",
    )
    pixel_sha256 = capture.get("pixelSHA256")
    png_sha256 = capture.get("pngSHA256")
    require(
        isinstance(pixel_sha256, str)
        and len(pixel_sha256) == 64
        and isinstance(png_sha256, str)
        and len(png_sha256) == 64,
        f"sample {sample_index} image digest differs",
    )
    png_path = directory / expected_name
    require(
        png_path.is_file()
        and png_path.stat().st_size == capture.get("pngBytes")
        and sha256(png_path) == png_sha256,
        f"sample {sample_index} PNG bytes differ",
    )
    return pixel_sha256, png_sha256, duration


def validate(
    timeline_path: Path,
    preregistration_path: Path,
    material: str,
    appearance: str,
    direction: str,
    geometry: str,
) -> dict[str, Any]:
    identity = (material, appearance, direction, geometry)
    require(identity in CASES, "runtime identity is not frozen")
    preregistration, case_id = validate_preregistration(preregistration_path, identity)
    preflight_path = timeline_path.parent / "capture-session-preflight.json"
    context_path = timeline_path.parent / "capture-context.txt"
    validate_preflight(preflight_path)
    capture_commit = validate_capture_context(context_path)
    timeline = load_json(timeline_path, "timeline")
    geometry_value = mapping(timeline.get("geometry"), "timeline geometry")
    require(
        timeline.get("schemaVersion") == TIMELINE_SCHEMA_VERSION
        and timeline.get("probe") == "paced-presentation-state-window-timeline"
        and timeline.get("material") == material
        and timeline.get("appearance") == appearance
        and timeline.get("direction") == direction
        and geometry_value.get("name") == geometry
        and timeline.get("animationCurve") == "linear"
        and timeline.get("animationDurationSeconds") == 60
        and timeline.get("sampleCount") == SAMPLE_COUNT
        and timeline.get("sampleProgressRule") == "index/(sampleCount-1)"
        and timeline.get("captureBackend") == "CGWindowListCreateImage"
        and timeline.get("windowBackingScaleFactor") == 2
        and timeline.get("expectedWindowPixels") == EXPECTED_WINDOW_PIXELS
        and timeline.get("failedSamples") == 0,
        "timeline identity differs",
    )
    uniforms = mapping(
        timeline.get("dynamicBackgroundUniforms"), "dynamic uniform evidence"
    )
    require(
        uniforms.get("schemaVersion") == 9
        and uniforms.get("requested") is False
        and uniforms.get("executed") is False
        and uniforms.get("evidenceMode") == "disabled"
        and uniforms.get("presentationLayerReplayed") is False,
        "observer-independent capture mode differs",
    )
    samples = sequence(timeline.get("samples"), "timeline samples")
    require(len(samples) == SAMPLE_COUNT, "timeline sample count differs")
    pixel_hashes: list[str] = []
    png_hashes: list[str] = []
    png_tree = hashlib.sha256()
    face_opacities: list[float] = []
    maximum_state_bracket = 0.0
    maximum_capture_duration = 0.0
    maximum_progress_error = 0.0
    previous_target_time: float | None = None
    for sample_index, sample_value in enumerate(samples):
        sample = mapping(sample_value, f"sample {sample_index}")
        requested = sample_index / (SAMPLE_COUNT - 1)
        progress = finite_number(
            sample.get("progress"), f"sample {sample_index} progress"
        )
        actual_progress = finite_number(
            sample.get("actualProgress"), f"sample {sample_index} actual progress"
        )
        require(
            sample.get("executed") is True
            and struct.pack("<d", progress) == struct.pack("<d", requested),
            f"sample {sample_index} requested progress differs",
        )
        progress_error = abs(actual_progress - requested)
        allowed_error = (
            MAXIMUM_ENDPOINT_PROGRESS_ERROR
            if sample_index == SAMPLE_COUNT - 1
            else MAXIMUM_PROGRESS_ERROR
        )
        require(
            progress_error <= allowed_error,
            f"sample {sample_index} presentation schedule differs",
        )
        if sample_index == 0:
            require(actual_progress == 0.0, "initial actual progress differs")
        elif sample_index < SAMPLE_COUNT - 1:
            require(0.0 < actual_progress < 1.0, "dynamic actual progress differs")
        else:
            require(1.0 <= actual_progress <= 1.02, "endpoint progress differs")
        target_time = finite_number(
            sample.get("targetMediaTime"), f"sample {sample_index} target time"
        )
        if previous_target_time is not None:
            require(
                target_time > previous_target_time, "target times are not increasing"
            )
        previous_target_time = target_time
        bracket = finite_number(
            sample.get("stateBracketSeconds"), f"sample {sample_index} state bracket"
        )
        require(
            0.0 <= bracket <= MAXIMUM_STATE_BRACKET_SECONDS,
            f"sample {sample_index} state bracket differs",
        )
        before = validate_state(
            sample.get("presentationStateBeforeCapture"),
            direction,
            sample_index,
            f"sample {sample_index} before state",
        )
        after = validate_state(
            sample.get("presentationStateAfterCapture"),
            direction,
            sample_index,
            f"sample {sample_index} after state",
        )
        require(
            before is None
            and after is None
            or before is not None
            and after is not None
            and struct.pack("<d", before) == struct.pack("<d", after),
            f"sample {sample_index} bracketed face opacity differs",
        )
        if after is not None:
            face_opacities.append(after)
        pixel_sha256, png_sha256, capture_duration = validate_window_capture(
            sample.get("windowCapture"),
            timeline_path.parent,
            direction,
            sample_index,
        )
        pixel_hashes.append(pixel_sha256)
        png_hashes.append(png_sha256)
        png_tree.update(f"transition-{direction}-{sample_index:02d}-rgba8.png".encode())
        png_tree.update(b"\0")
        png_tree.update(bytes.fromhex(png_sha256))
        maximum_state_bracket = max(maximum_state_bracket, bracket)
        maximum_capture_duration = max(maximum_capture_duration, capture_duration)
        maximum_progress_error = max(maximum_progress_error, progress_error)
    require(
        len(set(pixel_hashes)) == SAMPLE_COUNT and len(set(png_hashes)) == SAMPLE_COUNT,
        "WindowServer frames are not all distinct",
    )
    dynamic_values = (
        face_opacities[:-1] if direction == "materialize" else face_opacities[1:]
    )
    require(
        len(dynamic_values) == len(DYNAMIC_INDICES), "dynamic opacity count differs"
    )
    pairs = zip(dynamic_values, dynamic_values[1:])
    if direction == "materialize":
        require(all(left < right for left, right in pairs), "opacity is not increasing")
    else:
        require(all(left > right for left, right in pairs), "opacity is not decreasing")
    endpoint = mapping(samples[-1], "endpoint sample")
    require(
        endpoint.get("endpointTopologyExpectedGlassBackground")
        is (direction == "materialize")
        and endpoint.get("endpointTopologyMatchedBeforeCapture") is True
        and (
            endpoint.get("endpointTopologyObservedFaceOpacity") == 1
            if direction == "materialize"
            else endpoint.get("endpointTopologyObservedFaceOpacity") is None
        ),
        "endpoint topology wait differs",
    )
    return {
        "transitionPresentationLifetimeHoldoutValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "status": "passed",
        "authority": "prospective-holdout",
        "caseId": case_id,
        "profile": {
            "material": material,
            "appearance": appearance,
            "direction": direction,
            "geometry": geometry,
        },
        "capture": {
            "debuggerUsed": False,
            "dynamicUniformReplayUsed": False,
            "sampleCount": SAMPLE_COUNT,
            "presentationStateCount": SAMPLE_COUNT * 2,
            "glassBackgroundPresenceCount": 64,
            "glassForegroundPresenceCount": 62,
            "uniquePixelSHA256Count": len(set(pixel_hashes)),
            "uniquePngSHA256Count": len(set(png_hashes)),
            "pngTreeSHA256": png_tree.hexdigest(),
            "maximumStateBracketSeconds": maximum_state_bracket,
            "maximumWindowCaptureSeconds": maximum_capture_duration,
            "maximumAbsoluteRequestedProgressError": maximum_progress_error,
        },
        "topology": {
            "backgroundPath": BACKGROUND_PATH,
            "foregroundPath": FOREGROUND_PATH,
            "dynamicSampleIndices": list(DYNAMIC_INDICES),
            "dynamicFaceOpacityValues": dynamic_values,
            "strictFaceOpacityMonotonicityPassed": True,
            "endpointTopologyPassed": True,
            "allPresentationBracketsExact": True,
        },
        "evidence": {
            "captureCommit": capture_commit,
            "timelineSHA256": sha256(timeline_path),
            "preflightSHA256": sha256(preflight_path),
            "captureContextSHA256": sha256(context_path),
            "preregistrationSHA256": sha256(preregistration_path),
            "calibrationResultSHA256": sha256(CALIBRATION_RESULT),
        },
        "sealedConclusion": {
            "observerIndependentPresentationLifetimeTransferPassedForCase": True,
            "appearanceDependentRemovalObservedForCase": False,
            "physicalRetinaColorPixelCompositorTransferEstablished": False,
            "independentWalleZeroByteFrameParityEstablished": False,
            "productionShaderChanged": False,
            "liquidGlassParityEstablished": False,
        },
        "preregistrationClassification": preregistration["classification"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("timeline", type=Path)
    parser.add_argument("preregistration", type=Path)
    parser.add_argument("--material", required=True, choices=("clear", "regular"))
    parser.add_argument("--appearance", required=True, choices=("light", "dark"))
    parser.add_argument(
        "--direction", required=True, choices=("materialize", "dematerialize")
    )
    parser.add_argument("--geometry", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(
        arguments.timeline,
        arguments.preregistration,
        arguments.material,
        arguments.appearance,
        arguments.direction,
        arguments.geometry,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
