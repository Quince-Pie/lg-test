#!/usr/bin/env python3
"""Validate regular Filter/SDF crop transfer on frozen unseen geometries."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_prepare_layer_filter_map_bounds_profile_transfer_retry as profile


VALIDATION_SCHEMA_VERSION = 1
SOURCE_DOD_EXPANSION = 280.0
EXPECTED_GEOMETRY_WIDTHS = {
    "circle-127-center": 127,
    "circle-128-center": 128,
    "circle-255-center": 255,
    "circle-257-center": 257,
    "circle-511-center": 511,
    "circle-512-center": 512,
    "circle-1023-center": 1023,
    "circle-1024-center": 1024,
}


def expected_source_bounds(geometry: str) -> tuple[float, float, float, float]:
    try:
        width = EXPECTED_GEOMETRY_WIDTHS[geometry]
    except KeyError as error:
        raise ValueError("expected regular geometry differs") from error
    extent = float(width) + 2.0 * SOURCE_DOD_EXPANSION
    return (-SOURCE_DOD_EXPANSION, -SOURCE_DOD_EXPANSION, extent, extent)


def validate_recursive_source(
    producer_records: Sequence[Mapping[str, Any]], geometry: str
) -> tuple[float, float, float, float]:
    source = expected_source_bounds(geometry)
    expected_child = (0.0, 0.0, source[2], source[3])
    expected_hex = profile.exact.f64_hex(expected_child)
    for record in producer_records:
        role = profile.exact.mapping(
            record.get("roleIntermediates"), "regular geometry role"
        )
        child = profile.exact.rect(
            role.get("recursiveChildF64"), "regular geometry recursive child"
        )
        if profile.exact.f64_hex(child) != expected_hex:
            raise ValueError("regular geometry recursive child differs")
    return source


def validate(
    trace_path: Path,
    timeline_path: Path,
    expected_geometry: str,
    expected_appearance: str,
    expected_direction: str,
) -> dict[str, Any]:
    expected = expected_source_bounds(expected_geometry)
    original_source_bounds = profile.source_bounds

    def frozen_regular_source_bounds(
        material: str, producer_records: Sequence[Mapping[str, Any]]
    ) -> tuple[float, float, float, float]:
        if material != "regular":
            raise ValueError("regular geometry material differs")
        return validate_recursive_source(producer_records, expected_geometry)

    profile.source_bounds = frozen_regular_source_bounds
    try:
        result = profile.validate(
            trace_path,
            timeline_path,
            expected_geometry,
            "regular",
            expected_appearance,
            expected_direction,
        )
    finally:
        profile.source_bounds = original_source_bounds

    source = profile.exact.mapping(result.get("sourceBounds"), "source bounds")
    if profile.exact.f64_hex(source.get("f64")) != profile.exact.f64_hex(expected):
        raise ValueError("regular geometry source DOD differs")

    result[
        "prepareLayerFilterMapBoundsRegularGeometryTransferValidationSchemaVersion"
    ] = VALIDATION_SCHEMA_VERSION
    result["classification"] = (
        "prospectively frozen target-output-blind exact regular Filter/SDF crop "
        "transfer on a previously unopened geometry/profile combination; the "
        "source DOD is predicted from geometry width and the decoded exact "
        "280-point expansion before target output"
    )
    source["rule"] = (
        "[-280, -280, geometryWidth + 560, geometryWidth + 560], with the "
        "recursive child required to be [0, 0, geometryWidth + 560, "
        "geometryWidth + 560]"
    )
    source["geometryWidth"] = EXPECTED_GEOMETRY_WIDTHS[expected_geometry]
    source["exactExpansionPerEdge"] = SOURCE_DOD_EXPANSION
    source["geometryOrProducerOutputUsedToFitRule"] = False

    sealed = profile.exact.mapping(result.get("sealedConclusion"), "sealed conclusion")
    sealed["singleRegularGeometryProfileExactCropReplayPassed"] = True
    sealed["regularGeometryProfileCartesianTransferPassed"] = False
    sealed["regularUnseenGeometryTransferPassed"] = False
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--expected-geometry", required=True)
    parser.add_argument(
        "--expected-appearance", required=True, choices=profile.VALID_APPEARANCES
    )
    parser.add_argument(
        "--expected-direction", required=True, choices=profile.VALID_DIRECTIONS
    )
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(
        arguments.trace,
        arguments.timeline,
        arguments.expected_geometry,
        arguments.expected_appearance,
        arguments.expected_direction,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
