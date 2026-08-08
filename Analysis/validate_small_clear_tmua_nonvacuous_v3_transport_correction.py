#!/usr/bin/env python3
"""Apply the narrow final-input-dimension correction to the frozen v3 gate."""

import argparse
from collections.abc import Callable, Mapping
import json
from pathlib import Path
import re
from typing import Any

import validate_small_clear_tmua_nonvacuous_v3 as frozen


type JsonObject = dict[str, Any]
type PatternValidator = Callable[
    [Path, Mapping[str, Any], str, tuple[int, int], int],
    str,
]

FINAL_INPUT_LABEL = re.compile(r"sample ([0-9]+) final input", re.ASCII)


def corrected_pattern_validator(original: PatternValidator) -> PatternValidator:
    def validate(
        directory: Path,
        snapshot: Mapping[str, Any],
        label: str,
        dimensions: tuple[int, int],
        salt: int,
    ) -> str:
        match = FINAL_INPUT_LABEL.fullmatch(label)
        if match is None:
            return original(directory, snapshot, label, dimensions, salt)
        sample = int(match.group(1))
        frozen.v2.require(
            dimensions == (576, 448),
            "frozen final-input assumption was not the expected v3 value",
        )
        if 3 <= sample <= 9:
            corrected_dimensions = (576, 448)
        elif 10 <= sample <= 31:
            corrected_dimensions = (576, 384)
        else:
            frozen.v2.fail("final-input correction sample is outside the frozen grid")
        return original(
            directory,
            snapshot,
            label,
            corrected_dimensions,
            salt,
        )

    return validate


def validate_amendment(
    amendment_path: Path,
    capture_directory: Path,
    preregistration_path: Path,
) -> JsonObject:
    amendment = frozen.v2.load_json(amendment_path, "transport correction")
    frozen.v2.require(
        amendment.get("smallClearTmuaNonvacuousV3TransportCorrectionSchemaVersion")
        == 1,
        "transport correction schema differs",
    )
    expected_files = {
        "correctedValidatorSHA256": Path(__file__).resolve(),
        "frozenValidatorSHA256": Path(frozen.__file__).resolve(),
        "frozenPreregistrationSHA256": preregistration_path,
    }
    for field, path in expected_files.items():
        expected = amendment.get(field)
        frozen.v2.require(isinstance(expected, str), f"{field} is absent")
        frozen.v2.require(path.is_file(), f"{field} file is absent")
        frozen.v2.require(
            frozen.v2.sha256_file(path) == expected,
            f"{field} differs",
        )
    timeline_path = capture_directory / "transition-timeline.json"
    frozen.v2.require(timeline_path.is_file(), "capture timeline is absent")
    frozen.v2.require(
        frozen.v2.sha256_file(timeline_path) == amendment.get("timelineSHA256"),
        "capture timeline differs",
    )
    frozen.v2.require(
        amendment.get("correctedFinalInputDimensionSchedule")
        == {
            "samples3Through9": [576, 448],
            "samples10Through31": [576, 384],
        },
        "corrected dimension schedule differs",
    )
    return amendment


def validate(
    capture_directory: Path,
    preregistration_path: Path,
    preflight_path: Path,
    amendment_path: Path,
) -> JsonObject:
    amendment = validate_amendment(
        amendment_path,
        capture_directory,
        preregistration_path,
    )
    original = frozen.v2.validate_controlled_pattern
    frozen.v2.validate_controlled_pattern = corrected_pattern_validator(original)
    try:
        result = frozen.validate(
            capture_directory,
            preregistration_path,
            preflight_path,
        )
    finally:
        frozen.v2.validate_controlled_pattern = original
    result["transportCorrection"] = {
        "schemaVersion": 1,
        "classification": (
            "post-capture structural dimension correction with frozen pixel "
            "comparisons and zero tolerance"
        ),
        "answerPixelsKnownAtCorrection": True,
        "selectionChanged": False,
        "mutationChanged": False,
        "comparisonChanged": False,
        "toleranceChanged": False,
        "correctedField": "controlled final-input texture dimensions only",
        "amendmentSHA256": frozen.v2.sha256_file(amendment_path),
        "originalFrozenValidatorSHA256": amendment["frozenValidatorSHA256"],
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_directory", type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--preflight", required=True, type=Path)
    parser.add_argument("--amendment", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(
        arguments.capture_directory,
        arguments.preregistration,
        arguments.preflight,
        arguments.amendment,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
