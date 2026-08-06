#!/usr/bin/env python3
"""Open the exact trailing topology of run 31065261980's helper inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_prepare_layer_crop_union_operand_matrix as crop_analysis
import validate_prepare_layer_mask_instruction_inventory as validator
import validate_prepare_layer_mask_instruction_trace as trace_validator


RESULT_SCHEMA_VERSION = 1
RUN_ID = 31_065_261_980
EXPECTED_TRACE_SHA256 = (
    "1379bd443f1a80f654d0f052764c38f324ba2708cc76166ca57ee45446fc6b16"
)
EXPECTED_TIMELINE_SHA256 = (
    "56a86840da44b482c4deafc9d99ad0ec44b7c055aa4fb76b4cbd9ff62c91dbc5"
)
ORIGINAL_VALIDATOR_FAILURE = "inventory helper marker links leave trailing entries"
EXPECTED_HELPER_INTERVAL_COUNTS = {1: 12, **dict.fromkeys(range(2, 33), 14), 33: 1}
EXPECTED_EVENT_KIND_COUNTS = {
    "prepare-layer-mask-entry": 447,
    "nested-crop-store": 352,
    "crop-transfer-marker": 32,
}


mapping = trace_validator.mapping
sequence = trace_validator.sequence
integer = trace_validator.integer


def validate_opened_marker_links(
    extension: Mapping[str, Any], entries: Sequence[Mapping[str, Any]]
) -> tuple[int, int]:
    links = list(sequence(extension.get("markerLinks"), "helper marker links"))
    if len(links) != 32 or extension.get("finalMarkerLinkCount") != 32:
        raise ValueError("opened helper marker-link count differs")
    previous_end = 0
    for interval, raw in enumerate(links, start=1):
        link = mapping(raw, f"opened helper marker link {interval}")
        start = integer(link.get("startHelperRecordIndex"), "helper link start")
        end = integer(
            link.get("endHelperRecordIndexExclusive"), "helper link end"
        )
        if (
            link.get("markerRecordIndex") != interval - 1
            or integer(link.get("markerCallbackSequence"), "marker callback") <= 0
            or link.get("markerIntervalIndex") != interval
            or start != previous_end
            or not 0 <= start <= end <= len(entries)
            or link.get("selectedHelperRecordIndices") != []
            or link.get("helperCollectionStoppedAtTarget") is not False
            or any(
                record["markerIntervalIndex"] != interval
                for record in entries[start:end]
            )
        ):
            raise ValueError(f"opened helper marker link {interval} differs")
        previous_end = end
    trailing = list(entries[previous_end:])
    if (
        previous_end != 446
        or len(trailing) != 1
        or trailing[0]["recordIndex"] != 446
        or trailing[0]["markerIntervalIndex"] != 33
        or trailing[0]["qualifiedOrdinalWithinMarkerInterval"] != 1
        or trailing[0]["prepareRecursionDepth"] != 4
    ):
        raise ValueError("opened trailing helper topology differs")
    return previous_end, len(trailing)


def validate_opened_callback_events(
    transport: Mapping[str, Any],
    trace: Mapping[str, Any],
    entries: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]], list[dict[str, Any]]]:
    events = list(sequence(transport.get("callbackEvents"), "callback events"))
    stores = list(
        sequence(
            mapping(
                trace.get("cropPolicyHoldoutExtension"), "store extension"
            ).get("storeRecords"),
            "store records",
        )
    )
    markers = list(sequence(trace.get("qualifiedRecords"), "marker records"))
    helper_events: list[dict[str, Any]] = []
    store_events: dict[int, dict[str, Any]] = {}
    marker_indices: list[int] = []
    for index, raw in enumerate(events):
        event = mapping(raw, f"opened callback event {index}")
        kind = event.get("kind")
        interval = integer(event.get("markerIntervalIndex"), "event interval")
        if event.get("eventIndex") != index or not 1 <= interval <= 33:
            raise ValueError("opened callback event identity differs")
        if kind == "prepare-layer-mask-entry":
            record_index = integer(event.get("helperRecordIndex"), "helper event")
            if not 0 <= record_index < len(entries):
                raise ValueError("opened helper event index differs")
            record = entries[record_index]
            if (
                interval != record["markerIntervalIndex"]
                or event.get("qualifiedOrdinalWithinMarkerInterval")
                != record["qualifiedOrdinalWithinMarkerInterval"]
                or event.get("callerRoleBase") != record["callerRoleBase"]
                or event.get("outputLayerShapesAddress")
                != record["outputLayerShapesAddress"]
                or event.get("prepareRecursionDepth")
                != record["prepareRecursionDepth"]
            ):
                raise ValueError("opened helper callback event differs")
            helper_events.append(dict(event))
        elif kind == "nested-crop-store":
            record_index = integer(event.get("storeRecordIndex"), "store event")
            if not 0 <= record_index < len(stores) or record_index in store_events:
                raise ValueError("opened store event index differs")
            record = mapping(stores[record_index], "opened store record")
            identity = mapping(record.get("frameIdentity"), "store identity")
            if (
                event.get("callerRoleBase") != identity.get("roleBase")
                or event.get("prepareRecursionDepth")
                != record.get("prepareRecursionDepth")
            ):
                raise ValueError("opened store callback event differs")
            store_events[record_index] = dict(event)
        elif kind == "crop-transfer-marker":
            record_index = integer(event.get("markerRecordIndex"), "marker event")
            if (
                not 0 <= record_index < len(markers)
                or interval != record_index + 1
            ):
                raise ValueError("opened marker callback event differs")
            marker_indices.append(record_index)
        else:
            raise ValueError("opened callback event kind differs")
    counts = Counter(event["kind"] for event in events)
    trailing_events = [event for event in events if event["markerIntervalIndex"] == 33]
    if (
        transport.get("finalCallbackEventCount") != len(events)
        or len(events) != 831
        or dict(counts) != EXPECTED_EVENT_KIND_COUNTS
        or sorted(event["helperRecordIndex"] for event in helper_events)
        != list(range(len(entries)))
        or sorted(store_events) != list(range(len(stores)))
        or marker_indices != list(range(len(markers)))
        or [event["eventIndex"] for event in trailing_events]
        != [826, 827, 828, 829, 830]
        or [event["kind"] for event in trailing_events]
        != [
            "nested-crop-store",
            "prepare-layer-mask-entry",
            "nested-crop-store",
            "nested-crop-store",
            "nested-crop-store",
        ]
    ):
        raise ValueError("opened callback event coverage differs")
    return helper_events, store_events, trailing_events


def analyze(trace_path: Path, timeline_path: Path) -> dict[str, Any]:
    if (
        crop_analysis.sha256_file(trace_path) != EXPECTED_TRACE_SHA256
        or crop_analysis.sha256_file(timeline_path) != EXPECTED_TIMELINE_SHA256
    ):
        raise ValueError("inventory frozen input hash differs")
    try:
        validator.validate(trace_path, timeline_path)
    except ValueError as error:
        if str(error) != ORIGINAL_VALIDATOR_FAILURE:
            raise ValueError(f"original inventory failure differs: {error}") from error
    else:
        raise ValueError("original inventory validator unexpectedly passed")

    base_result, trace, _timeline, opened, prepare_start = validator.validate_inherited(
        trace_path, timeline_path, trace_validator.EXPECTED_GEOMETRY
    )
    extension = mapping(
        trace.get("prepareLayerMaskInstructionExtension"), "helper extension"
    )
    helper, code = trace_validator.validate_helper_identity(
        extension, trace, prepare_start
    )
    code_sha = hashlib.sha256(code).hexdigest()
    if code_sha != validator.KNOWN_HELPER_CODE_SHA256:
        raise ValueError("opened helper code identity differs")
    entries = validator.validate_entries(extension, helper, prepare_start)
    linked_count, trailing_count = validate_opened_marker_links(extension, entries)
    interval_counts = Counter(record["markerIntervalIndex"] for record in entries)
    if dict(interval_counts) != EXPECTED_HELPER_INTERVAL_COUNTS:
        raise ValueError("opened helper interval counts differ")
    transport = mapping(
        extension.get("prepareLayerMaskInventoryCalibrationTransport"),
        "inventory transport",
    )
    helper_events, store_events, trailing_events = validate_opened_callback_events(
        transport, trace, entries
    )
    mappings = validator.structural_mappings(opened, helper_events, store_events)
    if (
        len(mappings) != 32
        or mappings[0]["selectedQualifiedOrdinal"] != 12
        or any(record["selectedQualifiedOrdinal"] != 14 for record in mappings[1:])
        or any(record["matchingPriorHelperCount"] != 1 for record in mappings)
    ):
        raise ValueError("opened producer helper mapping differs")
    sample2 = mappings[1]
    return {
        "prepareLayerMaskInstructionInventoryValidationSchemaVersion": 1,
        "prepareLayerMaskInstructionInventoryOpenedResultSchemaVersion": (
            RESULT_SCHEMA_VERSION
        ),
        "classification": (
            "retrospectively opened exact trailing topology for the prospectively "
            "captured output-blind inventory; selection remains event-order, "
            "caller-role, and recursion-depth only"
        ),
        "conclusion": "success",
        "runID": RUN_ID,
        "originalProspectiveValidatorPassed": False,
        "originalProspectiveValidatorFailure": ORIGINAL_VALIDATOR_FAILURE,
        "inputs": {
            "trace": "transition-inventory/prepare-layer-mask-instruction-trace.json",
            "traceSHA256": EXPECTED_TRACE_SHA256,
            "timeline": "transition-inventory/transition-timeline.json",
            "timelineSHA256": EXPECTED_TIMELINE_SHA256,
        },
        "geometry": base_result["geometry"],
        "helper": {
            "function": trace_validator.HELPER_FUNCTION,
            "codeSHA256": code_sha,
            "symbolByteCount": len(code),
            "qualifiedEntryCount": len(entries),
            "markerLinkedEntryCount": linked_count,
            "trailingEntryCount": trailing_count,
            "intervalEntryCountPattern": {
                "interval1": interval_counts[1],
                "interval2Through32": interval_counts[2],
                "interval33": interval_counts[33],
            },
            "callbackEventCount": transport["finalCallbackEventCount"],
        },
        "openedTrailingTopology": {
            "markerIntervalIndex": 33,
            "helperEntryCount": trailing_count,
            "storeEventCount": 4,
            "markerEventCount": 0,
            "eventIndices": [event["eventIndex"] for event in trailing_events],
            "eventKinds": [event["kind"] for event in trailing_events],
            "usedForSample2Selection": False,
        },
        "structuralSelection": {
            "sampleIndex": 2,
            "rule": (
                "within marker interval 2 choose the last helper-entry event "
                "before the independently selected producer-store event whose "
                "caller role and prepare recursion depth equal that producer"
            ),
            "sample2TargetQualifiedOrdinal": sample2[
                "selectedQualifiedOrdinal"
            ],
            "sample2TargetHelperRecordIndex": sample2[
                "selectedByLastPriorStructuralIdentityHelperRecordIndex"
            ],
            "sample2MatchingPriorHelperCount": sample2[
                "matchingPriorHelperCount"
            ],
            "sample2MatchingPriorHelperOrdinals": sample2[
                "matchingPriorHelperOrdinals"
            ],
            "sample2ProducerStoreRecordIndex": sample2[
                "structuralProducerStoreRecordIndex"
            ],
            "sample2ProducerCallerRoleBase": sample2["producerCallerRoleBase"],
            "sample2ProducerPrepareRecursionDepth": sample2[
                "producerPrepareRecursionDepth"
            ],
            "sample2HelperEventIndex": sample2["selectedHelperEventIndex"],
            "sample2ProducerStoreEventIndex": sample2[
                "structuralProducerStoreEventIndex"
            ],
            "cropOrOutputValuesUsedForSelection": False,
        },
        "mappingSummary": {
            "sampleCount": len(mappings),
            "matchingPriorHelperCountOne": sum(
                record["matchingPriorHelperCount"] == 1 for record in mappings
            ),
            "sample1TargetQualifiedOrdinal": mappings[0][
                "selectedQualifiedOrdinal"
            ],
            "sample2Through32TargetQualifiedOrdinal": 14,
        },
        "sealedConclusion": {
            "allInheritedMarkerUnionAndStoreEvidenceRevalidated": True,
            "originalProspectiveFailurePreserved": True,
            "knownHelperCodeIdentityRepassed": True,
            "allHelperEntriesRetainedWithoutSelection": True,
            "allHelperStoreAndMarkerCallbackEventsAccounted": True,
            "exactObservedTrailingTopologyOpened": True,
            "sample2ProducerRoleMappedByLastPriorHelper": True,
            "cropOrOutputValuesUsedForSelection": False,
            "freshSelectedProcessPassed": False,
            "exactHelperSemanticsDecoded": False,
            "unchangedRepeatPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = analyze(arguments.trace, arguments.timeline)
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    main()
