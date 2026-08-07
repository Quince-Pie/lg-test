#!/usr/bin/env python3
"""Validate the frozen circle-497 v3 holdout with split branch coverage."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import validate_prepare_layer_live_crop_replay_v3_local_macos_26_6_1 as v3


VALIDATION_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
EXPECTED_GEOMETRY = "circle-497-center"
EXPECTED_MATERIAL = "regular"
EXPECTED_APPEARANCE = "dark"
EXPECTED_DIRECTION = "materialize"
V3_OPENED_OUTCOME_RESULT = Path(__file__).with_name(
    "prepare_layer_live_crop_replay_v3_a2ff533_holdout_outcome_result.json"
)
V3_OPENED_OUTCOME_RESULT_SHA256 = (
    "12e0c95afa4d87a42c76de98004417f6901b85e0ed13db02d7587bbca0f5b3b2"
)
V3_REANALYSIS_RESULT = Path(__file__).with_name(
    "prepare_layer_live_crop_replay_v3_reanalysis_result.json"
)
V3_REANALYSIS_RESULT_SHA256 = (
    "cfbd34542d871fd93fd56bbe3006ef1a1ebc56d42e296c0c847f67dd96208131"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    return value


def _sequence(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} is not an array")
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
            "prepareLayerLiveCropReplayV3SplitHoldoutPreregistrationSchemaVersion"
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
        or candidate.get("pointerReuseEventRequired") is not False
        or candidate.get("pointerReuseBranchValidatedWhenPresent") is not True
        or candidate.get("cropOrProducerValuesUsedForSelection") is not False
        or candidate.get("targetOutputsUsed") is not False
        or candidate.get("toleranceUsed") is not False
        or evidence.get("v3OpenedOutcomeResultSHA256")
        != V3_OPENED_OUTCOME_RESULT_SHA256
        or evidence.get("v3ReanalysisResultSHA256") != V3_REANALYSIS_RESULT_SHA256
        or _sha256(V3_OPENED_OUTCOME_RESULT) != V3_OPENED_OUTCOME_RESULT_SHA256
        or _sha256(V3_REANALYSIS_RESULT) != V3_REANALYSIS_RESULT_SHA256
    ):
        raise ValueError("unseen v3 split preregistration differs")
    repository = path.parent.parent
    frozen_files = preregistration.get("frozenFiles")
    if not isinstance(frozen_files, list) or not frozen_files:
        raise ValueError("unseen v3 split frozen-file inventory differs")
    for raw_record in frozen_files:
        record = _mapping(raw_record, "frozen file")
        relative = record.get("path")
        digest = record.get("sha256")
        if (
            not isinstance(relative, str)
            or not isinstance(digest, str)
            or _sha256(repository / relative) != digest
        ):
            raise ValueError("unseen v3 split frozen file differs")
    return preregistration


def _validate_pointer_plan(pointer: dict[str, Any]) -> dict[str, Any]:
    records = _sequence(pointer.get("records"), "pointer records")
    if len(records) != 32:
        raise ValueError("unseen v3 split pointer record count differs")
    matching_count = 0
    discarded_count = 0
    reuse_count = 0
    for raw_record in records:
        record = _mapping(raw_record, "pointer record")
        matching = _sequence(
            record.get("matchingStoreRecordIndices"), "matching stores"
        )
        discarded = _sequence(
            record.get("discardedEarlierMatchingStoreRecordIndices"),
            "discarded stores",
        )
        if (
            not matching
            or matching != sorted(matching)
            or record.get("selectedStoreRecordIndex") != matching[-1]
            or discarded != matching[:-1]
        ):
            raise ValueError("unseen v3 split last-store selection differs")
        matching_count += len(matching)
        discarded_count += len(discarded)
        reuse_count += bool(discarded)
    if (
        pointer.get("recordCount") != 32
        or pointer.get("matchingStoreRecordCount") != matching_count
        or pointer.get("pointerReuseRecordCount") != reuse_count
        or pointer.get("discardedEarlierMatchCount") != discarded_count
        or pointer.get("cropOrProducerValuesUsedForSelection") is not False
    ):
        raise ValueError("unseen v3 split pointer accounting differs")
    return {
        "recordCount": len(records),
        "matchingStoreRecordCount": matching_count,
        "pointerReuseRecordCount": reuse_count,
        "discardedEarlierMatchCount": discarded_count,
        "pointerReuseBranchExecuted": reuse_count > 0,
        "pointerReuseEventRequired": False,
        "everySelectedStoreIsLastMatchingStore": True,
    }


def validate(
    trace_path: Path, timeline_path: Path, preregistration_path: Path
) -> dict[str, Any]:
    preregistration = _preregistration(preregistration_path)
    result = v3.validate(
        trace_path,
        timeline_path,
        EXPECTED_GEOMETRY,
        EXPECTED_MATERIAL,
        EXPECTED_APPEARANCE,
        EXPECTED_DIRECTION,
    )
    profile = _mapping(result.get("profile"), "profile")
    pointer = _mapping(result.get("liveStorePointerReuse"), "pointer reuse")
    pointer_gate = _validate_pointer_plan(pointer)
    identity = _mapping(result.get("liveCropArithmeticCodeIdentity"), "code identity")
    model = _mapping(result.get("regularGeometryModel"), "geometry model")
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
        or replay.get("rectangleCount") != 32
        or replay.get("componentCount") != 128
        or replay.get("exactRectangleCount") != 32
        or replay.get("exactComponentCount") != 128
        or replay.get("mismatchedRectangleCount") != 0
        or replay.get("mismatchedComponentCount") != 0
        or replay.get("maximumAbsoluteErrorsXYWH") != [0.0, 0.0, 0.0, 0.0]
        or replay.get("maximumULPDistancesXYWH") != [0, 0, 0, 0]
    ):
        raise ValueError("unseen v3 split live crop holdout differs")

    result[
        "prepareLayerLiveCropReplayV3SplitHoldoutLocalMacOS2661ValidationSchemaVersion"
    ] = VALIDATION_SCHEMA_VERSION
    result["classification"] = (
        "prospective runtime-unseen circle-497 transfer of the frozen live-code "
        "authenticated v3 binary32-boundary crop arithmetic; last-store selection "
        "is exact for every record and pointer reuse is validated when present "
        "without requiring the allocator to produce that branch"
    )
    inputs = _mapping(result.get("inputs"), "inputs")
    inputs["preregistrationSHA256"] = _sha256(preregistration_path)
    inputs["v3OpenedOutcomeResultSHA256"] = V3_OPENED_OUTCOME_RESULT_SHA256
    inputs["v3ReanalysisResultSHA256"] = V3_REANALYSIS_RESULT_SHA256
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
    sealed["v2UnseenGeometryTransferPassed"] = False
    sealed["v2UnseenGeometryTransferFalsified"] = True
    sealed["v3OpenedGeometryReplayPassed"] = True
    sealed["v3UnseenGeometryArithmeticPassed"] = True
    sealed["v3UnseenGeometryTransferPassed"] = True
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
