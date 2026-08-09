#!/usr/bin/env python3
"""Open the rejected v1 reveal capture without weakening its frozen gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from validate_walle_reveal_composition import load_rgba


SEQUENCE_ID = "sweep__wallpaper-reveal__regular__dark"
TRAVERSALS = ("frames", "reverseFrames", "repeatFrames")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def effective_radius(radius: float) -> float:
    """Return the half-pixel radius implied by the opened Retina frames."""
    return math.floor(2.0 * radius) / 2.0


def sequence_record(manifest: dict[str, Any]) -> dict[str, Any]:
    matches = [
        item
        for item in manifest.get("sweepSequences", [])
        if isinstance(item, dict) and item.get("id") == SEQUENCE_ID
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one {SEQUENCE_ID} sequence; found {len(matches)}")
    return matches[0]


def load_traversal(
    capture_root: Path,
    sequence: dict[str, Any],
    traversal: str,
) -> list[np.ndarray]:
    records = sequence.get(traversal)
    if not isinstance(records, list) or len(records) != 17:
        raise ValueError(f"{traversal}: expected 17 records")
    ordered = sorted(records, key=lambda item: item["index"])
    if [item["index"] for item in ordered] != list(range(17)):
        raise ValueError(f"{traversal}: indices differ")
    return [load_rgba(capture_root / item["file"]) for item in ordered]


def frame_discovery(
    actual: np.ndarray,
    outgoing: np.ndarray,
    incoming: np.ndarray,
    distance: np.ndarray,
    radius: float,
    feather: np.ndarray,
) -> dict[str, Any]:
    distinct = np.any(outgoing != incoming, axis=2)
    equals_outgoing = np.all(actual == outgoing, axis=2)
    equals_incoming = np.all(actual == incoming, axis=2)
    neither = distinct & ~(equals_outgoing | equals_incoming)
    signed_distance = distance - radius
    edge_support = neither & (np.abs(signed_distance) <= 1.5)
    off_edge = neither & ~edge_support

    outgoing_rgb = outgoing[:, :, :3].astype(np.float64)
    incoming_rgb = incoming[:, :, :3].astype(np.float64)
    actual_rgb = actual[:, :, :3].astype(np.float64)
    delta = incoming_rgb - outgoing_rgb
    denominator = np.sum(delta * delta, axis=2)
    estimated_alpha = np.sum((actual_rgb - outgoing_rgb) * delta, axis=2)
    estimated_alpha /= np.maximum(denominator, 1.0)
    sdf_alpha = np.clip(
        0.5 - signed_distance / np.maximum(feather, 1.0e-300),
        0.0,
        1.0,
    )
    informative = (denominator >= 2500.0) & (np.abs(signed_distance) < 1.5)
    estimate = estimated_alpha[informative]
    candidate = sdf_alpha[informative]
    correlation = float(np.corrcoef(estimate, candidate)[0, 1])

    coordinates = np.argwhere(off_edge)
    first_off_edge: dict[str, Any] | None = None
    if coordinates.size:
        y, x = (int(value) for value in coordinates[0])
        first_off_edge = {
            "x": x,
            "y": y,
            "signedDistancePixels": float(signed_distance[y, x]),
            "actual": actual[y, x].tolist(),
            "incomingEndpoint": incoming[y, x].tolist(),
            "outgoingEndpoint": outgoing[y, x].tolist(),
        }
    return {
        "neitherEndpointPixels": int(np.count_nonzero(neither)),
        "edgeSupportPixels": int(np.count_nonzero(edge_support)),
        "offEdgePixels": int(np.count_nonzero(off_edge)),
        "firstOffEdge": first_off_edge,
        "informativePixels": int(np.count_nonzero(informative)),
        "encodedAlphaVsSdfCorrelation": correlation,
        "encodedAlphaVsSdfMeanAbsoluteError": float(
            np.mean(np.abs(estimate - candidate))
        ),
    }


def analyze(capture_root: Path, frozen_validation_path: Path) -> dict[str, Any]:
    manifest_path = capture_root / "manifest.json"
    manifest = load_object(manifest_path)
    frozen_validation = load_object(frozen_validation_path)
    sequence = sequence_record(manifest)
    loaded = {
        traversal: load_traversal(capture_root, sequence, traversal)
        for traversal in TRAVERSALS
    }

    endpoint_stability: dict[str, Any] = {}
    for index in (0, 16):
        baseline = loaded["frames"][index]
        endpoint_stability[str(index)] = {
            traversal: {
                "mismatchedBytesVsForward": int(
                    np.count_nonzero(loaded[traversal][index] != baseline)
                ),
                "mismatchedPixelsVsForward": int(
                    np.count_nonzero(
                        np.any(loaded[traversal][index] != baseline, axis=2)
                    )
                ),
            }
            for traversal in TRAVERSALS
        }

    points_width, points_height = manifest["windowPoints"]
    scale = float(manifest["backingScaleFactor"])
    origin_x, origin_y = manifest["transitionOriginNormalized"]
    center_x_points = points_width * origin_x
    center_y_points = points_height * origin_y
    farthest_radius = max(
        math.hypot(center_x_points, center_y_points),
        math.hypot(points_width - center_x_points, center_y_points),
        math.hypot(center_x_points, points_height - center_y_points),
        math.hypot(
            points_width - center_x_points,
            points_height - center_y_points,
        ),
    )
    full_radius = farthest_radius * 1.03 * scale
    center_x = center_x_points * scale
    center_y = center_y_points * scale
    height, width, _ = loaded["frames"][0].shape
    y, x = np.indices((height, width), dtype=np.float64)
    dx = x + 0.5 - center_x
    dy = y + 0.5 - center_y
    distance = np.hypot(dx, dy)
    feather = (np.abs(dx) + np.abs(dy)) / np.maximum(distance, 1.0e-300)

    traversal_identity: dict[str, Any] = {}
    forward = loaded["frames"]
    for traversal in TRAVERSALS[1:]:
        mismatched_bytes = 0
        mismatched_pixels = 0
        for index, baseline in enumerate(forward):
            unequal = loaded[traversal][index] != baseline
            mismatched_bytes += int(np.count_nonzero(unequal))
            mismatched_pixels += int(
                np.count_nonzero(np.any(unequal, axis=2))
            )
        traversal_identity[traversal] = {
            "mismatchedBytesVsForward": mismatched_bytes,
            "mismatchedPixelsVsForward": mismatched_pixels,
        }

    per_traversal = {
        "neitherEndpointPixels": 0,
        "edgeSupportPixels": 0,
        "offEdgePixels": 0,
    }
    frames = []
    outgoing = forward[0]
    incoming = forward[16]
    for index in range(1, 16):
        unsnapped_radius = full_radius * index / 16.0
        radius = effective_radius(unsnapped_radius)
        result = frame_discovery(
            forward[index],
            outgoing,
            incoming,
            distance,
            radius,
            feather,
        )
        frames.append(
            {
                "index": index,
                "progress": index / 16.0,
                "unsnappedRadiusPixels": unsnapped_radius,
                "effectiveRadiusPixels": radius,
                **result,
            }
        )
        for key in per_traversal:
            per_traversal[key] += result[key]
    all_traversals = {
        key: value * len(TRAVERSALS) for key, value in per_traversal.items()
    }

    return {
        "schemaVersion": 1,
        "status": "rejected-frozen-binary-candidate-opened-discovery",
        "claimBoundary": {
            "promotes": [],
            "doesNotAuthorize": [
                "a nonzero comparison tolerance",
                "post-hoc acceptance of the rejected v1 candidate",
                "ordinary Walle integration",
                "production parity",
            ],
        },
        "capture": {
            "manifestSHA256": sha256(manifest_path),
            "frozenValidationSHA256": sha256(frozen_validation_path),
            "frozenStatus": frozen_validation.get("status"),
            "frozenTotals": frozen_validation.get("totals"),
        },
        "endpointStability": endpoint_stability,
        "openedFinding": {
            "physicalDiameterRule": "floor(diameterPixels)",
            "effectiveRadiusRule": "floor(diameterPixels) / 2",
            "comparisonSources": "same-surface captured endpoints",
            "traversalIdentity": traversal_identity,
            "perTraversal": per_traversal,
            "allTraversals": all_traversals,
            "frames": frames,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("--frozen-validation", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze(args.capture_root, args.frozen_validation)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
