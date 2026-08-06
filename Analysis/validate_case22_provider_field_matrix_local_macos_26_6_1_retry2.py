#!/usr/bin/env python3
"""Validate the closed, zero-provider-call local field-matrix result."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


RESULT_SCHEMA_VERSION = 1
EXPECTED_HASHES = {
    "basePreregistration": "57a7039661a966c177ba2f923051d095070e260b514623ad1ccb2b93759d50e0",
    "retryPreregistration": "22ebed82398ad37311f0af8be0e15087301ca2e1a193f4d1ff4a3e4da17c39d8",
    "retry2Preregistration": "267356b525e41b4360a7f9b9bc9cf87a3e47582c65ba74c0c4644670d107c53e",
    "applicationReport": "f457e74a8e179166c13690c45cc73920f50f5a8d1e68aea0dffe617341b043f9",
    "trace": "f38bd2c049aeb917de1ef2d2430dee333a78ab745421d4e42f970779b377bdf8",
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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_requested_value(record: Mapping[str, Any], intervention: Mapping[str, Any]) -> None:
    requested = mapping(record.get("requestedValues"), "requested values")
    key = intervention.get("key")
    if key is None:
        require(not requested, "baseline unexpectedly requests a value")
        return
    require(set(requested) == {key}, "requested intervention key differs")
    value = requested[key]
    if key == "inputShadowOffset":
        serialized = mapping(value, "serialized shadow offset")
        observed = serialized.get("hex")
    else:
        require(isinstance(value, (int, float)), "requested scalar is not numeric")
        observed = struct.pack("<f", float(value)).hex()
    require(
        observed == intervention.get("rawLittleEndianHex"),
        "requested intervention raw value differs",
    )


def validate(
    base_path: Path,
    retry_path: Path,
    retry2_path: Path,
    report_path: Path,
    trace_path: Path,
) -> dict[str, Any]:
    paths = {
        "basePreregistration": base_path,
        "retryPreregistration": retry_path,
        "retry2Preregistration": retry2_path,
        "applicationReport": report_path,
        "trace": trace_path,
    }
    observed_hashes = {name: sha256(path) for name, path in paths.items()}
    require(observed_hashes == EXPECTED_HASHES, "input SHA-256 identity differs")

    base = mapping(load_json(base_path, "base preregistration"), "base preregistration")
    retry = mapping(load_json(retry_path, "retry preregistration"), "retry preregistration")
    retry2 = mapping(load_json(retry2_path, "retry2 preregistration"), "retry2 preregistration")
    report = mapping(load_json(report_path, "application report"), "application report")
    trace = mapping(load_json(trace_path, "trace"), "trace")

    require(retry["runtimeOutcomeFrozenBeforeRetryDispatch"] is None, "retry outcome was not sealed")
    require(retry2["runtimeOutcomeFrozenBeforeRetryDispatch"] is None, "retry2 outcome was not sealed")
    require(report.get("executed") is True, "application matrix did not execute")
    require(report.get("material") == "regular", "report material differs")
    require(report.get("appearance") == "light", "report appearance differs")
    require(report.get("interventionCount") == 23, "report intervention count differs")
    require(report.get("executedInterventionCount") == 23, "not every intervention rendered")

    interventions = sequence(base.get("interventions"), "frozen interventions")
    records = sequence(report.get("records"), "application records")
    require(len(interventions) == len(records) == 23, "intervention record count differs")
    names = []
    for index, (intervention_value, record_value) in enumerate(zip(interventions, records)):
        intervention = mapping(intervention_value, "frozen intervention")
        record = mapping(record_value, "application record")
        require(intervention.get("index") == record.get("index") == index, "intervention index differs")
        require(intervention.get("name") == record.get("name"), "intervention name differs")
        require(record.get("executed") is True, "intervention render failed")
        require(record.get("missingInputKeys") == [], "intervention input key was missing")
        validate_requested_value(record, intervention)
        names.append(intervention["name"])
    require(report.get("interventionNames") == names, "report intervention order differs")
    for key in (
        "selectionUsesProviderReturn",
        "selectionUsesMargin",
        "selectionUsesCrop",
        "selectionUsesImageOrPixel",
    ):
        require(report.get(key) is False, f"{key} differs")

    configuration = mapping(trace.get("configuration"), "trace configuration")
    symbols = mapping(base.get("symbols"), "frozen symbols")
    wrapper_contract = mapping(symbols.get("wrapper"), "wrapper contract")
    provider_contract = mapping(symbols.get("provider"), "provider contract")
    require(configuration.get("interventionNames") == names, "trace intervention order differs")
    require(configuration.get("swiftUICoreUUID") == base["host"]["swiftUICoreUUID"], "SwiftUICore UUID differs")
    require(configuration.get("designLibraryUUID") == base["host"]["designLibraryUUID"], "DesignLibrary UUID differs")
    require(configuration.get("wrapperCodeSHA256") == wrapper_contract["codeSHA256"], "wrapper configuration differs")
    require(configuration.get("providerCodeSHA256") == provider_contract["codeSHA256"], "provider configuration differs")
    for key in (
        "capturedObjectUsedForSelection",
        "capturedReturnUsedForSelection",
        "capturedMarginUsedForSelection",
        "capturedCropUsedForSelection",
        "capturedImageUsedForSelection",
        "capturedPixelUsedForSelection",
    ):
        require(configuration.get(key) is False, f"trace {key} differs")

    modules = mapping(trace.get("modules"), "trace modules")
    require(modules["swiftUICore"]["uuid"] == base["host"]["swiftUICoreUUID"], "captured SwiftUICore differs")
    require(modules["designLibrary"]["uuid"] == base["host"]["designLibraryUUID"], "captured DesignLibrary differs")
    wrapper = mapping(trace.get("wrapper"), "captured wrapper")
    provider = mapping(trace.get("provider"), "captured provider")
    require(wrapper.get("codeSHA256") == wrapper_contract["codeSHA256"], "captured wrapper code differs")
    require(wrapper.get("function") == wrapper_contract["function"], "captured wrapper function differs")
    require(provider.get("codeSHA256") == provider_contract["codeSHA256"], "captured provider code differs")
    require(provider.get("function") == provider_contract["function"], "captured provider function differs")

    require(trace.get("status") == "finalized", "trace did not finalize")
    require(trace.get("statusBeforeFinalization") == "all-intervals-closed", "trace did not close every interval")
    require(trace.get("allIntervalsClosed") is True, "allIntervalsClosed differs")
    require(trace.get("finalIntervalCount") == 23, "final interval count differs")
    require(trace.get("finalCallCount") == 0, "provider unexpectedly ran")
    require(trace.get("finalEventCount") == 46, "marker event count differs")
    require(trace.get("finalFailureCount") == 0, "trace recorded a failure")
    require(trace.get("finalPendingCallCount") == 0, "trace retained a pending call")
    require(not sequence(trace.get("calls"), "provider calls"), "provider calls are not empty")
    require(not sequence(trace.get("failures"), "trace failures"), "trace failures are not empty")

    intervals = sequence(trace.get("intervals"), "trace intervals")
    events = sequence(trace.get("events"), "trace events")
    require(len(intervals) == 23 and len(events) == 46, "trace interval/event count differs")
    for index, (name, interval_value) in enumerate(zip(names, intervals)):
        interval = mapping(interval_value, "trace interval")
        require(interval.get("intervalIndex") == interval.get("interventionIndex") == index, "interval index differs")
        require(interval.get("interventionName") == name, "interval name differs")
        require(interval.get("status") == "closed", "interval is not closed")
        require(interval.get("callIndices") == [], "interval unexpectedly contains calls")
        require(interval.get("finalCallCount") == 0, "interval call count differs")
        require(interval.get("beforeMarkerEventIndex") == 2 * index, "before marker index differs")
        require(interval.get("afterMarkerEventIndex") == 2 * index + 1, "after marker index differs")
        for phase, event_index in (("marker-before", 2 * index), ("marker-after", 2 * index + 1)):
            event = mapping(events[event_index], "marker event")
            require(event == {"eventIndex": event_index, "kind": phase, "recordIndex": index}, "marker event differs")

    required_calls = bool(base["captureContract"]["requireAtLeastOneProviderCallPerInterval"])
    require(required_calls, "base contract did not require provider calls")
    return {
        "case22ProviderFieldMatrixLocalMacOSRetry2ValidationSchemaVersion": RESULT_SCHEMA_VERSION,
        "classification": "exact validation of a prospectively frozen intervention run whose application and marker transport passed but whose provider-call requirement failed",
        "inputs": {name: {"path": str(path), "sha256": observed_hashes[name]} for name, path in paths.items()},
        "application": {
            "interventionCount": 23,
            "executedInterventionCount": 23,
            "allRequestedValuesMatchFrozenRawWords": True,
        },
        "trace": {
            "intervalCount": 23,
            "closedIntervalCount": 23,
            "markerEventCount": 46,
            "providerCallCount": 0,
            "failureCount": 0,
            "exactWrapperAndProviderCodeAuthenticated": True,
        },
        "captureContractPassed": False,
        "failedRequirement": "requireAtLeastOneProviderCallPerInterval",
        "conclusion": "copied real glassBackground filters render after KVC intervention without re-entering SwiftUI's sdfBackdropMargin provider; provider construction or margin materialization is upstream of these CARenderer brackets",
        "fieldMappingAuthority": False,
        "productParityAuthority": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-preregistration", type=Path, required=True)
    parser.add_argument("--retry-preregistration", type=Path, required=True)
    parser.add_argument("--retry2-preregistration", type=Path, required=True)
    parser.add_argument("--application-report", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        result = validate(
            arguments.base_preregistration,
            arguments.retry_preregistration,
            arguments.retry2_preregistration,
            arguments.application_report,
            arguments.trace,
        )
    except ValueError as error:
        parser.error(str(error))
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
