#!/usr/bin/env python3
"""Validate the exact SwiftUI two-wallpaper circle-reveal composition."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


class ValidationError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: expected a JSON object")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def load_rgba(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGBA"), dtype=np.uint8)


def reveal_mask(
    width: int,
    height: int,
    center_x: float,
    center_y: float,
    radius: float,
) -> np.ndarray:
    x = np.arange(width, dtype=np.float64) + 0.5
    y = np.arange(height, dtype=np.float64) + 0.5
    dx = x - center_x
    dy = y - center_y
    return dy[:, None] * dy[:, None] + dx[None, :] * dx[None, :] <= radius * radius


def compare_frame(
    actual: np.ndarray,
    outgoing: np.ndarray,
    incoming: np.ndarray,
    mask: np.ndarray,
) -> dict[str, Any]:
    expected = np.where(mask[:, :, None], incoming, outgoing)
    unequal = actual != expected
    unequal_pixels = np.any(unequal, axis=2)
    distinct_sources = np.any(outgoing != incoming, axis=2)
    equals_outgoing = np.all(actual == outgoing, axis=2)
    equals_incoming = np.all(actual == incoming, axis=2)
    neither_source = distinct_sources & ~(equals_outgoing | equals_incoming)
    coordinates = np.argwhere(unequal_pixels)
    first: dict[str, Any] | None = None
    if coordinates.size:
        y, x = (int(value) for value in coordinates[0])
        first = {
            "x": x,
            "y": y,
            "actual": actual[y, x].tolist(),
            "expected": expected[y, x].tolist(),
            "outgoing": outgoing[y, x].tolist(),
            "incoming": incoming[y, x].tolist(),
            "insideCandidate": bool(mask[y, x]),
        }
    return {
        "checkedBytes": int(actual.size),
        "mismatchedBytes": int(np.count_nonzero(unequal)),
        "mismatchedPixels": int(np.count_nonzero(unequal_pixels)),
        "neitherSourcePixels": int(np.count_nonzero(neither_source)),
        "firstMismatch": first,
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def select_reference(manifest: dict[str, Any], background: str) -> dict[str, Any]:
    matches = [
        item
        for item in manifest.get("references", [])
        if isinstance(item, dict) and item.get("background") == background
    ]
    require(
        len(matches) == 1, f"expected one {background} reference; found {len(matches)}"
    )
    return matches[0]


def validate(
    capture_root: Path,
    preregistration_path: Path,
    preflight_path: Path,
) -> dict[str, Any]:
    preregistration = load_json(preregistration_path)
    manifest_path = capture_root / "manifest.json"
    manifest = load_json(manifest_path)
    preflight = load_json(preflight_path)
    expected = preregistration["capture"]

    require(preflight.get("passed") is True, "physical Retina preflight did not pass")
    require(
        preflight.get("backingScaleFactor") == 2, "capture session is not 2x Retina"
    )
    require(
        preflight.get("sessionOnConsole") is True, "capture session is not on-console"
    )
    require(preflight.get("sessionLocked") is False, "capture session is locked")
    require(preflight.get("displayActive") is True, "capture display is inactive")
    require(preflight.get("displayAsleep") is False, "capture display is asleep")
    require(manifest.get("osBuild") == expected["macOSBuild"], "macOS build differs")
    require(
        manifest.get("backingScaleFactor") == expected["backingScaleFactor"],
        "scale differs",
    )
    require(
        manifest.get("windowPoints") == expected["windowPoints"], "window size differs"
    )
    require(
        manifest.get("transitionOriginNormalized")
        == expected["transitionOriginNormalized"],
        "transition origin differs",
    )
    require(
        manifest.get("requestedDynamicModes") == ["wallpaper-reveal"],
        "capture is not the isolated reveal mode",
    )
    require(
        manifest.get("exactSweepsRequested") is True, "exact sweeps were not requested"
    )

    source_contract = preregistration["frozenSources"]
    repository = preregistration_path.parent.parent
    for relative, expected_hash in source_contract.items():
        require(
            sha256(repository / relative) == expected_hash,
            f"{relative} SHA-256 differs",
        )

    sweeps = manifest.get("sweepSequences")
    require(isinstance(sweeps, list), "manifest has no sweep sequence list")
    identifier = "sweep__wallpaper-reveal__regular__dark"
    matches = [
        item
        for item in sweeps
        if isinstance(item, dict) and item.get("id") == identifier
    ]
    require(len(matches) == 1, f"expected one reveal sweep; found {len(matches)}")
    sequence = matches[0]
    require(
        sequence.get("probeRole") == "walle-two-wallpaper-reveal-oracle", "role differs"
    )
    require(
        sequence.get("outgoingBackground") == "dynamic-coded-field",
        "outgoing source differs",
    )
    require(
        sequence.get("incomingBackground") == "dynamic-coded-field-incoming",
        "incoming source differs",
    )

    outgoing_record = select_reference(manifest, "dynamic-coded-field")
    incoming_record = select_reference(manifest, "dynamic-coded-field-incoming")
    outgoing_path = capture_root / outgoing_record["file"]
    incoming_path = capture_root / incoming_record["file"]
    require(
        sha256(outgoing_path) == outgoing_record["fileSha256"],
        "outgoing file hash differs",
    )
    require(
        sha256(incoming_path) == incoming_record["fileSha256"],
        "incoming file hash differs",
    )
    outgoing = load_rgba(outgoing_path)
    incoming = load_rgba(incoming_path)
    require(outgoing.shape == incoming.shape, "source dimensions differ")
    height, width, channels = outgoing.shape
    require(channels == 4, "sources are not RGBA")

    points_width, points_height = expected["windowPoints"]
    scale = float(expected["backingScaleFactor"])
    require(width == int(points_width * scale), "source pixel width differs")
    require(height == int(points_height * scale), "source pixel height differs")
    origin_x, origin_y = expected["transitionOriginNormalized"]
    center_x_points = points_width * origin_x
    center_y_points = points_height * origin_y
    right = points_width - center_x_points
    bottom = points_height - center_y_points
    farthest_radius_squared = max(
        center_x_points * center_x_points + center_y_points * center_y_points,
        right * right + center_y_points * center_y_points,
        center_x_points * center_x_points + bottom * bottom,
        right * right + bottom * bottom,
    )
    full_diameter_points = math.sqrt(farthest_radius_squared) * 2.06
    center_x = center_x_points * scale
    center_y = center_y_points * scale

    traversal_names = ("frames", "reverseFrames", "repeatFrames")
    frame_count = expected["sweepFrameCount"]
    records: list[dict[str, Any]] = []
    totals = {
        "checkedBytes": 0,
        "mismatchedBytes": 0,
        "mismatchedPixels": 0,
        "neitherSourcePixels": 0,
    }
    for traversal in traversal_names:
        frames = sequence.get(traversal)
        require(isinstance(frames, list), f"{traversal} is absent")
        require(len(frames) == frame_count, f"{traversal} frame count differs")
        observed_indices = {record.get("index") for record in frames}
        require(
            observed_indices == set(range(frame_count)), f"{traversal} indices differ"
        )
        for record in frames:
            index = record["index"]
            progress = index / (frame_count - 1)
            require(
                record.get("progress") == progress,
                f"{traversal} progress differs at {index}",
            )
            require(
                record.get("stable") is True, f"{traversal} frame {index} is unstable"
            )
            frame_path = capture_root / record["file"]
            require(
                sha256(frame_path) == record["fileSha256"],
                f"{record['file']} hash differs",
            )
            actual = load_rgba(frame_path)
            require(
                actual.shape == outgoing.shape, f"{record['file']} dimensions differ"
            )
            radius = (full_diameter_points * progress * scale) / 2.0
            mask = reveal_mask(width, height, center_x, center_y, radius)
            comparison = compare_frame(actual, outgoing, incoming, mask)
            records.append(
                {
                    "traversal": traversal,
                    "index": index,
                    "progress": progress,
                    "radiusPixels": radius,
                    "file": record["file"],
                    "fileSHA256": record["fileSha256"],
                    **comparison,
                }
            )
            for key in totals:
                totals[key] += comparison[key]

    accepted = all(value == 0 for key, value in totals.items() if key != "checkedBytes")
    return {
        "schemaVersion": 1,
        "status": "accepted-exact-pixel-center-circle-reveal"
        if accepted
        else "rejected",
        "capture": {
            "root": str(capture_root),
            "manifestSHA256": sha256(manifest_path),
            "preflightSHA256": sha256(preflight_path),
            "physicalRetina": True,
            "backingScaleFactor": scale,
        },
        "candidate": {
            "coordinateSystem": "top-left physical pixels",
            "sampleLocation": "(x + 0.5, y + 0.5)",
            "insidePredicate": "dx*dx + dy*dy <= radius*radius in binary64",
            "sourceSelection": "incoming inside, outgoing outside, no blend",
            "centerPixels": [center_x, center_y],
            "fullDiameterPoints": full_diameter_points,
        },
        "traversalCount": len(traversal_names),
        "frameCount": len(records),
        "records": records,
        "totals": totals,
        "tolerance": 0,
        "accepted": accepted,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        result = validate(
            arguments.capture_root, arguments.preregistration, arguments.preflight
        )
    except (OSError, KeyError, TypeError, ValueError, ValidationError) as error:
        result = {
            "schemaVersion": 1,
            "status": "rejected",
            "error": str(error),
            "accepted": False,
        }
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(result["totals"] if "totals" in result else result, sort_keys=True)
    )
    return 0 if result.get("accepted") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
