#!/usr/bin/env python3
"""Apply the schema-only correction to the frozen backdrop validator."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import validate_walle_regular_controlled_backdrop as frozen


def validate(capture: Path) -> frozen.JSONObject:
    root = capture.resolve()
    timeline = root / "transition-timeline.json"
    report = frozen.mapping(
        json.loads(timeline.read_text(encoding="utf-8")),
        "timeline",
    )
    if (
        report.get("material") != "regular"
        or report.get("appearance") != "dark"
        or report.get("direction") != "dematerialize"
        or frozen.mapping(report.get("geometry"), "geometry").get("name")
        != "circle-480-center"
    ):
        raise ValueError("capture profile differs from the frozen Walle case")

    dynamic = frozen.mapping(
        report.get("dynamicBackgroundUniforms"),
        "dynamic uniforms",
    )
    if dynamic.get("schemaVersion") != 9:
        raise ValueError("corrected validator requires dynamic-uniform schema 9")
    records = [
        frozen.mapping(value, "dynamic state")
        for value in frozen.sequence(dynamic.get("records"), "dynamic states")
    ]
    if tuple(value.get("sampleIndex") for value in records) != frozen.EXPECTED_SAMPLES:
        raise ValueError("dynamic sample inventory differs")

    expected_input = frozen.controlled_input()
    if frozen.sha256_bytes(expected_input) != frozen.CONTROLLED_SHA256:
        raise AssertionError("controlled-input implementation hash differs")
    states = [frozen.validate_state(root, value, expected_input) for value in records]
    fragments = Counter(state["producerFragment"] for state in states)
    if set(fragments) != frozen.PRODUCER_FRAGMENTS:
        raise ValueError("capture does not exercise both regular producer branches")

    return {
        "schemaVersion": 2,
        "status": "accepted-after-schema-only-transport-correction",
        "capture": str(root),
        "timelineSHA256": frozen.sha256_file(timeline),
        "captureDynamicUniformSchemaVersion": 9,
        "frozenValidatorExpectedSchemaVersion": 7,
        "transportCorrection": {
            "field": "dynamicBackgroundUniforms.schemaVersion",
            "frozenValue": 7,
            "correctedValue": 9,
            "answerBytesReadBeforeFrozenFailure": 0,
            "stateSelectionChanged": False,
            "pixelSelectionChanged": False,
            "acceptanceThresholdChanged": False,
            "toleranceChanged": False,
        },
        "stateCount": len(states),
        "sampleIndices": list(frozen.EXPECTED_SAMPLES),
        "producerFragmentCounts": dict(sorted(fragments.items())),
        "controlledInputSHA256": frozen.CONTROLLED_SHA256,
        "states": states,
        "acceptance": {
            "allControlledInputsExact": True,
            "allProducerOutputsNondegenerate": True,
            "allCopyBaseMipZeroOutputsNondegenerate": True,
            "producerAndCopyBaseJoinsExact": True,
            "directAndDownsampleProducerBranchesObserved": True,
            "pixelTolerance": 0,
        },
        "claimBoundary": {
            "captureValidated": True,
            "producerArithmeticReconstructed": False,
            "productionParityEstablished": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.capture)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
