#!/usr/bin/env python3
"""Replicate the public/provider word join across two retained captures.

The selector was discovered retrospectively, so this analysis cannot create
prospective construction authority.  It can answer a narrower question
exactly: does the same raw-word relationship survive an independently timed
capture with different diagnostic flags and different public input words?
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_backdrop_margin_case22_provider_complete_semantics as complete
import analyze_backdrop_margin_case22_provider_public_timeline_join as opened
import validate_backdrop_margin_case22_provider_object_matrix_minimal_retry2_local_macos_26_6_1 as allocation_validator
import validate_backdrop_margin_case22_provider_object_matrix_normal_local_macos_26_6_1 as normal_validator


ANALYSIS_SCHEMA_VERSION = 1
TRACE_NAME = "provider-object-matrix-trace.json"
TIMELINE_NAME = "transition-timeline.json"
OPENED_RESULT_SHA256 = (
    "00fab84d0c6163629da387ea4e0f50884ee40b9f04842646fe01a36936b50e3d"
)
ALLOCATION_TRACE_SHA256 = (
    "0e83312d2535ad6601b6bcae178e939e13a9ebae95d15efcc166ffde013e6d72"
)
ALLOCATION_TIMELINE_SHA256 = (
    "1dd73cfa4e696c43a0612c107e9a5edcb78c72b14ba80e67a53e4e99b06d931f"
)
NORMAL_TRACE_SHA256 = "32f82fab6a209831347bd2673a6c83fb304cdc72fb04045f37ed23c1ea0be614"
NORMAL_TIMELINE_SHA256 = (
    "e6fa2d9a2f9916f077f2af1b02d9e24a26a90bc60d72a84e0bb27fda5ef65345"
)
ALLOCATION_COMMIT = "b694a919a7dd2e6c3a06b24fd1705a1bcb6646f3"
NORMAL_COMMIT = "d28806a1ad328e6a56f2c7fd33e3d3a6b91d8d26"
ALLOCATION_SAMPLE_CALLS = {
    1: 50,
    4: 163,
    8: 330,
    12: 482,
    16: 642,
    20: 790,
    24: 948,
    28: 1102,
}
NORMAL_SAMPLE_CALLS = {
    1: 70,
    4: 177,
    8: 331,
    12: 497,
    16: 657,
    20: 817,
    24: 964,
    28: 1091,
}
NORMAL_SAMPLE_INDICES = (1, 4, 8, 12, 16, 20, 24, 28, 32)
VARYING_LOADED_OFFSETS = (0x018, 0x098, 0x0E8, 0x160)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_mapping(path: Path, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is unreadable: {error}") from error
    return allocation_validator.mapping(value, label)


def calls_from_trace(
    trace: Mapping[str, Any], label: str
) -> tuple[list[Mapping[str, Any]], list[bytes]]:
    calls = [
        allocation_validator.mapping(value, f"{label} call {index}")
        for index, value in enumerate(
            allocation_validator.sequence(trace.get("calls"), f"{label} calls")
        )
    ]
    objects = [
        opened.object_raw(call, f"{label} call {index}")
        for index, call in enumerate(calls)
    ]
    return calls, objects


def records_from_timeline(
    timeline: Mapping[str, Any], label: str
) -> list[Mapping[str, Any]]:
    dynamic = allocation_validator.mapping(
        timeline.get("dynamicBackgroundUniforms"), f"{label} dynamic evidence"
    )
    return [
        allocation_validator.mapping(value, f"{label} record {index}")
        for index, value in enumerate(
            allocation_validator.sequence(
                dynamic.get("records"), f"{label} public records"
            )
        )
    ]


def match_records(
    records: Sequence[Mapping[str, Any]],
    objects: Sequence[bytes],
    expected_unique_calls: Mapping[int, int],
    expected_endpoint_calls: Sequence[int],
    label: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    joined = []
    endpoint = None
    for record in records:
        sample_index = int(record.get("sampleIndex"))
        inputs = opened.input_values(record, f"{label} sample {sample_index}")
        words = opened.signature_words(inputs)
        counts = [opened.signature_match_count(raw, words) for raw in objects]
        histogram = Counter(counts)
        full_matches = [index for index, count in enumerate(counts) if count == 4]
        partial_count = sum(
            count
            for matching_word_count, count in histogram.items()
            if 0 < matching_word_count < 4
        )
        require(
            partial_count == 0, f"{label} sample {sample_index} has a partial collision"
        )
        common = {
            "sampleIndex": sample_index,
            "fullMatchCallIndices": full_matches,
            "partialMatchCallCount": partial_count,
            "providerCallMatchHistogram": opened.histogram_record(histogram),
            "signatureWordsRawLittleEndianHex": [word.hex() for word in words],
        }
        if sample_index == 32:
            require(
                full_matches == list(expected_endpoint_calls),
                f"{label} endpoint ambiguity differs",
            )
            require(
                histogram == Counter({0: len(objects) - 3, 4: 3}),
                f"{label} endpoint histogram differs",
            )
            endpoint = {
                **common,
                "classification": "ambiguous-initial-and-two-terminal-endpoint-calls",
            }
            continue
        require(
            full_matches == [expected_unique_calls[sample_index]],
            f"{label} sample {sample_index} unique call differs",
        )
        require(
            histogram == Counter({0: len(objects) - 1, 4: 1}),
            f"{label} sample {sample_index} histogram differs",
        )
        joined.append(
            {
                **common,
                "classification": "unique-retrospective-four-word-join",
                "matchedProviderCallIndex": full_matches[0],
                "providerObjectSHA256": hashlib.sha256(
                    objects[full_matches[0]]
                ).hexdigest(),
            }
        )
    require(endpoint is not None, f"{label} endpoint record is absent")
    require(
        [record["matchedProviderCallIndex"] for record in joined]
        == sorted(record["matchedProviderCallIndex"] for record in joined),
        f"{label} unique calls are not monotonic",
    )
    return joined, endpoint


def replay_normal_matches(
    trace: Mapping[str, Any],
    calls: Sequence[Mapping[str, Any]],
    objects: Sequence[bytes],
    joined: Sequence[Mapping[str, Any]],
    llvm_mc: str,
) -> dict[str, Any]:
    provider_code = complete.provider_code(trace)
    instructions = complete.disassemble(provider_code, llvm_mc)
    paths = set()
    loaded_ranges = set()
    for record in joined:
        call_index = int(record["matchedProviderCallIndex"])
        replay = complete.replay(instructions, objects[call_index])
        expected_return = str(calls[call_index].get("returnF64RawLittleEndianHex", ""))
        require(
            replay["returnRawLittleEndianHex"] == expected_return,
            f"normal sample {record['sampleIndex']} provider replay differs",
        )
        require(
            expected_return == "0000000000000000",
            f"normal sample {record['sampleIndex']} return is not exact zero",
        )
        paths.add(tuple(replay["executedInstructionOffsets"]))
        loaded_ranges.add(tuple(tuple(value) for value in replay["loadedObjectRanges"]))
    require(len(paths) == 1, "normal joined provider paths differ")
    require(
        loaded_ranges == {opened.EXPECTED_LOADED_RANGES},
        "normal joined loaded ranges differ",
    )
    return {
        "providerCodeSHA256": hashlib.sha256(provider_code).hexdigest(),
        "matchingReplayReturnCount": len(joined),
        "distinctExecutedPathCount": len(paths),
        "loadedObjectRanges": [
            {"providerObjectOffset": offset, "byteCount": width}
            for offset, width in opened.EXPECTED_LOADED_RANGES
        ],
    }


def cross_capture_pairs(
    allocation_records: Sequence[Mapping[str, Any]],
    allocation_objects: Sequence[bytes],
    normal_records: Sequence[Mapping[str, Any]],
    normal_objects: Sequence[bytes],
) -> list[dict[str, Any]]:
    allocation_by_sample = {
        int(record["sampleIndex"]): record for record in allocation_records
    }
    normal_by_sample = {int(record["sampleIndex"]): record for record in normal_records}
    loaded_fields = opened.expanded_loaded_fields(opened.EXPECTED_LOADED_RANGES)
    constant_fields = [
        value for value in loaded_fields if value[0] not in VARYING_LOADED_OFFSETS
    ]
    varying_fields = [
        value for value in loaded_fields if value[0] in VARYING_LOADED_OFFSETS
    ]
    require(len(constant_fields) == 14, "constant loaded-field count differs")
    require(len(varying_fields) == 4, "varying loaded-field count differs")

    pairs = []
    for sample_index in ALLOCATION_SAMPLE_CALLS:
        allocation_inputs = opened.input_values(
            allocation_by_sample[sample_index],
            f"allocation sample {sample_index}",
        )
        normal_inputs = opened.input_values(
            normal_by_sample[sample_index], f"normal sample {sample_index}"
        )
        allocation_words = opened.signature_words(allocation_inputs)
        normal_words = opened.signature_words(normal_inputs)
        changed_signature_words = sum(
            left != right for left, right in zip(allocation_words, normal_words)
        )
        allocation_raw = allocation_objects[ALLOCATION_SAMPLE_CALLS[sample_index]]
        normal_raw = normal_objects[NORMAL_SAMPLE_CALLS[sample_index]]
        equal_constant_fields = sum(
            allocation_raw[offset : offset + width]
            == normal_raw[offset : offset + width]
            for offset, _storage, width in constant_fields
        )
        changed_varying_fields = sum(
            allocation_raw[offset : offset + width]
            != normal_raw[offset : offset + width]
            for offset, _storage, width in varying_fields
        )
        require(
            changed_signature_words == 4,
            f"sample {sample_index} did not change every signature word",
        )
        require(
            equal_constant_fields == 14,
            f"sample {sample_index} constant fields differ across captures",
        )
        require(
            changed_varying_fields == 4,
            f"sample {sample_index} varying fields did not all change",
        )
        pairs.append(
            {
                "sampleIndex": sample_index,
                "allocationProviderCallIndex": ALLOCATION_SAMPLE_CALLS[sample_index],
                "normalProviderCallIndex": NORMAL_SAMPLE_CALLS[sample_index],
                "changedSignatureWordCount": changed_signature_words,
                "equalConstantLoadedFieldCount": equal_constant_fields,
                "changedVaryingLoadedFieldCount": changed_varying_fields,
                "allocationProviderObjectSHA256": hashlib.sha256(
                    allocation_raw
                ).hexdigest(),
                "normalProviderObjectSHA256": hashlib.sha256(normal_raw).hexdigest(),
            }
        )
    return pairs


def analyze(
    allocation_preregistration: Path,
    allocation_artifact_directory: Path,
    normal_preregistration: Path,
    normal_artifact_directory: Path,
    opened_result_path: Path,
    llvm_mc: str,
) -> dict[str, Any]:
    allocation_validation = allocation_validator.validate(
        allocation_preregistration, allocation_artifact_directory
    )
    require(
        allocation_validation["captureContractPassed"] is True,
        "allocation capture contract failed",
    )
    normal_validation = normal_validator.validate(
        normal_preregistration, normal_artifact_directory
    )
    require(
        normal_validation["transportAndObjectCapturePassed"] is True,
        "normal object transport failed",
    )
    require(
        normal_validation["captureContractPassed"] is False
        and normal_validation["failedRequirements"]
        == [
            "requireAtLeastTwoDistinctProviderReturnWords",
            "requireAtLeastOneFinitePositiveProviderReturn",
        ],
        "normal original prospective failure differs",
    )
    require(
        sha256(opened_result_path) == OPENED_RESULT_SHA256,
        "opened allocation join result identity differs",
    )
    opened_result = load_mapping(opened_result_path, "opened allocation join result")
    require(
        opened_result["selector"]["matchedProviderCallIndices"][:1] == [50],
        "opened allocation join result differs",
    )

    allocation_trace_path = allocation_artifact_directory / TRACE_NAME
    allocation_timeline_path = allocation_artifact_directory / TIMELINE_NAME
    normal_trace_path = normal_artifact_directory / TRACE_NAME
    normal_timeline_path = normal_artifact_directory / TIMELINE_NAME
    require(
        sha256(allocation_trace_path) == ALLOCATION_TRACE_SHA256,
        "allocation trace identity differs",
    )
    require(
        sha256(allocation_timeline_path) == ALLOCATION_TIMELINE_SHA256,
        "allocation timeline identity differs",
    )
    require(
        sha256(normal_trace_path) == NORMAL_TRACE_SHA256,
        "normal trace identity differs",
    )
    require(
        sha256(normal_timeline_path) == NORMAL_TIMELINE_SHA256,
        "normal timeline identity differs",
    )

    allocation_trace = load_mapping(allocation_trace_path, "allocation trace")
    allocation_timeline = load_mapping(allocation_timeline_path, "allocation timeline")
    normal_trace = load_mapping(normal_trace_path, "normal trace")
    normal_timeline = load_mapping(normal_timeline_path, "normal timeline")
    allocation_calls, allocation_objects = calls_from_trace(
        allocation_trace, "allocation"
    )
    normal_calls, normal_objects = calls_from_trace(normal_trace, "normal")
    allocation_records = records_from_timeline(allocation_timeline, "allocation")
    normal_records = records_from_timeline(normal_timeline, "normal")
    require(len(allocation_calls) == 1228, "allocation provider call count differs")
    require(len(normal_calls) == 1232, "normal provider call count differs")
    require(len(allocation_records) == 32, "allocation public record count differs")
    require(
        tuple(int(record["sampleIndex"]) for record in normal_records)
        == NORMAL_SAMPLE_INDICES,
        "normal public sample indices differ",
    )

    allocation_joined, allocation_endpoint = match_records(
        allocation_records,
        allocation_objects,
        {
            int(record["sampleIndex"]): int(record["matchedProviderCallIndex"])
            for record in opened_result["selector"]["joinedSamples"]
        },
        (0, 1226, 1227),
        "allocation",
    )
    normal_joined, normal_endpoint = match_records(
        normal_records,
        normal_objects,
        NORMAL_SAMPLE_CALLS,
        (0, 1230, 1231),
        "normal",
    )
    require(len(allocation_joined) == 31, "allocation unique join count differs")
    require(len(normal_joined) == 8, "normal unique join count differs")
    normal_replay = replay_normal_matches(
        normal_trace, normal_calls, normal_objects, normal_joined, llvm_mc
    )

    normal_joined_objects = [
        normal_objects[int(record["matchedProviderCallIndex"])]
        for record in normal_joined
    ]
    normal_joined_inputs = [
        opened.input_values(record, f"normal sample {record['sampleIndex']}")
        for record in normal_records
        if int(record["sampleIndex"]) != 32
    ]
    normal_loaded_field_observations = [
        opened.relation_record(
            offset,
            storage,
            width,
            normal_joined_objects,
            normal_joined_inputs,
        )
        for offset, storage, width in opened.expanded_loaded_fields(
            opened.EXPECTED_LOADED_RANGES
        )
    ]
    pairs = cross_capture_pairs(
        allocation_records,
        allocation_objects,
        normal_records,
        normal_objects,
    )
    require(
        sum(record["changedSignatureWordCount"] for record in pairs) == 32,
        "cross-capture changed signature count differs",
    )
    require(
        sum(record["equalConstantLoadedFieldCount"] for record in pairs) == 112,
        "cross-capture constant comparison count differs",
    )
    require(
        sum(record["changedVaryingLoadedFieldCount"] for record in pairs) == 32,
        "cross-capture varying comparison count differs",
    )

    return {
        "backdropMarginCase22ProviderPublicTimelineCrossCaptureReplicationAnalysisSchemaVersion": ANALYSIS_SCHEMA_VERSION,
        "classification": (
            "exact retrospective replication of the four-word public/provider "
            "join across independently timed allocation and normal diagnostic captures"
        ),
        "inputs": {
            "analysisSource": {
                "path": f"Analysis/{Path(__file__).name}",
                "sha256": sha256(Path(__file__).resolve()),
            },
            "openedAllocationJoinResult": {
                "path": f"Analysis/{opened_result_path.name}",
                "sha256": OPENED_RESULT_SHA256,
            },
            "allocationCapture": {
                "sourceCommit": ALLOCATION_COMMIT,
                "preregistrationSHA256": sha256(allocation_preregistration),
                "providerTraceSHA256": ALLOCATION_TRACE_SHA256,
                "publicTimelineSHA256": ALLOCATION_TIMELINE_SHA256,
                "originalProspectiveContractPassed": True,
                "evidenceMode": "allocation-metadata-v1",
            },
            "normalCapture": {
                "sourceCommit": NORMAL_COMMIT,
                "preregistrationSHA256": sha256(normal_preregistration),
                "providerTraceSHA256": NORMAL_TRACE_SHA256,
                "publicTimelineSHA256": NORMAL_TIMELINE_SHA256,
                "transportAndObjectCapturePassed": True,
                "originalProspectiveContractPassed": False,
                "originalFailedRequirementsPreserved": normal_validation[
                    "failedRequirements"
                ],
                "evidenceMode": "controlled-replay-v1",
            },
        },
        "replication": {
            "independentCaptureCount": 2,
            "allocationProviderCallCount": len(allocation_calls),
            "normalProviderCallCount": len(normal_calls),
            "allocationUniqueNonEndpointJoinCount": len(allocation_joined),
            "normalUniqueNonEndpointJoinCount": len(normal_joined),
            "normalMatchedProviderCallIndices": [
                record["matchedProviderCallIndex"] for record in normal_joined
            ],
            "allUniqueJoinsHaveZeroPartialCollisions": True,
            "allUniqueJoinsStrictlyIncreasingWithinCapture": True,
            "endpointPatternReplicatedAsInitialPlusTwoTerminalCalls": True,
            "allocationEndpoint": allocation_endpoint,
            "normalEndpoint": normal_endpoint,
            "overlappingNonEndpointSampleCount": len(pairs),
            "changedSignatureWordComparisonCount": 32,
            "equalConstantLoadedFieldComparisonCount": 112,
            "changedVaryingLoadedFieldComparisonCount": 32,
            "crossCapturePairs": pairs,
        },
        "normalProviderExecution": {
            **normal_replay,
            "loadedFieldCount": len(normal_loaded_field_observations),
            "loadedFieldObservations": normal_loaded_field_observations,
            "allEightReturnsReplayedBitwise": True,
            "allEightReturnsExactZero": True,
        },
        "authority": {
            "retrospectiveCrossCaptureReplicationEstablished": True,
            "sameFourWordRelationsReplicatedAcrossDifferentCapturedInputWords": True,
            "allFourWordsChangedAtEveryOverlappingNonEndpointSample": True,
            "constantLoadedFieldsStableAcrossCaptureModes": True,
            "normalOriginalProspectiveFailureRelabelledAsPass": False,
            "authenticatedPerCallbackTemporalJoinEstablished": False,
            "prospectivePublicInputToProviderConstructionTransferEstablished": False,
            "freshMaterialAppearanceGeometryProfileTransferEstablished": False,
            "generalPublicInputObjectConstructionLawEstablished": False,
            "upstreamCropAllocationPolicyEstablished": False,
            "physicalRetinaColorPixelCompositorTransferEstablished": False,
            "independentWalleZeroByteFrameParityEstablished": False,
            "liquidGlassParityEstablished": False,
            "productionShaderAuthorized": False,
        },
        "nextExactGate": (
            "execute the already frozen value-blind public-render interval transfer; "
            "on pass, freeze fresh profile and independent-input interventions at the "
            "same authenticated boundary"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allocation-preregistration", required=True, type=Path)
    parser.add_argument("--allocation-artifact-directory", required=True, type=Path)
    parser.add_argument("--normal-preregistration", required=True, type=Path)
    parser.add_argument("--normal-artifact-directory", required=True, type=Path)
    parser.add_argument("--opened-result", required=True, type=Path)
    parser.add_argument("--llvm-mc", default="llvm-mc")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        result = analyze(
            arguments.allocation_preregistration,
            arguments.allocation_artifact_directory,
            arguments.normal_preregistration,
            arguments.normal_artifact_directory,
            arguments.opened_result,
            arguments.llvm_mc,
        )
    except (OSError, ValueError, KeyError, OverflowError, struct.error) as error:
        parser.error(str(error))
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
