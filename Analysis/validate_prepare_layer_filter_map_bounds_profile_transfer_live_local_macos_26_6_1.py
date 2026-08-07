#!/usr/bin/env python3
"""Validate a crop-profile replay through the active M1 QuartzCore code.

The numerical and structural gate remains the frozen profile-transfer
validator.  This adapter authenticates the value-blind live code record and
translates only the three moved instruction sites plus the complete function
identity.  It runs under ``nix develop`` Python, never LLDB's Python 3.9.
"""

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import prepare_layer_live_transport_local_macos_26_6_1 as live
import validate_prepare_layer_filter_map_bounds_profile_transfer_retry as profile


VALIDATION_SCHEMA_VERSION = 1
RETINA_BACKING_SCALE_FACTOR = 2


def _configure_live_validators() -> None:
    crop = profile.crop_validator
    union = profile.union_validator
    store = profile.store_validator

    crop.PREPARE_LAYER_SYMBOL_BYTE_COUNT = live.PREPARE_LAYER_SYMBOL_BYTE_COUNT
    crop.PREPARE_LAYER_FULL_CODE_SHA256 = live.PREPARE_LAYER_FULL_CODE_SHA256
    crop.KNOWN_PREPARE_LAYER_WINDOWS = live.PREPARE_LAYER_WINDOWS
    crop.EXPECTED_CONFIGURATION = {
        **crop.EXPECTED_CONFIGURATION,
        "prepareLayerSymbolByteCount": live.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
        "prepareLayerFullCodeSHA256": live.PREPARE_LAYER_FULL_CODE_SHA256,
        "knownPrepareLayerWindows": [
            {"offset": offset, "byteCount": count, "sha256": digest}
            for offset, count, digest in live.PREPARE_LAYER_WINDOWS
        ],
        "markerOffset": live.MARKER_OFFSET,
        "markerInstructionRawLittleEndianHex": (
            live.MARKER_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
        ),
    }

    union.UNION_CALL_OFFSET = live.UNION_CALL_OFFSET
    union.UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = (
        live.UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
    )
    union.UNION_RETURN_OFFSET = live.UNION_RETURN_OFFSET
    union.UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = (
        live.UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
    )
    union.EXPECTED_EXTENSION_CONFIGURATION = {
        **union.EXPECTED_EXTENSION_CONFIGURATION,
        "unionCallOffset": live.UNION_CALL_OFFSET,
        "unionCallInstructionRawLittleEndianHex": (
            live.UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
        ),
        "unionReturnOffset": live.UNION_RETURN_OFFSET,
        "unionReturnInstructionRawLittleEndianHex": (
            live.UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
        ),
        "callSelectionRule": live.union_call_selection_rule(),
    }

    store.STORE_OFFSET = live.STORE_OFFSET
    store.STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = (
        live.STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
    )
    store.EXPECTED_EXTENSION_CONFIGURATION = {
        **store.EXPECTED_EXTENSION_CONFIGURATION,
        "storeOffset": live.STORE_OFFSET,
        "storeInstructionRawLittleEndianHex": (
            live.STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
        ),
        "storeSelectionRule": live.store_selection_rule(),
    }


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    return value


def _authenticate_transport(trace_path: Path) -> dict[str, Any]:
    trace = _mapping(profile.crop_validator.load_json(trace_path, "trace"), "trace")
    observed = _mapping(
        trace.get("livePrepareLayerTransport"), "live prepare_layer transport"
    )
    expected = live.transport_record()
    if observed != expected:
        raise ValueError("live prepare_layer transport record differs")
    prepare = _mapping(trace.get("prepareLayer"), "prepare layer")
    if (
        prepare.get("function") != live.PREPARE_LAYER_FUNCTION
        or prepare.get("symbolByteCount") != live.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        or prepare.get("fullCodeSHA256") != live.PREPARE_LAYER_FULL_CODE_SHA256
    ):
        raise ValueError("live prepare_layer capture identity differs")
    return observed


def _authenticate_retina_timeline(timeline_path: Path) -> dict[str, Any]:
    timeline = _mapping(
        profile.crop_validator.load_json(timeline_path, "timeline"), "timeline"
    )
    if timeline.get("windowBackingScaleFactor") != RETINA_BACKING_SCALE_FACTOR:
        raise ValueError("physical Retina backing scale differs")
    return {
        "observedBackingScaleFactor": RETINA_BACKING_SCALE_FACTOR,
        "normalizedBackingScaleFactorForInheritedGate": 1,
        "timelineBytesChanged": False,
    }


def _store_pointer_reuse_plan(trace_path: Path) -> tuple[dict[str, Any], set[int]]:
    """Authenticate pointer reuse and select the last store by record order."""

    trace = _mapping(
        profile.crop_validator.load_json(trace_path, "trace"), "trace"
    )
    prepare = _mapping(trace.get("prepareLayer"), "prepare layer")
    prepare_start = profile.holdout.integer(
        prepare.get("symbolStart"), "prepare layer start"
    )
    extension = _mapping(
        trace.get("cropPolicyHoldoutExtension"), "store extension"
    )
    union_extension = _mapping(
        trace.get("cropUnionOperandExtension"), "union extension"
    )
    raw_stores = profile.exact.sequence(
        extension.get("storeRecords"), "store records"
    )
    stores = [
        profile.store_validator.validate_store_record(raw, index, prepare_start)
        for index, raw in enumerate(raw_stores)
    ]
    links = profile.exact.sequence(extension.get("markerLinks"), "store links")
    markers = profile.exact.sequence(trace.get("qualifiedRecords"), "markers")
    union_links = profile.exact.sequence(
        union_extension.get("markerLinks"), "union links"
    )
    unions = profile.exact.sequence(
        union_extension.get("unionRecords"), "union records"
    )
    if not len(links) == len(markers) == len(union_links) == profile.EXPECTED_RECORD_COUNT:
        raise ValueError("live store pointer-reuse inventory differs")

    excluded: set[int] = set()
    records: list[dict[str, Any]] = []
    for sample_index, (raw_link, raw_marker, raw_union_link) in enumerate(
        zip(links, markers, union_links, strict=True), start=1
    ):
        link = _mapping(raw_link, "store link")
        marker = _mapping(raw_marker, "marker")
        union_link = _mapping(raw_union_link, "union link")
        start = profile.holdout.integer(
            link.get("startStoreRecordIndex"), "store start"
        )
        end = profile.holdout.integer(
            link.get("endStoreRecordIndexExclusive"), "store end"
        )
        union_indices = list(
            profile.exact.sequence(
                union_link.get("matchingUnionRecordIndices"), "matching unions"
            )
        )
        if not union_indices:
            raise ValueError("live store link has no matching union")
        selected_union_index = profile.holdout.integer(
            union_indices[-1], "selected union"
        )
        selected_union = _mapping(unions[selected_union_index], "selected union")
        selected_layer_shapes = profile.holdout.integer(
            _mapping(
                selected_union.get("frameIdentity"), "selected union identity"
            ).get("layerShapesBase"),
            "selected LayerShapes base",
        )
        recomputed = [
            store["recordIndex"]
            for store in stores[start:end]
            if store["layerShapesBase"] == selected_layer_shapes
        ]
        captured = list(
            profile.exact.sequence(
                link.get("matchingStoreRecordIndices"), "matching stores"
            )
        )
        embedded = _mapping(
            marker.get("cropPolicyStoreWindow"), "embedded store window"
        )
        if (
            not recomputed
            or captured != recomputed
            or captured != sorted(captured)
            or link.get("selectedUnionRecordIndex") != selected_union_index
            or link.get("selectedLayerShapesBase") != selected_layer_shapes
            or embedded.get("startRecordIndex") != start
            or embedded.get("endRecordIndexExclusive") != end
            or embedded.get("selectedUnionRecordIndex") != selected_union_index
            or embedded.get("selectedLayerShapesBase") != selected_layer_shapes
            or embedded.get("matchingStoreRecordIndices") != captured
        ):
            raise ValueError("live store pointer-reuse authentication differs")
        discarded = captured[:-1]
        excluded.update(discarded)
        records.append(
            {
                "sampleIndex": sample_index,
                "storeWindow": [start, end],
                "selectedLayerShapesBase": selected_layer_shapes,
                "matchingStoreRecordIndices": captured,
                "selectedStoreRecordIndex": captured[-1],
                "discardedEarlierMatchingStoreRecordIndices": discarded,
            }
        )

    return (
        {
            "selectionRule": (
                "within each marker interval select the last store whose "
                "LayerShapes base equals the last destination-matched union; "
                "record order and pointer identity only"
            ),
            "cropOrProducerValuesUsedForSelection": False,
            "recordCount": len(records),
            "matchingStoreRecordCount": sum(
                len(record["matchingStoreRecordIndices"]) for record in records
            ),
            "pointerReuseRecordCount": sum(
                bool(record["discardedEarlierMatchingStoreRecordIndices"])
                for record in records
            ),
            "discardedEarlierMatchCount": len(excluded),
            "records": records,
        },
        excluded,
    )


def _normalized_trace_view(
    trace: dict[str, Any], plan: dict[str, Any]
) -> dict[str, Any]:
    """Build the structural view expected by the immutable one-match gate."""

    normalized = deepcopy(trace)
    extension = normalized["cropPolicyHoldoutExtension"]
    markers = normalized["qualifiedRecords"]
    records = plan["records"]
    for link, marker, record in zip(
        extension["markerLinks"], markers, records, strict=True
    ):
        selected = [record["selectedStoreRecordIndex"]]
        link["matchingStoreRecordIndices"] = selected
        marker["cropPolicyStoreWindow"]["matchingStoreRecordIndices"] = selected
    extension["finalLinkedStoreRecordCount"] = len(records)
    return normalized


def validate(
    trace_path: Path,
    timeline_path: Path,
    expected_geometry: str,
    expected_material: str,
    expected_appearance: str,
    expected_direction: str,
) -> dict[str, Any]:
    _configure_live_validators()
    transport = _authenticate_transport(trace_path)
    retina = _authenticate_retina_timeline(timeline_path)
    pointer_reuse, excluded_store_indices = _store_pointer_reuse_plan(trace_path)

    raw_trace = _mapping(
        profile.crop_validator.load_json(trace_path, "trace"), "trace"
    )
    normalized_trace = _normalized_trace_view(raw_trace, pointer_reuse)
    original_load_json = profile.crop_validator.load_json
    original_validate_timeline = profile.crop_validator.validate_timeline
    original_validate_store_record = profile.store_validator.validate_store_record

    def load_normalized(path: Path, label: str) -> Any:
        if label == "trace":
            return deepcopy(normalized_trace)
        return original_load_json(path, label)

    def validate_retina_timeline(
        timeline: dict[str, Any], geometry: str
    ) -> tuple[dict[str, Any], list[Any]]:
        if timeline.get("windowBackingScaleFactor") != RETINA_BACKING_SCALE_FACTOR:
            raise ValueError("physical Retina backing scale differs")
        normalized = dict(timeline)
        normalized["windowBackingScaleFactor"] = 1
        return original_validate_timeline(normalized, geometry)

    def validate_selected_store_record(
        raw: Any, index: int, prepare_start: int
    ) -> dict[str, Any]:
        decoded = original_validate_store_record(raw, index, prepare_start)
        if index not in excluded_store_indices:
            return decoded
        normalized = dict(decoded)
        normalized["layerShapesBase"] = 0
        return normalized

    profile.crop_validator.load_json = load_normalized
    profile.crop_validator.validate_timeline = validate_retina_timeline
    profile.store_validator.validate_store_record = validate_selected_store_record
    try:
        result = profile.validate(
            trace_path,
            timeline_path,
            expected_geometry,
            expected_material,
            expected_appearance,
            expected_direction,
        )
    finally:
        profile.crop_validator.load_json = original_load_json
        profile.crop_validator.validate_timeline = original_validate_timeline
        profile.store_validator.validate_store_record = original_validate_store_record

    result[
        "prepareLayerFilterMapBoundsLiveLocalMacOS2661ValidationSchemaVersion"
    ] = VALIDATION_SCHEMA_VERSION
    result["classification"] = (
        "retrospective known-profile calibration through authenticated "
        "active-M1 QuartzCore code transport and physical Retina scale; "
        "the last-store pointer-reuse rule requires an unseen holdout"
    )
    result["livePrepareLayerTransport"] = transport
    result["physicalRetinaMetadataAdapter"] = retina
    result["liveStorePointerReuse"] = pointer_reuse
    result["profile"]["backingScaleFactor"] = RETINA_BACKING_SCALE_FACTOR
    metadata = _mapping(result.get("metadataAdapter"), "metadata adapter")
    metadata["onlyMaterialAppearanceDirectionNormalized"] = False
    metadata["retinaBackingScaleAuthenticatedBeforeNormalization"] = True
    metadata["storePointerReuseAuthenticatedBeforeNormalization"] = True
    metadata["normalizationUsedCropOrProducerValues"] = False
    sealed = _mapping(result.get("sealedConclusion"), "sealed conclusion")
    sealed["activeM1CropCaptureTransportPassed"] = True
    sealed["physicalRetina2xInternalCropReplayPassed"] = True
    sealed["knownProfileCalibrationOnly"] = True
    sealed["lastStorePointerReuseUnseenHoldoutPassed"] = False
    sealed["selectedRegionOriginTransferPassed"] = False
    sealed["productionShaderAuthorized"] = False
    sealed["liquidGlassParityEstablished"] = False
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--expected-geometry", required=True)
    parser.add_argument("--expected-material", required=True)
    parser.add_argument("--expected-appearance", required=True)
    parser.add_argument("--expected-direction", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(
        arguments.trace,
        arguments.timeline,
        arguments.expected_geometry,
        arguments.expected_material,
        arguments.expected_appearance,
        arguments.expected_direction,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
