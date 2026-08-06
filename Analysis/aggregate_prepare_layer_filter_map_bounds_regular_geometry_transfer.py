#!/usr/bin/env python3
"""Aggregate the 32-case regular geometry/profile Cartesian transfer."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from itertools import product
from pathlib import Path
from typing import Any

import validate_prepare_layer_filter_map_bounds_profile_transfer_retry as profile
import validate_prepare_layer_filter_map_bounds_regular_geometry_transfer as regular


AGGREGATE_SCHEMA_VERSION = 1
VALIDATION_FILE_NAME = (
    "prepare-layer-filter-map-bounds-regular-geometry-transfer-validation.json"
)
RESULT_ARTIFACT_PREFIX = "liquid-glass-filter-map-bounds-regular-geometry-result-"
EXPECTED_CASES = tuple(
    product(
        regular.EXPECTED_GEOMETRY_WIDTHS,
        profile.VALID_APPEARANCES,
        profile.VALID_DIRECTIONS,
    )
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} is not an object")
    return value


def artifact_directory(
    root: Path, geometry: str, appearance: str, direction: str
) -> Path:
    prefix = f"{RESULT_ARTIFACT_PREFIX}{geometry}-{appearance}-{direction}-"
    matches = [
        path
        for path in root.iterdir()
        if path.is_dir() and path.name.startswith(prefix)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"{geometry}/{appearance}/{direction} result artifact is not unique"
        )
    return matches[0]


def validate_result(
    path: Path, geometry: str, appearance: str, direction: str
) -> dict[str, Any]:
    result = mapping(json.loads(path.read_text(encoding="utf-8")), "validation")
    actual_profile = mapping(result.get("profile"), "profile")
    source = mapping(result.get("sourceBounds"), "source bounds")
    replay = mapping(result.get("floatingReplay"), "floating replay")
    sdf = mapping(result.get("sdfState"), "SDF state")
    endpoint = mapping(result.get("endpointYOffset"), "endpoint y offset")
    selection = mapping(result.get("structuralSelection"), "selection")
    sealed = mapping(result.get("sealedConclusion"), "sealed conclusion")
    expected_source = list(regular.expected_source_bounds(geometry))
    if (
        result.get(
            "prepareLayerFilterMapBoundsRegularGeometryTransferValidationSchemaVersion"
        )
        != regular.VALIDATION_SCHEMA_VERSION
        or result.get("conclusion") != "success"
        or actual_profile.get("material") != "regular"
        or actual_profile.get("appearance") != appearance
        or actual_profile.get("direction") != direction
        or actual_profile.get("geometry") != geometry
        or actual_profile.get("backingScaleFactor") != 1
        or source.get("f64") != expected_source
        or source.get("geometryWidth") != regular.EXPECTED_GEOMETRY_WIDTHS[geometry]
        or source.get("exactExpansionPerEdge") != regular.SOURCE_DOD_EXPANSION
        or source.get("geometryOrProducerOutputUsedToFitRule") is not False
        or replay.get("rectangleCount") != profile.EXPECTED_RECORD_COUNT
        or replay.get("componentCount") != profile.EXPECTED_RECORD_COUNT * 4
        or replay.get("exactRectangleCount") != profile.EXPECTED_RECORD_COUNT
        or replay.get("exactComponentCount") != profile.EXPECTED_RECORD_COUNT * 4
        or replay.get("mismatchedRectangleCount") != 0
        or replay.get("mismatchedComponentCount") != 0
        or replay.get("maximumAbsoluteErrorsXYWH") != [0.0, 0.0, 0.0, 0.0]
        or replay.get("maximumULPDistancesXYWH") != [0, 0, 0, 0]
        or replay.get("allRectanglesExact") is not True
        or replay.get("allComponentsExact") is not True
        or sdf.get("recordCount") != profile.EXPECTED_RECORD_COUNT
        or sdf.get("expectedParametersHex")
        != profile.EXPECTED_SDF_PARAMETERS_HEX["regular"]
        or endpoint.get("appliedRecordCount") != 1
        or selection.get("cropOrProducerValuesUsedForSelection") is not False
        or selection.get("twoStageRegularCropChainExactCount")
        != profile.EXPECTED_RECORD_COUNT
        or sealed.get("singleRegularGeometryProfileExactCropReplayPassed") is not True
        or sealed.get("regularGeometryProfileCartesianTransferPassed") is not False
        or sealed.get("regularUnseenGeometryTransferPassed") is not False
        or sealed.get("productionShaderAuthorized") is not False
        or sealed.get("liquidGlassParityEstablished") is not False
    ):
        raise ValueError(f"{geometry}/{appearance}/{direction} validation differs")
    inputs = mapping(result.get("inputs"), "inputs")
    for name in ("traceSHA256", "timelineSHA256"):
        value = inputs.get(name)
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(f"{geometry}/{appearance}/{direction} {name} differs")
    return {
        "geometry": geometry,
        "appearance": appearance,
        "direction": direction,
        "sourceBoundsF64": expected_source,
        "validationSHA256": sha256(path),
        "traceSHA256": inputs["traceSHA256"],
        "timelineSHA256": inputs["timelineSHA256"],
        "exactRectangleCount": replay["exactRectangleCount"],
        "exactComponentCount": replay["exactComponentCount"],
        "sdfStateRecordCount": sdf["recordCount"],
        "endpointYOffsetAppliedRecordCount": endpoint["appliedRecordCount"],
    }


def aggregate(root: Path, run_id: int, head_sha: str) -> dict[str, Any]:
    if run_id <= 0:
        raise ValueError("run ID differs")
    if len(head_sha) != 40 or any(
        character not in "0123456789abcdef" for character in head_sha
    ):
        raise ValueError("head SHA differs")
    cases = []
    for geometry, appearance, direction in EXPECTED_CASES:
        directory = artifact_directory(root, geometry, appearance, direction)
        path = directory / VALIDATION_FILE_NAME
        if not path.is_file():
            raise ValueError(
                f"{geometry}/{appearance}/{direction} validation is missing"
            )
        cases.append(validate_result(path, geometry, appearance, direction))

    rectangle_count = sum(record["exactRectangleCount"] for record in cases)
    component_count = sum(record["exactComponentCount"] for record in cases)
    sdf_state_count = sum(record["sdfStateRecordCount"] for record in cases)
    endpoint_count = sum(
        record["endpointYOffsetAppliedRecordCount"] for record in cases
    )
    if (
        len(cases) != 32
        or rectangle_count != 1024
        or component_count != 4096
        or sdf_state_count != 1024
        or endpoint_count != 32
    ):
        raise ValueError("regular geometry/profile matrix accounting differs")

    return {
        "prepareLayerFilterMapBoundsRegularGeometryTransferAggregateSchemaVersion": (
            AGGREGATE_SCHEMA_VERSION
        ),
        "classification": (
            "prospective zero-tolerance aggregate of eight unopened regular "
            "geometries crossed with light/dark and materialize/dematerialize"
        ),
        "conclusion": "success",
        "run": {"id": run_id, "headSHA": head_sha},
        "geometryCount": len(regular.EXPECTED_GEOMETRY_WIDTHS),
        "profilePerGeometryCount": 4,
        "caseCount": len(cases),
        "exactRectangleCount": rectangle_count,
        "exactComponentCount": component_count,
        "sdfStateRecordCount": sdf_state_count,
        "endpointYOffsetAppliedRecordCount": endpoint_count,
        "maximumULPDistance": 0,
        "maximumAbsoluteError": 0.0,
        "cases": cases,
        "sealedConclusion": {
            "regularGeometryProfileCartesianTransferPassed": True,
            "regularUnseenGeometryTransferPassed": True,
            "filterOpCropProfileTransferPassed": True,
            "currentShaderCapturedInputOpticalTransferPassed": False,
            "independentPrivateInputGenerationPassed": False,
            "opticalMaterialAppearanceDirectionTransferPassed": False,
            "physicalRetina2xAndColorTransferPassed": False,
            "independentWalleZeroByteFrameParityPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_root", type=Path)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = aggregate(arguments.artifact_root, arguments.run_id, arguments.head_sha)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
