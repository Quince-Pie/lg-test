#!/usr/bin/env python3
"""Validate the frozen namespace-only ``prepare_layer_mask`` trace retry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import validate_prepare_layer_mask_instruction_trace as base


VALIDATION_SCHEMA_VERSION = 1
KNOWN_HELPER_CODE_SHA256 = (
    "f78c5fd222dc429152882dffb0b88a5535050351e3a2a5d7102a5abeca5c4c0c"
)


def validate(
    trace_path: Path,
    timeline_path: Path,
    expected_geometry: str = base.EXPECTED_GEOMETRY,
) -> dict[str, Any]:
    result = base.validate(trace_path, timeline_path, expected_geometry)
    helper = result["helper"]
    if helper.get("codeSHA256") != KNOWN_HELPER_CODE_SHA256:
        raise ValueError("failed-run prepare_layer_mask code identity differs")
    result[
        "prepareLayerMaskInstructionTraceRetryValidationSchemaVersion"
    ] = VALIDATION_SCHEMA_VERSION
    result["classification"] = (
        "prospectively frozen namespace-only retry of the structurally selected "
        "prepare_layer_mask helper-body calibration; the helper code identity "
        "opened before the failed callback is required bit for bit"
    )
    result["failedRun"] = {
        "runID": 31063528744,
        "failureStage": "helper-entry",
        "failureClass": "Python module constant ownership",
        "helperCodeSHA256": KNOWN_HELPER_CODE_SHA256,
        "helperCodeIdentityRepassed": True,
        "selectorOutcomeInFailedRun": None,
    }
    helper["codeExpectedBeforeOriginalCapture"] = False
    helper["codeExpectedBeforeRetry"] = True
    helper["failedRunCodeIdentityRepassed"] = True
    result["sealedConclusion"]["failedRunTechnicalFailurePreserved"] = True
    result["sealedConclusion"]["failedRunHelperCodeIdentityRepassed"] = True
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--expected-geometry", default=base.EXPECTED_GEOMETRY)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = validate(
        arguments.trace, arguments.timeline, arguments.expected_geometry
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
