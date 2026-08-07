#!/usr/bin/env python3
"""Seal the three opened captures that falsified and repaired crop replay v1."""

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

import validate_prepare_layer_live_crop_replay_v2_local_macos_26_6_1 as v2


ANALYSIS_SCHEMA_VERSION = 1
EXPECTED_INPUTS = {
    "failed485": {
        "traceSHA256": (
            "018e870a730042f24fc5d06957ef693e39d63b01d9481c2f694b8abf8c3e6ef0"
        ),
        "timelineSHA256": (
            "c549bafa4ae350818ba062ff834ec726e9c8ca42797ab1a0c30b850a9fe49012"
        ),
        "geometry": "circle-485-center",
    },
    "dod485": {
        "traceSHA256": (
            "691cffb51557a9fb63596534bb09d8e5497bd8c06163e77071d656561bfce2d7"
        ),
        "timelineSHA256": (
            "f4a5180d646e088f5aaa5dda7b5a65d98754a4dfcffcaa6a494dfb54118deedc"
        ),
        "validationSHA256": (
            "f952045c050c1d5cf4c04bf819864f8a34e5a9d119d18637b7f0d1042f01515a"
        ),
        "geometry": "circle-485-center",
    },
    "known800": {
        "traceSHA256": (
            "271871e797714fae80052bcd8a3f280baa6c50653fabd26c35a88e876fe2c8f5"
        ),
        "timelineSHA256": (
            "5bbadf2e5da0f5038ffe665540281da84107c2a6ee1857515e546b7160db0abc"
        ),
        "geometry": "circle-800-center",
    },
}
EXPECTED_DOD_SOURCE = (-169.75, -169.75, 824.5, 824.5)
EXPECTED_DOD_SOURCE_COUNT = 80


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    return value


def _check_hash(path: Path, expected: str, label: str) -> None:
    if v2._sha256(path) != expected:
        raise ValueError(f"{label} hash differs")


def _opened_replay(
    trace: Path, timeline: Path, specification: dict[str, str]
) -> dict[str, Any]:
    _check_hash(trace, specification["traceSHA256"], "trace")
    _check_hash(timeline, specification["timelineSHA256"], "timeline")
    result = v2.validate(
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
        "sourceBoundsF64": model["sourceBoundsF64"],
        "sourceBoundsHex": model["sourceBoundsHex"],
        "terminalInputBleedAmountF64": model["terminalInputBleedAmountF64"],
        "rectangleCount": replay["rectangleCount"],
        "exactRectangleCount": replay["exactRectangleCount"],
        "componentCount": replay["componentCount"],
        "exactComponentCount": replay["exactComponentCount"],
        "maximumAbsoluteErrorsXYWH": replay["maximumAbsoluteErrorsXYWH"],
        "maximumULPDistancesXYWH": replay["maximumULPDistancesXYWH"],
    }


def analyze(
    failed_trace: Path,
    failed_timeline: Path,
    dod_trace: Path,
    dod_timeline: Path,
    dod_validation: Path,
    known_trace: Path,
    known_timeline: Path,
) -> dict[str, Any]:
    replays = {
        "failed485": _opened_replay(
            failed_trace, failed_timeline, EXPECTED_INPUTS["failed485"]
        ),
        "dod485": _opened_replay(dod_trace, dod_timeline, EXPECTED_INPUTS["dod485"]),
        "known800": _opened_replay(
            known_trace, known_timeline, EXPECTED_INPUTS["known800"]
        ),
    }
    _check_hash(
        dod_validation,
        EXPECTED_INPUTS["dod485"]["validationSHA256"],
        "DOD validation",
    )
    opened_dod = _mapping(
        json.loads(dod_validation.read_text(encoding="utf-8")), "DOD validation"
    )
    dod_records = opened_dod.get("records")
    if not isinstance(dod_records, list):
        raise ValueError("DOD validation records differ")
    outputs = Counter(
        tuple(
            v2.exact.finite(component, "DOD output")
            for component in _mapping(record, "DOD record").get("outputBoundsF64", [])
        )
        for record in dod_records
    )
    if (
        opened_dod.get("conclusion") != "success"
        or opened_dod.get("sourceRecordCount") != 178
        or outputs[EXPECTED_DOD_SOURCE] != EXPECTED_DOD_SOURCE_COUNT
    ):
        raise ValueError("opened DOD source calibration differs")

    total_rectangles = sum(record["rectangleCount"] for record in replays.values())
    exact_rectangles = sum(record["exactRectangleCount"] for record in replays.values())
    total_components = sum(record["componentCount"] for record in replays.values())
    exact_components = sum(record["exactComponentCount"] for record in replays.values())
    if (
        total_rectangles != 96
        or exact_rectangles != total_rectangles
        or total_components != 384
        or exact_components != total_components
    ):
        raise ValueError("opened v2 aggregate replay differs")

    return {
        "prepareLayerLiveCropReplayV2ReanalysisSchemaVersion": (
            ANALYSIS_SCHEMA_VERSION
        ),
        "classification": (
            "retrospective exact reanalysis of two circle-485 runs and the "
            "known circle-800 calibration; this repairs the falsified v1 "
            "model but supplies no unseen-transfer authority"
        ),
        "conclusion": "success",
        "v1Falsification": {
            "captureSucceeded": True,
            "originalValidationExitStatus": 1,
            "originalFailure": "regular recursive child differs",
            "fixed1360SquareAssumptionFalsified": True,
            "algebraicallySimplifiedSDFTransformFalsified": True,
        },
        "liveDODCalibration": {
            "validationSHA256": EXPECTED_INPUTS["dod485"]["validationSHA256"],
            "recordCount": len(dod_records),
            "uniqueOutputCount": len(outputs),
            "exactSourceBoundsF64": list(EXPECTED_DOD_SOURCE),
            "exactSourceBoundsHex": v2.exact.f64_hex(EXPECTED_DOD_SOURCE),
            "exactSourceBoundsOccurrenceCount": outputs[EXPECTED_DOD_SOURCE],
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
            "v2OpenedEvidenceReplayPassed": True,
            "v2UnseenGeometryTransferPassed": False,
            "selectedRegionOriginTransferPassed": False,
            "physicalRetinaColorTransferPassed": False,
            "independentWalleZeroByteFrameParityPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--failed-trace", required=True, type=Path)
    parser.add_argument("--failed-timeline", required=True, type=Path)
    parser.add_argument("--dod-trace", required=True, type=Path)
    parser.add_argument("--dod-timeline", required=True, type=Path)
    parser.add_argument("--dod-validation", required=True, type=Path)
    parser.add_argument("--known-trace", required=True, type=Path)
    parser.add_argument("--known-timeline", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = analyze(
        arguments.failed_trace,
        arguments.failed_timeline,
        arguments.dod_trace,
        arguments.dod_timeline,
        arguments.dod_validation,
        arguments.known_trace,
        arguments.known_timeline,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
