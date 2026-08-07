#!/usr/bin/env python3
"""Validate the value-blind live Parameters/BackgroundFilter call census."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

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
    "census_local_macos_26_6_1_lldb.py"
)
VALIDATOR_PATH = (
    "Analysis/validate_background_filter_constructor_timeline_marker_"
    "census_local_macos_26_6_1.py"
)
RUNNER_PATH = (
    "Analysis/run_background_filter_constructor_timeline_marker_"
    "census_local_macos_26_6_1.sh"
)
PARENT_RESULT_PATH = (
    "Analysis/backdrop_margin_case22_provider_timeline_marker_retina_"
    "transfer_local_macos_26_6_1_result.json"
)
PARENT_RESULT_SHA256 = (
    "9ce1e32be073ef9ff0684fe8537d7fd44870f4b6566ac55498a25772bad7bc2e"
)


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
    preregistration = mapping(value, "constructor census preregistration")
    require(
        preregistration.get(
            "backgroundFilterConstructorTimelineMarkerCensusLocalMacOSPreregistrationSchemaVersion"
        )
        == PREREGISTRATION_SCHEMA_VERSION,
        "preregistration schema differs",
    )
    require(
        preregistration.get("runtimeOutcomeFrozenBeforeDispatch") is None,
        "runtime outcome was not null before dispatch",
    )
    require(
        mapping(preregistration.get("parentProviderGate"), "parent provider gate")
        == {
            "captureCommit": "1864f6489baf3209bd78e5769f3ca754a7cc2b6c",
            "resultPath": PARENT_RESULT_PATH,
            "resultSHA256": PARENT_RESULT_SHA256,
            "prospectiveValidationPassed": True,
        },
        "parent provider gate differs",
    )
    parent_path = repository_root / PARENT_RESULT_PATH
    require(parent_path.is_file(), "parent provider result is absent")
    require(sha256(parent_path) == PARENT_RESULT_SHA256, "parent result hash differs")
    parent = mapping(load_json(parent_path, "parent result"), "parent result")
    authority = mapping(parent.get("authority"), "parent result authority")
    parent_capture = mapping(parent.get("capture"), "parent result capture")
    require(
        parent_capture.get("lldbExitStatus") == 0
        and parent_capture.get("validationExitStatus") == 0
        and authority.get(
            "authenticatedMarkerLastCallTemporalJoinEstablishedSamples1Through32"
        )
        is True
        and authority.get(
            "sameProfileAll18PublicProviderLoadedFieldsTransferredProspectively"
        )
        is True,
        "parent provider result did not pass",
    )
    require(
        mapping(preregistration.get("selectionPolicy"), "selection policy")
        == {
            "captureWindow": "strictly after marker 0 through entry of marker 32",
            "constructorCalls": "fixed authenticated producer BL and matching immediate return",
            "parametersBuilderCalls": "fixed authenticated caller BL and matching immediate return",
            "markerSelection": "exact main-module function entry and zero-based ordinal only",
            "capturedValuesMaySelectCalls": False,
            "minimumObservedCallCount": None,
            "selectionFrozenBeforeDispatch": True,
        },
        "selection policy differs",
    )
    require(
        mapping(preregistration.get("captureContract"), "capture contract")
        == {
            "activeRetinaSessionPreflightRequired": True,
            "all33TimelineMarkersRequired": True,
            "parentProviderPredictionsRevalidatedInSameRun": True,
            "allSelectedDirectCallsAndReturnsRetained": True,
            "pendingCallsAtMarkerBoundariesRetainedAsTopologyEvidence": True,
            "noParametersOrBackgroundFilterBytesRead": True,
            "noRegisterArgumentsRead": True,
            "noObservedCallCountPredicted": True,
            "maximumConstructorCalls": 4096,
            "maximumParametersBuilderCalls": 4096,
            "nativeAppleCommandLineToolsOnly": True,
            "zeroToleranceForStructuralIdentity": True,
        },
        "capture contract differs",
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


def validate_region_set(
    trace: Mapping[str, Any],
) -> tuple[
    Mapping[str, Any],
    Mapping[str, Any],
    Mapping[str, Any],
    Mapping[str, Any],
    Mapping[str, Any],
]:
    module = mapping(
        trace.get("constructorCensusDesignLibraryModule"),
        "constructor census DesignLibrary module",
    )
    require(module.get("valid") is True, "DesignLibrary module is invalid")
    require(
        module.get("uuid") == parked.DESIGN_LIBRARY_UUID,
        "DesignLibrary UUID differs",
    )
    require(
        isinstance(module.get("loadAddress"), int) and module["loadAddress"] > 0,
        "DesignLibrary load address differs",
    )
    require(
        str(module.get("path", "")).endswith("/DesignLibrary"),
        "DesignLibrary path differs",
    )
    constructor, _ = parked.validate_fixed_region(
        trace.get("constructorCensusConstructor"),
        module,
        parked.CONSTRUCTOR_MODULE_OFFSET,
        parked.CONSTRUCTOR_BYTE_COUNT,
        parked.CONSTRUCTOR_CODE_SHA256,
        "constructor census constructor",
    )
    producer, producer_raw = parked.validate_fixed_region(
        trace.get("constructorCensusProducer"),
        module,
        parked.PRODUCER_MODULE_OFFSET,
        parked.PRODUCER_BYTE_COUNT,
        parked.PRODUCER_CODE_SHA256,
        "constructor census producer",
    )
    builder, _ = parked.validate_fixed_region(
        trace.get("constructorCensusParametersBuilder"),
        module,
        parked.RESOLVED_RECIPE_BUILDER_MODULE_OFFSET,
        parked.RESOLVED_RECIPE_BUILDER_BYTE_COUNT,
        parked.RESOLVED_RECIPE_BUILDER_CODE_SHA256,
        "constructor census Parameters builder",
    )
    builder_caller, builder_caller_raw = parked.validate_fixed_region(
        trace.get("constructorCensusParametersBuilderCaller"),
        module,
        parked.RESOLVED_RECIPE_BUILDER_CALLER_MODULE_OFFSET,
        parked.RESOLVED_RECIPE_BUILDER_CALLER_BYTE_COUNT,
        parked.RESOLVED_RECIPE_BUILDER_CALLER_CODE_SHA256,
        "constructor census Parameters builder caller",
    )
    constructor_call_raw = producer_raw[
        parked.CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER :
        parked.CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER + 4
    ]
    require(
        constructor_call_raw.hex() == parked.CONSTRUCTOR_CALL_INSTRUCTION_HEX,
        "constructor BL differs",
    )
    require(
        public.decode_arm64_bl_target(
            constructor_call_raw,
            producer["startAddress"] + parked.CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER,
        )
        == constructor["startAddress"],
        "constructor BL target differs",
    )
    builder_call_raw = builder_caller_raw[
        parked.RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER :
        parked.RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER + 4
    ]
    require(
        builder_call_raw.hex() == parked.RESOLVED_RECIPE_BUILDER_CALL_INSTRUCTION_HEX,
        "Parameters builder BL differs",
    )
    require(
        public.decode_arm64_bl_target(
            builder_call_raw,
            builder_caller["startAddress"]
            + parked.RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER,
        )
        == builder["startAddress"],
        "Parameters builder BL target differs",
    )
    return module, constructor, producer, builder, builder_caller


def validate_census_event(
    events: Sequence[Any],
    index: Any,
    kind: str,
    record_index: int,
    marker_index: int,
    label: str,
) -> int:
    require(
        isinstance(index, int) and 0 <= index < len(events),
        f"{label} event index differs",
    )
    require(
        mapping(events[index], f"{label} event")
        == {
            "eventIndex": index,
            "kind": kind,
            "recordIndex": record_index,
            "latestObservedMarkerIndex": marker_index,
        },
        f"{label} event differs",
    )
    return index


def validate_call_sequence(
    calls_value: Any,
    events: Sequence[Any],
    marker_event_indices: Sequence[int],
    module: Mapping[str, Any],
    symbol: Mapping[str, Any],
    entry_offset: int,
    return_offset: int,
    entry_kind: str,
    return_kind: str,
    maximum: int,
    label: str,
) -> tuple[list[Mapping[str, Any]], dict[int, int], dict[int, int]]:
    calls = sequence(calls_value, f"{label} calls")
    require(len(calls) < maximum, f"{label} call bound was reached")
    normalized: list[Mapping[str, Any]] = []
    entries_by_marker = {index: 0 for index in range(32)}
    returns_by_marker = {index: 0 for index in range(33)}
    for index, call_value in enumerate(calls):
        call = mapping(call_value, f"{label} call {index}")
        normalized.append(call)
        require(call.get("callIndex") == index, f"{label} call {index} index differs")
        thread_id = call.get("threadID")
        require(isinstance(thread_id, int), f"{label} call {index} thread differs")
        entry_marker = call.get("entryAfterMarkerIndex")
        return_marker = call.get("returnAfterMarkerIndex")
        require(
            isinstance(entry_marker, int) and 0 <= entry_marker < 32,
            f"{label} call {index} entry marker differs",
        )
        require(
            isinstance(return_marker, int)
            and entry_marker <= return_marker <= 32,
            f"{label} call {index} return marker differs",
        )
        entry_event = validate_census_event(
            events,
            call.get("entryEventIndex"),
            entry_kind,
            index,
            entry_marker,
            f"{label} call {index} entry",
        )
        return_event = validate_census_event(
            events,
            call.get("returnEventIndex"),
            return_kind,
            index,
            return_marker,
            f"{label} call {index} return",
        )
        require(entry_event < return_event, f"{label} call {index} event order differs")
        require(
            marker_event_indices[entry_marker] < entry_event,
            f"{label} call {index} entry precedes its marker",
        )
        if entry_marker < 32:
            require(
                entry_event < marker_event_indices[entry_marker + 1],
                f"{label} call {index} entry crossed its next marker",
            )
        require(
            marker_event_indices[return_marker] < return_event,
            f"{label} call {index} return precedes its marker",
        )
        if return_marker < 32:
            require(
                return_event < marker_event_indices[return_marker + 1],
                f"{label} call {index} return crossed its next marker",
            )
        parked.validate_frame(
            call.get("entryFrame"),
            module,
            symbol["startAddress"],
            symbol["endAddress"],
            entry_offset,
            f"{label} call {index} entry frame",
        )
        parked.validate_frame(
            call.get("returnFrame"),
            module,
            symbol["startAddress"],
            symbol["endAddress"],
            return_offset,
            f"{label} call {index} return frame",
        )
        require(
            isinstance(call.get("selection"), str) and bool(call["selection"]),
            f"{label} call {index} selection label differs",
        )
        entries_by_marker[entry_marker] += 1
        returns_by_marker[return_marker] += 1
    return normalized, entries_by_marker, returns_by_marker


def marker_cumulative_count(histogram: Mapping[int, int], marker_index: int) -> int:
    return sum(count for index, count in histogram.items() if index < marker_index)


def topology_summary(
    constructor_calls: Sequence[Mapping[str, Any]],
    builder_calls: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    intervals: list[dict[str, Any]] = []
    for after_marker in range(32):
        constructors = [
            call
            for call in constructor_calls
            if call["entryAfterMarkerIndex"] == after_marker
            and call["returnAfterMarkerIndex"] == after_marker
        ]
        builders = [
            call
            for call in builder_calls
            if call["entryAfterMarkerIndex"] == after_marker
            and call["returnAfterMarkerIndex"] == after_marker
        ]
        constructor_entries = [int(call["entryEventIndex"]) for call in constructors]
        builder_returns = [int(call["returnEventIndex"]) for call in builders]
        intervals.append(
            {
                "afterMarkerIndex": after_marker,
                "beforeMarkerIndex": after_marker + 1,
                "fullyContainedConstructorCallCount": len(constructors),
                "fullyContainedParametersBuilderCallCount": len(builders),
                "allContainedBuilderReturnsPrecedeAllContainedConstructorCalls": (
                    bool(constructor_entries)
                    and bool(builder_returns)
                    and max(builder_returns) < min(constructor_entries)
                ),
            }
        )
    return {
        "constructorCallCount": len(constructor_calls),
        "parametersBuilderCallCount": len(builder_calls),
        "constructorCallsCrossingMarkerCount": sum(
            call["entryAfterMarkerIndex"] != call["returnAfterMarkerIndex"]
            for call in constructor_calls
        ),
        "parametersBuilderCallsCrossingMarkerCount": sum(
            call["entryAfterMarkerIndex"] != call["returnAfterMarkerIndex"]
            for call in builder_calls
        ),
        "intervals": intervals,
        "intervalsWithConstructorCalls": sum(
            interval["fullyContainedConstructorCallCount"] > 0
            for interval in intervals
        ),
        "intervalsWithParametersBuilderCalls": sum(
            interval["fullyContainedParametersBuilderCallCount"] > 0
            for interval in intervals
        ),
        "intervalsWithBuilderThenConstructorOrdering": sum(
            interval["allContainedBuilderReturnsPrecedeAllContainedConstructorCalls"]
            for interval in intervals
        ),
    }


def validate_census(trace_value: Any) -> dict[str, Any]:
    trace = mapping(trace_value, "constructor census trace")
    require(
        trace.get(
            "backgroundFilterConstructorTimelineMarkerCensusLocalMacOSLldbTraceSchemaVersion"
        )
        == TRACE_SCHEMA_VERSION,
        "constructor census trace schema differs",
    )
    configuration = mapping(trace.get("configuration"), "trace configuration")
    expected_configuration = {
        "constructorCensusEnabledAfterMarkerIndex": 0,
        "constructorCensusDisabledAtMarkerIndex": 32,
        "constructorCensusMaximumCalls": 4096,
        "parametersBuilderCensusMaximumCalls": 4096,
        "constructorCensusSelection": (
            "fixed authenticated producer BL callsite and matching immediate "
            "return, bounded by marker ordinal"
        ),
        "parametersBuilderCensusSelection": (
            "fixed authenticated caller BL callsite and matching immediate "
            "return, bounded by marker ordinal"
        ),
    }
    for key, expected in expected_configuration.items():
        require(configuration.get(key) == expected, f"trace {key} differs")
    for key in (
        "capturedParametersUsedForCensusSelection",
        "capturedBackgroundFilterUsedForCensusSelection",
        "capturedProviderObjectUsedForCensusSelection",
        "capturedRegisterArgumentUsedForCensusSelection",
        "capturedAddressValueUsedForCensusSelection",
        "capturedImageUsedForCensusSelection",
        "capturedPixelUsedForCensusSelection",
    ):
        require(configuration.get(key) is False, f"trace {key} differs")

    module, _constructor, producer, _builder, builder_caller = validate_region_set(
        trace
    )
    breakpoint_values = sequence(
        trace.get("constructorCensusBreakpoints"),
        "constructor census breakpoints",
    )
    expected_breakpoints = {
        "constructor_callsite": (
            producer["startAddress"] + parked.CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER
        ),
        "constructor_return": (
            producer["startAddress"] + parked.CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER
        ),
        "parameters_builder_callsite": (
            builder_caller["startAddress"]
            + parked.RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER
        ),
        "parameters_builder_return": (
            builder_caller["startAddress"]
            + parked.RESOLVED_RECIPE_BUILDER_RETURN_OFFSET_IN_CALLER
        ),
    }
    require(len(breakpoint_values) == 4, "constructor census breakpoint count differs")
    observed_breakpoints: dict[str, int] = {}
    for value in breakpoint_values:
        breakpoint = mapping(value, "constructor census breakpoint")
        name = str(breakpoint.get("name", ""))
        require(name in expected_breakpoints, "constructor census breakpoint name differs")
        require(name not in observed_breakpoints, "constructor census breakpoint repeats")
        require(
            breakpoint.get("address") == expected_breakpoints[name]
            and breakpoint.get("locationCount") == 1
            and isinstance(breakpoint.get("id"), int),
            f"constructor census breakpoint {name} differs",
        )
        observed_breakpoints[name] = int(breakpoint["address"])
    require(observed_breakpoints == expected_breakpoints, "census breakpoints differ")

    events = sequence(trace.get("constructorCensusEvents"), "constructor census events")
    for index, value_event in enumerate(events):
        require(
            mapping(value_event, f"constructor census event {index}").get("eventIndex")
            == index,
            f"constructor census event {index} index differs",
        )
    markers = sequence(trace.get("timelineMarkers"), "timeline markers")
    require(len(markers) == 33, "constructor census marker count differs")
    marker_event_indices: list[int] = []
    for marker_index, value_marker in enumerate(markers):
        marker = mapping(value_marker, f"constructor census marker {marker_index}")
        marker_event_indices.append(
            validate_census_event(
                events,
                marker.get("constructorCensusEventIndex"),
                "timeline-marker-entry",
                marker_index,
                marker_index,
                f"constructor census marker {marker_index}",
            )
        )
    require(
        marker_event_indices == sorted(marker_event_indices),
        "constructor census marker event order differs",
    )

    constructor_calls, constructor_entries, constructor_returns = validate_call_sequence(
        trace.get("constructorCensusCalls"),
        events,
        marker_event_indices,
        module,
        producer,
        parked.CONSTRUCTOR_CALL_OFFSET_IN_PRODUCER,
        parked.CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER,
        "constructor-call",
        "constructor-return",
        parked.MAXIMUM_CONSTRUCTOR_CALLS,
        "constructor census",
    )
    builder_calls, builder_entries, builder_returns = validate_call_sequence(
        trace.get("parametersBuilderCensusCalls"),
        events,
        marker_event_indices,
        module,
        builder_caller,
        parked.RESOLVED_RECIPE_BUILDER_CALL_OFFSET_IN_CALLER,
        parked.RESOLVED_RECIPE_BUILDER_RETURN_OFFSET_IN_CALLER,
        "parameters-builder-call",
        "parameters-builder-return",
        parked.MAXIMUM_PARAMETERS_BUILDER_CALLS,
        "Parameters builder census",
    )
    require(
        len(events) == 33 + 2 * len(constructor_calls) + 2 * len(builder_calls),
        "constructor census event count differs",
    )

    for marker_index, value_marker in enumerate(markers):
        marker = mapping(value_marker, f"constructor census marker {marker_index}")
        expected_constructor_entries = marker_cumulative_count(
            constructor_entries, marker_index
        )
        expected_constructor_returns = marker_cumulative_count(
            constructor_returns, marker_index
        )
        expected_builder_entries = marker_cumulative_count(builder_entries, marker_index)
        expected_builder_returns = marker_cumulative_count(builder_returns, marker_index)
        require(
            marker.get("constructorCensusEntryCountAtMarker")
            == expected_constructor_entries
            and marker.get("constructorCensusReturnCountAtMarker")
            == expected_constructor_returns
            and marker.get("parametersBuilderCensusEntryCountAtMarker")
            == expected_builder_entries
            and marker.get("parametersBuilderCensusReturnCountAtMarker")
            == expected_builder_returns,
            f"constructor census marker {marker_index} cumulative counts differ",
        )
        open_constructor_threads = {
            call["threadID"]
            for call in constructor_calls
            if int(call["entryEventIndex"]) < marker_event_indices[marker_index]
            < int(call["returnEventIndex"])
        }
        open_builder_threads = {
            call["threadID"]
            for call in builder_calls
            if int(call["entryEventIndex"]) < marker_event_indices[marker_index]
            < int(call["returnEventIndex"])
        }
        require(
            marker.get("pendingConstructorCensusThreadCountAtMarker")
            == len(open_constructor_threads)
            and marker.get("pendingParametersBuilderCensusThreadCountAtMarker")
            == len(open_builder_threads),
            f"constructor census marker {marker_index} pending counts differ",
        )

    require(
        trace.get("finalConstructorCensusCallCount") == len(constructor_calls)
        and trace.get("finalConstructorCensusReturnCount") == len(constructor_calls)
        and trace.get("finalParametersBuilderCensusCallCount") == len(builder_calls)
        and trace.get("finalParametersBuilderCensusReturnCount") == len(builder_calls),
        "constructor census final call counts differ",
    )
    require(
        trace.get("finalPendingConstructorCensusThreadCount") == 0
        and trace.get("finalPendingParametersBuilderCensusThreadCount") == 0,
        "constructor census finalized with pending calls",
    )
    require(
        trace.get("finalConstructorCensusEventCount") == len(events)
        and trace.get("finalConstructorCensusEntryCaptureEnabled") is False
        and trace.get("finalConstructorCensusMarkerObserved") is True,
        "constructor census final state differs",
    )
    enabled_states = mapping(
        trace.get("finalConstructorCensusBreakpointEnabledStates"),
        "constructor census final breakpoint states",
    )
    require(
        enabled_states
        == {
            "constructorCallsiteBreakpoint": False,
            "constructorReturnBreakpoint": False,
            "builderCallsiteBreakpoint": False,
            "builderReturnBreakpoint": False,
        },
        "constructor census breakpoints remained enabled",
    )
    return topology_summary(constructor_calls, builder_calls)


def validate(
    preregistration_path: Path,
    artifact_directory: Path,
    repository_root: Path,
) -> dict[str, Any]:
    paths = {
        "captureContext": artifact_directory / "capture-context.txt",
        "preflight": artifact_directory / "capture-session-preflight.json",
        "trace": artifact_directory / "provider-timeline-marker-trace.json",
        "timeline": artifact_directory / "transition-timeline.json",
        "lldbExitStatus": artifact_directory / "lldb-exit-status.txt",
        "lldbLog": artifact_directory / "lldb.log",
        "runtimeStdout": artifact_directory / "runtime-stdout.log",
        "runtimeStderr": artifact_directory / "runtime-stderr.log",
    }
    for label, path in paths.items():
        require(path.is_file(), f"{label} is absent")
    preregistration = validate_preregistration(
        load_json(preregistration_path, "preregistration"),
        repository_root,
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
    capture_commit = timeline.validate_context(
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
    trace_value = load_json(paths["trace"], "trace")
    timeline_value = load_json(paths["timeline"], "timeline")
    provider_summary, markers = retina.validate_provider_trace_structure(trace_value)
    timeline_summary = matrix.validate_timeline(timeline_value, artifact_directory)
    provider_predictions = retina.validate_predictions(
        trace_value,
        timeline_value,
        markers,
    )
    census = validate_census(trace_value)
    return {
        "backgroundFilterConstructorTimelineMarkerCensusLocalMacOSValidationSchemaVersion": (
            RESULT_SCHEMA_VERSION
        ),
        "classification": (
            "prospective value-blind structural census of the exact live "
            "ResolvedRecipe Parameters-builder and BackgroundFilter-constructor "
            "direct-call boundaries on the authenticated Retina provider timeline"
        ),
        "captureCommit": capture_commit,
        "captureContractPassed": True,
        "preflight": preflight,
        "providerTrace": provider_summary,
        "providerPredictions": provider_predictions,
        "timeline": timeline_summary,
        "constructorCensus": census,
        "artifactSHA256": {label: sha256(path) for label, path in paths.items()},
        "authority": {
            "liveParametersBuilderAndConstructorTemporalTopologyMeasured": True,
            "sameRunProviderTransferRevalidated": True,
            "parametersBytesJoinedToConstructor": False,
            "constructorOutputJoinedToProviderObject": False,
            "generalPublicInputConstructionLawEstablished": False,
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
