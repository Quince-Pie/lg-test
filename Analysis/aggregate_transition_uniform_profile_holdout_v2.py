#!/usr/bin/env python3
"""Aggregate the corrected frozen v2 four-profile uniform holdout."""

import argparse
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_transition_uniform_profile_holdout as v1
import validate_transition_uniform_profile_holdout_v2 as validator


AGGREGATE_SCHEMA_VERSION = 1
ABSENT_FRAME_NAME = "transition-materialize-00-rgba8.png"


def load_validation(path: Path) -> Mapping[str, Any]:
    value = v1.load_json(path, f"v2 validation {path}")
    profile = v1.mapping(value.get("profile"), "v2 validation profile")
    conclusion = v1.mapping(value.get("conclusion"), "v2 conclusion")
    uniform = v1.mapping(value.get("uniformAnalysis"), "v2 uniform analysis")
    frames = v1.mapping(value.get("windowServerFrames"), "v2 frames")
    v1.require(
        value.get("transitionUniformProfileHoldoutV2ValidationSchemaVersion") == 1
        and value.get("classification")
        == (
            "corrected prospective direct-Retina v2 materialize numeric uniform "
            "transfer; one case of the frozen four-profile matrix"
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
        "v2 per-case validation differs",
    )
    return value


def aggregate(paths: Sequence[Path]) -> dict[str, Any]:
    v1.require(len(paths) == 4, "exactly four v2 results are required")
    values = [load_validation(path) for path in paths]
    identities = {
        (
            value["profile"]["material"],
            value["profile"]["appearance"],
            value["profile"]["geometry"],
        )
        for value in values
    }
    v1.require(identities == set(validator.EXPECTED_CASES), "v2 matrix differs")
    commits = {value.get("captureCommit") for value in values}
    v1.require(len(commits) == 1, "v2 cases do not share one frozen commit")
    calibration_hashes = {value.get("openedCalibrationSHA256") for value in values}
    v1.require(len(calibration_hashes) == 1, "v2 calibration identity differs")

    occurrences: defaultdict[str, list[tuple[str, str]]] = defaultdict(list)
    for value in values:
        hashes = v1.mapping(
            v1.mapping(value.get("windowServerFrames"), "v2 frames").get("sha256"),
            "v2 frame hashes",
        )
        for name, digest in hashes.items():
            v1.require(
                isinstance(name, str) and isinstance(digest, str),
                "frame digest differs",
            )
            occurrences[digest].append((str(value["caseId"]), name))
    duplicates = {
        digest: locations
        for digest, locations in occurrences.items()
        if len(locations) > 1
    }
    v1.require(
        sum(len(locations) for locations in occurrences.values()) == 132,
        "v2 frame count differs",
    )
    v1.require(len(occurrences) == 129, "v2 distinct frame count differs")
    v1.require(len(duplicates) == 1, "v2 duplicate-class count differs")
    duplicate_digest, duplicate_locations = next(iter(duplicates.items()))
    v1.require(
        len(duplicate_locations) == 4
        and {name for _, name in duplicate_locations} == {ABSENT_FRAME_NAME}
        and {case for case, _ in duplicate_locations}
        == {value["caseId"] for value in values},
        "v2 common absent endpoint relation differs",
    )

    ordered_pairs = sorted(
        zip(values, paths, strict=True), key=lambda pair: str(pair[0]["caseId"])
    )
    numeric_count = sum(
        int(value["uniformAnalysis"]["numericComparisonCount"])
        for value, _ in ordered_pairs
    )
    exact_count = sum(
        int(value["uniformAnalysis"]["numericExactMatchCount"])
        for value, _ in ordered_pairs
    )
    v1.require(
        numeric_count == 6_016 and exact_count == 6_016,
        "v2 numeric aggregate differs",
    )
    return {
        "transitionUniformProfileHoldoutV2AggregateSchemaVersion": (
            AGGREGATE_SCHEMA_VERSION
        ),
        "classification": (
            "corrected prospective direct-Retina transfer of all 47 numeric "
            "materialize glassBackground inputs across four profiles"
        ),
        "captureCommit": commits.pop(),
        "openedCalibrationSHA256": calibration_hashes.pop(),
        "aggregate": {
            "profileCount": 4,
            "dynamicStateCount": 128,
            "numericFieldCount": 47,
            "numericComparisonCount": numeric_count,
            "numericExactMatchCount": exact_count,
            "numericMismatchCount": 0,
            "structuredRecordCount": 128,
            "windowServerFrameCount": 132,
            "distinctWindowServerFrameCount": 129,
            "duplicateFrameClassCount": 1,
            "commonAbsentEndpointSHA256": duplicate_digest,
            "commonAbsentEndpointOccurrences": [
                {"caseId": case, "frame": name}
                for case, name in sorted(duplicate_locations)
            ],
        },
        "cases": [
            {
                "caseId": value["caseId"],
                "profile": value["profile"],
                "validationSHA256": v1.sha256_file(path),
                "timelineSHA256": value["inputs"]["timelineSHA256"],
                "nativeClampResultSHA256": value["inputs"]["nativeClampResultSHA256"],
                "numericComparisonCount": 1_504,
                "numericExactMatchCount": 1_504,
            }
            for value, path in ordered_pairs
        ],
        "conclusion": {
            "fourProfileNumericMaterializeTransferEstablished": True,
            "allSixThousandSixteenNumericWordsExact": True,
            "commonAbsentEndpointRelationTransferred": True,
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
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
        print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
