#!/usr/bin/env python3
"""Validate dense post-opening allocation calibration metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import validate_dynamic_allocation_holdout as holdout


EXPECTED_SAMPLE_INDICES = tuple(range(1, 33))
CLASSIFICATION = "post-opening-dense-temporal-allocation-calibration"


def validate(path: Path, *, expected_geometry: str) -> dict[str, object]:
    result = holdout.validate(
        path,
        expected_geometry=expected_geometry,
        expected_sample_indices=EXPECTED_SAMPLE_INDICES,
        classification=CLASSIFICATION,
    )
    acceptance = holdout.mapping(
        result.get("acceptance"), "frozen holdout-policy comparison"
    )
    aggregate = holdout.mapping(result.get("aggregate"), "calibration aggregate")
    result["calibration"] = {
        "captureIntegrityPassed": True,
        "stateCount": aggregate.get("stateCount"),
        "runtimeScaleLawExactEveryState": aggregate.get(
            "runtimeScaleLawExactEveryState"
        ),
        "primaryProducerSourceQLawExactEveryState": True,
        "frozenGeometrySpecificPolicyPassed": acceptance.get("passed"),
        "acceptanceRole": (
            "capture integrity and discriminator evidence only; this is not an "
            "unseen holdout or production authorization"
        ),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--expected-geometry", required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = validate(
        arguments.report,
        expected_geometry=arguments.expected_geometry,
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
