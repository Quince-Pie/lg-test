#!/usr/bin/env python3
"""Preserve the failed v4 holdout and diagnose it with the v5 model."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import validate_prepare_layer_live_crop_replay_v4_local_macos_26_6_1 as v4
import validate_prepare_layer_live_crop_replay_v5_local_macos_26_6_1 as v5


ANALYSIS_SCHEMA_VERSION = 1
TRACE_SHA256 = "6a39a28ca2c60aa549bfab6f0c044ad4b36744ec5f9a51b468be944c660e4382"
TIMELINE_SHA256 = "eb2f1c5eeff2be1489da0bde7e19cc9f2afc7dbdc60a294596dd7e5e9f380561"
PREREGISTRATION_SHA256 = (
    "4bddc2d722bdd0b96db32fd4d989cb22a457d4c3196ee17360d017e9fb16e47c"
)
EXPECTED_PROFILE = ("circle-498-center", "regular", "dark", "materialize")


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    return value


def _diagnostic_v4(trace_path: Path, timeline_path: Path) -> dict[str, Any]:
    """Let the immutable v4 validator finish while retaining its real metric."""

    holdout = v4.v3.v2.profile.holdout
    original_metric = holdout.ExactMetric
    captured: list[dict[str, Any]] = []

    class DiagnosticMetric(original_metric):
        def result(self) -> dict[str, Any]:
            actual = super().result()
            captured.append(deepcopy(actual))
            accepted = deepcopy(actual)
            accepted.update(
                {
                    "exactRectangleCount": accepted["rectangleCount"],
                    "mismatchedRectangleCount": 0,
                    "exactComponentCount": accepted["componentCount"],
                    "mismatchedComponentCount": 0,
                    "exactComponentCountsXYWH": [accepted["rectangleCount"]] * 4,
                    "maximumAbsoluteErrorsXYWH": [0.0] * 4,
                    "maximumULPDistancesXYWH": [0] * 4,
                }
            )
            return accepted

    holdout.ExactMetric = DiagnosticMetric
    try:
        result = v4.validate(trace_path, timeline_path, *EXPECTED_PROFILE)
    finally:
        holdout.ExactMetric = original_metric
    if len(captured) != 1:
        raise ValueError("v4 diagnostic metric count differs")
    records = _mapping(result.get("floatingReplay"), "v4 replay").get("records")
    if not isinstance(records, list):
        raise ValueError("v4 replay records differ")
    mismatches = [record for record in records if record.get("exact") is not True]
    return {"metric": captured[0], "mismatches": mismatches}


def analyze(
    trace_path: Path, timeline_path: Path, preregistration_path: Path
) -> dict[str, Any]:
    for path, expected, label in (
        (trace_path, TRACE_SHA256, "trace"),
        (timeline_path, TIMELINE_SHA256, "timeline"),
        (preregistration_path, PREREGISTRATION_SHA256, "preregistration"),
    ):
        if v5.v2._sha256(path) != expected:
            raise ValueError(f"v4 holdout {label} hash differs")

    v4_diagnostic = _diagnostic_v4(trace_path, timeline_path)
    metric = v4_diagnostic["metric"]
    if (
        metric.get("rectangleCount") != 32
        or metric.get("exactRectangleCount") != 0
        or metric.get("componentCount") != 128
        or metric.get("exactComponentCount") != 79
        or metric.get("maximumULPDistancesXYWH") != [4, 4, 1, 1]
    ):
        raise ValueError("v4 holdout falsification metric differs")

    corrected = v5.validate(trace_path, timeline_path, *EXPECTED_PROFILE)
    replay = _mapping(corrected.get("floatingReplay"), "v5 replay")
    model = _mapping(corrected.get("regularGeometryModel"), "v5 geometry model")
    shadow = _mapping(corrected.get("filterShadowArithmetic"), "v5 shadow")
    if (
        replay.get("exactRectangleCount") != 32
        or replay.get("exactComponentCount") != 128
        or replay.get("maximumULPDistancesXYWH") != [0, 0, 0, 0]
        or shadow.get("recordCount") != 32
        or shadow.get("positiveExpansionRecordCount") != 32
    ):
        raise ValueError("v5 correction replay differs")

    first = _mapping(v4_diagnostic["mismatches"][0], "first v4 mismatch")
    return {
        "prepareLayerLiveCropReplayV4CC25DF6HoldoutFalsificationSchemaVersion": (
            ANALYSIS_SCHEMA_VERSION
        ),
        "classification": (
            "immutable outcome of the prospectively frozen circle-498 v4 "
            "holdout, followed by target-opened diagnosis under v5; the failed "
            "v4 gate is not relabelled as a pass"
        ),
        "conclusion": "v4-falsified-v5-retrospectively-exact",
        "inputs": {
            "traceSHA256": TRACE_SHA256,
            "timelineSHA256": TIMELINE_SHA256,
            "preregistrationSHA256": PREREGISTRATION_SHA256,
            "v4OriginalValidationExitStatus": 1,
        },
        "v4FrozenCandidate": {
            **metric,
            "failed": True,
            "sourceOriginAssumedAsNegatedBinary32Margin": True,
            "endpointOffsetGroupedIntoSDFTranslation": True,
        },
        "firstDivergence": {
            "sampleIndex": first["sampleIndex"],
            "observedProducerF64": first["observedProducerF64"],
            "observedProducerHex": first["observedProducerHex"],
            "v4ReplayF64": first["replayF64"],
            "v4ReplayHex": first["replayHex"],
        },
        "v5OpenedDiagnosis": {
            "publicBackdropBoundsF64": model["publicBackdropBoundsF64"],
            "publicBackdropBoundsHex": model["publicBackdropBoundsHex"],
            "sourceBoundsF64": model["sourceBoundsF64"],
            "sourceBoundsHex": model["sourceBoundsHex"],
            "legacyEndpointTranslationFalsified": True,
            "gaussianShadowExpansionApplied": True,
            "positiveShadowExpansionRecordCount": shadow[
                "positiveExpansionRecordCount"
            ],
            "rectangleCount": replay["rectangleCount"],
            "exactRectangleCount": replay["exactRectangleCount"],
            "componentCount": replay["componentCount"],
            "exactComponentCount": replay["exactComponentCount"],
            "maximumAbsoluteErrorsXYWH": replay["maximumAbsoluteErrorsXYWH"],
            "maximumULPDistancesXYWH": replay["maximumULPDistancesXYWH"],
            "toleranceUsed": False,
            "targetOutputsUsedForDiagnosis": True,
        },
        "sealedConclusion": {
            "v4UnseenGeometryTransferPassed": False,
            "v4UnseenGeometryTransferFalsified": True,
            "v5OpenedEvidenceReplayPassed": True,
            "v5UnseenGeometryTransferPassed": False,
            "selectedRegionOriginTransferPassed": False,
            "opticalTransferPassed": False,
            "physicalRetinaColorCompositorTransferPassed": False,
            "independentWalleZeroByteFrameParityPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("preregistration", type=Path)
    arguments = parser.parse_args()
    print(
        json.dumps(
            analyze(arguments.trace, arguments.timeline, arguments.preregistration),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
