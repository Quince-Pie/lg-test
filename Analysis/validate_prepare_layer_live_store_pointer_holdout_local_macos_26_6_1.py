#!/usr/bin/env python3
"""Validate the frozen unseen-geometry last-store Retina holdout."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import validate_prepare_layer_filter_map_bounds_profile_transfer_live_local_macos_26_6_1 as live


VALIDATION_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
EXPECTED_GEOMETRY = "circle-485-center"
EXPECTED_MATERIAL = "regular"
EXPECTED_APPEARANCE = "dark"
EXPECTED_DIRECTION = "materialize"
CALIBRATION_RESULT = Path(__file__).with_name(
    "prepare_layer_live_transport_d439d53_calibration_result.json"
)
CALIBRATION_RESULT_SHA256 = (
    "2939ee106bdebd362ef3c699cd660e78e7d1f98a2b1d5a44e2c2a745129f24e8"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    return value


def _preregistration(path: Path) -> dict[str, Any]:
    preregistration = _mapping(
        json.loads(path.read_text(encoding="utf-8")), "preregistration"
    )
    holdout = _mapping(preregistration.get("holdout"), "holdout")
    candidate = _mapping(preregistration.get("frozenCandidate"), "candidate")
    calibration = _mapping(
        preregistration.get("openedCalibrationEvidence"), "calibration"
    )
    if (
        preregistration.get(
            "prepareLayerLiveStorePointerHoldoutPreregistrationSchemaVersion"
        )
        != PREREGISTRATION_SCHEMA_VERSION
        or preregistration.get("runtimeOutcomeFrozenBeforeDispatch") is not None
        or holdout.get("geometry") != EXPECTED_GEOMETRY
        or holdout.get("material") != EXPECTED_MATERIAL
        or holdout.get("appearance") != EXPECTED_APPEARANCE
        or holdout.get("direction") != EXPECTED_DIRECTION
        or holdout.get("backingScaleFactor") != live.RETINA_BACKING_SCALE_FACTOR
        or holdout.get("targetOutputsOpenedAtFreeze") is not False
        or candidate.get("cropOrProducerValuesUsedForSelection") is not False
        or candidate.get("toleranceUsed") is not False
        or calibration.get("resultSHA256") != CALIBRATION_RESULT_SHA256
        or _sha256(CALIBRATION_RESULT) != CALIBRATION_RESULT_SHA256
    ):
        raise ValueError("unseen last-store preregistration differs")
    return preregistration


def validate(
    trace_path: Path, timeline_path: Path, preregistration_path: Path
) -> dict[str, Any]:
    preregistration = _preregistration(preregistration_path)
    result = live.validate(
        trace_path,
        timeline_path,
        EXPECTED_GEOMETRY,
        EXPECTED_MATERIAL,
        EXPECTED_APPEARANCE,
        EXPECTED_DIRECTION,
    )
    profile = _mapping(result.get("profile"), "profile")
    pointer = _mapping(result.get("liveStorePointerReuse"), "pointer reuse")
    replay = _mapping(result.get("floatingReplay"), "floating replay")
    if (
        profile
        != {
            "material": EXPECTED_MATERIAL,
            "appearance": EXPECTED_APPEARANCE,
            "direction": EXPECTED_DIRECTION,
            "geometry": EXPECTED_GEOMETRY,
            "backingScaleFactor": live.RETINA_BACKING_SCALE_FACTOR,
        }
        or pointer.get("recordCount") != 32
        or pointer.get("matchingStoreRecordCount", 0) < 33
        or pointer.get("pointerReuseRecordCount", 0) < 1
        or pointer.get("discardedEarlierMatchCount", 0) < 1
        or pointer.get("cropOrProducerValuesUsedForSelection") is not False
        or replay.get("rectangleCount") != 32
        or replay.get("componentCount") != 128
        or replay.get("exactRectangleCount") != 32
        or replay.get("exactComponentCount") != 128
        or replay.get("mismatchedRectangleCount") != 0
        or replay.get("mismatchedComponentCount") != 0
        or replay.get("maximumAbsoluteErrorsXYWH") != [0.0, 0.0, 0.0, 0.0]
        or replay.get("maximumULPDistancesXYWH") != [0, 0, 0, 0]
    ):
        raise ValueError("unseen last-store Retina holdout differs")

    result[
        "prepareLayerLiveStorePointerHoldoutLocalMacOS2661ValidationSchemaVersion"
    ] = VALIDATION_SCHEMA_VERSION
    result["classification"] = (
        "prospective unseen-geometry bit-exact transfer of the frozen "
        "last-matching-store rule and internal Retina crop replay"
    )
    inputs = _mapping(result.get("inputs"), "inputs")
    inputs["preregistrationSHA256"] = _sha256(preregistration_path)
    inputs["calibrationResultSHA256"] = CALIBRATION_RESULT_SHA256
    result["prospectiveHoldout"] = {
        "frozenAtUtc": preregistration["frozenAtUtc"],
        "geometryWasUnopenedAtFreeze": True,
        "targetOutputsOpenedAtFreeze": False,
        "toleranceUsed": False,
    }
    sealed = _mapping(result.get("sealedConclusion"), "sealed conclusion")
    sealed["knownProfileCalibrationOnly"] = False
    sealed["lastStorePointerReuseUnseenHoldoutPassed"] = True
    sealed["physicalRetina2xInternalCropGeometryTransferPassed"] = True
    sealed["selectedRegionOriginTransferPassed"] = False
    sealed["physicalRetina2xAndColorTransferPassed"] = False
    sealed["independentWalleZeroByteFrameParityPassed"] = False
    sealed["productionShaderAuthorized"] = False
    sealed["liquidGlassParityEstablished"] = False
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(
        arguments.trace, arguments.timeline, arguments.preregistration
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
