#!/usr/bin/env python3
"""Audit failed capture_backdrop operand run 30764095287 without promoting it."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_dynamic_allocation_surviving_path_threshold as surviving


EXPECTED_RUN_ID = 30_764_095_287
EXPECTED_HEAD_SHA = "56ee24016165155da617898c476a08ca1494f168"
EXPECTED_TIMELINE_SHA256 = (
    "b9497caae11dd25fd010c1c0ba235d9375aee9dfdc136251cab6f4db786e57b1"
)
EXPECTED_GATE_ERROR = "capture_backdrop operand metadata differs"
CLASSIFICATION = (
    "post-opening-audit-of-failed-preregistered-capture-backdrop-operand-"
    "replay; not-a-prospective-pass-or-upstream-crop-policy"
)
EXPECTED_RECT_COUNTS = {
    (199, 172, 644, 653): 8,
    (199, 172, 645, 652): 14,
    (199, 173, 645, 652): 5,
    (200, 172, 644, 653): 14,
    (200, 173, 642, 651): 1,
    (200, 173, 643, 650): 1,
    (200, 173, 643, 651): 68,
    (200, 174, 643, 650): 2,
    (201, 173, 642, 651): 1,
}


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} differs")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label} differs")
    return value


def analyze(timeline_path: Path, *, run_id: int, head_sha: str) -> dict[str, Any]:
    if run_id != EXPECTED_RUN_ID or head_sha != EXPECTED_HEAD_SHA:
        raise ValueError("failed-run identity differs")
    timeline_sha = surviving.holdout.sha256_file(timeline_path)
    if timeline_sha != EXPECTED_TIMELINE_SHA256:
        raise ValueError("failed-run timeline digest differs")

    corrected = surviving.validate(timeline_path)
    aggregate = mapping(corrected.get("aggregate"), "corrected aggregate")
    replay = mapping(
        aggregate.get("captureBackdropOperandReplay"), "corrected operand replay"
    )
    records = [
        mapping(value, "corrected record")
        for value in sequence(corrected.get("records"), "corrected records")
    ]
    operands = [
        mapping(record.get("captureBackdropOperands"), "corrected operands")
        for record in records
    ]

    rect_counts = Counter(
        tuple(int(component) for component in sequence(item.get("rect"), "rect"))
        for item in operands
    )
    scale_bits = {int(item.get("scaleBits", -1)) for item in operands}
    origin_values = {
        tuple(int(component) for component in sequence(item.get("origin"), "origin"))
        for item in operands
    }
    affine_values = {
        tuple(float(component) for component in sequence(item.get("affine"), "affine"))
        for item in operands
    }
    transform_counts = Counter(str(item.get("transformBranch")) for item in operands)

    call_site = mapping(aggregate.get("producerGeometryCallSite"), "producer call site")
    capture_code = mapping(call_site.get("captureBackdrop"), "capture code")
    direct_calls = [
        mapping(value, "capture direct call")
        for value in sequence(capture_code.get("directCalls"), "capture direct calls")
    ]
    region_calls = [
        call
        for call in direct_calls
        if call.get("sourceInstructionOffset")
        == surviving.CAPTURE_BACKDROP_REGION_ITERATE_CALL_OFFSET
    ]
    if (
        len(records) != 114
        or corrected.get("captureEvidenceSchemaVersion") != 5
        or rect_counts != Counter(EXPECTED_RECT_COUNTS)
        or scale_bits != {0x3F03_EB10}
        or origin_values != {(0, 0)}
        or affine_values != {(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)}
        or transform_counts != Counter({"identity": 114})
        or any(item.get("schemaVersion") != 1 for item in operands)
        or any(item.get("shapePointerNonzero") is not True for item in operands)
        or any(item.get("transformPointerNonzero") is not False for item in operands)
        or any(item.get("primaryPositionExact") is not True for item in operands)
        or any(item.get("primarySourceExact") is not True for item in operands)
        or replay.get("captureCount") != 114
        or replay.get("primaryPositionComponentCount") != 912
        or replay.get("primaryPositionMismatchedComponents") != 0
        or replay.get("primarySourceComponentCount") != 912
        or replay.get("primarySourceMismatchedComponents") != 0
        or len(region_calls) != 1
        or region_calls[0].get("targetCodeSHA256")
        != surviving.CAPTURE_BACKDROP_EXPECTED_REGION_ITERATE_PREFIX_SHA256
        or region_calls[0].get("targetSymbol")
        != surviving.CAPTURE_BACKDROP_REGION_ITERATE_SYMBOL
        or region_calls[0].get("targetSymbolOffset") != "0x0"
    ):
        raise ValueError("failed-run corrected operand audit differs")

    q = mapping(aggregate.get("primaryProducerSourceQ"), "source-q aggregate")
    allocation = mapping(aggregate.get("allocationInvariants"), "allocation aggregate")
    return {
        "dynamicAllocationCaptureBackdropOperandFailedRunAnalysisSchemaVersion": 1,
        "classification": CLASSIFICATION,
        "runID": run_id,
        "headSHA": head_sha,
        "workflowConclusion": "failure",
        "frozenGateError": EXPECTED_GATE_ERROR,
        "prospectiveGatePassed": False,
        "inputTimelineArtifact": timeline_path.parent.name + "/" + timeline_path.name,
        "inputTimelineSHA256": timeline_sha,
        "aggregate": {
            "recordCount": len(records),
            "primarySourceQ": dict(q),
            "allocationInvariants": dict(allocation),
            "captureBackdropOperandReplay": {
                "captureCount": replay.get("captureCount"),
                "primaryPositionComponentCount": replay.get(
                    "primaryPositionComponentCount"
                ),
                "primaryPositionMismatchedComponents": replay.get(
                    "primaryPositionMismatchedComponents"
                ),
                "primarySourceComponentCount": replay.get(
                    "primarySourceComponentCount"
                ),
                "primarySourceMismatchedComponents": replay.get(
                    "primarySourceMismatchedComponents"
                ),
                "transformBranchCounts": dict(sorted(transform_counts.items())),
                "shapePointerNonzeroCount": 114,
                "originValues": [list(value) for value in sorted(origin_values)],
                "affineValues": [list(value) for value in sorted(affine_values)],
                "contextScaleBits": [f"0x{value:08x}" for value in sorted(scale_bits)],
                "allowNumericTolerance": False,
            },
            "capturedRectangleFrequency": [
                {"rect": list(rect), "count": count}
                for rect, count in sorted(rect_counts.items())
            ],
        },
        "openedCodeFacts": {
            "primaryPositionRule": (
                "floor(scale * lower) and ceil(scale * upper), stored as the "
                "four position pairs"
            ),
            "primarySourceRule": (
                "identity-branch fused residual-times-inverse-scale plus the "
                "integer-origin-adjusted rectangle bound"
            ),
            "selectedRegionHandleStackOffset": 0x2A0,
            "selectedRegionIteratorStackOffset": 0x3C0,
            "selectedRegionIteratorCallOffset": (
                surviving.CAPTURE_BACKDROP_REGION_ITERATE_CALL_OFFSET
            ),
            "selectedRegionIteratorSymbol": surviving.CAPTURE_BACKDROP_REGION_ITERATE_SYMBOL,
            "selectedRegionIteratorPrefixSHA256": (
                surviving.CAPTURE_BACKDROP_EXPECTED_REGION_ITERATE_PREFIX_SHA256
            ),
            "originBoundsPointerStackOffset": 0x190,
            "originBoundsByteCount": 16,
            "selectedRegionIntersectionInstructionRange": [0x2480, 0x24DC],
            "selectedRegionIntersectionCondition": (
                "null transform pointer and nonzero shape pointer"
            ),
        },
        "conclusion": {
            "frozenOperandGatePassed": False,
            "failureWasIncorrectNonzeroTransformRequirement": True,
            "retrospectiveInstructionOrderReplayExact": True,
            "primaryPositionAndSourceWordsExact": True,
            "selectedRegionPolicyRecovered": False,
            "requiresSelectedRegionCapture": True,
            "requiresUnseenGeometryTransfer": True,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = analyze(
        arguments.timeline,
        run_id=arguments.run_id,
        head_sha=arguments.head_sha,
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
