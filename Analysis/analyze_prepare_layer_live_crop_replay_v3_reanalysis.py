#!/usr/bin/env python3
"""Reanalyze all four opened regular crop captures under the v3 precision law."""

import argparse
import json
from pathlib import Path
from typing import Any

import validate_prepare_layer_live_crop_replay_v3_local_macos_26_6_1 as v3


ANALYSIS_SCHEMA_VERSION = 1
EXPECTED_INPUTS = {
    "failed485": {
        "traceSHA256": "018e870a730042f24fc5d06957ef693e39d63b01d9481c2f694b8abf8c3e6ef0",
        "timelineSHA256": "c549bafa4ae350818ba062ff834ec726e9c8ca42797ab1a0c30b850a9fe49012",
        "geometry": "circle-485-center",
    },
    "dod485": {
        "traceSHA256": "691cffb51557a9fb63596534bb09d8e5497bd8c06163e77071d656561bfce2d7",
        "timelineSHA256": "f4a5180d646e088f5aaa5dda7b5a65d98754a4dfcffcaa6a494dfb54118deedc",
        "geometry": "circle-485-center",
    },
    "known800": {
        "traceSHA256": "271871e797714fae80052bcd8a3f280baa6c50653fabd26c35a88e876fe2c8f5",
        "timelineSHA256": "5bbadf2e5da0f5038ffe665540281da84107c2a6ee1857515e546b7160db0abc",
        "geometry": "circle-800-center",
    },
    "failed487": {
        "traceSHA256": "537e2f7068009f6873ffb63e788c41965d4902de96b246fe4adcef0ac6288927",
        "timelineSHA256": "fea52975827939fd5bce84dd8451c16676d8d16b5408905e4d7c48311816637c",
        "geometry": "circle-487-center",
    },
}


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    return value


def _check_hash(path: Path, expected: str, label: str) -> None:
    if v3.v2._sha256(path) != expected:
        raise ValueError(f"{label} hash differs")


def _opened_replay(
    trace: Path, timeline: Path, specification: dict[str, str]
) -> dict[str, Any]:
    _check_hash(trace, specification["traceSHA256"], "trace")
    _check_hash(timeline, specification["timelineSHA256"], "timeline")
    result = v3.validate(
        trace,
        timeline,
        specification["geometry"],
        "regular",
        "dark",
        "materialize",
        require_embedded_code_identity=False,
    )
    replay = _mapping(result.get("floatingReplay"), "floating replay")
    model = _mapping(result.get("regularGeometryModel"), "geometry model")
    return {
        "geometry": specification["geometry"],
        "traceSHA256": specification["traceSHA256"],
        "timelineSHA256": specification["timelineSHA256"],
        "terminalPublicInputBleedAmountF64": model["terminalPublicInputBleedAmountF64"],
        "internalInputBleedAmountF32": model["internalInputBleedAmountF32"],
        "internalInputBleedAmountF32RawLittleEndianHex": model[
            "internalInputBleedAmountF32RawLittleEndianHex"
        ],
        "sourceBoundsF64": model["sourceBoundsF64"],
        "sourceBoundsHex": model["sourceBoundsHex"],
        "rectangleCount": replay["rectangleCount"],
        "exactRectangleCount": replay["exactRectangleCount"],
        "componentCount": replay["componentCount"],
        "exactComponentCount": replay["exactComponentCount"],
        "maximumAbsoluteErrorsXYWH": replay["maximumAbsoluteErrorsXYWH"],
        "maximumULPDistancesXYWH": replay["maximumULPDistancesXYWH"],
    }


def analyze(inputs: dict[str, tuple[Path, Path]]) -> dict[str, Any]:
    if set(inputs) != set(EXPECTED_INPUTS):
        raise ValueError("v3 opened input inventory differs")
    replays = {
        label: _opened_replay(*inputs[label], specification)
        for label, specification in EXPECTED_INPUTS.items()
    }
    total_rectangles = sum(record["rectangleCount"] for record in replays.values())
    exact_rectangles = sum(record["exactRectangleCount"] for record in replays.values())
    total_components = sum(record["componentCount"] for record in replays.values())
    exact_components = sum(record["exactComponentCount"] for record in replays.values())
    if (
        total_rectangles != 128
        or exact_rectangles != total_rectangles
        or total_components != 512
        or exact_components != total_components
    ):
        raise ValueError("opened v3 aggregate replay differs")
    return {
        "prepareLayerLiveCropReplayV3ReanalysisSchemaVersion": (
            ANALYSIS_SCHEMA_VERSION
        ),
        "classification": (
            "retrospective exact reanalysis of all four opened live regular-crop "
            "captures after the prospective v2 circle-487 falsification; this "
            "calibrates v3 but supplies no unseen-transfer authority"
        ),
        "conclusion": "success",
        "v2HoldoutFalsification": {
            "geometry": "circle-487-center",
            "originalValidationExitStatus": 1,
            "originalFailure": "regular recursive child differs",
            "hiddenPublicF64ToInternalF32BoundaryFalsifiedV2": True,
            "v2UnseenGeometryTransferPassed": False,
        },
        "v3PrecisionRule": {
            "rule": (
                "convert terminal public inputBleedAmount to binary32 exactly "
                "once, promote to binary64, then derive source DOD, recursive "
                "child, and endpoint term"
            ),
            "conversionCount": 1,
            "cropOrProducerValuesUsed": False,
            "toleranceUsed": False,
        },
        "openedReplays": replays,
        "aggregate": {
            "rectangleCount": total_rectangles,
            "exactRectangleCount": exact_rectangles,
            "componentCount": total_components,
            "exactComponentCount": exact_components,
            "maximumAbsoluteErrorsXYWH": [0.0, 0.0, 0.0, 0.0],
            "maximumULPDistancesXYWH": [0, 0, 0, 0],
            "toleranceUsed": False,
        },
        "sealedConclusion": {
            "v2UnseenGeometryTransferPassed": False,
            "v2UnseenGeometryTransferFalsified": True,
            "v3OpenedEvidenceReplayPassed": True,
            "v3UnseenGeometryTransferPassed": False,
            "selectedRegionOriginTransferPassed": False,
            "physicalRetinaColorTransferPassed": False,
            "independentWalleZeroByteFrameParityPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    for label in EXPECTED_INPUTS:
        parser.add_argument(f"--{label}-trace", required=True, type=Path)
        parser.add_argument(f"--{label}-timeline", required=True, type=Path)
    arguments = parser.parse_args()
    inputs = {
        label: (
            getattr(arguments, f"{label}_trace"),
            getattr(arguments, f"{label}_timeline"),
        )
        for label in EXPECTED_INPUTS
    }
    print(json.dumps(analyze(inputs), indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
