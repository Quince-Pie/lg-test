#!/usr/bin/env python3
"""Freeze the preregistered inputClamp arithmetic transfer result."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import validate_dynamic_allocation_holdout as holdout
import validate_transition_input_clamp_probe as clamp


CLASSIFICATION = (
    "prospective-transfer-of-preregistered-input-clamp-arithmetic-to-newly-"
    "timed-clear-light-states; not-an-unseen-rendering-or-profile-transfer"
)


def validate_result(result: Mapping[str, Any]) -> None:
    aggregate = holdout.mapping(result.get("aggregate"), "inputClamp aggregate")
    conclusion = holdout.mapping(result.get("conclusion"), "inputClamp conclusion")
    if (
        result.get("transitionInputClampProbeResultSchemaVersion") != 1
        or result.get("classification") != clamp.CLASSIFICATION
        or result.get("probeSchemaVersion") != 2
        or aggregate.get("sampleCount") != 32
        or aggregate.get("candidateCount") != 28
        or aggregate.get("recoveredTransferCandidate")
        != clamp.RECOVERED_TRANSFER_CANDIDATE
        or aggregate.get("recoveredTransferCandidateExact") is not True
        or aggregate.get("exactEveryStateCandidateNames")
        != [clamp.RECOVERED_TRANSFER_CANDIDATE]
        or conclusion.get("captureIntegrityPassed") is not True
        or conclusion.get("affineExpandedTransferPassed") is not True
        or conclusion.get("productionShaderAuthorized") is not False
    ):
        raise ValueError("inputClamp affine transfer result differs")


def analyze(result_path: Path, *, run_id: int) -> dict[str, Any]:
    if run_id <= 0:
        raise ValueError("run ID must be positive")
    result = holdout.mapping(
        json.loads(result_path.read_text(encoding="utf-8")), "inputClamp result"
    )
    validate_result(result)
    aggregate = holdout.mapping(result.get("aggregate"), "inputClamp aggregate")
    records = result.get("records")
    if not isinstance(records, list) or len(records) != 32:
        raise ValueError("inputClamp transfer records differ")
    candidate = clamp.RECOVERED_TRANSFER_CANDIDATE
    counterexamples = [
        {
            "sampleIndex": record["sampleIndex"],
            "remainingBits": record["remainingBits"],
            "observedBits": record["observedInputClampBits"],
            "candidateBits": holdout.mapping(
                record.get("candidateDecodedBits"), "candidate decoded bits"
            )[candidate],
        }
        for record in records
        if holdout.mapping(
            record.get("candidateDecodedBits"), "candidate decoded bits"
        )[candidate]
        != record["observedInputClampBits"]
    ]
    if counterexamples:
        raise ValueError("inputClamp affine transfer has counterexamples")
    return {
        "transitionInputClampAffineTransferAnalysisSchemaVersion": 1,
        "classification": CLASSIFICATION,
        "runID": run_id,
        "inputValidatorResultArtifact": result_path.parent.name
        + "/"
        + result_path.name,
        "inputValidatorResultSHA256": holdout.sha256_file(result_path),
        "timelineSHA256": result["timelineSHA256"],
        "candidateName": candidate,
        "candidateFormula": {
            "encoded": "float32((1-k)*1.0f + k*1.15f)",
            "base": (
                "float32(float32(encoded * float32(1.0f/1.055f)) + "
                "float32(0.055f/1.055f))"
            ),
            "decode": "Darwin.powf(base, 2.4f)",
            "reciprocalBits": "3f72a76f",
            "offsetBits": "3d55891a",
        },
        "aggregate": {
            "sampleCount": aggregate["sampleCount"],
            "candidateCount": aggregate["candidateCount"],
            "candidateExactMatchCount": aggregate["exactMatchCounts"][candidate],
            "counterexampleCount": 0,
            "uniqueExactEveryStateCandidate": True,
            "exactMatchCounts": aggregate["exactMatchCounts"],
        },
        "records": [
            {
                "sampleIndex": record["sampleIndex"],
                "remaining": record["remaining"],
                "remainingBits": record["remainingBits"],
                "observedInputClamp": record["observedInputClamp"],
                "observedInputClampBits": record["observedInputClampBits"],
                "candidateBits": holdout.mapping(
                    record.get("candidateDecodedBits"), "candidate decoded bits"
                )[candidate],
            }
            for record in records
        ],
        "conclusion": {
            "preregisteredTemporalArithmeticTransferPassed": True,
            "zeroTolerance": True,
            "clearLightMaterializeDomainOnly": True,
            "requiresUnseenRenderingAndProfileTransfer": True,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = analyze(arguments.result, run_id=arguments.run_id)
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
        print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
