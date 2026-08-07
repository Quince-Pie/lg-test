#!/usr/bin/env python3
"""Validate the prospective Parameters-to-BackgroundFilter public join."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_backdrop_margin_case22_provider_object_matrix_minimal_retry2_local_macos_26_6_1 as allocation
import validate_backdrop_margin_case22_provider_public_render_interval_transfer_local_macos_26_6_1 as public


RESULT_SCHEMA_VERSION = 2
PREREGISTRATION_SCHEMA_VERSION = 2
TRACE_SCHEMA_VERSION = 2

EXPECTED_BINARY_SHA256 = (
    "b9cb4068e77a61ff87794fa20a5c273e007f3ee20dd74503b1ab78839104e8dd"
)
EXPECTED_PREFLIGHT_SHA256 = (
    "f12a1cbe29629dc843cc3250a46fa686225f3c08bcf1bf1dbdf50aea913926f1"
)
EXPECTED_PREDECESSOR_COMMIT = "d18aca7fe2638d25eb347df96fe9d5d3a3428060"
EXPECTED_PREDECESSOR_PREREGISTRATION_SHA256 = (
    "1f9e756a20e563b11018085e74520763d67f84df43209fdeb5e2f0a55a8aa9c4"
)
EXPECTED_PREDECESSOR_VALIDATOR_SHA256 = (
    "1f7ff6bd50b67404dcc86db4e73990b7247bdc52198c16923034764eef18781d"
)
DESIGN_LIBRARY_UUID = "1E980802-69F5-3E69-89EF-50088297FCF5"

CONSTRUCTOR_MODULE_OFFSET = 0xBAD00
CONSTRUCTOR_BYTE_COUNT = 0x414
CONSTRUCTOR_CODE_SHA256 = (
    "71a592bc8a187fe8bcca0fa50c3f4d36ea3c2916dbd5d16f3fa1df05b86f131d"
)
PRODUCER_MODULE_OFFSET = 0xB7FA8
PRODUCER_BYTE_COUNT = 0x66C
PRODUCER_CODE_SHA256 = (
    "0729f7b0f874c0fb9fb64fa3383a6f2ed328d1dc55fdce53b82038a188df6f97"
)
CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER = 0x38C
CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER = 0x390
CONSTRUCTOR_CALL_INSTRUCTION_HEX = "730a0094"
PARAMETERS_BYTE_COUNT = 0x401
BACKGROUND_FILTER_BYTE_COUNT = 0x1F8
MAXIMUM_CONSTRUCTOR_CALLS = 4096

RESOLVED_RECIPE_BUILDER_MODULE_OFFSET = 0x120B4C
RESOLVED_RECIPE_BUILDER_BYTE_COUNT = 0x1334
RESOLVED_RECIPE_BUILDER_CODE_SHA256 = (
    "07d9b8571ca8fed42e1d8e71b312f00a9c9713ce19f406d6f2c15a9d2403fde4"
)
RESOLVED_RECIPE_BUILDER_CALLER_MODULE_OFFSET = 0x11F1BC
RESOLVED_RECIPE_BUILDER_CALLER_BYTE_COUNT = 0xD7C
RESOLVED_RECIPE_BUILDER_CALLER_CODE_SHA256 = (
    "ba0ad1081cece802ccd1e148660a542145f95bf57a92de4407a3fad55f4679c6"
)
RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER = 0xD34
RESOLVED_RECIPE_BUILDER_RETURN_OFFSET_IN_CALLER = 0xD38
RESOLVED_RECIPE_BUILDER_CALL_INSTRUCTION_HEX = "17030094"
BLEND_DECISION_OFFSET_IN_BUILDER = 0xFB8
BLEND_FINAL_GATE_OFFSET_IN_BUILDER = 0x1174
BLEND_RESOLVED_OFFSET_IN_BUILDER = 0x118C
BUILDER_FRAME_PARAMETERS_OFFSET = 0x1068
BUILDER_FRAME_ACCUMULATOR_OFFSET = 0x1900
BUILDER_FRAME_WORKING_PARAMETERS_OFFSET = 0xC60
BUILDER_FRAME_COLLECTION_COUNT_OFFSET = 0xB0
BUILDER_FRAME_RESOLVER_FLAG_OFFSET = 0x7C
ANIMATABLE_DATA_BYTE_COUNT = 0x481
MAXIMUM_PARAMETERS_BUILDER_CALLS = 4096
MAXIMUM_BLEND_DECISIONS = 16384
F64_ONE_RAW_LITTLE_ENDIAN_HEX = "000000000000f03f"
BACKGROUND_FILTER_INITIALIZED_RANGES = (
    (0x000, 0x15D),
    (0x160, 0x1CA),
    (0x1D0, 0x1DC),
    (0x1E0, 0x1F8),
)
BACKGROUND_FILTER_PADDING_RANGES = (
    (0x15D, 0x160),
    (0x1CA, 0x1D0),
    (0x1DC, 0x1E0),
)
BACKGROUND_FILTER_INITIALIZED_BYTE_COUNT = sum(
    end - start for start, end in BACKGROUND_FILTER_INITIALIZED_RANGES
)

EXPECTED_ENVIRONMENT = public.EXPECTED_ENVIRONMENT
PUBLIC_CONFIGURATION_KEYS = {
    "appearance",
    "architecture",
    "backgroundByteCount",
    "backgroundCodeSHA256",
    "backgroundModuleOffset",
    "capturedCropUsedForSelection",
    "capturedImageUsedForSelection",
    "capturedMarginUsedForSelection",
    "capturedObjectUsedForSelection",
    "capturedPixelUsedForSelection",
    "capturedPublicInputUsedForSelection",
    "capturedReturnUsedForSelection",
    "direction",
    "geometry",
    "mainUUID",
    "macOSBuildVersion",
    "macOSProductVersion",
    "material",
    "maximumCallsPerInterval",
    "maximumTotalCalls",
    "renderByteCount",
    "renderCallInstructionHex",
    "renderCallOffset",
    "renderCodeSHA256",
    "renderModuleOffset",
    "renderReturnOffset",
    "sampleIndices",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    return allocation.mapping(value, label)


def sequence(value: Any, label: str) -> Sequence[Any]:
    return allocation.sequence(value, label)


def load_json(path: Path, label: str) -> Any:
    return allocation.load_json(path, label)


def validate_snapshot(
    value: Any,
    address: int,
    byte_count: int,
    label: str,
) -> bytes:
    snapshot = mapping(value, label)
    payload = bytes.fromhex(str(snapshot.get("hex", "")))
    require(snapshot.get("address") == address, f"{label} address differs")
    require(
        snapshot.get("byteCount") == byte_count,
        f"{label} byte count differs",
    )
    require(len(payload) == byte_count, f"{label} payload length differs")
    require(
        snapshot.get("sha256") == hashlib.sha256(payload).hexdigest(),
        f"{label} SHA-256 differs",
    )
    return payload


def validate_register_record(value: Any, name: str, label: str) -> bytes:
    record = mapping(value, label)
    require(record.get("name") == name, f"{label} name differs")
    require(record.get("byteCount") == 8, f"{label} byte count differs")
    raw_hex = str(record.get("hex", ""))
    require(len(raw_hex) == 16, f"{label} payload width differs")
    try:
        payload = bytes.fromhex(raw_hex)
    except ValueError as error:
        raise ValueError(f"{label} payload is not hexadecimal") from error
    require(len(payload) == 8, f"{label} payload width differs")
    require(isinstance(record.get("valueString"), str), f"{label} value differs")
    return payload


def initialized_background_filter_bytes(payload: bytes) -> bytes:
    require(
        len(payload) == BACKGROUND_FILTER_BYTE_COUNT,
        "BackgroundFilter payload width differs",
    )
    return b"".join(
        payload[start:end] for start, end in BACKGROUND_FILTER_INITIALIZED_RANGES
    )


def validate_fixed_region(
    value: Any,
    module: Mapping[str, Any],
    offset: int,
    byte_count: int,
    digest: str,
    label: str,
) -> tuple[Mapping[str, Any], bytes]:
    region = mapping(value, label)
    payload = bytes.fromhex(str(region.get("hex", "")))
    start = module["loadAddress"] + offset
    require(region.get("startAddress") == start, f"{label} start differs")
    require(
        region.get("endAddress") == start + byte_count,
        f"{label} end differs",
    )
    require(region.get("moduleOffset") == offset, f"{label} offset differs")
    require(region.get("byteCount") == byte_count, f"{label} width differs")
    require(len(payload) == byte_count, f"{label} payload width differs")
    require(region.get("sha256") == digest, f"{label} recorded hash differs")
    require(
        hashlib.sha256(payload).hexdigest() == digest,
        f"{label} code hash differs",
    )
    region_module = mapping(region.get("module"), f"{label} module")
    require(region_module == module, f"{label} module differs")
    return region, payload


def validate_frame(
    value: Any,
    module: Mapping[str, Any],
    symbol_start: int,
    symbol_end: int,
    offset: int,
    label: str,
) -> None:
    frame = mapping(value, label)
    require(frame.get("symbolStart") == symbol_start, f"{label} start differs")
    require(frame.get("symbolEnd") == symbol_end, f"{label} end differs")
    require(frame.get("symbolOffset") == offset, f"{label} offset differs")
    require(frame.get("pc") == symbol_start + offset, f"{label} PC differs")
    frame_module = mapping(frame.get("module"), f"{label} module")
    require(frame_module == module, f"{label} module differs")


def validate_event(
    events: Sequence[Any],
    index: Any,
    kind: str,
    record_index: int,
    label: str,
) -> int:
    require(
        isinstance(index, int) and 0 <= index < len(events),
        f"{label} event index differs",
    )
    event = mapping(events[index], f"{label} event")
    require(
        event == {"eventIndex": index, "kind": kind, "recordIndex": record_index},
        f"{label} event differs",
    )
    return index


def public_projection(trace_value: Any) -> dict[str, Any]:
    """Remove constructor-only records without weakening the public validator."""

    projected = copy.deepcopy(mapping(trace_value, "trace"))
    configuration = mapping(projected.get("configuration"), "configuration")
    projected["configuration"] = {
        key: configuration[key] for key in PUBLIC_CONFIGURATION_KEYS
    }
    breakpoints = mapping(projected.get("breakpoints"), "breakpoints")
    projected["breakpoints"] = {
        key: breakpoints[key]
        for key in (
            "bootstrap",
            "renderCall",
            "renderReturn",
            "providerEntry",
            "providerReturn",
        )
    }

    events = sequence(projected.get("events"), "events")
    retained = [
        copy.deepcopy(mapping(value, "event"))
        for value in events
        if mapping(value, "event").get("kind")
        in {"render-call", "render-return", "provider-entry", "provider-return"}
    ]
    remap = {}
    for index, event in enumerate(retained):
        old_index = int(event["eventIndex"])
        remap[old_index] = index
        event["eventIndex"] = index
    projected["events"] = retained

    for interval in projected["intervals"]:
        interval["entryEventIndex"] = remap[int(interval["entryEventIndex"])]
        interval["returnEventIndex"] = remap[int(interval["returnEventIndex"])]
        interval.pop("preRenderConstructorCallIndices", None)
        interval.pop("inRenderConstructorCallIndices", None)
        interval.pop("preRenderParametersBuilderCallIndices", None)
        interval.pop("inRenderParametersBuilderCallIndices", None)
    for call in projected["calls"]:
        call["entryEventIndex"] = remap[int(call["entryEventIndex"])]
        call["returnEventIndex"] = remap[int(call["returnEventIndex"])]
        call.pop("providerObjectComplete", None)
        call.pop("returnObjectComplete", None)
        call.pop("completeObjectChanged", None)
    projected["finalEventCount"] = len(retained)
    return projected


def validate_preregistration(
    value: Any,
    repository_root: Path,
) -> Mapping[str, Any]:
    preregistration = mapping(value, "constructor preregistration")
    require(
        preregistration.get(
            "backgroundFilterConstructorPublicRenderIntervalLocalMacOSPreregistrationSchemaVersion"
        )
        == PREREGISTRATION_SCHEMA_VERSION,
        "preregistration schema differs",
    )
    require(
        preregistration.get("runtimeOutcomeFrozenBeforeDispatch") is None,
        "runtime outcome was not sealed",
    )
    amendment = mapping(
        preregistration.get("operationalAmendment"),
        "preflight operational amendment",
    )
    require(
        amendment.get("noAppleApplicationDispatchedBeforeCorrection") is True,
        "preflight correction followed application dispatch",
    )
    require(
        amendment.get("prospectivePredictionsUnchanged") is True,
        "preflight correction changed a prediction",
    )
    require(
        amendment.get("runtimeOutcomeStillNull") is True,
        "preflight correction observed a runtime outcome",
    )
    symbol_amendment = mapping(
        preregistration.get("symbolIdentityOperationalAmendment"),
        "symbol-presentation operational amendment",
    )
    require(
        symbol_amendment
        == {
            "failedCaptureFinalCallCount": 0,
            "failedCaptureFinalIntervalCount": 0,
            "opticalPredictionsEvaluatedBeforeCorrection": False,
            "path": public.SYMBOL_PRESENTATION_CORRECTION_PATH,
            "prospectiveOpticalPredictionsUnchanged": True,
            "sha256": public.SYMBOL_PRESENTATION_CORRECTION_SHA256,
        },
        "symbol-presentation operational amendment differs",
    )
    framework_amendment = mapping(
        preregistration.get("frameworkSymbolIdentityOperationalAmendment"),
        "framework-identity operational amendment",
    )
    require(
        framework_amendment
        == {
            "failedCaptureFinalCallCount": 0,
            "failedCaptureFinalIntervalCount": 0,
            "opticalPredictionsEvaluatedBeforeCorrection": False,
            "path": public.FRAMEWORK_IDENTITY_CORRECTION_PATH,
            "prospectiveOpticalPredictionsUnchanged": True,
            "sha256": public.FRAMEWORK_IDENTITY_CORRECTION_SHA256,
        },
        "framework-identity operational amendment differs",
    )
    binary = mapping(preregistration.get("binary"), "binary")
    require(binary.get("sha256") == EXPECTED_BINARY_SHA256, "binary hash differs")
    profile = mapping(preregistration.get("profile"), "profile")
    require(
        profile
        == {
            "appearance": "light",
            "direction": "materialize",
            "geometry": "circle-127-center",
            "material": "regular",
            "sampleIndices": list(range(1, 33)),
        },
        "profile differs",
    )
    boundary = mapping(preregistration.get("constructorBoundary"), "boundary")
    require(
        boundary
        == {
            "backgroundFilterByteCount": BACKGROUND_FILTER_BYTE_COUNT,
            "initializedByteCount": BACKGROUND_FILTER_INITIALIZED_BYTE_COUNT,
            "initializedRanges": [
                list(value) for value in BACKGROUND_FILTER_INITIALIZED_RANGES
            ],
            "paddingRanges": [
                list(value) for value in BACKGROUND_FILTER_PADDING_RANGES
            ],
            "callInstructionHex": CONSTRUCTOR_CALL_INSTRUCTION_HEX,
            "callOffsetInProducer": CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER,
            "constructorByteCount": CONSTRUCTOR_BYTE_COUNT,
            "constructorCodeSHA256": CONSTRUCTOR_CODE_SHA256,
            "constructorModuleOffset": CONSTRUCTOR_MODULE_OFFSET,
            "parametersByteCount": PARAMETERS_BYTE_COUNT,
            "producerByteCount": PRODUCER_BYTE_COUNT,
            "producerCodeSHA256": PRODUCER_CODE_SHA256,
            "producerModuleOffset": PRODUCER_MODULE_OFFSET,
            "returnOffsetInProducer": CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER,
        },
        "constructor boundary differs",
    )
    blend_boundary = mapping(
        preregistration.get("parametersBlendBoundary"),
        "Parameters blend boundary",
    )
    require(
        blend_boundary
        == {
            "accumulatorFrameOffset": BUILDER_FRAME_ACCUMULATOR_OFFSET,
            "animatableDataByteCount": ANIMATABLE_DATA_BYTE_COUNT,
            "blendDecisionOffsetInBuilder": BLEND_DECISION_OFFSET_IN_BUILDER,
            "blendFinalGateOffsetInBuilder": BLEND_FINAL_GATE_OFFSET_IN_BUILDER,
            "blendResolvedOffsetInBuilder": BLEND_RESOLVED_OFFSET_IN_BUILDER,
            "builderByteCount": RESOLVED_RECIPE_BUILDER_BYTE_COUNT,
            "builderCodeSHA256": RESOLVED_RECIPE_BUILDER_CODE_SHA256,
            "builderModuleOffset": RESOLVED_RECIPE_BUILDER_MODULE_OFFSET,
            "callInstructionHex": RESOLVED_RECIPE_BUILDER_CALL_INSTRUCTION_HEX,
            "callOffsetInCaller": RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER,
            "callerByteCount": RESOLVED_RECIPE_BUILDER_CALLER_BYTE_COUNT,
            "callerCodeSHA256": RESOLVED_RECIPE_BUILDER_CALLER_CODE_SHA256,
            "callerModuleOffset": RESOLVED_RECIPE_BUILDER_CALLER_MODULE_OFFSET,
            "collectionCountFrameOffset": (BUILDER_FRAME_COLLECTION_COUNT_OFFSET),
            "currentParametersFrameOffset": BUILDER_FRAME_PARAMETERS_OFFSET,
            "factorRegister": "d9",
            "maximumBlendDecisions": MAXIMUM_BLEND_DECISIONS,
            "maximumParametersBuilderCalls": MAXIMUM_PARAMETERS_BUILDER_CALLS,
            "parametersByteCount": PARAMETERS_BYTE_COUNT,
            "resolverFlagFrameOffset": BUILDER_FRAME_RESOLVER_FLAG_OFFSET,
            "returnOffsetInCaller": RESOLVED_RECIPE_BUILDER_RETURN_OFFSET_IN_CALLER,
            "unityRawLittleEndianHex": F64_ONE_RAW_LITTLE_ENDIAN_HEX,
            "unityRegister": "d12",
            "workingParametersFrameOffset": (BUILDER_FRAME_WORKING_PARAMETERS_OFFSET),
        },
        "Parameters blend boundary differs",
    )
    predictions = mapping(preregistration.get("prospectivePredictions"), "predictions")
    require(
        predictions
        == {
            "allConstructorCallsOnAuthenticatedFunctionThread": True,
            "allConstructorInputsRemainBitwiseUnchanged": True,
            "allConstructorLayerIndicesAreZero": True,
            "allConstructorParametersHaveSameSampleBuilderOutput": True,
            "allMatchedProviderInitializedBytesHaveSameSampleConstructorOutput": True,
            "allParametersBuilderCallsHaveAtLeastOneBlendDecision": True,
            "allParametersBuilderCallsOnAuthenticatedFunctionThread": True,
            "allParametersBuilderCallsReachFinalGate": True,
            "allParametersBuilderCallsReachResolvedConvergence": True,
            "allParametersBuilderOutputsEqualResolvedWorkingParameters": True,
            "allSamplesHaveAtLeastOneConstructorCall": True,
            "allSamplesHaveAtLeastOneParametersBuilderCall": True,
            "completePaddingByteEqualityRequired": False,
            "oneDistinctParametersValuePerMatchedSample": True,
            "resolverFlagIsOneAtEveryDecision": True,
            "unityRegisterIsExactOneAtEveryDecision": True,
        },
        "prospective predictions differ",
    )
    predecessor = mapping(
        preregistration.get("requiredPredecessor"),
        "required predecessor",
    )
    require(
        predecessor
        == {
            "artifactDirectory": (
                "local-case22-provider-public-render-interval-d18aca7-run1"
            ),
            "captureCommit": EXPECTED_PREDECESSOR_COMMIT,
            "captureContractMustPass": True,
            "preregistrationSHA256": (
                EXPECTED_PREDECESSOR_PREREGISTRATION_SHA256
            ),
            "validatorSHA256": EXPECTED_PREDECESSOR_VALIDATOR_SHA256,
        },
        "required predecessor differs",
    )
    frozen = sequence(
        mapping(preregistration.get("frozenImplementation"), "implementation").get(
            "files"
        ),
        "frozen files",
    )
    for item_value in frozen:
        item = mapping(item_value, "frozen file")
        relative = str(item.get("path", ""))
        require(relative.startswith("Analysis/"), "frozen path escapes Analysis")
        path = repository_root / relative
        require(path.is_file(), f"frozen file {relative} is absent")
        require(sha256(path) == item.get("sha256"), f"{relative} hash differs")
    return preregistration


def validate_context(
    path: Path,
    preregistration_path: Path,
    frozen_files: Mapping[str, str],
) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    require(len(lines) >= 9, "capture context is incomplete")
    require(len(lines[0]) == 40, "capture commit identity differs")
    int(lines[0], 16)
    expected_hashes = (
        EXPECTED_BINARY_SHA256,
        frozen_files[
            "Analysis/capture_background_filter_constructor_public_render_interval_local_macos_26_6_1_lldb.py"
        ],
        sha256(preregistration_path),
        EXPECTED_PREFLIGHT_SHA256,
        frozen_files[
            "Analysis/validate_background_filter_constructor_public_render_interval_local_macos_26_6_1.py"
        ],
        frozen_files[
            "Analysis/run_background_filter_constructor_public_render_interval_local_macos_26_6_1.sh"
        ],
    )
    for line, expected in zip(lines[1:7], expected_hashes):
        require(line.startswith(expected + "  "), "capture context hash differs")
    environment = dict(line.split("=", 1) for line in lines[7:])
    trace_path = environment.pop(
        "LG_BACKGROUND_FILTER_CONSTRUCTOR_PUBLIC_RENDER_INTERVAL_TRACE_OUTPUT",
        None,
    )
    require(
        trace_path is not None
        and trace_path.endswith(
            "/background-filter-constructor-public-render-interval-trace.json"
        ),
        "trace output environment differs",
    )
    require(environment == EXPECTED_ENVIRONMENT, "capture environment differs")
    return lines[0]


def validate_constructor_trace(
    trace_value: Any,
    matched_provider_call_indices: Sequence[Any],
) -> dict[str, Any]:
    trace = mapping(trace_value, "trace")
    require(
        trace.get(
            "backgroundFilterConstructorPublicRenderIntervalLocalMacOSLldbTraceSchemaVersion"
        )
        == TRACE_SCHEMA_VERSION,
        "constructor trace schema differs",
    )
    configuration = mapping(trace.get("configuration"), "configuration")
    expected_configuration = {
        "designLibraryUUID": DESIGN_LIBRARY_UUID,
        "constructorModuleOffset": CONSTRUCTOR_MODULE_OFFSET,
        "constructorByteCount": CONSTRUCTOR_BYTE_COUNT,
        "constructorCodeSHA256": CONSTRUCTOR_CODE_SHA256,
        "producerModuleOffset": PRODUCER_MODULE_OFFSET,
        "producerByteCount": PRODUCER_BYTE_COUNT,
        "producerCodeSHA256": PRODUCER_CODE_SHA256,
        "constructorCallOffsetInProducer": CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER,
        "constructorReturnOffsetInProducer": CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER,
        "constructorCallInstructionHex": CONSTRUCTOR_CALL_INSTRUCTION_HEX,
        "parametersByteCount": PARAMETERS_BYTE_COUNT,
        "backgroundFilterByteCount": BACKGROUND_FILTER_BYTE_COUNT,
        "maximumConstructorCalls": MAXIMUM_CONSTRUCTOR_CALLS,
        "resolvedRecipeBuilderModuleOffset": RESOLVED_RECIPE_BUILDER_MODULE_OFFSET,
        "resolvedRecipeBuilderByteCount": RESOLVED_RECIPE_BUILDER_BYTE_COUNT,
        "resolvedRecipeBuilderCodeSHA256": RESOLVED_RECIPE_BUILDER_CODE_SHA256,
        "resolvedRecipeBuilderCallerModuleOffset": (
            RESOLVED_RECIPE_BUILDER_CALLER_MODULE_OFFSET
        ),
        "resolvedRecipeBuilderCallerByteCount": (
            RESOLVED_RECIPE_BUILDER_CALLER_BYTE_COUNT
        ),
        "resolvedRecipeBuilderCallerCodeSHA256": (
            RESOLVED_RECIPE_BUILDER_CALLER_CODE_SHA256
        ),
        "resolvedRecipeBuilderCallOffsetInCaller": (
            RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER
        ),
        "resolvedRecipeBuilderReturnOffsetInCaller": (
            RESOLVED_RECIPE_BUILDER_RETURN_OFFSET_IN_CALLER
        ),
        "resolvedRecipeBuilderCallInstructionHex": (
            RESOLVED_RECIPE_BUILDER_CALL_INSTRUCTION_HEX
        ),
        "blendDecisionOffsetInBuilder": BLEND_DECISION_OFFSET_IN_BUILDER,
        "blendFinalGateOffsetInBuilder": BLEND_FINAL_GATE_OFFSET_IN_BUILDER,
        "blendResolvedOffsetInBuilder": BLEND_RESOLVED_OFFSET_IN_BUILDER,
        "builderFrameParametersOffset": BUILDER_FRAME_PARAMETERS_OFFSET,
        "builderFrameAccumulatorOffset": BUILDER_FRAME_ACCUMULATOR_OFFSET,
        "builderFrameWorkingParametersOffset": (
            BUILDER_FRAME_WORKING_PARAMETERS_OFFSET
        ),
        "builderFrameCollectionCountOffset": (BUILDER_FRAME_COLLECTION_COUNT_OFFSET),
        "builderFrameResolverFlagOffset": BUILDER_FRAME_RESOLVER_FLAG_OFFSET,
        "animatableDataByteCount": ANIMATABLE_DATA_BYTE_COUNT,
        "maximumParametersBuilderCalls": MAXIMUM_PARAMETERS_BUILDER_CALLS,
        "maximumBlendDecisions": MAXIMUM_BLEND_DECISIONS,
        "constructorCaptureStartsAtBackgroundFunctionEntry": True,
        "constructorCaptureEndsAtFinalRenderReturn": True,
        "parametersBuilderCaptureStartsAtBackgroundFunctionEntry": True,
        "parametersBuilderCaptureEndsAtFinalRenderReturn": True,
        "preRenderAssignmentRule": (
            "all completed unassigned constructor and Parameters builder calls "
            "are assigned to the immediately following structural render interval"
        ),
        "capturedParametersUsedForSelection": False,
        "capturedConstructorOutputUsedForSelection": False,
        "capturedProviderObjectUsedForSelection": False,
        "capturedAddressUsedForSelection": False,
        "capturedBlendFactorUsedForSelection": False,
        "capturedBlendCountUsedForSelection": False,
        "capturedAnimatableDataUsedForSelection": False,
        "capturedBuilderOutputUsedForSelection": False,
        "completeProviderObjectByteCount": BACKGROUND_FILTER_BYTE_COUNT,
    }
    for key, expected in expected_configuration.items():
        require(configuration.get(key) == expected, f"configuration {key} differs")
    background_thread = configuration.get("backgroundFunctionThreadID")
    require(isinstance(background_thread, int), "background thread differs")

    modules = mapping(trace.get("modules"), "modules")
    design_module = mapping(modules.get("designLibrary"), "DesignLibrary module")
    require(design_module.get("valid") is True, "DesignLibrary module is invalid")
    require(
        design_module.get("uuid") == DESIGN_LIBRARY_UUID,
        "DesignLibrary UUID differs",
    )
    require(
        isinstance(design_module.get("loadAddress"), int)
        and design_module["loadAddress"] > 0,
        "DesignLibrary load address differs",
    )
    constructor, constructor_raw = validate_fixed_region(
        trace.get("constructor"),
        design_module,
        CONSTRUCTOR_MODULE_OFFSET,
        CONSTRUCTOR_BYTE_COUNT,
        CONSTRUCTOR_CODE_SHA256,
        "constructor",
    )
    producer, producer_raw = validate_fixed_region(
        trace.get("constructorProducer"),
        design_module,
        PRODUCER_MODULE_OFFSET,
        PRODUCER_BYTE_COUNT,
        PRODUCER_CODE_SHA256,
        "producer",
    )
    builder, _builder_raw = validate_fixed_region(
        trace.get("resolvedRecipeBuilder"),
        design_module,
        RESOLVED_RECIPE_BUILDER_MODULE_OFFSET,
        RESOLVED_RECIPE_BUILDER_BYTE_COUNT,
        RESOLVED_RECIPE_BUILDER_CODE_SHA256,
        "ResolvedRecipe Parameters builder",
    )
    builder_caller, builder_caller_raw = validate_fixed_region(
        trace.get("resolvedRecipeBuilderCaller"),
        design_module,
        RESOLVED_RECIPE_BUILDER_CALLER_MODULE_OFFSET,
        RESOLVED_RECIPE_BUILDER_CALLER_BYTE_COUNT,
        RESOLVED_RECIPE_BUILDER_CALLER_CODE_SHA256,
        "ResolvedRecipe Parameters builder caller",
    )
    call_raw = producer_raw[
        CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER : CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER + 4
    ]
    require(
        call_raw.hex() == CONSTRUCTOR_CALL_INSTRUCTION_HEX,
        "constructor call instruction differs",
    )
    require(
        public.decode_arm64_bl_target(
            call_raw,
            producer["startAddress"] + CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER,
        )
        == constructor["startAddress"],
        "constructor call target differs",
    )
    builder_call_raw = builder_caller_raw[
        RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER : RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER
        + 4
    ]
    require(
        builder_call_raw.hex() == RESOLVED_RECIPE_BUILDER_CALL_INSTRUCTION_HEX,
        "ResolvedRecipe builder call instruction differs",
    )
    require(
        public.decode_arm64_bl_target(
            builder_call_raw,
            builder_caller["startAddress"]
            + RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER,
        )
        == builder["startAddress"],
        "ResolvedRecipe builder call target differs",
    )

    breakpoints = mapping(trace.get("breakpoints"), "breakpoints")
    for key, expected in (
        ("constructorEntry", constructor["startAddress"]),
        (
            "constructorReturn",
            producer["startAddress"] + CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER,
        ),
        ("parametersBuilderEntry", builder["startAddress"]),
        (
            "parametersBlendDecision",
            builder["startAddress"] + BLEND_DECISION_OFFSET_IN_BUILDER,
        ),
        (
            "parametersBlendFinal",
            builder["startAddress"] + BLEND_FINAL_GATE_OFFSET_IN_BUILDER,
        ),
        (
            "parametersBlendResolved",
            builder["startAddress"] + BLEND_RESOLVED_OFFSET_IN_BUILDER,
        ),
        (
            "parametersBuilderReturn",
            builder_caller["startAddress"]
            + RESOLVED_RECIPE_BUILDER_RETURN_OFFSET_IN_CALLER,
        ),
    ):
        breakpoint = mapping(breakpoints.get(key), key)
        require(breakpoint.get("address") == expected, f"{key} address differs")
        require(breakpoint.get("locationCount") == 1, f"{key} count differs")

    events = sequence(trace.get("events"), "events")
    intervals = [
        mapping(value, f"interval {index}")
        for index, value in enumerate(sequence(trace.get("intervals"), "intervals"))
    ]
    provider_calls = [
        mapping(value, f"provider call {index}")
        for index, value in enumerate(sequence(trace.get("calls"), "provider calls"))
    ]
    constructor_calls = [
        mapping(value, f"constructor call {index}")
        for index, value in enumerate(
            sequence(trace.get("constructorCalls"), "constructor calls")
        )
    ]
    builder_calls = [
        mapping(value, f"Parameters builder call {index}")
        for index, value in enumerate(
            sequence(trace.get("parametersBuilderCalls"), "Parameters builder calls")
        )
    ]
    blend_decisions = [
        mapping(value, f"Parameters blend decision {index}")
        for index, value in enumerate(
            sequence(
                trace.get("parametersBlendDecisions"),
                "Parameters blend decisions",
            )
        )
    ]
    require(len(intervals) == 32, "interval count differs")
    require(
        32 <= len(constructor_calls) <= MAXIMUM_CONSTRUCTOR_CALLS,
        "constructor call count differs",
    )
    require(
        32 <= len(builder_calls) <= MAXIMUM_PARAMETERS_BUILDER_CALLS,
        "Parameters builder call count differs",
    )
    require(
        0 < len(blend_decisions) <= MAXIMUM_BLEND_DECISIONS,
        "Parameters blend decision count differs",
    )

    referenced_constructor_calls = []
    for interval_index, interval in enumerate(intervals):
        pre_render = list(
            sequence(
                interval.get("preRenderConstructorCallIndices"),
                f"interval {interval_index} pre-render constructors",
            )
        )
        in_render = list(
            sequence(
                interval.get("inRenderConstructorCallIndices"),
                f"interval {interval_index} in-render constructors",
            )
        )
        require(
            pre_render or in_render, f"sample {interval_index + 1} has no constructor"
        )
        referenced_constructor_calls.extend(pre_render)
        referenced_constructor_calls.extend(in_render)
    require(
        sorted(referenced_constructor_calls) == list(range(len(constructor_calls))),
        "constructor interval partition differs",
    )
    require(
        len(set(referenced_constructor_calls)) == len(constructor_calls),
        "constructor call is assigned more than once",
    )

    referenced_builder_calls = []
    for interval_index, interval in enumerate(intervals):
        pre_render = list(
            sequence(
                interval.get("preRenderParametersBuilderCallIndices"),
                f"interval {interval_index} pre-render Parameters builders",
            )
        )
        in_render = list(
            sequence(
                interval.get("inRenderParametersBuilderCallIndices"),
                f"interval {interval_index} in-render Parameters builders",
            )
        )
        require(
            pre_render or in_render,
            f"sample {interval_index + 1} has no Parameters builder",
        )
        referenced_builder_calls.extend(pre_render)
        referenced_builder_calls.extend(in_render)
    require(
        sorted(referenced_builder_calls) == list(range(len(builder_calls))),
        "Parameters builder interval partition differs",
    )
    require(
        len(set(referenced_builder_calls)) == len(builder_calls),
        "Parameters builder call is assigned more than once",
    )

    constructor_events = []
    outputs_by_interval: dict[int, list[tuple[int, bytes, bytes]]] = {
        index: [] for index in range(32)
    }
    parameter_hashes = set()
    for index, call in enumerate(constructor_calls):
        require(call.get("callIndex") == index, f"constructor {index} index differs")
        thread_id = call.get("threadID")
        require(thread_id == background_thread, f"constructor {index} thread differs")
        require(
            call.get("onBackgroundFunctionThread") is True,
            f"constructor {index} thread marker differs",
        )
        interval_index = call.get("assignedIntervalIndex")
        require(
            isinstance(interval_index, int) and 0 <= interval_index < 32,
            f"constructor {index} interval differs",
        )
        require(
            call.get("assignedSampleIndex") == interval_index + 1,
            f"constructor {index} sample differs",
        )
        parameters_address = call.get("parametersAddress")
        output_address = call.get("outputAddress")
        require(
            isinstance(parameters_address, int) and parameters_address > 0,
            f"constructor {index} Parameters address differs",
        )
        require(
            isinstance(output_address, int) and output_address > 0,
            f"constructor {index} output address differs",
        )
        require(call.get("layerIndex") == 0, f"constructor {index} layer differs")
        require(
            isinstance(call.get("flagsRawValue"), int)
            and 0 <= call["flagsRawValue"] < 1 << 64,
            f"constructor {index} flags differ",
        )
        parameters_entry = validate_snapshot(
            call.get("parametersAtEntry"),
            parameters_address,
            PARAMETERS_BYTE_COUNT,
            f"constructor {index} Parameters entry",
        )
        parameters_return = validate_snapshot(
            call.get("parametersAtReturn"),
            parameters_address,
            PARAMETERS_BYTE_COUNT,
            f"constructor {index} Parameters return",
        )
        require(
            parameters_entry == parameters_return,
            f"constructor {index} Parameters changed",
        )
        require(
            call.get("parametersChanged") is False,
            f"constructor {index} Parameters mutation marker differs",
        )
        output = validate_snapshot(
            call.get("outputAtReturn"),
            output_address,
            BACKGROUND_FILTER_BYTE_COUNT,
            f"constructor {index} output",
        )
        validate_frame(
            call.get("entryFrame"),
            design_module,
            constructor["startAddress"],
            constructor["endAddress"],
            0,
            f"constructor {index} entry frame",
        )
        validate_frame(
            call.get("returnFrame"),
            design_module,
            producer["startAddress"],
            producer["endAddress"],
            CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER,
            f"constructor {index} return frame",
        )
        entry_event = validate_event(
            events,
            call.get("entryEventIndex"),
            "constructor-entry",
            index,
            f"constructor {index} entry",
        )
        return_event = validate_event(
            events,
            call.get("returnEventIndex"),
            "constructor-return",
            index,
            f"constructor {index} return",
        )
        require(entry_event < return_event, f"constructor {index} event order differs")
        interval = intervals[interval_index]
        timing = call.get("timingRelativeToRender")
        if timing == "pre-render":
            require(
                index in interval["preRenderConstructorCallIndices"],
                f"constructor {index} pre-render assignment differs",
            )
            require(
                return_event < interval["entryEventIndex"],
                f"constructor {index} did not precede render",
            )
            if interval_index > 0:
                require(
                    intervals[interval_index - 1]["returnEventIndex"] < entry_event,
                    f"constructor {index} precedes prior render return",
                )
            require(
                call.get("structuralNextSampleIndexAtEntry") == interval_index + 1,
                f"constructor {index} structural next sample differs",
            )
        elif timing == "in-render":
            require(
                index in interval["inRenderConstructorCallIndices"],
                f"constructor {index} in-render assignment differs",
            )
            require(
                interval["entryEventIndex"]
                < entry_event
                < return_event
                < interval["returnEventIndex"],
                f"constructor {index} escaped render interval",
            )
            require(
                call.get("structuralNextSampleIndexAtEntry") is None,
                f"constructor {index} next sample marker differs",
            )
        else:
            raise ValueError(f"constructor {index} timing differs")
        constructor_events.extend((entry_event, return_event))
        outputs_by_interval[interval_index].append((index, parameters_entry, output))
        parameter_hashes.add(hashlib.sha256(parameters_entry).hexdigest())

    require(
        trace.get("finalConstructorCallCount") == len(constructor_calls),
        "final constructor count differs",
    )
    require(
        trace.get("finalPendingConstructorCallCount") == 0,
        "pending constructor count differs",
    )
    require(
        trace.get("finalUnassignedConstructorCallCount") == 0,
        "unassigned constructor count differs",
    )
    require(trace.get("allConstructorCallsReturned") is True, "return seal differs")
    require(trace.get("allConstructorCallsAssigned") is True, "assignment seal differs")

    builder_events = []
    referenced_blend_decisions = []
    builder_outputs_by_interval: dict[int, list[tuple[int, bytes]]] = {
        index: [] for index in range(32)
    }
    direct_copy_builder_indices = []
    weighted_builder_indices = []
    for index, call in enumerate(builder_calls):
        require(
            call.get("builderCallIndex") == index,
            f"Parameters builder {index} index differs",
        )
        thread_id = call.get("threadID")
        require(
            thread_id == background_thread,
            f"Parameters builder {index} thread differs",
        )
        require(
            call.get("onBackgroundFunctionThread") is True,
            f"Parameters builder {index} thread marker differs",
        )
        interval_index = call.get("assignedIntervalIndex")
        require(
            isinstance(interval_index, int) and 0 <= interval_index < 32,
            f"Parameters builder {index} interval differs",
        )
        require(
            call.get("assignedSampleIndex") == interval_index + 1,
            f"Parameters builder {index} sample differs",
        )
        for register_name in ("inputX0RawValue", "inputX1RawValue", "inputX2RawValue"):
            require(
                isinstance(call.get(register_name), int)
                and 0 <= call[register_name] < 1 << 64,
                f"Parameters builder {index} {register_name} differs",
            )
        output_address = call.get("outputParametersAddress")
        require(
            isinstance(output_address, int) and output_address > 0,
            f"Parameters builder {index} output address differs",
        )
        validate_frame(
            call.get("entryFrame"),
            design_module,
            builder["startAddress"],
            builder["endAddress"],
            0,
            f"Parameters builder {index} entry frame",
        )
        validate_frame(
            call.get("finalFrame"),
            design_module,
            builder["startAddress"],
            builder["endAddress"],
            BLEND_FINAL_GATE_OFFSET_IN_BUILDER,
            f"Parameters builder {index} final frame",
        )
        validate_frame(
            call.get("resolvedFrame"),
            design_module,
            builder["startAddress"],
            builder["endAddress"],
            BLEND_RESOLVED_OFFSET_IN_BUILDER,
            f"Parameters builder {index} resolved frame",
        )
        validate_frame(
            call.get("returnFrame"),
            design_module,
            builder_caller["startAddress"],
            builder_caller["endAddress"],
            RESOLVED_RECIPE_BUILDER_RETURN_OFFSET_IN_CALLER,
            f"Parameters builder {index} return frame",
        )
        entry_event = validate_event(
            events,
            call.get("entryEventIndex"),
            "parameters-builder-entry",
            index,
            f"Parameters builder {index} entry",
        )
        final_event = validate_event(
            events,
            call.get("finalEventIndex"),
            "parameters-blend-final",
            index,
            f"Parameters builder {index} final",
        )
        resolved_event = validate_event(
            events,
            call.get("resolvedEventIndex"),
            "parameters-blend-resolved",
            index,
            f"Parameters builder {index} resolved",
        )
        return_event = validate_event(
            events,
            call.get("returnEventIndex"),
            "parameters-builder-return",
            index,
            f"Parameters builder {index} return",
        )
        require(
            entry_event < final_event < resolved_event < return_event,
            f"Parameters builder {index} event order differs",
        )
        interval = intervals[interval_index]
        timing = call.get("timingRelativeToRender")
        if timing == "pre-render":
            require(
                index in interval["preRenderParametersBuilderCallIndices"],
                f"Parameters builder {index} pre-render assignment differs",
            )
            require(
                return_event < interval["entryEventIndex"],
                f"Parameters builder {index} did not precede render",
            )
            if interval_index > 0:
                require(
                    intervals[interval_index - 1]["returnEventIndex"] < entry_event,
                    f"Parameters builder {index} precedes prior render return",
                )
            require(
                call.get("structuralNextSampleIndexAtEntry") == interval_index + 1,
                f"Parameters builder {index} structural next sample differs",
            )
        elif timing == "in-render":
            require(
                index in interval["inRenderParametersBuilderCallIndices"],
                f"Parameters builder {index} in-render assignment differs",
            )
            require(
                interval["entryEventIndex"]
                < entry_event
                < return_event
                < interval["returnEventIndex"],
                f"Parameters builder {index} escaped render interval",
            )
            require(
                call.get("structuralNextSampleIndexAtEntry") is None,
                f"Parameters builder {index} next sample marker differs",
            )
        else:
            raise ValueError(f"Parameters builder {index} timing differs")

        frame_base = call.get("frameBaseAtFinalGate")
        require(
            isinstance(frame_base, int) and frame_base > 0,
            f"Parameters builder {index} final frame base differs",
        )
        resolver_flag = call.get("resolverFlagAtFinalGate")
        require(
            resolver_flag in (0, 1),
            f"Parameters builder {index} final resolver flag differs",
        )
        pre_resolver_working = validate_snapshot(
            call.get("preResolverWorkingParameters"),
            frame_base + BUILDER_FRAME_WORKING_PARAMETERS_OFFSET,
            PARAMETERS_BYTE_COUNT,
            f"Parameters builder {index} pre-resolver working Parameters",
        )
        validate_snapshot(
            call.get("accumulatorAnimatableDataAtFinalGate"),
            frame_base + BUILDER_FRAME_ACCUMULATOR_OFFSET,
            ANIMATABLE_DATA_BYTE_COUNT,
            f"Parameters builder {index} final-gate accumulator",
        )
        resolved_frame_base = call.get("frameBaseAtResolvedConvergence")
        require(
            resolved_frame_base == frame_base,
            f"Parameters builder {index} resolved frame base differs",
        )
        resolved_working = validate_snapshot(
            call.get("resolvedWorkingParameters"),
            frame_base + BUILDER_FRAME_WORKING_PARAMETERS_OFFSET,
            PARAMETERS_BYTE_COUNT,
            f"Parameters builder {index} resolved working Parameters",
        )
        output_parameters = validate_snapshot(
            call.get("outputParametersAtReturn"),
            output_address,
            PARAMETERS_BYTE_COUNT,
            f"Parameters builder {index} output Parameters",
        )
        require(
            resolved_working == output_parameters,
            f"Parameters builder {index} resolved working/output bytes differ",
        )

        decision_indices = list(
            sequence(
                call.get("decisionIndices"),
                f"Parameters builder {index} decision indices",
            )
        )
        require(decision_indices, f"Parameters builder {index} has no decision")
        require(
            decision_indices == sorted(decision_indices)
            and len(set(decision_indices)) == len(decision_indices),
            f"Parameters builder {index} decision order differs",
        )
        decision_events = []
        decision_values = []
        for decision_index in decision_indices:
            require(
                isinstance(decision_index, int)
                and 0 <= decision_index < len(blend_decisions),
                f"Parameters builder {index} decision index differs",
            )
            decision = blend_decisions[decision_index]
            require(
                decision.get("decisionIndex") == decision_index,
                f"Parameters blend decision {decision_index} index differs",
            )
            require(
                decision.get("builderCallIndex") == index,
                f"Parameters blend decision {decision_index} builder differs",
            )
            require(
                decision.get("threadID") == thread_id,
                f"Parameters blend decision {decision_index} thread differs",
            )
            decision_frame_base = decision.get("frameBase")
            require(
                decision_frame_base == frame_base,
                f"Parameters blend decision {decision_index} frame base differs",
            )
            validate_frame(
                decision.get("frame"),
                design_module,
                builder["startAddress"],
                builder["endAddress"],
                BLEND_DECISION_OFFSET_IN_BUILDER,
                f"Parameters blend decision {decision_index} frame",
            )
            collection_count = decision.get("collectionCount")
            require(
                isinstance(collection_count, int) and 0 <= collection_count < 1 << 64,
                f"Parameters blend decision {decision_index} count differs",
            )
            predecision_flag = decision.get("resolverFlagBeforeDecision")
            require(
                predecision_flag == 1,
                f"Parameters blend decision {decision_index} flag differs",
            )
            factor = validate_register_record(
                decision.get("factorD9"),
                "d9",
                f"Parameters blend decision {decision_index} factor",
            )
            unity = validate_register_record(
                decision.get("unityD12"),
                "d12",
                f"Parameters blend decision {decision_index} unity",
            )
            require(
                unity.hex() == F64_ONE_RAW_LITTLE_ENDIAN_HEX,
                f"Parameters blend decision {decision_index} unity differs",
            )
            current = validate_snapshot(
                decision.get("currentParameters"),
                frame_base + BUILDER_FRAME_PARAMETERS_OFFSET,
                PARAMETERS_BYTE_COUNT,
                f"Parameters blend decision {decision_index} current Parameters",
            )
            validate_snapshot(
                decision.get("priorAccumulatorAnimatableData"),
                frame_base + BUILDER_FRAME_ACCUMULATOR_OFFSET,
                ANIMATABLE_DATA_BYTE_COUNT,
                f"Parameters blend decision {decision_index} prior accumulator",
            )
            decision_event = validate_event(
                events,
                decision.get("eventIndex"),
                "parameters-blend-decision",
                decision_index,
                f"Parameters blend decision {decision_index}",
            )
            require(
                entry_event < decision_event < final_event,
                f"Parameters blend decision {decision_index} event order differs",
            )
            decision_events.append(decision_event)
            decision_values.append((collection_count, factor, current))
        require(
            decision_events == sorted(decision_events),
            f"Parameters builder {index} decision event order differs",
        )
        referenced_blend_decisions.extend(decision_indices)
        builder_events.extend(
            (
                entry_event,
                *decision_events,
                final_event,
                resolved_event,
                return_event,
            )
        )

        if resolver_flag == 0:
            collection_count, factor, current = decision_values[-1]
            require(
                collection_count == 1,
                f"Parameters builder {index} direct-copy collection count differs",
            )
            require(
                factor.hex() == F64_ONE_RAW_LITTLE_ENDIAN_HEX,
                f"Parameters builder {index} direct-copy factor differs",
            )
            require(
                pre_resolver_working == current,
                f"Parameters builder {index} direct-copy source bytes differ",
            )
            require(
                resolved_working == pre_resolver_working,
                f"Parameters builder {index} direct-copy convergence bytes differ",
            )
            direct_copy_builder_indices.append(index)
        else:
            weighted_builder_indices.append(index)
        builder_outputs_by_interval[interval_index].append((index, output_parameters))

    require(
        sorted(referenced_blend_decisions) == list(range(len(blend_decisions))),
        "Parameters blend decision partition differs",
    )
    require(
        len(set(referenced_blend_decisions)) == len(blend_decisions),
        "Parameters blend decision is assigned more than once",
    )
    require(
        trace.get("finalParametersBuilderCallCount") == len(builder_calls),
        "final Parameters builder count differs",
    )
    require(
        trace.get("finalBlendDecisionCount") == len(blend_decisions),
        "final Parameters blend decision count differs",
    )
    require(
        trace.get("finalPendingParametersBuilderCallCount") == 0,
        "pending Parameters builder count differs",
    )
    require(
        trace.get("finalUnassignedParametersBuilderCallCount") == 0,
        "unassigned Parameters builder count differs",
    )
    require(
        trace.get("allParametersBuilderCallsReachedFinalGate") is True,
        "Parameters builder final-gate seal differs",
    )
    require(
        trace.get("allParametersBuilderCallsReachedResolvedConvergence") is True,
        "Parameters builder resolved-convergence seal differs",
    )
    require(
        trace.get("allParametersBuilderCallsReturned") is True,
        "Parameters builder return seal differs",
    )
    require(
        trace.get("allParametersBuilderCallsAssigned") is True,
        "Parameters builder assignment seal differs",
    )

    constructor_builder_joins = []
    for interval_index, values in outputs_by_interval.items():
        for constructor_index, parameters, _output in values:
            matches = [
                builder_index
                for builder_index, builder_output in builder_outputs_by_interval[
                    interval_index
                ]
                if builder_output == parameters
            ]
            require(
                matches,
                f"constructor {constructor_index} has no same-sample Parameters builder output",
            )
            constructor_builder_joins.append(
                {
                    "sampleIndex": interval_index + 1,
                    "constructorCallIndex": constructor_index,
                    "parametersBuilderCallIndices": matches,
                    "parametersSHA256": hashlib.sha256(parameters).hexdigest(),
                }
            )

    for index, call in enumerate(provider_calls):
        address = int(call["providerObjectAddress"])
        prefix = validate_snapshot(
            call.get("providerObject"),
            address,
            allocation.OBJECT_BYTE_COUNT,
            f"provider {index} prefix",
        )
        complete = validate_snapshot(
            call.get("providerObjectComplete"),
            address,
            BACKGROUND_FILTER_BYTE_COUNT,
            f"provider {index} complete entry",
        )
        returned = validate_snapshot(
            call.get("returnObjectComplete"),
            address,
            BACKGROUND_FILTER_BYTE_COUNT,
            f"provider {index} complete return",
        )
        require(complete[: len(prefix)] == prefix, f"provider {index} prefix differs")
        require(complete == returned, f"provider {index} complete object changed")
        require(
            call.get("completeObjectChanged") is False,
            f"provider {index} complete mutation marker differs",
        )

    joins = []
    for raw_call_index in matched_provider_call_indices:
        call_index = int(raw_call_index)
        call = provider_calls[call_index]
        interval_index = int(call["intervalIndex"])
        provider_raw = bytes.fromhex(call["providerObjectComplete"]["hex"])
        provider_initialized = initialized_background_filter_bytes(provider_raw)
        matches = [
            (constructor_index, parameters, output)
            for constructor_index, parameters, output in outputs_by_interval[
                interval_index
            ]
            if initialized_background_filter_bytes(output) == provider_initialized
        ]
        require(
            matches,
            f"matched provider {call_index} has no same-sample initialized constructor output",
        )
        distinct_parameters = {parameters for _, parameters, _ in matches}
        require(
            len(distinct_parameters) == 1,
            f"sample {interval_index + 1} has ambiguous Parameters values",
        )
        parameters = next(iter(distinct_parameters))
        builder_matches = [
            builder_index
            for builder_index, builder_output in builder_outputs_by_interval[
                interval_index
            ]
            if builder_output == parameters
        ]
        require(
            builder_matches,
            f"matched provider {call_index} has no same-sample Parameters builder output",
        )
        full_matches = [
            constructor_index
            for constructor_index, _, output in matches
            if output == provider_raw
        ]
        padding_differences = sorted(
            {
                offset
                for _, _, output in matches
                for start, end in BACKGROUND_FILTER_PADDING_RANGES
                for offset in range(start, end)
                if output[offset] != provider_raw[offset]
            }
        )
        joins.append(
            {
                "sampleIndex": interval_index + 1,
                "providerCallIndex": call_index,
                "constructorCallIndices": [value[0] for value in matches],
                "parametersBuilderCallIndices": builder_matches,
                "full504ByteMatchConstructorCallIndices": full_matches,
                "backgroundFilterSHA256": hashlib.sha256(provider_raw).hexdigest(),
                "initialized491ByteSHA256": hashlib.sha256(
                    provider_initialized
                ).hexdigest(),
                "parametersSHA256": hashlib.sha256(parameters).hexdigest(),
                "paddingDifferenceOffsets": padding_differences,
            }
        )

    public_event_indices = [
        int(mapping(value, "event")["eventIndex"])
        for value in events
        if mapping(value, "event").get("kind")
        in {"render-call", "render-return", "provider-entry", "provider-return"}
    ]
    require(
        sorted(public_event_indices + constructor_events + builder_events)
        == list(range(len(events))),
        "complete event partition differs",
    )
    require(
        len(events)
        == 2 * len(intervals)
        + 2 * len(provider_calls)
        + 2 * len(constructor_calls)
        + 4 * len(builder_calls)
        + len(blend_decisions),
        "complete event cardinality differs",
    )
    return {
        "constructorCallCount": len(constructor_calls),
        "parametersBuilderCallCount": len(builder_calls),
        "parametersBlendDecisionCount": len(blend_decisions),
        "directCopyBuilderCallCount": len(direct_copy_builder_indices),
        "weightedBuilderCallCount": len(weighted_builder_indices),
        "directCopyBuilderCallIndices": direct_copy_builder_indices,
        "weightedBuilderCallIndices": weighted_builder_indices,
        "distinctParametersCount": len(parameter_hashes),
        "matchedProviderCallCount": len(joins),
        "initializedBackgroundFilterByteCount": (
            BACKGROUND_FILTER_INITIALIZED_BYTE_COUNT
        ),
        "paddingByteCount": (
            BACKGROUND_FILTER_BYTE_COUNT - BACKGROUND_FILTER_INITIALIZED_BYTE_COUNT
        ),
        "allMatchedProvidersHaveExactSameSampleInitializedConstructorOutput": True,
        "allMatchedProvidersHaveFull504ByteConstructorOutput": all(
            value["full504ByteMatchConstructorCallIndices"] for value in joins
        ),
        "oneDistinctParametersValuePerMatchedSample": True,
        "allConstructorParametersHaveSameSampleBuilderOutput": True,
        "allBuilderOutputsEqualResolvedWorkingParameters": True,
        "constructorBuilderJoins": constructor_builder_joins,
        "joins": joins,
    }


def validate(
    preregistration_path: Path,
    artifact_directory: Path,
) -> dict[str, Any]:
    repository_root = preregistration_path.resolve().parent.parent
    preregistration = validate_preregistration(
        load_json(preregistration_path, "preregistration"), repository_root
    )
    frozen_files = {
        str(mapping(value, "frozen file")["path"]): str(
            mapping(value, "frozen file")["sha256"]
        )
        for value in sequence(
            mapping(preregistration["frozenImplementation"], "implementation")["files"],
            "frozen files",
        )
    }
    commit = validate_context(
        artifact_directory / "capture-context.txt",
        preregistration_path,
        frozen_files,
    )
    public.validate_preflight(
        load_json(artifact_directory / "capture-session-preflight.json", "preflight")
    )
    require(
        (artifact_directory / "lldb-exit-status.txt").read_text(encoding="utf-8")
        == "0\n",
        "LLDB exit status differs",
    )
    lldb_log = (artifact_directory / "lldb.log").read_text(encoding="utf-8")
    require("exited with status = 0" in lldb_log, "application did not exit zero")
    require("Traceback" not in lldb_log, "LLDB log contains a traceback")
    require(
        "error: Aborting reading of commands" not in lldb_log,
        "LLDB command failed",
    )

    predecessor = mapping(preregistration.get("requiredPredecessor"), "predecessor")
    predecessor_directory = repository_root / str(predecessor["artifactDirectory"])
    predecessor_result = public.validate(
        repository_root
        / "Analysis/backdrop_margin_case22_provider_public_render_interval_transfer_local_macos_26_6_1_preregistration.json",
        predecessor_directory,
    )
    require(
        predecessor_result.get("captureContractPassed") is True,
        "predecessor capture did not pass",
    )
    require(
        mapping(predecessor_result.get("inputs"), "predecessor inputs").get(
            "sourceCommit"
        )
        == EXPECTED_PREDECESSOR_COMMIT,
        "predecessor capture commit differs",
    )

    trace_path = (
        artifact_directory
        / "background-filter-constructor-public-render-interval-trace.json"
    )
    timeline_path = artifact_directory / "transition-timeline.json"
    trace = load_json(trace_path, "trace")
    timeline = load_json(timeline_path, "timeline")
    projected = public_projection(trace)
    public_summary, _ = public.validate_trace(projected)
    timeline_summary = allocation.validate_timeline(timeline, artifact_directory)
    transfer = public.validate_interval_transfer(timeline, projected)
    constructor_summary = validate_constructor_trace(
        trace, transfer["matchedProviderCallIndices"]
    )
    primary_paths = {
        "captureContext": artifact_directory / "capture-context.txt",
        "captureSessionPreflight": artifact_directory
        / "capture-session-preflight.json",
        "lldbExitStatus": artifact_directory / "lldb-exit-status.txt",
        "lldbLog": artifact_directory / "lldb.log",
        "constructorTrace": trace_path,
        "publicTimeline": timeline_path,
        "transitionProgress": artifact_directory / "transition-progress.json",
        "runtimeStdout": artifact_directory / "runtime-stdout.log",
        "runtimeStderr": artifact_directory / "runtime-stderr.log",
    }
    return {
        "backgroundFilterConstructorPublicRenderIntervalLocalMacOSValidationSchemaVersion": RESULT_SCHEMA_VERSION,
        "classification": (
            "prospective exact public sample to ResolvedRecipe blend decision "
            "to Parameters to BackgroundFilter constructor-output to "
            "provider-object join"
        ),
        "inputs": {
            "sourceCommit": commit,
            "preregistration": {
                "path": str(preregistration_path),
                "sha256": sha256(preregistration_path),
            },
            "predecessorArtifactDirectory": str(predecessor_directory),
            **{
                name: {"path": str(path), "sha256": sha256(path)}
                for name, path in primary_paths.items()
            },
        },
        "application": timeline_summary,
        "publicProviderTransfer": transfer,
        "publicTrace": public_summary,
        "constructorProviderJoin": constructor_summary,
        "captureContractPassed": True,
        "authority": {
            "sameProfilePublicParametersConstructionJoinEstablished": True,
            "sameProfilePublicParametersBlendProvenanceEstablished": True,
            "runtimeUnityDirectCopyPathObserved": bool(
                constructor_summary["directCopyBuilderCallCount"]
            ),
            "runtimeWeightedBlendPathObserved": bool(
                constructor_summary["weightedBuilderCallCount"]
            ),
            "allInitializedBackgroundFilterProviderBytesJoinedBitwise": True,
            "completeBackgroundFilterProviderObjectJoinedBitwise": (
                constructor_summary[
                    "allMatchedProvidersHaveFull504ByteConstructorOutput"
                ]
            ),
            "freshMaterialAppearanceGeometryProfileTransferEstablished": False,
            "generalPublicInputConstructionLawEstablished": False,
            "upstreamCropAllocationPolicyEstablished": False,
            "physicalRetinaColorPixelCompositorTransferEstablished": False,
            "independentWalleZeroByteFrameParityEstablished": False,
            "liquidGlassParityEstablished": False,
            "productionShaderAuthorized": False,
        },
        "nextExactGate": (
            "freeze an orthogonal material/appearance/geometry profile and "
            "join its public environment-layer selection and runtime factors "
            "through the proven Parameters recurrence before crop/compositor replay"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--artifact-directory", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        result = validate(arguments.preregistration, arguments.artifact_directory)
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
