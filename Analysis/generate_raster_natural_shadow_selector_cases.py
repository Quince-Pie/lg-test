#!/usr/bin/env python3
"""Generate the frozen circle-480 shadow-raster determinant domain."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np


type JsonObject = dict[str, object]

FIXED_UNITS_PER_PIXEL = 256
MARGIN_FIXED_LOWER = 0
MARGIN_FIXED_UPPER = 12_288
PHASE_DENOMINATOR = 256
DIAMETER = 480.0
WINDOW_EXTENT = 1_024.0
CENTER = 512.0
MINIMUM_REMAINING = 2.0**-24
CASE_RECORD_DTYPE = np.dtype("<u4")


def shadow_pairs(remaining: np.ndarray) -> np.ndarray:
    """Return all positive ring-quad fixed extents for each remaining value."""
    half = DIAMETER / 2.0
    scale_limit = (DIAMETER + 16.0) / DIAMETER
    remaining64 = remaining.astype(np.float64)
    carrier_extent = DIAMETER * remaining64
    carrier_position = CENTER - carrier_extent / 2.0
    progress = np.float32(1.0 - remaining).astype(np.float64)
    transition_scale = 1.0 + progress * (scale_limit - 1.0)

    lower = half - half * transition_scale
    upper = transition_scale * DIAMETER + (half - half * transition_scale)
    for scale in (1.0 / math.sqrt(scale_limit), math.sqrt(scale_limit)):
        translation = half - half * scale
        lower = scale * lower + translation
        upper = scale * upper + translation

    snapped_carrier_extent = np.floor(carrier_extent + 0.5)
    root_translation = CENTER - half + (snapped_carrier_extent - carrier_extent) / 2.0
    root_lower = lower + root_translation
    root_upper = upper + root_translation
    element_extent = root_upper - root_lower
    element_position = root_lower - carrier_position
    horizontal_origin = carrier_position + element_position
    vertical_origin = WINDOW_EXTENT - carrier_position - element_position

    margin = np.float32(np.float32(48.0) * remaining).astype(np.float64)
    top_margin = np.maximum(margin - 8.0, 0.0)
    extended_width = np.float32(element_extent + margin).astype(np.float64)
    extended_height = np.float32(element_extent + margin + 8.0).astype(np.float64)
    positions_x = np.stack(
        (
            np.float32(horizontal_origin - margin),
            np.float32(horizontal_origin),
            np.float32(horizontal_origin + element_extent),
            np.float32(horizontal_origin + extended_width),
        ),
        axis=1,
    ).astype(np.float64)
    positions_y = np.stack(
        (
            np.float32(vertical_origin + top_margin),
            np.float32(vertical_origin),
            np.float32(vertical_origin - element_extent),
            np.float32(vertical_origin - extended_height),
        ),
        axis=1,
    ).astype(np.float64)

    # The independently measured raster snap is 1/256 pixel with half ties
    # toward positive infinity. Multiplication by 256 is exact for binary32.
    fixed_x = np.floor(positions_x * FIXED_UNITS_PER_PIXEL + 0.5).astype(np.int64)
    fixed_y = np.floor(positions_y * FIXED_UNITS_PER_PIXEL + 0.5).astype(np.int64)
    x_gaps = np.diff(fixed_x, axis=1)
    y_gaps = -np.diff(fixed_y, axis=1)
    pairs = np.stack(
        (
            x_gaps[:, 0],
            y_gaps[:, 0],
            x_gaps[:, 2],
            y_gaps[:, 0],
            x_gaps[:, 2],
            y_gaps[:, 2],
            x_gaps[:, 0],
            y_gaps[:, 2],
            x_gaps[:, 1],
            y_gaps[:, 0],
            x_gaps[:, 0],
            y_gaps[:, 1],
            x_gaps[:, 2],
            y_gaps[:, 1],
            x_gaps[:, 1],
            y_gaps[:, 2],
        ),
        axis=1,
    ).reshape(-1, 2)
    return pairs[(pairs[:, 0] > 0) & (pairs[:, 1] > 0)]


def cases() -> np.ndarray:
    """Enumerate and sort the complete preregistered finite input lattice."""
    encoded: set[int] = set()
    phases = np.arange(PHASE_DENOMINATOR + 1, dtype=np.float64)[None, :]
    for start in range(MARGIN_FIXED_LOWER, MARGIN_FIXED_UPPER + 1, 512):
        margins = np.arange(
            start,
            min(start + 512, MARGIN_FIXED_UPPER + 1),
            dtype=np.float64,
        )[:, None]
        remaining = np.float32(
            np.clip(
                (margins + phases / PHASE_DENOMINATOR - 0.5) / MARGIN_FIXED_UPPER,
                MINIMUM_REMAINING,
                1.0,
            )
        ).reshape(-1)
        pairs = shadow_pairs(remaining)
        packed = (pairs[:, 0].astype(np.uint64) << np.uint64(32)) | pairs[:, 1].astype(
            np.uint64
        )
        encoded.update(map(int, np.unique(packed)))
    ordered = np.asarray(sorted(encoded), dtype=np.uint64)
    result = np.empty((len(ordered), 2), dtype=CASE_RECORD_DTYPE)
    result[:, 0] = ordered >> np.uint64(32)
    result[:, 1] = ordered & np.uint64(0xFFFF_FFFF)
    return result


def report(values: np.ndarray, payload: bytes) -> JsonObject:
    return {
        "schemaVersion": 1,
        "classification": (
            "finite natural circle-480 regular-material shadow-raster "
            "dimension calibration; not a portable reciprocal law"
        ),
        "geometry": {
            "shape": "circle",
            "diameter": int(DIAMETER),
            "center": [int(CENTER), int(CENTER)],
            "windowExtent": int(WINDOW_EXTENT),
            "material": "regular",
        },
        "enumeration": {
            "fixedUnitsPerPixel": FIXED_UNITS_PER_PIXEL,
            "marginFixedLower": MARGIN_FIXED_LOWER,
            "marginFixedUpper": MARGIN_FIXED_UPPER,
            "subBinPhaseDenominator": PHASE_DENOMINATOR,
            "subBinPhaseCount": PHASE_DENOMINATOR + 1,
            "minimumRemaining": MINIMUM_REMAINING,
            "positiveQuadsOnly": True,
            "ordering": "ascending widthFixed,heightFixed",
        },
        "cases": {
            "count": len(values),
            "recordBytes": 8,
            "rawBytes": len(payload),
            "dtype": "two little-endian uint32 words",
            "components": ["widthFixed", "heightFixed"],
            "sha256": hashlib.sha256(payload).hexdigest(),
            "minimumWidthFixed": int(values[:, 0].min()),
            "maximumWidthFixed": int(values[:, 0].max()),
            "minimumHeightFixed": int(values[:, 1].min()),
            "maximumHeightFixed": int(values[:, 1].max()),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args()
    values = cases()
    payload = values.tobytes()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(payload)
    metadata = report(values, payload)
    encoded = json.dumps(metadata, indent=2, sort_keys=True) + "\n"
    if arguments.report is not None:
        arguments.report.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
