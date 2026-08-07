#!/usr/bin/env python3
"""Aggregate the frozen four-profile materialize uniform holdout matrix."""

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_transition_uniform_profile_holdout as validator


AGGREGATE_SCHEMA_VERSION = 1


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def mapping(value: object, label: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping), f"{label} is not an object")
    return value


def sequence(value: object, label: str) -> list[Any]:
    require(isinstance(value, list), f"{label} is not an array")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_validation(path: Path) -> Mapping[str, Any]:
    value = mapping(json.loads(path.read_text(encoding="utf-8")), f"validation {path}")
    profile = mapping(value.get("profile"), "validation profile")
    conclusion = mapping(value.get("conclusion"), "validation conclusion")
    uniform = mapping(value.get("uniformAnalysis"), "uniform analysis")
    frames = mapping(value.get("windowServerFrames"), "WindowServer frames")
    require(
        value.get("transitionUniformProfileHoldoutValidationSchemaVersion") == 1
        and value.get("classification")
        == (
            "prospective direct-Retina materialize numeric uniform transfer; "
            "one case of the frozen four-profile matrix"
        )
        and profile.get("direction") == "materialize"
        and conclusion.get("captureIntegrityPassed") is True
        and conclusion.get("numericMaterializeTransferPassedForCase") is True
        and conclusion.get("allNumericWordsExact") is True
        and conclusion.get("numericMismatchCount") == 0
        and conclusion.get("fourProfileMatrixComplete") is False
        and conclusion.get("productionShaderChangeAuthorized") is False
        and uniform.get("numericComparisonCount") == 1_504
        and uniform.get("numericExactMatchCount") == 1_504
        and uniform.get("structuredRecordCount") == 32
        and frames.get("count") == 33
        and frames.get("distinctSHA256Count") == 33,
        "per-case validation contract differs",
    )
    return value


def aggregate(paths: Sequence[Path]) -> dict[str, Any]:
    require(len(paths) == 4, "exactly four validation results are required")
    values = [load_validation(path) for path in paths]
    identities = {
        (
            value["profile"]["material"],
            value["profile"]["appearance"],
            value["profile"]["geometry"],
        )
        for value in values
    }
    require(identities == set(validator.EXPECTED_CASES), "profile matrix differs")
    commits = {value.get("captureCommit") for value in values}
    require(len(commits) == 1, "holdout cases do not share one frozen commit")
    calibration_hashes = {value.get("openedCalibrationSHA256") for value in values}
    require(len(calibration_hashes) == 1, "opened calibration identity differs")

    frame_hashes = [
        digest
        for value in values
        for digest in mapping(
            mapping(value.get("windowServerFrames"), "frames").get("sha256"),
            "frame hashes",
        ).values()
    ]
    require(
        len(frame_hashes) == 132 and len(set(frame_hashes)) == 132,
        "matrix WindowServer frames are not all distinct",
    )
    ordered = sorted(values, key=lambda value: str(value["caseId"]))
    return {
        "transitionUniformProfileHoldoutAggregateSchemaVersion": (
            AGGREGATE_SCHEMA_VERSION
        ),
        "classification": (
            "prospective direct-Retina transfer of all 47 numeric materialize "
            "glassBackground inputs across the frozen four-profile matrix"
        ),
        "captureCommit": commits.pop(),
        "openedCalibrationSHA256": calibration_hashes.pop(),
        "aggregate": {
            "profileCount": len(ordered),
            "dynamicStateCount": 128,
            "numericFieldCount": 47,
            "numericComparisonCount": sum(
                int(value["uniformAnalysis"]["numericComparisonCount"])
                for value in ordered
            ),
            "numericExactMatchCount": sum(
                int(value["uniformAnalysis"]["numericExactMatchCount"])
                for value in ordered
            ),
            "numericMismatchCount": 0,
            "structuredRecordCount": sum(
                int(value["uniformAnalysis"]["structuredRecordCount"])
                for value in ordered
            ),
            "windowServerFrameCount": len(frame_hashes),
            "distinctWindowServerFrameCount": len(set(frame_hashes)),
        },
        "cases": [
            {
                "caseId": value["caseId"],
                "profile": value["profile"],
                "validationSHA256": sha256_file(path),
                "timelineSHA256": value["inputs"]["timelineSHA256"],
                "nativeClampResultSHA256": value["inputs"]["nativeClampResultSHA256"],
                "numericComparisonCount": value["uniformAnalysis"][
                    "numericComparisonCount"
                ],
                "numericExactMatchCount": value["uniformAnalysis"][
                    "numericExactMatchCount"
                ],
            }
            for value, path in sorted(
                zip(values, paths, strict=True), key=lambda pair: pair[0]["caseId"]
            )
        ],
        "conclusion": {
            "fourProfileNumericMaterializeTransferEstablished": True,
            "allSixThousandSixteenNumericWordsExact": True,
            "dematerializeTransferEstablished": False,
            "nestedResolvedColorTransferEstablished": False,
            "meshSourceBackdropMipGenerationEstablished": False,
            "physicalPixelParityEstablished": False,
            "independentWalleZeroByteFrameEstablished": False,
            "liquidGlassParityEstablished": False,
            "productionShaderChangeAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("validation", type=Path, nargs=4)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = aggregate(arguments.validation)
    numeric = result["aggregate"]
    require(
        numeric["numericComparisonCount"] == 6_016
        and numeric["numericExactMatchCount"] == 6_016,
        "aggregate numeric acceptance differs",
    )
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
        print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
