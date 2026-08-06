#!/usr/bin/env python3
"""Aggregate eight exact profile-transfer retry validations."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from itertools import product
from pathlib import Path
from typing import Any

import validate_prepare_layer_filter_map_bounds_profile_transfer_retry as validator


AGGREGATE_SCHEMA_VERSION = 1
VALIDATION_FILE_NAME = (
    "prepare-layer-filter-map-bounds-profile-transfer-retry-validation.json"
)
RESULT_ARTIFACT_PREFIX = "liquid-glass-filter-map-bounds-profile-retry-result-"
EXPECTED_PROFILES = tuple(
    product(
        validator.VALID_MATERIALS,
        validator.VALID_APPEARANCES,
        validator.VALID_DIRECTIONS,
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
    root: Path, material: str, appearance: str, direction: str
) -> Path:
    prefix = f"{RESULT_ARTIFACT_PREFIX}{material}-{appearance}-{direction}-"
    matches = [
        path
        for path in root.iterdir()
        if path.is_dir() and path.name.startswith(prefix)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"{material}/{appearance}/{direction} result artifact is not unique"
        )
    return matches[0]


def validate_result(
    path: Path, material: str, appearance: str, direction: str
) -> dict[str, Any]:
    result = mapping(json.loads(path.read_text(encoding="utf-8")), "validation")
    profile = mapping(result.get("profile"), "profile")
    replay = mapping(result.get("floatingReplay"), "floating replay")
    sdf = mapping(result.get("sdfState"), "SDF state")
    endpoint = mapping(result.get("endpointYOffset"), "endpoint y offset")
    sealed = mapping(result.get("sealedConclusion"), "sealed conclusion")
    expected_endpoint_count = 1 if material == "regular" else 0
    if (
        result.get(
            "prepareLayerFilterMapBoundsProfileTransferRetryValidationSchemaVersion"
        )
        != validator.VALIDATION_SCHEMA_VERSION
        or result.get("conclusion") != "success"
        or profile.get("material") != material
        or profile.get("appearance") != appearance
        or profile.get("direction") != direction
        or profile.get("geometry") != "circle-800-center"
        or profile.get("backingScaleFactor") != 1
        or replay.get("rectangleCount") != validator.EXPECTED_RECORD_COUNT
        or replay.get("componentCount") != validator.EXPECTED_RECORD_COUNT * 4
        or replay.get("exactRectangleCount") != validator.EXPECTED_RECORD_COUNT
        or replay.get("exactComponentCount") != validator.EXPECTED_RECORD_COUNT * 4
        or replay.get("mismatchedRectangleCount") != 0
        or replay.get("mismatchedComponentCount") != 0
        or replay.get("maximumAbsoluteErrorsXYWH") != [0.0, 0.0, 0.0, 0.0]
        or replay.get("maximumULPDistancesXYWH") != [0, 0, 0, 0]
        or replay.get("allRectanglesExact") is not True
        or replay.get("allComponentsExact") is not True
        or sdf.get("recordCount") != validator.EXPECTED_RECORD_COUNT
        or sdf.get("expectedParametersHex")
        != validator.EXPECTED_SDF_PARAMETERS_HEX[material]
        or endpoint.get("appliedRecordCount") != expected_endpoint_count
        or sealed.get("singleProfileExactCropReplayPassed") is not True
        or sealed.get("completeProfileMatrixPassed") is not False
        or sealed.get("filterOpCropProfileTransferPassed") is not False
        or sealed.get("productionShaderAuthorized") is not False
        or sealed.get("liquidGlassParityEstablished") is not False
    ):
        raise ValueError(f"{material}/{appearance}/{direction} validation differs")
    inputs = mapping(result.get("inputs"), "inputs")
    for name in ("traceSHA256", "timelineSHA256"):
        value = inputs.get(name)
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(f"{material}/{appearance}/{direction} {name} differs")
    return {
        "material": material,
        "appearance": appearance,
        "direction": direction,
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
    profiles = []
    for material, appearance, direction in EXPECTED_PROFILES:
        directory = artifact_directory(root, material, appearance, direction)
        path = directory / VALIDATION_FILE_NAME
        if not path.is_file():
            raise ValueError(
                f"{material}/{appearance}/{direction} validation is missing"
            )
        profiles.append(validate_result(path, material, appearance, direction))

    rectangle_count = sum(record["exactRectangleCount"] for record in profiles)
    component_count = sum(record["exactComponentCount"] for record in profiles)
    sdf_state_count = sum(record["sdfStateRecordCount"] for record in profiles)
    endpoint_count = sum(
        record["endpointYOffsetAppliedRecordCount"] for record in profiles
    )
    if (
        len(profiles) != 8
        or rectangle_count != 256
        or component_count != 1024
        or sdf_state_count != 256
        or endpoint_count != 4
    ):
        raise ValueError("complete profile matrix accounting differs")

    return {
        "prepareLayerFilterMapBoundsProfileTransferRetryAggregateSchemaVersion": (
            AGGREGATE_SCHEMA_VERSION
        ),
        "classification": (
            "prospective zero-tolerance aggregate of the complete clear/regular "
            "by light/dark by materialize/dematerialize crop-transfer matrix"
        ),
        "conclusion": "success",
        "run": {"id": run_id, "headSHA": head_sha},
        "profileCount": len(profiles),
        "exactRectangleCount": rectangle_count,
        "exactComponentCount": component_count,
        "sdfStateRecordCount": sdf_state_count,
        "endpointYOffsetAppliedRecordCount": endpoint_count,
        "maximumULPDistance": 0,
        "maximumAbsoluteError": 0.0,
        "profiles": profiles,
        "sealedConclusion": {
            "completeProfileMatrixPassed": True,
            "filterOpCropProfileTransferPassed": True,
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
