#!/usr/bin/env python3
"""Aggregate all prospectively frozen presentation-lifetime cases."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


AGGREGATE_SCHEMA_VERSION = 1
VALIDATION_SCHEMA_VERSION = 1
CASES = {
    ("clear", "light", "materialize", "circle-452-center"),
    ("clear", "light", "dematerialize", "circle-453-center"),
    ("clear", "dark", "materialize", "circle-460-center"),
    ("clear", "dark", "dematerialize", "circle-461-center"),
    ("regular", "light", "materialize", "circle-468-center"),
    ("regular", "light", "dematerialize", "circle-469-center"),
    ("regular", "dark", "materialize", "circle-476-center"),
    ("regular", "dark", "dematerialize", "circle-477-center"),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def mapping(value: Any, label: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{label} is not an object")
    return value


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        return mapping(json.loads(path.read_text(encoding="utf-8")), label)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        error.add_note(f"while reading {path}")
        raise


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def aggregate(
    preregistration_path: Path,
    validation_paths: list[Path],
) -> dict[str, Any]:
    preregistration = load_json(preregistration_path, "preregistration")
    require(
        preregistration.get(
            "transitionPresentationLifetimeHoldoutPreregistrationSchemaVersion"
        )
        == 1,
        "preregistration schema differs",
    )
    require(len(validation_paths) == len(CASES), "validation count differs")
    cases: list[dict[str, Any]] = []
    identities: set[tuple[str, str, str, str]] = set()
    timeline_hashes: set[str] = set()
    png_tree_hashes: set[str] = set()
    capture_commits: set[str] = set()
    maximum_state_bracket = 0.0
    maximum_capture_duration = 0.0
    maximum_progress_error = 0.0
    for index, path in enumerate(validation_paths):
        result = load_json(path, f"validation {index}")
        profile = mapping(result.get("profile"), f"validation {index} profile")
        capture = mapping(result.get("capture"), f"validation {index} capture")
        conclusion = mapping(
            result.get("sealedConclusion"), f"validation {index} conclusion"
        )
        evidence = mapping(result.get("evidence"), f"validation {index} evidence")
        identity = (
            profile.get("material"),
            profile.get("appearance"),
            profile.get("direction"),
            profile.get("geometry"),
        )
        require(
            result.get("transitionPresentationLifetimeHoldoutValidationSchemaVersion")
            == VALIDATION_SCHEMA_VERSION
            and result.get("status") == "passed"
            and result.get("authority") == "prospective-holdout"
            and identity in CASES
            and capture.get("debuggerUsed") is False
            and capture.get("dynamicUniformReplayUsed") is False
            and capture.get("sampleCount") == 33
            and capture.get("presentationStateCount") == 66
            and capture.get("glassBackgroundPresenceCount") == 64
            and capture.get("glassForegroundPresenceCount") == 62
            and capture.get("uniquePixelSHA256Count") == 33
            and capture.get("uniquePngSHA256Count") == 33
            and conclusion.get(
                "observerIndependentPresentationLifetimeTransferPassedForCase"
            )
            is True
            and conclusion.get("appearanceDependentRemovalObservedForCase") is False
            and conclusion.get("productionShaderChanged") is False
            and conclusion.get("liquidGlassParityEstablished") is False,
            f"validation {index} did not pass its frozen case",
        )
        require(identity not in identities, "duplicate profile validation")
        identities.add(identity)
        timeline_hash = evidence.get("timelineSHA256")
        png_tree_hash = capture.get("pngTreeSHA256")
        capture_commit = evidence.get("captureCommit")
        require(
            isinstance(timeline_hash, str)
            and len(timeline_hash) == 64
            and isinstance(png_tree_hash, str)
            and len(png_tree_hash) == 64,
            f"validation {index} digest differs",
        )
        require(
            isinstance(capture_commit, str) and len(capture_commit) == 40,
            f"validation {index} capture commit differs",
        )
        timeline_hashes.add(timeline_hash)
        png_tree_hashes.add(png_tree_hash)
        capture_commits.add(capture_commit)
        maximum_state_bracket = max(
            maximum_state_bracket, capture["maximumStateBracketSeconds"]
        )
        maximum_capture_duration = max(
            maximum_capture_duration, capture["maximumWindowCaptureSeconds"]
        )
        maximum_progress_error = max(
            maximum_progress_error,
            capture["maximumAbsoluteRequestedProgressError"],
        )
        cases.append(
            {
                "caseId": result.get("caseId"),
                "profile": profile,
                "captureCommit": capture_commit,
                "validationSHA256": sha256(path),
                "timelineSHA256": timeline_hash,
                "pngTreeSHA256": png_tree_hash,
                "maximumStateBracketSeconds": capture["maximumStateBracketSeconds"],
                "maximumWindowCaptureSeconds": capture["maximumWindowCaptureSeconds"],
                "maximumAbsoluteRequestedProgressError": capture[
                    "maximumAbsoluteRequestedProgressError"
                ],
            }
        )
    require(identities == CASES, "prospective case matrix is incomplete")
    require(
        len(timeline_hashes) == len(CASES) and len(png_tree_hashes) == len(CASES),
        "case output identities are not unique",
    )
    require(len(capture_commits) == 1, "cases did not run from one frozen commit")
    cases.sort(
        key=lambda case: (
            case["profile"]["material"],
            case["profile"]["appearance"],
            case["profile"]["direction"],
        )
    )
    return {
        "transitionPresentationLifetimeHoldoutAggregateSchemaVersion": (
            AGGREGATE_SCHEMA_VERSION
        ),
        "status": "passed",
        "authority": "prospective-holdout-matrix",
        "captureCommit": next(iter(capture_commits)),
        "caseCount": len(cases),
        "cases": cases,
        "matrixTotals": {
            "windowServerFrameCount": len(cases) * 33,
            "presentationStateCount": len(cases) * 66,
            "glassBackgroundPresenceCount": len(cases) * 64,
            "glassForegroundPresenceCount": len(cases) * 62,
            "maximumStateBracketSeconds": maximum_state_bracket,
            "maximumWindowCaptureSeconds": maximum_capture_duration,
            "maximumAbsoluteRequestedProgressError": maximum_progress_error,
        },
        "evidence": {
            "preregistrationSHA256": sha256(preregistration_path),
            "calibrationResultSHA256": preregistration["calibrationEvidence"]["sha256"],
        },
        "sealedConclusion": {
            "observerIndependentPresentationLifetimeTransferPassed": True,
            "appearanceDependentPresentationRemovalLawRejected": True,
            "historicalCombinedSnapshotFailureWasNotProductRemovalProof": True,
            "presentationLifetimeGateClosedForFrozenProfileMatrix": True,
            "capturedInputOpticalTemporalMeshSourceMipColorTransferPassed": False,
            "physicalRetinaOutputTransferPassed": False,
            "independentWalleZeroByteParityPassed": False,
            "productionShaderChanged": False,
            "liquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("preregistration", type=Path)
    parser.add_argument("validations", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = aggregate(arguments.preregistration, arguments.validations)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
