#!/usr/bin/env python3
"""Validate the prospective Walle-shaped physical Retina transfer gate."""

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Never

import numpy as np
from PIL import Image


REPOSITORY = Path(__file__).resolve().parents[1]
WIDTH = 2048
HEIGHT = 2048
PIXELS = WIDTH * HEIGHT
FRAME_BYTES = PIXELS * 4
EXPECTED_CASES = (
    ("clear-light", "clear", "light"),
    ("clear-dark", "clear", "dark"),
    ("regular-light", "regular", "light"),
    ("regular-dark", "regular", "dark"),
)
ACCEPTED_CONSTRUCTION_RECORD = (
    REPOSITORY
    / "Analysis/current_final_compositor_transfer_5d0e8de_v7_result.json"
)
ACCEPTED_CONSTRUCTION_SHA256 = (
    "72043d18ff0e9d11d81abe8963b898deb27b7c48d2667ce97ff64bacdf483057"
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


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def capture_file(root: Path, relative: object, label: str) -> Path:
    require(isinstance(relative, str), f"{label} filename is absent")
    resolved_root = root.resolve()
    path = (root / relative).resolve()
    require(path.is_relative_to(resolved_root), f"{label} escapes capture root")
    require(path.is_file(), f"{label} is absent")
    return path


def mismatch_metrics(reference: bytes, candidate: bytes) -> JSONObject:
    require(len(reference) == len(candidate), "comparison byte lengths differ")
    require(len(reference) % 4 == 0, "comparison pixel stride differs")
    if reference == candidate:
        return {
            "byteCount": len(reference),
            "pixelCount": len(reference) // 4,
            "mismatchedByteCount": 0,
            "mismatchedPixelCount": 0,
            "maximumChannelDelta": 0,
            "firstMismatchedByte": -1,
            "exactByteMatch": True,
            "referenceSHA256": sha256_bytes(reference),
            "candidateSHA256": sha256_bytes(candidate),
        }
    reference_array = np.frombuffer(reference, dtype=np.uint8)
    candidate_array = np.frombuffer(candidate, dtype=np.uint8)
    delta = np.abs(
        reference_array.astype(np.int16) - candidate_array.astype(np.int16)
    )
    unequal = delta != 0
    unequal_indices = np.flatnonzero(unequal)
    return {
        "byteCount": len(reference),
        "pixelCount": len(reference) // 4,
        "mismatchedByteCount": int(np.count_nonzero(unequal)),
        "mismatchedPixelCount": int(
            np.count_nonzero(np.any(unequal.reshape((-1, 4)), axis=1))
        ),
        "maximumChannelDelta": int(delta.max(initial=0)),
        "firstMismatchedByte": int(unequal_indices[0]),
        "exactByteMatch": False,
        "referenceSHA256": sha256_bytes(reference),
        "candidateSHA256": sha256_bytes(candidate),
    }


def validate_reported_comparison(
    untyped: object,
    independent: Mapping[str, object],
    *,
    label: str,
) -> None:
    reported = mapping(untyped, label)
    require(reported.get("compared") is True, f"{label} was not compared")
    for field, expected in independent.items():
        require(reported.get(field) == expected, f"{label} {field} differs")


def require_exact(metrics: Mapping[str, object], label: str) -> None:
    unequal_bytes = metrics.get("mismatchedByteCount")
    unequal_pixels = metrics.get("mismatchedPixelCount")
    maximum_delta = metrics.get("maximumChannelDelta")
    require(
        metrics.get("exactByteMatch") is True
        and unequal_bytes == 0
        and unequal_pixels == 0
        and maximum_delta == 0,
        f"{label} is not exact: {unequal_bytes} unequal bytes, "
        f"{unequal_pixels} unequal pixels, maximum delta {maximum_delta}",
    )


def validate_sources(preregistration: Mapping[str, object]) -> None:
    sources = mapping(preregistration.get("sourceSHA256"), "sourceSHA256")
    for relative, expected in sources.items():
        require(
            isinstance(relative, str)
            and isinstance(expected, str)
            and len(expected) == 64,
            "source hash entry is malformed",
        )
        source = (REPOSITORY / relative).resolve()
        require(
            source.is_relative_to(REPOSITORY.resolve()),
            f"pinned source escapes repository: {relative}",
        )
        require(source.is_file(), f"pinned source is absent: {relative}")
        require(
            sha256_file(source) == expected,
            f"pinned source differs: {relative}",
        )


def validate_preregistration(preregistration: Mapping[str, object]) -> None:
    require(
        preregistration.get("walleRetinaTransferPreregistrationSchemaVersion") == 1
        and preregistration.get("status")
        == "frozen-v1-before-prospective-physical-retina-capture",
        "preregistration identity differs",
    )
    dependency = mapping(
        preregistration.get("dependsOnAcceptedAppleConstruction"),
        "accepted construction dependency",
    )
    require(
        dependency.get("captureCommit")
        == "5d0e8de277c7cf09a5ef7c9da69eb64831c3597b"
        and dependency.get("acceptedRecordSHA256")
        == ACCEPTED_CONSTRUCTION_SHA256
        and dependency.get("remainingAppleConstructionQuestions") == 0
        and dependency.get("candidateAndSystemComparedBytes") == 117_440_512
        and dependency.get("unequalBytes") == 0
        and dependency.get("maximumChannelDelta") == 0,
        "accepted construction dependency differs",
    )
    require(
        ACCEPTED_CONSTRUCTION_RECORD.is_file()
        and sha256_file(ACCEPTED_CONSTRUCTION_RECORD)
        == ACCEPTED_CONSTRUCTION_SHA256,
        "accepted construction record differs",
    )
    accepted = load_json(ACCEPTED_CONSTRUCTION_RECORD)
    observations = mapping(accepted.get("observations"), "accepted observations")
    system_comparison = mapping(
        observations.get("capturedVsSystemSpecialization"),
        "accepted system comparison",
    )
    candidate_comparison = mapping(
        observations.get("capturedVsIndependentCandidate"),
        "accepted candidate comparison",
    )
    require(
        accepted.get("status") == "accepted-exact-current-compositor-transfer"
        and accepted.get("promotedEvidence") is True
        and accepted.get("remainingAppleConstructionQuestions") == 0
        and system_comparison.get("comparedBytes") == 58_720_256
        and system_comparison.get("unequalBytes") == 0
        and system_comparison.get("maximumChannelDelta") == 0
        and candidate_comparison.get("comparedBytes") == 58_720_256
        and candidate_comparison.get("unequalBytes") == 0
        and candidate_comparison.get("maximumChannelDelta") == 0,
        "accepted construction record is not exact",
    )
    scope = mapping(preregistration.get("scientificScope"), "scientificScope")
    require(
        scope.get("appleFrameRole") == "controlled transfer stimulus only"
        and scope.get("walleShaped") is True
        and scope.get("independentWalleFrame") is False
        and scope.get("appleConstructionReopened") is False
        and scope.get("algorithmFittingPermitted") is False
        and scope.get("postCaptureCaseExclusionPermitted") is False
        and scope.get("outputTolerance") == 0,
        "scientific scope differs",
    )
    geometry = mapping(preregistration.get("frozenGeometry"), "frozenGeometry")
    require(
        geometry.get("name") == "circle-800-center"
        and geometry.get("widthPoints") == 800
        and geometry.get("heightPoints") == 800
        and geometry.get("centerPoints") == [512, 512]
        and geometry.get("windowPoints") == [1024, 1024]
        and geometry.get("windowPixels") == [WIDTH, HEIGHT]
        and geometry.get("backingScaleFactor") == 2,
        "frozen geometry differs",
    )
    cases = sequence(preregistration.get("cases"), "cases")
    observed_cases = tuple(
        (
            mapping(case, "case").get("label"),
            mapping(case, "case").get("material"),
            mapping(case, "case").get("appearance"),
        )
        for case in cases
    )
    require(observed_cases == EXPECTED_CASES, "preregistered cases differ")
    acceptance = mapping(preregistration.get("acceptance"), "acceptance")
    expected_acceptance = {
        "caseCount": 4,
        "bytesPerFrame": FRAME_BYTES,
        "nativeStabilityComparisonCount": 4,
        "stimulusStabilityComparisonCount": 4,
        "flatStabilityComparisonCount": 4,
        "transferComparisonCount": 4,
        "comparedTransferBytes": 4 * FRAME_BYTES,
        "comparedStabilityBytes": 12 * FRAME_BYTES,
        "totalComparedBytes": 16 * FRAME_BYTES,
        "requiredUnequalBytes": 0,
        "requiredUnequalPixels": 0,
        "requiredMaximumChannelDelta": 0,
        "tolerance": 0,
    }
    for field, expected in expected_acceptance.items():
        require(
            acceptance.get(field) == expected,
            f"acceptance {field} differs",
        )
    validate_sources(preregistration)


def validate_png_capture(
    case_directory: Path,
    untyped: object,
    *,
    label: str,
) -> tuple[bytes, JSONObject]:
    evidence = mapping(untyped, label)
    expected = {
        "backend": "CGWindowListCreateImage",
        "width": WIDTH,
        "height": HEIGHT,
        "bytesPerRow": WIDTH * 4,
        "pixelFormat": "RGBA8 premultiplied-last sRGB top-left",
        "pixelBytes": FRAME_BYTES,
        "sourceBitsPerComponent": 8,
        "sourceBitsPerPixel": 32,
    }
    for field, value in expected.items():
        require(evidence.get(field) == value, f"{label} {field} differs")
    for timing in (
        "startedMediaTime",
        "finishedMediaTime",
        "midpointMediaTime",
        "captureDurationSeconds",
    ):
        require(
            isinstance(evidence.get(timing), int | float),
            f"{label} {timing} is absent",
        )
    require(
        float(evidence["finishedMediaTime"])
        >= float(evidence["startedMediaTime"]),
        f"{label} timing is reversed",
    )
    path = capture_file(case_directory, evidence.get("pngFile"), f"{label} PNG")
    encoded = path.read_bytes()
    require(len(encoded) == evidence.get("pngBytes"), f"{label} PNG bytes differ")
    require(
        sha256_bytes(encoded) == evidence.get("pngSHA256"),
        f"{label} PNG SHA-256 differs",
    )
    with Image.open(path) as image:
        require(image.format == "PNG", f"{label} is not PNG")
        require(image.mode == "RGBA", f"{label} mode differs")
        require(image.size == (WIDTH, HEIGHT), f"{label} dimensions differ")
        pixels = image.tobytes()
    require(len(pixels) == FRAME_BYTES, f"{label} decoded bytes differ")
    require(
        sha256_bytes(pixels) == evidence.get("pixelSHA256"),
        f"{label} pixel SHA-256 differs",
    )
    require(
        pixels[3::4] == b"\xff" * PIXELS,
        f"{label} contains nonopaque pixels",
    )
    source_color_space = evidence.get("sourceColorSpace")
    require(
        isinstance(source_color_space, str) and source_color_space,
        f"{label} source color space is absent",
    )
    return pixels, dict(evidence)


def validate_stimulus(
    case_directory: Path,
    untyped: object,
    *,
    label: str,
) -> tuple[bytes, JSONObject]:
    evidence = mapping(untyped, label)
    expected = {
        "width": WIDTH,
        "height": HEIGHT,
        "scale": 2,
        "bounds": "{{0, 0}, {1024, 1024}}",
        "pixelFormat": "BGRA8 premultiplied-first sRGB top-left",
        "byteCount": FRAME_BYTES,
        "capturedApplePixelsUsedAsTransferStimulus": True,
        "renderConstructionAuthorityClaimed": False,
    }
    for field, value in expected.items():
        require(evidence.get(field) == value, f"{label} {field} differs")
    path = capture_file(case_directory, evidence.get("rawFile"), f"{label} raw")
    pixels = path.read_bytes()
    require(len(pixels) == FRAME_BYTES, f"{label} raw byte count differs")
    require(
        sha256_bytes(pixels) == evidence.get("rawSHA256"),
        f"{label} raw SHA-256 differs",
    )
    require(
        pixels[3::4] == b"\xff" * PIXELS,
        f"{label} contains nonopaque pixels",
    )
    return pixels, dict(evidence)


def validate_color_spaces(
    case_directory: Path,
    untyped: object,
    *,
    label: str,
) -> str:
    records = sequence(untyped, f"{label} colorSpaces")
    require(len(records) == 3, f"{label} color-space count differs")
    by_label = {
        mapping(record, f"{label} color space").get("label"): mapping(
            record, f"{label} color space"
        )
        for record in records
    }
    require(
        set(by_label) == {"window", "screen", "main-display"},
        f"{label} color-space labels differ",
    )
    for name, record in by_label.items():
        require(record.get("available") is True, f"{label} {name} is unavailable")
        require(
            isinstance(record.get("description"), str)
            and isinstance(record.get("numberOfComponents"), int),
            f"{label} {name} metadata differs",
        )
    main_display = by_label["main-display"]
    icc_path = capture_file(
        case_directory,
        main_display.get("iccFile"),
        f"{label} main-display ICC",
    )
    payload = icc_path.read_bytes()
    require(
        len(payload) == main_display.get("iccBytes") and len(payload) > 0,
        f"{label} main-display ICC bytes differ",
    )
    return sha256_bytes(payload)


def validate_case(
    capture_root: Path,
    *,
    case_label: str,
    material: str,
    appearance: str,
) -> JSONObject:
    case_directory = capture_root / case_label
    require(case_directory.is_dir(), f"{case_label} capture directory is absent")
    report = load_json(case_directory / "walle-retina-transfer.json")
    expected = {
        "schemaVersion": 1,
        "executed": True,
        "scope": "physical Retina color and WindowServer transfer only",
        "material": material,
        "appearance": appearance,
        "windowPoints": [1024, 1024],
        "windowPixels": [WIDTH, HEIGHT],
        "windowBackingScaleFactor": 2,
        "capturedApplePixelsUsedOnlyAsTransferStimulus": True,
        "appleConstructionReopened": False,
        "independentWalleFrameClaimed": False,
        "outputTolerance": 0,
    }
    for field, value in expected.items():
        require(report.get(field) == value, f"{case_label} {field} differs")
    geometry = mapping(report.get("geometry"), f"{case_label} geometry")
    require(
        geometry.get("name") == "circle-800-center"
        and geometry.get("shape") == "circle"
        and geometry.get("width") == 800
        and geometry.get("height") == 800
        and geometry.get("centerX") == 512
        and geometry.get("centerY") == 512
        and geometry.get("windowWidth") == 1024
        and geometry.get("windowHeight") == 1024
        and geometry.get("extendsBeyondWindow") is False,
        f"{case_label} geometry differs",
    )
    presentation = mapping(
        report.get("candidatePresentation"),
        f"{case_label} candidatePresentation",
    )
    expected_presentation = {
        "producer": "flat opaque CALayer framebuffer",
        "contentsScale": 2,
        "contentsGravity": "resize",
        "minificationFilter": "nearest",
        "magnificationFilter": "nearest",
        "sourceColorSpace": "sRGB",
        "windowColorSpace": "sRGB",
        "walleShaped": True,
    }
    for field, value in expected_presentation.items():
        require(
            presentation.get(field) == value,
            f"{case_label} presentation {field} differs",
        )

    native_records = sequence(
        report.get("nativeWindowCaptures"), f"{case_label} native captures"
    )
    flat_records = sequence(
        report.get("flatWindowCaptures"), f"{case_label} flat captures"
    )
    stimulus_records = sequence(
        report.get("stimulusFrames"), f"{case_label} stimuli"
    )
    require(len(native_records) == 2, f"{case_label} native count differs")
    require(len(flat_records) == 2, f"{case_label} flat count differs")
    require(len(stimulus_records) == 2, f"{case_label} stimulus count differs")
    native = [
        validate_png_capture(
            case_directory, record, label=f"{case_label} native {index}"
        )
        for index, record in enumerate(native_records)
    ]
    flat = [
        validate_png_capture(
            case_directory, record, label=f"{case_label} flat {index}"
        )
        for index, record in enumerate(flat_records)
    ]
    stimuli = [
        validate_stimulus(
            case_directory, record, label=f"{case_label} stimulus {index}"
        )
        for index, record in enumerate(stimulus_records)
    ]
    capture_spaces = {
        record[1]["sourceColorSpace"] for record in (*native, *flat)
    }
    require(
        len(capture_spaces) == 1,
        f"{case_label} native and flat capture color spaces differ",
    )

    comparisons = (
        (
            "native stability",
            report.get("nativeCaptureStability"),
            native[0][0],
            native[1][0],
        ),
        (
            "stimulus stability",
            report.get("stimulusStability"),
            stimuli[0][0],
            stimuli[1][0],
        ),
        (
            "flat stability",
            report.get("flatCaptureStability"),
            flat[0][0],
            flat[1][0],
        ),
        (
            "native-vs-flat transfer",
            report.get("nativeVsFlatTransfer"),
            native[0][0],
            flat[0][0],
        ),
    )
    summaries: JSONObject = {}
    for name, reported, reference, candidate in comparisons:
        metrics = mismatch_metrics(reference, candidate)
        validate_reported_comparison(
            reported,
            metrics,
            label=f"{case_label} {name}",
        )
        require_exact(metrics, f"{case_label} {name}")
        summaries[name] = metrics
    require(report.get("accepted") is True, f"{case_label} report is not accepted")
    display_icc_sha256 = validate_color_spaces(
        case_directory, report.get("colorSpaces"), label=case_label
    )
    return {
        "label": case_label,
        "material": material,
        "appearance": appearance,
        "nativePixelSHA256": sha256_bytes(native[0][0]),
        "stimulusSHA256": sha256_bytes(stimuli[0][0]),
        "flatPixelSHA256": sha256_bytes(flat[0][0]),
        "captureSourceColorSpace": next(iter(capture_spaces)),
        "mainDisplayICCSHA256": display_icc_sha256,
        "comparisons": summaries,
    }


def validate(
    capture_root: Path,
    preregistration_path: Path,
    preflight_path: Path,
) -> JSONObject:
    preregistration = load_json(preregistration_path)
    validate_preregistration(preregistration)
    preflight = load_json(preflight_path)
    require(preflight.get("passed") is True, "Retina preflight did not pass")
    require(preflight.get("backingScaleFactor") == 2, "Retina scale differs")
    require(
        preflight.get("physicalPixels") == [3456, 2234],
        "physical Retina display differs",
    )
    summaries = [
        validate_case(
            capture_root,
            case_label=label,
            material=material,
            appearance=appearance,
        )
        for label, material, appearance in EXPECTED_CASES
    ]
    native_hashes = {summary["nativePixelSHA256"] for summary in summaries}
    stimulus_hashes = {summary["stimulusSHA256"] for summary in summaries}
    require(len(native_hashes) == 4, "native material/appearance endpoints collapse")
    require(
        len(stimulus_hashes) == 4,
        "stimulus material/appearance endpoints collapse",
    )
    require(
        len({summary["captureSourceColorSpace"] for summary in summaries}) == 1,
        "capture source color space differs across cases",
    )
    require(
        len({summary["mainDisplayICCSHA256"] for summary in summaries}) == 1,
        "main display ICC differs across cases",
    )
    return {
        "walleRetinaTransferResultSchemaVersion": 1,
        "accepted": True,
        "captureRoot": capture_root.name,
        "physicalRetina": True,
        "caseCount": len(EXPECTED_CASES),
        "cases": summaries,
        "nativeStabilityComparisonCount": 4,
        "stimulusStabilityComparisonCount": 4,
        "flatStabilityComparisonCount": 4,
        "exactTransferComparisonCount": 4,
        "comparedTransferBytes": 4 * FRAME_BYTES,
        "comparedStabilityBytes": 12 * FRAME_BYTES,
        "totalComparedBytes": 16 * FRAME_BYTES,
        "unequalBytes": 0,
        "unequalPixels": 0,
        "maximumChannelDelta": 0,
        "remainingAppleConstructionQuestions": 0,
        "remainingProductProofs": [
            "fresh production-Walle frame with zero unequal bytes"
        ],
        "productionParity": False,
        "protectedShaderChangeAuthorized": False,
        "independentExactWalleFrameWorkAuthorized": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = validate(
            args.capture_root,
            args.preregistration,
            args.preflight,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"validation failed: {error}", file=sys.stderr)
        return 1
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
