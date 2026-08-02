#!/usr/bin/env python3
"""Open the preregistered QuartzCore capture_backdrop code evidence."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_dynamic_allocation_fixed_state as fixed
import validate_dynamic_allocation_holdout as holdout
import validate_dynamic_allocation_surviving_path_threshold as surviving


CLASSIFICATION = (
    "post-opening-analysis-of-preregistered-capture-backdrop-symbol-prefix-"
    "and-direct-call-targets; not-a-recovered-producer-mesh-policy"
)
EVIDENCE_STATUSES = frozenset(
    {
        "prospective-validator-pass",
        "retrospective-validator-correction-after-failed-ci-gate",
    }
)


def sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def control_flow_instruction(instruction: int, offset: int) -> dict[str, Any] | None:
    kind: str
    target: int | None = None
    if instruction & 0xFC00_0000 == 0x9400_0000:
        kind = "bl"
        target = offset + sign_extend(instruction & 0x03FF_FFFF, 26) * 4
    elif instruction & 0xFC00_0000 == 0x1400_0000:
        kind = "b"
        target = offset + sign_extend(instruction & 0x03FF_FFFF, 26) * 4
    elif instruction & 0xFF00_0010 == 0x5400_0000:
        kind = "b.cond"
        target = offset + sign_extend((instruction >> 5) & 0x7_FFFF, 19) * 4
    elif instruction & 0x7E00_0000 == 0x3400_0000:
        kind = "cbnz" if instruction & 0x0100_0000 else "cbz"
        target = offset + sign_extend((instruction >> 5) & 0x7_FFFF, 19) * 4
    elif instruction & 0x7E00_0000 == 0x3600_0000:
        kind = "tbnz" if instruction & 0x0100_0000 else "tbz"
        target = offset + sign_extend((instruction >> 5) & 0x3FFF, 14) * 4
    elif instruction & 0xFFFF_FC1F == 0xD61F_0000:
        kind = "br"
    elif instruction & 0xFFFF_FC1F == 0xD63F_0000:
        kind = "blr"
    elif instruction & 0xFFFF_FC1F == 0xD65F_0000:
        kind = "ret"
    else:
        return None
    result: dict[str, Any] = {
        "kind": kind,
        "offset": offset,
        "instruction": f"{instruction:08x}",
    }
    if target is not None:
        result["targetOffset"] = target
    return result


def decision_control_flow(payload: bytes) -> list[dict[str, Any]]:
    lower, upper = surviving.CAPTURE_BACKDROP_DECISION_CALL_RANGE
    return [
        branch
        for offset in range(lower, upper, 4)
        if (
            branch := control_flow_instruction(
                int.from_bytes(payload[offset : offset + 4], "little"), offset
            )
        )
        is not None
    ]


def direct_call_groups(calls: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for call in calls:
        image_offset = call.get("targetImageOffset")
        if not isinstance(image_offset, str):
            raise ValueError("direct-call target image offset is absent")
        grouped.setdefault(image_offset, []).append(call)
    result = []
    for image_offset, members in sorted(
        grouped.items(), key=lambda item: int(item[0], 16)
    ):
        hashes = {
            holdout.mapping(member.get("targetCode"), "target code").get("sha256")
            for member in members
        }
        symbols = {member.get("targetSymbol") for member in members}
        symbol_offsets = {member.get("targetSymbolOffset") for member in members}
        if len(hashes) != 1 or len(symbols) != 1 or len(symbol_offsets) != 1:
            raise ValueError("same-address direct-call metadata differs")
        result.append(
            {
                "targetImageOffset": image_offset,
                "targetSymbol": next(iter(symbols)),
                "targetSymbolOffset": next(iter(symbol_offsets)),
                "targetCodeSHA256": next(iter(hashes)),
                "sourceInstructionOffsets": [
                    int(member["sourceInstructionOffset"]) for member in members
                ],
            }
        )
    return result


def producer_call_site(timeline: Mapping[str, Any]) -> Mapping[str, Any]:
    uniforms = holdout.mapping(
        timeline.get("dynamicBackgroundUniforms"), "dynamic background uniforms"
    )
    evidence = holdout.mapping(
        uniforms.get("pathIsolationInterventions"), "path-isolation evidence"
    )
    call_sites = []
    for untyped_record in fixed.sequence(evidence.get("records"), "capture records"):
        record = holdout.mapping(untyped_record, "capture record")
        render = holdout.mapping(record.get("render"), "capture render")
        buffers = holdout.mapping(
            render.get("metalBufferSnapshots"), "Metal buffer snapshots"
        )
        for untyped_snapshot in fixed.sequence(
            buffers.get("snapshots"), "Metal buffer snapshot list"
        ):
            snapshot = holdout.mapping(untyped_snapshot, "Metal buffer snapshot")
            if "producerGeometryCallSite" in snapshot:
                call_sites.append(
                    holdout.mapping(
                        snapshot["producerGeometryCallSite"],
                        "producer geometry call site",
                    )
                )
    if len(call_sites) != 1:
        raise ValueError("producer geometry call site is not unique")
    return call_sites[0]


def analyze(
    timeline_path: Path,
    result_path: Path,
    *,
    run_id: int,
    evidence_status: str = "prospective-validator-pass",
) -> dict[str, Any]:
    if run_id <= 0:
        raise ValueError("run ID must be positive")
    if evidence_status not in EVIDENCE_STATUSES:
        raise ValueError("evidence status differs")
    timeline_sha = holdout.sha256_file(timeline_path)
    validator_result = holdout.mapping(
        json.loads(result_path.read_text(encoding="utf-8")), "validator result"
    )
    validator_aggregate = holdout.mapping(
        validator_result.get("aggregate"), "validator aggregate"
    )
    validator_call_site = holdout.mapping(
        validator_aggregate.get("producerGeometryCallSite"),
        "validator producer call-site summary",
    )
    if (
        validator_result.get("timelineSHA256") != timeline_sha
        or validator_call_site.get("schemaVersion") != 5
    ):
        raise ValueError("validator result does not accept schema-5 code evidence")

    timeline = holdout.mapping(
        json.loads(timeline_path.read_text(encoding="utf-8")), "transition timeline"
    )
    call_site = producer_call_site(timeline)
    validated_call_site = surviving.validate_producer_geometry_call_site(call_site)
    if validated_call_site != validator_call_site:
        raise ValueError("timeline and validator call-site summaries differ")
    code_frames = [
        frame
        for value in fixed.sequence(call_site.get("frames"), "call-site frames")
        if "captureBackdropCode" in (frame := holdout.mapping(value, "call-site frame"))
    ]
    if len(code_frames) != 1:
        raise ValueError("capture_backdrop code frame is not unique")
    capture = holdout.mapping(
        code_frames[0].get("captureBackdropCode"), "capture_backdrop code"
    )
    payload = surviving.hexadecimal_bytes(capture, "capture_backdrop symbol-prefix")
    calls = [
        holdout.mapping(value, "capture_backdrop direct call")
        for value in fixed.sequence(
            capture.get("directCalls"), "capture_backdrop direct calls"
        )
    ]
    control_flow = decision_control_flow(payload)
    kind_counts = Counter(str(record["kind"]) for record in control_flow)
    groups = direct_call_groups(calls)
    return {
        "dynamicAllocationCaptureBackdropCodeAnalysisSchemaVersion": 1,
        "classification": CLASSIFICATION,
        "evidenceStatus": evidence_status,
        "runID": run_id,
        "inputTimelineArtifact": timeline_path.parent.name + "/" + timeline_path.name,
        "inputTimelineSHA256": timeline_sha,
        "inputValidatorResultArtifact": (
            result_path.parent.name + "/" + result_path.name
        ),
        "inputValidatorResultSHA256": holdout.sha256_file(result_path),
        "captureBackdrop": {
            "symbol": capture.get("symbol"),
            "symbolImageOffset": capture.get("imageOffset"),
            "symbolPrefixByteCount": len(payload),
            "symbolPrefixSHA256": capture.get("sha256"),
            "decisionRegion": list(surviving.CAPTURE_BACKDROP_DECISION_CALL_RANGE),
            "controlFlowInstructionCount": len(control_flow),
            "controlFlowKindCounts": {
                name: kind_counts[name] for name in sorted(kind_counts)
            },
            "controlFlow": control_flow,
            "directCallCount": len(calls),
            "uniqueDirectCallTargetCount": len(groups),
            "directCallGroups": groups,
            "producerVertexBindingCallOffset": (
                surviving.CAPTURE_BACKDROP_VERTEX_BINDING_CALL_OFFSET
            ),
        },
        "conclusion": {
            "symbolAndEveryDecisionCallTargetByteValidated": True,
            "controlFlowOpenedWithoutFitting": True,
            "prospectiveGatePassed": (
                evidence_status == "prospective-validator-pass"
            ),
            "producerMeshPolicyRecovered": False,
            "requiresArithmeticAndBranchRecovery": True,
            "requiresUnseenGeometryTransfer": True,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("result", type=Path)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument(
        "--evidence-status",
        choices=sorted(EVIDENCE_STATUSES),
        default="prospective-validator-pass",
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = analyze(
        arguments.timeline,
        arguments.result,
        run_id=arguments.run_id,
        evidence_status=arguments.evidence_status,
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
