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


RESULT_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
TRACE_SCHEMA_VERSION = 1

EXPECTED_BINARY_SHA256 = (
    "b9cb4068e77a61ff87794fa20a5c273e007f3ee20dd74503b1ab78839104e8dd"
)
EXPECTED_PREFLIGHT_SHA256 = (
    "72e259882f0c9cc5f40e7f12d172dbbe2582da729b0ee176647917b07f172981"
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


def initialized_background_filter_bytes(payload: bytes) -> bytes:
    require(
        len(payload) == BACKGROUND_FILTER_BYTE_COUNT,
        "BackgroundFilter payload width differs",
    )
    return b"".join(
        payload[start:end]
        for start, end in BACKGROUND_FILTER_INITIALIZED_RANGES
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
        event
        == {"eventIndex": index, "kind": kind, "recordIndex": record_index},
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
    predictions = mapping(
        preregistration.get("prospectivePredictions"), "predictions"
    )
    require(
        predictions
        == {
            "allConstructorCallsOnAuthenticatedFunctionThread": True,
            "allConstructorInputsRemainBitwiseUnchanged": True,
            "allConstructorLayerIndicesAreZero": True,
            "allMatchedProviderInitializedBytesHaveSameSampleConstructorOutput": True,
            "allSamplesHaveAtLeastOneConstructorCall": True,
            "completePaddingByteEqualityRequired": False,
            "oneDistinctParametersValuePerMatchedSample": True,
        },
        "prospective predictions differ",
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
        "constructorCaptureStartsAtBackgroundFunctionEntry": True,
        "constructorCaptureEndsAtFinalRenderReturn": True,
        "preRenderAssignmentRule": (
            "all completed unassigned constructor calls are assigned to the "
            "immediately following structural render interval"
        ),
        "capturedParametersUsedForSelection": False,
        "capturedConstructorOutputUsedForSelection": False,
        "capturedProviderObjectUsedForSelection": False,
        "capturedAddressUsedForSelection": False,
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
    call_raw = producer_raw[
        CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER :
        CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER + 4
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

    breakpoints = mapping(trace.get("breakpoints"), "breakpoints")
    for key, expected in (
        ("constructorEntry", constructor["startAddress"]),
        (
            "constructorReturn",
            producer["startAddress"] + CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER,
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
    require(len(intervals) == 32, "interval count differs")
    require(
        32 <= len(constructor_calls) <= MAXIMUM_CONSTRUCTOR_CALLS,
        "constructor call count differs",
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
        require(pre_render or in_render, f"sample {interval_index + 1} has no constructor")
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
        outputs_by_interval[interval_index].append(
            (index, parameters_entry, output)
        )
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
        sorted(public_event_indices + constructor_events) == list(range(len(events))),
        "complete event partition differs",
    )
    require(
        len(events)
        == 2 * len(intervals)
        + 2 * len(provider_calls)
        + 2 * len(constructor_calls),
        "complete event cardinality differs",
    )
    return {
        "constructorCallCount": len(constructor_calls),
        "distinctParametersCount": len(parameter_hashes),
        "matchedProviderCallCount": len(joins),
        "initializedBackgroundFilterByteCount": (
            BACKGROUND_FILTER_INITIALIZED_BYTE_COUNT
        ),
        "paddingByteCount": (
            BACKGROUND_FILTER_BYTE_COUNT
            - BACKGROUND_FILTER_INITIALIZED_BYTE_COUNT
        ),
        "allMatchedProvidersHaveExactSameSampleInitializedConstructorOutput": True,
        "allMatchedProvidersHaveFull504ByteConstructorOutput": all(
            value["full504ByteMatchConstructorCallIndices"] for value in joins
        ),
        "oneDistinctParametersValuePerMatchedSample": True,
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
            mapping(preregistration["frozenImplementation"], "implementation")[
                "files"
            ],
            "frozen files",
        )
    }
    commit = validate_context(
        artifact_directory / "capture-context.txt",
        preregistration_path,
        frozen_files,
    )
    public.validate_preflight(
        load_json(
            artifact_directory / "capture-session-preflight.json", "preflight"
        )
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
            "prospective exact public sample to Parameters to BackgroundFilter "
            "constructor-output to provider-object join"
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
            "decode the 1,025-byte Parameters values against the public input "
            "timeline, then freeze an orthogonal fresh-profile transfer"
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
