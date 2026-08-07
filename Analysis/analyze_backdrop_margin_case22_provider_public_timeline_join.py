#!/usr/bin/env python3
"""Join retained public filter samples to exact case-22 provider objects.

The four selector words were opened by the earlier endpoint analysis.  This
analysis applies them unchanged to every retained public sample and every
retained provider call.  It is deliberately retrospective: a unique value
signature inside one capture is strong covariance evidence, but it is not a
prospective intervention on SwiftUI's object constructor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_backdrop_margin_case22_provider_complete_semantics as complete
import validate_backdrop_margin_case22_provider_object_matrix_minimal_retry2_local_macos_26_6_1 as matrix_validator


ANALYSIS_SCHEMA_VERSION = 1
TRACE_NAME = "provider-object-matrix-trace.json"
TIMELINE_NAME = "transition-timeline.json"
TRACE_SHA256 = "0e83312d2535ad6601b6bcae178e939e13a9ebae95d15efcc166ffde013e6d72"
TIMELINE_SHA256 = "1dd73cfa4e696c43a0612c107e9a5edcb78c72b14ba80e67a53e4e99b06d931f"
ARTIFACT_LABEL = (
    "artifacts/local-case22-provider-object-matrix-minimal-retry2-"
    "b694a91-run1"
)
PREREGISTRATION_LABEL = (
    "Analysis/backdrop_margin_case22_provider_object_matrix_minimal_"
    "retry2_local_macos_26_6_1_preregistration.json"
)

# These are the four exact endpoint equalities recorded by the already sealed
# matrix validator.  Their reuse here is a retrospective selector, not new
# prospective mapping authority.
SIGNATURE = (
    (0x018, "inputShadowAmount", 1.0),
    (0x098, "inputBlurRadius", 2.0),
    (0x0E8, "inputInnerRefractionAmount", 1.0),
    (0x160, "inputBleedAmount", 1.0),
)

EXPECTED_LOADED_RANGES = (
    (0x008, 16),
    (0x018, 8),
    (0x028, 8),
    (0x038, 8),
    (0x088, 4),
    (0x090, 8),
    (0x098, 16),
    (0x0A8, 16),
    (0x0B8, 16),
    (0x0E8, 8),
    (0x0F8, 8),
    (0x110, 4),
    (0x160, 8),
    (0x178, 4),
)
ZERO_F64_OFFSETS = (
    0x028,
    0x038,
    0x090,
    0x0A0,
    0x0A8,
    0x0B0,
    0x0B8,
    0x0C0,
    0x0F8,
)
ZERO_F32_OFFSETS = (0x088, 0x110, 0x178)


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
    return matrix_validator.mapping(value, label)


def input_values(record: Mapping[str, Any], label: str) -> Mapping[str, Any]:
    filter_record = matrix_validator.mapping(record.get("filter"), f"{label} filter")
    return matrix_validator.mapping(
        filter_record.get("inputValues"), f"{label} filter inputs"
    )


def binary64_word(value: Any, scale: float, label: str) -> bytes:
    require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"{label} is not numeric",
    )
    result = float(value) * scale
    require(math.isfinite(result), f"{label} is not finite")
    return struct.pack("<d", result)


def object_raw(call: Mapping[str, Any], label: str) -> bytes:
    snapshot = matrix_validator.mapping(
        call.get("providerEntryObject"), f"{label} provider object"
    )
    try:
        raw = bytes.fromhex(str(snapshot.get("hex", "")))
    except ValueError as error:
        raise ValueError(f"{label} provider object is not hexadecimal") from error
    require(
        len(raw) == matrix_validator.OBJECT_BYTE_COUNT,
        f"{label} provider object width differs",
    )
    require(
        snapshot.get("sha256") == hashlib.sha256(raw).hexdigest(),
        f"{label} provider object digest differs",
    )
    return raw


def signature_words(inputs: Mapping[str, Any]) -> tuple[bytes, ...]:
    return tuple(
        binary64_word(inputs.get(key), scale, key)
        for _offset, key, scale in SIGNATURE
    )


def signature_match_count(raw: bytes, words: Sequence[bytes]) -> int:
    require(len(words) == len(SIGNATURE), "signature word count differs")
    return sum(
        raw[offset : offset + 8] == word
        for (offset, _key, _scale), word in zip(SIGNATURE, words)
    )


def histogram_record(histogram: Counter[int]) -> list[dict[str, int]]:
    return [
        {
            "matchingSignatureWordCount": count,
            "providerCallCount": histogram[count],
        }
        for count in sorted(histogram)
    ]


def expanded_loaded_fields(
    ranges: Sequence[tuple[int, int]],
) -> tuple[tuple[int, str, int], ...]:
    fields = []
    for offset, width in ranges:
        if width == 16:
            fields.extend(((offset, "binary64", 8), (offset + 8, "binary64", 8)))
        elif width == 8:
            fields.append((offset, "binary64", 8))
        elif width == 4:
            fields.append((offset, "binary32", 4))
        else:
            raise ValueError(f"unsupported provider load width {width}")
    unique = sorted(set(fields))
    require(len(unique) == len(fields), "provider loaded fields overlap")
    return tuple(unique)


def relation_record(
    offset: int,
    storage: str,
    width: int,
    joined_objects: Sequence[bytes],
    joined_inputs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    observed = [raw[offset : offset + width] for raw in joined_objects]
    distinct = sorted({word.hex() for word in observed})
    base = {
        "providerObjectOffset": offset,
        "providerObjectOffsetHex": f"0x{offset:03x}",
        "storage": storage,
        "byteCount": width,
        "joinedSampleCount": len(observed),
        "distinctRawWordCount": len(distinct),
        "distinctRawLittleEndianHex": distinct,
    }

    if offset in ZERO_F64_OFFSETS or offset in ZERO_F32_OFFSETS:
        zero = struct.pack("<d" if width == 8 else "<f", 0.0)
        require(all(word == zero for word in observed), f"field {offset:#x} is not zero")
        return {
            **base,
            "observation": {
                "classification": "constant-zero-in-opened-profile",
                "exactRawLittleEndianHex": zero.hex(),
                "semanticSourceDisambiguatedWithinProfile": False,
            },
        }

    if offset in (0x008, 0x010):
        lane = 0 if offset == 0x008 else 1
        public_words = []
        for index, inputs in enumerate(joined_inputs, 1):
            shadow_offset = matrix_validator.mapping(
                inputs.get("inputShadowOffset"),
                f"joined sample {index} inputShadowOffset",
            )
            try:
                raw_offset = bytes.fromhex(str(shadow_offset.get("hex", "")))
            except ValueError as error:
                raise ValueError("inputShadowOffset is not hexadecimal") from error
            require(len(raw_offset) == 16, "inputShadowOffset width differs")
            public_words.append(raw_offset[lane * 8 : lane * 8 + 8])
        require(observed == public_words, f"field {offset:#x} shadow-offset lane differs")
        return {
            **base,
            "observation": {
                "classification": "exact-observational-public-word-equality",
                "publicInput": "inputShadowOffset",
                "publicInputBinary64Lane": lane,
                "transform": "identity",
                "exactMatchCount": len(observed),
                "semanticSourceDisambiguatedWithinProfile": False,
            },
        }

    candidate_specs: tuple[tuple[str, float], ...]
    source_disambiguated = True
    if offset == 0x018:
        candidate_specs = (("inputShadowAmount", 1.0),)
    elif offset == 0x098:
        candidate_specs = (("inputBlurRadius", 2.0),)
    elif offset == 0x0E8:
        candidate_specs = (
            ("inputInnerRefractionAmount", 1.0),
            ("inputShadowAmount", -0.8),
        )
        source_disambiguated = False
    elif offset == 0x160:
        candidate_specs = (
            ("inputBleedAmount", 1.0),
            ("inputBleedHeight", 1.0),
        )
        source_disambiguated = False
    else:
        raise ValueError(f"loaded field {offset:#x} lacks a declared observation")

    candidates = []
    for key, scale in candidate_specs:
        expected = [
            binary64_word(inputs.get(key), scale, f"joined sample {index} {key}")
            for index, inputs in enumerate(joined_inputs, 1)
        ]
        require(observed == expected, f"field {offset:#x} relation to {key} differs")
        candidates.append(
            {
                "publicInput": key,
                "binary64Scale": scale,
                "exactMatchCount": len(observed),
            }
        )
    return {
        **base,
        "observation": {
            "classification": "exact-observational-public-word-equality",
            "candidateRelations": candidates,
            "semanticSourceDisambiguatedWithinProfile": source_disambiguated,
        },
    }


def analyze(
    preregistration_path: Path,
    artifact_directory: Path,
    llvm_mc: str,
) -> dict[str, Any]:
    capture_result = matrix_validator.validate(
        preregistration_path, artifact_directory
    )
    require(capture_result["captureContractPassed"] is True, "capture contract failed")

    trace_path = artifact_directory / TRACE_NAME
    timeline_path = artifact_directory / TIMELINE_NAME
    require(sha256(trace_path) == TRACE_SHA256, "provider trace identity differs")
    require(sha256(timeline_path) == TIMELINE_SHA256, "public timeline identity differs")
    trace = load_mapping(trace_path, "provider trace")
    timeline = load_mapping(timeline_path, "public timeline")
    calls = [
        matrix_validator.mapping(value, f"provider call {index}")
        for index, value in enumerate(
            matrix_validator.sequence(trace.get("calls"), "provider calls")
        )
    ]
    call_objects = [
        object_raw(call, f"provider call {index}")
        for index, call in enumerate(calls)
    ]
    dynamic = matrix_validator.mapping(
        timeline.get("dynamicBackgroundUniforms"), "dynamic background uniforms"
    )
    records = [
        matrix_validator.mapping(value, f"public record {index}")
        for index, value in enumerate(
            matrix_validator.sequence(dynamic.get("records"), "public records"), 1
        )
    ]
    require(len(calls) == 1228, "provider call count differs")
    require(len(records) == 32, "public record count differs")
    require(
        [record.get("sampleIndex") for record in records] == list(range(1, 33)),
        "public sample indices differ",
    )

    provider_code = complete.provider_code(trace)
    instructions = complete.disassemble(provider_code, llvm_mc)
    unique_records = []
    unique_call_indices = []
    joined_objects = []
    joined_inputs = []
    executed_paths = set()
    loaded_range_sets = set()
    matching_replay_count = 0

    for record in records:
        sample_index = int(record["sampleIndex"])
        inputs = input_values(record, f"public sample {sample_index}")
        words = signature_words(inputs)
        match_counts = [
            signature_match_count(raw, words) for raw in call_objects
        ]
        histogram = Counter(match_counts)
        full_matches = [
            index for index, count in enumerate(match_counts) if count == len(SIGNATURE)
        ]
        partial_matches = sum(
            count for words_matched, count in histogram.items() if 0 < words_matched < 4
        )
        signature_record = {
            "sampleIndex": sample_index,
            "signatureWords": [
                {
                    "providerObjectOffset": offset,
                    "publicInput": key,
                    "binary64Scale": scale,
                    "rawLittleEndianHex": word.hex(),
                }
                for (offset, key, scale), word in zip(SIGNATURE, words)
            ],
            "providerCallMatchHistogram": histogram_record(histogram),
            "fullMatchCallIndices": full_matches,
            "partialMatchCallCount": partial_matches,
        }

        if sample_index == 32:
            require(full_matches == [0, 1226, 1227], "endpoint ambiguity differs")
            require(histogram == Counter({0: 1225, 4: 3}), "endpoint collision histogram differs")
            endpoint_record = {
                **signature_record,
                "classification": "ambiguous-repeated-endpoint-excluded-from-unique-join",
            }
            continue

        require(len(full_matches) == 1, f"sample {sample_index} join is not unique")
        require(partial_matches == 0, f"sample {sample_index} has a partial collision")
        require(
            histogram == Counter({0: 1227, 4: 1}),
            f"sample {sample_index} collision histogram differs",
        )
        call_index = full_matches[0]
        call = calls[call_index]
        raw = call_objects[call_index]
        replay = complete.replay(instructions, raw)
        expected_return = str(call.get("returnF64RawLittleEndianHex", ""))
        observed_return = str(replay["returnRawLittleEndianHex"])
        require(observed_return == expected_return, f"sample {sample_index} replay differs")
        matching_replay_count += 1
        executed_paths.add(tuple(replay["executedInstructionOffsets"]))
        loaded_ranges = tuple(tuple(value) for value in replay["loadedObjectRanges"])
        loaded_range_sets.add(loaded_ranges)
        unique_call_indices.append(call_index)
        joined_objects.append(raw)
        joined_inputs.append(inputs)
        unique_records.append(
            {
                **signature_record,
                "classification": "unique-retrospective-cross-artifact-value-signature-join",
                "matchedProviderCallIndex": call_index,
                "matchedProviderThreadID": call.get("threadID"),
                "providerObjectSHA256": hashlib.sha256(raw).hexdigest(),
                "providerReturnRawLittleEndianHex": expected_return,
                "replayedReturnRawLittleEndianHex": observed_return,
            }
        )

    require(
        unique_call_indices == sorted(unique_call_indices),
        "unique joins are not strictly monotonic",
    )
    require(
        len(set(unique_call_indices)) == 31,
        "unique joins reuse a provider call",
    )
    require(len(loaded_range_sets) == 1, "joined provider load paths differ")
    loaded_ranges = next(iter(loaded_range_sets))
    require(loaded_ranges == EXPECTED_LOADED_RANGES, "joined loaded ranges differ")
    loaded_fields = expanded_loaded_fields(loaded_ranges)
    field_observations = [
        relation_record(offset, storage, width, joined_objects, joined_inputs)
        for offset, storage, width in loaded_fields
    ]
    varying_fields = [
        record for record in field_observations if record["distinctRawWordCount"] > 1
    ]
    require(
        [record["providerObjectOffset"] for record in varying_fields]
        == [0x018, 0x098, 0x0E8, 0x160],
        "varying joined loaded-field set differs",
    )

    return {
        "backdropMarginCase22ProviderPublicTimelineJoinAnalysisSchemaVersion": ANALYSIS_SCHEMA_VERSION,
        "classification": (
            "exact retrospective unique cross-artifact value-signature join "
            "between public glassBackground inputs and authenticated finite "
            "case-22 provider objects in one retained Retina capture"
        ),
        "inputs": {
            "analysisSource": {
                "path": f"Analysis/{Path(__file__).name}",
                "sha256": sha256(Path(__file__).resolve()),
            },
            "preregistration": {
                "path": PREREGISTRATION_LABEL,
                "sha256": sha256(preregistration_path),
            },
            "providerTrace": {
                "path": f"{ARTIFACT_LABEL}/{TRACE_NAME}",
                "sha256": TRACE_SHA256,
            },
            "publicTimeline": {
                "path": f"{ARTIFACT_LABEL}/{TIMELINE_NAME}",
                "sha256": TIMELINE_SHA256,
            },
            "captureContractPassed": True,
            "providerCodeSHA256": hashlib.sha256(provider_code).hexdigest(),
        },
        "selector": {
            "classification": (
                "four exact endpoint candidate equalities reused unchanged "
                "as a retrospective raw-binary64 selector"
            ),
            "providerCallCount": len(calls),
            "publicRecordCount": len(records),
            "uniqueNonEndpointJoinCount": len(unique_records),
            "allNonEndpointOtherCallsMatchedZeroSignatureWords": True,
            "allNonEndpointJoinsStrictlyIncreasing": True,
            "matchedProviderCallIndices": unique_call_indices,
            "joinedSamples": unique_records,
            "endpoint": endpoint_record,
        },
        "providerExecution": {
            "joinedSampleCount": len(joined_objects),
            "matchingInstructionReplayReturnCount": matching_replay_count,
            "distinctExecutedPathCount": len(executed_paths),
            "loadedObjectRanges": [
                {"providerObjectOffset": offset, "byteCount": width}
                for offset, width in loaded_ranges
            ],
            "loadedFieldCount": len(loaded_fields),
            "loadedFieldObservations": field_observations,
            "varyingLoadedFieldCount": len(varying_fields),
            "constantLoadedFieldCount": len(field_observations) - len(varying_fields),
            "allJoinedReturnsReplayedBitwise": (
                matching_replay_count == len(joined_objects)
            ),
        },
        "authority": {
            "retrospectiveUniqueCrossArtifactValueJoinEstablished": True,
            "strictMonotonicCallSequenceAlignmentObserved": True,
            "allProviderLoadedFieldsCharacterizedForJoinedOpenedPath": True,
            "varyingLoadedWordRelationsExactAcrossJoinedSamples": True,
            "authenticatedPerCallbackTemporalJoinEstablished": False,
            "prospectivePublicInputToProviderConstructionTransferEstablished": False,
            "generalPublicInputObjectConstructionLawEstablished": False,
            "upstreamCropAllocationPolicyEstablished": False,
            "physicalRetinaColorPixelCompositorTransferEstablished": False,
            "independentWalleZeroByteFrameParityEstablished": False,
            "liquidGlassParityEstablished": False,
            "productionShaderAuthorized": False,
        },
        "nextExactGate": (
            "freeze these four selector words and all 18 provider-loaded field "
            "predictions before a fresh public transition profile, then require "
            "a unique callback-time join and exact blind transfer; constant and "
            "co-varying aliases require independent public-input interventions"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--artifact-directory", required=True, type=Path)
    parser.add_argument("--llvm-mc", default="llvm-mc")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        result = analyze(
            arguments.preregistration,
            arguments.artifact_directory,
            arguments.llvm_mc,
        )
    except (OSError, ValueError, KeyError, struct.error) as error:
        parser.error(str(error))
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
