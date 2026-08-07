#!/usr/bin/env python3
"""Validate the fresh active-Retina timeline-marker/provider transfer."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_backdrop_margin_case22_provider_public_timeline_join as join
import validate_backdrop_margin_case22_provider_object_matrix_minimal_retry2_local_macos_26_6_1 as matrix
import validate_backdrop_margin_case22_provider_public_render_interval_transfer_local_macos_26_6_1 as public
import validate_backdrop_margin_case22_provider_timeline_marker_transfer_local_macos_26_6_1 as predecessor


RESULT_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
TRACE_SCHEMA_VERSION = 1
FAILURE_RESULT_PATH = (
    "Analysis/backdrop_margin_case22_provider_timeline_marker_"
    "28817f3_failure_result.json"
)
FAILURE_RESULT_SHA256 = (
    "f01ae11f8f1ff47ca2eb80648618eb989f39c266f86caed9b6925548298c02f4"
)
CAPTURE_PATH = (
    "Analysis/capture_backdrop_margin_case22_provider_timeline_marker_"
    "transfer_local_macos_26_6_1_lldb.py"
)
VALIDATOR_PATH = (
    "Analysis/validate_backdrop_margin_case22_provider_timeline_marker_"
    "retina_transfer_local_macos_26_6_1.py"
)
RUNNER_PATH = (
    "Analysis/run_backdrop_margin_case22_provider_timeline_marker_"
    "retina_transfer_local_macos_26_6_1.sh"
)
ZERO_F64 = bytes(8)

F64_PUBLIC_FIELDS = (
    (0x018, "inputShadowAmount", 1.0),
    (0x038, "inputShadowRadius", 1.0),
    (0x090, "inputShadowVibrancyContribution", 1.0),
    (0x098, "inputBlurRadius", 2.0),
    (0x0A0, "inputBlurDistance0", 1.0),
    (0x0A8, "inputBlurDistance1", 1.0),
    (0x0C0, "inputBlurDistance4", 1.0),
    (0x0E8, "inputInnerRefractionAmount", 1.0),
    (0x0F8, "inputOuterRefractionAmount", 1.0),
    (0x160, "inputBleedAmount", 1.0),
)
F64_ZERO_FIELDS = (0x028, 0x0B0, 0x0B8)
F32_PUBLIC_FIELDS = (
    (0x088, "inputShadowOpacity"),
    (0x110, "inputRefractionOpacity"),
    (0x178, "inputBleedOpacity"),
)


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


def numeric(value: Any, label: str) -> float:
    require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"{label} is not numeric",
    )
    result = float(value)
    require(math.isfinite(result), f"{label} is not finite")
    return result


def validate_preregistration(
    value: Any,
    repository_root: Path,
) -> Mapping[str, Any]:
    preregistration = mapping(value, "Retina-transfer preregistration")
    require(
        preregistration.get(
            "case22ProviderTimelineMarkerRetinaTransferLocalMacOSPreregistrationSchemaVersion"
        )
        == PREREGISTRATION_SCHEMA_VERSION,
        "preregistration schema differs",
    )
    require(
        preregistration.get("runtimeOutcomeFrozenBeforeDispatch") is None,
        "runtime outcome was not frozen before dispatch",
    )
    rejected = mapping(
        preregistration.get("rejectedPredecessor"),
        "rejected predecessor",
    )
    require(
        rejected.get("captureCommit")
        == "28817f34f60207aa3466118835e2166b2ad249d9"
        and rejected.get("validationExitStatus") == 2
        and rejected.get("frozenGateRemainsFailed") is True
        and rejected.get("failureResultPath") == FAILURE_RESULT_PATH
        and rejected.get("failureResultSHA256") == FAILURE_RESULT_SHA256,
        "rejected predecessor differs",
    )
    failure_path = repository_root / FAILURE_RESULT_PATH
    require(
        sha256(failure_path) == FAILURE_RESULT_SHA256,
        "rejected predecessor result hash differs",
    )
    failure = mapping(load_json(failure_path, "failure result"), "failure result")
    failure_authority = mapping(
        failure.get("authority"), "failure result authority"
    )
    require(
        failure_authority.get("prospectiveZeroFieldAndReturnTransferPassed")
        is False
        and failure_authority.get("structuralLastCallMarkerJoinEstablishedRetrospectively")
        is True,
        "failure result authority differs",
    )
    selection = mapping(
        preregistration.get("selectionPolicy"), "selection policy"
    )
    require(
        selection
        == {
            "capturedObjectOrOutputMaySelectCall": False,
            "markerSelection": "exact main-module function entry and zero-based ordinal only",
            "sampleIndices": list(range(1, 33)),
            "selectedProviderCall": "last structurally completed call in the preceding marker interval",
            "selectionFrozenBeforeDispatch": True,
        },
        "selection policy differs",
    )
    predictions = mapping(
        preregistration.get("prospectivePredictions"),
        "prospective predictions",
    )
    require(
        predictions
        == {
            "all32SelectedCallsMatchAll18LoadedFieldsBitwise": True,
            "all32SelectedCallsMatchFourWordSignatureUniquely": True,
            "all32SelectedReturnsMatchExactPublicLaw": True,
            "allNoninitialCapturedCallsMatchExactObjectReturnLaw": True,
            "initialCapturedCallReturnsExactPositiveZero": True,
            "returnLaw": "abs(inputShadowOffset.y) + abs(inputShadowAmount)",
        },
        "prospective predictions differ",
    )
    files = sequence(
        mapping(
            preregistration.get("frozenImplementation"),
            "frozen implementation",
        ).get("files"),
        "frozen files",
    )
    for item_value in files:
        item = mapping(item_value, "frozen file")
        relative = str(item.get("path", ""))
        require(relative.startswith("Analysis/"), "frozen path escapes Analysis")
        path = repository_root / relative
        require(path.is_file(), f"frozen file {relative} is absent")
        require(sha256(path) == item.get("sha256"), f"{relative} hash differs")
    return preregistration


def validate_provider_trace_structure(
    trace_value: Any,
) -> tuple[dict[str, Any], Sequence[Mapping[str, Any]]]:
    trace = mapping(trace_value, "Retina-transfer trace")
    configuration = mapping(trace.get("configuration"), "trace configuration")
    require(
        trace.get("case22ProviderObjectMatrixMinimalLocalMacOSLldbTraceSchemaVersion")
        == 1,
        "base trace schema differs",
    )
    require(
        trace.get(
            "case22ProviderTimelineMarkerTransferLocalMacOSLldbTraceSchemaVersion"
        )
        == TRACE_SCHEMA_VERSION,
        "timeline-marker trace schema differs",
    )
    expected_configuration = {
        "maximumCallCount": matrix.MAXIMUM_CALL_COUNT,
        "previousMaximumCallCount": 512,
        "boundChangeOnly": True,
        "activeBreakpointCountPerSelectedCall": 6,
        "perSelectedCallMaximumStopCount": 6,
        "unrelatedWrapperOrProviderCallbacksArmed": False,
        "mainUUID": predecessor.MAIN_UUID,
        "timelineMarkerModuleOffset": predecessor.TIMELINE_MARKER_MODULE_OFFSET,
        "timelineMarkerByteCount": predecessor.TIMELINE_MARKER_BYTE_COUNT,
        "timelineMarkerCodeSHA256": predecessor.TIMELINE_MARKER_CODE_SHA256,
        "timelineMarkerCount": predecessor.TIMELINE_MARKER_COUNT,
        "providerCaptureEnabledAfterMarkerIndex": 0,
        "providerCaptureDisabledAtMarkerIndex": 32,
        "markerOrdinalUsedForSampleSelection": True,
        "capturedPublicInputUsedForSelection": False,
        "capturedTimelineStateUsedForSelection": False,
    }
    for key, expected in expected_configuration.items():
        require(configuration.get(key) == expected, f"trace {key} differs")
    for key in (
        "capturedObjectUsedForSelection",
        "capturedReturnUsedForSelection",
        "capturedMarginUsedForSelection",
        "capturedCropUsedForSelection",
        "capturedImageUsedForSelection",
        "capturedPixelUsedForSelection",
        "capturedValueUsedToSelectNewBound",
    ):
        require(configuration.get(key) is False, f"trace {key} differs")

    modules = mapping(trace.get("modules"), "trace modules")
    require(
        mapping(modules.get("swiftUICore"), "SwiftUICore module").get("uuid")
        == matrix.SWIFTUICORE_UUID,
        "SwiftUICore UUID differs",
    )
    require(
        mapping(modules.get("designLibrary"), "DesignLibrary module").get("uuid")
        == matrix.DESIGN_LIBRARY_UUID,
        "DesignLibrary UUID differs",
    )
    caller = matrix.validate_symbol(
        trace.get("caller"),
        matrix.EXPECTED_SYMBOLS["caller"],
        matrix.SWIFTUICORE_UUID,
        "caller",
    )
    group = matrix.validate_symbol(
        trace.get("group"),
        matrix.EXPECTED_SYMBOLS["group"],
        matrix.SWIFTUICORE_UUID,
        "Group",
    )
    wrapper = matrix.validate_symbol(
        trace.get("wrapper"),
        matrix.EXPECTED_SYMBOLS["wrapper"],
        matrix.SWIFTUICORE_UUID,
        "wrapper",
    )
    provider = matrix.validate_symbol(
        trace.get("provider"),
        matrix.EXPECTED_SYMBOLS["provider"],
        matrix.DESIGN_LIBRARY_UUID,
        "provider",
    )
    require(caller.get("symbolOffset") == 5760, "caller selected offset differs")
    require(
        bytes.fromhex(str(caller.get("hex", "")))[5760:5764].hex()
        == "5526e997",
        "caller Group call instruction differs",
    )

    marker_module = mapping(
        trace.get("timelineMarkerModule"), "timeline marker module"
    )
    marker_symbol = predecessor.validate_marker_symbol(
        trace.get("timelineMarkerFunction"), marker_module
    )
    breakpoints = sequence(trace.get("breakpoints"), "trace breakpoints")
    require(len(breakpoints) == 7, "trace breakpoint count differs")
    require(
        {mapping(value, "breakpoint").get("name") for value in breakpoints}
        == {
            "selected_callsite",
            "wrapper_entry",
            "provider_entry",
            "provider_return",
            "group_return",
            "selected_caller_return",
            "timeline_marker",
        },
        "trace breakpoint names differ",
    )
    marker_breakpoint = [
        mapping(value, "marker breakpoint")
        for value in breakpoints
        if mapping(value, "breakpoint").get("name") == "timeline_marker"
    ]
    require(
        len(marker_breakpoint) == 1
        and marker_breakpoint[0].get("address") == marker_symbol["symbolStart"],
        "timeline marker breakpoint differs",
    )

    calls = sequence(trace.get("calls"), "provider calls")
    require(
        2 <= len(calls) < matrix.MAXIMUM_CALL_COUNT,
        "provider call count violates the frozen bound",
    )
    objects: list[bytes] = []
    returns: list[bytes] = []
    thread_ids: set[int] = set()
    for index, call_value in enumerate(calls):
        call = mapping(call_value, f"provider call {index}")
        require(call.get("callIndex") == index, f"provider call {index} index differs")
        wrapper_address = call.get("wrapperObjectAddress")
        provider_address = call.get("providerObjectAddress")
        require(
            isinstance(wrapper_address, int) and isinstance(provider_address, int),
            f"provider call {index} address differs",
        )
        require(
            provider_address == wrapper_address + 16
            and call.get("providerObjectOffsetFromWrapper") == 16,
            f"provider call {index} object offset differs",
        )
        wrapper_raw = matrix.validate_snapshot(
            call.get("wrapperEntryObject"),
            provider_address,
            f"provider call {index} wrapper snapshot",
        )
        entry_raw = matrix.validate_snapshot(
            call.get("providerEntryObject"),
            provider_address,
            f"provider call {index} entry snapshot",
        )
        return_raw = matrix.validate_snapshot(
            call.get("returnObject"),
            provider_address,
            f"provider call {index} return snapshot",
        )
        require(
            wrapper_raw == entry_raw == return_raw,
            f"provider call {index} object changed",
        )
        require(
            call.get("providerEntryMatchesWrapperObjectBitwise") is True
            and call.get("objectChanged") is False,
            f"provider call {index} object flags differ",
        )
        raw_v0 = bytes.fromhex(str(call.get("returnV0RawLittleEndianHex", "")))
        raw_f64 = bytes.fromhex(str(call.get("returnF64RawLittleEndianHex", "")))
        group_v0 = bytes.fromhex(
            str(call.get("groupReturnV0RawLittleEndianHex", ""))
        )
        require(
            len(raw_v0) == 16
            and len(raw_f64) == 8
            and raw_v0[:8] == raw_f64
            and raw_v0 == group_v0,
            f"provider call {index} return join differs",
        )
        require(
            call.get("providerReturnMatchesGroupBitwise") is True,
            f"provider call {index} Group join flag differs",
        )
        matrix.validate_frame(
            call.get("wrapperEntryFrame"), wrapper, 0, f"provider call {index} wrapper"
        )
        matrix.validate_frame(
            call.get("providerEntryFrame"), provider, 0, f"provider call {index} provider"
        )
        matrix.validate_frame(
            call.get("wrapperReturnFrame"),
            wrapper,
            104,
            f"provider call {index} wrapper return",
        )
        matrix.validate_frame(
            call.get("groupCallerFrame"), group, 620, f"provider call {index} Group caller"
        )
        matrix.validate_frame(
            call.get("groupReturnFrame"), group, 620, f"provider call {index} Group return"
        )
        require(isinstance(call.get("threadID"), int), f"provider call {index} thread differs")
        thread_ids.add(call["threadID"])
        objects.append(entry_raw)
        returns.append(raw_f64)

    require(trace.get("status") == "finalized", "trace did not finalize")
    require(
        trace.get("statusBeforeFinalization") == "between-selected-calls",
        "trace did not finish between calls",
    )
    require(not sequence(trace.get("failures"), "trace failures"), "trace contains failures")
    for key in (
        "finalCallCount",
        "finalSelectedCallerCount",
        "finalProviderEnteredCallCount",
        "finalReturnedCallCount",
        "finalGroupLinkedCallCount",
        "finalUnchangedObjectCount",
    ):
        require(trace.get(key) == len(calls), f"trace {key} differs")
    require(trace.get("finalPendingThreadCount") == 0, "trace has a pending call")
    require(
        trace.get("finalActiveSelectedCallerCount") == 0,
        "trace has an active selected caller",
    )
    require(trace.get("finalFailureCount") == 0, "trace failure count differs")

    events = sequence(trace.get("timelineEvents"), "timeline events")
    markers = sequence(trace.get("timelineMarkers"), "timeline markers")
    require(
        len(markers) == predecessor.TIMELINE_MARKER_COUNT,
        "timeline marker count differs",
    )
    require(
        len(events) == predecessor.TIMELINE_MARKER_COUNT + 2 * len(calls),
        "timeline event count differs",
    )
    for index, event_value in enumerate(events):
        require(
            mapping(event_value, f"timeline event {index}").get("eventIndex")
            == index,
            f"timeline event {index} index differs",
        )
    previous_end = 0
    marker_event_indices: list[int] = []
    normalized_markers: list[Mapping[str, Any]] = []
    for index, marker_value in enumerate(markers):
        marker = mapping(marker_value, f"timeline marker {index}")
        normalized_markers.append(marker)
        require(
            marker.get("markerIndex") == index
            and marker.get("sampleIndex") == index,
            f"timeline marker {index} identity differs",
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
        require(
            mapping(events[event_index], f"timeline marker {index} event")
            == {
                "eventIndex": event_index,
                "kind": "timeline-marker",
                "recordIndex": index,
            },
            f"timeline marker {index} event mapping differs",
        )
        predecessor.validate_marker_frame(
            marker.get("frame"),
            marker_symbol,
            marker.get("threadID"),
            f"timeline marker {index} frame",
        )
        marker_event_indices.append(event_index)
        if index == 0:
            require((previous_end, end) == (0, 0), "marker zero captured calls")
        else:
            for call_index in range(previous_end, end):
                call = mapping(calls[call_index], f"provider call {call_index}")
                entry = call.get("timelineEntryEventIndex")
                complete = call.get("timelineCompletionEventIndex")
                require(
                    isinstance(entry, int)
                    and isinstance(complete, int)
                    and marker_event_indices[index - 1]
                    < entry
                    < complete
                    < event_index,
                    f"provider call {call_index} lies outside marker batch {index}",
                )
                require(
                    mapping(events[entry], f"provider call {call_index} entry")
                    == {
                        "eventIndex": entry,
                        "kind": "provider-call-entry",
                        "recordIndex": call_index,
                    }
                    and mapping(events[complete], f"provider call {call_index} complete")
                    == {
                        "eventIndex": complete,
                        "kind": "provider-call-complete",
                        "recordIndex": call_index,
                    },
                    f"provider call {call_index} event mapping differs",
                )
        previous_end = end
    require(previous_end == len(calls), "provider calls exist outside marker batches")
    require(
        trace.get("finalTimelineMarkerCount") == len(markers)
        and trace.get("finalTimelineEventCount") == len(events)
        and trace.get("finalMarkerAssignedCallCount") == len(calls),
        "final timeline counts differ",
    )
    require(
        trace.get("selectedCallsiteEnabledAtFinalization") is False,
        "provider capture remained enabled",
    )

    require(returns[0] == ZERO_F64, "initial captured call is not exact positive zero")
    object_law_matches = 0
    for index, (raw, observed) in enumerate(zip(objects[1:], returns[1:]), start=1):
        axis_x, axis_y = struct.unpack_from("<dd", raw, 0x008)
        shape_radius = struct.unpack_from("<d", raw, 0x018)[0]
        shape_inset = raw[0x028:0x030]
        require(shape_inset == ZERO_F64, f"provider call {index} shape inset differs")
        expected = struct.pack(
            "<d", max(abs(axis_x), abs(axis_y)) + abs(shape_radius)
        )
        require(observed == expected, f"provider call {index} object return law differs")
        object_law_matches += 1
    return (
        {
            "callCount": len(calls),
            "threadCount": len(thread_ids),
            "distinctProviderObjectCount": len(set(objects)),
            "distinctProviderReturnCount": len(set(returns)),
            "unchangedProviderObjectCount": len(calls),
            "providerGroupLinkedCallCount": len(calls),
            "initialPositiveZeroReturnCount": 1,
            "noninitialExactObjectReturnLawCount": object_law_matches,
            "failureCount": 0,
            "pendingCallCount": 0,
        },
        normalized_markers,
    )


def provider_loaded_fields_match(raw: bytes, inputs: Mapping[str, Any]) -> None:
    require(len(raw) == matrix.OBJECT_BYTE_COUNT, "provider object width differs")
    shadow_offset = mapping(inputs.get("inputShadowOffset"), "inputShadowOffset")
    shadow_raw = bytes.fromhex(str(shadow_offset.get("hex", "")))
    require(len(shadow_raw) == 16, "inputShadowOffset width differs")
    require(raw[0x008:0x018] == shadow_raw, "provider shadow offset differs")
    for offset, key, scale in F64_PUBLIC_FIELDS:
        expected = struct.pack("<d", numeric(inputs.get(key), key) * scale)
        require(
            raw[offset : offset + 8] == expected,
            f"provider {key} at +{offset:#x} differs",
        )
    for offset in F64_ZERO_FIELDS:
        require(
            raw[offset : offset + 8] == ZERO_F64,
            f"provider +{offset:#x} is not exact positive zero",
        )
    for offset, key in F32_PUBLIC_FIELDS:
        expected = struct.pack("<f", numeric(inputs.get(key), key))
        require(
            raw[offset : offset + 4] == expected,
            f"provider {key} at +{offset:#x} differs",
        )

    require(
        raw[0x0C0:0x0C8]
        == join.binary64_word(inputs.get("inputOuterRefractionAmount"), 1.0, "outer alias"),
        "provider outer-refraction directional alias differs",
    )
    require(
        raw[0x0C0:0x0C8]
        == join.binary64_word(inputs.get("inputShadowHeight"), 0.5, "shadow-height alias"),
        "provider shadow-height directional alias differs",
    )
    require(
        raw[0x0E8:0x0F0]
        == join.binary64_word(inputs.get("inputShadowAmount"), -0.8, "shadow scale"),
        "provider negative shadow scaling differs",
    )
    require(
        raw[0x0F8:0x100]
        == join.binary64_word(inputs.get("inputBlurDistance4"), 1.0, "blur-distance alias"),
        "provider secondary directional alias differs",
    )
    require(
        raw[0x160:0x168]
        == join.binary64_word(inputs.get("inputBleedHeight"), 1.0, "bleed height"),
        "provider bleed-height alias differs",
    )
    require(
        raw[0x160:0x168]
        == join.binary64_word(inputs.get("inputBleedBlurRadius"), 0.5, "bleed blur"),
        "provider bleed-blur alias differs",
    )


def expected_public_return(inputs: Mapping[str, Any]) -> bytes:
    shadow = mapping(inputs.get("inputShadowOffset"), "inputShadowOffset")
    raw = bytes.fromhex(str(shadow.get("hex", "")))
    require(len(raw) == 16, "inputShadowOffset width differs")
    _axis_x, axis_y = struct.unpack("<dd", raw)
    amount = numeric(inputs.get("inputShadowAmount"), "inputShadowAmount")
    return struct.pack("<d", abs(axis_y) + abs(amount))


def validate_predictions(
    trace_value: Any,
    timeline_value: Any,
    markers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    trace = mapping(trace_value, "trace")
    calls = sequence(trace.get("calls"), "provider calls")
    timeline = mapping(timeline_value, "timeline")
    dynamic = mapping(
        timeline.get("dynamicBackgroundUniforms"), "dynamic background uniforms"
    )
    records = sequence(dynamic.get("records"), "dynamic records")
    require(len(records) == 32, "dynamic record count differs")
    record_by_sample: dict[int, Mapping[str, Any]] = {}
    for record_value in records:
        record = mapping(record_value, "dynamic record")
        sample_index = record.get("sampleIndex")
        require(
            isinstance(sample_index, int) and 1 <= sample_index <= 32,
            "dynamic sample index differs",
        )
        require(sample_index not in record_by_sample, "dynamic sample repeats")
        record_by_sample[sample_index] = record
    require(set(record_by_sample) == set(range(1, 33)), "dynamic sample set differs")

    object_raw = [
        join.object_raw(mapping(call, f"provider call {index}"), f"provider call {index}")
        for index, call in enumerate(calls)
    ]
    selected: list[dict[str, Any]] = []
    for sample_index in range(1, 33):
        marker = markers[sample_index]
        start = int(marker["precedingCompletedCallStartIndex"])
        end = int(marker["precedingCompletedCallEndIndexExclusive"])
        require(start < end, f"sample {sample_index} marker batch is empty")
        call_index = end - 1
        inputs = join.input_values(
            record_by_sample[sample_index], f"dynamic sample {sample_index}"
        )
        provider_loaded_fields_match(object_raw[call_index], inputs)
        words = join.signature_words(inputs)
        batch_counts = [
            join.signature_match_count(object_raw[index], words)
            for index in range(start, end)
        ]
        require(
            batch_counts[-1] == len(join.SIGNATURE),
            f"sample {sample_index} structurally selected signature differs",
        )
        require(
            all(count in (0, len(join.SIGNATURE)) for count in batch_counts),
            f"sample {sample_index} has a partial signature collision",
        )
        global_matches = [
            index
            for index, raw in enumerate(object_raw)
            if join.signature_match_count(raw, words) == len(join.SIGNATURE)
        ]
        require(
            global_matches == [call_index],
            f"sample {sample_index} signature uniqueness differs",
        )
        call = mapping(calls[call_index], f"provider call {call_index}")
        expected_return = expected_public_return(inputs)
        require(
            call.get("returnF64RawLittleEndianHex") == expected_return.hex(),
            f"sample {sample_index} public return law differs",
        )
        selected.append(
            {
                "sampleIndex": sample_index,
                "markerBatchCallStartIndex": start,
                "markerBatchCallEndIndexExclusive": end,
                "markerBatchCallCount": end - start,
                "structurallySelectedProviderCallIndex": call_index,
                "selectedCallIsLastCompletedBeforeMarker": True,
                "globalFullSignatureMatchedProviderCallIndices": global_matches,
                "loadedFieldPredictionCount": 18,
                "returnRawLittleEndianHex": expected_return.hex(),
            }
        )
    return {
        "openedSampleCount": len(selected),
        "selectedCalls": selected,
        "distinctSelectedProviderCallCount": len(
            {record["structurallySelectedProviderCallIndex"] for record in selected}
        ),
        "selectionUsesCapturedValues": False,
        "all32SamplesAcceptanceGated": True,
        "loadedFieldPredictionCountPerSample": 18,
        "exactReturnLaw": "abs(inputShadowOffset.y) + abs(inputShadowAmount)",
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
    capture_commit = predecessor.validate_context(
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
    trace = load_json(paths["trace"], "trace")
    timeline = load_json(paths["timeline"], "timeline")
    provider_summary, markers = validate_provider_trace_structure(trace)
    timeline_summary = matrix.validate_timeline(timeline, artifact_directory)
    prediction_summary = validate_predictions(trace, timeline, markers)
    return {
        "case22ProviderTimelineMarkerRetinaTransferLocalMacOSValidationSchemaVersion": (
            RESULT_SCHEMA_VERSION
        ),
        "classification": (
            "prospective active-Retina value-blind last-completed-call transfer "
            "of all 18 loaded provider fields and the exact public return law "
            "for timeline samples 1 through 32"
        ),
        "captureCommit": capture_commit,
        "captureContractPassed": True,
        "preflight": preflight,
        "providerTrace": provider_summary,
        "timeline": timeline_summary,
        "predictions": prediction_summary,
        "artifactSHA256": {label: sha256(path) for label, path in paths.items()},
        "authority": {
            "authenticatedMarkerLastCallTemporalJoinEstablishedSamples1Through32": True,
            "sameProfileAll18PublicProviderLoadedFieldsTransferredProspectively": True,
            "sameProfileExactPublicProviderReturnLawTransferredProspectively": True,
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
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
