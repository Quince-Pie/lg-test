#!/usr/bin/env python3
"""Recover binary32 tile constants from every word in schema-4 residual setups."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import explore_schema4_endpoint_constant_pipeline as pipeline
import raster_tile_selector_model as v1
import raster_tile_selector_model_v8 as v8
import validate_raster_tile_phase_holdout as capture


type JsonObject = dict[str, Any]

OFFSET_RADIUS = 256


def intervals(values: list[int]) -> list[list[int]]:
    if not values:
        return []
    result: list[list[int]] = []
    lower = previous = values[0]
    for value in values[1:]:
        if value != previous + 1:
            result.append([lower, previous])
            lower = value
        previous = value
    result.append([lower, previous])
    return result


def analyze(root: Path) -> JsonObject:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    raw = (root / manifest["rasterTileNumerator"]["file"]).read_bytes()
    selector_table = v1.load_selector_table()
    setup_count = 0
    physical_failure_count = 0
    recovered_count = 0
    unique_count = 0
    offset_counts: Counter[int] = Counter()
    interval_counts: Counter[str] = Counter()
    failures: list[JsonObject] = []
    recovered: list[JsonObject] = []

    for case_index, capture_case in enumerate(capture.CASES):
        samples = capture.sample_positions(capture_case)
        for endpoint_index, endpoint in enumerate(capture.ENDPOINTS):
            if endpoint.name not in pipeline.TARGET_ENDPOINTS:
                continue
            groups: dict[tuple[int, int, int], list[object]] = defaultdict(list)
            for sample in samples:
                groups[(sample.axis, sample.primitive, sample.tile)].append(sample)
            for (axis, primitive, tile), group_samples in groups.items():
                actual = tuple(
                    pipeline.record_at(raw, case_index, endpoint_index, sample)
                    for sample in group_samples
                )
                if not actual or all(record == capture.SENTINEL for record in actual):
                    continue
                setup_count += 1
                slope_float = v8.determinant_slope(
                    capture_case,
                    endpoint,
                    axis=axis,
                    selector_table=selector_table,
                )
                physical_bits = v8.physical_constant_bits(
                    capture_case,
                    endpoint,
                    group_samples[0],
                    selector_table=selector_table,
                )

                def exact(offset: int) -> bool:
                    candidate_bits = physical_bits + offset
                    return all(
                        pipeline.predicted_record(
                            sample,
                            endpoint,
                            slope_float=slope_float,
                            constant_bits=candidate_bits,
                        )
                        == expected
                        for sample, expected in zip(
                            group_samples,
                            actual,
                            strict=True,
                        )
                    )

                if exact(0):
                    continue
                physical_failure_count += 1
                matching = [
                    offset
                    for offset in range(-OFFSET_RADIUS, OFFSET_RADIUS + 1)
                    if exact(offset)
                ]
                identity = {
                    "case": capture_case.name,
                    "caseRole": capture_case.role,
                    "endpoint": endpoint.name,
                    "axis": axis,
                    "primitive": primitive,
                    "tile": tile,
                    "physicalBits": f"0x{physical_bits:08x}",
                }
                if not matching:
                    if len(failures) < 128:
                        failures.append(identity)
                    continue
                recovered_count += 1
                unique_count += len(matching) == 1
                offset_counts.update(matching)
                matching_intervals = intervals(matching)
                interval_counts[str(matching_intervals)] += 1
                if len(recovered) < 256:
                    recovered.append(
                        {
                            **identity,
                            "matchingOffsets": matching,
                            "matchingOffsetIntervals": matching_intervals,
                        }
                    )

    return {
        "schema4FullConstantRecoverySchemaVersion": 1,
        "source": str(root),
        "targetEndpoints": sorted(pipeline.TARGET_ENDPOINTS),
        "offsetRadius": OFFSET_RADIUS,
        "setupCount": setup_count,
        "physicalFailureCount": physical_failure_count,
        "recoveredFailureCount": recovered_count,
        "unrecoveredFailureCount": physical_failure_count - recovered_count,
        "uniqueRecoveryCount": unique_count,
        "matchingOffsetCounts": {
            str(offset): count for offset, count in sorted(offset_counts.items())
        },
        "matchingIntervalCounts": dict(interval_counts.most_common()),
        "unrecoveredExamples": failures,
        "recoveredExamples": recovered,
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
