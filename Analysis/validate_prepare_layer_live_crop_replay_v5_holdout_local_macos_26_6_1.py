#!/usr/bin/env python3
"""Validate the frozen runtime-unseen circle-499 v5 crop holdout."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import validate_prepare_layer_live_crop_replay_v3_split_holdout_local_macos_26_6_1 as split
import validate_prepare_layer_live_crop_replay_v5_local_macos_26_6_1 as v5


VALIDATION_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
EXPECTED_GEOMETRY = "circle-499-center"
EXPECTED_MATERIAL = "regular"
EXPECTED_APPEARANCE = "dark"
EXPECTED_DIRECTION = "materialize"
V4_FALSIFICATION_RESULT = Path(__file__).with_name(
    "prepare_layer_live_crop_replay_v4_cc25df6_holdout_falsification_result.json"
)
V4_FALSIFICATION_RESULT_SHA256 = (
    "9ed4a3f68dcc59955e430580c1f6c3a1400531cb68de61b3b18a47a98ac950c5"
)
V5_REANALYSIS_RESULT = Path(__file__).with_name(
    "prepare_layer_live_crop_replay_v5_reanalysis_result.json"
)
V5_REANALYSIS_RESULT_SHA256 = (
    "8cdabb54f1b20add151dd6a7558b6180976479623b9b0f9507b1ebc8a0ea41a4"
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
            "prepareLayerLiveCropReplayV5HoldoutPreregistrationSchemaVersion"
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
        or candidate.get("publicBackdropLayerBoundsUsed") is not True
        or candidate.get("authenticatedBackdropBoundsOperationOrder") is not True
        or candidate.get("gaussianShadowExpansionApplied") is not True
        or candidate.get("endpointDerivedSDFTranslationApplied") is not False
        or candidate.get("pointerReuseEventRequired") is not False
        or candidate.get("pointerReuseBranchValidatedWhenPresent") is not True
        or candidate.get("cropOrProducerValuesUsedForSelection") is not False
        or candidate.get("targetOutputsUsed") is not False
        or candidate.get("toleranceUsed") is not False
        or evidence.get("v4FalsificationResultSHA256") != V4_FALSIFICATION_RESULT_SHA256
        or evidence.get("v5ReanalysisResultSHA256") != V5_REANALYSIS_RESULT_SHA256
        or _sha256(V4_FALSIFICATION_RESULT) != V4_FALSIFICATION_RESULT_SHA256
        or _sha256(V5_REANALYSIS_RESULT) != V5_REANALYSIS_RESULT_SHA256
    ):
        raise ValueError("unseen v5 crop preregistration differs")
    repository = path.parent.parent
    frozen_files = preregistration.get("frozenFiles")
    if not isinstance(frozen_files, list) or not frozen_files:
        raise ValueError("unseen v5 frozen-file inventory differs")
    for raw_record in frozen_files:
        record = _mapping(raw_record, "frozen file")
        relative = record.get("path")
        digest = record.get("sha256")
        if (
            not isinstance(relative, str)
            or not isinstance(digest, str)
            or _sha256(repository / relative) != digest
        ):
            raise ValueError("unseen v5 frozen file differs")
    return preregistration


def validate(
    trace_path: Path, timeline_path: Path, preregistration_path: Path
) -> dict[str, Any]:
    preregistration = _preregistration(preregistration_path)
    result = v5.validate(
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
    endpoint = _mapping(result.get("endpointYOffset"), "endpoint witness")
    shadow = _mapping(result.get("filterShadowArithmetic"), "shadow arithmetic")
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
        or model.get("backdropBoundsRecordCount") != 32
        or model.get("backdropBoundsUsedAsPublicInput") is not True
        or model.get("cropOrProducerValuesUsed") is not False
        or sdf.get("endpointOffsetGroupedIntoYTranslation") is not False
        or endpoint.get("appliedRecordCount") != 1
        or endpoint.get("arithmeticOffsetApplied") is not False
        or shadow.get("recordCount") != 32
        or shadow.get("positiveExpansionRecordCount") != 32
        or shadow.get("publicTimelineInputsUsed") is not True
        or shadow.get("cropOrProducerValuesUsed") is not False
        or shadow.get("toleranceUsed") is not False
        or replay.get("rectangleCount") != 32
        or replay.get("componentCount") != 128
        or replay.get("exactRectangleCount") != 32
        or replay.get("exactComponentCount") != 128
        or replay.get("mismatchedRectangleCount") != 0
        or replay.get("mismatchedComponentCount") != 0
        or replay.get("maximumAbsoluteErrorsXYWH") != [0.0, 0.0, 0.0, 0.0]
        or replay.get("maximumULPDistancesXYWH") != [0, 0, 0, 0]
    ):
        raise ValueError("unseen v5 live crop holdout differs")

    result[
        "prepareLayerLiveCropReplayV5HoldoutLocalMacOS2661ValidationSchemaVersion"
    ] = VALIDATION_SCHEMA_VERSION
    result["classification"] = (
        "prospective runtime-unseen circle-499 transfer of frozen v5 crop "
        "arithmetic: public BackdropLayer bounds, exact delegated expansion, "
        "Gaussian-expanded shadow union, no endpoint-derived SDF translation, "
        "and last-store selection all pass with zero tolerance"
    )
    inputs = _mapping(result.get("inputs"), "inputs")
    inputs["preregistrationSHA256"] = _sha256(preregistration_path)
    inputs["v4FalsificationResultSHA256"] = V4_FALSIFICATION_RESULT_SHA256
    inputs["v5ReanalysisResultSHA256"] = V5_REANALYSIS_RESULT_SHA256
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
    sealed["v4UnseenGeometryTransferPassed"] = False
    sealed["v4UnseenGeometryTransferFalsified"] = True
    sealed["v5OpenedGeometryReplayPassed"] = True
    sealed["v5UnseenGeometryArithmeticPassed"] = True
    sealed["v5UnseenGeometryTransferPassed"] = True
    sealed["selectedRegionOriginTransferPassed"] = False
    sealed["opticalTransferPassed"] = False
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
