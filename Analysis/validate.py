#!/usr/bin/env python3
"""Validate a GlassCapture v2 artifact without trusting its manifest hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image


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
        rgba = source.convert("RGBA")
        pixels = rgba.tobytes()
        return DecodedImage(
            width=rgba.width,
            height=rgba.height,
            rgba=pixels,
            pixel_sha256=hashlib.sha256(pixels).hexdigest(),
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
    expected_size = (record.get("pixelWidth"), record.get("pixelHeight"))
    if (decoded.width, decoded.height) != expected_size:
        findings.error(
            f"{label}: decoded size {decoded.width}x{decoded.height}, expected "
            f"{expected_size[0]}x{expected_size[1]}"
        )
    return decoded


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
    if manifest.get("schemaVersion") != 2:
        findings.error(
            f"schemaVersion is {manifest.get('schemaVersion')!r}; validator requires 2"
        )
    if manifest.get("rigVersion") != "2.0.0":
        findings.error(f"unexpected rigVersion: {manifest.get('rigVersion')!r}")
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
    base_controls: set[tuple[str, str]] = set()
    actual_cases: set[tuple[str, str, str, str]] = set()
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
        case = (str(background), str(scene), str(overlay), str(appearance))
        if case in actual_cases:
            findings.error(f"{label}: duplicate logical capture case {case}")
        actual_cases.add(case)
        if overlay == "none" and scene == "circle-0500-center":
            if isinstance(background, str) and isinstance(appearance, str):
                base_controls.add((background, appearance))
            reference_entry = references.get(str(background))
            stored_diff = record.get("controlDiff")
            if reference_entry is None:
                findings.error(f"{label}: no reference for control")
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
                    findings.error(f"{label}: missing controlDiff")
                elif actual_diff[:2] != expected_diff[:2] or not math.isclose(
                    actual_diff[2], expected_diff[2], rel_tol=0, abs_tol=1e-12
                ):
                    findings.error(
                        f"{label}: stored controlDiff {expected_diff} does not "
                        f"match recomputed {actual_diff}"
                    )
                if actual_diff != (0, 0, 0.0):
                    findings.error(
                        f"{label}: control is not pixel-exact: {actual_diff}"
                    )
        elif overlay != "hig-interactive-regular":
            if (str(background), str(appearance)) not in base_controls:
                # Ordering is not a scientific requirement; check again after
                # collecting all records below.
                pass

    for value in captures:
        if not isinstance(value, dict):
            continue
        if value.get("overlay") in {"none", "hig-interactive-regular"}:
            continue
        pair = (str(value.get("background")), str(value.get("appearance")))
        if pair not in base_controls:
            findings.error(
                f"{value.get('file')}: no base no-glass control for {pair[0]}/{pair[1]}"
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
    timing_reports: list[JsonObject] = []
    total_frames = 0
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
        if isinstance(configured_frames, int) and len(frames) != configured_frames:
            findings.error(
                f"{label}: has {len(frames)} frames, configured for {configured_frames}"
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

        total_frames += len(frames)
        actual_times: list[float] = []
        timing_errors: list[float] = []
        capture_durations: list[float] = []
        pixel_hashes: list[str] = []
        first_decoded: DecodedImage | None = None
        for frame_index, frame_value in enumerate(frames):
            if not isinstance(frame_value, dict):
                findings.error(f"{label}: frame[{frame_index}] is not an object")
                continue
            frame: JsonObject = frame_value
            frame_label = f"{label} frame[{frame_index}]"
            if frame.get("index") != frame_index:
                findings.error(f"{frame_label}: stored index is {frame.get('index')!r}")
            expected_target = duration * frame_index / (len(frames) - 1)
            target = frame.get("targetSeconds")
            actual = frame.get("actualSeconds")
            error = frame.get("timingErrorSeconds")
            capture_duration = frame.get("captureDurationSeconds")
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
            elif frame_index:
                timing_errors.append(abs(float(error)))
            if not isinstance(capture_duration, (int, float)) or capture_duration < 0:
                findings.error(f"{frame_label}: invalid capture duration")
            else:
                capture_durations.append(float(capture_duration))

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
                if frame_index == 0:
                    first_decoded = decoded
                expected_size = (crop.get("width"), crop.get("height"))
                if (decoded.width, decoded.height) != expected_size:
                    findings.error(
                        f"{frame_label}: dimensions disagree with crop {expected_size}"
                    )
                pixel_hashes.append(decoded.pixel_sha256)

        if any(right <= left for left, right in zip(actual_times, actual_times[1:])):
            findings.error(f"{label}: actual sample times are not strictly increasing")
        unique_frames = len(set(pixel_hashes))
        minimum_unique = min(10, max(3, len(frames) // 4))
        if unique_frames < minimum_unique:
            findings.error(
                f"{label}: only {unique_frames} unique frames; expected at least "
                f"{minimum_unique}"
            )
        materialize_control_exact: bool | None = None
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
                        materialize_control_exact = control_diff == (0, 0, 0.0)
                        if not materialize_control_exact:
                            findings.error(
                                f"{label}: pre-materialization control is not "
                                f"pixel-exact: {control_diff}"
                            )
                    except (KeyError, TypeError, ValueError) as error:
                        findings.error(
                            f"{label}: cannot validate materialize control: {error}"
                        )
        interval = duration / (len(frames) - 1)
        maximum_error = max(timing_errors, default=0)
        timing_limit = max(0.050, interval * 3)
        if maximum_error > timing_limit:
            findings.error(
                f"{label}: worst timing error {maximum_error:.6f}s exceeds "
                f"{timing_limit:.6f}s"
            )
        timing_reports.append(
            {
                "id": sequence_id,
                "frames": len(frames),
                "uniqueFrames": unique_frames,
                "timingErrorMedianSeconds": statistics.median(timing_errors)
                if timing_errors
                else 0,
                "timingErrorP95Seconds": percentile(timing_errors, 0.95),
                "timingErrorMaxSeconds": maximum_error,
                "captureDurationMedianSeconds": statistics.median(capture_durations)
                if capture_durations
                else 0,
                "captureDurationP95Seconds": percentile(capture_durations, 0.95),
                "materializeControlExact": materialize_control_exact,
            }
        )
    if manifest.get("requestedSuite") in {"dynamic", "all"}:
        expected_ids = {
            f"{mode}__{overlay}__{appearance}"
            for mode in ("materialize", "resize", "translate", "morph")
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


def validate(root: Path) -> tuple[Findings, JsonObject]:
    findings = Findings()
    root = root.resolve()

    def unreadable_report() -> JsonObject:
        return {
            "schemaVersion": 1,
            "valid": False,
            "artifact": str(root),
            "summary": {
                "references": 0,
                "static": {"count": 0},
                "dynamic": {"sequences": 0, "frames": 0},
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

    requested = manifest.get("requestedSuite")
    if requested in {"static", "all"} and static_summary["count"] == 0:
        findings.error("requested static suite produced no captures")
    if requested in {"dynamic", "all"} and dynamic_summary["sequences"] == 0:
        findings.error("requested dynamic suite produced no sequences")

    report: JsonObject = {
        "schemaVersion": 1,
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
        description="Independently validate a GlassCapture v2 artifact."
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
        f"dynamic_frames={summary.get('dynamic', {}).get('frames', 0)}"
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
