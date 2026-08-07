#!/usr/bin/env python3
"""Validate the four-stop live Parameters/constructor/provider join."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_backdrop_margin_case22_provider_public_timeline_join as public_join
import validate_backdrop_margin_case22_provider_object_matrix_minimal_retry2_local_macos_26_6_1 as matrix
import validate_backdrop_margin_case22_provider_public_render_interval_transfer_local_macos_26_6_1 as public
import validate_backdrop_margin_case22_provider_timeline_marker_retina_transfer_local_macos_26_6_1 as retina
import validate_backdrop_margin_case22_provider_timeline_marker_transfer_local_macos_26_6_1 as timeline
import validate_background_filter_constructor_public_render_interval_local_macos_26_6_1 as parked


RESULT_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
TRACE_SCHEMA_VERSION = 1

CAPTURE_PATH = (
    "Analysis/capture_background_filter_constructor_timeline_marker_"
    "direct_join_local_macos_26_6_1_lldb.py"
)
VALIDATOR_PATH = (
    "Analysis/validate_background_filter_constructor_timeline_marker_"
    "direct_join_local_macos_26_6_1.py"
)
RUNNER_PATH = (
    "Analysis/run_background_filter_constructor_timeline_marker_"
    "direct_join_local_macos_26_6_1.sh"
)
CENSUS_FAILURE_RESULT_PATH = (
    "Analysis/background_filter_constructor_timeline_marker_census_"
    "69fe692_failure_result.json"
)
CENSUS_FAILURE_RESULT_SHA256 = (
    "e1bbf34f361434497a94312b03da744e869bc0131f2de82d12d6cdb088946a8d"
)
TRACE_OUTPUT_ENVIRONMENT = (
    "LG_BACKGROUND_FILTER_CONSTRUCTOR_TIMELINE_MARKER_DIRECT_JOIN_TRACE_OUTPUT"
)
MAXIMUM_CHAIN_COUNT = 4096


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


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
    return matrix.mapping(value, label)


def sequence(value: Any, label: str) -> Sequence[Any]:
    return matrix.sequence(value, label)


def validate_preregistration(
    value: Any,
    repository_root: Path,
) -> Mapping[str, Any]:
    preregistration = mapping(value, "direct-join preregistration")
    require(
        preregistration.get(
            "backgroundFilterConstructorTimelineMarkerDirectJoinLocalMacOSPreregistrationSchemaVersion"
        )
        == PREREGISTRATION_SCHEMA_VERSION,
        "preregistration schema differs",
    )
    require(
        preregistration.get("runtimeOutcomeFrozenBeforeDispatch") is None,
        "runtime outcome was not null before dispatch",
    )
    predecessor = mapping(
        preregistration.get("rejectedCensusPredecessor"),
        "rejected census predecessor",
    )
    require(
        predecessor
        == {
            "captureCommit": "69fe692",
            "failureResultPath": CENSUS_FAILURE_RESULT_PATH,
            "failureResultSHA256": CENSUS_FAILURE_RESULT_SHA256,
            "validationExitStatus": 2,
            "frozenGateRemainsFailed": True,
            "retrospectiveExactOneToOneTopologyEstablished": True,
        },
        "rejected census predecessor differs",
    )
    failure_path = repository_root / CENSUS_FAILURE_RESULT_PATH
    require(failure_path.is_file(), "census failure result is absent")
    require(
        sha256(failure_path) == CENSUS_FAILURE_RESULT_SHA256,
        "census failure result hash differs",
    )
    failure = mapping(load_json(failure_path, "census failure"), "census failure")
    failure_authority = mapping(
        failure.get("authority"), "census failure authority"
    )
    require(
        failure_authority.get("prospectiveSameRunAll32ProviderGatePassed")
        is False
        and failure_authority.get(
            "oneBuilderOneConstructorOneProviderCallPerObservedRenderEstablishedRetrospectively"
        )
        is True,
        "census failure authority differs",
    )
    require(
        mapping(preregistration.get("selectionPolicy"), "selection policy")
        == {
            "captureWindow": "strictly after marker 0 through entry of marker 32",
            "chainSelection": "exact builder BL/return, exact constructor BL, then exact provider entry on the same thread",
            "sampleSelection": "last structurally completed chain in each preceding marker interval",
            "markerSelection": "exact main-module function entry and zero-based ordinal only",
            "capturedValuesMaySelectCalls": False,
            "selectionFrozenBeforeDispatch": True,
        },
        "selection policy differs",
    )
    require(
        mapping(preregistration.get("prospectivePredictions"), "predictions")
        == {
            "all32MarkerBatchesAreNonempty": True,
            "everyChainHasExactFourEventSequence": True,
            "everyBuilderOutputMatchesConstructorParametersBitwise": True,
            "everyInitializedConstructorOutputByteMatchesProviderObjectBitwise": True,
            "all32SelectedChainsAreUniqueGlobalPublicSignatureMatches": True,
            "all32SelectedProviderObjectsMatchAll18LoadedPublicFieldsBitwise": True,
            "constructorAndProviderAddressEqualityPredicted": None,
            "paddingByteEqualityAcceptanceGated": False,
            "publicParameters49FieldMatchCountPredicted": None,
        },
        "prospective predictions differ",
    )
    frozen = sequence(
        mapping(
            preregistration.get("frozenImplementation"),
            "frozen implementation",
        ).get("files"),
        "frozen files",
    )
    for value_item in frozen:
        item = mapping(value_item, "frozen file")
        relative = str(item.get("path", ""))
        require(relative.startswith("Analysis/"), "frozen path escapes Analysis")
        path = repository_root / relative
        require(path.is_file(), f"frozen file {relative} is absent")
        require(sha256(path) == item.get("sha256"), f"{relative} hash differs")
    return preregistration


def validate_context(
    path: Path,
    preregistration_path: Path,
    capture_sha256: str,
    validator_sha256: str,
    runner_sha256: str,
) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    require(len(lines) >= 9, "capture context is incomplete")
    require(len(lines[0]) == 40, "capture commit identity differs")
    int(lines[0], 16)
    expected_hashes = (
        timeline.EXPECTED_BINARY_SHA256,
        capture_sha256,
        sha256(preregistration_path),
        timeline.EXPECTED_PREFLIGHT_SHA256,
        validator_sha256,
        runner_sha256,
    )
    for line, expected in zip(lines[1:7], expected_hashes):
        require(line.startswith(expected + "  "), "capture context hash differs")
    environment = dict(line.split("=", 1) for line in lines[7:])
    trace_path = environment.pop(TRACE_OUTPUT_ENVIRONMENT, None)
    require(
        trace_path is not None
        and trace_path.endswith("/background-filter-direct-join-trace.json"),
        "direct-join trace environment differs",
    )
    require(environment == public.EXPECTED_ENVIRONMENT, "capture environment differs")
    return lines[0]


def validate_code_identity(
    trace: Mapping[str, Any],
) -> tuple[
    Mapping[str, Any],
    Mapping[str, Any],
    Mapping[str, Any],
    Mapping[str, Any],
    Mapping[str, Any],
    Mapping[str, Any],
]:
    modules = mapping(trace.get("modules"), "trace modules")
    main_module = mapping(modules.get("main"), "main module")
    design_module = mapping(modules.get("designLibrary"), "DesignLibrary module")
    require(
        design_module.get("uuid") == parked.DESIGN_LIBRARY_UUID
        and design_module.get("valid") is True
        and str(design_module.get("path", "")).endswith("/DesignLibrary"),
        "DesignLibrary identity differs",
    )
    marker = timeline.validate_marker_symbol(
        trace.get("timelineMarkerFunction"), main_module
    )
    constructor, _ = parked.validate_fixed_region(
        trace.get("constructor"),
        design_module,
        parked.CONSTRUCTOR_MODULE_OFFSET,
        parked.CONSTRUCTOR_BYTE_COUNT,
        parked.CONSTRUCTOR_CODE_SHA256,
        "direct-join constructor",
    )
    producer, producer_raw = parked.validate_fixed_region(
        trace.get("constructorProducer"),
        design_module,
        parked.PRODUCER_MODULE_OFFSET,
        parked.PRODUCER_BYTE_COUNT,
        parked.PRODUCER_CODE_SHA256,
        "direct-join constructor producer",
    )
    builder, _ = parked.validate_fixed_region(
        trace.get("resolvedRecipeBuilder"),
        design_module,
        parked.RESOLVED_RECIPE_BUILDER_MODULE_OFFSET,
        parked.RESOLVED_RECIPE_BUILDER_BYTE_COUNT,
        parked.RESOLVED_RECIPE_BUILDER_CODE_SHA256,
        "direct-join Parameters builder",
    )
    builder_caller, builder_caller_raw = parked.validate_fixed_region(
        trace.get("resolvedRecipeBuilderCaller"),
        design_module,
        parked.RESOLVED_RECIPE_BUILDER_CALLER_MODULE_OFFSET,
        parked.RESOLVED_RECIPE_BUILDER_CALLER_BYTE_COUNT,
        parked.RESOLVED_RECIPE_BUILDER_CALLER_CODE_SHA256,
        "direct-join Parameters builder caller",
    )
    constructor_raw = producer_raw[
        parked.CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER :
        parked.CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER + 4
    ]
    require(
        constructor_raw.hex() == parked.CONSTRUCTOR_CALL_INSTRUCTION_HEX
        and public.decode_arm64_bl_target(
            constructor_raw,
            producer["startAddress"] + parked.CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER,
        )
        == constructor["startAddress"],
        "constructor direct branch differs",
    )
    builder_raw = builder_caller_raw[
        parked.RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER :
        parked.RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER + 4
    ]
    require(
        builder_raw.hex() == parked.RESOLVED_RECIPE_BUILDER_CALL_INSTRUCTION_HEX
        and public.decode_arm64_bl_target(
            builder_raw,
            builder_caller["startAddress"]
            + parked.RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER,
        )
        == builder["startAddress"],
        "Parameters builder direct branch differs",
    )
    provider = matrix.validate_symbol(
        trace.get("provider"),
        matrix.EXPECTED_SYMBOLS["provider"],
        matrix.DESIGN_LIBRARY_UUID,
        "direct-join provider",
    )
    return main_module, marker, design_module, producer, builder_caller, provider


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
    require(
        mapping(events[index], f"{label} event")
        == {"eventIndex": index, "kind": kind, "recordIndex": record_index},
        f"{label} event differs",
    )
    return index


def validate_trace(
    trace_value: Any,
) -> tuple[
    dict[str, Any],
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    list[bytes],
    list[bytes],
]:
    trace = mapping(trace_value, "direct-join trace")
    require(
        trace.get(
            "backgroundFilterConstructorTimelineMarkerDirectJoinLocalMacOSLldbTraceSchemaVersion"
        )
        == TRACE_SCHEMA_VERSION,
        "direct-join trace schema differs",
    )
    configuration = mapping(trace.get("configuration"), "trace configuration")
    expected_configuration = {
        "timelineMarkerCount": 33,
        "maximumChainCount": MAXIMUM_CHAIN_COUNT,
        "captureEnabledAfterMarkerIndex": 0,
        "captureDisabledAtMarkerIndex": 32,
        "stopsPerSelectedChain": 4,
        "parametersByteCount": parked.PARAMETERS_BYTE_COUNT,
        "backgroundFilterByteCount": parked.BACKGROUND_FILTER_BYTE_COUNT,
        "expectedControlFlowSequence": [
            "parameters-builder-call",
            "parameters-builder-return",
            "constructor-call",
            "provider-entry",
        ],
    }
    for key, expected in expected_configuration.items():
        require(configuration.get(key) == expected, f"trace {key} differs")
    for key in (
        "capturedParametersUsedForSelection",
        "capturedConstructorOutputUsedForSelection",
        "capturedProviderObjectUsedForSelection",
        "capturedRegisterArgumentUsedForSelection",
        "capturedAddressUsedForSelection",
        "capturedImageUsedForSelection",
        "capturedPixelUsedForSelection",
    ):
        require(configuration.get(key) is False, f"trace {key} differs")

    main_module, marker_symbol, design_module, producer, builder_caller, provider = (
        validate_code_identity(trace)
    )
    breakpoints = sequence(trace.get("breakpoints"), "trace breakpoints")
    expected_breakpoints = {
        "timeline_marker": marker_symbol["symbolStart"],
        "parameters_builder_callsite": (
            builder_caller["startAddress"]
            + parked.RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER
        ),
        "parameters_builder_return": (
            builder_caller["startAddress"]
            + parked.RESOLVED_RECIPE_BUILDER_RETURN_OFFSET_IN_CALLER
        ),
        "constructor_callsite": (
            producer["startAddress"] + parked.CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER
        ),
        "provider_entry": provider["symbolStart"],
    }
    require(len(breakpoints) == len(expected_breakpoints), "breakpoint count differs")
    observed_breakpoints: dict[str, int] = {}
    for value_breakpoint in breakpoints:
        breakpoint = mapping(value_breakpoint, "direct-join breakpoint")
        name = str(breakpoint.get("name", ""))
        require(name in expected_breakpoints, "breakpoint name differs")
        require(name not in observed_breakpoints, "breakpoint name repeats")
        require(
            breakpoint.get("address") == expected_breakpoints[name]
            and breakpoint.get("locationCount") == 1
            and isinstance(breakpoint.get("id"), int),
            f"breakpoint {name} differs",
        )
        observed_breakpoints[name] = int(breakpoint["address"])
    require(observed_breakpoints == expected_breakpoints, "breakpoint set differs")

    events = sequence(trace.get("events"), "direct-join events")
    for index, value_event in enumerate(events):
        require(
            mapping(value_event, f"event {index}").get("eventIndex") == index,
            f"event {index} index differs",
        )
    chains_value = sequence(trace.get("chains"), "direct chains")
    require(
        32 <= len(chains_value) < MAXIMUM_CHAIN_COUNT,
        "direct chain count violates bound",
    )
    chains: list[Mapping[str, Any]] = []
    parameter_payloads: list[bytes] = []
    provider_payloads: list[bytes] = []
    initialized_match_count = 0
    full_match_count = 0
    same_address_count = 0
    for index, value_chain in enumerate(chains_value):
        chain = mapping(value_chain, f"direct chain {index}")
        chains.append(chain)
        require(chain.get("chainIndex") == index, f"chain {index} index differs")
        require(
            isinstance(chain.get("threadID"), int), f"chain {index} thread differs"
        )
        require(chain.get("stage") == "complete", f"chain {index} is incomplete")
        event_indices = [
            validate_event(
                events,
                chain.get("builderCallEventIndex"),
                "parameters-builder-call",
                index,
                f"chain {index} builder call",
            ),
            validate_event(
                events,
                chain.get("builderReturnEventIndex"),
                "parameters-builder-return",
                index,
                f"chain {index} builder return",
            ),
            validate_event(
                events,
                chain.get("constructorCallEventIndex"),
                "constructor-call",
                index,
                f"chain {index} constructor call",
            ),
            validate_event(
                events,
                chain.get("providerEntryEventIndex"),
                "provider-entry",
                index,
                f"chain {index} provider entry",
            ),
        ]
        require(
            event_indices == list(range(event_indices[0], event_indices[0] + 4)),
            f"chain {index} four-event sequence differs",
        )
        parked.validate_frame(
            chain.get("builderCallFrame"),
            design_module,
            builder_caller["startAddress"],
            builder_caller["endAddress"],
            parked.RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER,
            f"chain {index} builder call frame",
        )
        parked.validate_frame(
            chain.get("builderReturnFrame"),
            design_module,
            builder_caller["startAddress"],
            builder_caller["endAddress"],
            parked.RESOLVED_RECIPE_BUILDER_RETURN_OFFSET_IN_CALLER,
            f"chain {index} builder return frame",
        )
        parked.validate_frame(
            chain.get("constructorCallFrame"),
            design_module,
            producer["startAddress"],
            producer["endAddress"],
            parked.CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER,
            f"chain {index} constructor call frame",
        )
        parked.validate_frame(
            chain.get("providerEntryFrame"),
            design_module,
            provider["symbolStart"],
            provider["symbolEnd"],
            0,
            f"chain {index} provider frame",
        )
        builder_address = chain.get("builderOutputAddress")
        constructor_parameters_address = chain.get("constructorParametersAddress")
        constructor_output_address = chain.get("constructorOutputAddress")
        provider_address = chain.get("providerObjectAddress")
        for address, label in (
            (builder_address, "builder output"),
            (constructor_parameters_address, "constructor Parameters"),
            (constructor_output_address, "constructor output"),
            (provider_address, "provider object"),
        ):
            require(isinstance(address, int) and address > 0, f"chain {index} {label} address differs")
        builder_raw = parked.validate_snapshot(
            chain.get("builderOutputAtReturn"),
            int(builder_address),
            parked.PARAMETERS_BYTE_COUNT,
            f"chain {index} builder output",
        )
        constructor_parameters_raw = parked.validate_snapshot(
            chain.get("constructorParametersAtCallsite"),
            int(constructor_parameters_address),
            parked.PARAMETERS_BYTE_COUNT,
            f"chain {index} constructor Parameters",
        )
        require(
            builder_raw == constructor_parameters_raw,
            f"chain {index} builder output differs from constructor Parameters",
        )
        constructor_output_raw = parked.validate_snapshot(
            chain.get("constructorOutputAtProviderEntry"),
            int(constructor_output_address),
            parked.BACKGROUND_FILTER_BYTE_COUNT,
            f"chain {index} constructor output",
        )
        provider_raw = parked.validate_snapshot(
            chain.get("providerObjectAtEntry"),
            int(provider_address),
            parked.BACKGROUND_FILTER_BYTE_COUNT,
            f"chain {index} provider object",
        )
        require(
            parked.initialized_background_filter_bytes(constructor_output_raw)
            == parked.initialized_background_filter_bytes(provider_raw),
            f"chain {index} initialized constructor/provider bytes differ",
        )
        initialized_match_count += 1
        full_match_count += constructor_output_raw == provider_raw
        same_address_count += constructor_output_address == provider_address
        parameter_payloads.append(builder_raw)
        provider_payloads.append(provider_raw)

    markers_value = sequence(trace.get("timelineMarkers"), "timeline markers")
    require(len(markers_value) == 33, "timeline marker count differs")
    markers: list[Mapping[str, Any]] = []
    previous_end = 0
    marker_events: list[int] = []
    for marker_index, value_marker in enumerate(markers_value):
        marker = mapping(value_marker, f"marker {marker_index}")
        markers.append(marker)
        require(
            marker.get("markerIndex") == marker_index
            and marker.get("sampleIndex") == marker_index,
            f"marker {marker_index} identity differs",
        )
        start = marker.get("precedingCompletedChainStartIndex")
        end = marker.get("precedingCompletedChainEndIndexExclusive")
        require(start == previous_end, f"marker {marker_index} start differs")
        require(
            isinstance(end, int) and previous_end <= end <= len(chains),
            f"marker {marker_index} end differs",
        )
        if marker_index == 0:
            require((start, end) == (0, 0), "marker zero contains a chain")
        else:
            require(end > start, f"sample {marker_index} marker batch is empty")
        event_index = validate_event(
            events,
            marker.get("eventIndex"),
            "timeline-marker",
            marker_index,
            f"marker {marker_index}",
        )
        timeline.validate_marker_frame(
            marker.get("frame"),
            marker_symbol,
            marker.get("threadID"),
            f"marker {marker_index} frame",
        )
        marker_events.append(event_index)
        if marker_index > 0:
            prior_marker_event = marker_events[marker_index - 1]
            for chain_index in range(int(start), int(end)):
                chain = chains[chain_index]
                require(
                    prior_marker_event < int(chain["builderCallEventIndex"])
                    and int(chain["providerEntryEventIndex"]) < event_index,
                    f"chain {chain_index} lies outside marker batch {marker_index}",
                )
        previous_end = int(end)
    require(previous_end == len(chains), "chains exist outside marker batches")

    require(trace.get("status") == "finalized", "trace did not finalize")
    require(not sequence(trace.get("failures"), "trace failures"), "trace contains failures")
    require(
        trace.get("finalTimelineMarkerCount") == 33
        and trace.get("finalChainCount") == len(chains)
        and trace.get("finalCompleteChainCount") == len(chains)
        and trace.get("finalPendingThreadCount") == 0
        and trace.get("finalMarkerAssignedChainCount") == len(chains)
        and trace.get("finalEventCount") == len(events)
        and trace.get("finalFailureCount") == 0
        and trace.get("finalMarkerObserved") is True
        and trace.get("finalCaptureEnabled") is False,
        "trace final state differs",
    )
    require(
        mapping(
            trace.get("finalBreakpointEnabledStates"),
            "final breakpoint states",
        )
        == {
            "markerBreakpoint": False,
            "builderCallsiteBreakpoint": False,
            "builderReturnBreakpoint": False,
            "constructorCallsiteBreakpoint": False,
            "providerEntryBreakpoint": False,
        },
        "breakpoints remained enabled",
    )
    return (
        {
            "chainCount": len(chains),
            "threadCount": len({chain["threadID"] for chain in chains}),
            "exactFourEventSequenceCount": len(chains),
            "builderConstructorParametersBitwiseMatchCount": len(chains),
            "initializedConstructorProviderBitwiseMatchCount": initialized_match_count,
            "full504ByteConstructorProviderBitwiseMatchCount": full_match_count,
            "constructorProviderSameAddressCount": same_address_count,
            "ignoredProviderEntryCount": trace.get("finalIgnoredProviderEntryCount"),
            "failureCount": 0,
        },
        markers,
        chains,
        parameter_payloads,
        provider_payloads,
    )


def dynamic_records(timeline_value: Any) -> dict[int, Mapping[str, Any]]:
    value = mapping(timeline_value, "timeline")
    uniforms = mapping(
        value.get("dynamicBackgroundUniforms"), "dynamic background uniforms"
    )
    records = sequence(uniforms.get("records"), "dynamic records")
    require(len(records) == 32, "dynamic record count differs")
    result: dict[int, Mapping[str, Any]] = {}
    for record_value in records:
        record = mapping(record_value, "dynamic record")
        sample_index = record.get("sampleIndex")
        require(
            isinstance(sample_index, int) and 1 <= sample_index <= 32,
            "dynamic sample index differs",
        )
        require(sample_index not in result, "dynamic sample index repeats")
        result[sample_index] = record
    require(set(result) == set(range(1, 33)), "dynamic sample set differs")
    return result


def validate_selected_public_joins(
    timeline_value: Any,
    markers: Sequence[Mapping[str, Any]],
    parameters: Sequence[bytes],
    providers: Sequence[bytes],
) -> dict[str, Any]:
    records = dynamic_records(timeline_value)
    selected: list[dict[str, Any]] = []
    provider_prefixes = [raw[: matrix.OBJECT_BYTE_COUNT] for raw in providers]
    for sample_index in range(1, 33):
        marker = markers[sample_index]
        start = int(marker["precedingCompletedChainStartIndex"])
        end = int(marker["precedingCompletedChainEndIndexExclusive"])
        selected_index = end - 1
        inputs = public_join.input_values(
            records[sample_index], f"dynamic sample {sample_index}"
        )
        words = public_join.signature_words(inputs)
        batch_matches = [
            index
            for index in range(start, end)
            if public_join.signature_match_count(provider_prefixes[index], words)
            == len(public_join.SIGNATURE)
        ]
        global_matches = [
            index
            for index, raw in enumerate(provider_prefixes)
            if public_join.signature_match_count(raw, words)
            == len(public_join.SIGNATURE)
        ]
        require(
            batch_matches == [selected_index] and global_matches == [selected_index],
            f"sample {sample_index} unique last-chain signature differs",
        )
        retina.provider_loaded_fields_match(provider_prefixes[selected_index], inputs)
        selected.append(
            {
                "sampleIndex": sample_index,
                "markerBatchChainStartIndex": start,
                "markerBatchChainEndIndexExclusive": end,
                "markerBatchChainCount": end - start,
                "structurallySelectedChainIndex": selected_index,
                "selectedChainIsLastCompletedBeforeMarker": True,
                "globalSignatureMatchedChainIndices": global_matches,
                "loadedFieldPredictionCount": 18,
                "parametersSHA256": hashlib.sha256(
                    parameters[selected_index]
                ).hexdigest(),
                "providerObjectSHA256": hashlib.sha256(
                    providers[selected_index]
                ).hexdigest(),
            }
        )
    return {
        "openedSampleCount": len(selected),
        "selectedChains": selected,
        "distinctSelectedChainCount": len(
            {record["structurallySelectedChainIndex"] for record in selected}
        ),
        "loadedFieldPredictionCount": 18 * len(selected),
        "selectionUsesCapturedValues": False,
        "all32SamplesAcceptanceGated": True,
    }


def validate(
    preregistration_path: Path,
    artifact_directory: Path,
    repository_root: Path,
) -> dict[str, Any]:
    paths = {
        "captureContext": artifact_directory / "capture-context.txt",
        "preflight": artifact_directory / "capture-session-preflight.json",
        "trace": artifact_directory / "background-filter-direct-join-trace.json",
        "timeline": artifact_directory / "transition-timeline.json",
        "lldbExitStatus": artifact_directory / "lldb-exit-status.txt",
        "lldbLog": artifact_directory / "lldb.log",
        "runtimeStdout": artifact_directory / "runtime-stdout.log",
        "runtimeStderr": artifact_directory / "runtime-stderr.log",
    }
    for label, path in paths.items():
        require(path.is_file(), f"{label} is absent")
    preregistration = validate_preregistration(
        load_json(preregistration_path, "preregistration"), repository_root
    )
    frozen_files = {
        str(mapping(item, "frozen file")["path"]): str(
            mapping(item, "frozen file")["sha256"]
        )
        for item in sequence(
            mapping(
                preregistration.get("frozenImplementation"),
                "frozen implementation",
            ).get("files"),
            "frozen files",
        )
    }
    capture_commit = validate_context(
        paths["captureContext"],
        preregistration_path,
        frozen_files[CAPTURE_PATH],
        frozen_files[VALIDATOR_PATH],
        frozen_files[RUNNER_PATH],
    )
    preflight = public.validate_preflight(load_json(paths["preflight"], "preflight"))
    require(
        paths["lldbExitStatus"].read_text(encoding="utf-8").strip() == "0",
        "LLDB process did not exit zero",
    )
    trace_value = load_json(paths["trace"], "direct-join trace")
    timeline_value = load_json(paths["timeline"], "timeline")
    trace_summary, markers, _chains, parameters, providers = validate_trace(trace_value)
    timeline_summary = matrix.validate_timeline(timeline_value, artifact_directory)
    public_summary = validate_selected_public_joins(
        timeline_value, markers, parameters, providers
    )
    return {
        "backgroundFilterConstructorTimelineMarkerDirectJoinLocalMacOSValidationSchemaVersion": (
            RESULT_SCHEMA_VERSION
        ),
        "classification": (
            "prospective active-Retina value-blind complete Parameters-to-"
            "constructor and initialized constructor-to-provider direct join"
        ),
        "captureCommit": capture_commit,
        "captureContractPassed": True,
        "preflight": preflight,
        "trace": trace_summary,
        "timeline": timeline_summary,
        "publicJoins": public_summary,
        "artifactSHA256": {label: sha256(path) for label, path in paths.items()},
        "authority": {
            "liveParametersBuilderToConstructorJoinedBitwise": True,
            "liveInitializedConstructorOutputToProviderJoinedBitwise": True,
            "sameRunPublicProvider18FieldJoinEstablishedSamples1Through32": True,
            "generalPublicParameters49FieldConstructionLawEstablished": False,
            "upstreamCropAllocationPolicyEstablished": False,
            "physicalRetinaColorPixelCompositorTransferEstablished": False,
            "independentWalleZeroByteFrameParityEstablished": False,
            "liquidGlassParityEstablished": False,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--artifact-directory", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        result = validate(
            arguments.preregistration,
            arguments.artifact_directory,
            arguments.repository_root,
        )
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
