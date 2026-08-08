#!/usr/bin/env python3
"""Aggregate the frozen four-profile dematerialize uniform holdout."""

import argparse
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_transition_uniform_dematerialize_holdout as validator
import validate_transition_uniform_profile_holdout as common


AGGREGATE_SCHEMA_VERSION = 1
ABSENT_FRAME_NAME = "transition-dematerialize-32-rgba8.png"
ABSENT_FRAME_SHA256 = (
    "f93a15f6884c8eccdf4b94203f748def9512e3137538aea2b99a53ece39b48a8"
)


def load_validation(path: Path) -> Mapping[str, Any]:
    value = common.load_json(path, f"dematerialize validation {path}")
    profile = common.mapping(value.get("profile"), "dematerialize profile")
    conclusion = common.mapping(value.get("conclusion"), "dematerialize conclusion")
    uniform = common.mapping(value.get("uniformAnalysis"), "dematerialize uniform")
    frames = common.mapping(value.get("windowServerFrames"), "dematerialize frames")
    common.require(
        value.get("transitionUniformDematerializeHoldoutValidationSchemaVersion")
        == 1
        and value.get("classification")
        == (
            "prospective direct-Retina dematerialize numeric uniform transfer; "
            "one case of the frozen four-profile matrix"
        )
        and profile.get("direction") == "dematerialize"
        and conclusion.get("captureIntegrityPassed") is True
        and conclusion.get("numericDematerializeTransferPassedForCase") is True
        and conclusion.get("allNumericWordsExact") is True
        and conclusion.get("numericMismatchCount") == 0
        and conclusion.get("fourProfileMatrixComplete") is False
        and conclusion.get("productionShaderChangeAuthorized") is False
        and uniform.get("numericComparisonCount") == 1_457
        and uniform.get("numericExactMatchCount") == 1_457
        and uniform.get("structuredRecordCount") == 31
        and frames.get("count") == 33
        and frames.get("distinctSHA256Count") == 33,
        "dematerialize per-case validation differs",
    )
    return value


def aggregate(paths: Sequence[Path]) -> dict[str, Any]:
    common.require(len(paths) == 4, "exactly four dematerialize results are required")
    values = [load_validation(path) for path in paths]
    identities = {
        (
            value["profile"]["material"],
            value["profile"]["appearance"],
            value["profile"]["geometry"],
        )
        for value in values
    }
    common.require(
        identities == set(validator.EXPECTED_CASES),
        "dematerialize matrix differs",
    )
    commits = {value.get("captureCommit") for value in values}
    common.require(
        len(commits) == 1,
        "dematerialize cases do not share one frozen commit",
    )
    calibration_hashes = {value.get("openedCalibrationSHA256") for value in values}
    common.require(
        len(calibration_hashes) == 1,
        "dematerialize calibration identity differs",
    )

    occurrences: defaultdict[str, list[tuple[str, str]]] = defaultdict(list)
    for value in values:
        hashes = common.mapping(
            common.mapping(
                value.get("windowServerFrames"), "dematerialize frames"
            ).get("sha256"),
            "dematerialize frame hashes",
        )
        for name, digest in hashes.items():
            common.require(
                isinstance(name, str) and isinstance(digest, str),
                "dematerialize frame digest differs",
            )
            occurrences[digest].append((str(value["caseId"]), name))
    duplicates = {
        digest: locations
        for digest, locations in occurrences.items()
        if len(locations) > 1
    }
    common.require(
        sum(len(locations) for locations in occurrences.values()) == 132,
        "dematerialize frame count differs",
    )
    common.require(
        len(occurrences) == 129,
        "dematerialize distinct frame count differs",
    )
    common.require(
        set(duplicates) == {ABSENT_FRAME_SHA256},
        "dematerialize duplicate class differs",
    )
    duplicate_locations = duplicates[ABSENT_FRAME_SHA256]
    common.require(
        len(duplicate_locations) == 4
        and {name for _, name in duplicate_locations} == {ABSENT_FRAME_NAME}
        and {case for case, _ in duplicate_locations}
        == {str(value["caseId"]) for value in values},
        "dematerialize common absent endpoint differs",
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
    common.require(
        numeric_count == 5_828 and exact_count == 5_828,
        "dematerialize numeric aggregate differs",
    )
    return {
        "transitionUniformDematerializeHoldoutAggregateSchemaVersion": (
            AGGREGATE_SCHEMA_VERSION
        ),
        "classification": (
            "prospective direct-Retina transfer of all 47 numeric "
            "dematerialize glassBackground inputs across four profiles"
        ),
        "captureCommit": commits.pop(),
        "openedCalibrationSHA256": calibration_hashes.pop(),
        "aggregate": {
            "profileCount": 4,
            "dynamicStateCount": 124,
            "numericFieldCount": 47,
            "numericComparisonCount": numeric_count,
            "numericExactMatchCount": exact_count,
            "numericMismatchCount": 0,
            "structuredRecordCount": 124,
            "windowServerFrameCount": 132,
            "distinctWindowServerFrameCount": 129,
            "duplicateFrameClassCount": 1,
            "commonAbsentEndpointSHA256": ABSENT_FRAME_SHA256,
            "commonAbsentEndpointOccurrences": [
                {"caseId": case, "frame": name}
                for case, name in sorted(duplicate_locations)
            ],
        },
        "cases": [
            {
                "caseId": value["caseId"],
                "profile": value["profile"],
                "validationSHA256": common.sha256_file(path),
                "timelineSHA256": value["inputs"]["timelineSHA256"],
                "nativeClampResultSHA256": value["inputs"][
                    "nativeClampResultSHA256"
                ],
                "numericComparisonCount": 1_457,
                "numericExactMatchCount": 1_457,
            }
            for value, path in ordered_pairs
        ],
        "conclusion": {
            "fourProfileNumericDematerializeTransferEstablished": True,
            "allFiveThousandEightHundredTwentyEightNumericWordsExact": True,
            "realDynamicRecordTopologyTransferred": True,
            "commonAbsentEndpointRelationTransferred": True,
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
