#!/usr/bin/env python3
"""Validate an output-blind inventory of every ``prepare_layer_mask`` call."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_prepare_layer_crop_policy_holdout_callback_retry as holdout_analysis
import analyze_prepare_layer_crop_union_operand_matrix as crop_analysis
import validate_prepare_layer_crop_policy_holdout as holdout_validator
import validate_prepare_layer_crop_transfer as crop_validator
import validate_prepare_layer_crop_union_operand as union_validator
import validate_prepare_layer_mask_instruction_trace as trace_validator


VALIDATION_SCHEMA_VERSION = 1
TRANSPORT_SCHEMA_VERSION = 1
INVENTORY_SENTINEL_ORDINAL = 4_097
KNOWN_HELPER_CODE_SHA256 = (
    "f78c5fd222dc429152882dffb0b88a5535050351e3a2a5d7102a5abeca5c4c0c"
)


mapping = trace_validator.mapping
sequence = trace_validator.sequence
integer = trace_validator.integer


def selection_rule(ordinal: int) -> str:
    return (
        "among exact direct-normal transition callers, select marker interval "
        f"2 ordinal {ordinal}, then require x1=x19+0x420 and "
        "x3=x19+0x290; do not inspect any rectangle or output bytes"
    )


def expected_configuration() -> dict[str, Any]:
    result = dict(trace_validator.EXPECTED_CONFIGURATION)
    result["targetQualifiedOrdinal"] = INVENTORY_SENTINEL_ORDINAL
    result["entrySelectionRule"] = selection_rule(INVENTORY_SENTINEL_ORDINAL)
    return result


def validate_inherited(
    trace_path: Path, timeline_path: Path, expected_geometry: str
) -> tuple[
    Mapping[str, Any],
    Mapping[str, Any],
    Mapping[str, Any],
    list[dict[str, Any]],
    int,
]:
    try:
        holdout_validator.validate(trace_path, timeline_path, expected_geometry)
    except ValueError as error:
        if str(error) != holdout_analysis.ORIGINAL_PROSPECTIVE_FLOAT_ERROR:
            raise ValueError(f"original prospective failure differs: {error}") from error
    else:
        raise ValueError("original crop-policy gate unexpectedly passed")

    base_result = crop_validator.validate(
        trace_path, timeline_path, expected_geometry
    )
    trace = mapping(crop_validator.load_json(trace_path, "trace"), "trace")
    timeline = mapping(
        crop_validator.load_json(timeline_path, "timeline"), "timeline"
    )
    crop_records, _ = crop_analysis.validate_extension(
        trace, base_result, timeline, expected_geometry
    )
    opened_records, _ = holdout_analysis.validate_store_extension(
        trace, base_result, timeline, crop_records, expected_geometry
    )
    prepare_start = integer(
        mapping(trace.get("prepareLayer"), "prepare layer").get("symbolStart"),
        "prepare start",
    )
    return base_result, trace, timeline, opened_records, prepare_start


def validate_entries(
    extension: Mapping[str, Any], helper: Mapping[str, Any], prepare_start: int
) -> list[dict[str, int]]:
    raw_records = list(
        sequence(extension.get("helperEntryRecords"), "helper entry records")
    )
    if not 1 <= len(raw_records) <= trace_validator.MAXIMUM_QUALIFIED_HELPER_ENTRY_COUNT:
        raise ValueError("inventory helper entry count differs")
    records: list[dict[str, int]] = []
    ordinal_by_interval: dict[int, int] = {}
    hit_indices: list[int] = []
    for index, raw in enumerate(raw_records):
        label = f"inventory helper entry {index}"
        record = mapping(raw, label)
        interval = integer(record.get("markerIntervalIndex"), f"{label} interval")
        ordinal_by_interval[interval] = ordinal_by_interval.get(interval, 0) + 1
        ordinal = ordinal_by_interval[interval]
        hit_index = integer(record.get("entryHitIndex"), f"{label} hit")
        hit_indices.append(hit_index)
        helper_frame = trace_validator.frame(record.get("frame"), f"{label} frame")
        caller = trace_validator.frame(
            record.get("callerFrame"), f"{label} caller"
        )
        if (
            record.get("recordIndex") != index
            or record.get("qualifiedEntryIndex") != index + 1
            or interval <= 0
            or record.get("qualifiedOrdinalWithinMarkerInterval") != ordinal
            or helper_frame.get("function") != trace_validator.HELPER_FUNCTION
            or helper_frame.get("symbolStart") != helper.get("symbolStart")
            or helper_frame.get("symbolEnd") != helper.get("symbolEnd")
            or helper_frame.get("symbolOffset") != 0
            or helper_frame.get("pc") != helper.get("symbolStart")
            or caller.get("function") != crop_validator.PREPARE_LAYER_FUNCTION
            or caller.get("symbolStart") != prepare_start
            or caller.get("symbolEnd")
            != prepare_start + crop_validator.PREPARE_LAYER_SYMBOL_BYTE_COUNT
            or caller.get("symbolOffset") != trace_validator.CALL_RETURN_OFFSET
            or caller.get("pc") != prepare_start + trace_validator.CALL_RETURN_OFFSET
        ):
            raise ValueError(f"{label} structural identity differs")
        backtrace = sequence(record.get("backtrace"), f"{label} backtrace")
        functions = union_validator.backtrace_functions(backtrace)
        if not union_validator.direct_timeline_caller(functions):
            raise ValueError(f"{label} caller chain differs")
        depth = sum(
            mapping(raw_frame, f"{label} backtrace frame").get("function")
            == crop_validator.PREPARE_LAYER_FUNCTION
            and mapping(raw_frame, f"{label} backtrace frame").get("symbolStart")
            == prepare_start
            and mapping(raw_frame, f"{label} backtrace frame").get("symbolEnd")
            == prepare_start + crop_validator.PREPARE_LAYER_SYMBOL_BYTE_COUNT
            for raw_frame in backtrace
        )
        registers = crop_validator.register_values(
            record.get("registers"),
            trace_validator.ENTRY_REGISTER_NAMES,
            f"{label} registers",
        )
        identity = mapping(record.get("frameIdentity"), f"{label} identity")
        expected_identity = {
            "threadID": record.get("threadID"),
            "callerRoleBase": registers["x19"],
            "callerFramePointer": registers["x29"],
            "globalStateX0": registers["x0"],
            "localStateX1": registers["x1"],
            "sourceLayerShapesX2": registers["x2"],
            "outputLayerShapesX3": registers["x3"],
        }
        offsets_match = (
            registers["x1"]
            == registers["x19"] + trace_validator.CALLER_LOCAL_STATE_OFFSET
            and registers["x3"]
            == registers["x19"] + trace_validator.CALLER_OUTPUT_OFFSET
        )
        if (
            record.get("prepareRecursionDepth") != depth
            or dict(identity) != expected_identity
            or offsets_match is not True
            or record.get("roleOffsetsMatch") is not True
            or record.get("selectedByFrozenOrdinal") is not False
            or record.get("selectedByFrozenRule") is not False
        ):
            raise ValueError(f"{label} argument identity differs")
        records.append(
            {
                "recordIndex": index,
                "markerIntervalIndex": interval,
                "qualifiedOrdinalWithinMarkerInterval": ordinal,
                "callerRoleBase": registers["x19"],
                "outputLayerShapesAddress": registers["x3"],
                "prepareRecursionDepth": depth,
            }
        )
    if hit_indices != sorted(hit_indices) or len(set(hit_indices)) != len(hit_indices):
        raise ValueError("inventory helper hit order differs")
    rejected = integer(
        extension.get("finalRejectedHelperEntryCount"), "rejected helper entries"
    )
    grouped = 0
    for raw_group in sequence(
        extension.get("rejectionGroups"), "helper rejections"
    ):
        group = mapping(raw_group, "helper rejection")
        if group.get("reason") != "caller-chain-excluded":
            raise ValueError("helper rejection reason differs")
        integer(group.get("prepareRecursionDepth"), "helper rejection depth")
        grouped += integer(group.get("hitCount"), "helper rejection count")
    if (
        rejected != grouped
        or extension.get("finalQualifiedHelperEntryCount") != len(records)
        or extension.get("finalHelperEntryRecordCount") != len(records)
        or extension.get("finalHelperEntryHitCount") != len(records) + rejected
    ):
        raise ValueError("inventory helper accounting differs")
    return records


def validate_marker_links(
    extension: Mapping[str, Any], records: Sequence[Mapping[str, Any]]
) -> None:
    links = list(sequence(extension.get("markerLinks"), "helper marker links"))
    if len(links) != 32 or extension.get("finalMarkerLinkCount") != 32:
        raise ValueError("inventory helper marker-link count differs")
    previous_end = 0
    for interval, raw in enumerate(links, start=1):
        link = mapping(raw, f"inventory helper marker link {interval}")
        start = integer(link.get("startHelperRecordIndex"), "helper link start")
        end = integer(
            link.get("endHelperRecordIndexExclusive"), "helper link end"
        )
        if (
            link.get("markerRecordIndex") != interval - 1
            or integer(link.get("markerCallbackSequence"), "marker callback") <= 0
            or link.get("markerIntervalIndex") != interval
            or start != previous_end
            or not 0 <= start <= end <= len(records)
            or link.get("selectedHelperRecordIndices") != []
            or link.get("helperCollectionStoppedAtTarget") is not False
            or any(
                record["markerIntervalIndex"] != interval
                for record in records[start:end]
            )
        ):
            raise ValueError(f"inventory helper marker link {interval} differs")
        previous_end = end
    if previous_end != len(records):
        raise ValueError("inventory helper marker links leave trailing entries")


def validate_callback_events(
    transport: Mapping[str, Any],
    trace: Mapping[str, Any],
    entries: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
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
        event = mapping(raw, f"callback event {index}")
        kind = event.get("kind")
        interval = integer(event.get("markerIntervalIndex"), "event interval")
        if event.get("eventIndex") != index or not 1 <= interval <= 32:
            raise ValueError("callback event identity differs")
        if kind == "prepare-layer-mask-entry":
            record_index = integer(event.get("helperRecordIndex"), "helper event")
            if not 0 <= record_index < len(entries):
                raise ValueError("helper callback record index differs")
            record = entries[record_index]
            if (
                event.get("qualifiedOrdinalWithinMarkerInterval")
                != record["qualifiedOrdinalWithinMarkerInterval"]
                or interval != record["markerIntervalIndex"]
                or event.get("callerRoleBase") != record["callerRoleBase"]
                or event.get("outputLayerShapesAddress")
                != record["outputLayerShapesAddress"]
                or event.get("prepareRecursionDepth")
                != record["prepareRecursionDepth"]
            ):
                raise ValueError("helper callback event differs")
            helper_events.append(dict(event))
        elif kind == "nested-crop-store":
            record_index = integer(event.get("storeRecordIndex"), "store event")
            if not 0 <= record_index < len(stores) or record_index in store_events:
                raise ValueError("store callback record index differs")
            record = mapping(stores[record_index], "store callback record")
            identity = mapping(record.get("frameIdentity"), "store identity")
            if (
                event.get("callerRoleBase") != identity.get("roleBase")
                or event.get("prepareRecursionDepth")
                != record.get("prepareRecursionDepth")
            ):
                raise ValueError("store callback event differs")
            store_events[record_index] = dict(event)
        elif kind == "crop-transfer-marker":
            record_index = integer(event.get("markerRecordIndex"), "marker event")
            if (
                not 0 <= record_index < len(markers)
                or interval != record_index + 1
            ):
                raise ValueError("marker callback event differs")
            marker_indices.append(record_index)
        else:
            raise ValueError("callback event kind differs")
    if (
        transport.get("finalCallbackEventCount") != len(events)
        or sorted(event["helperRecordIndex"] for event in helper_events)
        != list(range(len(entries)))
        or sorted(store_events) != list(range(len(stores)))
        or marker_indices != list(range(len(markers)))
    ):
        raise ValueError("callback event coverage differs")
    return helper_events, store_events


def structural_mappings(
    opened_records: Sequence[Mapping[str, Any]],
    helper_events: Sequence[Mapping[str, Any]],
    store_events: Mapping[int, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in opened_records:
        sample = mapping(raw, "opened producer record")
        sample_index = integer(sample.get("sampleIndex"), "sample index")
        store_index = integer(
            sample.get("structuralProducerStoreIndex"), "producer store"
        )
        producer_role = integer(sample.get("producerRoleBase"), "producer role")
        producer_depth = integer(
            sample.get("producerPrepareRecursionDepth"), "producer depth"
        )
        store_event = mapping(store_events.get(store_index), "producer store event")
        if (
            store_event.get("markerIntervalIndex") != sample_index
            or store_event.get("callerRoleBase") != producer_role
            or store_event.get("prepareRecursionDepth") != producer_depth
        ):
            raise ValueError(f"sample {sample_index} producer event differs")
        candidates = [
            event
            for event in helper_events
            if event.get("markerIntervalIndex") == sample_index
            and event.get("eventIndex") < store_event.get("eventIndex")
            and event.get("callerRoleBase") == producer_role
            and event.get("prepareRecursionDepth") == producer_depth
        ]
        if not candidates:
            raise ValueError(f"sample {sample_index} producer helper is absent")
        selected = candidates[-1]
        result.append(
            {
                "sampleIndex": sample_index,
                "structuralProducerStoreRecordIndex": store_index,
                "structuralProducerStoreEventIndex": store_event["eventIndex"],
                "producerCallerRoleBase": producer_role,
                "producerPrepareRecursionDepth": producer_depth,
                "matchingPriorHelperCount": len(candidates),
                "matchingPriorHelperOrdinals": [
                    event["qualifiedOrdinalWithinMarkerInterval"]
                    for event in candidates
                ],
                "selectedByLastPriorStructuralIdentityHelperRecordIndex": selected[
                    "helperRecordIndex"
                ],
                "selectedQualifiedOrdinal": selected[
                    "qualifiedOrdinalWithinMarkerInterval"
                ],
                "selectedHelperEventIndex": selected["eventIndex"],
                "cropOrOutputValuesUsedForSelection": False,
            }
        )
    return result


def validate(
    trace_path: Path,
    timeline_path: Path,
    expected_geometry: str = trace_validator.EXPECTED_GEOMETRY,
) -> dict[str, Any]:
    if expected_geometry != trace_validator.EXPECTED_GEOMETRY:
        raise ValueError("inventory expected geometry differs")
    base_result, trace, _timeline, opened, prepare_start = validate_inherited(
        trace_path, timeline_path, expected_geometry
    )
    extension = mapping(
        trace.get("prepareLayerMaskInstructionExtension"), "helper extension"
    )
    if (
        extension.get("prepareLayerMaskInstructionExtensionSchemaVersion")
        != trace_validator.EXTENSION_SCHEMA_VERSION
        or extension.get("configuration") != expected_configuration()
        or extension.get("status") != "finalized"
        or extension.get("statusBeforeFinalization")
        != "helper-entry-breakpoint-active"
        or extension.get("manualTraceStarted") is not False
        or extension.get("manualTraceFinished") is not False
        or extension.get("selectedInvocation") != {}
        or sequence(extension.get("instructionStates"), "instruction states")
        or sequence(extension.get("opaqueCalleeBoundaries"), "callee boundaries")
        or sequence(extension.get("executionEvents"), "execution events")
        or sequence(extension.get("failures"), "helper failures")
        or extension.get("finalInstructionStateCount") != 0
        or extension.get("finalOpaqueCalleeBoundaryCount") != 0
        or extension.get("finalExecutionEventCount") != 0
        or extension.get("finalFailureCount") != 0
    ):
        raise ValueError("inventory helper extension differs")
    helper, code = trace_validator.validate_helper_identity(
        extension, trace, prepare_start
    )
    code_sha = hashlib.sha256(code).hexdigest()
    if code_sha != KNOWN_HELPER_CODE_SHA256:
        raise ValueError("inventory helper code identity differs")
    entries = validate_entries(extension, helper, prepare_start)
    validate_marker_links(extension, entries)
    transport = mapping(
        extension.get("prepareLayerMaskInventoryCalibrationTransport"),
        "inventory transport",
    )
    if (
        transport.get("prepareLayerMaskInventoryCalibrationTransportSchemaVersion")
        != TRANSPORT_SCHEMA_VERSION
        or transport.get("mode") != "inventory"
        or transport.get("targetQualifiedOrdinal") != INVENTORY_SENTINEL_ORDINAL
        or transport.get("inventorySentinelOrdinal") != INVENTORY_SENTINEL_ORDINAL
        or transport.get("knownHelperCodeSHA256") != KNOWN_HELPER_CODE_SHA256
        or transport.get("inventoryValidationSource") is not None
        or transport.get("cropOrOutputValuesReadByTransport") is not False
        or transport.get("newBreakpointAddedByTransport") is not False
        or transport.get("captureByteRangeChangedByTransport") is not False
        or transport.get("steppingRuleChangedByTransport") is not False
    ):
        raise ValueError("inventory transport identity differs")
    helper_events, store_events = validate_callback_events(
        transport, trace, entries
    )
    mappings = structural_mappings(opened, helper_events, store_events)
    sample2 = next(record for record in mappings if record["sampleIndex"] == 2)
    return {
        "prepareLayerMaskInstructionInventoryValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            "prospective output-blind helper inventory calibration; every "
            "qualified helper entry is retained and the last prior exact "
            "caller-role/depth match to the independent producer store selects "
            "an ordinal for a fresh process"
        ),
        "conclusion": "success",
        "inputs": {
            "trace": str(trace_path),
            "traceSHA256": crop_analysis.sha256_file(trace_path),
            "timeline": str(timeline_path),
            "timelineSHA256": crop_analysis.sha256_file(timeline_path),
        },
        "geometry": base_result["geometry"],
        "helper": {
            "function": trace_validator.HELPER_FUNCTION,
            "codeSHA256": code_sha,
            "symbolByteCount": len(code),
            "qualifiedEntryCount": len(entries),
            "callbackEventCount": transport["finalCallbackEventCount"],
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
            "cropOrOutputValuesUsedForSelection": False,
        },
        "roleMappings": mappings,
        "sealedConclusion": {
            "allInheritedMarkerUnionAndStoreEvidenceRevalidated": True,
            "originalProspectiveFailurePreserved": True,
            "knownHelperCodeIdentityRepassed": True,
            "allHelperEntriesRetainedWithoutSelection": True,
            "allHelperStoreAndMarkerCallbackEventsAccounted": True,
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
    parser.add_argument("--expected-geometry", default=trace_validator.EXPECTED_GEOMETRY)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = validate(
        arguments.trace, arguments.timeline, arguments.expected_geometry
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
