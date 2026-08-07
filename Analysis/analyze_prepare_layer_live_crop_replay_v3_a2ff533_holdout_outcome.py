#!/usr/bin/env python3
"""Separate the v3 circle-496 arithmetic result from its compound coverage gate."""

import argparse
import json
from pathlib import Path
from typing import Any

import validate_prepare_layer_live_crop_replay_v3_local_macos_26_6_1 as v3


ANALYSIS_SCHEMA_VERSION = 1
EXPECTED_TRACE_SHA256 = (
    "8ff22c95a3c8614e17a1060578bfd34d4a5e1a9ccf5ce40b6fe76a39023cc201"
)
EXPECTED_TIMELINE_SHA256 = (
    "992035fc474a151c27d22a727ede99e76c365d1aebbf6ee82a91b48290fad95c"
)


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    return value


def analyze(trace_path: Path, timeline_path: Path) -> dict[str, Any]:
    if (
        v3.v2._sha256(trace_path) != EXPECTED_TRACE_SHA256
        or v3.v2._sha256(timeline_path) != EXPECTED_TIMELINE_SHA256
    ):
        raise ValueError("circle-496 v3 holdout input hash differs")
    result = v3.validate(
        trace_path,
        timeline_path,
        "circle-496-center",
        "regular",
        "dark",
        "materialize",
    )
    profile = _mapping(result.get("profile"), "profile")
    identity = _mapping(result.get("liveCropArithmeticCodeIdentity"), "identity")
    pointer = _mapping(result.get("liveStorePointerReuse"), "pointer")
    model = _mapping(result.get("regularGeometryModel"), "model")
    replay = _mapping(result.get("floatingReplay"), "replay")
    if (
        profile
        != {
            "material": "regular",
            "appearance": "dark",
            "direction": "materialize",
            "geometry": "circle-496-center",
            "backingScaleFactor": 2,
        }
        or identity.get("embeddedInTrace") is not True
        or identity.get("recordCount") != 6
        or pointer.get("recordCount") != 32
        or pointer.get("matchingStoreRecordCount") != 32
        or pointer.get("pointerReuseRecordCount") != 0
        or pointer.get("discardedEarlierMatchCount") != 0
        or model.get("binary32ConversionCount") != 1
        or model.get("cropOrProducerValuesUsed") is not False
        or replay.get("rectangleCount") != 32
        or replay.get("exactRectangleCount") != 32
        or replay.get("componentCount") != 128
        or replay.get("exactComponentCount") != 128
        or replay.get("mismatchedRectangleCount") != 0
        or replay.get("mismatchedComponentCount") != 0
        or replay.get("maximumAbsoluteErrorsXYWH") != [0.0, 0.0, 0.0, 0.0]
        or replay.get("maximumULPDistancesXYWH") != [0, 0, 0, 0]
    ):
        raise ValueError("circle-496 v3 opened outcome differs")

    return {
        "prepareLayerLiveCropReplayV3A2FF533HoldoutOutcomeSchemaVersion": (
            ANALYSIS_SCHEMA_VERSION
        ),
        "classification": (
            "immutable opened outcome of the prospective circle-496 v3 holdout; "
            "the frozen compound gate failed solely because a nondeterministic "
            "pointer-reuse coverage event did not occur, while the independently "
            "frozen arithmetic candidate matched every target component bitwise"
        ),
        "captureCommit": "a2ff53316a727f8563cb534d7e1ae89f6157eb55",
        "capturedAtUtc": "2026-08-07T20:43:13Z",
        "inputs": {
            "traceSHA256": EXPECTED_TRACE_SHA256,
            "timelineSHA256": EXPECTED_TIMELINE_SHA256,
            "preregistrationSHA256": (
                "4ceab97059a3c9e77fe45269a2a39e37adc312278de5ebdae59816a252c3f0d2"
            ),
            "compoundValidatorSHA256": (
                "e56d139e826d61ed57b16f605ff63b8b6ab29215004362c4f8360e1238fbbaf3"
            ),
            "v3ArithmeticModelSHA256": (
                "ee5fed1aaa98423abafc2ad415a8de2ee599340ee084eb5fb975ee0bf52b3e47"
            ),
        },
        "profile": profile,
        "capture": {
            "nativeLLDBExitStatus": 0,
            "compoundValidationExitStatus": 1,
            "traceFinalized": True,
            "traceFailureCount": 0,
            "qualifiedMarkerRecordCount": 32,
            "qualifiedUnionRecordCount": 352,
            "qualifiedStoreRecordCount": 352,
            "liveCodeIdentityAuthenticated": True,
            "liveCodeIdentityRecordCount": 6,
            "timelineSampleCount": 33,
            "failedTimelineSampleCount": 0,
        },
        "v3ArithmeticModel": {
            key: model[key]
            for key in (
                "terminalPublicInputBleedAmountF64",
                "terminalPublicInputBleedAmountF64Hex",
                "internalInputBleedAmountF32",
                "internalInputBleedAmountF32RawLittleEndianHex",
                "internalInputBleedAmountPromotedF64Hex",
                "sourceBoundsF64",
                "sourceBoundsHex",
                "recursiveChildF64",
                "recursiveChildHex",
                "binary32ConversionCount",
                "cropOrProducerValuesUsed",
            )
        },
        "prospectiveArithmeticResult": {
            key: replay[key]
            for key in (
                "rectangleCount",
                "exactRectangleCount",
                "componentCount",
                "exactComponentCount",
                "mismatchedRectangleCount",
                "mismatchedComponentCount",
                "maximumAbsoluteErrorsXYWH",
                "maximumULPDistancesXYWH",
            )
        },
        "observedPointerCoverage": {
            "recordCount": pointer["recordCount"],
            "matchingStoreRecordCount": pointer["matchingStoreRecordCount"],
            "pointerReuseRecordCount": pointer["pointerReuseRecordCount"],
            "discardedEarlierMatchCount": pointer["discardedEarlierMatchCount"],
            "cropOrProducerValuesUsedForSelection": pointer[
                "cropOrProducerValuesUsedForSelection"
            ],
            "allSingletonMatches": True,
            "pointerReuseBranchExecuted": False,
            "pointerSelectionMismatchObserved": False,
        },
        "frozenCompoundGate": {
            "conclusion": "failure",
            "originalFailure": "ValueError: unseen v3 live crop holdout differs",
            "failedCoverageTerms": [
                "matchingStoreRecordCount >= 33",
                "pointerReuseRecordCount >= 1",
                "discardedEarlierMatchCount >= 1",
            ],
            "failedArithmeticTerms": [],
            "relabelledAsPass": False,
        },
        "sealedConclusion": {
            "v3UnseenGeometryArithmeticPassed": True,
            "v3CompoundHoldoutPassed": False,
            "v3UnseenGeometryTransferPassed": False,
            "pointerReuseBranchMismatchObserved": False,
            "freshSplitCriterionHoldoutRequired": True,
            "selectedRegionOriginTransferPassed": False,
            "physicalRetinaColorTransferPassed": False,
            "independentWalleZeroByteFrameParityPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    arguments = parser.parse_args()
    print(
        json.dumps(
            analyze(arguments.trace, arguments.timeline),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
