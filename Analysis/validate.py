#!/usr/bin/env python3
"""Validate a GlassCapture artifact without trusting its manifest hashes."""

import argparse
import hashlib
import json
import math
import statistics
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageCms


type JsonObject = dict[str, Any]


@dataclass(slots=True)
class Findings:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


@dataclass(frozen=True, slots=True)
class DecodedImage:
    width: int
    height: int
    rgba: bytes
    pixel_sha256: str
    declared_srgb: bool
    color_description: str
    opaque_alpha: bool


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


@lru_cache(maxsize=2)
def decode_image(path: Path) -> DecodedImage:
    with Image.open(path) as source:
        source.load()
        color_description = "unlabeled"
        declared_srgb = "srgb" in source.info
        if declared_srgb:
            color_description = "sRGB PNG chunk"
        elif profile_data := source.info.get("icc_profile"):
            try:
                profile = ImageCms.ImageCmsProfile(BytesIO(profile_data))
                color_description = ImageCms.getProfileDescription(profile).strip()
                declared_srgb = "srgb" in color_description.casefold()
            except (OSError, TypeError, ValueError):
                color_description = "invalid ICC profile"
        rgba = source.convert("RGBA")
        pixels = rgba.tobytes()
        alpha_extrema = rgba.getextrema()[3]
        return DecodedImage(
            width=rgba.width,
            height=rgba.height,
            rgba=pixels,
            pixel_sha256=hashlib.sha256(pixels).hexdigest(),
            declared_srgb=declared_srgb,
            color_description=color_description,
            opaque_alpha=alpha_extrema == (255, 255),
        )


def artifact_path(root: Path, relative: object, findings: Findings) -> Path | None:
    if not isinstance(relative, str) or not relative:
        findings.error(f"invalid artifact path: {relative!r}")
        return None
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        findings.error(f"artifact path escapes root: {relative}")
        return None
    if not candidate.is_file():
        findings.error(f"missing file: {relative}")
        return None
    return candidate


def verify_image_record(
    *,
    root: Path,
    record: JsonObject,
    file_hash_key: str,
    label: str,
    findings: Findings,
) -> DecodedImage | None:
    path = artifact_path(root, record.get("file"), findings)
    if path is None:
        return None
    expected_file_hash = record.get(file_hash_key)
    actual_file_hash = file_sha256(path)
    if actual_file_hash != expected_file_hash:
        findings.error(
            f"{label}: file SHA-256 is {actual_file_hash}, expected "
            f"{expected_file_hash!r}"
        )
    try:
        decoded = decode_image(path)
    except Exception as error:
        findings.error(f"{label}: cannot decode PNG: {error}")
        return None
    expected_pixel_hash = record.get("pixelSha256")
    if decoded.pixel_sha256 != expected_pixel_hash:
        findings.error(
            f"{label}: RGBA pixel SHA-256 is {decoded.pixel_sha256}, expected "
            f"{expected_pixel_hash!r}"
        )
    if not decoded.declared_srgb:
        findings.error(
            f"{label}: PNG is not explicitly tagged sRGB ({decoded.color_description})"
        )
    if not decoded.opaque_alpha:
        findings.error(f"{label}: canonical PNG contains non-opaque alpha")
    expected_size = (record.get("pixelWidth"), record.get("pixelHeight"))
    if (decoded.width, decoded.height) != expected_size:
        findings.error(
            f"{label}: decoded size {decoded.width}x{decoded.height}, expected "
            f"{expected_size[0]}x{expected_size[1]}"
        )
    return decoded


def verify_image_metadata(
    *,
    record: JsonObject,
    decoded: DecodedImage,
    saved_key: str,
    label: str,
    findings: Findings,
    require_source: bool,
) -> None:
    saved = record.get(saved_key)
    if not isinstance(saved, dict):
        findings.error(f"{label}: missing {saved_key} metadata")
    else:
        expected = {
            "bitsPerComponent": 8,
            "bitsPerPixel": 32,
            "bytesPerRow": decoded.width * 4,
        }
        for key, value in expected.items():
            if saved.get(key) != value:
                findings.error(
                    f"{label}: {saved_key}.{key} is {saved.get(key)!r}, "
                    f"expected {value}"
                )
        color_space = str(saved.get("colorSpace", ""))
        if "srgb" not in color_space.casefold():
            findings.error(
                f"{label}: {saved_key} is not canonical sRGB: {color_space!r}"
            )
    if require_source:
        source = record.get("sourceImage")
        if not isinstance(source, dict):
            findings.error(f"{label}: missing sourceImage metadata")
        elif source.get("bitsPerComponent") != 8:
            findings.error(
                f"{label}: sourceImage.bitsPerComponent is "
                f"{source.get('bitsPerComponent')!r}, expected 8"
            )


def pixel_diff(reference: bytes, capture: bytes) -> tuple[int, int, float]:
    if len(reference) != len(capture) or len(reference) % 4:
        return max(len(reference), len(capture)) // 4, 255, 255.0
    if reference == capture:
        return 0, 0, 0.0

    changed_pixels = 0
    maximum = 0
    absolute_sum = 0
    for offset in range(0, len(reference), 4):
        changed = False
        for channel in range(3):
            delta = abs(reference[offset + channel] - capture[offset + channel])
            maximum = max(maximum, delta)
            absolute_sum += delta
            changed |= delta != 0
        changed_pixels += changed
    return changed_pixels, maximum, absolute_sum / (len(reference) // 4 * 3)


def source_diff_is_within_tolerance(
    diff: tuple[int, int, float],
    pixel_count: int,
    tolerance: JsonObject,
) -> bool:
    if pixel_count <= 0:
        return False
    changed_fraction = diff[0] / pixel_count
    maximum_fraction = tolerance.get("maximumChangedPixelFraction")
    maximum_delta = tolerance.get("maximumChannelDelta")
    maximum_mean = tolerance.get("maximumMeanAbsoluteChannelDelta")
    return (
        isinstance(maximum_fraction, (int, float))
        and isinstance(maximum_delta, int)
        and isinstance(maximum_mean, (int, float))
        and 0 <= maximum_fraction <= 1
        and maximum_delta >= 0
        and maximum_mean >= 0
        and changed_fraction <= maximum_fraction
        and diff[1] <= maximum_delta
        and diff[2] <= maximum_mean
    )


def crop_rgba(image: DecodedImage, crop: JsonObject) -> bytes:
    x = int(crop["x"])
    y = int(crop["y"])
    width = int(crop["width"])
    height = int(crop["height"])
    if (
        x < 0
        or y < 0
        or width <= 0
        or height <= 0
        or x + width > image.width
        or y + height > image.height
    ):
        raise ValueError(f"crop is outside {image.width}x{image.height}: {crop}")
    row_bytes = image.width * 4
    cropped_row_bytes = width * 4
    return b"".join(
        image.rgba[
            (row * row_bytes + x * 4) : (row * row_bytes + x * 4 + cropped_row_bytes)
        ]
        for row in range(y, y + height)
    )


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def validate_environment(manifest: JsonObject, findings: Findings) -> None:
    schema = manifest.get("schemaVersion")
    if schema not in {3, 4}:
        findings.error(f"schemaVersion is {schema!r}; validator supports 3 and 4")
    expected_rig = {3: "2.1.0", 4: "2.2.0"}.get(schema)
    if manifest.get("rigVersion") != expected_rig:
        findings.error(f"unexpected rigVersion: {manifest.get('rigVersion')!r}")
    if manifest.get("requestedSuite") not in {"static", "dynamic", "all"}:
        findings.error(f"invalid requestedSuite: {manifest.get('requestedSuite')!r}")
    if manifest.get("canonicalPixelEncoding") != "sRGB RGBA8 top-left opaque-alpha":
        findings.error(
            "unexpected canonicalPixelEncoding: "
            f"{manifest.get('canonicalPixelEncoding')!r}"
        )
    version = str(manifest.get("osVersion", ""))
    if "Version 26." not in version and "macOS 26." not in version:
        findings.error(f"capture did not report macOS 26: {version!r}")
    if manifest.get("reduceTransparency") is not False:
        findings.error("Reduce Transparency was enabled during capture")
    if manifest.get("increaseContrast") is not False:
        findings.error("Increase Contrast was enabled during capture")
    if manifest.get("reduceMotion") is not False:
        findings.error("Reduce Motion was enabled during capture")
    if manifest.get("applicationActive") is not True:
        findings.error("capture application was not active")
    if manifest.get("windowKey") is not True:
        findings.error("capture window was not key")
    preflight_errors = manifest.get("preflightErrors")
    if not isinstance(preflight_errors, list):
        findings.error("preflightErrors is not a list")
    elif preflight_errors:
        findings.error(f"capture preflight failed: {preflight_errors}")
    tolerance = manifest.get("sourceRoundTripTolerance")
    if not isinstance(tolerance, dict) or not source_diff_is_within_tolerance(
        (0, 0, 0.0), 1, tolerance
    ):
        findings.error(f"invalid sourceRoundTripTolerance: {tolerance!r}")
    scale = manifest.get("backingScaleFactor")
    if not isinstance(scale, (int, float)) or scale <= 0:
        findings.error(f"invalid backing scale: {scale!r}")


def validate_static(
    root: Path,
    manifest: JsonObject,
    references: dict[str, JsonObject],
    findings: Findings,
) -> dict[str, Any]:
    captures = manifest.get("captures")
    if not isinstance(captures, list):
        findings.error("captures is not a list")
        return {"count": 0}

    seen_files: set[str] = set()
    base_controls: dict[tuple[str, str], str] = {}
    decoded_hashes: dict[str, str] = {}
    actual_cases: set[tuple[str, str, str, str]] = set()
    tolerance_value = manifest.get("sourceRoundTripTolerance")
    tolerance = tolerance_value if isinstance(tolerance_value, dict) else {}
    unstable = 0
    for index, value in enumerate(captures):
        if not isinstance(value, dict):
            findings.error(f"capture[{index}] is not an object")
            continue
        record: JsonObject = value
        label = f"capture[{index}] {record.get('file', '<missing>')}"
        relative = record.get("file")
        if isinstance(relative, str):
            if relative in seen_files:
                findings.error(f"duplicate capture path: {relative}")
            seen_files.add(relative)
        decoded = verify_image_record(
            root=root,
            record=record,
            file_hash_key="sha256",
            label=label,
            findings=findings,
        )
        if decoded is not None and isinstance(relative, str):
            decoded_hashes[relative] = decoded.pixel_sha256
        if decoded is not None:
            verify_image_metadata(
                record=record,
                decoded=decoded,
                saved_key="savedImage",
                label=label,
                findings=findings,
                require_source=True,
            )
        if record.get("stable") is not True:
            unstable += 1
            findings.error(f"{label}: static pixels did not stabilize")
        samples = record.get("stabilitySamples")
        if not isinstance(samples, int) or not 2 <= samples <= 4:
            findings.error(f"{label}: invalid stabilitySamples {samples!r}")

        background = record.get("background")
        appearance = record.get("appearance")
        overlay = record.get("overlay")
        scene = record.get("scene")
        reference_entry = references.get(str(background))
        expected_reference_file = (
            reference_entry.get("file") if reference_entry is not None else None
        )
        if record.get("referenceFile") != expected_reference_file:
            findings.error(
                f"{label}: referenceFile is {record.get('referenceFile')!r}, "
                f"expected {expected_reference_file!r}"
            )
        expected_control_file = (
            f"shots/{background}__circle-0500-center__none__{appearance}.png"
        )
        if record.get("controlFile") != expected_control_file:
            findings.error(
                f"{label}: controlFile is {record.get('controlFile')!r}, "
                f"expected {expected_control_file!r}"
            )
        case = (str(background), str(scene), str(overlay), str(appearance))
        if case in actual_cases:
            findings.error(f"{label}: duplicate logical capture case {case}")
        actual_cases.add(case)
        if overlay == "none" and scene == "circle-0500-center":
            if isinstance(background, str) and isinstance(appearance, str):
                pair = (background, appearance)
                if isinstance(relative, str):
                    if pair in base_controls:
                        findings.error(f"{label}: duplicate base control {pair}")
                    base_controls[pair] = relative
            stored_diff = record.get("sourceDiff")
            if reference_entry is None:
                findings.error(f"{label}: no generated source reference")
            elif decoded is not None:
                reference_path = artifact_path(
                    root, reference_entry.get("file"), findings
                )
                if reference_path is None:
                    continue
                actual_diff = pixel_diff(
                    decode_image(reference_path).rgba, decoded.rgba
                )
                expected_diff = (
                    (
                        stored_diff.get("changedPixels"),
                        stored_diff.get("maxChannelDelta"),
                        stored_diff.get("meanAbsoluteChannelDelta"),
                    )
                    if isinstance(stored_diff, dict)
                    else None
                )
                if expected_diff is None:
                    findings.error(f"{label}: missing sourceDiff")
                elif actual_diff[:2] != expected_diff[:2] or not math.isclose(
                    actual_diff[2], expected_diff[2], rel_tol=0, abs_tol=1e-12
                ):
                    findings.error(
                        f"{label}: stored sourceDiff {expected_diff} does not "
                        f"match recomputed {actual_diff}"
                    )
                if not source_diff_is_within_tolerance(
                    actual_diff, decoded.width * decoded.height, tolerance
                ):
                    findings.error(
                        f"{label}: source round-trip exceeds tolerance: {actual_diff}"
                    )
        elif record.get("sourceDiff") is not None:
            findings.error(f"{label}: sourceDiff is only valid on base controls")

    for value in captures:
        if not isinstance(value, dict):
            continue
        pair = (str(value.get("background")), str(value.get("appearance")))
        if pair not in base_controls:
            findings.error(
                f"{value.get('file')}: no base no-glass control for {pair[0]}/{pair[1]}"
            )
        elif value.get("controlFile") != base_controls[pair]:
            findings.error(
                f"{value.get('file')}: does not reference the captured base "
                f"control {base_controls[pair]}"
            )

    backgrounds_with_controls = {background for background, _ in base_controls}
    for background in backgrounds_with_controls:
        light = base_controls.get((background, "light"))
        dark = base_controls.get((background, "dark"))
        if light is None or dark is None:
            continue
        if decoded_hashes.get(light) != decoded_hashes.get(dark):
            findings.error(
                f"no-glass controls differ between appearances for {background}"
            )
    if manifest.get("requestedSuite") in {"static", "all"}:
        static_backgrounds = {
            name
            for name, record in references.items()
            if record.get("family") != "dynamic"
        }
        appearances = {"light", "dark"}
        expected_cases = {
            (background, "circle-0500-center", overlay, appearance)
            for background in static_backgrounds
            for overlay in ("none", "regular", "clear")
            for appearance in appearances
        }
        tint_backgrounds = {
            "gray-000",
            "gray-128",
            "gray-255",
            "red-255",
            "green-255",
            "blue-255",
            "uv-map",
        }
        expected_cases |= {
            (background, "circle-0500-center", overlay, appearance)
            for background in tint_backgrounds & static_backgrounds
            for overlay in ("tintedBlue", "tintedOrange", "clearTintedBlue")
            for appearance in appearances
        }
        scene_values = manifest.get("scenes")
        scene_names = (
            {
                str(scene.get("name"))
                for scene in scene_values
                if isinstance(scene_values, list) and isinstance(scene, dict)
            }
            if isinstance(scene_values, list)
            else set()
        )
        expected_cases |= {
            (background, scene, overlay, appearance)
            for background in {"gray-128", "checker-0128", "uv-map", "radial-0128"}
            & static_backgrounds
            for scene in scene_names - {"circle-0500-center"}
            for overlay in ("regular", "clear")
            for appearance in appearances
        }
        if manifest.get("schemaVersion") == 4:
            expected_cases |= {
                (background, "circle-4000-center", overlay, appearance)
                for background in {"ramp-x", "ramp-y", "color-cube-9"}
                & static_backgrounds
                for overlay in ("regular", "clear")
                for appearance in appearances
            }
            expected_cases |= {
                (background, scene, overlay, appearance)
                for background in {
                    f"sine-{axis}-p{period:04d}-ph{phase}"
                    for axis in ("x", "y")
                    for period in (64, 256, 1024)
                    for phase in range(4)
                }
                & static_backgrounds
                for scene in ("circle-0256-center", "circle-4000-center")
                for overlay in ("regular", "clear")
                for appearance in appearances
            }
        if "brick" in static_backgrounds:
            expected_cases |= {
                (
                    "brick",
                    "hig-interactive-controls",
                    "hig-interactive-regular",
                    appearance,
                )
                for appearance in appearances
            }
        missing = expected_cases - actual_cases
        unexpected = actual_cases - expected_cases
        if missing:
            findings.error(
                f"static matrix is missing {len(missing)} cases; first: "
                f"{sorted(missing)[:8]}"
            )
        if unexpected:
            findings.error(
                f"static matrix has {len(unexpected)} unexpected cases; first: "
                f"{sorted(unexpected)[:8]}"
            )
    return {
        "count": len(captures),
        "controls": len(base_controls),
        "unstable": unstable,
    }


def validate_references(
    root: Path,
    manifest: JsonObject,
    findings: Findings,
) -> dict[str, JsonObject]:
    values = manifest.get("references")
    if not isinstance(values, list):
        findings.error("references is not a list")
        return {}
    references: dict[str, JsonObject] = {}
    seen_files: set[str] = set()
    for index, value in enumerate(values):
        if not isinstance(value, dict):
            findings.error(f"reference[{index}] is not an object")
            continue
        record: JsonObject = value
        background = record.get("background")
        label = f"reference[{index}] {record.get('file', '<missing>')}"
        relative = record.get("file")
        if isinstance(relative, str):
            if relative in seen_files:
                findings.error(f"duplicate reference path: {relative}")
            seen_files.add(relative)
        if not isinstance(background, str) or background in references:
            findings.error(f"{label}: duplicate or invalid background {background!r}")
            continue
        decoded = verify_image_record(
            root=root,
            record=record,
            file_hash_key="fileSha256",
            label=label,
            findings=findings,
        )
        if decoded is not None:
            verify_image_metadata(
                record=record,
                decoded=decoded,
                saved_key="image",
                label=label,
                findings=findings,
                require_source=False,
            )
            references[background] = record
    return references


def validate_dynamic(
    root: Path,
    manifest: JsonObject,
    references: dict[str, JsonObject],
    findings: Findings,
) -> tuple[dict[str, Any], list[JsonObject]]:
    values = manifest.get("dynamicSequences")
    if not isinstance(values, list):
        findings.error("dynamicSequences is not a list")
        return {"sequences": 0, "frames": 0}, []

    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    materialize_controls: dict[tuple[str, str], str] = {}
    timing_reports: list[JsonObject] = []
    total_frames = 0
    tolerance_value = manifest.get("sourceRoundTripTolerance")
    tolerance = tolerance_value if isinstance(tolerance_value, dict) else {}
    for sequence_index, value in enumerate(values):
        if not isinstance(value, dict):
            findings.error(f"dynamicSequences[{sequence_index}] is not an object")
            continue
        sequence: JsonObject = value
        sequence_id = sequence.get("id")
        label = f"dynamic {sequence_id!r}"
        if not isinstance(sequence_id, str) or sequence_id in seen_ids:
            findings.error(f"duplicate or invalid dynamic sequence id: {sequence_id!r}")
            continue
        seen_ids.add(sequence_id)
        expected_id = (
            f"{sequence.get('mode')}__{sequence.get('overlay')}"
            f"__{sequence.get('appearance')}"
        )
        if sequence_id != expected_id:
            findings.error(f"{label}: fields imply id {expected_id!r}")
        if sequence.get("background") not in references:
            findings.error(f"{label}: missing background reference")
        if sequence.get("animationCurve") != "linear":
            findings.error(f"{label}: animation curve is not linear")
        duration = sequence.get("durationSeconds")
        frames = sequence.get("frames")
        crop = sequence.get("cropPixels")
        if not isinstance(duration, (int, float)) or duration <= 0:
            findings.error(f"{label}: invalid duration {duration!r}")
            continue
        if not isinstance(frames, list) or len(frames) < 3:
            findings.error(f"{label}: too few frames")
            continue
        configured_frames = manifest.get("dynamicFrameCount")
        if not isinstance(configured_frames, int) or configured_frames < 3:
            findings.error(
                f"{label}: invalid configured target frame count {configured_frames!r}"
            )
            continue
        minimum_captured = min(10, configured_frames)
        if len(frames) < minimum_captured:
            findings.error(
                f"{label}: captured only {len(frames)} deadline-reachable frames; "
                f"expected at least {minimum_captured}"
            )
        configured_duration = manifest.get("dynamicDurationSeconds")
        if isinstance(configured_duration, (int, float)) and not math.isclose(
            duration, configured_duration, rel_tol=0, abs_tol=1e-12
        ):
            findings.error(
                f"{label}: duration {duration} differs from configured "
                f"{configured_duration}"
            )
        if not isinstance(crop, dict):
            findings.error(f"{label}: missing cropPixels")
            continue
        if manifest.get("schemaVersion") == 4:
            exclusions = sequence.get("analysisExclusionPixels")
            scale = manifest.get("backingScaleFactor")
            marker_height = (
                max(1, round(4 * float(scale)))
                if isinstance(scale, (int, float))
                else 4
            )
            crop_height = crop.get("height")
            expected_exclusions = (
                [
                    {
                        "x": 0,
                        "y": 0,
                        "width": crop.get("width"),
                        "height": min(marker_height, crop_height)
                        if isinstance(crop_height, int)
                        else marker_height,
                    }
                ]
                if sequence.get("mode") == "wallpaper-wipe"
                else []
            )
            if exclusions != expected_exclusions:
                findings.error(
                    f"{label}: analysisExclusionPixels is {exclusions!r}, "
                    f"expected {expected_exclusions!r}"
                )

        total_frames += len(frames)
        actual_times: list[float] = []
        timing_errors: list[float] = []
        capture_durations: list[float] = []
        presentation_progress: list[float] = []
        pixel_hashes: list[str] = []
        grid_indices: list[int] = []
        first_decoded: DecodedImage | None = None
        for frame_position, frame_value in enumerate(frames):
            if not isinstance(frame_value, dict):
                findings.error(f"{label}: frame[{frame_position}] is not an object")
                continue
            frame: JsonObject = frame_value
            frame_label = f"{label} frame[{frame_position}]"
            grid_index = frame.get("index")
            if (
                not isinstance(grid_index, int)
                or not 0 <= grid_index < configured_frames
            ):
                findings.error(
                    f"{frame_label}: invalid target-grid index {grid_index!r}"
                )
                continue
            grid_indices.append(grid_index)
            expected_target = duration * grid_index / (configured_frames - 1)
            target = frame.get("targetSeconds")
            actual = frame.get("actualSeconds")
            error = frame.get("timingErrorSeconds")
            capture_duration = frame.get("captureDurationSeconds")
            presented = frame.get("presentationProgress")
            if not isinstance(target, (int, float)) or not math.isclose(
                target, expected_target, rel_tol=0, abs_tol=1e-9
            ):
                findings.error(
                    f"{frame_label}: target {target!r}, expected {expected_target}"
                )
            if not isinstance(actual, (int, float)):
                findings.error(f"{frame_label}: invalid actualSeconds {actual!r}")
            else:
                actual_times.append(float(actual))
            if (
                not isinstance(error, (int, float))
                or not isinstance(actual, (int, float))
                or not isinstance(target, (int, float))
                or not math.isclose(error, actual - target, rel_tol=0, abs_tol=1e-9)
            ):
                findings.error(f"{frame_label}: inconsistent timingErrorSeconds")
            elif grid_index:
                timing_errors.append(abs(float(error)))
            if not isinstance(capture_duration, (int, float)) or capture_duration < 0:
                findings.error(f"{frame_label}: invalid capture duration")
            else:
                capture_durations.append(float(capture_duration))
            if presented is not None:
                if not isinstance(presented, (int, float)) or not 0 <= presented <= 1:
                    findings.error(
                        f"{frame_label}: invalid presentationProgress {presented!r}"
                    )
                else:
                    presentation_progress.append(float(presented))

            relative = frame.get("file")
            if isinstance(relative, str):
                if relative in seen_files:
                    findings.error(f"duplicate dynamic frame path: {relative}")
                seen_files.add(relative)
            decoded = verify_image_record(
                root=root,
                record=frame,
                file_hash_key="fileSha256",
                label=frame_label,
                findings=findings,
            )
            if decoded is not None:
                verify_image_metadata(
                    record=frame,
                    decoded=decoded,
                    saved_key="savedImage",
                    label=frame_label,
                    findings=findings,
                    require_source=True,
                )
                if frame_position == 0:
                    first_decoded = decoded
                expected_size = (crop.get("width"), crop.get("height"))
                if (decoded.width, decoded.height) != expected_size:
                    findings.error(
                        f"{frame_label}: dimensions disagree with crop {expected_size}"
                    )
                pixel_hashes.append(decoded.pixel_sha256)

        if any(right <= left for left, right in zip(grid_indices, grid_indices[1:])):
            findings.error(f"{label}: target-grid indices are not strictly increasing")
        if grid_indices and (
            grid_indices[0] != 0 or grid_indices[-1] != configured_frames - 1
        ):
            findings.error(
                f"{label}: target-grid endpoints are {grid_indices[0]} and "
                f"{grid_indices[-1]}, expected 0 and {configured_frames - 1}"
            )
        if any(right <= left for left, right in zip(actual_times, actual_times[1:])):
            findings.error(f"{label}: actual sample times are not strictly increasing")
        actual_gaps = [
            right - left for left, right in zip(actual_times, actual_times[1:])
        ]
        maximum_actual_gap = max(actual_gaps, default=0)
        if maximum_actual_gap > 0.200:
            findings.error(
                f"{label}: temporal evidence has a {maximum_actual_gap:.6f}s "
                "sampling hole; maximum is 0.200000s"
            )
        if actual_times and actual_times[-1] < duration - 0.050:
            findings.error(
                f"{label}: final sample is at {actual_times[-1]:.6f}s, "
                f"before the {duration:.6f}s endpoint"
            )
        if actual_times and actual_times[-1] > duration + 0.250:
            findings.error(
                f"{label}: final sample is at {actual_times[-1]:.6f}s, "
                f"more than 0.250000s after the {duration:.6f}s endpoint"
            )

        schema = manifest.get("schemaVersion")
        if schema == 4:
            if len(presentation_progress) != len(frames):
                findings.error(
                    f"{label}: presentation clock decoded for "
                    f"{len(presentation_progress)}/{len(frames)} frames"
                )
            elif presentation_progress:
                if presentation_progress[0] > 0.005:
                    findings.error(
                        f"{label}: presentation progress starts at "
                        f"{presentation_progress[0]:.6f}, expected 0"
                    )
                if presentation_progress[-1] < 0.995:
                    findings.error(
                        f"{label}: presentation progress ends at "
                        f"{presentation_progress[-1]:.6f}, expected 1"
                    )
                if any(
                    right < left
                    for left, right in zip(
                        presentation_progress, presentation_progress[1:]
                    )
                ):
                    findings.error(f"{label}: presentation progress is not monotonic")
                progress_gaps = [
                    right - left
                    for left, right in zip(
                        presentation_progress, presentation_progress[1:]
                    )
                ]
                maximum_progress_gap = max(progress_gaps, default=0)
                if maximum_progress_gap > 0.200:
                    findings.error(
                        f"{label}: presentation evidence skips "
                        f"{maximum_progress_gap:.6f} of the animation; "
                        "maximum is 0.200000"
                    )
        unique_frames = len(set(pixel_hashes))
        minimum_unique = min(10, len(frames))
        if unique_frames < minimum_unique:
            findings.error(
                f"{label}: only {unique_frames} unique frames; expected at least "
                f"{minimum_unique}"
            )
        materialize_source_within_tolerance: bool | None = None
        if sequence.get("mode") == "materialize" and first_decoded is not None:
            reference_record = references.get(str(sequence.get("background")))
            if reference_record is not None:
                reference_path = artifact_path(
                    root, reference_record.get("file"), findings
                )
                if reference_path is not None:
                    try:
                        reference_crop = crop_rgba(decode_image(reference_path), crop)
                        control_diff = pixel_diff(reference_crop, first_decoded.rgba)
                        materialize_source_within_tolerance = (
                            source_diff_is_within_tolerance(
                                control_diff,
                                first_decoded.width * first_decoded.height,
                                tolerance,
                            )
                        )
                        if not materialize_source_within_tolerance:
                            findings.error(
                                f"{label}: pre-materialization source round-trip "
                                f"exceeds tolerance: {control_diff}"
                            )
                    except (KeyError, TypeError, ValueError) as error:
                        findings.error(
                            f"{label}: cannot validate materialize control: {error}"
                        )
            control_key = (
                str(sequence.get("background")),
                str(sequence.get("appearance")),
            )
            previous_hash = materialize_controls.setdefault(
                control_key, first_decoded.pixel_sha256
            )
            if first_decoded.pixel_sha256 != previous_hash:
                findings.error(
                    f"{label}: pre-materialization frame differs between materials"
                )
        interval = duration / (configured_frames - 1)
        maximum_error = max(timing_errors, default=0)
        timing_limit = max(0.050, interval * 3)
        if maximum_error > timing_limit:
            timing_basis = (
                "actualSeconds and presentationProgress"
                if manifest.get("schemaVersion") == 4
                else "actualSeconds"
            )
            findings.warn(
                f"{label}: worst timing error {maximum_error:.6f}s exceeds "
                f"{timing_limit:.6f}s; use {timing_basis} for fitting"
            )
        progress_gaps = [
            right - left
            for left, right in zip(presentation_progress, presentation_progress[1:])
        ]
        timing_reports.append(
            {
                "id": sequence_id,
                "targetFrames": configured_frames,
                "capturedFrames": len(frames),
                "droppedTargets": configured_frames - len(frames),
                "uniqueFrames": unique_frames,
                "timingErrorMedianSeconds": statistics.median(timing_errors)
                if timing_errors
                else 0,
                "timingErrorP95Seconds": percentile(timing_errors, 0.95),
                "timingErrorMaxSeconds": maximum_error,
                "actualStartSeconds": actual_times[0] if actual_times else None,
                "actualEndSeconds": actual_times[-1] if actual_times else None,
                "actualGapMedianSeconds": statistics.median(actual_gaps)
                if actual_gaps
                else 0,
                "actualGapP95Seconds": percentile(actual_gaps, 0.95),
                "actualGapMaxSeconds": maximum_actual_gap,
                "captureDurationMedianSeconds": statistics.median(capture_durations)
                if capture_durations
                else 0,
                "captureDurationP95Seconds": percentile(capture_durations, 0.95),
                "presentationProgressSamples": len(presentation_progress),
                "presentationProgressGapMax": max(progress_gaps, default=None),
                "materializeSourceWithinTolerance": materialize_source_within_tolerance,
            }
        )
    if manifest.get("requestedSuite") in {"dynamic", "all"}:
        expected_ids = {
            f"{mode}__{overlay}__{appearance}"
            for mode in (
                "materialize",
                "resize",
                "translate",
                "morph",
                "wallpaper-wipe",
            )
            for overlay in ("regular", "clear")
            for appearance in ("light", "dark")
        }
        missing = expected_ids - seen_ids
        unexpected = seen_ids - expected_ids
        if missing:
            findings.error(f"missing dynamic sequences: {sorted(missing)}")
        if unexpected:
            findings.error(f"unexpected dynamic sequences: {sorted(unexpected)}")
    return {"sequences": len(values), "frames": total_frames}, timing_reports


def validate_sweeps(
    root: Path,
    manifest: JsonObject,
    references: dict[str, JsonObject],
    findings: Findings,
) -> dict[str, int]:
    values = manifest.get("sweepSequences")
    if manifest.get("schemaVersion") == 3 and values is None:
        return {"sequences": 0, "frames": 0}
    if not isinstance(values, list):
        findings.error("sweepSequences is not a list")
        return {"sequences": 0, "frames": 0}

    expected_ids = {
        f"sweep__{mode}__{overlay}__{appearance}"
        for mode in ("resize", "translate", "morph", "wallpaper-wipe")
        for overlay in ("regular", "clear")
        for appearance in ("light", "dark")
    }
    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    total_frames = 0
    for sequence_index, value in enumerate(values):
        if not isinstance(value, dict):
            findings.error(f"sweepSequences[{sequence_index}] is not an object")
            continue
        sequence: JsonObject = value
        sequence_id = sequence.get("id")
        label = f"sweep {sequence_id!r}"
        if not isinstance(sequence_id, str) or sequence_id in seen_ids:
            findings.error(f"duplicate or invalid sweep id: {sequence_id!r}")
            continue
        seen_ids.add(sequence_id)
        expected_id = (
            f"sweep__{sequence.get('mode')}__{sequence.get('overlay')}"
            f"__{sequence.get('appearance')}"
        )
        if sequence_id != expected_id:
            findings.error(f"{label}: fields imply id {expected_id!r}")
        if sequence.get("background") not in references:
            findings.error(f"{label}: missing background reference")
        crop = sequence.get("cropPixels")
        frames = sequence.get("frames")
        if not isinstance(crop, dict):
            findings.error(f"{label}: missing cropPixels")
            continue
        if not isinstance(frames, list) or len(frames) != 17:
            count = len(frames) if isinstance(frames, list) else 0
            findings.error(f"{label}: has {count} frames; expected 17 exact states")
            continue

        total_frames += len(frames)
        pixel_hashes: list[str] = []
        progress_values: list[float] = []
        for frame_position, frame_value in enumerate(frames):
            if not isinstance(frame_value, dict):
                findings.error(f"{label}: frame[{frame_position}] is not an object")
                continue
            frame: JsonObject = frame_value
            frame_label = f"{label} frame[{frame_position}]"
            if frame.get("index") != frame_position:
                findings.error(
                    f"{frame_label}: index is {frame.get('index')!r}, "
                    f"expected {frame_position}"
                )
            expected_progress = frame_position / (len(frames) - 1)
            progress = frame.get("progress")
            if not isinstance(progress, (int, float)) or not math.isclose(
                progress, expected_progress, rel_tol=0, abs_tol=1e-12
            ):
                findings.error(
                    f"{frame_label}: progress is {progress!r}, "
                    f"expected {expected_progress}"
                )
            else:
                progress_values.append(float(progress))
            if frame.get("stable") is not True:
                findings.error(f"{frame_label}: pixels did not stabilize")
            samples = frame.get("stabilitySamples")
            if not isinstance(samples, int) or not 2 <= samples <= 4:
                findings.error(f"{frame_label}: invalid stabilitySamples {samples!r}")
            relative = frame.get("file")
            if isinstance(relative, str):
                if relative in seen_files:
                    findings.error(f"duplicate sweep frame path: {relative}")
                seen_files.add(relative)
            decoded = verify_image_record(
                root=root,
                record=frame,
                file_hash_key="fileSha256",
                label=frame_label,
                findings=findings,
            )
            if decoded is None:
                continue
            verify_image_metadata(
                record=frame,
                decoded=decoded,
                saved_key="savedImage",
                label=frame_label,
                findings=findings,
                require_source=True,
            )
            expected_size = (crop.get("width"), crop.get("height"))
            if (decoded.width, decoded.height) != expected_size:
                findings.error(
                    f"{frame_label}: dimensions disagree with crop {expected_size}"
                )
            pixel_hashes.append(decoded.pixel_sha256)

        if any(
            right <= left for left, right in zip(progress_values, progress_values[1:])
        ):
            findings.error(f"{label}: progress values are not strictly increasing")
        if len(set(pixel_hashes)) != len(frames):
            findings.error(
                f"{label}: only {len(set(pixel_hashes))}/{len(frames)} "
                "exact geometry states are unique"
            )

    if manifest.get("schemaVersion") == 4 and manifest.get("requestedSuite") in {
        "dynamic",
        "all",
    }:
        missing = expected_ids - seen_ids
        unexpected = seen_ids - expected_ids
        if missing:
            findings.error(f"missing sweep sequences: {sorted(missing)}")
        if unexpected:
            findings.error(f"unexpected sweep sequences: {sorted(unexpected)}")
    return {"sequences": len(values), "frames": total_frames}


def validate(root: Path) -> tuple[Findings, JsonObject]:
    findings = Findings()
    root = root.resolve()

    def unreadable_report() -> JsonObject:
        return {
            "schemaVersion": 2,
            "valid": False,
            "artifact": str(root),
            "summary": {
                "references": 0,
                "static": {"count": 0},
                "dynamic": {"sequences": 0, "frames": 0},
                "sweeps": {"sequences": 0, "frames": 0},
                "errors": len(findings.errors),
                "warnings": len(findings.warnings),
            },
            "errors": findings.errors,
            "warnings": findings.warnings,
        }

    manifest_path = root / "manifest.json"
    try:
        manifest_value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as error:
        findings.error(f"cannot read manifest.json: {error}")
        return findings, unreadable_report()
    if not isinstance(manifest_value, dict):
        findings.error("manifest root is not an object")
        return findings, unreadable_report()
    manifest: JsonObject = manifest_value

    validate_environment(manifest, findings)
    references = validate_references(root, manifest, findings)
    static_summary = validate_static(root, manifest, references, findings)
    dynamic_summary, timing = validate_dynamic(root, manifest, references, findings)
    sweep_summary = validate_sweeps(root, manifest, references, findings)

    requested = manifest.get("requestedSuite")
    if requested in {"static", "all"} and static_summary["count"] == 0:
        findings.error("requested static suite produced no captures")
    if requested in {"dynamic", "all"} and dynamic_summary["sequences"] == 0:
        findings.error("requested dynamic suite produced no sequences")
    if (
        manifest.get("schemaVersion") == 4
        and requested in {"dynamic", "all"}
        and sweep_summary["sequences"] == 0
    ):
        findings.error("requested dynamic suite produced no exact-state sweeps")

    report: JsonObject = {
        "schemaVersion": 2,
        "valid": not findings.errors,
        "artifact": str(root),
        "captureManifest": {
            "rigVersion": manifest.get("rigVersion"),
            "requestedSuite": requested,
            "osVersion": manifest.get("osVersion"),
            "osBuild": manifest.get("osBuild"),
            "architecture": manifest.get("architecture"),
            "ciCommit": manifest.get("ciCommit"),
        },
        "summary": {
            "references": len(references),
            "static": static_summary,
            "dynamic": dynamic_summary,
            "sweeps": sweep_summary,
            "errors": len(findings.errors),
            "warnings": len(findings.warnings),
        },
        "dynamicTiming": timing,
        "errors": findings.errors,
        "warnings": findings.warnings,
    }
    return findings, report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently validate a GlassCapture v2.1/v2.2 artifact."
    )
    parser.add_argument("artifact", type=Path, help="capture artifact directory")
    parser.add_argument("--report", type=Path, help="write a JSON validation report")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit nonzero if any validation error is found",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    findings, report = validate(args.artifact)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    summary = report.get("summary", {})
    print(
        f"references={summary.get('references', 0)} "
        f"static={summary.get('static', {}).get('count', 0)} "
        f"dynamic_sequences={summary.get('dynamic', {}).get('sequences', 0)} "
        f"dynamic_frames={summary.get('dynamic', {}).get('frames', 0)} "
        f"sweep_sequences={summary.get('sweeps', {}).get('sequences', 0)} "
        f"sweep_frames={summary.get('sweeps', {}).get('frames', 0)}"
    )
    for message in findings.warnings:
        print(f"warning: {message}", file=sys.stderr)
    for message in findings.errors:
        print(f"error: {message}", file=sys.stderr)
    print(
        "VALID" if not findings.errors else f"INVALID ({len(findings.errors)} errors)"
    )
    return 1 if args.strict and findings.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
