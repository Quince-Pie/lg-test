#!/usr/bin/env python3
"""Validate the prospective combined transition-geometry transfer matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_transition_geometry_corpus_local_macos_26_6_1 as model


RESULT_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
REPOSITORY = Path(__file__).resolve().parents[1]
EXPECTED_PHYSICAL_PIXELS = [3456, 2234]
EXPECTED_LOGICAL_POINTS = [1728, 1117]
EXPECTED_SOURCE_PATHS = {
    "Analysis/analyze_transition_geometry_corpus_local_macos_26_6_1.py",
    "Analysis/analyze_transition_uniform_profile_calibration.py",
    "Analysis/check_local_retina_capture_session_v2.swift",
    "Analysis/test_analyze_transition_geometry_corpus_local_macos_26_6_1.py",
    "Analysis/test_validate_combined_transition_geometry_holdout_local_macos_26_6_1.py",
    "Analysis/validate_combined_transition_geometry_holdout_local_macos_26_6_1.py",
    "Analysis/validate_dynamic_allocation_holdout.py",
    "Analysis/validate_variable_blur_selected_region_origin.py",
    "Sources/GlassIntrospect/HalfBlendProbe.swift",
    "Sources/GlassIntrospect/HalfDotProbe.swift",
    "Sources/GlassIntrospect/HalfIntrinsicProbe.swift",
    "Sources/GlassIntrospect/MatrixBridge.c",
    "Sources/GlassIntrospect/MatrixBridge.h",
    "Sources/GlassIntrospect/SDFStageProbe.swift",
    "Sources/GlassIntrospect/main.swift",
    "flake.lock",
    "flake.nix",
}

type JsonObject = dict[str, Any]


EXPECTED_CASES: tuple[JsonObject, ...] = (
    {
        "caseId": "clear-light-materialize-01",
        "material": "clear",
        "appearance": "light",
        "direction": "materialize",
        "geometry": {
            "name": "circle-combined-holdout-01",
            "shape": "circle",
            "width": 53,
            "height": 53,
            "centerX": 11.25,
            "centerY": 211.75,
            "windowWidth": 1024,
            "windowHeight": 1024,
            "extendsBeyondWindow": False,
        },
        "records": 32,
    },
    {
        "caseId": "clear-dark-materialize-02",
        "material": "clear",
        "appearance": "dark",
        "direction": "materialize",
        "geometry": {
            "name": "circle-combined-holdout-02",
            "shape": "circle",
            "width": 389,
            "height": 389,
            "centerX": 151.5,
            "centerY": 302.25,
            "windowWidth": 1024,
            "windowHeight": 1024,
            "extendsBeyondWindow": False,
        },
        "records": 32,
    },
    {
        "caseId": "regular-light-materialize-03",
        "material": "regular",
        "appearance": "light",
        "direction": "materialize",
        "geometry": {
            "name": "circle-combined-holdout-03",
            "shape": "circle",
            "width": 541,
            "height": 541,
            "centerX": 772.75,
            "centerY": 296.5,
            "windowWidth": 1024,
            "windowHeight": 1024,
            "extendsBeyondWindow": False,
        },
        "records": 32,
    },
    {
        "caseId": "regular-dark-materialize-04",
        "material": "regular",
        "appearance": "dark",
        "direction": "materialize",
        "geometry": {
            "name": "circle-combined-holdout-04",
            "shape": "circle",
            "width": 317,
            "height": 317,
            "centerX": 243.125,
            "centerY": 850.875,
            "windowWidth": 1024,
            "windowHeight": 1024,
            "extendsBeyondWindow": False,
        },
        "records": 32,
    },
    {
        "caseId": "clear-light-dematerialize-05",
        "material": "clear",
        "appearance": "light",
        "direction": "dematerialize",
        "geometry": {
            "name": "circle-combined-holdout-05",
            "shape": "circle",
            "width": 607,
            "height": 607,
            "centerX": 689.625,
            "centerY": 608.375,
            "windowWidth": 1024,
            "windowHeight": 1024,
            "extendsBeyondWindow": False,
        },
        "records": 31,
    },
    {
        "caseId": "clear-dark-dematerialize-06",
        "material": "clear",
        "appearance": "dark",
        "direction": "dematerialize",
        "geometry": {
            "name": "circle-combined-holdout-06",
            "shape": "circle",
            "width": 51,
            "height": 51,
            "centerX": 1002.75,
            "centerY": 475.5,
            "windowWidth": 1024,
            "windowHeight": 1024,
            "extendsBeyondWindow": False,
        },
        "records": 31,
    },
    {
        "caseId": "regular-light-dematerialize-07",
        "material": "regular",
        "appearance": "light",
        "direction": "dematerialize",
        "geometry": {
            "name": "circle-combined-holdout-07",
            "shape": "circle",
            "width": 457,
            "height": 457,
            "centerX": 271.375,
            "centerY": 217.625,
            "windowWidth": 1024,
            "windowHeight": 1024,
            "extendsBeyondWindow": False,
        },
        "records": 31,
    },
    {
        "caseId": "regular-dark-dematerialize-08",
        "material": "regular",
        "appearance": "dark",
        "direction": "dematerialize",
        "geometry": {
            "name": "circle-combined-holdout-08",
            "shape": "circle",
            "width": 523,
            "height": 523,
            "centerX": 755.5,
            "centerY": 786.25,
            "windowWidth": 1024,
            "windowHeight": 1024,
            "extendsBeyondWindow": False,
        },
        "records": 31,
    },
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def mapping(value: object, name: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping), f"{name} is not an object")
    return value


def sequence(value: object, name: str) -> Sequence[Any]:
    require(isinstance(value, list), f"{name} is not an array")
    return value


def load_json(path: Path, name: str) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{name} is not an object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def validate_preregistration_value(value: Mapping[str, Any]) -> None:
    require(
        value.get(
            "combinedTransitionGeometryHoldoutPreregistrationSchemaVersion"
        )
        == PREREGISTRATION_SCHEMA_VERSION,
        "preregistration schema differs",
    )
    require(
        value.get("authority")
        == "prospective output-blind combined transition geometry transfer",
        "preregistration authority differs",
    )
    require(
        value.get("appleOutputsObservedAtFreeze") is False,
        "preregistration is not output-blind",
    )
    cases = sequence(value.get("caseMatrix"), "case matrix")
    require(list(cases) == list(EXPECTED_CASES), "case matrix differs")

    capture = mapping(value.get("captureContract"), "capture contract")
    require(
        capture.get("host") == "quince@10.0.41.19"
        and capture.get("githubActionsPermitted") is False
        and capture.get("debuggerPermitted") is False
        and capture.get("metalCaptureEnvironmentPermitted") is False
        and capture.get("nativeCaptureMayContainNixStorePath") is False
        and capture.get("sourceBuiltProbeRequired") is True
        and capture.get("declaredSDKVersion") == "26.5"
        and capture.get("dynamicUniformEvidenceMode") == "allocation-metadata-v1"
        and capture.get("denseStateCapture") is True
        and capture.get("allocationOnlyCapture") is True
        and capture.get("sampleCountPerTimeline") == 33,
        "capture contract differs",
    )

    acceptance = mapping(value.get("acceptance"), "acceptance")
    require(
        acceptance.get("timelineCount") == 8
        and acceptance.get("dynamicStateCount") == 252
        and acceptance.get("requiredMismatchCountPerMetric") == 0
        and acceptance.get("comparisonMode")
        == "exact integer, binary32, binary64, and byte-stream equality"
        and acceptance.get("requireAllCasesRegardlessOfEarlierOutcome") is True
        and acceptance.get("requireOneCaptureCommitAndBinary") is True
        and acceptance.get("requireDirectActiveRetinaSessionPerCase") is True
        and acceptance.get("requireNoCapturedValueInPrediction") is True
        and acceptance.get("productionShaderMutationPermitted") is False,
        "acceptance contract differs",
    )

    outputs = mapping(value.get("sealedOutputs"), "sealed outputs")
    require(
        outputs
        == {
            "timelineSHA256": None,
            "streamSHA256": None,
            "metricMismatchCounts": None,
            "finalHighlightTopologies": None,
            "prospectiveGatePassed": None,
        },
        "sealed output fields differ",
    )

    sources = mapping(value.get("sourceSHA256"), "source hash map")
    require(set(sources) == EXPECTED_SOURCE_PATHS, "source hash path set differs")
    require(
        all(
            isinstance(path, str)
            and isinstance(digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
            for path, digest in sources.items()
        ),
        "source hash entry differs",
    )


def validate_preregistration(path: Path) -> JsonObject:
    value = load_json(path, "preregistration")
    validate_preregistration_value(value)
    sources = mapping(value.get("sourceSHA256"), "source hash map")
    for relative, expected in sources.items():
        source = REPOSITORY / str(relative)
        require(source.is_file(), f"pinned source is absent: {relative}")
        require(
            sha256_file(source) == expected,
            f"pinned source differs: {relative}",
        )
    return value


def validate_preflight(path: Path) -> JsonObject:
    result = load_json(path, "Retina session preflight")
    require(
        result.get("localRetinaCaptureSessionPreflightSchemaVersion") == 2
        and result.get("passed") is True
        and result.get("sessionDictionaryAvailable") is True
        and result.get("sessionLockFieldValid") is True
        and result.get("sessionLocked") is False
        and result.get("sessionOnConsole") is True
        and result.get("sessionLoginDone") is True
        and result.get("displayActive") is True
        and result.get("displayAsleep") is False
        and result.get("physicalPixels") == EXPECTED_PHYSICAL_PIXELS
        and result.get("logicalPoints") == EXPECTED_LOGICAL_POINTS
        and result.get("backingScaleFactor") == 2,
        "physical Retina session differs",
    )
    return result


def context_fields(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    require("/nix/store/" not in text, "native context contains a Nix store path")
    result: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def validate_case_context(
    path: Path,
    case: Mapping[str, Any],
) -> tuple[str, str]:
    fields = context_fields(path)
    commit = fields.get("CAPTURE_COMMIT", "")
    binary_sha256 = fields.get("CAPTURE_BINARY_SHA256", "")
    geometry = mapping(case.get("geometry"), "expected geometry")
    expected = {
        "NATIVE_CAPTURE_DEBUGGER_USED": "0",
        "GITHUB_ACTIONS_USED": "0",
        "TRACKED_DIRTY_STATE": "0",
        "NATIVE_DECLARED_SDK_VERSION": "26.5",
        "MTL_CAPTURE_ENABLED": "0",
        "LG_GEOMETRY_POLICY": "0",
        "LG_GLASS_MATERIAL": str(case["material"]),
        "LG_GLASS_APPEARANCE": str(case["appearance"]),
        "LG_GLASS_GEOMETRY": str(geometry["name"]),
        "LG_TRANSITION_DIRECTION": str(case["direction"]),
        "LG_TRANSITION_TIMELINE": "1",
        "LG_TRANSITION_UNIFORMS": "1",
        "LG_TRANSITION_ALLOCATION_DENSE": "1",
        "LG_TRANSITION_ALLOCATION_ONLY": "1",
        "LG_TRANSITION_CONTROLLED_BACKDROP": "0",
        "LG_TRANSITION_HIGHLIGHT_VERTEX_TAIL_TRACE": "0",
    }
    require(
        re.fullmatch(r"[0-9a-f]{40}", commit) is not None,
        "capture commit differs",
    )
    require(
        re.fullmatch(r"[0-9a-f]{64}", binary_sha256) is not None,
        "capture binary digest differs",
    )
    require(
        all(fields.get(key) == value for key, value in expected.items()),
        f"native capture context differs for {case['caseId']}",
    )
    return commit, binary_sha256


def expected_input(
    case: Mapping[str, Any],
    timeline_path: Path,
) -> JsonObject:
    geometry = mapping(case.get("geometry"), "expected geometry")
    return {
        "sha256": sha256_file(timeline_path),
        "material": case["material"],
        "appearance": case["appearance"],
        "direction": case["direction"],
        "geometry": geometry["name"],
        "records": case["records"],
    }


def validate(root: Path, preregistration_path: Path) -> JsonObject:
    preregistration = validate_preregistration(preregistration_path)
    require(root.is_dir(), "capture root is absent")

    capture_commits: set[str] = set()
    capture_binaries: set[str] = set()
    expected_inputs: dict[str, JsonObject] = {}
    timeline_results: list[JsonObject] = []
    for case in EXPECTED_CASES:
        case_id = str(case["caseId"])
        directory = root / case_id
        require(directory.is_dir(), f"capture case is absent: {case_id}")
        require(
            (directory / "capture-exit-status.txt").read_text(
                encoding="utf-8"
            ).strip()
            == "0",
            f"native capture failed: {case_id}",
        )
        validate_preflight(directory / "capture-session-preflight.json")
        commit, binary = validate_case_context(
            directory / "capture-context.txt", case
        )
        capture_commits.add(commit)
        capture_binaries.add(binary)

        timeline_path = directory / "transition-timeline.json"
        require(timeline_path.is_file(), f"timeline is absent: {case_id}")
        timeline = load_json(timeline_path, f"{case_id} timeline")
        require(
            timeline.get("geometry") == case["geometry"],
            f"captured geometry differs: {case_id}",
        )
        relative = f"{case_id}/transition-timeline.json"
        expected_inputs[relative] = expected_input(case, timeline_path)
        timeline_results.append(
            {
                "caseId": case_id,
                "bytes": timeline_path.stat().st_size,
                "sha256": expected_inputs[relative]["sha256"],
            }
        )

    require(len(capture_commits) == 1, "capture commits differ across matrix")
    require(len(capture_binaries) == 1, "capture binaries differ across matrix")
    require(
        sum(int(value["records"]) for value in expected_inputs.values()) == 252,
        "prospective state cardinality differs",
    )

    model_result = model.analyze(root, expected_inputs=expected_inputs)
    require(model_result.get("status") == "passed", "combined model gate failed")
    require(
        model_result.get("stateCount") == 252
        and all(
            metric.get("exact") is True
            and metric.get("mismatchedComponents") == 0
            for untyped_metric in mapping(
                model_result.get("metrics"), "model metrics"
            ).values()
            for metric in [mapping(untyped_metric, "model metric")]
        ),
        "combined model metrics differ",
    )

    model_result["classification"] = (
        "prospective, output-blind, preregistered current-build unseen-geometry "
        "transfer over the complete profile and direction matrix"
    )
    model_result["remainingAlgorithmBoundaries"] = []
    model_result["nextRequiredEvidence"] = (
        "production Walle dynamic integration followed by physical Retina "
        "color/compositor and fresh zero-unequal-byte frame gates"
    )
    model_result["prospectiveUnseenGeometryTransferPassed"] = True

    return {
        "combinedTransitionGeometryHoldoutLocalMacOS2661ResultSchemaVersion": (
            RESULT_SCHEMA_VERSION
        ),
        "classification": (
            "prospective output-blind exact combined transition geometry transfer"
        ),
        "status": "passed",
        "captureCommit": next(iter(capture_commits)),
        "captureBinarySHA256": next(iter(capture_binaries)),
        "preregistration": {
            "path": str(preregistration_path),
            "sha256": sha256_file(preregistration_path),
            "appleOutputsObservedAtFreeze": preregistration[
                "appleOutputsObservedAtFreeze"
            ],
        },
        "timelineCount": len(timeline_results),
        "stateCount": model_result["stateCount"],
        "timelines": timeline_results,
        "modelResult": model_result,
        "prospectiveUnseenGeometryTransferPassed": True,
        "physicalRetinaColorCompositorTransferPassed": False,
        "independentFreshWalleZeroByteFramePassed": False,
        "liquidGlassParityEstablished": False,
        "productionShaderChanged": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.capture_root, arguments.preregistration)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
