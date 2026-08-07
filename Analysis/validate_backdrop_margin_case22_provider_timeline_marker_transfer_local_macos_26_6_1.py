#!/usr/bin/env python3
"""Validate the prospective timeline-marker/provider temporal transfer."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import struct
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_backdrop_margin_case22_provider_public_timeline_join as join
import validate_backdrop_margin_case22_provider_object_matrix_minimal_retry2_local_macos_26_6_1 as matrix
import validate_backdrop_margin_case22_provider_public_render_interval_transfer_local_macos_26_6_1 as public


RESULT_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
TRACE_SCHEMA_VERSION = 1
EXPECTED_BINARY_SHA256 = (
    "b9cb4068e77a61ff87794fa20a5c273e007f3ee20dd74503b1ab78839104e8dd"
)
EXPECTED_PREFLIGHT_SHA256 = (
    "f12a1cbe29629dc843cc3250a46fa686225f3c08bcf1bf1dbdf50aea913926f1"
)
EXPECTED_FAILURE_RESULT_SHA256 = (
    "01daf6b9e31cb0eacf45a250a2df605de7b10063a0b8668e422347b0db139e06"
)
FAILURE_RESULT_PATH = (
    "Analysis/backdrop_margin_case22_provider_public_render_interval_"
    "d18aca7_failure_result.json"
)
TRANSPORT_FAILURE_RESULT_SHA256 = (
    "eb48611b6c7b62bac21bb133414eacd0992992b7706bcfb71bbdfafca76362e2"
)
TRANSPORT_FAILURE_RESULT_PATH = (
    "Analysis/backdrop_margin_case22_provider_timeline_marker_"
    "ad2c061_transport_failure_result.json"
)
MAIN_UUID = "F8B0B6E3-3270-3C94-817F-B4914852D04C"
MAIN_PATH_SUFFIX = "/glass-transition-introspect-721293f"
TIMELINE_MARKER_MODULE_OFFSET = 0x8BE38
TIMELINE_MARKER_BYTE_COUNT = 0x674
TIMELINE_MARKER_CODE_SHA256 = (
    "f17ee5eb93c3732cfca195760366e9b7107fb5053d4cff519c5de3092a83fc85"
)
TIMELINE_MARKER_COUNT = 33
ZERO_F64 = b"\0" * 8
ZERO_F32 = b"\0" * 4


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


def require(condition: bool, message: str) -> None:
    matrix.require(condition, message)


def validate_preregistration(
    value: Any,
    repository_root: Path,
) -> Mapping[str, Any]:
    preregistration = mapping(value, "timeline-marker preregistration")
    require(
        preregistration.get(
            "case22ProviderTimelineMarkerTransferLocalMacOSPreregistrationSchemaVersion"
        )
        == PREREGISTRATION_SCHEMA_VERSION,
        "preregistration schema differs",
    )
    require(
        preregistration.get("runtimeOutcomeFrozenBeforeDispatch") is None,
        "runtime outcome was not frozen before dispatch",
    )
    predecessor = mapping(
        preregistration.get("rejectedPredecessor"),
        "rejected predecessor",
    )
    require(
        predecessor
        == {
            "all32RenderIntervalsClosed": True,
            "artifactDirectory": (
                "local-case22-provider-public-render-interval-d18aca7-run1"
            ),
            "captureCommit": "d18aca7fe2638d25eb347df96fe9d5d3a3428060",
            "failureResultPath": FAILURE_RESULT_PATH,
            "failureResultSHA256": EXPECTED_FAILURE_RESULT_SHA256,
            "providerCallsInsideIntervals": 0,
            "replacementRuntimeWindowChanged": True,
        },
        "rejected predecessor differs",
    )
    require(
        sha256(repository_root / FAILURE_RESULT_PATH) == EXPECTED_FAILURE_RESULT_SHA256,
        "rejected predecessor result hash differs",
    )
    transport_amendment = mapping(
        preregistration.get("transportOperationalAmendment"),
        "transport operational amendment",
    )
    require(
        transport_amendment
        == {
            "failedCaptureFinalProviderCallCount": 0,
            "failedCaptureFinalTimelineMarkerCount": 0,
            "opticalPredictionsEvaluatedBeforeCorrection": False,
            "path": TRANSPORT_FAILURE_RESULT_PATH,
            "prospectiveOpticalPredictionsUnchanged": True,
            "providerWindowUnchanged": True,
            "sha256": TRANSPORT_FAILURE_RESULT_SHA256,
        },
        "transport operational amendment differs",
    )
    transport_result_path = repository_root / TRANSPORT_FAILURE_RESULT_PATH
    require(
        sha256(transport_result_path) == TRANSPORT_FAILURE_RESULT_SHA256,
        "transport failure result hash differs",
    )
    transport_result = mapping(
        load_json(transport_result_path, "transport failure result"),
        "transport failure result",
    )
    require(
        transport_result.get(
            "providerTimelineMarkerTransportFailureResultSchemaVersion"
        )
        == 1,
        "transport failure result schema differs",
    )
    failed_transport = mapping(
        transport_result.get("capture"),
        "failed transport capture",
    )
    require(
        failed_transport.get("finalProviderCallCount") == 0
        and failed_transport.get("finalTimelineMarkerCount") == 0
        and failed_transport.get("opticalPredictionsEvaluated") is False,
        "failed transport crossed an optical boundary",
    )
    transport_correction = mapping(
        transport_result.get("correction"),
        "transport correction",
    )
    require(
        transport_correction.get("importAtExactMainEntryAfterDyldLoad") is True
        and transport_correction.get("captureSelectionChanged") is False
        and transport_correction.get("providerWindowChanged") is False
        and transport_correction.get("opticalPredictionsChanged") is False,
        "transport correction changed capture semantics",
    )
    marker = mapping(
        preregistration.get("timelineMarkerBoundary"),
        "timeline marker boundary",
    )
    require(
        marker
        == {
            "byteCount": TIMELINE_MARKER_BYTE_COUNT,
            "codeSHA256": TIMELINE_MARKER_CODE_SHA256,
            "markerCount": TIMELINE_MARKER_COUNT,
            "moduleOffset": TIMELINE_MARKER_MODULE_OFFSET,
            "providerCaptureDisabledAtMarkerIndex": 32,
            "providerCaptureEnabledAfterMarkerIndex": 0,
            "sampleIndexRule": "zero-based marker ordinal",
        },
        "timeline marker boundary differs",
    )
    predictions = mapping(
        preregistration.get("prospectivePredictions"),
        "prospective predictions",
    )
    require(
        predictions
        == {
            "all18LoadedFieldPredictionsMatchForSelectedCalls": True,
            "allMatchedProviderReturnsAreExactPositiveZero": True,
            "allNonmatchingCallsInEachOpenedBatchMatchZeroSelectorWords": True,
            "exactlyOneFullSignatureMatchPerMarkerBatchSamples1Through31": True,
            "marker32EndpointMatchCountIsExploratory": True,
            "uniqueFullSignatureMatchGloballySamples1Through31": True,
        },
        "prospective predictions differ",
    )
    frozen = sequence(
        mapping(preregistration.get("frozenImplementation"), "implementation").get(
            "files"
        ),
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
        "LG_CASE22_PROVIDER_OBJECT_MATRIX_MINIMAL_TRACE_OUTPUT",
        None,
    )
    require(
        trace_path is not None
        and trace_path.endswith("/provider-timeline-marker-trace.json"),
        "trace output environment differs",
    )
    require(environment == public.EXPECTED_ENVIRONMENT, "capture environment differs")
    return lines[0]


def validate_marker_symbol(
    value: Any,
    module: Mapping[str, Any],
) -> Mapping[str, Any]:
    record = mapping(value, "timeline marker function")
    record_module = mapping(record.get("module"), "timeline marker record module")
    payload = bytes.fromhex(str(record.get("hex", "")))
    require(module.get("valid") is True, "timeline marker module is invalid")
    require(module.get("uuid") == MAIN_UUID, "timeline marker module UUID differs")
    require(
        isinstance(module.get("loadAddress"), int) and module["loadAddress"] > 0,
        "timeline marker module load address differs",
    )
    require(
        str(module.get("path", "")).endswith(MAIN_PATH_SUFFIX),
        "timeline marker module path differs",
    )
    require(
        record_module.get("uuid") == MAIN_UUID
        and record_module.get("loadAddress") == module["loadAddress"]
        and str(record_module.get("path", "")).endswith(MAIN_PATH_SUFFIX),
        "timeline marker record module differs",
    )
    require(
        isinstance(record.get("function"), str) and bool(record["function"]),
        "timeline marker function presentation is absent",
    )
    require(
        record.get("symbolStart")
        == module["loadAddress"] + TIMELINE_MARKER_MODULE_OFFSET,
        "timeline marker module offset differs",
    )
    require(record.get("symbolOffset") == 0, "timeline marker symbol offset differs")
    require(
        record.get("symbolByteCount") == TIMELINE_MARKER_BYTE_COUNT,
        "timeline marker byte count differs",
    )
    require(
        len(payload) == TIMELINE_MARKER_BYTE_COUNT, "timeline marker code width differs"
    )
    require(
        record.get("codeSHA256") == TIMELINE_MARKER_CODE_SHA256,
        "timeline marker recorded code hash differs",
    )
    require(
        hashlib.sha256(payload).hexdigest() == TIMELINE_MARKER_CODE_SHA256,
        "timeline marker code hash differs",
    )
    return record


def validate_marker_frame(
    value: Any,
    symbol: Mapping[str, Any],
    thread_id: Any,
    label: str,
) -> None:
    frame = mapping(value, label)
    module = mapping(frame.get("module"), f"{label} module")
    require(frame.get("pc") == symbol["symbolStart"], f"{label} PC differs")
    require(frame.get("symbolStart") == symbol["symbolStart"], f"{label} start differs")
    require(frame.get("symbolOffset") == 0, f"{label} offset differs")
    require(module.get("uuid") == MAIN_UUID, f"{label} module differs")
    require(isinstance(thread_id, int), f"{label} thread differs")


def validate_trace(value: Any) -> tuple[dict[str, Any], Sequence[Mapping[str, Any]]]:
    trace = mapping(value, "timeline-marker trace")
    require(
        trace.get(
            "case22ProviderTimelineMarkerTransferLocalMacOSLldbTraceSchemaVersion"
        )
        == TRACE_SCHEMA_VERSION,
        "timeline-marker trace schema differs",
    )
    configuration = mapping(trace.get("configuration"), "trace configuration")
    expected_configuration = {
        "mainUUID": MAIN_UUID,
        "timelineMarkerModuleOffset": TIMELINE_MARKER_MODULE_OFFSET,
        "timelineMarkerByteCount": TIMELINE_MARKER_BYTE_COUNT,
        "timelineMarkerCodeSHA256": TIMELINE_MARKER_CODE_SHA256,
        "timelineMarkerCount": TIMELINE_MARKER_COUNT,
        "providerCaptureEnabledAfterMarkerIndex": 0,
        "providerCaptureDisabledAtMarkerIndex": 32,
        "markerOrdinalUsedForSampleSelection": True,
        "capturedPublicInputUsedForSelection": False,
        "capturedTimelineStateUsedForSelection": False,
    }
    for key, expected in expected_configuration.items():
        require(configuration.get(key) == expected, f"trace {key} differs")

    base_projection = copy.deepcopy(trace)
    base_projection["breakpoints"] = [
        value_item
        for value_item in sequence(trace.get("breakpoints"), "trace breakpoints")
        if mapping(value_item, "breakpoint").get("name") != "timeline_marker"
    ]
    provider_summary = matrix.validate_trace(base_projection)
    calls = sequence(trace.get("calls"), "provider calls")

    marker_module = mapping(
        trace.get("timelineMarkerModule"),
        "timeline marker module",
    )
    marker_symbol = validate_marker_symbol(
        trace.get("timelineMarkerFunction"),
        marker_module,
    )
    breakpoints = sequence(trace.get("breakpoints"), "trace breakpoints")
    marker_breakpoints = [
        mapping(value_item, "timeline marker breakpoint")
        for value_item in breakpoints
        if mapping(value_item, "breakpoint").get("name") == "timeline_marker"
    ]
    require(len(breakpoints) == 7, "timeline-marker breakpoint count differs")
    require(len(marker_breakpoints) == 1, "timeline marker breakpoint differs")
    require(
        marker_breakpoints[0].get("address") == marker_symbol["symbolStart"],
        "timeline marker breakpoint address differs",
    )

    markers = sequence(trace.get("timelineMarkers"), "timeline markers")
    events = sequence(trace.get("timelineEvents"), "timeline events")
    require(len(markers) == TIMELINE_MARKER_COUNT, "timeline marker count differs")
    require(
        len(events) == TIMELINE_MARKER_COUNT + 2 * len(calls),
        "timeline event count differs",
    )
    for index, event_value in enumerate(events):
        event = mapping(event_value, f"timeline event {index}")
        require(
            event.get("eventIndex") == index, f"timeline event {index} index differs"
        )

    previous_end = 0
    marker_event_indices: list[int] = []
    for index, marker_value in enumerate(markers):
        marker = mapping(marker_value, f"timeline marker {index}")
        require(
            marker.get("markerIndex") == index, f"timeline marker {index} index differs"
        )
        require(
            marker.get("sampleIndex") == index,
            f"timeline marker {index} sample differs",
        )
        require(
            marker.get("precedingCompletedCallStartIndex") == previous_end,
            f"timeline marker {index} call start differs",
        )
        end = marker.get("precedingCompletedCallEndIndexExclusive")
        require(
            isinstance(end, int) and previous_end <= end <= len(calls),
            f"timeline marker {index} call end differs",
        )
        event_index = marker.get("eventIndex")
        require(isinstance(event_index, int), f"timeline marker {index} event differs")
        event = mapping(events[event_index], f"timeline marker {index} event")
        require(
            event.get("kind") == "timeline-marker"
            and event.get("recordIndex") == index,
            f"timeline marker {index} event mapping differs",
        )
        validate_marker_frame(
            marker.get("frame"),
            marker_symbol,
            marker.get("threadID"),
            f"timeline marker {index} frame",
        )
        marker_event_indices.append(event_index)
        if index == 0:
            require(
                (previous_end, end) == (0, 0), "marker zero captured provider calls"
            )
        else:
            for call_index in range(previous_end, end):
                call = mapping(calls[call_index], f"provider call {call_index}")
                entry = call.get("timelineEntryEventIndex")
                complete = call.get("timelineCompletionEventIndex")
                require(
                    isinstance(entry, int) and isinstance(complete, int),
                    f"provider call {call_index} timeline events differ",
                )
                require(
                    marker_event_indices[index - 1] < entry < complete < event_index,
                    f"provider call {call_index} lies outside marker batch {index}",
                )
                require(
                    mapping(events[entry], f"provider call {call_index} entry event")
                    == {
                        "eventIndex": entry,
                        "kind": "provider-call-entry",
                        "recordIndex": call_index,
                    },
                    f"provider call {call_index} entry event differs",
                )
                require(
                    mapping(
                        events[complete], f"provider call {call_index} complete event"
                    )
                    == {
                        "eventIndex": complete,
                        "kind": "provider-call-complete",
                        "recordIndex": call_index,
                    },
                    f"provider call {call_index} complete event differs",
                )
        previous_end = end
    require(previous_end == len(calls), "provider calls exist outside marker batches")
    require(
        trace.get("finalTimelineMarkerCount") == TIMELINE_MARKER_COUNT,
        "final timeline marker count differs",
    )
    require(
        trace.get("finalTimelineEventCount") == len(events),
        "final timeline event count differs",
    )
    require(
        trace.get("finalMarkerAssignedCallCount") == len(calls),
        "final marker-assigned call count differs",
    )
    require(
        trace.get("selectedCallsiteEnabledAtFinalization") is False,
        "provider capture remained enabled after marker 32",
    )
    return provider_summary, [mapping(value_item, "marker") for value_item in markers]


def provider_loaded_fields_match(raw: bytes, inputs: Mapping[str, Any]) -> None:
    shadow_offset = mapping(inputs.get("inputShadowOffset"), "inputShadowOffset")
    require(
        raw[0x008:0x018] == bytes.fromhex(str(shadow_offset.get("hex", ""))),
        "provider shadow offset differs",
    )
    require(
        raw[0x018:0x020]
        == join.binary64_word(inputs.get("inputShadowAmount"), 1.0, "shadow amount"),
        "provider shadow amount differs",
    )
    require(
        raw[0x098:0x0A0]
        == join.binary64_word(inputs.get("inputBlurRadius"), 2.0, "blur radius"),
        "provider blur radius differs",
    )
    inner = join.binary64_word(
        inputs.get("inputInnerRefractionAmount"),
        1.0,
        "inner refraction amount",
    )
    require(raw[0x0E8:0x0F0] == inner, "provider inner refraction differs")
    require(
        raw[0x0E8:0x0F0]
        == join.binary64_word(inputs.get("inputShadowAmount"), -0.8, "shadow scale"),
        "provider negative shadow scaling differs",
    )
    bleed = join.binary64_word(
        inputs.get("inputBleedAmount"),
        1.0,
        "bleed amount",
    )
    require(raw[0x160:0x168] == bleed, "provider bleed amount differs")
    require(
        raw[0x160:0x168]
        == join.binary64_word(inputs.get("inputBleedHeight"), 1.0, "bleed height"),
        "provider bleed height differs",
    )
    for offset in join.ZERO_F64_OFFSETS:
        require(
            raw[offset : offset + 8] == ZERO_F64, f"provider +{offset:#x} is not +0"
        )
    for offset in join.ZERO_F32_OFFSETS:
        require(
            raw[offset : offset + 4] == ZERO_F32, f"provider +{offset:#x} is not +0"
        )


def validate_predictions(
    trace_value: Any,
    timeline_value: Any,
    markers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    trace = mapping(trace_value, "trace")
    calls = sequence(trace.get("calls"), "provider calls")
    timeline = mapping(timeline_value, "timeline")
    dynamic = mapping(
        timeline.get("dynamicBackgroundUniforms"),
        "dynamic background uniforms",
    )
    records = sequence(dynamic.get("records"), "dynamic records")
    require(len(records) == 32, "dynamic record count differs")
    record_by_sample: dict[int, Mapping[str, Any]] = {}
    for value_record in records:
        record = mapping(value_record, "dynamic record")
        sample_index = record.get("sampleIndex")
        require(
            isinstance(sample_index, int) and 1 <= sample_index <= 32,
            "dynamic sample index differs",
        )
        require(sample_index not in record_by_sample, "dynamic sample index repeats")
        record_by_sample[sample_index] = record
    require(set(record_by_sample) == set(range(1, 33)), "dynamic sample set differs")

    object_raw = [
        join.object_raw(
            mapping(value_call, f"provider call {index}"), f"provider call {index}"
        )
        for index, value_call in enumerate(calls)
    ]
    selected: list[dict[str, Any]] = []
    for sample_index in range(1, 32):
        marker = markers[sample_index]
        start = int(marker["precedingCompletedCallStartIndex"])
        end = int(marker["precedingCompletedCallEndIndexExclusive"])
        inputs = join.input_values(
            record_by_sample[sample_index],
            f"dynamic sample {sample_index}",
        )
        words = join.signature_words(inputs)
        batch_counts = [
            join.signature_match_count(object_raw[index], words)
            for index in range(start, end)
        ]
        matches = [
            start + index
            for index, count in enumerate(batch_counts)
            if count == len(join.SIGNATURE)
        ]
        require(
            len(matches) == 1, f"sample {sample_index} full batch match count differs"
        )
        require(
            all(count in (0, len(join.SIGNATURE)) for count in batch_counts),
            f"sample {sample_index} has a partial batch signature collision",
        )
        global_matches = [
            index
            for index, raw in enumerate(object_raw)
            if join.signature_match_count(raw, words) == len(join.SIGNATURE)
        ]
        require(
            global_matches == matches,
            f"sample {sample_index} global signature uniqueness differs",
        )
        call_index = matches[0]
        provider_loaded_fields_match(object_raw[call_index], inputs)
        call = mapping(calls[call_index], f"provider call {call_index}")
        require(
            call.get("returnF64RawLittleEndianHex") == ZERO_F64.hex(),
            f"sample {sample_index} provider return differs",
        )
        selected.append(
            {
                "sampleIndex": sample_index,
                "markerBatchCallStartIndex": start,
                "markerBatchCallEndIndexExclusive": end,
                "markerBatchCallCount": end - start,
                "matchedProviderCallIndex": call_index,
                "partialSignatureMatchCount": sum(
                    1 for count in batch_counts if 0 < count < len(join.SIGNATURE)
                ),
                "loadedFieldPredictionCount": 18,
                "returnRawLittleEndianHex": ZERO_F64.hex(),
            }
        )

    endpoint_inputs = join.input_values(record_by_sample[32], "dynamic sample 32")
    endpoint_words = join.signature_words(endpoint_inputs)
    endpoint_marker = markers[32]
    endpoint_start = int(endpoint_marker["precedingCompletedCallStartIndex"])
    endpoint_end = int(endpoint_marker["precedingCompletedCallEndIndexExclusive"])
    endpoint_counts = [
        join.signature_match_count(object_raw[index], endpoint_words)
        for index in range(endpoint_start, endpoint_end)
    ]
    endpoint_histogram = Counter(endpoint_counts)
    return {
        "openedSampleCount": len(selected),
        "selectedCalls": selected,
        "distinctSelectedProviderCallCount": len(
            {record["matchedProviderCallIndex"] for record in selected}
        ),
        "endpointSample32Exploratory": {
            "markerBatchCallStartIndex": endpoint_start,
            "markerBatchCallEndIndexExclusive": endpoint_end,
            "signatureMatchHistogram": [
                {
                    "matchingSignatureWordCount": count,
                    "providerCallCount": endpoint_histogram[count],
                }
                for count in sorted(endpoint_histogram)
            ],
            "fullSignatureMatchedProviderCallIndices": [
                endpoint_start + index
                for index, count in enumerate(endpoint_counts)
                if count == len(join.SIGNATURE)
            ],
            "usedAsAcceptanceGate": False,
        },
    }


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
        str(mapping(value_item, "frozen file")["path"]): str(
            mapping(value_item, "frozen file")["sha256"]
        )
        for value_item in mapping(
            preregistration.get("frozenImplementation"),
            "implementation",
        )["files"]
    }
    capture_path = (
        "Analysis/capture_backdrop_margin_case22_provider_timeline_marker_"
        "transfer_local_macos_26_6_1_lldb.py"
    )
    validator_path = (
        "Analysis/validate_backdrop_margin_case22_provider_timeline_marker_"
        "transfer_local_macos_26_6_1.py"
    )
    runner_path = (
        "Analysis/run_backdrop_margin_case22_provider_timeline_marker_"
        "transfer_local_macos_26_6_1.sh"
    )
    capture_commit = validate_context(
        paths["captureContext"],
        preregistration_path,
        frozen_files[capture_path],
        frozen_files[validator_path],
        frozen_files[runner_path],
    )
    preflight = public.validate_preflight(load_json(paths["preflight"], "preflight"))
    require(
        paths["lldbExitStatus"].read_text(encoding="utf-8").strip() == "0",
        "LLDB process did not exit zero",
    )
    trace = load_json(paths["trace"], "trace")
    timeline = load_json(paths["timeline"], "timeline")
    provider_summary, markers = validate_trace(trace)
    timeline_summary = matrix.validate_timeline(timeline, artifact_directory)
    prediction_summary = validate_predictions(trace, timeline, markers)
    artifact_hashes = {
        label: sha256(path)
        for label, path in paths.items()
        if label != "captureContext" or path.is_file()
    }
    return {
        "case22ProviderTimelineMarkerTransferLocalMacOSValidationSchemaVersion": (
            RESULT_SCHEMA_VERSION
        ),
        "classification": (
            "prospective exact public timeline-marker batch transfer for "
            "samples 1 through 31; endpoint 32 remains exploratory"
        ),
        "captureCommit": capture_commit,
        "captureContractPassed": True,
        "preflight": preflight,
        "providerTrace": provider_summary,
        "timeline": timeline_summary,
        "predictions": prediction_summary,
        "artifactSHA256": artifact_hashes,
        "authority": {
            "authenticatedMarkerBatchTemporalJoinEstablishedForSamples1Through31": True,
            "sameProfilePublicProviderLoadedFieldsTransferredProspectively": True,
            "freshMaterialAppearanceGeometryProfileTransferEstablished": False,
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
    except (OSError, ValueError, KeyError, struct.error) as error:
        parser.error(str(error))
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
