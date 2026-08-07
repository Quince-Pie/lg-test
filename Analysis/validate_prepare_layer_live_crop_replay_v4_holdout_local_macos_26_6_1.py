#!/usr/bin/env python3
"""Validate the frozen runtime-unseen circle-498 live crop-replay v4 holdout."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import validate_prepare_layer_live_crop_replay_v3_split_holdout_local_macos_26_6_1 as split
import validate_prepare_layer_live_crop_replay_v4_local_macos_26_6_1 as v4


VALIDATION_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
EXPECTED_GEOMETRY = "circle-498-center"
EXPECTED_MATERIAL = "regular"
EXPECTED_APPEARANCE = "dark"
EXPECTED_DIRECTION = "materialize"
V3_FALSIFICATION_RESULT = Path(__file__).with_name(
    "prepare_layer_live_crop_replay_v3_7f0807a_split_holdout_falsification_result.json"
)
V3_FALSIFICATION_RESULT_SHA256 = (
    "4c83339bd7573860376c49ddb6e3cd2a53b40ecbd23434aeecb3dc374b21fa32"
)
V4_REANALYSIS_RESULT = Path(__file__).with_name(
    "prepare_layer_live_crop_replay_v4_reanalysis_result.json"
)
V4_REANALYSIS_RESULT_SHA256 = (
    "496bb20efd6aa0ef7a1727536ae2c560c17b563a8b01a2205d4acd6917e24efc"
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
            "prepareLayerLiveCropReplayV4HoldoutPreregistrationSchemaVersion"
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
        or candidate.get("publicBleedConvertedToBinary32ExactlyOnce") is not True
        or candidate.get("endpointOffsetGroupedIntoYTranslation") is not True
        or candidate.get("pointerReuseEventRequired") is not False
        or candidate.get("pointerReuseBranchValidatedWhenPresent") is not True
        or candidate.get("cropOrProducerValuesUsedForSelection") is not False
        or candidate.get("targetOutputsUsed") is not False
        or candidate.get("toleranceUsed") is not False
        or evidence.get("v3FalsificationResultSHA256") != V3_FALSIFICATION_RESULT_SHA256
        or evidence.get("v4ReanalysisResultSHA256") != V4_REANALYSIS_RESULT_SHA256
        or _sha256(V3_FALSIFICATION_RESULT) != V3_FALSIFICATION_RESULT_SHA256
        or _sha256(V4_REANALYSIS_RESULT) != V4_REANALYSIS_RESULT_SHA256
    ):
        raise ValueError("unseen v4 crop preregistration differs")
    repository = path.parent.parent
    frozen_files = preregistration.get("frozenFiles")
    if not isinstance(frozen_files, list) or not frozen_files:
        raise ValueError("unseen v4 frozen-file inventory differs")
    for raw_record in frozen_files:
        record = _mapping(raw_record, "frozen file")
        relative = record.get("path")
        digest = record.get("sha256")
        if (
            not isinstance(relative, str)
            or not isinstance(digest, str)
            or _sha256(repository / relative) != digest
        ):
            raise ValueError("unseen v4 frozen file differs")
    return preregistration


def validate(
    trace_path: Path, timeline_path: Path, preregistration_path: Path
) -> dict[str, Any]:
    preregistration = _preregistration(preregistration_path)
    result = v4.validate(
        trace_path,
        timeline_path,
        EXPECTED_GEOMETRY,
        EXPECTED_MATERIAL,
        EXPECTED_APPEARANCE,
        EXPECTED_DIRECTION,
    )
    profile = _mapping(result.get("profile"), "profile")
    pointer = _mapping(result.get("liveStorePointerReuse"), "pointer reuse")
    pointer_gate = split._validate_pointer_plan(pointer)
    identity = _mapping(result.get("liveCropArithmeticCodeIdentity"), "code identity")
    model = _mapping(result.get("regularGeometryModel"), "geometry model")
    sdf = _mapping(result.get("sdfState"), "SDF state")
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
        or model.get("binary32ConversionCount") != 1
        or model.get("cropOrProducerValuesUsed") is not False
        or sdf.get("endpointOffsetGroupedIntoYTranslation") is not True
        or replay.get("rectangleCount") != 32
        or replay.get("componentCount") != 128
        or replay.get("exactRectangleCount") != 32
        or replay.get("exactComponentCount") != 128
        or replay.get("mismatchedRectangleCount") != 0
        or replay.get("mismatchedComponentCount") != 0
        or replay.get("maximumAbsoluteErrorsXYWH") != [0.0, 0.0, 0.0, 0.0]
        or replay.get("maximumULPDistancesXYWH") != [0, 0, 0, 0]
    ):
        raise ValueError("unseen v4 live crop holdout differs")

    result[
        "prepareLayerLiveCropReplayV4HoldoutLocalMacOS2661ValidationSchemaVersion"
    ] = VALIDATION_SCHEMA_VERSION
    result["classification"] = (
        "prospective runtime-unseen circle-498 transfer of frozen v4 crop "
        "arithmetic, including endpoint-translation grouping; last-store "
        "selection is exact for every record and pointer reuse is validated "
        "when present without requiring allocator branch occurrence"
    )
    inputs = _mapping(result.get("inputs"), "inputs")
    inputs["preregistrationSHA256"] = _sha256(preregistration_path)
    inputs["v3FalsificationResultSHA256"] = V3_FALSIFICATION_RESULT_SHA256
    inputs["v4ReanalysisResultSHA256"] = V4_REANALYSIS_RESULT_SHA256
    result["prospectiveHoldout"] = {
        "frozenAtUtc": preregistration["frozenAtUtc"],
        "geometryWasRuntimeUnseenAtFreeze": True,
        "targetOutputsOpenedAtFreeze": False,
        "targetOutputsUsed": False,
        "toleranceUsed": False,
    }
    result["splitPointerCoverageGate"] = pointer_gate
    sealed = _mapping(result.get("sealedConclusion"), "sealed conclusion")
    sealed["knownProfileCalibrationOnly"] = False
    sealed["lastStoreSelectionUnseenHoldoutPassed"] = True
    sealed["pointerReuseBranchExecutedInThisHoldout"] = pointer_gate[
        "pointerReuseBranchExecuted"
    ]
    sealed["physicalRetina2xInternalCropReplayPassed"] = True
    sealed["v3UnseenGeometryTransferPassed"] = False
    sealed["v3UnseenGeometryTransferFalsified"] = True
    sealed["v4OpenedGeometryReplayPassed"] = True
    sealed["v4UnseenGeometryArithmeticPassed"] = True
    sealed["v4UnseenGeometryTransferPassed"] = True
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
