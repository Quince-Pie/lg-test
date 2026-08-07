#!/usr/bin/env python3
"""Validate the frozen unseen circle-487 live crop-replay v2 holdout."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import validate_prepare_layer_live_crop_replay_v2_local_macos_26_6_1 as v2


VALIDATION_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
EXPECTED_GEOMETRY = "circle-487-center"
EXPECTED_MATERIAL = "regular"
EXPECTED_APPEARANCE = "dark"
EXPECTED_DIRECTION = "materialize"
CALIBRATION_RESULT = Path(__file__).with_name(
    "prepare_layer_live_crop_replay_v2_39b462c_calibration_result.json"
)
CALIBRATION_RESULT_SHA256 = (
    "5627fa05d11bfd49ba2f3ced1169d9c701f5c8cd134cdecd4dceaa65a3d4d4ac"
)
REANALYSIS_RESULT = Path(__file__).with_name(
    "prepare_layer_live_crop_replay_v2_reanalysis_result.json"
)
REANALYSIS_RESULT_SHA256 = (
    "cc85c131e29d6f91434c87872778d85f347fa7ae4301ef118d29559ff06732ec"
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
    evidence = _mapping(preregistration.get("openedEvidence"), "opened evidence")
    if (
        preregistration.get(
            "prepareLayerLiveCropReplayV2HoldoutPreregistrationSchemaVersion"
        )
        != PREREGISTRATION_SCHEMA_VERSION
        or preregistration.get("runtimeOutcomeFrozenBeforeDispatch") is not None
        or holdout.get("geometry") != EXPECTED_GEOMETRY
        or holdout.get("material") != EXPECTED_MATERIAL
        or holdout.get("appearance") != EXPECTED_APPEARANCE
        or holdout.get("direction") != EXPECTED_DIRECTION
        or holdout.get("backingScaleFactor") != 2
        or holdout.get("targetOutputsOpenedAtFreeze") is not False
        or holdout.get("runtimeEvidenceMatchCountAtFreeze") != 0
        or candidate.get("cropOrProducerValuesUsedForSelection") is not False
        or candidate.get("targetOutputsUsed") is not False
        or candidate.get("toleranceUsed") is not False
        or evidence.get("calibrationResultSHA256") != CALIBRATION_RESULT_SHA256
        or evidence.get("openedReanalysisResultSHA256") != REANALYSIS_RESULT_SHA256
        or _sha256(CALIBRATION_RESULT) != CALIBRATION_RESULT_SHA256
        or _sha256(REANALYSIS_RESULT) != REANALYSIS_RESULT_SHA256
    ):
        raise ValueError("unseen v2 crop preregistration differs")
    repository = path.parent.parent
    frozen_files = preregistration.get("frozenFiles")
    if not isinstance(frozen_files, list) or not frozen_files:
        raise ValueError("unseen v2 frozen-file inventory differs")
    for raw_record in frozen_files:
        record = _mapping(raw_record, "frozen file")
        relative = record.get("path")
        digest = record.get("sha256")
        if (
            not isinstance(relative, str)
            or not isinstance(digest, str)
            or _sha256(repository / relative) != digest
        ):
            raise ValueError("unseen v2 frozen file differs")
    return preregistration


def validate(
    trace_path: Path, timeline_path: Path, preregistration_path: Path
) -> dict[str, Any]:
    preregistration = _preregistration(preregistration_path)
    result = v2.validate(
        trace_path,
        timeline_path,
        EXPECTED_GEOMETRY,
        EXPECTED_MATERIAL,
        EXPECTED_APPEARANCE,
        EXPECTED_DIRECTION,
    )
    profile = _mapping(result.get("profile"), "profile")
    pointer = _mapping(result.get("liveStorePointerReuse"), "pointer reuse")
    identity = _mapping(result.get("liveCropArithmeticCodeIdentity"), "code identity")
    replay = _mapping(result.get("floatingReplay"), "floating replay")
    if (
        profile
        != {
            "material": EXPECTED_MATERIAL,
            "appearance": EXPECTED_APPEARANCE,
            "direction": EXPECTED_DIRECTION,
            "geometry": EXPECTED_GEOMETRY,
            "backingScaleFactor": 2,
        }
        or identity.get("embeddedInTrace") is not True
        or identity.get("recordCount") != 6
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
        raise ValueError("unseen v2 live crop holdout differs")

    result[
        "prepareLayerLiveCropReplayV2HoldoutLocalMacOS2661ValidationSchemaVersion"
    ] = VALIDATION_SCHEMA_VERSION
    result["classification"] = (
        "prospective runtime-unseen circle-487 transfer of the frozen live-code "
        "authenticated v2 regular crop arithmetic and last-store pointer rule"
    )
    inputs = _mapping(result.get("inputs"), "inputs")
    inputs["preregistrationSHA256"] = _sha256(preregistration_path)
    inputs["calibrationResultSHA256"] = CALIBRATION_RESULT_SHA256
    inputs["openedReanalysisResultSHA256"] = REANALYSIS_RESULT_SHA256
    result["prospectiveHoldout"] = {
        "frozenAtUtc": preregistration["frozenAtUtc"],
        "geometryWasRuntimeUnseenAtFreeze": True,
        "targetOutputsOpenedAtFreeze": False,
        "targetOutputsUsed": False,
        "toleranceUsed": False,
    }
    sealed = _mapping(result.get("sealedConclusion"), "sealed conclusion")
    sealed["knownProfileCalibrationOnly"] = False
    sealed["lastStorePointerReuseUnseenHoldoutPassed"] = True
    sealed["physicalRetina2xInternalCropReplayPassed"] = True
    sealed["v2OpenedGeometryReplayPassed"] = True
    sealed["v2UnseenGeometryTransferPassed"] = True
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
    result = validate(arguments.trace, arguments.timeline, arguments.preregistration)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
