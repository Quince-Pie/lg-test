#!/usr/bin/env python3
"""Validate the live constructor output captured at its immediate return."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_backdrop_margin_case22_provider_object_matrix_minimal_retry2_local_macos_26_6_1 as matrix
import validate_backdrop_margin_case22_provider_public_render_interval_transfer_local_macos_26_6_1 as public
import validate_background_filter_constructor_public_render_interval_local_macos_26_6_1 as parked
import validate_background_filter_constructor_timeline_marker_direct_join_local_macos_26_6_1 as direct


RESULT_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
TRACE_SCHEMA_VERSION = 1

CAPTURE_PATH = (
    "Analysis/capture_background_filter_constructor_timeline_marker_"
    "return_join_local_macos_26_6_1_lldb.py"
)
VALIDATOR_PATH = (
    "Analysis/validate_background_filter_constructor_timeline_marker_"
    "return_join_local_macos_26_6_1.py"
)
RUNNER_PATH = (
    "Analysis/run_background_filter_constructor_timeline_marker_"
    "return_join_local_macos_26_6_1.sh"
)
DIRECT_FAILURE_RESULT_PATH = (
    "Analysis/background_filter_constructor_timeline_marker_direct_join_"
    "7d2f8ab_failure_result.json"
)
DIRECT_FAILURE_RESULT_SHA256 = (
    "b9aaccf97ee9883ee532551909a81b171c5a69315c8b34193157fc3d042cb1ea"
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
    return direct.load_json(path, label)


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    return matrix.mapping(value, label)


def sequence(value: Any, label: str) -> Sequence[Any]:
    return matrix.sequence(value, label)


def validate_preregistration(
    value: Any,
    repository_root: Path,
) -> Mapping[str, Any]:
    preregistration = mapping(value, "constructor-return preregistration")
    require(
        preregistration.get(
            "backgroundFilterConstructorTimelineMarkerReturnJoinLocalMacOSPreregistrationSchemaVersion"
        )
        == PREREGISTRATION_SCHEMA_VERSION,
        "preregistration schema differs",
    )
    require(
        preregistration.get("runtimeOutcomeFrozenBeforeDispatch") is None,
        "runtime outcome was not null before dispatch",
    )
    predecessor = mapping(
        preregistration.get("rejectedDirectJoinPredecessor"),
        "rejected direct-join predecessor",
    )
    require(
        predecessor
        == {
            "captureCommit": "7d2f8ab",
            "failureResultPath": DIRECT_FAILURE_RESULT_PATH,
            "failureResultSHA256": DIRECT_FAILURE_RESULT_SHA256,
            "validationExitStatus": 2,
            "frozenGateRemainsFailed": True,
            "builderConstructorAndPublicProviderJoinsPassedRetrospectively": True,
            "constructorOutputWasObservedAfterTemporaryLifetime": True,
        },
        "rejected direct-join predecessor differs",
    )
    failure_path = repository_root / DIRECT_FAILURE_RESULT_PATH
    require(failure_path.is_file(), "direct-join failure result is absent")
    require(
        sha256(failure_path) == DIRECT_FAILURE_RESULT_SHA256,
        "direct-join failure result hash differs",
    )
    failure = mapping(load_json(failure_path, "direct-join failure"), "failure")
    authority = mapping(failure.get("authority"), "failure authority")
    require(
        authority.get("prospectiveInitializedConstructorProviderJoinPassed")
        is False
        and authority.get(
            "liveBuilderOutputToConstructorInputJoinedBitwiseRetrospectively"
        )
        is True
        and authority.get("constructorReturnValueCapturedWithinLifetime") is False,
        "direct-join failure authority differs",
    )
    require(
        mapping(preregistration.get("selectionPolicy"), "selection policy")
        == {
            "captureWindow": "strictly after marker 0 through entry of marker 32",
            "chainSelection": "exact builder BL/return, exact constructor BL/immediate return, then exact provider entry on the same thread",
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
            "everyChainHasExactFiveEventSequence": True,
            "everyBuilderOutputMatchesConstructorParametersBitwise": True,
            "everyInitializedConstructorReturnByteMatchesProviderObjectBitwise": True,
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


def validate_return_capture(trace_value: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    trace = mapping(trace_value, "constructor-return trace")
    require(
        trace.get(
            "backgroundFilterConstructorTimelineMarkerReturnJoinLocalMacOSLldbTraceSchemaVersion"
        )
        == TRACE_SCHEMA_VERSION,
        "constructor-return trace schema differs",
    )
    configuration = mapping(trace.get("configuration"), "trace configuration")
    require(configuration.get("stopsPerSelectedChain") == 5, "stop count differs")
    require(
        configuration.get("expectedControlFlowSequence")
        == [
            "parameters-builder-call",
            "parameters-builder-return",
            "constructor-call",
            "constructor-return",
            "provider-entry",
        ],
        "five-event sequence differs",
    )
    require(
        configuration.get("constructorOutputSnapshotTiming")
        == "exact producer instruction immediately after constructor BL"
        and configuration.get("constructorOutputAtProviderEntryUsedForJoin") is False
        and configuration.get("capturedConstructorReturnValueUsedForSelection")
        is False,
        "constructor-return capture contract differs",
    )
    _main, _marker, design, producer, _caller, _provider = direct.validate_code_identity(
        trace
    )
    breakpoints = sequence(trace.get("breakpoints"), "trace breakpoints")
    return_breakpoints = [
        mapping(value, "constructor-return breakpoint")
        for value in breakpoints
        if mapping(value, "breakpoint").get("name") == "constructor_return"
    ]
    expected_return_address = (
        producer["startAddress"] + parked.CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER
    )
    require(
        len(breakpoints) == 6
        and len(return_breakpoints) == 1
        and return_breakpoints[0].get("address") == expected_return_address
        and return_breakpoints[0].get("locationCount") == 1,
        "constructor-return breakpoint differs",
    )
    events = sequence(trace.get("events"), "trace events")
    chains = sequence(trace.get("chains"), "direct chains")
    require(len(chains) >= 32, "direct chain count differs")
    return_payloads: list[bytes] = []
    for index, value_chain in enumerate(chains):
        chain = mapping(value_chain, f"direct chain {index}")
        indices = [
            direct.validate_event(
                events,
                chain.get("builderCallEventIndex"),
                "parameters-builder-call",
                index,
                f"chain {index} builder call",
            ),
            direct.validate_event(
                events,
                chain.get("builderReturnEventIndex"),
                "parameters-builder-return",
                index,
                f"chain {index} builder return",
            ),
            direct.validate_event(
                events,
                chain.get("constructorCallEventIndex"),
                "constructor-call",
                index,
                f"chain {index} constructor call",
            ),
            direct.validate_event(
                events,
                chain.get("constructorReturnEventIndex"),
                "constructor-return",
                index,
                f"chain {index} constructor return",
            ),
            direct.validate_event(
                events,
                chain.get("providerEntryEventIndex"),
                "provider-entry",
                index,
                f"chain {index} provider entry",
            ),
        ]
        require(
            indices == list(range(indices[0], indices[0] + 5)),
            f"chain {index} exact five-event order differs",
        )
        parked.validate_frame(
            chain.get("constructorReturnFrame"),
            design,
            producer["startAddress"],
            producer["endAddress"],
            parked.CONSTRUCTOR_RETURN_OFFSET_IN_PRODUCER,
            f"chain {index} constructor return frame",
        )
        output_address = chain.get("constructorOutputAddress")
        require(
            isinstance(output_address, int) and output_address > 0,
            f"chain {index} constructor output address differs",
        )
        return_payloads.append(
            parked.validate_snapshot(
                chain.get("constructorOutputAtReturn"),
                output_address,
                parked.BACKGROUND_FILTER_BYTE_COUNT,
                f"chain {index} constructor output at return",
            )
        )
        require(
            chain.get("constructorOutputAtProviderEntry") is None,
            f"chain {index} retained a late constructor snapshot",
        )
    require(
        trace.get("finalConstructorReturnSnapshotCount") == len(chains)
        and trace.get("finalConstructorReturnBreakpointEnabled") is False,
        "constructor-return final state differs",
    )
    return (
        {
            "constructorReturnSnapshotCount": len(return_payloads),
            "constructorReturnBreakpointAddress": expected_return_address,
            "constructorOutputSnapshotTiming": configuration[
                "constructorOutputSnapshotTiming"
            ],
        },
        project_to_four_stop_contract(trace),
    )


def project_to_four_stop_contract(trace_value: Mapping[str, Any]) -> dict[str, Any]:
    """Project away the extra stop while preserving its captured output bytes."""

    projected = copy.deepcopy(dict(trace_value))
    configuration = dict(mapping(projected.get("configuration"), "configuration"))
    configuration["stopsPerSelectedChain"] = 4
    configuration["expectedControlFlowSequence"] = [
        "parameters-builder-call",
        "parameters-builder-return",
        "constructor-call",
        "provider-entry",
    ]
    projected["configuration"] = configuration
    projected["breakpoints"] = [
        value
        for value in sequence(projected.get("breakpoints"), "breakpoints")
        if mapping(value, "breakpoint").get("name") != "constructor_return"
    ]

    original_events = sequence(projected.get("events"), "events")
    retained_events: list[dict[str, Any]] = []
    index_map: dict[int, int] = {}
    for old_index, value_event in enumerate(original_events):
        event = dict(mapping(value_event, f"event {old_index}"))
        if event.get("kind") == "constructor-return":
            continue
        new_index = len(retained_events)
        index_map[old_index] = new_index
        event["eventIndex"] = new_index
        retained_events.append(event)
    projected["events"] = retained_events
    for value_chain in sequence(projected.get("chains"), "chains"):
        chain = mapping(value_chain, "chain")
        for key in (
            "builderCallEventIndex",
            "builderReturnEventIndex",
            "constructorCallEventIndex",
            "providerEntryEventIndex",
        ):
            chain[key] = index_map[int(chain[key])]
        chain["constructorOutputAtProviderEntry"] = copy.deepcopy(
            chain["constructorOutputAtReturn"]
        )
    for value_marker in sequence(projected.get("timelineMarkers"), "markers"):
        marker = mapping(value_marker, "marker")
        marker["eventIndex"] = index_map[int(marker["eventIndex"])]
    projected["finalEventCount"] = len(retained_events)
    return projected


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
    capture_commit = direct.validate_context(
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
    trace_value = load_json(paths["trace"], "constructor-return trace")
    timeline_value = load_json(paths["timeline"], "timeline")
    return_summary, projected_trace = validate_return_capture(trace_value)
    trace_summary, markers, _chains, parameters, providers = direct.validate_trace(
        projected_trace
    )
    trace_summary.update(return_summary)
    timeline_summary = matrix.validate_timeline(timeline_value, artifact_directory)
    public_summary = direct.validate_selected_public_joins(
        timeline_value, markers, parameters, providers
    )
    return {
        "backgroundFilterConstructorTimelineMarkerReturnJoinLocalMacOSValidationSchemaVersion": (
            RESULT_SCHEMA_VERSION
        ),
        "classification": (
            "prospective active-Retina value-blind complete Parameters-to-"
            "constructor and immediate-return constructor-to-provider join"
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
            "liveInitializedConstructorReturnToProviderJoinedBitwise": True,
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
