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

import numpy as np
from PIL import Image, ImageCms

from probe_catalog import (
    ADAPTIVE_SPATIAL_PROBES,
    CLEAR_AMPLITUDE_SWEEP_PROBES,
    CLEAR_FILTER_STAGE_PROBES,
    CLEAR_FIXED_BLOCK_SWEEP_PROBES,
    CLEAR_FIXED_IMPULSE_SWEEP_PROBES,
    CLEAR_GRID_BASIS_PROBES,
    CLEAR_KERNEL_PROBES,
    CLEAR_TOMOGRAPHY_PROBES,
    expected_adaptive_reference,
    expected_clear_amplitude_sweep_reference,
    expected_clear_filter_stage_reference,
    expected_clear_fixed_block_reference,
    expected_clear_fixed_impulse_reference,
    expected_clear_grid_basis_reference,
    expected_clear_kernel_reference,
    expected_clear_tomography_reference,
)


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
    # macOS exposes temporary directories through /var, which is a symlink to
    # /private/var.  Resolve both sides before the containment check so a safe
    # fixture below TemporaryDirectory is not mistaken for an escape.
    resolved_root = root.resolve()
    candidate = (resolved_root / relative).resolve()
    try:
        candidate.relative_to(resolved_root)
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


def rgba_excluding_regions(
    rgba: bytes,
    *,
    width: int,
    height: int,
    regions: list[JsonObject],
) -> bytes:
    """Return row-major RGBA pixels outside a small set of rectangles."""
    if not regions:
        return rgba
    chunks: list[bytes] = []
    row_bytes = width * 4
    for y in range(height):
        intervals = sorted(
            (
                max(0, int(region["x"])),
                min(width, int(region["x"]) + int(region["width"])),
            )
            for region in regions
            if int(region["y"]) <= y < int(region["y"]) + int(region["height"])
        )
        cursor = 0
        row_start = y * row_bytes
        for start, end in intervals:
            if end <= cursor:
                continue
            if start > cursor:
                chunks.append(rgba[row_start + cursor * 4 : row_start + start * 4])
            cursor = max(cursor, end)
        if cursor < width:
            chunks.append(rgba[row_start + cursor * 4 : row_start + row_bytes])
    return b"".join(chunks)


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
    if schema not in {3, 4, 5}:
        findings.error(f"schemaVersion is {schema!r}; validator supports 3, 4, and 5")
    expected_rigs = {
        3: {"2.1.0"},
        4: {"2.2.0", "2.3.0", "2.4.0", "2.5.0"},
        5: {
            "2.6.0",
            "2.7.0",
            "2.8.0",
            "2.9.0",
            "2.10.0",
            "2.11.0",
            "2.12.0",
            "2.13.0",
            "2.14.0",
            "2.15.0",
            "2.16.0",
            "2.17.0",
            "2.18.0",
            "2.19.0",
        },
    }.get(schema, set())
    if manifest.get("rigVersion") not in expected_rigs:
        findings.error(f"unexpected rigVersion: {manifest.get('rigVersion')!r}")
    if manifest.get("requestedSuite") not in {"static", "dynamic", "all"}:
        findings.error(f"invalid requestedSuite: {manifest.get('requestedSuite')!r}")
    if schema == 5:
        known_modes = {
            "materialize",
            "dematerialize",
            "resize",
            "translate",
            "morph",
            "wallpaper-wipe",
            "wallpaper-transition",
            "wallpaper-transition-reverse",
        }
        requested_modes = manifest.get("requestedDynamicModes")
        if (
            not isinstance(requested_modes, list)
            or not requested_modes
            or any(not isinstance(mode, str) for mode in requested_modes)
            or len(set(requested_modes)) != len(requested_modes)
            or not set(requested_modes) <= known_modes
        ):
            findings.error(f"invalid requestedDynamicModes: {requested_modes!r}")
        origin = manifest.get("transitionOriginNormalized")
        if (
            not isinstance(origin, list)
            or len(origin) != 2
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0 <= value <= 1
                for value in origin
            )
        ):
            findings.error(f"invalid transitionOriginNormalized: {origin!r}")
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
    if (
        manifest.get("rigVersion")
        in {
            "2.5.0",
            "2.6.0",
            "2.7.0",
            "2.8.0",
            "2.9.0",
            "2.10.0",
            "2.11.0",
            "2.12.0",
            "2.13.0",
            "2.14.0",
            "2.15.0",
            "2.16.0",
            "2.17.0",
            "2.18.0",
            "2.19.0",
        }
        and manifest.get("requestedSuite") != "static"
    ):
        clock = manifest.get("presentationClockPreflight")
        if not isinstance(clock, dict):
            findings.error("missing presentationClockPreflight evidence")
        else:
            if clock.get("backend") != "appkit-raster-monotonic":
                findings.error(
                    "presentationClockPreflight.backend is "
                    f"{clock.get('backend')!r}, expected "
                    "'appkit-raster-monotonic'"
                )
            expected_ranges = {
                "staticQuarterProgress": (0.20, 0.30),
                "staticThreeQuarterProgress": (0.70, 0.80),
                "liveMidpointProgress": (0.05, 0.95),
                "liveEndpointProgress": (0.995, 1.000_001),
            }
            for key, (lower, upper) in expected_ranges.items():
                value = clock.get(key)
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or not lower <= value < upper
                ):
                    findings.error(
                        f"presentationClockPreflight.{key} is {value!r}; "
                        f"expected {lower} <= value < {upper}"
                    )
            if "probePixelSize" in clock:
                probe_size = clock.get("probePixelSize")
                if (
                    not isinstance(probe_size, list)
                    or len(probe_size) != 2
                    or any(
                        not isinstance(value, int) or value <= 0
                        for value in probe_size
                    )
                ):
                    findings.error(
                        "presentationClockPreflight.probePixelSize is "
                        f"{probe_size!r}; expected two positive integers"
                    )
                probe_ranges = {
                    "probeStaticQuarterProgress": (0.20, 0.30),
                    "probeStaticThreeQuarterProgress": (0.70, 0.80),
                    "probeLiveMidpointProgress": (0.05, 0.95),
                    "probeLiveEndpointProgress": (0.995, 1.000_001),
                }
                for key, (lower, upper) in probe_ranges.items():
                    value = clock.get(key)
                    if (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(value)
                        or not lower <= value < upper
                    ):
                        findings.error(
                            f"presentationClockPreflight.{key} is "
                            f"{value!r}; expected {lower} <= value < "
                            f"{upper}"
                        )
    tolerance = manifest.get("sourceRoundTripTolerance")
    if not isinstance(tolerance, dict) or not source_diff_is_within_tolerance(
        (0, 0, 0.0), 1, tolerance
    ):
        findings.error(f"invalid sourceRoundTripTolerance: {tolerance!r}")
    scale = manifest.get("backingScaleFactor")
    if not isinstance(scale, (int, float)) or scale <= 0:
        findings.error(f"invalid backing scale: {scale!r}")


def full_geometry_matrix_scenes(
    manifest: JsonObject,
    scene_names: set[str],
) -> set[str]:
    scenes = scene_names - {"circle-0500-center"}
    if manifest.get("rigVersion") in {
        "2.14.0",
        "2.15.0",
        "2.16.0",
        "2.17.0",
        "2.18.0",
        "2.19.0",
    }:
        scenes -= {"rect-4000x6000-r000-center"}
    return scenes


def static_capture_requires_control(
    manifest: JsonObject,
    record: JsonObject,
) -> bool:
    """Recognize only explicitly cataloged reference-only fit captures."""
    if manifest.get("rigVersion") not in {
        "2.16.0",
        "2.17.0",
        "2.18.0",
        "2.19.0",
    }:
        return True
    background = record.get("background")
    grid_metadata = (
        CLEAR_GRID_BASIS_PROBES.get(background)
        if isinstance(background, str)
        else None
    )
    fixed_metadata = (
        CLEAR_FIXED_IMPULSE_SWEEP_PROBES.get(background)
        if (
            manifest.get("rigVersion") in {"2.18.0", "2.19.0"}
            and isinstance(background, str)
        )
        else None
    )
    block_metadata = (
        CLEAR_FIXED_BLOCK_SWEEP_PROBES.get(background)
        if (
            manifest.get("rigVersion") == "2.19.0"
            and isinstance(background, str)
        )
        else None
    )
    reference_only = (
        (
            grid_metadata is not None
            and grid_metadata["sourceControl"] is False
        )
        or (
            fixed_metadata is not None
            and fixed_metadata["sourceControl"] is False
        )
        or (
            block_metadata is not None
            and block_metadata["sourceControl"] is False
        )
    )
    return not (
        reference_only
        and record.get("scene") == "circle-4000-center"
        and record.get("overlay") == "clear"
        and record.get("appearance") == "dark"
    )


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
        expected_control_file = None
        if static_capture_requires_control(manifest, record):
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
        if not static_capture_requires_control(manifest, value):
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
        if manifest.get("rigVersion") in {
            "2.8.0",
            "2.9.0",
            "2.10.0",
            "2.11.0",
            "2.12.0",
            "2.13.0",
            "2.14.0",
            "2.15.0",
            "2.16.0",
            "2.17.0",
            "2.18.0",
            "2.19.0",
        }:
            required_v28_backgrounds = {
                "color-cube-9-permuted",
                "color-cube-holdout-8",
            }
            missing_v28_backgrounds = required_v28_backgrounds - static_backgrounds
            if missing_v28_backgrounds:
                findings.error(
                    "v2.8 static references are missing "
                    f"{sorted(missing_v28_backgrounds)}"
                )
        if manifest.get("rigVersion") in {
            "2.9.0",
            "2.10.0",
            "2.11.0",
            "2.12.0",
            "2.13.0",
            "2.14.0",
            "2.15.0",
            "2.16.0",
            "2.17.0",
            "2.18.0",
            "2.19.0",
        }:
            required_v29_backgrounds = {
                "color-cube-9-shuffled",
                "color-cube-holdout-8-shuffled",
            }
            missing_v29_backgrounds = required_v29_backgrounds - static_backgrounds
            if missing_v29_backgrounds:
                findings.error(
                    "v2.9 static references are missing "
                    f"{sorted(missing_v29_backgrounds)}"
                )
        if manifest.get("rigVersion") in {
            "2.10.0",
            "2.11.0",
            "2.12.0",
            "2.13.0",
            "2.14.0",
            "2.15.0",
            "2.16.0",
            "2.17.0",
            "2.18.0",
            "2.19.0",
        }:
            required_v210_backgrounds = {
                *{f"color-cube-9-context-train-{index:02d}" for index in range(4)},
                *{
                    f"color-cube-holdout-8-context-train-{index:02d}"
                    for index in range(4)
                },
                *{
                    f"noise-{channel}-a{amplitude:03d}-{role}"
                    for channel in ("gray", "rgb")
                    for amplitude in (16, 64)
                    for role in ("train", "holdout")
                },
            }
            missing_v210_backgrounds = required_v210_backgrounds - static_backgrounds
            if missing_v210_backgrounds:
                findings.error(
                    "v2.10 static references are missing "
                    f"{sorted(missing_v210_backgrounds)}"
                )
        if manifest.get("rigVersion") in {
            "2.11.0",
            "2.12.0",
            "2.13.0",
            "2.14.0",
            "2.15.0",
            "2.16.0",
            "2.17.0",
            "2.18.0",
            "2.19.0",
        }:
            required_v211_backgrounds = set(ADAPTIVE_SPATIAL_PROBES)
            missing_v211_backgrounds = required_v211_backgrounds - static_backgrounds
            if missing_v211_backgrounds:
                findings.error(
                    "v2.11+ adaptive static references are missing "
                    f"{sorted(missing_v211_backgrounds)}"
                )
            for background in sorted(required_v211_backgrounds & static_backgrounds):
                reference = references[background]
                path = artifact_path(root, reference.get("file"), findings)
                if path is None:
                    continue
                try:
                    decoded = decode_image(path)
                    expected = expected_adaptive_reference(
                        background,
                        width=decoded.width,
                        height=decoded.height,
                    )
                    actual = np.frombuffer(
                        decoded.rgba,
                        dtype=np.uint8,
                    ).reshape(decoded.height, decoded.width, 4)[:, :, :3]
                except Exception as error:
                    findings.error(
                        f"{background}: cannot verify v2.11+ probe generator: {error}"
                    )
                    continue
                if not np.array_equal(expected, actual):
                    delta = np.abs(expected.astype(np.int16) - actual.astype(np.int16))
                    changed = np.any(delta != 0, axis=2)
                    findings.error(
                        f"{background}: archived reference does not match "
                        "the v2.11+ deterministic generator "
                        f"({np.count_nonzero(changed)} changed pixels, "
                        f"maximum channel delta {delta.max(initial=0)})"
                    )
        if manifest.get("rigVersion") in {
            "2.13.0",
            "2.14.0",
            "2.15.0",
            "2.16.0",
            "2.17.0",
            "2.18.0",
            "2.19.0",
        }:
            required_v213_backgrounds = set(CLEAR_KERNEL_PROBES)
            missing_v213_backgrounds = required_v213_backgrounds - static_backgrounds
            if missing_v213_backgrounds:
                findings.error(
                    "v2.13 clear-kernel references are missing "
                    f"{sorted(missing_v213_backgrounds)}"
                )
            for background in sorted(required_v213_backgrounds & static_backgrounds):
                reference = references[background]
                path = artifact_path(root, reference.get("file"), findings)
                if path is None:
                    continue
                try:
                    decoded = decode_image(path)
                    expected = expected_clear_kernel_reference(
                        background,
                        width=decoded.width,
                        height=decoded.height,
                    )
                    actual = np.frombuffer(
                        decoded.rgba,
                        dtype=np.uint8,
                    ).reshape(decoded.height, decoded.width, 4)[:, :, :3]
                except Exception as error:
                    findings.error(
                        f"{background}: cannot verify v2.13 probe generator: {error}"
                    )
                    continue
                if not np.array_equal(expected, actual):
                    delta = np.abs(expected.astype(np.int16) - actual.astype(np.int16))
                    changed = np.any(delta != 0, axis=2)
                    findings.error(
                        f"{background}: archived reference does not match "
                        "the v2.13 deterministic generator "
                        f"({np.count_nonzero(changed)} changed pixels, "
                        f"maximum channel delta {delta.max(initial=0)})"
                    )
        if manifest.get("rigVersion") in {
            "2.14.0",
            "2.15.0",
            "2.16.0",
            "2.17.0",
            "2.18.0",
            "2.19.0",
        }:
            required_v214_backgrounds = set(CLEAR_TOMOGRAPHY_PROBES)
            missing_v214_backgrounds = required_v214_backgrounds - static_backgrounds
            if missing_v214_backgrounds:
                findings.error(
                    "v2.14 amplitude-tomography references are missing "
                    f"{sorted(missing_v214_backgrounds)}"
                )
            for background in sorted(required_v214_backgrounds & static_backgrounds):
                reference = references[background]
                path = artifact_path(root, reference.get("file"), findings)
                if path is None:
                    continue
                try:
                    decoded = decode_image(path)
                    expected = expected_clear_tomography_reference(
                        background,
                        width=decoded.width,
                        height=decoded.height,
                    )
                    actual = np.frombuffer(
                        decoded.rgba,
                        dtype=np.uint8,
                    ).reshape(decoded.height, decoded.width, 4)[:, :, :3]
                except Exception as error:
                    findings.error(
                        f"{background}: cannot verify v2.14 probe generator: {error}"
                    )
                    continue
                if not np.array_equal(expected, actual):
                    delta = np.abs(
                        expected.astype(np.int16) - actual.astype(np.int16)
                    )
                    changed = np.any(delta != 0, axis=2)
                    findings.error(
                        f"{background}: archived reference does not match "
                        "the v2.14 deterministic generator "
                        f"({np.count_nonzero(changed)} changed pixels, "
                        f"maximum channel delta {delta.max(initial=0)})"
                    )
        if manifest.get("rigVersion") in {
            "2.15.0",
            "2.16.0",
            "2.17.0",
            "2.18.0",
            "2.19.0",
        }:
            required_v215_backgrounds = set(CLEAR_AMPLITUDE_SWEEP_PROBES)
            missing_v215_backgrounds = (
                required_v215_backgrounds - static_backgrounds
            )
            if missing_v215_backgrounds:
                findings.error(
                    "v2.15 dense-amplitude references are missing "
                    f"{sorted(missing_v215_backgrounds)}"
                )
            for background in sorted(
                required_v215_backgrounds & static_backgrounds
            ):
                reference = references[background]
                path = artifact_path(root, reference.get("file"), findings)
                if path is None:
                    continue
                try:
                    decoded = decode_image(path)
                    expected = expected_clear_amplitude_sweep_reference(
                        background,
                        width=decoded.width,
                        height=decoded.height,
                    )
                    actual = np.frombuffer(
                        decoded.rgba,
                        dtype=np.uint8,
                    ).reshape(decoded.height, decoded.width, 4)[:, :, :3]
                except Exception as error:
                    findings.error(
                        f"{background}: cannot verify v2.15 probe generator: "
                        f"{error}"
                    )
                    continue
                if not np.array_equal(expected, actual):
                    delta = np.abs(
                        expected.astype(np.int16) - actual.astype(np.int16)
                    )
                    changed = np.any(delta != 0, axis=2)
                    findings.error(
                        f"{background}: archived reference does not match "
                        "the v2.15 deterministic generator "
                        f"({np.count_nonzero(changed)} changed pixels, "
                        f"maximum channel delta {delta.max(initial=0)})"
                    )
        if manifest.get("rigVersion") in {
            "2.16.0",
            "2.17.0",
            "2.18.0",
            "2.19.0",
        }:
            required_v216_backgrounds = set(CLEAR_GRID_BASIS_PROBES)
            missing_v216_backgrounds = (
                required_v216_backgrounds - static_backgrounds
            )
            if missing_v216_backgrounds:
                findings.error(
                    "v2.16 clear-grid-basis references are missing "
                    f"{sorted(missing_v216_backgrounds)}"
                )
            for background in sorted(
                required_v216_backgrounds & static_backgrounds
            ):
                reference = references[background]
                path = artifact_path(root, reference.get("file"), findings)
                if path is None:
                    continue
                try:
                    decoded = decode_image(path)
                    expected = expected_clear_grid_basis_reference(
                        background,
                        width=decoded.width,
                        height=decoded.height,
                    )
                    actual = np.frombuffer(
                        decoded.rgba,
                        dtype=np.uint8,
                    ).reshape(decoded.height, decoded.width, 4)[:, :, :3]
                except Exception as error:
                    findings.error(
                        f"{background}: cannot verify v2.16 probe generator: "
                        f"{error}"
                    )
                    continue
                if not np.array_equal(expected, actual):
                    delta = np.abs(
                        expected.astype(np.int16) - actual.astype(np.int16)
                    )
                    changed = np.any(delta != 0, axis=2)
                    findings.error(
                        f"{background}: archived reference does not match "
                        "the v2.16 deterministic generator "
                        f"({np.count_nonzero(changed)} changed pixels, "
                        f"maximum channel delta {delta.max(initial=0)})"
                    )
        if manifest.get("rigVersion") in {
            "2.17.0",
            "2.18.0",
            "2.19.0",
        }:
            required_v217_backgrounds = set(CLEAR_FILTER_STAGE_PROBES)
            missing_v217_backgrounds = (
                required_v217_backgrounds - static_backgrounds
            )
            if missing_v217_backgrounds:
                findings.error(
                    "v2.17 clear-filter-stage references are missing "
                    f"{sorted(missing_v217_backgrounds)}"
                )
            for background in sorted(
                required_v217_backgrounds & static_backgrounds
            ):
                reference = references[background]
                path = artifact_path(root, reference.get("file"), findings)
                if path is None:
                    continue
                try:
                    decoded = decode_image(path)
                    expected = expected_clear_filter_stage_reference(
                        background,
                        width=decoded.width,
                        height=decoded.height,
                    )
                    actual = np.frombuffer(
                        decoded.rgba,
                        dtype=np.uint8,
                    ).reshape(decoded.height, decoded.width, 4)[:, :, :3]
                except Exception as error:
                    findings.error(
                        f"{background}: cannot verify v2.17 probe generator: "
                        f"{error}"
                    )
                    continue
                if not np.array_equal(expected, actual):
                    delta = np.abs(
                        expected.astype(np.int16) - actual.astype(np.int16)
                    )
                    changed = np.any(delta != 0, axis=2)
                    findings.error(
                        f"{background}: archived reference does not match "
                        "the v2.17 deterministic generator "
                        f"({np.count_nonzero(changed)} changed pixels, "
                        f"maximum channel delta {delta.max(initial=0)})"
                    )
        if manifest.get("rigVersion") in {"2.18.0", "2.19.0"}:
            required_v218_backgrounds = set(CLEAR_FIXED_IMPULSE_SWEEP_PROBES)
            missing_v218_backgrounds = (
                required_v218_backgrounds - static_backgrounds
            )
            if missing_v218_backgrounds:
                findings.error(
                    "v2.18 fixed-impulse references are missing "
                    f"{sorted(missing_v218_backgrounds)}"
                )
            for background in sorted(
                required_v218_backgrounds & static_backgrounds
            ):
                reference = references[background]
                path = artifact_path(root, reference.get("file"), findings)
                if path is None:
                    continue
                try:
                    decoded = decode_image(path)
                    expected = expected_clear_fixed_impulse_reference(
                        background,
                        width=decoded.width,
                        height=decoded.height,
                    )
                    actual = np.frombuffer(
                        decoded.rgba,
                        dtype=np.uint8,
                    ).reshape(decoded.height, decoded.width, 4)[:, :, :3]
                except Exception as error:
                    findings.error(
                        f"{background}: cannot verify v2.18 probe generator: "
                        f"{error}"
                    )
                    continue
                if not np.array_equal(expected, actual):
                    delta = np.abs(
                        expected.astype(np.int16) - actual.astype(np.int16)
                    )
                    changed = np.any(delta != 0, axis=2)
                    findings.error(
                        f"{background}: archived reference does not match "
                        "the v2.18 deterministic generator "
                        f"({np.count_nonzero(changed)} changed pixels, "
                        f"maximum channel delta {delta.max(initial=0)})"
                    )
        if manifest.get("rigVersion") == "2.19.0":
            required_v219_backgrounds = set(CLEAR_FIXED_BLOCK_SWEEP_PROBES)
            missing_v219_backgrounds = (
                required_v219_backgrounds - static_backgrounds
            )
            if missing_v219_backgrounds:
                findings.error(
                    "v2.19 fixed-block references are missing "
                    f"{sorted(missing_v219_backgrounds)}"
                )
            for background in sorted(
                required_v219_backgrounds & static_backgrounds
            ):
                reference = references[background]
                path = artifact_path(root, reference.get("file"), findings)
                if path is None:
                    continue
                try:
                    decoded = decode_image(path)
                    expected = expected_clear_fixed_block_reference(
                        background,
                        width=decoded.width,
                        height=decoded.height,
                    )
                    actual = np.frombuffer(
                        decoded.rgba,
                        dtype=np.uint8,
                    ).reshape(decoded.height, decoded.width, 4)[:, :, :3]
                except Exception as error:
                    findings.error(
                        f"{background}: cannot verify v2.19 probe generator: "
                        f"{error}"
                    )
                    continue
                if not np.array_equal(expected, actual):
                    delta = np.abs(
                        expected.astype(np.int16) - actual.astype(np.int16)
                    )
                    changed = np.any(delta != 0, axis=2)
                    findings.error(
                        f"{background}: archived reference does not match "
                        "the v2.19 deterministic generator "
                        f"({np.count_nonzero(changed)} changed pixels, "
                        f"maximum channel delta {delta.max(initial=0)})"
                    )
        appearances = {"light", "dark"}
        base_matrix_backgrounds = static_backgrounds
        if manifest.get("rigVersion") in {
            "2.14.0",
            "2.15.0",
            "2.16.0",
            "2.17.0",
            "2.18.0",
            "2.19.0",
        }:
            base_matrix_backgrounds = (
                static_backgrounds
                - set(CLEAR_TOMOGRAPHY_PROBES)
                - set(CLEAR_AMPLITUDE_SWEEP_PROBES)
                - set(CLEAR_GRID_BASIS_PROBES)
                - set(CLEAR_FILTER_STAGE_PROBES)
                - set(CLEAR_FIXED_IMPULSE_SWEEP_PROBES)
                - set(CLEAR_FIXED_BLOCK_SWEEP_PROBES)
            )
        expected_cases = {
            (background, "circle-0500-center", overlay, appearance)
            for background in base_matrix_backgrounds
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
            for scene in full_geometry_matrix_scenes(manifest, scene_names)
            for overlay in ("regular", "clear")
            for appearance in appearances
        }
        if manifest.get("schemaVersion") in {4, 5}:
            dense_transfer_backgrounds = {"ramp-x", "ramp-y", "color-cube-9"}
            if manifest.get("rigVersion") in {
                "2.8.0",
                "2.9.0",
                "2.10.0",
                "2.11.0",
                "2.12.0",
                "2.13.0",
                "2.14.0",
                "2.15.0",
                "2.16.0",
                "2.17.0",
                "2.18.0",
                "2.19.0",
            }:
                dense_transfer_backgrounds |= {
                    "color-cube-9-permuted",
                    "color-cube-holdout-8",
                }
            if manifest.get("rigVersion") in {
                "2.9.0",
                "2.10.0",
                "2.11.0",
                "2.12.0",
                "2.13.0",
                "2.14.0",
                "2.15.0",
                "2.16.0",
                "2.17.0",
                "2.18.0",
                "2.19.0",
            }:
                dense_transfer_backgrounds |= {
                    "color-cube-9-shuffled",
                    "color-cube-holdout-8-shuffled",
                }
            if manifest.get("rigVersion") in {
                "2.10.0",
                "2.11.0",
                "2.12.0",
                "2.13.0",
                "2.14.0",
                "2.15.0",
                "2.16.0",
                "2.17.0",
                "2.18.0",
                "2.19.0",
            }:
                dense_transfer_backgrounds |= {
                    *{f"color-cube-9-context-train-{index:02d}" for index in range(4)},
                    *{
                        f"color-cube-holdout-8-context-train-{index:02d}"
                        for index in range(4)
                    },
                }
            expected_cases |= {
                (background, "circle-4000-center", overlay, appearance)
                for background in dense_transfer_backgrounds & static_backgrounds
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
            if manifest.get("rigVersion") in {
                "2.9.0",
                "2.10.0",
                "2.11.0",
                "2.12.0",
                "2.13.0",
                "2.14.0",
                "2.15.0",
                "2.16.0",
                "2.17.0",
                "2.18.0",
                "2.19.0",
            }:
                expected_cases |= {
                    (
                        background,
                        "circle-4000-center",
                        "regular",
                        appearance,
                    )
                    for background in {
                        f"sine-{axis}-p{period:04d}-ph{phase}"
                        for axis in ("x", "y")
                        for period in (32, 128, 512)
                        for phase in range(4)
                    }
                    & static_backgrounds
                    for appearance in appearances
                }
                if manifest.get("rigVersion") in {
                    "2.10.0",
                    "2.11.0",
                    "2.12.0",
                    "2.13.0",
                    "2.14.0",
                    "2.15.0",
                    "2.16.0",
                    "2.17.0",
                    "2.18.0",
                    "2.19.0",
                }:
                    expected_cases |= {
                        (
                            background,
                            "circle-4000-center",
                            "regular",
                            appearance,
                        )
                        for background in {
                            f"noise-{channel}-a{amplitude:03d}-{role}"
                            for channel in ("gray", "rgb")
                            for amplitude in (16, 64)
                            for role in ("train", "holdout")
                        }
                        & static_backgrounds
                        for appearance in appearances
                    }
                if manifest.get("rigVersion") in {
                    "2.11.0",
                    "2.12.0",
                    "2.13.0",
                    "2.14.0",
                    "2.15.0",
                    "2.16.0",
                    "2.17.0",
                    "2.18.0",
                    "2.19.0",
                }:
                    expected_cases |= {
                        (
                            background,
                            "circle-4000-center",
                            overlay,
                            appearance,
                        )
                        for background in set(ADAPTIVE_SPATIAL_PROBES)
                        & static_backgrounds
                        for overlay in ("regular", "clear")
                        for appearance in appearances
                    }
                expected_cases |= {
                    (
                        background,
                        "circle-4000-center",
                        "regular",
                        appearance,
                    )
                    for background in {
                        "edge-x",
                        "edge-y",
                        "edge-slant",
                        "line-x",
                        "line-y",
                        "noise-gray",
                        "checker-0032",
                        "checker-0064",
                        "checker-0256",
                        "checker-0512",
                    }
                    & static_backgrounds
                    for appearance in appearances
                }
                if manifest.get("rigVersion") in {
                    "2.12.0",
                    "2.13.0",
                    "2.14.0",
                    "2.15.0",
                    "2.16.0",
                    "2.17.0",
                    "2.18.0",
                    "2.19.0",
                }:
                    clear_giant_identification_backgrounds = {
                        *{
                            f"sine-{axis}-p{period:04d}-ph{phase}"
                            for axis in ("x", "y")
                            for period in (32, 128, 512)
                            for phase in range(4)
                        },
                        "edge-x",
                        "edge-y",
                        "edge-slant",
                        "line-x",
                        "line-y",
                        "noise-gray",
                        "checker-0032",
                        "checker-0064",
                        "checker-0256",
                        "checker-0512",
                        *{
                            f"noise-{channel}-a{amplitude:03d}-{role}"
                            for channel in ("gray", "rgb")
                            for amplitude in (16, 64)
                            for role in ("train", "holdout")
                        },
                    }
                    expected_cases |= {
                        (
                            background,
                            "circle-4000-center",
                            "clear",
                            appearance,
                        )
                        for background in clear_giant_identification_backgrounds
                        & static_backgrounds
                        for appearance in appearances
                    }
            if manifest.get("rigVersion") in {
                "2.13.0",
                "2.14.0",
                "2.15.0",
                "2.16.0",
                "2.17.0",
                "2.18.0",
                "2.19.0",
            }:
                clear_kernel_scenes = {
                    "circle-4000-center",
                    "circle-6000-upper-left",
                    "rect-6000x4000-r000-center",
                }
                missing_clear_kernel_scenes = clear_kernel_scenes - scene_names
                if missing_clear_kernel_scenes:
                    findings.error(
                        "v2.13 clear-kernel scenes are missing "
                        f"{sorted(missing_clear_kernel_scenes)}"
                    )
                expected_cases |= {
                    (background, scene, "clear", appearance)
                    for background in set(CLEAR_KERNEL_PROBES) & static_backgrounds
                    for scene in clear_kernel_scenes
                    for appearance in appearances
                }
                expected_cases |= {
                    (background, scene, "clear", appearance)
                    for background in {
                        "noise-rgb-a064-train",
                        "noise-rgb-a064-holdout",
                    }
                    & static_backgrounds
                    for scene in {
                        "circle-6000-upper-left",
                        "rect-6000x4000-r000-center",
                    }
                    for appearance in appearances
                }
            if manifest.get("rigVersion") in {
                "2.14.0",
                "2.15.0",
                "2.16.0",
                "2.17.0",
                "2.18.0",
                "2.19.0",
            }:
                tomography_scenes = {
                    "circle-4000-center",
                    "circle-6000-upper-left",
                    "rect-6000x4000-r000-center",
                    "rect-4000x6000-r000-center",
                }
                missing_tomography_scenes = tomography_scenes - scene_names
                if missing_tomography_scenes:
                    findings.error(
                        "v2.14 tomography scenes are missing "
                        f"{sorted(missing_tomography_scenes)}"
                    )
                expected_cases |= {
                    (
                        background,
                        "circle-0500-center",
                        "none",
                        "dark",
                    )
                    for background in set(CLEAR_TOMOGRAPHY_PROBES)
                    & static_backgrounds
                }
                expected_cases |= {
                    (background, scene, "clear", "dark")
                    for background in set(CLEAR_TOMOGRAPHY_PROBES)
                    & static_backgrounds
                    for scene in tomography_scenes
                }
                expected_cases |= {
                    (
                        background,
                        "rect-4000x6000-r000-center",
                        "clear",
                        "dark",
                    )
                    for background in set(CLEAR_KERNEL_PROBES)
                    & static_backgrounds
                }
                if "gray-128" in static_backgrounds:
                    expected_cases.add(
                        (
                            "gray-128",
                            "rect-4000x6000-r000-center",
                            "clear",
                            "dark",
                        )
                    )
            if manifest.get("rigVersion") in {
                "2.15.0",
                "2.16.0",
                "2.17.0",
                "2.18.0",
                "2.19.0",
            }:
                sweep_backgrounds = (
                    set(CLEAR_AMPLITUDE_SWEEP_PROBES) & static_backgrounds
                )
                expected_cases |= {
                    (
                        background,
                        "circle-0500-center",
                        "none",
                        "dark",
                    )
                    for background in sweep_backgrounds
                }
                expected_cases |= {
                    (background, scene, "clear", "dark")
                    for background in sweep_backgrounds
                    for scene in CLEAR_AMPLITUDE_SWEEP_PROBES[background][
                        "scenes"
                    ]
                }
            if manifest.get("rigVersion") in {
                "2.16.0",
                "2.17.0",
                "2.18.0",
                "2.19.0",
            }:
                grid_basis_backgrounds = (
                    set(CLEAR_GRID_BASIS_PROBES) & static_backgrounds
                )
                expected_cases |= {
                    (
                        background,
                        "circle-0500-center",
                        "none",
                        "dark",
                    )
                    for background in grid_basis_backgrounds
                    if CLEAR_GRID_BASIS_PROBES[background]["sourceControl"]
                }
                expected_cases |= {
                    (
                        background,
                        "circle-4000-center",
                        "clear",
                        "dark",
                    )
                    for background in grid_basis_backgrounds
                }
            if manifest.get("rigVersion") in {
                "2.17.0",
                "2.18.0",
                "2.19.0",
            }:
                filter_stage_backgrounds = (
                    set(CLEAR_FILTER_STAGE_PROBES) & static_backgrounds
                )
                expected_cases |= {
                    (
                        background,
                        "circle-0500-center",
                        "none",
                        "dark",
                    )
                    for background in filter_stage_backgrounds
                }
                expected_cases |= {
                    (
                        background,
                        "circle-4000-center",
                        "clear",
                        "dark",
                    )
                    for background in filter_stage_backgrounds
                }
            if manifest.get("rigVersion") in {"2.18.0", "2.19.0"}:
                fixed_impulse_backgrounds = (
                    set(CLEAR_FIXED_IMPULSE_SWEEP_PROBES)
                    & static_backgrounds
                )
                expected_cases |= {
                    (
                        background,
                        "circle-0500-center",
                        "none",
                        "dark",
                    )
                    for background in fixed_impulse_backgrounds
                    if CLEAR_FIXED_IMPULSE_SWEEP_PROBES[background][
                        "sourceControl"
                    ]
                }
                expected_cases |= {
                    (
                        background,
                        "circle-4000-center",
                        "clear",
                        "dark",
                    )
                    for background in fixed_impulse_backgrounds
                }
            if manifest.get("rigVersion") == "2.19.0":
                fixed_block_backgrounds = (
                    set(CLEAR_FIXED_BLOCK_SWEEP_PROBES)
                    & static_backgrounds
                )
                expected_cases |= {
                    (
                        background,
                        "circle-0500-center",
                        "none",
                        "dark",
                    )
                    for background in fixed_block_backgrounds
                    if CLEAR_FIXED_BLOCK_SWEEP_PROBES[background][
                        "sourceControl"
                    ]
                }
                expected_cases |= {
                    (
                        background,
                        "circle-4000-center",
                        "clear",
                        "dark",
                    )
                    for background in fixed_block_backgrounds
                }
        if manifest.get("rigVersion") in {
            "2.7.0",
            "2.8.0",
            "2.9.0",
            "2.10.0",
            "2.11.0",
            "2.12.0",
            "2.13.0",
            "2.14.0",
            "2.15.0",
            "2.16.0",
            "2.17.0",
            "2.18.0",
            "2.19.0",
        }:
            expected_cases |= {
                (background, scene, overlay, appearance)
                for background in {
                    f"sine-{axis}-p0256-ph{phase}"
                    for axis in ("x", "y")
                    for phase in range(4)
                }
                & static_backgrounds
                for scene in {
                    "circle-0500-upper-left",
                    "circle-0500-upper-right",
                    "circle-0500-lower-left",
                    "circle-0500-lower-right",
                }
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
    materialize_controls: dict[tuple[str, str, str], str] = {}
    timing_reports: list[JsonObject] = []
    total_frames = 0
    total_post_settle_frames = 0
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
        if manifest.get("rigVersion") in {
            "2.3.0",
            "2.4.0",
            "2.5.0",
            "2.6.0",
            "2.7.0",
            "2.8.0",
            "2.9.0",
            "2.10.0",
            "2.11.0",
            "2.12.0",
            "2.13.0",
            "2.14.0",
            "2.15.0",
            "2.16.0",
            "2.17.0",
            "2.18.0",
            "2.19.0",
        }:
            sampling_method = sequence.get("samplingMethod")
            if sampling_method not in {
                "continuous-off-main-presentation-binned",
                "continuous-bounded-clock-full-frame-verified",
            }:
                findings.error(f"{label}: unexpected dynamic sampling method")
            attempts = sequence.get("captureAttempts")
            decoded_samples = sequence.get("decodedSamples")
            transient_failures = sequence.get("transientFailures")
            if (
                not isinstance(attempts, int)
                or not isinstance(decoded_samples, int)
                or not isinstance(transient_failures, int)
                or min(attempts, decoded_samples, transient_failures) < 0
                or attempts != decoded_samples + transient_failures
            ):
                findings.error(f"{label}: inconsistent dynamic sampler counters")
            if (
                sampling_method
                == "continuous-bounded-clock-full-frame-verified"
            ):
                clock_surface = sequence.get("clockProbeSurface")
                bounded_probes = sequence.get("boundedClockProbes")
                full_captures = sequence.get("fullFrameCaptures")
                full_decodes = sequence.get("fullFrameClockDecodes")
                retained_live_frames = max(
                    0,
                    len(sequence.get("frames", [])) - 1,
                )
                if clock_surface not in {
                    "dedicated-clock-window",
                    "full-window-fallback",
                }:
                    findings.error(
                        f"{label}: invalid bounded clock-probe surface"
                    )
                if (
                    not isinstance(bounded_probes, int)
                    or not isinstance(full_captures, int)
                    or not isinstance(full_decodes, int)
                    or min(
                        bounded_probes,
                        full_captures,
                        full_decodes,
                    ) < 0
                    or not isinstance(attempts, int)
                    or bounded_probes > attempts
                    or full_decodes > full_captures
                    or full_decodes < retained_live_frames
                ):
                    findings.error(
                        f"{label}: inconsistent bounded clock/full-frame "
                        "verification counters"
                    )
        if manifest.get("rigVersion") in {
            "2.4.0",
            "2.5.0",
            "2.6.0",
            "2.7.0",
            "2.8.0",
            "2.9.0",
            "2.10.0",
            "2.11.0",
            "2.12.0",
            "2.13.0",
            "2.14.0",
            "2.15.0",
            "2.16.0",
            "2.17.0",
            "2.18.0",
            "2.19.0",
        }:
            expected_clock = "swiftui-animatable-frame"
            if sequence.get("mode") in {
                "materialize",
                "dematerialize",
                "wallpaper-transition",
                "wallpaper-transition-reverse",
            }:
                expected_clock = (
                    "core-animation-layer"
                    if manifest.get("rigVersion") == "2.4.0"
                    else "appkit-raster-monotonic"
                )
            if sequence.get("presentationClock") != expected_clock:
                findings.error(
                    f"{label}: presentationClock is "
                    f"{sequence.get('presentationClock')!r}, "
                    f"expected {expected_clock!r}"
                )
        if manifest.get("schemaVersion") == 5:
            mode = sequence.get("mode")
            outgoing = sequence.get("outgoingBackground")
            incoming = sequence.get("incomingBackground")
            if outgoing != sequence.get("background") or outgoing not in references:
                findings.error(f"{label}: invalid outgoingBackground {outgoing!r}")
            expected_sources = {
                "wallpaper-transition": (
                    "dynamic-coded-field",
                    "dynamic-coded-field-incoming",
                ),
                "wallpaper-transition-reverse": (
                    "dynamic-coded-field-incoming",
                    "dynamic-coded-field",
                ),
            }
            expected_outgoing, expected_incoming = expected_sources.get(
                str(mode), ("dynamic-coded-field", None)
            )
            if outgoing != expected_outgoing:
                findings.error(
                    f"{label}: outgoingBackground is {outgoing!r}, "
                    f"expected {expected_outgoing!r}"
                )
            if incoming != expected_incoming:
                findings.error(
                    f"{label}: incomingBackground is {incoming!r}, "
                    f"expected {expected_incoming!r}"
                )
            if isinstance(incoming, str) and incoming not in references:
                findings.error(f"{label}: missing incoming background reference")
            expected_role = {
                "materialize": "material-topology-response",
                "dematerialize": "material-topology-response",
                "resize": "geometry-system-identification",
                "translate": "geometry-system-identification",
                "morph": "geometry-system-identification",
                "wallpaper-wipe": "single-source-expansion-control",
                "wallpaper-transition": "walle-two-wallpaper-reference",
                "wallpaper-transition-reverse": "walle-two-wallpaper-reference",
            }.get(str(mode))
            if sequence.get("probeRole") != expected_role:
                findings.error(
                    f"{label}: probeRole is {sequence.get('probeRole')!r}, "
                    f"expected {expected_role!r}"
                )
            if (
                sequence.get("stateIsolation")
                != "fresh-swiftui-dynamic-subtree-per-sequence"
            ):
                findings.error(f"{label}: missing fresh subtree isolation")
            expected_schedule = (
                {
                    "expansionEnd": 0.62,
                    "dematerializeStart": 0.66,
                    "dematerializeEnd": 1.0,
                }
                if mode in {"wallpaper-transition", "wallpaper-transition-reverse"}
                else {"end": 1.0}
            )
            if sequence.get("phaseSchedule") != expected_schedule:
                findings.error(
                    f"{label}: phaseSchedule is {sequence.get('phaseSchedule')!r}, "
                    f"expected {expected_schedule!r}"
                )
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
        if (
            manifest.get("rigVersion")
            in {
                "2.3.0",
                "2.4.0",
                "2.5.0",
                "2.6.0",
                "2.7.0",
                "2.8.0",
                "2.9.0",
                "2.10.0",
                "2.11.0",
                "2.12.0",
                "2.13.0",
                "2.14.0",
                "2.15.0",
                "2.16.0",
                "2.17.0",
                "2.18.0",
                "2.19.0",
            }
            and isinstance(sequence.get("decodedSamples"), int)
            and sequence["decodedSamples"] < len(frames) - 1
        ):
            findings.error(f"{label}: decoded fewer samples than the saved live frames")
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
        analysis_exclusions: list[JsonObject] = []
        if manifest.get("schemaVersion") in {4, 5}:
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
                if sequence.get("mode")
                in {
                    "wallpaper-wipe",
                    "wallpaper-transition",
                    "wallpaper-transition-reverse",
                }
                else []
            )
            if exclusions != expected_exclusions:
                findings.error(
                    f"{label}: analysisExclusionPixels is {exclusions!r}, "
                    f"expected {expected_exclusions!r}"
                )
            elif isinstance(exclusions, list):
                analysis_exclusions = [
                    exclusion for exclusion in exclusions if isinstance(exclusion, dict)
                ]

        total_frames += len(frames)
        actual_times: list[float] = []
        timing_errors: list[float] = []
        capture_durations: list[float] = []
        presentation_progress: list[float] = []
        pixel_hashes: list[str] = []
        grid_indices: list[int] = []
        first_decoded: DecodedImage | None = None
        post_settle_decoded: DecodedImage | None = None
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

        if manifest.get("schemaVersion") == 5:
            expected_delay = float(manifest.get("settleSeconds", 0)) * 2
            delay = sequence.get("postSettleDelaySeconds")
            if not isinstance(delay, (int, float)) or not math.isclose(
                delay, expected_delay, rel_tol=0, abs_tol=1e-12
            ):
                findings.error(
                    f"{label}: postSettleDelaySeconds is {delay!r}, "
                    f"expected {expected_delay}"
                )
            post_value = sequence.get("postSettleFrame")
            if not isinstance(post_value, dict):
                findings.error(f"{label}: missing postSettleFrame")
            else:
                total_post_settle_frames += 1
                post_record: JsonObject = post_value
                post_label = f"{label} post-settle"
                relative = post_record.get("file")
                if isinstance(relative, str):
                    if relative in seen_files:
                        findings.error(f"duplicate dynamic frame path: {relative}")
                    seen_files.add(relative)
                post_settle_decoded = verify_image_record(
                    root=root,
                    record=post_record,
                    file_hash_key="fileSha256",
                    label=post_label,
                    findings=findings,
                )
                if post_settle_decoded is not None:
                    verify_image_metadata(
                        record=post_record,
                        decoded=post_settle_decoded,
                        saved_key="savedImage",
                        label=post_label,
                        findings=findings,
                        require_source=True,
                    )
                    expected_size = (crop.get("width"), crop.get("height"))
                    if (
                        post_settle_decoded.width,
                        post_settle_decoded.height,
                    ) != expected_size:
                        findings.error(
                            f"{post_label}: dimensions disagree with crop "
                            f"{expected_size}"
                        )
                if post_record.get("stable") is not True:
                    findings.error(f"{post_label}: pixels did not stabilize")
                samples = post_record.get("stabilitySamples")
                if not isinstance(samples, int) or not 3 <= samples <= 6:
                    findings.error(
                        f"{post_label}: invalid stabilitySamples {samples!r}"
                    )

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
        if schema in {4, 5}:
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
        initial_control_within_tolerance: bool | None = None
        post_settle_control_within_tolerance: bool | None = None

        def check_source_control(
            decoded: DecodedImage,
            *,
            reference_name: str,
            context: str,
            exclusions: list[JsonObject],
        ) -> bool | None:
            reference_record = references.get(reference_name)
            if reference_record is not None:
                reference_path = artifact_path(
                    root, reference_record.get("file"), findings
                )
                if reference_path is not None:
                    try:
                        reference_crop = crop_rgba(decode_image(reference_path), crop)
                        reference_pixels = rgba_excluding_regions(
                            reference_crop,
                            width=decoded.width,
                            height=decoded.height,
                            regions=exclusions,
                        )
                        captured_pixels = rgba_excluding_regions(
                            decoded.rgba,
                            width=decoded.width,
                            height=decoded.height,
                            regions=exclusions,
                        )
                        control_diff = pixel_diff(reference_pixels, captured_pixels)
                        within_tolerance = source_diff_is_within_tolerance(
                            control_diff,
                            len(reference_pixels) // 4,
                            tolerance,
                        )
                        if not within_tolerance:
                            findings.error(
                                f"{label}: {context} source round-trip "
                                f"exceeds tolerance: {control_diff}"
                            )
                        return within_tolerance
                    except (KeyError, TypeError, ValueError) as error:
                        findings.error(
                            f"{label}: cannot validate {context} control: {error}"
                        )
            return None

        mode = sequence.get("mode")
        if (
            mode
            in {
                "materialize",
                "wallpaper-transition",
                "wallpaper-transition-reverse",
            }
            and first_decoded
        ):
            initial_control_within_tolerance = check_source_control(
                first_decoded,
                reference_name=str(
                    sequence.get(
                        "outgoingBackground",
                        sequence.get("background"),
                    )
                ),
                context="initial",
                exclusions=analysis_exclusions,
            )
            control_key = (
                str(mode),
                str(sequence.get("outgoingBackground", sequence.get("background"))),
                str(sequence.get("appearance")),
            )
            previous_hash = materialize_controls.setdefault(
                control_key, first_decoded.pixel_sha256
            )
            if first_decoded.pixel_sha256 != previous_hash:
                findings.error(f"{label}: initial control differs between materials")
        if (
            mode
            in {
                "dematerialize",
                "wallpaper-transition",
                "wallpaper-transition-reverse",
            }
            and post_settle_decoded is not None
        ):
            reference_name = (
                sequence.get("incomingBackground")
                if mode in {"wallpaper-transition", "wallpaper-transition-reverse"}
                else sequence.get("outgoingBackground", sequence.get("background"))
            )
            post_settle_control_within_tolerance = check_source_control(
                post_settle_decoded,
                reference_name=str(reference_name),
                context="post-settle",
                exclusions=[],
            )
        materialize_source_within_tolerance = (
            initial_control_within_tolerance if mode == "materialize" else None
        )
        interval = duration / (configured_frames - 1)
        maximum_error = max(timing_errors, default=0)
        timing_limit = max(0.050, interval * 3)
        if maximum_error > timing_limit:
            timing_basis = (
                "actualSeconds and presentationProgress"
                if manifest.get("schemaVersion") in {4, 5}
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
                "initialControlWithinTolerance": initial_control_within_tolerance,
                "postSettleControlWithinTolerance": post_settle_control_within_tolerance,
                "presentationClock": sequence.get("presentationClock"),
                "samplingMethod": sequence.get("samplingMethod"),
                "captureAttempts": sequence.get("captureAttempts"),
                "decodedSamples": sequence.get("decodedSamples"),
                "transientFailures": sequence.get("transientFailures"),
            }
        )
    if manifest.get("requestedSuite") in {"dynamic", "all"}:
        modes = [
            "materialize",
            "resize",
            "translate",
            "morph",
            "wallpaper-wipe",
        ]
        if manifest.get("schemaVersion") == 5:
            requested_modes = manifest.get("requestedDynamicModes")
            modes = (
                [str(mode) for mode in requested_modes]
                if isinstance(requested_modes, list)
                else []
            )
        expected_ids = {
            f"{mode}__{overlay}__{appearance}"
            for mode in modes
            for overlay in ("regular", "clear")
            for appearance in ("light", "dark")
        }
        missing = expected_ids - seen_ids
        unexpected = seen_ids - expected_ids
        if missing:
            findings.error(f"missing dynamic sequences: {sorted(missing)}")
        if unexpected:
            findings.error(f"unexpected dynamic sequences: {sorted(unexpected)}")
    summary: JsonObject = {"sequences": len(values), "frames": total_frames}
    if manifest.get("schemaVersion") == 5:
        summary["postSettleFrames"] = total_post_settle_frames
    return summary, timing_reports


def validate_sweeps(
    root: Path,
    manifest: JsonObject,
    references: dict[str, JsonObject],
    findings: Findings,
) -> dict[str, Any]:
    values = manifest.get("sweepSequences")
    if manifest.get("schemaVersion") == 3 and values is None:
        return {"sequences": 0, "frames": 0}
    if not isinstance(values, list):
        findings.error("sweepSequences is not a list")
        return {"sequences": 0, "frames": 0}

    schema = manifest.get("schemaVersion")
    exact_requested = (
        manifest.get("exactSweepsRequested") is True if schema == 5 else True
    )
    if schema == 5 and not isinstance(manifest.get("exactSweepsRequested"), bool):
        findings.error("exactSweepsRequested is not a Boolean")
    if schema == 5 and not exact_requested and values:
        findings.error("exact sweeps were skipped but sweepSequences is not empty")

    modes = ["resize", "translate", "morph", "wallpaper-wipe"]
    if schema == 5:
        requested_modes = manifest.get("requestedDynamicModes")
        modes = [
            mode
            for mode in (
                [str(value) for value in requested_modes]
                if isinstance(requested_modes, list)
                else []
            )
            if mode
            in {
                "resize",
                "translate",
                "morph",
                "wallpaper-wipe",
                "wallpaper-transition",
                "wallpaper-transition-reverse",
            }
        ]
    expected_ids = {
        f"sweep__{mode}__{overlay}__{appearance}"
        for mode in modes
        for overlay in ("regular", "clear")
        for appearance in ("light", "dark")
    }
    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    total_frames = 0
    cold_repeat_differences = 0
    warm_reverse_differences = 0
    repeatability: list[JsonObject] = []
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
        if not isinstance(crop, dict):
            findings.error(f"{label}: missing cropPixels")
            continue
        if schema == 5:
            mode = sequence.get("mode")
            outgoing = sequence.get("outgoingBackground")
            incoming = sequence.get("incomingBackground")
            if outgoing != sequence.get("background") or outgoing not in references:
                findings.error(f"{label}: invalid outgoingBackground {outgoing!r}")
            expected_sources = {
                "wallpaper-transition": (
                    "dynamic-coded-field",
                    "dynamic-coded-field-incoming",
                ),
                "wallpaper-transition-reverse": (
                    "dynamic-coded-field-incoming",
                    "dynamic-coded-field",
                ),
            }
            expected_outgoing, expected_incoming = expected_sources.get(
                str(mode), ("dynamic-coded-field", None)
            )
            if outgoing != expected_outgoing:
                findings.error(
                    f"{label}: outgoingBackground is {outgoing!r}, "
                    f"expected {expected_outgoing!r}"
                )
            if incoming != expected_incoming:
                findings.error(
                    f"{label}: incomingBackground is {incoming!r}, "
                    f"expected {expected_incoming!r}"
                )
            if isinstance(incoming, str) and incoming not in references:
                findings.error(f"{label}: missing incoming background reference")
            expected_role = (
                "walle-two-wallpaper-expansion"
                if mode in {"wallpaper-transition", "wallpaper-transition-reverse"}
                else "settled-geometry-control"
            )
            if sequence.get("probeRole") != expected_role:
                findings.error(
                    f"{label}: probeRole is {sequence.get('probeRole')!r}, "
                    f"expected {expected_role!r}"
                )
            if (
                sequence.get("stateIsolation")
                != "cold-forward/warm-reverse/cold-repeat"
            ):
                findings.error(f"{label}: invalid stateIsolation")
            expected_traversals = [
                "forward-cold",
                "reverse-warm",
                "forward-cold-repeat",
            ]
            if sequence.get("traversals") != expected_traversals:
                findings.error(f"{label}: invalid traversals")
            confirmation = sequence.get("stabilityConfirmationSeconds")
            if not isinstance(confirmation, (int, float)) or not math.isclose(
                confirmation, 0.10, rel_tol=0, abs_tol=1e-12
            ):
                findings.error(
                    f"{label}: invalid stabilityConfirmationSeconds {confirmation!r}"
                )

        traversals = [
            ("frames", list(range(17)), "forward-cold"),
        ]
        if schema == 5:
            traversals += [
                ("reverseFrames", list(reversed(range(17))), "reverse-warm"),
                ("repeatFrames", list(range(17)), "forward-cold-repeat"),
            ]
        hashes_by_traversal: dict[str, dict[int, str]] = {}
        for key, expected_indices, traversal_name in traversals:
            frames = sequence.get(key)
            if not isinstance(frames, list) or len(frames) != 17:
                count = len(frames) if isinstance(frames, list) else 0
                findings.error(
                    f"{label} {traversal_name}: has {count} frames; "
                    "expected 17 exact states"
                )
                continue
            total_frames += len(frames)
            pixel_hashes: list[str] = []
            hashes_by_index: dict[int, str] = {}
            progress_values: list[float] = []
            for frame_position, (frame_value, expected_index) in enumerate(
                zip(frames, expected_indices, strict=True)
            ):
                if not isinstance(frame_value, dict):
                    findings.error(
                        f"{label} {traversal_name}: "
                        f"frame[{frame_position}] is not an object"
                    )
                    continue
                frame: JsonObject = frame_value
                frame_label = f"{label} {traversal_name} frame[{frame_position}]"
                if frame.get("index") != expected_index:
                    findings.error(
                        f"{frame_label}: index is {frame.get('index')!r}, "
                        f"expected {expected_index}"
                    )
                expected_progress = expected_index / 16
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
                minimum_samples = 3 if schema == 5 else 2
                maximum_samples = 6 if schema == 5 else 4
                if (
                    not isinstance(samples, int)
                    or not minimum_samples <= samples <= maximum_samples
                ):
                    findings.error(
                        f"{frame_label}: invalid stabilitySamples {samples!r}"
                    )
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
                hashes_by_index[expected_index] = decoded.pixel_sha256

            pairs = zip(progress_values, progress_values[1:])
            if traversal_name == "reverse-warm":
                if any(right >= left for left, right in pairs):
                    findings.error(
                        f"{label}: reverse progress values are not strictly decreasing"
                    )
            elif any(right <= left for left, right in pairs):
                findings.error(
                    f"{label}: {traversal_name} progress values are not "
                    "strictly increasing"
                )
            if len(set(pixel_hashes)) != len(frames):
                findings.error(
                    f"{label} {traversal_name}: only "
                    f"{len(set(pixel_hashes))}/{len(frames)} exact geometry "
                    "states are unique"
                )
            hashes_by_traversal[traversal_name] = hashes_by_index

        if schema == 5:
            forward = hashes_by_traversal.get("forward-cold", {})
            reverse = hashes_by_traversal.get("reverse-warm", {})
            repeat = hashes_by_traversal.get("forward-cold-repeat", {})
            cold_changed = sum(
                forward.get(index) != repeat.get(index) for index in range(17)
            )
            reverse_changed = sum(
                forward.get(index) != reverse.get(index) for index in range(17)
            )
            cold_repeat_differences += cold_changed
            warm_reverse_differences += reverse_changed
            repeatability.append(
                {
                    "id": sequence_id,
                    "coldRepeatDifferingStates": cold_changed,
                    "warmReverseDifferingStates": reverse_changed,
                }
            )
            if cold_changed:
                findings.warn(
                    f"{label}: {cold_changed}/17 settled states differ across "
                    "fresh cold traversals; retain both trials as the measured "
                    "repeatability envelope"
                )
            if reverse_changed:
                findings.warn(
                    f"{label}: {reverse_changed}/17 settled states differ after "
                    "reverse traversal; retain both directions as hysteresis "
                    "evidence"
                )

    if (
        schema in {4, 5}
        and exact_requested
        and manifest.get("requestedSuite") in {"dynamic", "all"}
    ):
        missing = expected_ids - seen_ids
        unexpected = seen_ids - expected_ids
        if missing:
            findings.error(f"missing sweep sequences: {sorted(missing)}")
        if unexpected:
            findings.error(f"unexpected sweep sequences: {sorted(unexpected)}")
    summary: dict[str, Any] = {
        "sequences": len(values),
        "frames": total_frames,
    }
    if schema == 5:
        summary.update(
            {
                "coldRepeatDifferingStates": cold_repeat_differences,
                "warmReverseDifferingStates": warm_reverse_differences,
                "repeatability": repeatability,
            }
        )
    return summary


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
        manifest.get("schemaVersion") in {4, 5}
        and requested in {"dynamic", "all"}
        and (
            manifest.get("schemaVersion") == 4
            or manifest.get("exactSweepsRequested") is True
        )
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
            "requestedDynamicModes": manifest.get("requestedDynamicModes"),
            "dynamicDurationSeconds": manifest.get("dynamicDurationSeconds"),
            "transitionOriginNormalized": manifest.get("transitionOriginNormalized"),
            "exactSweepsRequested": manifest.get("exactSweepsRequested"),
            "osVersion": manifest.get("osVersion"),
            "osBuild": manifest.get("osBuild"),
            "architecture": manifest.get("architecture"),
            "ciCommit": manifest.get("ciCommit"),
            "presentationClockPreflight": manifest.get("presentationClockPreflight"),
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
        description="Independently validate a GlassCapture v2.1-v2.19 artifact."
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
