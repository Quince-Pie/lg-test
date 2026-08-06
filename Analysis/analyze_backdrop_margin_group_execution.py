#!/usr/bin/env python3
"""Authenticate and preserve the opened ``Group.margin`` execution diagnostic."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import struct
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_backdrop_margin_group_execution as group
import validate_backdrop_margin_writer_execution as writer


ANALYSIS_SCHEMA_VERSION = 1
RUN_ID = 31118243811
HEAD_SHA = "f4054b43b1a1b6c16f78c4e78e6350e7678a8763"
JOB_ID = 92673064584
ARTIFACT_ID = 8974080154
ARTIFACT_NAME = "liquid-glass-backdrop-margin-group-execution-31118243811"
ARTIFACT_SIZE_BYTES = 87_254_614
ARTIFACT_DIGEST = (
    "sha256:6c3ad6261166570c5016c07abd916d22360359dd10c624cb750f74940bdd82e6"
)

PROFILE = ("regular", "light", "materialize", "circle-127-center")
INDIRECT_TARGET_MODULE_OFFSET = 0x76BC54
INDIRECT_TARGET_ADDRESS = 9_366_203_476
INDIRECT_MODIFIER_RAW = 13_534_161_353_748_195_992

FILES = {
    "trace": (
        "backdrop-margin-writer-trace.json",
        "3f1494ad1d1e3fe547252b82ed9744667fa621a34b57b5810613d433db7e792c",
    ),
    "timeline": (
        "transition-timeline.json",
        "0a7db5d9416c4c69f19b608de73e9225e7edf8629e112de2be0d07cab1adc711",
    ),
    "validation": (
        "group-margin-validation.json",
        "8b974c97d28c92ec3a0adf9919ff1e2c7108e2199fbd658e917f668d6766cef2",
    ),
    "contractsLog": (
        "contracts.log",
        "9b191cf091d32f755403352d612e8421b07d2a9d7b67c95d8b028c755103ce16",
    ),
    "lldbLog": (
        "lldb-group-execution.log",
        "5fecafd93bd43fdb26601de3c932d2cd596c8a610194ae5ac4192850f8b98f89",
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is unreadable: {error}") from error


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} is not an object")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{label} is not an array")
    return value


def normalized_validation(value: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    inputs = dict(mapping(result.get("inputs"), "validation inputs"))
    inputs.pop("trace", None)
    inputs.pop("preregistration", None)
    result["inputs"] = inputs
    return result


def exact_candidate_corroboration(
    trace: Mapping[str, Any], timeline: Mapping[str, Any]
) -> dict[str, Any]:
    material, appearance, direction, geometry = PROFILE
    candidate = writer.transition_candidate(
        dict(timeline), material, appearance, direction, geometry
    )
    records = sequence(candidate.get("records"), "candidate records")
    candidate_words = [
        mapping(value, f"candidate record {index}").get(
            "requiredMarginF64RawLittleEndianHex"
        )
        for index, value in enumerate(records)
    ]
    if len(candidate_words) != 32 or any(
        not isinstance(value, str) or len(value) != 16 for value in candidate_words
    ):
        raise ValueError("candidate binary64 words differ")

    extension = mapping(trace.get("groupMarginExecution"), "group extension")
    invocations = sequence(extension.get("invocations"), "group invocations")
    return_words = [
        mapping(value, f"invocation {index}").get(
            "returnF64RawLittleEndianHex"
        )
        for index, value in enumerate(invocations)
    ]
    return_set = set(return_words)
    missing = sorted(set(candidate_words) - return_set)
    if missing:
        raise ValueError(f"candidate words absent from live returns: {missing}")

    matches = []
    for raw in sorted(set(candidate_words)):
        payload = bytes.fromhex(raw)
        value = struct.unpack("<d", payload)[0]
        matches.append(
            {
                "requiredMarginF64": value,
                "rawLittleEndianHex": raw,
                "timelineRecordIndices": [
                    index + 1
                    for index, candidate_raw in enumerate(candidate_words)
                    if candidate_raw == raw
                ],
                "liveInvocationIndices": [
                    index
                    for index, return_raw in enumerate(return_words)
                    if return_raw == raw
                ],
            }
        )
    return {
        "frozenCandidate": (
            "max(inputBleedAmount, inputShadowAmount + "
            "max(abs(inputShadowOffset.x), abs(inputShadowOffset.y)))"
        ),
        "timelineRecordCount": len(candidate_words),
        "timelineDistinctWordCount": len(set(candidate_words)),
        "liveInvocationCount": len(return_words),
        "liveDistinctReturnWordCount": len(return_set),
        "timelineRecordsWhoseWordOccursInLiveReturns": sum(
            value in return_set for value in candidate_words
        ),
        "timelineDistinctWordsOccurringInLiveReturns": len(
            set(candidate_words) & return_set
        ),
        "matches": matches,
        "binary64Tolerance": "zero bits",
        "perFrameTemporalJoinCaptured": False,
        "sameOpenedProfileDiagnostic": True,
        "prospectiveTransferAuthority": False,
        "interpretation": (
            "exact semantic corroboration only: all 32 record values (8 distinct "
            "binary64 words) occur among the 76 live returns, but the LLDB and "
            "timeline streams have no authenticated per-frame temporal join"
        ),
    }


def validate_case22_path(trace: Mapping[str, Any]) -> dict[str, Any]:
    extension = mapping(trace.get("groupMarginExecution"), "group extension")
    invocations = sequence(extension.get("invocations"), "group invocations")
    producer_gate = mapping(extension.get("producerCodeGate"), "producer code gate")
    module = mapping(producer_gate.get("module"), "producer module")
    module_base = module.get("loadAddress")
    if not isinstance(module_base, int):
        raise ValueError("producer module base differs")

    targets: list[int] = []
    modifiers: list[int] = []
    projection_object_links = 0
    side_tags: Counter[int] = Counter()
    case_counts: Counter[int] = Counter()
    for index, value in enumerate(invocations):
        invocation = mapping(value, f"invocation {index}")
        stages = sequence(invocation.get("stages"), f"invocation {index} stages")
        if [mapping(stage, "stage").get("instructionOffset") for stage in stages] != [
            0x0BC,
            0x20C,
            0x268,
            0x26C,
            0x278,
            0x2B0,
        ]:
            raise ValueError(f"invocation {index} is not the exact case-22 path")
        discriminator = mapping(stages[0], "discriminator")
        case = discriminator.get("discriminatorCase")
        if not isinstance(case, int):
            raise ValueError("discriminator case differs")
        case_counts[case] += 1

        projected = mapping(stages[1], "case-22 projection")
        snapshot = mapping(projected.get("projectionSnapshot"), "projection snapshot")
        payload = bytes.fromhex(str(snapshot.get("hex")))
        if len(payload) != 128:
            raise ValueError("case-22 projection byte count differs")
        indirect = mapping(stages[2], "case-22 indirect call")
        registers = mapping(indirect.get("registers"), "indirect registers")
        projected_object = struct.unpack_from("<Q", payload)[0]
        if projected_object != registers.get("x20") or registers.get("x0") != registers.get(
            "x20"
        ):
            raise ValueError("case-22 projected object link differs")
        projection_object_links += 1
        targets.append(indirect.get("authenticatedIndirectTargetRaw"))
        modifiers.append(indirect.get("authenticatedIndirectModifierRaw"))

        group_value = mapping(invocation.get("group"), "group value")
        payloads = sequence(group_value.get("taggedSidePayloads"), "tagged payloads")
        for side_value in payloads:
            tag = mapping(side_value, "tagged payload").get("tag")
            if not isinstance(tag, int):
                raise ValueError("tagged side word differs")
            side_tags[tag] += 1

    if (
        len(invocations) != 76
        or case_counts != Counter({22: 76})
        or set(targets) != {INDIRECT_TARGET_ADDRESS}
        or set(modifiers) != {INDIRECT_MODIFIER_RAW}
        or INDIRECT_TARGET_ADDRESS - module_base != INDIRECT_TARGET_MODULE_OFFSET
        or projection_object_links != len(invocations)
        or side_tags != Counter({10: 76})
    ):
        raise ValueError("case-22 execution identity differs")
    return {
        "invocationCount": len(invocations),
        "discriminatorCaseCounts": {str(key): value for key, value in case_counts.items()},
        "sideTagCounts": {str(key): value for key, value in side_tags.items()},
        "projectionFirstWordEqualsIndirectObjectPointerCount": projection_object_links,
        "authenticatedIndirectTargetAddress": INDIRECT_TARGET_ADDRESS,
        "authenticatedIndirectModifierRaw": INDIRECT_MODIFIER_RAW,
        "swiftUICoreModuleOffset": INDIRECT_TARGET_MODULE_OFFSET,
        "targetSymbolCaptured": False,
        "targetCodeCaptured": False,
        "targetInstructionExecutionCaptured": False,
        "unexercisedDiscriminatorCases": [1, 2, 3, 21],
    }


def analyze(artifact_directory: Path, preregistration_path: Path) -> dict[str, Any]:
    paths: dict[str, Path] = {}
    file_records = []
    for label, (filename, expected_sha256) in FILES.items():
        path = artifact_directory / filename
        actual_sha256 = sha256(path)
        if actual_sha256 != expected_sha256:
            raise ValueError(f"{label} SHA-256 differs")
        paths[label] = path
        file_records.append(
            {
                "label": label,
                "name": filename,
                "byteCount": path.stat().st_size,
                "sha256": actual_sha256,
            }
        )

    trace = mapping(load_json(paths["trace"], "trace"), "trace")
    timeline = mapping(load_json(paths["timeline"], "timeline"), "timeline")
    ci_validation = mapping(
        load_json(paths["validation"], "CI validation"), "CI validation"
    )
    local_validation = group.validate(paths["trace"], preregistration_path)
    if normalized_validation(ci_validation) != normalized_validation(local_validation):
        raise ValueError("independent local validation differs from CI")

    case22 = validate_case22_path(trace)
    corroboration = exact_candidate_corroboration(trace, timeline)
    direct_targets = sequence(
        mapping(trace.get("groupMarginExecution"), "group extension").get(
            "directTargets"
        ),
        "direct targets",
    )
    direct_target_records = [
        {
            "function": mapping(value, "direct target").get("function"),
            "symbolByteCount": mapping(value, "direct target").get(
                "symbolByteCount"
            ),
            "codeSHA256": mapping(value, "direct target").get("codeSHA256"),
            "completeCodeCaptured": mapping(value, "direct target").get(
                "completeCodeCaptured"
            ),
        }
        for value in direct_targets
    ]

    return {
        "backdropMarginGroupExecutionAnalysisSchemaVersion": ANALYSIS_SCHEMA_VERSION,
        "classification": (
            "immutable successful retrospective execution diagnostic for one "
            "already-opened regular/light profile; exact case-22 execution is "
            "captured, while its dynamic callee arithmetic and product parity remain open"
        ),
        "run": {
            "runID": RUN_ID,
            "headSHA": HEAD_SHA,
            "event": "push",
            "workflow": "Decode backdrop margin Group execution",
            "conclusion": "success",
            "jobID": JOB_ID,
            "job": "regular-light-materialize-circle-127-center",
        },
        "artifact": {
            "artifactID": ARTIFACT_ID,
            "name": ARTIFACT_NAME,
            "sizeBytes": ARTIFACT_SIZE_BYTES,
            "digest": ARTIFACT_DIGEST,
            "files": file_records,
        },
        "independentValidationEqualExceptCallerPaths": True,
        "validatedExecution": local_validation,
        "case22": case22,
        "directTargets": direct_target_records,
        "candidateCorroboration": corroboration,
        "openedFacts": {
            "groupCollectionTag": 64,
            "recordsPerInvocation": 1,
            "sideEntriesPerInvocation": 1,
            "onlyDiscriminatorCaseObserved": 22,
            "case22TargetStableAcrossAllInvocations": True,
            "allGetterReturnsMatchAdjacentSetterBitwise": True,
        },
        "nextExactGate": (
            "capture the complete SwiftUICore symbol at module offset 0x76bc54, "
            "its case-22 object bytes, and one structurally selected active "
            "instruction trace without selecting on a margin value"
        ),
        "sealedConclusion": {
            "groupMarginCase22LiveExecutionCaptured": True,
            "frozenCandidateExactlyCorroboratedOnOpenedProfile": True,
            "case22TargetIdentityOpened": True,
            "case22TargetArithmeticDecoded": False,
            "discriminatorCases1To3And21LiveMapped": False,
            "publicInputMarginLawDecoded": False,
            "prospectiveUnseenProfileTransferPassed": False,
            "independentTemporalInputGenerationPassed": False,
            "physicalOutputTransferPassed": False,
            "independentWalleZeroByteFrameParityPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_directory", type=Path)
    parser.add_argument("preregistration", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = analyze(arguments.artifact_directory, arguments.preregistration)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
