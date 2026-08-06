#!/usr/bin/env python3
"""Validate exact FilterOp replay for one frozen material/profile transfer."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import validate_prepare_layer_crop_transfer as crop_validator
import validate_prepare_layer_filter_map_bounds_blind_replay as blind_validator


VALIDATION_SCHEMA_VERSION = 1
VALID_MATERIALS = ("clear", "regular")
VALID_APPEARANCES = ("light", "dark")
VALID_DIRECTIONS = ("materialize", "dematerialize")


def require_profile(
    timeline: Mapping[str, Any],
    expected_material: str,
    expected_appearance: str,
    expected_direction: str,
) -> None:
    if (
        timeline.get("material") != expected_material
        or timeline.get("appearance") != expected_appearance
        or timeline.get("direction") != expected_direction
    ):
        raise ValueError("timeline profile metadata differs")


def validate(
    trace_path: Path,
    timeline_path: Path,
    expected_geometry: str,
    expected_material: str,
    expected_appearance: str,
    expected_direction: str,
) -> dict[str, Any]:
    if expected_material not in VALID_MATERIALS:
        raise ValueError("expected material differs")
    if expected_appearance not in VALID_APPEARANCES:
        raise ValueError("expected appearance differs")
    if expected_direction not in VALID_DIRECTIONS:
        raise ValueError("expected direction differs")

    original_validate_timeline = crop_validator.validate_timeline

    def validate_profile_timeline(
        timeline: Mapping[str, Any], geometry: str
    ) -> tuple[Mapping[str, Any], list[Any]]:
        require_profile(
            timeline,
            expected_material,
            expected_appearance,
            expected_direction,
        )
        normalized = dict(timeline)
        normalized["material"] = "clear"
        normalized["appearance"] = "light"
        normalized["direction"] = "materialize"
        return original_validate_timeline(normalized, geometry)

    crop_validator.validate_timeline = validate_profile_timeline
    try:
        result = blind_validator.validate(trace_path, timeline_path, expected_geometry)
    finally:
        crop_validator.validate_timeline = original_validate_timeline

    result["prepareLayerFilterMapBoundsProfileTransferValidationSchemaVersion"] = (
        VALIDATION_SCHEMA_VERSION
    )
    result["classification"] = (
        "prospectively frozen profile-transfer exact binary64 FilterOp replay; "
        "the actual material, appearance, and direction are authenticated before "
        "the unchanged clear/light/materialize structural validator is reused"
    )
    result["profile"] = {
        "material": expected_material,
        "appearance": expected_appearance,
        "direction": expected_direction,
        "geometry": expected_geometry,
        "backingScaleFactor": 1,
    }
    result["metadataAdapter"] = {
        "actualProfileAuthenticatedBeforeNormalization": True,
        "onlyMaterialAppearanceDirectionNormalized": True,
        "traceBytesChanged": False,
        "timelineBytesChanged": False,
        "cropOrProducerValuesInspected": False,
    }
    result["sealedConclusion"]["singleProfileExactCropReplayPassed"] = True
    result["sealedConclusion"]["completeProfileMatrixPassed"] = False
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--expected-geometry", required=True)
    parser.add_argument("--expected-material", required=True, choices=VALID_MATERIALS)
    parser.add_argument(
        "--expected-appearance", required=True, choices=VALID_APPEARANCES
    )
    parser.add_argument("--expected-direction", required=True, choices=VALID_DIRECTIONS)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(
        arguments.trace,
        arguments.timeline,
        arguments.expected_geometry,
        arguments.expected_material,
        arguments.expected_appearance,
        arguments.expected_direction,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
