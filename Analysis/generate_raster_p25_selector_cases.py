#!/usr/bin/env python3
"""Generate one fixed-grid raster rectangle for every normalized P25 key.

The AGX raster reciprocal receives an unsimplified 24.8 fixed-point
determinant.  Existing square, near-square, and natural-shadow captures agree
that rounding that determinant to a 25-bit normalized integer (half ties up)
is a sufficient selector key.  This generator constructs a bounded rectangle
whose determinant maps to each possible key.  It does not consult any captured
selector output.
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 1
KEY_LOWER = 1 << 24
KEY_UPPER = 1 << 25
KEY_COUNT = KEY_UPPER - KEY_LOWER
DETERMINANT_SHIFT = 10
HALF_BIN = 1 << (DETERMINANT_SHIFT - 1)
FIXED_UNITS_PER_PIXEL = 256
SEARCH_RADIUS = 1_024
BATCH_COUNT = 65_536
CASE_DTYPE = np.dtype("<u4")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def normalized_p25_key(determinant: np.ndarray) -> np.ndarray:
    """Return the half-up P25 key for determinants in [2**34, 2**35)."""

    quotient, remainder = np.divmod(
        determinant,
        np.int64(1 << DETERMINANT_SHIFT),
    )
    return quotient + (remainder >= HALF_BIN)


def representatives(keys: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Find deterministic near-square fixed extents for a batch of keys."""

    targets = keys << DETERMINANT_SHIFT
    roots = np.sqrt(targets).astype(np.int64)
    best_error = np.full(keys.shape, np.iinfo(np.int64).max, dtype=np.int64)
    best_width = np.zeros(keys.shape, dtype=np.int64)
    best_height = np.zeros(keys.shape, dtype=np.int64)

    # Search in increasing absolute displacement so equal-error ties have a
    # stable, input-only resolution.  Vectorizing each displacement keeps the
    # exhaustive generator fast without materializing a key-by-candidate cube.
    displacements = [0]
    for magnitude in range(1, SEARCH_RADIUS + 1):
        displacements.extend((magnitude, -magnitude))
    for displacement in displacements:
        widths = roots + displacement
        heights = (targets + widths // 2) // widths
        errors = np.abs(widths * heights - targets)
        improved = errors < best_error
        best_error[improved] = errors[improved]
        best_width[improved] = widths[improved]
        best_height[improved] = heights[improved]

    if np.any(best_error >= HALF_BIN):
        failed = np.flatnonzero(best_error >= HALF_BIN)
        first = [
            {
                "key": int(keys[index]),
                "bestError": int(best_error[index]),
            }
            for index in failed[:16]
        ]
        raise ValueError(f"P25 representative search failed: {first}")
    determinant = best_width * best_height
    if not np.array_equal(normalized_p25_key(determinant), keys):
        raise ValueError("P25 representative normalized key differs")
    if (
        np.any(best_width <= 0)
        or np.any(best_height <= 0)
        or np.any(best_width > np.iinfo(np.uint32).max)
        or np.any(best_height > np.iinfo(np.uint32).max)
    ):
        raise ValueError("P25 representative extent is outside uint32")
    return best_width, best_height, best_error


def generate(output: Path) -> JsonObject:
    output.parent.mkdir(parents=True, exist_ok=True)
    cases = np.memmap(
        output,
        mode="w+",
        dtype=CASE_DTYPE,
        shape=(KEY_COUNT, 2),
    )
    error_counts: dict[int, int] = {}
    minimum_width = np.iinfo(np.int64).max
    maximum_width = 0
    minimum_height = np.iinfo(np.int64).max
    maximum_height = 0
    maximum_error = 0

    for start in range(0, KEY_COUNT, BATCH_COUNT):
        stop = min(start + BATCH_COUNT, KEY_COUNT)
        keys = np.arange(KEY_LOWER + start, KEY_LOWER + stop, dtype=np.int64)
        widths, heights, errors = representatives(keys)
        cases[start:stop, 0] = widths.astype(np.uint32)
        cases[start:stop, 1] = heights.astype(np.uint32)
        values, counts = np.unique(errors, return_counts=True)
        for value, count in zip(values.tolist(), counts.tolist(), strict=True):
            error_counts[value] = error_counts.get(value, 0) + count
        minimum_width = min(minimum_width, int(widths.min()))
        maximum_width = max(maximum_width, int(widths.max()))
        minimum_height = min(minimum_height, int(heights.min()))
        maximum_height = max(maximum_height, int(heights.max()))
        maximum_error = max(maximum_error, int(errors.max()))
        if (stop // BATCH_COUNT) % 16 == 0 or stop == KEY_COUNT:
            print(f"p25-cases: {stop}/{KEY_COUNT}", flush=True)

    cases.flush()
    del cases
    byte_count = output.stat().st_size
    expected_bytes = KEY_COUNT * 2 * CASE_DTYPE.itemsize
    if byte_count != expected_bytes:
        raise ValueError("P25 representative file size differs")
    return {
        "rasterP25SelectorCaseGenerationSchemaVersion": SCHEMA_VERSION,
        "classification": (
            "input-only exhaustive normalized-P25 fixed-grid rectangle generation"
        ),
        "domain": {
            "keyLowerInclusive": KEY_LOWER,
            "keyUpperExclusive": KEY_UPPER,
            "keyCount": KEY_COUNT,
            "normalization": (
                "round-half-up((widthFixed*heightFixed)/2^10)"
            ),
            "fixedUnitsPerPixel": FIXED_UNITS_PER_PIXEL,
        },
        "search": {
            "targetDeterminant": "key*2^10",
            "center": "floor(sqrt(targetDeterminant))",
            "displacements": f"0,+1,-1,...,+{SEARCH_RADIUS},-{SEARCH_RADIUS}",
            "selection": "minimum absolute determinant error; first on ties",
            "maximumAllowedAbsoluteError": HALF_BIN - 1,
            "maximumObservedAbsoluteError": maximum_error,
        },
        "cases": {
            "file": output.name,
            "bytes": byte_count,
            "sha256": sha256_path(output),
            "dtype": "two little-endian uint32 words",
            "ordering": "ascending normalized-P25 key",
            "minimumWidthFixed": minimum_width,
            "maximumWidthFixed": maximum_width,
            "minimumHeightFixed": minimum_height,
            "maximumHeightFixed": maximum_height,
        },
        "determinantAbsoluteErrorDistribution": {
            str(key): value for key, value in sorted(error_counts.items())
        },
        "capturedAppleOutputUsed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args()
    report = generate(arguments.output)
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.report is not None:
        arguments.report.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
