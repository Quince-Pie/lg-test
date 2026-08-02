#!/usr/bin/env python3
"""Validate same-diameter producer-mesh phase calibration metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import validate_dynamic_allocation_holdout as holdout


EXPECTED_SAMPLE_INDICES = tuple(range(1, 33))
EXPECTED_GEOMETRIES = frozenset(
    {
        "circle-640-center",
        "circle-640-integer",
        "circle-640-phase-0500-even",
        "circle-640-phase-0500-signed",
    }
)
CLASSIFICATION = "post-opening-primary-mesh-center-phase-calibration"


def validate(path: Path, *, expected_geometry: str) -> dict[str, object]:
    result = holdout.validate(
        path,
        expected_geometry=expected_geometry,
        expected_sample_indices=EXPECTED_SAMPLE_INDICES,
        classification=CLASSIFICATION,
        allowed_geometries=EXPECTED_GEOMETRIES,
    )
    acceptance = holdout.mapping(
        result.get("acceptance"), "frozen geometry-specific comparison"
    )
    aggregate = holdout.mapping(result.get("aggregate"), "calibration aggregate")
    result["meshCalibration"] = {
        "captureIntegrityPassed": True,
        "stateCount": aggregate.get("stateCount"),
        "runtimeScaleLawExactEveryState": aggregate.get(
            "runtimeScaleLawExactEveryState"
        ),
        "primaryProducerSourceQLawExactEveryState": True,
        "oldGeometrySpecificPolicyPassed": acceptance.get("passed"),
        "acceptanceRole": (
            "same-diameter center-phase intervention only; this is not an "
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
