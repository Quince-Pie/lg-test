#!/usr/bin/env python3
"""Validate the frozen Filter/SDF diagnostic at a 127-point geometry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import validate_prepare_layer_sdf_map_bounds_diagnostic as frozen


VALIDATION_SCHEMA_VERSION = 1
EXPECTED_GEOMETRY = "circle-127-center"


def validate(
    trace_path: Path, timeline_path: Path, inventory_path: Path
) -> dict[str, Any]:
    original_geometry = frozen.regular.EXPECTED_GEOMETRY
    original_configuration = frozen.EXPECTED_CONFIGURATION
    frozen.regular.EXPECTED_GEOMETRY = EXPECTED_GEOMETRY
    frozen.EXPECTED_CONFIGURATION = {
        **original_configuration,
        "geometry": EXPECTED_GEOMETRY,
    }
    try:
        result = frozen.validate(trace_path, timeline_path, inventory_path)
    finally:
        frozen.regular.EXPECTED_GEOMETRY = original_geometry
        frozen.EXPECTED_CONFIGURATION = original_configuration

    profile = result.get("profile")
    if not isinstance(profile, dict) or profile.get("geometry") != EXPECTED_GEOMETRY:
        raise ValueError("small-geometry diagnostic profile differs")

    result["prepareLayerFilterSDFSmallGeometryValidationSchemaVersion"] = (
        VALIDATION_SCHEMA_VERSION
    )
    result["classification"] = (
        "prospective output-blind small-geometry instruction diagnostic using "
        "the unchanged structural FilterOp/SDFOp selector; this discovers exact "
        "source, clip, SDF, and shadow arithmetic without transfer authority"
    )
    result["smallGeometryDiagnostic"] = {
        "geometry": EXPECTED_GEOMETRY,
        "selectedSampleIndex": 2,
        "filterAndSDFSelectorsChanged": False,
        "cropOrOutputValuesUsedForSelection": False,
        "sourceDODCandidateAcceptedBeforeCapture": False,
    }
    sealed = result["sealedConclusion"]
    sealed["smallGeometryFilterSDFDiagnosticPassed"] = True
    sealed["regularGeometryTransferPassed"] = False
    sealed["productionShaderAuthorized"] = False
    sealed["liquidGlassParityEstablished"] = False
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.trace, arguments.timeline, arguments.inventory)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
