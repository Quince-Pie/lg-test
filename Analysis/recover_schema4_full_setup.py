#!/usr/bin/env python3
"""Recover joint slope and tile-constant neighbors for schema-4 broad ramps."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import explore_schema4_endpoint_constant_pipeline as pipeline
import raster_tile_selector_model as v1
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v8 as v8
import validate_raster_tile_phase_holdout as capture


type JsonObject = dict[str, Any]

SLOPE_OFFSETS = tuple(range(-4, 5))
CONSTANT_OFFSETS = tuple(range(-4, 5))


def analyze(root: Path) -> JsonObject:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    raw = (root / manifest["rasterTileNumerator"]["file"]).read_bytes()
    selector_table = v1.load_selector_table()
    setup_count = 0
    exact_setup_count = 0
    accepted_slope_offsets: Counter[int] = Counter()
    groups: list[JsonObject] = []

    for case_index, capture_case in enumerate(capture.CASES):
        samples = capture.sample_positions(capture_case)
        for endpoint_index, endpoint in enumerate(capture.ENDPOINTS):
            if endpoint.name not in pipeline.TARGET_ENDPOINTS:
                continue
            for axis in range(capture.AXIS_COUNT):
                setup_count += 1
                axis_samples = [sample for sample in samples if sample.axis == axis]
                by_tile: dict[tuple[int, int], list[object]] = defaultdict(list)
                for sample in axis_samples:
                    by_tile[(sample.primitive, sample.tile)].append(sample)
                slope_bits, phase, internal = v4.determinant_slope(
                    capture_case,
                    endpoint,
                    axis=axis,
                    selector_table=selector_table,
                )
                accepted: dict[int, dict[str, list[int]]] = {}
                for slope_offset in SLOPE_OFFSETS:
                    slope_float = v1.bits_float32(slope_bits + slope_offset)
                    constants: dict[str, list[int]] = {}
                    all_groups_match = True
                    for (primitive, tile), group_samples in by_tile.items():
                        actual = tuple(
                            pipeline.record_at(
                                raw,
                                case_index,
                                endpoint_index,
                                sample,
                            )
                            for sample in group_samples
                        )
                        physical_bits = v8.physical_constant_bits(
                            capture_case,
                            endpoint,
                            group_samples[0],
                            selector_table=selector_table,
                        )
                        matching_constants = [
                            constant_offset
                            for constant_offset in CONSTANT_OFFSETS
                            if all(
                                pipeline.predicted_record(
                                    sample,
                                    endpoint,
                                    slope_float=slope_float,
                                    constant_bits=physical_bits + constant_offset,
                                )
                                == expected
                                for sample, expected in zip(
                                    group_samples,
                                    actual,
                                    strict=True,
                                )
                            )
                        ]
                        if not matching_constants:
                            all_groups_match = False
                            break
                        constants[f"p{primitive}:t{tile}"] = matching_constants
                    if all_groups_match:
                        accepted[slope_offset] = constants
                        accepted_slope_offsets[slope_offset] += 1
                exact_setup_count += bool(accepted)
                extent = capture_case.width if axis == 0 else capture_case.height
                delta = (
                    v1.float32_bits_fraction(endpoint.highBits)
                    - v1.float32_bits_fraction(endpoint.lowBits)
                )
                exact = delta / extent
                groups.append(
                    {
                        "case": capture_case.name,
                        "caseRole": capture_case.role,
                        "endpoint": endpoint.name,
                        "axis": axis,
                        "extent": extent,
                        "origin": (
                            capture_case.originX
                            if axis == 0
                            else capture_case.originY
                        ),
                        "slopeBits": f"0x{slope_bits:08x}",
                        "p27Phase": str(phase),
                        "exactSlope": str(exact),
                        "fixedInternal": internal.hex(),
                        "acceptedSlopeOffsets": {
                            str(offset): constants
                            for offset, constants in accepted.items()
                        },
                    }
                )

    return {
        "schema4FullSetupRecoverySchemaVersion": 1,
        "source": str(root),
        "targetEndpoints": sorted(pipeline.TARGET_ENDPOINTS),
        "slopeOffsets": list(SLOPE_OFFSETS),
        "constantOffsets": list(CONSTANT_OFFSETS),
        "setupCount": setup_count,
        "exactSetupCount": exact_setup_count,
        "acceptedSlopeOffsetCounts": {
            str(offset): count
            for offset, count in sorted(accepted_slope_offsets.items())
        },
        "groups": groups,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = analyze(arguments.root)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(rendered, end="")
    else:
        arguments.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
