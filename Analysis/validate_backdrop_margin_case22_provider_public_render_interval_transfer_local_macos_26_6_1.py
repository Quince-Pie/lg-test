#!/usr/bin/env python3
"""Validate the prospective public-render/provider interval transfer."""

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

import analyze_backdrop_margin_case22_provider_public_timeline_join as join
import validate_backdrop_margin_case22_provider_object_matrix_minimal_retry2_local_macos_26_6_1 as allocation


RESULT_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
TRACE_SCHEMA_VERSION = 1
EXPECTED_BINARY_SHA256 = (
    "b9cb4068e77a61ff87794fa20a5c273e007f3ee20dd74503b1ab78839104e8dd"
)
EXPECTED_PREFLIGHT_SHA256 = (
    "f12a1cbe29629dc843cc3250a46fa686225f3c08bcf1bf1dbdf50aea913926f1"
)
SYMBOL_PRESENTATION_CORRECTION_PATH = (
    "Analysis/public_render_main_symbol_presentation_correction_local_macos_26_6_1.json"
)
SYMBOL_PRESENTATION_CORRECTION_SHA256 = (
    "0caa2811f60cbc72b0895ed4367d14b117c695ba3075b5f956464459ac24c474"
)
FRAMEWORK_IDENTITY_CORRECTION_PATH = (
    "Analysis/public_render_framework_symbol_identity_correction_local_macos_26_6_1.json"
)
FRAMEWORK_IDENTITY_CORRECTION_SHA256 = (
    "1771020d81ddde0926b23246666e50dd33e4e28819312cd3074e0081f6dfff63"
)
MAIN_UUID = "F8B0B6E3-3270-3C94-817F-B4914852D04C"
BACKGROUND_MANGLED = (
    "$s4main35transitionBackgroundUniformEvidence029_12232F587A4C5CD8B1EEDF696793G2FCLL"
    "9rootLayer9snapshots20matrixBasisRequested14allocationOnly010fixedStateR0013pathIsolationR0"
    "15outputDirectorySDySSypGSo7CALayerC_SayAA010TransitionC14FilterSnapshotACLLVGS4b10Foundation3URLVtF"
)
BACKGROUND_MODULE_OFFSET = 0x881B0
BACKGROUND_BYTE_COUNT = 0x23B0
BACKGROUND_CODE_SHA256 = (
    "1ca54720d237eb6970b65dd2ecc88b8372b64667f4ea2d28ef4bc8414668e2fd"
)
RENDER_MODULE_OFFSET = 0x7D12C
RENDER_BYTE_COUNT = 0x4E8
RENDER_CODE_SHA256 = "0c661f1010199a56e6730d897079fda69fc4a267f7f48d1e2054b14ff9270e0c"
RENDER_CALL_OFFSET = 0x1000
RENDER_RETURN_OFFSET = 0x1004
RENDER_CALL_INSTRUCTION_HEX = "dfcfff97"
WRAPPER_RETURN_OFFSET = 0x68
MAXIMUM_CALLS_PER_INTERVAL = 128
MAXIMUM_TOTAL_CALLS = 4096
EXPECTED_ENVIRONMENT = {
    "LG_GEOMETRY_POLICY": "0",
    "LG_GLASS_APPEARANCE": "light",
    "LG_GLASS_GEOMETRY": "circle-127-center",
    "LG_GLASS_MATERIAL": "regular",
    "LG_TRANSITION_ALLOCATION_CALIBRATION": "0",
    "LG_TRANSITION_ALLOCATION_DENSE": "1",
    "LG_TRANSITION_ALLOCATION_FIXED_STATE": "0",
    "LG_TRANSITION_ALLOCATION_MESH_CALIBRATION": "0",
    "LG_TRANSITION_ALLOCATION_ONLY": "1",
    "LG_TRANSITION_ALLOCATION_PATH_ISOLATION": "0",
    "LG_TRANSITION_CONTROLLED_BACKDROP": "0",
    "LG_TRANSITION_DIRECTION": "materialize",
    "LG_TRANSITION_HIGHLIGHT_TRACE": "0",
    "LG_TRANSITION_MATRIX_BASIS": "0",
    "LG_TRANSITION_TIMELINE": "1",
    "LG_TRANSITION_UNIFORMS": "1",
}
EXPECTED_PREFLIGHT = {
    "backingScaleFactor": 2,
    "classification": (
        "fail-closed native macOS 26.6.1 presentation-session preflight v2"
    ),
    "displayActive": True,
    "displayAsleep": False,
    "expectedBackingScaleFactor": 2,
    "expectedLogicalPoints": [1728, 1117],
    "expectedPhysicalPixels": [3456, 2234],
    "localRetinaCaptureSessionPreflightSchemaVersion": 2,
    "logicalPoints": [1728, 1117],
    "passed": True,
    "physicalPixels": [3456, 2234],
    "sessionDictionaryAvailable": True,
    "sessionLockFieldPresent": False,
    "sessionLockFieldValid": True,
    "sessionLocked": False,
    "sessionLoginDone": True,
    "sessionOnConsole": True,
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


def validate_preregistration(value: Any, repository_root: Path) -> Mapping[str, Any]:
    preregistration = mapping(value, "public render-interval preregistration")
    require(
        preregistration.get(
            "case22ProviderPublicRenderIntervalTransferLocalMacOSPreregistrationSchemaVersion"
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
    require(
        amendment.get("supersededPreflightSHA256")
        == "72e259882f0c9cc5f40e7f12d172dbbe2582da729b0ee176647917b07f172981",
        "superseded preflight identity differs",
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
            "path": SYMBOL_PRESENTATION_CORRECTION_PATH,
            "prospectiveOpticalPredictionsUnchanged": True,
            "sha256": SYMBOL_PRESENTATION_CORRECTION_SHA256,
        },
        "symbol-presentation operational amendment differs",
    )
    correction_path = repository_root / SYMBOL_PRESENTATION_CORRECTION_PATH
    require(
        sha256(correction_path) == SYMBOL_PRESENTATION_CORRECTION_SHA256,
        "symbol-presentation correction hash differs",
    )
    correction = mapping(
        load_json(correction_path, "symbol-presentation correction"),
        "symbol-presentation correction",
    )
    require(
        correction.get("publicRenderMainSymbolPresentationCorrectionSchemaVersion")
        == 1,
        "symbol-presentation correction schema differs",
    )
    failed_capture = mapping(
        correction.get("failedCapture"), "failed symbol-presentation capture"
    )
    require(
        failed_capture.get("finalIntervalCount") == 0
        and failed_capture.get("finalCallCount") == 0
        and failed_capture.get("opticalPredictionsEvaluated") is False,
        "failed symbol-presentation capture crossed an optical boundary",
    )
    correction_contract = mapping(
        correction.get("correction"), "symbol-presentation correction contract"
    )
    require(
        correction_contract.get("functionPresentationUsedAsBinaryIdentity") is False
        and correction_contract.get("opticalPredictionsChanged") is False
        and correction_contract.get("runtimeCaptureSelectionChanged") is False,
        "symbol-presentation correction changed capture semantics",
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
            "path": FRAMEWORK_IDENTITY_CORRECTION_PATH,
            "prospectiveOpticalPredictionsUnchanged": True,
            "sha256": FRAMEWORK_IDENTITY_CORRECTION_SHA256,
        },
        "framework-identity operational amendment differs",
    )
    framework_correction_path = repository_root / FRAMEWORK_IDENTITY_CORRECTION_PATH
    require(
        sha256(framework_correction_path) == FRAMEWORK_IDENTITY_CORRECTION_SHA256,
        "framework-identity correction hash differs",
    )
    framework_correction = mapping(
        load_json(framework_correction_path, "framework-identity correction"),
        "framework-identity correction",
    )
    require(
        framework_correction.get(
            "publicRenderFrameworkSymbolIdentityCorrectionSchemaVersion"
        )
        == 1,
        "framework-identity correction schema differs",
    )
    failed_framework_capture = mapping(
        framework_correction.get("failedCapture"),
        "failed framework-identity capture",
    )
    require(
        failed_framework_capture.get("finalIntervalCount") == 0
        and failed_framework_capture.get("finalCallCount") == 0
        and failed_framework_capture.get("opticalPredictionsEvaluated") is False,
        "failed framework-identity capture crossed an optical boundary",
    )
    framework_contract = mapping(
        framework_correction.get("correction"),
        "framework-identity correction contract",
    )
    require(
        framework_contract.get("staleTransitiveUUIDAssertionRetained") is False
        and framework_contract.get("opticalPredictionsChanged") is False
        and framework_contract.get("runtimeCaptureSelectionChanged") is False,
        "framework-identity correction changed capture semantics",
    )
    profile = mapping(preregistration.get("profile"), "preregistered profile")
    require(
        profile
        == {
            "appearance": "light",
            "direction": "materialize",
            "geometry": "circle-127-center",
            "material": "regular",
            "sampleIndices": list(range(1, 33)),
        },
        "preregistered profile differs",
    )
    binary = mapping(preregistration.get("binary"), "preregistered binary")
    require(binary.get("sha256") == EXPECTED_BINARY_SHA256, "binary hash differs")
    boundary = mapping(
        preregistration.get("structuralRenderBoundary"),
        "structural render boundary",
    )
    expected_boundary = {
        "backgroundModuleOffset": BACKGROUND_MODULE_OFFSET,
        "backgroundByteCount": BACKGROUND_BYTE_COUNT,
        "backgroundCodeSHA256": BACKGROUND_CODE_SHA256,
        "renderModuleOffset": RENDER_MODULE_OFFSET,
        "renderByteCount": RENDER_BYTE_COUNT,
        "renderCodeSHA256": RENDER_CODE_SHA256,
        "renderCallOffset": RENDER_CALL_OFFSET,
        "renderReturnOffset": RENDER_RETURN_OFFSET,
        "renderCallInstructionHex": RENDER_CALL_INSTRUCTION_HEX,
        "mainUUID": MAIN_UUID,
    }
    for key, expected in expected_boundary.items():
        require(boundary.get(key) == expected, f"boundary field {key} differs")
    predictions = mapping(
        preregistration.get("prospectivePredictions"), "prospective predictions"
    )
    require(
        predictions.get("uniqueFullSignatureMatchesPerSamples1Through31") == 1,
        "non-endpoint match prediction differs",
    )
    require(
        predictions.get("fullSignatureMatchesForRepeatedEndpointSample32") == 2,
        "endpoint match prediction differs",
    )
    require(
        predictions.get("partialSignatureMatchesPerInterval") == 0,
        "partial-match prediction differs",
    )
    require(
        predictions.get("matchedProviderReturnRawLittleEndianHex")
        == "0000000000000000",
        "provider return prediction differs",
    )
    files = sequence(
        mapping(
            preregistration.get("frozenImplementation"),
            "frozen implementation",
        ).get("files"),
        "frozen implementation files",
    )
    require(len(files) >= 6, "frozen implementation file set is incomplete")
    for index, file_value in enumerate(files):
        record = mapping(file_value, f"frozen file {index}")
        path = repository_root / str(record.get("path"))
        require(sha256(path) == record.get("sha256"), f"{path} hash differs")
    unknowns = mapping(preregistration.get("unknownBeforeDispatch"), "runtime unknowns")
    require(
        unknowns and all(value is None for value in unknowns.values()),
        "runtime unknowns were not null",
    )
    return preregistration


def validate_preflight(value: Any) -> dict[str, Any]:
    report = mapping(value, "capture-session preflight")
    require(report == EXPECTED_PREFLIGHT, "capture-session preflight differs")
    return dict(report)


def decode_arm64_bl_target(instruction_raw: bytes, address: int) -> int:
    require(len(instruction_raw) == 4, "render call instruction width differs")
    instruction = struct.unpack("<I", instruction_raw)[0]
    require(instruction >> 26 == 0b100101, "render callsite is not ARM64 BL")
    displacement = instruction & 0x03FFFFFF
    if displacement & (1 << 25):
        displacement -= 1 << 26
    return address + displacement * 4


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
        EXPECTED_BINARY_SHA256,
        capture_sha256,
        sha256(preregistration_path),
        EXPECTED_PREFLIGHT_SHA256,
        validator_sha256,
        runner_sha256,
    )
    for line, expected in zip(lines[1:7], expected_hashes):
        require(line.startswith(expected + "  "), "capture context hash differs")
    environment = dict(line.split("=", 1) for line in lines[7:])
    trace_path = environment.pop(
        "LG_CASE22_PROVIDER_PUBLIC_RENDER_INTERVAL_TRACE_OUTPUT", None
    )
    require(
        trace_path is not None
        and trace_path.endswith("/provider-public-render-interval-trace.json"),
        "trace output environment differs",
    )
    require(environment == EXPECTED_ENVIRONMENT, "capture environment differs")
    return lines[0]


def validate_main_symbol(
    value: Any,
    module: Mapping[str, Any],
    offset: int,
    byte_count: int,
    digest: str,
    label: str,
) -> Mapping[str, Any]:
    record = mapping(value, label)
    payload = bytes.fromhex(str(record.get("hex", "")))
    record_module = mapping(record.get("module"), f"{label} module")
    require(record_module.get("valid") is True, f"{label} module is invalid")
    require(record_module.get("uuid") == MAIN_UUID, f"{label} UUID differs")
    require(
        record_module.get("loadAddress") == module.get("loadAddress"),
        f"{label} load address differs",
    )
    require(
        isinstance(record.get("function"), str) and bool(record["function"]),
        f"{label} function presentation is absent",
    )
    require(
        record.get("symbolStart") == module.get("loadAddress") + offset,
        f"{label} offset differs",
    )
    require(record.get("symbolByteCount") == byte_count, f"{label} byte count differs")
    require(len(payload) == byte_count, f"{label} payload width differs")
    require(record.get("codeSHA256") == digest, f"{label} recorded hash differs")
    require(hashlib.sha256(payload).hexdigest() == digest, f"{label} code hash differs")
    return record


def validate_framework_symbol(
    value: Any,
    module: Mapping[str, Any],
    contract: Mapping[str, Any],
    expected_uuid: str,
    path_suffix: str,
    label: str,
) -> Mapping[str, Any]:
    record = mapping(value, label)
    record_module = mapping(record.get("module"), f"{label} module")
    payload = bytes.fromhex(str(record.get("hex", "")))
    require(module.get("valid") is True, f"{label} module is invalid")
    require(module.get("uuid") == expected_uuid, f"{label} module UUID differs")
    require(
        isinstance(module.get("loadAddress"), int) and module["loadAddress"] > 0,
        f"{label} module load address differs",
    )
    require(
        str(module.get("path", "")).endswith(path_suffix),
        f"{label} module path differs",
    )
    require(
        record_module.get("uuid") == expected_uuid
        and record_module.get("loadAddress") == module.get("loadAddress")
        and str(record_module.get("path", "")).endswith(path_suffix),
        f"{label} record module differs",
    )
    require(
        isinstance(record.get("function"), str) and bool(record["function"]),
        f"{label} function presentation is absent",
    )
    require(
        record.get("symbolStart")
        == module.get("loadAddress") + int(contract["moduleOffset"]),
        f"{label} module offset differs",
    )
    require(
        record.get("symbolByteCount") == contract["byteCount"],
        f"{label} byte count differs",
    )
    require(
        len(payload) == contract["byteCount"],
        f"{label} code payload length differs",
    )
    require(
        record.get("codeSHA256") == contract["codeSHA256"],
        f"{label} recorded code hash differs",
    )
    require(
        hashlib.sha256(payload).hexdigest() == contract["codeSHA256"],
        f"{label} code hash differs",
    )
    return record


def validate_event(
    events: Sequence[Any], index: Any, kind: str, record_index: int, label: str
) -> None:
    require(
        isinstance(index, int) and 0 <= index < len(events),
        f"{label} event index differs",
    )
    event = mapping(events[index], f"{label} event")
    require(
        event == {"eventIndex": index, "kind": kind, "recordIndex": record_index},
        f"{label} event differs",
    )


def validate_trace(value: Any) -> tuple[dict[str, Any], list[Mapping[str, Any]]]:
    trace = mapping(value, "public render-interval trace")
    require(
        trace.get(
            "case22ProviderPublicRenderIntervalTransferLocalMacOSLldbTraceSchemaVersion"
        )
        == TRACE_SCHEMA_VERSION,
        "trace schema differs",
    )
    configuration = mapping(trace.get("configuration"), "trace configuration")
    expected_configuration = {
        "appearance": "light",
        "architecture": "arm64",
        "backgroundByteCount": BACKGROUND_BYTE_COUNT,
        "backgroundCodeSHA256": BACKGROUND_CODE_SHA256,
        "backgroundModuleOffset": BACKGROUND_MODULE_OFFSET,
        "capturedCropUsedForSelection": False,
        "capturedImageUsedForSelection": False,
        "capturedMarginUsedForSelection": False,
        "capturedObjectUsedForSelection": False,
        "capturedPixelUsedForSelection": False,
        "capturedPublicInputUsedForSelection": False,
        "capturedReturnUsedForSelection": False,
        "direction": "materialize",
        "geometry": "circle-127-center",
        "mainUUID": MAIN_UUID,
        "macOSBuildVersion": "25G76",
        "macOSProductVersion": "26.6.1",
        "material": "regular",
        "maximumCallsPerInterval": MAXIMUM_CALLS_PER_INTERVAL,
        "maximumTotalCalls": MAXIMUM_TOTAL_CALLS,
        "renderByteCount": RENDER_BYTE_COUNT,
        "renderCallInstructionHex": RENDER_CALL_INSTRUCTION_HEX,
        "renderCallOffset": RENDER_CALL_OFFSET,
        "renderCodeSHA256": RENDER_CODE_SHA256,
        "renderModuleOffset": RENDER_MODULE_OFFSET,
        "renderReturnOffset": RENDER_RETURN_OFFSET,
        "sampleIndices": list(range(1, 33)),
    }
    require(configuration == expected_configuration, "trace configuration differs")
    modules = mapping(trace.get("modules"), "trace modules")
    require(
        set(modules) == {"main", "swiftUICore", "designLibrary"},
        "trace module set differs",
    )
    main_module = mapping(modules.get("main"), "main module")
    swift_module = mapping(modules.get("swiftUICore"), "SwiftUICore module")
    design_module = mapping(modules.get("designLibrary"), "DesignLibrary module")
    require(main_module.get("valid") is True, "main module is invalid")
    require(main_module.get("uuid") == MAIN_UUID, "main module UUID differs")
    require(
        isinstance(main_module.get("loadAddress"), int)
        and main_module["loadAddress"] > 0,
        "main module load address differs",
    )
    require(
        str(main_module.get("path", "")).endswith(
            "/glass-transition-introspect-721293f"
        ),
        "main module path differs",
    )
    background = validate_main_symbol(
        trace.get("backgroundFunction"),
        main_module,
        BACKGROUND_MODULE_OFFSET,
        BACKGROUND_BYTE_COUNT,
        BACKGROUND_CODE_SHA256,
        "background function",
    )
    render = validate_main_symbol(
        trace.get("renderFunction"),
        main_module,
        RENDER_MODULE_OFFSET,
        RENDER_BYTE_COUNT,
        RENDER_CODE_SHA256,
        "render function",
    )
    background_raw = bytes.fromhex(str(background["hex"]))
    require(
        background_raw[RENDER_CALL_OFFSET : RENDER_CALL_OFFSET + 4].hex()
        == RENDER_CALL_INSTRUCTION_HEX,
        "render call instruction differs",
    )
    require(
        decode_arm64_bl_target(
            background_raw[RENDER_CALL_OFFSET : RENDER_CALL_OFFSET + 4],
            background["symbolStart"] + RENDER_CALL_OFFSET,
        )
        == render["symbolStart"],
        "render call target differs",
    )
    wrapper = validate_framework_symbol(
        trace.get("wrapper"),
        swift_module,
        allocation.EXPECTED_SYMBOLS["wrapper"],
        allocation.SWIFTUICORE_UUID,
        "/SwiftUICore",
        "wrapper",
    )
    provider = validate_framework_symbol(
        trace.get("provider"),
        design_module,
        allocation.EXPECTED_SYMBOLS["provider"],
        allocation.DESIGN_LIBRARY_UUID,
        "/DesignLibrary",
        "provider",
    )
    breakpoints = mapping(trace.get("breakpoints"), "trace breakpoints")
    expected_breakpoint_addresses = {
        "renderCall": background["symbolStart"] + RENDER_CALL_OFFSET,
        "renderReturn": background["symbolStart"] + RENDER_RETURN_OFFSET,
        "providerEntry": provider["symbolStart"],
        "providerReturn": wrapper["symbolStart"] + WRAPPER_RETURN_OFFSET,
    }
    require(
        set(breakpoints) == {"bootstrap", *expected_breakpoint_addresses},
        "trace breakpoint set differs",
    )
    bootstrap = mapping(breakpoints.get("bootstrap"), "bootstrap breakpoint")
    require(
        bootstrap.get("requestedName") == BACKGROUND_MANGLED,
        "bootstrap breakpoint name differs",
    )
    breakpoint_ids = []
    for label, address in expected_breakpoint_addresses.items():
        record = mapping(breakpoints.get(label), f"{label} breakpoint")
        require(
            record.get("address") == address,
            f"{label} breakpoint address differs",
        )
        require(
            record.get("locationCount") == 1,
            f"{label} breakpoint location count differs",
        )
        breakpoint_ids.append(record.get("id"))
    require(
        bootstrap.get("locationCount") == 1,
        "bootstrap breakpoint location count differs",
    )
    breakpoint_ids.append(bootstrap.get("id"))
    require(
        all(isinstance(value, int) and value > 0 for value in breakpoint_ids)
        and len(set(breakpoint_ids)) == len(breakpoint_ids),
        "breakpoint identities differ",
    )
    events = sequence(trace.get("events"), "trace events")
    intervals = [
        mapping(value, f"render interval {index}")
        for index, value in enumerate(
            sequence(trace.get("intervals"), "render intervals")
        )
    ]
    calls = [
        mapping(value, f"provider call {index}")
        for index, value in enumerate(sequence(trace.get("calls"), "provider calls"))
    ]
    require(len(intervals) == 32, "render interval count differs")
    require(0 < len(calls) <= MAXIMUM_TOTAL_CALLS, "provider call count differs")
    referenced_calls = []
    referenced_events = []
    previous_return_event = -1
    for index, interval in enumerate(intervals):
        require(
            interval.get("intervalIndex") == index, f"interval {index} index differs"
        )
        require(
            interval.get("sampleIndex") == index + 1, f"interval {index} sample differs"
        )
        require(interval.get("status") == "closed", f"interval {index} did not close")
        require(
            isinstance(interval.get("threadID"), int),
            f"interval {index} thread differs",
        )
        allocation.validate_frame(
            interval.get("entryFrame"),
            background,
            RENDER_CALL_OFFSET,
            f"interval {index} entry",
        )
        allocation.validate_frame(
            interval.get("returnFrame"),
            background,
            RENDER_RETURN_OFFSET,
            f"interval {index} return",
        )
        validate_event(
            events,
            interval.get("entryEventIndex"),
            "render-call",
            index,
            f"interval {index} entry",
        )
        validate_event(
            events,
            interval.get("returnEventIndex"),
            "render-return",
            index,
            f"interval {index} return",
        )
        entry_event = interval["entryEventIndex"]
        return_event = interval["returnEventIndex"]
        require(
            previous_return_event < entry_event < return_event,
            f"interval {index} event order differs",
        )
        previous_return_event = return_event
        referenced_events.extend((entry_event, return_event))
        call_indices = list(
            sequence(interval.get("callIndices"), f"interval {index} calls")
        )
        require(
            0 < len(call_indices) <= MAXIMUM_CALLS_PER_INTERVAL,
            f"interval {index} call count differs",
        )
        require(
            interval.get("finalCallCount") == len(call_indices),
            f"interval {index} final count differs",
        )
        referenced_calls.extend(call_indices)
    require(
        referenced_calls == list(range(len(calls))), "interval call partition differs"
    )

    object_payloads = []
    for index, call in enumerate(calls):
        require(call.get("callIndex") == index, f"provider call {index} index differs")
        interval_index = call.get("intervalIndex")
        require(
            isinstance(interval_index, int) and 0 <= interval_index < 32,
            f"provider call {index} interval differs",
        )
        interval = intervals[interval_index]
        require(
            call.get("sampleIndex") == interval["sampleIndex"],
            f"provider call {index} sample differs",
        )
        interval_call_index = call.get("intervalCallIndex")
        require(
            isinstance(interval_call_index, int)
            and 0 <= interval_call_index < len(interval["callIndices"])
            and interval["callIndices"][interval_call_index] == index,
            f"provider call {index} interval position differs",
        )
        require(
            isinstance(call.get("threadID"), int),
            f"provider call {index} thread differs",
        )
        address = call.get("providerObjectAddress")
        require(
            isinstance(address, int) and address > 0,
            f"provider call {index} object address differs",
        )
        entry_raw = allocation.validate_snapshot(
            call.get("providerObject"), address, f"provider call {index} entry object"
        )
        return_raw = allocation.validate_snapshot(
            call.get("returnObject"), address, f"provider call {index} return object"
        )
        require(entry_raw == return_raw, f"provider call {index} object changed")
        require(
            call.get("objectChanged") is False,
            f"provider call {index} mutation flag differs",
        )
        allocation.validate_frame(
            call.get("entryFrame"), provider, 0, f"provider call {index} entry"
        )
        allocation.validate_frame(
            call.get("returnFrame"),
            wrapper,
            WRAPPER_RETURN_OFFSET,
            f"provider call {index} return",
        )
        raw_v0 = str(call.get("returnV0RawLittleEndianHex", ""))
        raw_f64 = str(call.get("returnF64RawLittleEndianHex", ""))
        require(
            len(bytes.fromhex(raw_v0)) == 16,
            f"provider call {index} return width differs",
        )
        require(
            len(bytes.fromhex(raw_f64)) == 8,
            f"provider call {index} f64 return width differs",
        )
        require(raw_v0[:16] == raw_f64, f"provider call {index} return word differs")
        validate_event(
            events,
            call.get("entryEventIndex"),
            "provider-entry",
            index,
            f"provider call {index} entry",
        )
        validate_event(
            events,
            call.get("returnEventIndex"),
            "provider-return",
            index,
            f"provider call {index} return",
        )
        entry_event = call["entryEventIndex"]
        return_event = call["returnEventIndex"]
        require(
            interval["entryEventIndex"]
            < entry_event
            < return_event
            < interval["returnEventIndex"],
            f"provider call {index} escaped its render interval",
        )
        referenced_events.extend((entry_event, return_event))
        object_payloads.append(entry_raw)
    require(
        len(events) == 2 * len(intervals) + 2 * len(calls),
        "trace event cardinality differs",
    )
    require(
        sorted(referenced_events) == list(range(len(events))),
        "trace event partition differs",
    )
    require(trace.get("status") == "finalized", "trace did not finalize")
    require(
        trace.get("statusBeforeFinalization") == "all-render-intervals-closed",
        "trace did not finish after all intervals",
    )
    require(
        not sequence(trace.get("failures"), "trace failures"), "trace contains failures"
    )
    require(trace.get("allIntervalsClosed") is True, "trace interval closure differs")
    require(trace.get("finalIntervalCount") == 32, "trace final interval count differs")
    require(trace.get("finalCallCount") == len(calls), "trace final call count differs")
    require(
        trace.get("finalEventCount") == len(events), "trace final event count differs"
    )
    require(trace.get("finalFailureCount") == 0, "trace final failure count differs")
    require(trace.get("finalPendingCallCount") == 0, "trace has pending calls")
    require(trace.get("finalActiveInterval") is None, "trace has an active interval")
    return (
        {
            "intervalCount": len(intervals),
            "providerCallCount": len(calls),
            "eventCount": len(events),
            "distinctProviderObjectCount": len(set(object_payloads)),
            "failureCount": 0,
        },
        calls,
    )


def public_inputs(record: Mapping[str, Any], sample_index: int) -> Mapping[str, Any]:
    filter_record = mapping(record.get("filter"), f"sample {sample_index} filter")
    return mapping(filter_record.get("inputValues"), f"sample {sample_index} inputs")


def binary64(value: Any, scale: float, label: str) -> bytes:
    require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"{label} is not numeric",
    )
    result = float(value) * scale
    require(math.isfinite(result), f"{label} is not finite")
    return struct.pack("<d", result)


def validate_loaded_field_predictions(
    raw: bytes, inputs: Mapping[str, Any], sample_index: int
) -> None:
    shadow_offset = mapping(
        inputs.get("inputShadowOffset"), f"sample {sample_index} shadow offset"
    )
    offset_raw = bytes.fromhex(str(shadow_offset.get("hex", "")))
    require(len(offset_raw) == 16, f"sample {sample_index} shadow offset width differs")
    require(
        raw[0x008:0x018] == offset_raw,
        f"sample {sample_index} shadow offset fields differ",
    )
    shadow = binary64(inputs.get("inputShadowAmount"), 1.0, "inputShadowAmount")
    blur = binary64(inputs.get("inputBlurRadius"), 2.0, "inputBlurRadius")
    inner = binary64(
        inputs.get("inputInnerRefractionAmount"), 1.0, "inputInnerRefractionAmount"
    )
    shadow_scaled = binary64(
        inputs.get("inputShadowAmount"), -0.8, "scaled inputShadowAmount"
    )
    bleed = binary64(inputs.get("inputBleedAmount"), 1.0, "inputBleedAmount")
    bleed_height = binary64(inputs.get("inputBleedHeight"), 1.0, "inputBleedHeight")
    require(raw[0x018:0x020] == shadow, f"sample {sample_index} shadow amount differs")
    require(raw[0x098:0x0A0] == blur, f"sample {sample_index} blur field differs")
    require(
        raw[0x0E8:0x0F0] == inner == shadow_scaled,
        f"sample {sample_index} inner field differs",
    )
    require(
        raw[0x160:0x168] == bleed == bleed_height,
        f"sample {sample_index} bleed field differs",
    )
    zero64 = struct.pack("<d", 0.0)
    zero32 = struct.pack("<f", 0.0)
    for offset in join.ZERO_F64_OFFSETS:
        require(
            raw[offset : offset + 8] == zero64,
            f"sample {sample_index} field {offset:#x} differs",
        )
    for offset in join.ZERO_F32_OFFSETS:
        require(
            raw[offset : offset + 4] == zero32,
            f"sample {sample_index} field {offset:#x} differs",
        )


def validate_interval_transfer(
    timeline_value: Any,
    trace_value: Any,
) -> dict[str, Any]:
    timeline = mapping(timeline_value, "timeline")
    dynamic = mapping(
        timeline.get("dynamicBackgroundUniforms"), "dynamic background uniforms"
    )
    records = [
        mapping(value, f"public record {index}")
        for index, value in enumerate(
            sequence(dynamic.get("records"), "public records"), 1
        )
    ]
    trace = mapping(trace_value, "trace")
    intervals = [
        mapping(value, f"interval {index}")
        for index, value in enumerate(sequence(trace.get("intervals"), "intervals"))
    ]
    calls = [
        mapping(value, f"call {index}")
        for index, value in enumerate(sequence(trace.get("calls"), "calls"))
    ]
    require(
        len(records) == len(intervals) == 32, "timeline/interval cardinality differs"
    )
    joined = []
    matched_indices = []
    for record, interval in zip(records, intervals):
        sample_index = int(record.get("sampleIndex"))
        require(
            interval.get("sampleIndex") == sample_index,
            f"sample {sample_index} interval alignment differs",
        )
        inputs = public_inputs(record, sample_index)
        words = join.signature_words(inputs)
        interval_calls = [
            calls[int(index)]
            for index in sequence(
                interval.get("callIndices"), f"sample {sample_index} call indices"
            )
        ]
        match_counts = []
        payloads = []
        for call in interval_calls:
            raw = bytes.fromhex(
                mapping(call.get("providerObject"), "provider object")["hex"]
            )
            payloads.append(raw)
            match_counts.append(join.signature_match_count(raw, words))
        histogram = Counter(match_counts)
        full = [position for position, count in enumerate(match_counts) if count == 4]
        partial = sum(count for matched, count in histogram.items() if 0 < matched < 4)
        expected_full_count = 2 if sample_index == 32 else 1
        require(
            len(full) == expected_full_count,
            f"sample {sample_index} full-match count differs",
        )
        require(partial == 0, f"sample {sample_index} has partial signature collisions")
        require(
            histogram.get(0, 0) + histogram.get(4, 0) == len(interval_calls),
            f"sample {sample_index} signature histogram differs",
        )
        sample_matches = []
        for position in full:
            call = interval_calls[position]
            raw = payloads[position]
            validate_loaded_field_predictions(raw, inputs, sample_index)
            require(
                call.get("returnF64RawLittleEndianHex") == "0000000000000000",
                f"sample {sample_index} matched return differs",
            )
            call_index = int(call["callIndex"])
            matched_indices.append(call_index)
            sample_matches.append(
                {
                    "providerCallIndex": call_index,
                    "intervalCallIndex": call.get("intervalCallIndex"),
                    "providerObjectSHA256": hashlib.sha256(raw).hexdigest(),
                    "returnRawLittleEndianHex": call["returnF64RawLittleEndianHex"],
                }
            )
        joined.append(
            {
                "sampleIndex": sample_index,
                "intervalProviderCallCount": len(interval_calls),
                "fullSignatureMatchCount": len(full),
                "partialSignatureMatchCount": partial,
                "zeroSignatureMatchCount": histogram.get(0, 0),
                "matches": sample_matches,
            }
        )
    require(
        matched_indices == sorted(matched_indices),
        "matched provider sequence is not monotonic",
    )
    require(
        len(set(matched_indices)) == len(matched_indices),
        "matched provider calls are reused",
    )
    return {
        "sampleCount": len(joined),
        "uniqueNonEndpointJoinCount": 31,
        "endpointFullMatchCount": 2,
        "totalFullMatchCount": len(matched_indices),
        "partialMatchCount": 0,
        "matchedProviderCallIndices": matched_indices,
        "allMatchedLoadedFieldPredictionsExact": True,
        "allMatchedReturnsExactZero": True,
        "allMatchedProviderCallsStrictlyIncreasing": True,
        "samples": joined,
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
            mapping(preregistration["frozenImplementation"], "frozen implementation")[
                "files"
            ],
            "frozen files",
        )
    }
    capture_path = (
        repository_root
        / "Analysis/capture_backdrop_margin_case22_provider_public_render_interval_transfer_local_macos_26_6_1_lldb.py"
    )
    validator_path = Path(__file__).resolve()
    runner_path = (
        repository_root
        / "Analysis/run_backdrop_margin_case22_provider_public_render_interval_transfer_local_macos_26_6_1.sh"
    )
    preflight_path = (
        repository_root / "Analysis/check_local_retina_capture_session_v2.swift"
    )
    require(
        sha256(preflight_path) == EXPECTED_PREFLIGHT_SHA256,
        "preflight source hash differs",
    )
    commit = validate_context(
        artifact_directory / "capture-context.txt",
        preregistration_path,
        frozen_files[str(capture_path.relative_to(repository_root))],
        sha256(validator_path),
        frozen_files[str(runner_path.relative_to(repository_root))],
    )
    validate_preflight(
        load_json(artifact_directory / "capture-session-preflight.json", "preflight")
    )
    require(
        (artifact_directory / "lldb-exit-status.txt").read_text(encoding="utf-8")
        == "0\n",
        "LLDB exit status differs",
    )
    log = (artifact_directory / "lldb.log").read_text(encoding="utf-8")
    require("exited with status = 0" in log, "application did not exit zero")
    require("Traceback" not in log, "LLDB log contains a traceback")
    require("error: Aborting reading of commands" not in log, "LLDB command failed")
    trace_path = artifact_directory / "provider-public-render-interval-trace.json"
    timeline_path = artifact_directory / "transition-timeline.json"
    trace = load_json(trace_path, "trace")
    timeline = load_json(timeline_path, "timeline")
    trace_summary, _calls = validate_trace(trace)
    timeline_summary = allocation.validate_timeline(timeline, artifact_directory)
    transfer = validate_interval_transfer(timeline, trace)
    primary_paths = {
        "captureContext": artifact_directory / "capture-context.txt",
        "captureSessionPreflight": artifact_directory
        / "capture-session-preflight.json",
        "lldbExitStatus": artifact_directory / "lldb-exit-status.txt",
        "lldbLog": artifact_directory / "lldb.log",
        "providerTrace": trace_path,
        "publicTimeline": timeline_path,
        "transitionProgress": artifact_directory / "transition-progress.json",
        "runtimeStdout": artifact_directory / "runtime-stdout.log",
        "runtimeStderr": artifact_directory / "runtime-stderr.log",
    }
    return {
        "case22ProviderPublicRenderIntervalTransferLocalMacOSValidationSchemaVersion": RESULT_SCHEMA_VERSION,
        "classification": (
            "prospective exact same-profile transfer of public sample "
            "boundaries and all opened provider-loaded word predictions"
        ),
        "inputs": {
            "sourceCommit": commit,
            "preregistration": {
                "path": str(preregistration_path),
                "sha256": sha256(preregistration_path),
            },
            **{
                name: {"path": str(path), "sha256": sha256(path)}
                for name, path in primary_paths.items()
            },
        },
        "application": timeline_summary,
        "trace": trace_summary,
        "transfer": transfer,
        "captureContractPassed": True,
        "authority": {
            "sameProfileBlindRepeatPassed": True,
            "authenticatedPerRenderCallbackIntervalJoinEstablished": True,
            "prospectivePublicWordToProviderObjectTransferEstablishedForOpenedProfile": True,
            "allOpenedLoadedFieldPredictionsTransferredBitwise": True,
            "constantAndCovaryingSemanticSourcesDisambiguated": False,
            "freshMaterialAppearanceGeometryProfileTransferEstablished": False,
            "generalPublicInputObjectConstructionLawEstablished": False,
            "upstreamCropAllocationPolicyEstablished": False,
            "physicalRetinaColorPixelCompositorTransferEstablished": False,
            "independentWalleZeroByteFrameParityEstablished": False,
            "liquidGlassParityEstablished": False,
            "productionShaderAuthorized": False,
        },
        "nextExactGate": (
            "freeze independent public-input interventions or a fresh "
            "material/appearance/geometry profile at the same authenticated "
            "render boundary to disambiguate constant and co-varying fields"
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
