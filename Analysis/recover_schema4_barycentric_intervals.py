#!/usr/bin/env python3
"""Intersect broad-endpoint center outputs into per-sample weight intervals."""

import argparse
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

import explore_schema4_barycentric_composition as composition
import raster_tile_selector_model as v1
import validate_raster_tile_phase_holdout as capture


def record_at(
    raw: bytes,
    case_index: int,
    endpoint_index: int,
    sample: object,
) -> tuple[int, ...]:
    record_index = (
        case_index * len(capture.ENDPOINTS) + endpoint_index
    ) * capture.SLOT_COUNT + sample.slot
    return capture.RECORD.unpack_from(raw, record_index * capture.RECORD.size)


def analyze(root: Path) -> dict[str, object]:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    raw = (root / manifest["rasterTileNumerator"]["file"]).read_bytes()
    selector_table = v1.load_selector_table()
    endpoint_indices = [
        (index, endpoint)
        for index, endpoint in enumerate(capture.ENDPOINTS)
        if endpoint.name in composition.TARGET_ENDPOINTS
    ]
    control_index, control = next(
        (index, endpoint)
        for index, endpoint in enumerate(capture.ENDPOINTS)
        if endpoint.name == "zero-to-one"
    )
    records = 0
    empty_intersections = 0
    p36_inside = 0
    exact_geometry_inside = 0
    candidate_side: Counter[str] = Counter()
    width_exponents: Counter[int] = Counter()
    examples: list[dict[str, object]] = []

    for case_index, capture_case in enumerate(capture.CASES):
        for sample in capture.sample_positions(capture_case):
            control_record = record_at(
                raw,
                case_index,
                control_index,
                sample,
            )
            if control_record == capture.SENTINEL:
                continue
            records += 1
            center_bits = control_record[capture.PULL_COUNT]
            lower = v1.float32_bits_fraction(center_bits)
            upper = v1.float32_bits_fraction(center_bits + 1)
            constraints: list[tuple[str, Fraction, Fraction]] = [
                ("zero-to-one", lower, upper)
            ]
            for endpoint_index, endpoint in endpoint_indices:
                actual = record_at(
                    raw,
                    case_index,
                    endpoint_index,
                    sample,
                )
                bits = actual[capture.PULL_COUNT]
                value_lower = v1.float32_bits_fraction(bits)
                value_upper = v1.float32_bits_fraction(bits + 1)
                low = v1.float32_bits_fraction(endpoint.lowBits)
                delta = (
                    v1.float32_bits_fraction(endpoint.highBits) - low
                )
                constraints.append(
                    (
                        endpoint.name,
                        (value_lower - low) / delta,
                        (value_upper - low) / delta,
                    )
                )
            intersection_lower = max(value[1] for value in constraints)
            intersection_upper = min(value[2] for value in constraints)
            left, right = composition.control_pair(
                capture_case,
                control,
                sample,
                selector_table,
            )
            coordinate = sample.x if sample.axis == 0 else sample.y
            local_pixel = coordinate - sample.tile * capture.TILE_SIZE
            candidate = right if local_pixel & 1 else left
            extent = (
                capture_case.width
                if sample.axis == 0
                else capture_case.height
            )
            origin = (
                capture_case.originX
                if sample.axis == 0
                else capture_case.originY
            )
            exact_geometry = Fraction(2 * (coordinate - origin) + 1, 2 * extent)

            if intersection_lower >= intersection_upper:
                empty_intersections += 1
                if len(examples) < 64:
                    examples.append(
                        {
                            "case": capture_case.name,
                            "axis": sample.axis,
                            "primitive": sample.primitive,
                            "tile": sample.tile,
                            "edge": sample.edge,
                            "coordinate": coordinate,
                            "intersectionEmpty": True,
                            "lower": str(intersection_lower),
                            "upper": str(intersection_upper),
                            "constraints": [
                                {
                                    "endpoint": name,
                                    "lower": str(value_lower),
                                    "upper": str(value_upper),
                                }
                                for name, value_lower, value_upper in constraints
                            ],
                        }
                    )
                continue

            width = intersection_upper - intersection_lower
            width_exponents[v1.floor_binary_exponent(width)] += 1
            candidate_inside = intersection_lower <= candidate < intersection_upper
            exact_inside = (
                intersection_lower <= exact_geometry < intersection_upper
            )
            p36_inside += candidate_inside
            exact_geometry_inside += exact_inside
            candidate_side[
                "inside"
                if candidate_inside
                else "below"
                if candidate < intersection_lower
                else "above"
            ] += 1
            if (not candidate_inside or not exact_inside) and len(examples) < 64:
                examples.append(
                    {
                        "case": capture_case.name,
                        "axis": sample.axis,
                        "primitive": sample.primitive,
                        "tile": sample.tile,
                        "edge": sample.edge,
                        "coordinate": coordinate,
                        "intersectionEmpty": False,
                        "lower": str(intersection_lower),
                        "upper": str(intersection_upper),
                        "width": str(width),
                        "p36Candidate": str(candidate),
                        "p36Inside": candidate_inside,
                        "exactGeometry": str(exact_geometry),
                        "exactGeometryInside": exact_inside,
                    }
                )

    nonempty = records - empty_intersections
    return {
        "recordCount": records,
        "emptyIntersectionCount": empty_intersections,
        "nonemptyIntersectionCount": nonempty,
        "p36CandidateInsideCount": p36_inside,
        "exactGeometryInsideCount": exact_geometry_inside,
        "candidateSideCounts": dict(sorted(candidate_side.items())),
        "intersectionWidthBinaryExponentCounts": dict(
            sorted(width_exponents.items())
        ),
        "examples": examples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(analyze(arguments.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
