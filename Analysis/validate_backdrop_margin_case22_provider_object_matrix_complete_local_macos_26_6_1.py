#!/usr/bin/env python3
"""Validate both stages of the unlocked complete provider capture.

Structural, session, code, object, and return joins fail closed.  The two
output-dependent hypotheses are reported as results instead of being used to
change the validator: reproduction of the historical selected return and
opening of the positive provider branch across the complete matrix.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_backdrop_margin_case22_provider_local_macos_26_6_1 as selected
import validate_backdrop_margin_case22_provider_object_matrix_minimal_retry2_local_macos_26_6_1 as allocation


RESULT_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
COMPLETE_TRACE_SCHEMA_VERSION = 1
EXPECTED_BINARY_SHA256 = (
    "b9cb4068e77a61ff87794fa20a5c273e007f3ee20dd74503b1ab78839104e8dd"
)
EXPECTED_COMPLETE_CAPTURE_SHA256 = (
    "05e12987979401fa79615d86fc119084a5126aeac1ba3b79b44eeaf80988b9b1"
)
EXPECTED_PREFLIGHT_SHA256 = (
    "72e259882f0c9cc5f40e7f12d172dbbe2582da729b0ee176647917b07f172981"
)
EXPECTED_SELECTED_RETURN = "0000006002a22a40"
EXPECTED_ENVIRONMENT = {
    "LG_GEOMETRY_POLICY": "0",
    **allocation.EXPECTED_ENVIRONMENT,
}
EXPECTED_PREFLIGHT = {
    "backingScaleFactor": 2,
    "displayActive": True,
    "displayAsleep": False,
    "expectedBackingScaleFactor": 2,
    "expectedLogicalPoints": [1728, 1117],
    "expectedPhysicalPixels": [3456, 2234],
    "localRetinaCaptureSessionPreflightSchemaVersion": 1,
    "logicalPoints": [1728, 1117],
    "passed": True,
    "physicalPixels": [3456, 2234],
    "sessionLocked": False,
    "sessionOnConsole": True,
}
CALLER_CALL_OFFSET = 0x1680
CALLER_RETURN_OFFSET = 0x1684
GROUP_RETURN_OFFSET = 0x26C
WRAPPER_RETURN_OFFSET = 0x68
MAXIMUM_CALL_COUNT = 4096
GAUSSIAN_INPUT_OFFSET = 0x88
GAUSSIAN_GATE_OFFSET = 0x90


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    return allocation.mapping(value, label)


def sequence(value: Any, label: str) -> Sequence[Any]:
    return allocation.sequence(value, label)


def load_json(path: Path, label: str) -> Any:
    return allocation.load_json(path, label)


def validate_preregistration(
    value: Any, repository_root: Path
) -> Mapping[str, Any]:
    preregistration = mapping(value, "complete preregistration")
    require(
        preregistration.get(
            "backdropMarginCase22ProviderObjectMatrixCompleteLocalMacOSPreregistrationSchemaVersion"
        )
        == PREREGISTRATION_SCHEMA_VERSION,
        "complete preregistration schema differs",
    )
    require(
        preregistration.get("runtimeOutcomeFrozenBeforeDispatch") is None,
        "runtime outcome was not unknown before dispatch",
    )
    complete = mapping(
        preregistration.get("completeCapture"), "complete capture contract"
    )
    require(
        complete.get("sha256") == EXPECTED_COMPLETE_CAPTURE_SHA256,
        "complete capture hash differs",
    )
    require(
        sha256(repository_root / str(complete.get("path")))
        == EXPECTED_COMPLETE_CAPTURE_SHA256,
        "complete capture source bytes differ",
    )
    preflight = mapping(
        preregistration.get("nativeSessionPreflight"),
        "native session preflight contract",
    )
    require(
        preflight.get("sha256") == EXPECTED_PREFLIGHT_SHA256,
        "preflight hash differs",
    )
    require(
        sha256(repository_root / str(preflight.get("path")))
        == EXPECTED_PREFLIGHT_SHA256,
        "preflight source bytes differ",
    )
    runner = mapping(preregistration.get("nativeRunner"), "native runner")
    require(
        sha256(repository_root / str(runner.get("path")))
        == runner.get("sha256"),
        "native runner source bytes differ",
    )
    for key in (
        "directNativeCommandLineTools",
        "preflightImmediatelyBeforeEachStage",
        "secondStageIndependentOfFirstStageValue",
        "trackedRepositoryMustBeClean",
    ):
        require(runner.get(key) is True, f"native runner field {key} differs")
    stages = sequence(
        preregistration.get("unconditionalTwoStageDispatch"),
        "unconditional dispatch",
    )
    require(len(stages) == 2, "unconditional dispatch stage count differs")
    require(
        mapping(stages[0], "selected stage").get(
            "expectedReturnRawLittleEndianHex"
        )
        == EXPECTED_SELECTED_RETURN,
        "selected reproduction expectation differs",
    )
    require(
        mapping(stages[1], "complete stage").get(
            "dispatchRegardlessOfFirstStageOutcome"
        )
        is True,
        "complete stage is conditional",
    )
    return preregistration


def validate_preflight(value: Any, label: str) -> dict[str, Any]:
    report = mapping(value, label)
    for key, expected in EXPECTED_PREFLIGHT.items():
        require(report.get(key) == expected, f"{label} field {key} differs")
    require(
        report.get("classification")
        == "fail-closed native macOS presentation-session preflight",
        f"{label} classification differs",
    )
    return dict(report)


def validate_context(
    path: Path,
    preregistration_path: Path,
    expected_capture_sha256: str,
    trace_environment_key: str,
) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    require(len(lines) >= 7, "capture context is incomplete")
    require(len(lines[0]) == 40, "capture commit identity differs")
    int(lines[0], 16)
    require(
        lines[1].startswith(EXPECTED_BINARY_SHA256 + "  "),
        "binary context hash differs",
    )
    require(
        lines[2].startswith(expected_capture_sha256 + "  "),
        "capture source context hash differs",
    )
    require(
        lines[3].startswith(sha256(preregistration_path) + "  "),
        "preregistration context hash differs",
    )
    require(
        lines[4].startswith(EXPECTED_PREFLIGHT_SHA256 + "  "),
        "preflight source context hash differs",
    )
    environment = dict(line.split("=", 1) for line in lines[5:])
    trace_output = environment.pop(trace_environment_key, None)
    require(
        trace_output is not None and trace_output.endswith(".json"),
        "trace output environment differs",
    )
    require(environment == EXPECTED_ENVIRONMENT, "capture environment differs")
    return lines[0]


def validate_process_transport(artifact_directory: Path) -> None:
    require(
        (artifact_directory / "lldb-exit-status.txt").read_text(
            encoding="utf-8"
        )
        == "0\n",
        "LLDB exit status differs",
    )
    log = (artifact_directory / "lldb.log").read_text(encoding="utf-8")
    require("exited with status = 0" in log, "application did not exit zero")
    require("Traceback" not in log, "LLDB log contains a traceback")
    require("error: Aborting reading of commands" not in log, "LLDB command failed")


def validate_complete_trace(value: Any) -> dict[str, Any]:
    trace = mapping(value, "complete trace")
    configuration = mapping(trace.get("configuration"), "trace configuration")
    require(
        trace.get(
            "case22ProviderObjectMatrixCompleteLocalMacOSLldbTraceSchemaVersion"
        )
        == COMPLETE_TRACE_SCHEMA_VERSION,
        "complete trace schema differs",
    )
    require(
        trace.get(
            "case22ProviderObjectMatrixMinimalLocalMacOSLldbTraceSchemaVersion"
        )
        == 1,
        "inherited trace schema differs",
    )
    for key, expected in {
        "importedBeforeProcessLaunch": True,
        "pendingCallerEntryBootstrap": True,
        "capturesFirstExactCallerInvocation": True,
        "capturesEveryCase22IterationUntilCallerReturn": True,
        "previousFirstCaseDisarmRemoved": True,
        "perSelectedCallerStopCountFormula": (
            "2 + 4 * case22ProviderCallCount"
        ),
        "perSelectedCallMaximumStopCount": 2 + 4 * MAXIMUM_CALL_COUNT,
        "activeBreakpointCountPerSelectedCall": 6,
        "unrelatedWrapperOrProviderCallbacksArmed": False,
        "maximumCallCount": MAXIMUM_CALL_COUNT,
    }.items():
        require(configuration.get(key) == expected, f"configuration {key} differs")
    for key in (
        "capturedObjectUsedForSelection",
        "capturedReturnUsedForSelection",
        "capturedMarginUsedForSelection",
        "capturedCropUsedForSelection",
        "capturedImageUsedForSelection",
        "capturedPixelUsedForSelection",
        "capturedValueUsedToSelectNewBound",
    ):
        require(configuration.get(key) is False, f"configuration {key} differs")

    modules = mapping(trace.get("modules"), "trace modules")
    require(
        mapping(modules.get("swiftUICore"), "SwiftUICore module").get("uuid")
        == allocation.SWIFTUICORE_UUID,
        "SwiftUICore UUID differs",
    )
    require(
        mapping(modules.get("designLibrary"), "DesignLibrary module").get(
            "uuid"
        )
        == allocation.DESIGN_LIBRARY_UUID,
        "DesignLibrary UUID differs",
    )
    caller = allocation.validate_symbol(
        trace.get("caller"),
        allocation.EXPECTED_SYMBOLS["caller"],
        allocation.SWIFTUICORE_UUID,
        "caller",
    )
    group = allocation.validate_symbol(
        trace.get("group"),
        allocation.EXPECTED_SYMBOLS["group"],
        allocation.SWIFTUICORE_UUID,
        "Group",
    )
    wrapper = allocation.validate_symbol(
        trace.get("wrapper"),
        allocation.EXPECTED_SYMBOLS["wrapper"],
        allocation.SWIFTUICORE_UUID,
        "wrapper",
    )
    provider = allocation.validate_symbol(
        trace.get("provider"),
        allocation.EXPECTED_SYMBOLS["provider"],
        allocation.DESIGN_LIBRARY_UUID,
        "provider",
    )
    require(caller.get("symbolOffset") == 0, "caller bootstrap offset differs")
    caller_code = bytes.fromhex(str(caller.get("hex", "")))
    require(
        caller_code[CALLER_CALL_OFFSET : CALLER_CALL_OFFSET + 4].hex()
        == "5526e997",
        "caller Group call instruction differs",
    )
    bootstrap = mapping(trace.get("bootstrap"), "bootstrap")
    require(bootstrap.get("observed") is True, "bootstrap was not observed")
    allocation.validate_frame(
        bootstrap.get("frame"), caller, 0, "bootstrap caller entry"
    )
    require(
        bootstrap.get("callerEntryPC") == caller["symbolStart"],
        "bootstrap caller entry PC differs",
    )
    require(
        bootstrap.get("callerCallsiteAddress")
        == caller["symbolStart"] + CALLER_CALL_OFFSET,
        "bootstrap caller callsite differs",
    )
    require(
        bootstrap.get("callerReturnAddress")
        == caller["symbolStart"] + CALLER_RETURN_OFFSET,
        "bootstrap caller return differs",
    )

    breakpoints = sequence(trace.get("breakpoints"), "trace breakpoints")
    breakpoint_names = [
        mapping(value, "breakpoint").get("name") for value in breakpoints
    ]
    require(
        len(breakpoints) == 7
        and len(set(breakpoint_names)) == 7
        and set(breakpoint_names)
        == {
            "bootstrap_caller_entry",
            "selected_callsite",
            "wrapper_entry",
            "provider_entry",
            "provider_return",
            "group_return",
            "selected_caller_return",
        },
        "trace breakpoint names differ",
    )

    calls = sequence(trace.get("calls"), "provider calls")
    selected_calls = sequence(
        trace.get("selectedCallerCalls"), "selected caller calls"
    )
    require(0 < len(calls) < MAXIMUM_CALL_COUNT, "provider call count differs")
    require(selected_calls, "selected caller set is empty")
    owned_indices: list[int] = []
    for selected_index, value in enumerate(selected_calls):
        selected_call = mapping(value, f"selected caller {selected_index}")
        indices = list(
            sequence(
                selected_call.get("providerCallIndices"),
                f"selected caller {selected_index} provider indices",
            )
        )
        require(
            selected_call.get("selectedCallerIndex") == selected_index,
            f"selected caller {selected_index} index differs",
        )
        selected_thread_id = selected_call.get("threadID")
        require(
            isinstance(selected_thread_id, int),
            f"selected caller {selected_index} thread differs",
        )
        require(indices, f"selected caller {selected_index} has no provider call")
        require(
            selected_call.get("providerCallCount") == len(indices),
            f"selected caller {selected_index} provider count differs",
        )
        require(
            selected_call.get("allProviderCallsCompleted") is True,
            f"selected caller {selected_index} is incomplete",
        )
        allocation.validate_frame(
            selected_call.get("callsiteFrame"),
            caller,
            CALLER_CALL_OFFSET,
            f"selected caller {selected_index} callsite",
        )
        allocation.validate_frame(
            selected_call.get("callerReturnFrame"),
            caller,
            CALLER_RETURN_OFFSET,
            f"selected caller {selected_index} return",
        )
        require(
            indices == list(range(indices[0], indices[0] + len(indices))),
            f"selected caller {selected_index} provider indices are not contiguous",
        )
        for call_offset, call_index in enumerate(indices):
            require(
                isinstance(call_index, int) and 0 <= call_index < len(calls),
                f"selected caller {selected_index} provider index differs",
            )
            call = mapping(calls[call_index], f"provider call {call_index}")
            require(
                call.get("selectedCallerIndex") == selected_index,
                f"provider call {call_index} owner differs",
            )
            require(
                call.get("threadID") == selected_thread_id,
                f"provider call {call_index} owner thread differs",
            )
            require(
                call.get("providerCallIndexWithinSelectedCaller") == call_offset,
                f"provider call {call_index} owner-relative index differs",
            )
        owned_indices.extend(indices)
    require(
        owned_indices == list(range(len(calls)))
        and len(set(owned_indices)) == len(calls),
        "provider calls are not an exact selected-caller partition",
    )

    object_payloads: list[bytes] = []
    return_words: list[str] = []
    positive_gate_count = 0
    positive_return_count = 0
    for index, value in enumerate(calls):
        call = mapping(value, f"provider call {index}")
        require(call.get("callIndex") == index, f"provider call {index} index differs")
        wrapper_address = call.get("wrapperObjectAddress")
        provider_address = call.get("providerObjectAddress")
        require(
            isinstance(wrapper_address, int) and isinstance(provider_address, int),
            f"provider call {index} object address differs",
        )
        require(
            provider_address == wrapper_address + 16,
            f"provider call {index} object offset differs",
        )
        require(
            call.get("providerObjectOffsetFromWrapper") == 16,
            f"provider call {index} recorded object offset differs",
        )
        wrapper_payload = allocation.validate_snapshot(
            call.get("wrapperEntryObject"),
            provider_address,
            f"provider call {index} wrapper object",
        )
        entry_payload = allocation.validate_snapshot(
            call.get("providerEntryObject"),
            provider_address,
            f"provider call {index} entry object",
        )
        return_payload = allocation.validate_snapshot(
            call.get("returnObject"),
            provider_address,
            f"provider call {index} return object",
        )
        require(
            wrapper_payload == entry_payload == return_payload,
            f"provider call {index} object changed",
        )
        require(
            call.get("providerEntryMatchesWrapperObjectBitwise") is True
            and call.get("objectChanged") is False,
            f"provider call {index} object join differs",
        )
        raw_v0 = str(call.get("returnV0RawLittleEndianHex", ""))
        raw_f64 = str(call.get("returnF64RawLittleEndianHex", ""))
        group_v0 = str(call.get("groupReturnV0RawLittleEndianHex", ""))
        require(
            len(bytes.fromhex(raw_v0)) == 16
            and raw_v0[:16] == raw_f64
            and raw_v0 == group_v0,
            f"provider call {index} return join differs",
        )
        require(
            call.get("providerReturnMatchesGroupBitwise") is True,
            f"provider call {index} Group join flag differs",
        )
        allocation.validate_frame(
            call.get("wrapperEntryFrame"), wrapper, 0, f"provider call {index} wrapper entry"
        )
        allocation.validate_frame(
            call.get("providerEntryFrame"), provider, 0, f"provider call {index} provider entry"
        )
        allocation.validate_frame(
            call.get("wrapperReturnFrame"),
            wrapper,
            WRAPPER_RETURN_OFFSET,
            f"provider call {index} wrapper return",
        )
        allocation.validate_frame(
            call.get("groupCallerFrame"),
            group,
            GROUP_RETURN_OFFSET,
            f"provider call {index} Group caller",
        )
        allocation.validate_frame(
            call.get("groupReturnFrame"),
            group,
            GROUP_RETURN_OFFSET,
            f"provider call {index} Group return",
        )
        gaussian_input = struct.unpack_from(
            "<f", entry_payload, GAUSSIAN_INPUT_OFFSET
        )[0]
        gaussian_gate = struct.unpack_from(
            "<d", entry_payload, GAUSSIAN_GATE_OFFSET
        )[0]
        if gaussian_input > 0.0 and gaussian_gate > 0.0:
            positive_gate_count += 1
        return_value = struct.unpack("<d", bytes.fromhex(raw_f64))[0]
        if math.isfinite(return_value) and return_value > 0.0:
            positive_return_count += 1
        object_payloads.append(entry_payload)
        return_words.append(raw_f64)

    require(trace.get("status") == "finalized", "trace did not finalize")
    require(
        trace.get("statusBeforeFinalization")
        == "between-complete-selected-callers",
        "trace did not finish between selected callers",
    )
    require(not sequence(trace.get("failures"), "trace failures"), "trace has failures")
    for key in (
        "finalCallCount",
        "finalProviderEnteredCallCount",
        "finalReturnedCallCount",
        "finalGroupLinkedCallCount",
        "finalUnchangedObjectCount",
    ):
        require(trace.get(key) == len(calls), f"trace {key} differs")
    require(
        trace.get("finalSelectedCallerCount") == len(selected_calls),
        "final selected caller count differs",
    )
    require(
        trace.get("finalActiveSelectedCallerCount") == 0
        and trace.get("finalPendingThreadCount") == 0,
        "trace retained active calls",
    )
    require(trace.get("finalFailureCount") == 0, "trace failure count differs")
    provider_counts = [
        mapping(value, "selected caller")["providerCallCount"]
        for value in selected_calls
    ]
    require(
        trace.get("finalMinimumProviderCallsPerSelectedCaller")
        == min(provider_counts)
        and trace.get("finalMaximumProviderCallsPerSelectedCaller")
        == max(provider_counts),
        "final provider-per-caller extrema differ",
    )
    require(trace.get("finalBootstrapObserved") is True, "final bootstrap flag differs")

    distinct_objects = len(set(object_payloads))
    distinct_returns = len(set(return_words))
    contract_passed = (
        distinct_objects >= 2
        and distinct_returns >= 2
        and positive_gate_count >= 1
        and positive_return_count >= 1
    )
    return {
        "callCount": len(calls),
        "selectedCallerCount": len(selected_calls),
        "minimumProviderCallsPerSelectedCaller": min(provider_counts),
        "maximumProviderCallsPerSelectedCaller": max(provider_counts),
        "multipleProviderCallSelectedCallerCount": sum(
            count > 1 for count in provider_counts
        ),
        "distinctProviderObjectCount": distinct_objects,
        "distinctProviderReturnCount": distinct_returns,
        "providerReturnWords": sorted(set(return_words)),
        "positiveGaussianInputAndGateObjectCount": positive_gate_count,
        "finitePositiveProviderReturnCount": positive_return_count,
        "completeProcessAndAllIterationIntegrityPassed": True,
        "positiveBranchContractPassed": contract_passed,
    }


def artifact_hashes(directory: Path, trace_name: str) -> dict[str, str]:
    names = {
        "captureContext": "capture-context.txt",
        "preflight": "capture-session-preflight.json",
        "lldbExitStatus": "lldb-exit-status.txt",
        "lldbLog": "lldb.log",
        "trace": trace_name,
        "timeline": "transition-timeline.json",
        "progress": "transition-progress.json",
        "runtimeStdout": "runtime-stdout.log",
        "runtimeStderr": "runtime-stderr.log",
    }
    return {key: sha256(directory / name) for key, name in names.items()}


def validate(
    preregistration_path: Path,
    selected_artifact_directory: Path,
    complete_artifact_directory: Path,
) -> dict[str, Any]:
    repository_root = Path(__file__).resolve().parent.parent
    preregistration = validate_preregistration(
        load_json(preregistration_path, "complete preregistration"),
        repository_root,
    )
    selected_preflight = validate_preflight(
        load_json(
            selected_artifact_directory / "capture-session-preflight.json",
            "selected-stage preflight",
        ),
        "selected-stage preflight",
    )
    complete_preflight = validate_preflight(
        load_json(
            complete_artifact_directory / "capture-session-preflight.json",
            "complete-stage preflight",
        ),
        "complete-stage preflight",
    )
    selected_commit = validate_context(
        selected_artifact_directory / "capture-context.txt",
        preregistration_path,
        str(
            mapping(
                sequence(
                    preregistration["unconditionalTwoStageDispatch"], "stages"
                )[0],
                "selected stage",
            )["captureSHA256"]
        ),
        "LG_BACKDROP_MARGIN_WRITER_TRACE_OUTPUT",
    )
    complete_commit = validate_context(
        complete_artifact_directory / "capture-context.txt",
        preregistration_path,
        EXPECTED_COMPLETE_CAPTURE_SHA256,
        "LG_CASE22_PROVIDER_OBJECT_MATRIX_MINIMAL_TRACE_OUTPUT",
    )
    require(
        selected_commit == complete_commit,
        "the two stages used different repository commits",
    )
    validate_process_transport(selected_artifact_directory)
    validate_process_transport(complete_artifact_directory)

    selected_trace_path = (
        selected_artifact_directory / "backdrop-margin-writer-trace.json"
    )
    selected_result = selected.validate(
        selected_trace_path,
        repository_root
        / "Analysis/backdrop_margin_case22_provider_local_macos_26_6_1_preregistration.json",
    )
    selected_timeline = allocation.validate_timeline(
        load_json(
            selected_artifact_directory / "transition-timeline.json",
            "selected-stage timeline",
        ),
        selected_artifact_directory,
    )
    selected_return = str(
        mapping(selected_result["providerExecution"], "selected provider result").get(
            "returnF64RawLittleEndianHex"
        )
    )
    selected_reproduced = selected_return == EXPECTED_SELECTED_RETURN

    complete_trace_path = (
        complete_artifact_directory / "provider-object-matrix-trace.json"
    )
    complete_trace = load_json(complete_trace_path, "complete trace")
    complete_result = validate_complete_trace(complete_trace)
    complete_timeline = allocation.validate_timeline(
        load_json(
            complete_artifact_directory / "transition-timeline.json",
            "complete-stage timeline",
        ),
        complete_artifact_directory,
    )
    complete_contract = bool(complete_result["positiveBranchContractPassed"])
    failed_requirements = []
    if not selected_reproduced:
        failed_requirements.append("requireSelectedStageHistoricalReturnReproduction")
    if complete_result["distinctProviderObjectCount"] < 2:
        failed_requirements.append("requireAtLeastTwoDistinctProviderObjects")
    if complete_result["distinctProviderReturnCount"] < 2:
        failed_requirements.append("requireAtLeastTwoDistinctProviderReturnWords")
    if complete_result["positiveGaussianInputAndGateObjectCount"] < 1:
        failed_requirements.append(
            "requireAtLeastOnePositiveGaussianInputAndGateObject"
        )
    if complete_result["finitePositiveProviderReturnCount"] < 1:
        failed_requirements.append("requireAtLeastOneFinitePositiveProviderReturn")

    selected_hashes = artifact_hashes(
        selected_artifact_directory, "backdrop-margin-writer-trace.json"
    )
    complete_hashes = artifact_hashes(
        complete_artifact_directory, "provider-object-matrix-trace.json"
    )
    capture_contract_passed = selected_reproduced and complete_contract
    return {
        "backdropMarginCase22ProviderObjectMatrixCompleteLocalMacOSValidationSchemaVersion": RESULT_SCHEMA_VERSION,
        "classification": (
            "prospective unlocked-Retina validation of the unconditional "
            "selected-return reproduction and complete-process all-case22 "
            "provider matrix"
        ),
        "inputs": {
            "preregistration": {
                "path": str(preregistration_path),
                "sha256": sha256(preregistration_path),
            },
            "selectedStage": {
                "directory": str(selected_artifact_directory),
                "sha256": selected_hashes,
            },
            "completeStage": {
                "directory": str(complete_artifact_directory),
                "sha256": complete_hashes,
            },
        },
        "session": {
            "selectedStage": selected_preflight,
            "completeStage": complete_preflight,
            "bothStagesUnlockedAwakeExactRetina": True,
        },
        "selectedStage": {
            "application": selected_timeline,
            "returnF64RawLittleEndianHex": selected_return,
            "historicalReturnReproducedBitwise": selected_reproduced,
        },
        "completeStage": {
            "application": complete_timeline,
            "trace": complete_result,
        },
        "transportAndStructuralIntegrityPassed": True,
        "captureContractPassed": capture_contract_passed,
        "failedRequirements": failed_requirements,
        "completeProcessProviderDomainEstablished": True,
        "unlockedSessionSelectedReturnTransferPassed": selected_reproduced,
        "positiveProviderBranchTransferPassed": complete_contract,
        "completeFiniteProviderLaw": False,
        "publicInputMappingAuthority": False,
        "upstreamIntegerCropAllocationPolicy": False,
        "physicalRetinaColorPixelCompositorTransfer": False,
        "independentWalleZeroByteFrameParity": False,
        "productionShaderAuthorized": False,
        "liquidGlassParityEstablished": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--selected-artifact-directory", type=Path, required=True)
    parser.add_argument("--complete-artifact-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        result = validate(
            arguments.preregistration,
            arguments.selected_artifact_directory,
            arguments.complete_artifact_directory,
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
