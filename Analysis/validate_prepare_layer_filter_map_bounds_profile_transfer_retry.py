#!/usr/bin/env python3
"""Validate the frozen exact FilterOp profile-transfer retry.

The first profile matrix reused clear-material SDF and Filter assumptions for
regular glass.  This validator keeps the authenticated structural producer
selection, opens the adjacent SDF state without consulting crop values, and
replays the now-decoded clear/regular arithmetic bit for bit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_prepare_layer_crop_policy_holdout_callback_retry as holdout
import analyze_prepare_layer_crop_union_operand_matrix as crop_analysis
import analyze_prepare_layer_filter_map_bounds_exact_replay as exact
import validate_prepare_layer_crop_policy_holdout as store_validator
import validate_prepare_layer_crop_transfer as crop_validator
import validate_prepare_layer_crop_union_operand as union_validator


VALIDATION_SCHEMA_VERSION = 1
EXPECTED_RECORD_COUNT = 32
VALID_MATERIALS = ("clear", "regular")
VALID_APPEARANCES = ("light", "dark")
VALID_DIRECTIONS = ("materialize", "dematerialize")
DEMATERIALIZE_NORMAL_PREPARE_RECURSION_DEPTHS = (3,) * 30 + (4, 4)

SDF_STATE_STORE_INDEX_DELTA_FROM_MIRROR = -1
SDF_STATE_ROLE_DELTA_FROM_MIRROR = -0x800
SDF_STATE_DEPTH_DELTA_FROM_MIRROR = 1
SDF_PARAMETERS_OFFSET = 0x7F0
SDF_PARAMETERS_BYTE_COUNT = 16
EXPECTED_SDF_PARAMETERS_HEX = {
    "clear": "00001041000000000000000000000000",
    "regular": "04db2942000000000000000000000000",
}

REGULAR_SOURCE_BOUNDS = (-280.0, -280.0, 1360.0, 1360.0)
REGULAR_RECURSIVE_CHILD = (0.0, 0.0, 1360.0, 1360.0)
REGULAR_ENDPOINT_SOURCE_ORIGIN = 280.0
REGULAR_MATERIALIZE_ENDPOINT_DEPTH = 6
REGULAR_DEMATERIALIZE_ENDPOINT_DEPTH = 7


def require_profile(
    timeline: Mapping[str, Any],
    expected_material: str,
    expected_appearance: str,
    expected_direction: str,
) -> None:
    """Authenticate actual profile metadata before adapting the old base gate."""

    if (
        timeline.get("material") != expected_material
        or timeline.get("appearance") != expected_appearance
        or timeline.get("direction") != expected_direction
    ):
        raise ValueError("timeline profile metadata differs")


def validate_base(
    trace_path: Path,
    timeline_path: Path,
    expected_geometry: str,
    expected_material: str,
    expected_appearance: str,
    expected_direction: str,
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    """Run the frozen crop gate with only authenticated metadata adapted."""

    original_validate_timeline = crop_validator.validate_timeline
    original_topology = crop_validator.EXPECTED_NORMAL_PREPARE_RECURSION_DEPTHS

    def validate_profile_timeline(
        timeline: Mapping[str, Any], geometry: str
    ) -> tuple[Mapping[str, Any], list[Any]]:
        require_profile(
            timeline,
            expected_material,
            expected_appearance,
            expected_direction,
        )
        normalized = dict(timeline)
        normalized["material"] = "clear"
        normalized["appearance"] = "light"
        normalized["direction"] = "materialize"
        return original_validate_timeline(normalized, geometry)

    crop_validator.validate_timeline = validate_profile_timeline
    if expected_direction == "dematerialize":
        crop_validator.EXPECTED_NORMAL_PREPARE_RECURSION_DEPTHS = (
            DEMATERIALIZE_NORMAL_PREPARE_RECURSION_DEPTHS
        )
    try:
        base_result = crop_validator.validate(
            trace_path, timeline_path, expected_geometry
        )
    finally:
        crop_validator.validate_timeline = original_validate_timeline
        crop_validator.EXPECTED_NORMAL_PREPARE_RECURSION_DEPTHS = original_topology

    trace = exact.mapping(crop_validator.load_json(trace_path, "trace"), "trace")
    timeline = exact.mapping(
        crop_validator.load_json(timeline_path, "timeline"), "timeline"
    )
    return base_result, trace, timeline


def validated_store_inventory(
    trace: Mapping[str, Any],
) -> tuple[Sequence[Any], list[dict[str, Any]]]:
    prepare_start = holdout.integer(
        exact.mapping(trace.get("prepareLayer"), "prepare layer").get("symbolStart"),
        "prepare layer start",
    )
    extension = exact.mapping(
        trace.get("cropPolicyHoldoutExtension"), "store extension"
    )
    raw_stores = exact.sequence(extension.get("storeRecords"), "store records")
    stores = [
        store_validator.validate_store_record(raw, index, prepare_start)
        for index, raw in enumerate(raw_stores)
    ]
    return raw_stores, stores


def validate_regular_union_structure(
    trace: Mapping[str, Any],
    base_result: Mapping[str, Any],
    timeline: Mapping[str, Any],
    label: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Validate every union fact except the falsified clear crop formula."""

    extension = exact.mapping(
        trace.get("cropUnionOperandExtension"), "crop union extension"
    )
    if (
        extension.get("cropUnionOperandExtensionSchemaVersion")
        != union_validator.EXTENSION_SCHEMA_VERSION
        or extension.get("configuration")
        != union_validator.EXPECTED_EXTENSION_CONFIGURATION
        or extension.get("status") != "finalized"
        or extension.get("statusBeforeFinalization") != "crop-union-breakpoints-active"
    ):
        raise ValueError(f"{label} regular union extension identity differs")

    prepare_start = holdout.integer(
        exact.mapping(trace.get("prepareLayer"), "prepare layer").get("symbolStart"),
        "prepare start",
    )
    if extension.get("prepareLayerSymbolStart") != prepare_start:
        raise ValueError(f"{label} regular union prepare start differs")
    call_digest = hashlib.sha256(
        bytes.fromhex(union_validator.UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX)
    ).hexdigest()
    return_digest = hashlib.sha256(
        bytes.fromhex(union_validator.UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX)
    ).hexdigest()
    if (
        extension.get("unionCallInstructionSHA256") != call_digest
        or extension.get("unionReturnInstructionSHA256") != return_digest
    ):
        raise ValueError(f"{label} regular union instruction identity differs")

    raw_unions = exact.sequence(extension.get("unionRecords"), "union records")
    unions = [
        union_validator.validate_union_record(raw, index, prepare_start)
        for index, raw in enumerate(raw_unions)
    ]
    event_sequences = [
        event
        for record in unions
        for event in (record["callEventSequence"], record["returnEventSequence"])
    ]
    if sorted(event_sequences) != list(range(1, len(event_sequences) + 1)):
        raise ValueError(f"{label} regular union event sequence differs")

    rejected_calls = holdout.integer(
        extension.get("finalRejectedUnionCallCount"), "rejected union calls"
    )
    rejected_returns = holdout.integer(
        extension.get("finalRejectedUnionReturnCount"), "rejected union returns"
    )
    grouped_rejections = sum(
        holdout.integer(
            exact.mapping(raw, "union rejection group").get("hitCount"),
            "union rejection count",
        )
        for raw in exact.sequence(extension.get("rejectionGroups"), "union rejections")
    )
    if (
        rejected_calls != rejected_returns
        or rejected_calls != grouped_rejections
        or extension.get("finalQualifiedUnionRecordCount") != len(unions)
        or extension.get("finalCompleteUnionRecordCount") != len(unions)
        or extension.get("finalEventSequence") != len(unions) * 2
        or extension.get("finalUnionCallHitCount") != len(unions) + rejected_calls
        or extension.get("finalUnionReturnHitCount") != len(unions) + rejected_returns
    ):
        raise ValueError(f"{label} regular union accounting differs")

    markers = exact.sequence(trace.get("qualifiedRecords"), "qualified markers")
    public_records = exact.sequence(base_result.get("records"), "public records")
    timeline_records = exact.sequence(
        exact.mapping(
            timeline.get("dynamicBackgroundUniforms"), "dynamic uniforms"
        ).get("records"),
        "timeline records",
    )
    links = exact.sequence(extension.get("markerLinks"), "union marker links")
    if (
        not len(markers)
        == len(public_records)
        == len(timeline_records)
        == len(links)
        == EXPECTED_RECORD_COUNT
    ):
        raise ValueError(f"{label} regular union marker inventory differs")

    records: list[dict[str, Any]] = []
    previous_end = 0
    for index, (raw_link, raw_marker, raw_public) in enumerate(
        zip(links, markers, public_records, strict=True), start=1
    ):
        link = exact.mapping(raw_link, "union marker link")
        marker = exact.mapping(raw_marker, "qualified marker")
        public = exact.mapping(raw_public, "public record")
        start = holdout.integer(link.get("startUnionRecordIndex"), "union start")
        end = holdout.integer(link.get("endUnionRecordIndexExclusive"), "union end")
        identity = exact.mapping(marker.get("frameIdentity"), "marker identity")
        destination = (
            holdout.integer(identity.get("roleBase"), "marker role base")
            + union_validator.UNION_DESTINATION_ROLE_OFFSET
        )
        matching = list(
            exact.sequence(link.get("matchingUnionRecordIndices"), "matching unions")
        )
        recomputed = [
            record["recordIndex"]
            for record in unions[start:end]
            if record["destinationAddress"] == destination
        ]
        embedded = exact.mapping(
            marker.get("cropUnionOperandWindow"), "embedded union window"
        )
        if (
            start != previous_end
            or not start < end <= len(unions)
            or matching != recomputed
            or len(matching) != 2
            or matching[-1] != end - 1
            or link.get("destinationAddress") != destination
            or embedded.get("matchingRecordIndices") != matching
        ):
            raise ValueError(f"{label} regular sample {index} union topology differs")
        first = unions[holdout.integer(matching[0], "first union index")]
        selected = unions[holdout.integer(matching[-1], "selected union index")]
        if (
            first["prepareRecursionDepth"] != selected["prepareRecursionDepth"]
            or selected["roleBase"] != first["roleBase"] + 48
            or not crop_analysis.same_f64_rect(
                crop_analysis.finite_rect(
                    first["targetBeforeF64"], "first target before"
                ),
                (0.0, 0.0, 0.0, 0.0),
            )
        ):
            raise ValueError(f"{label} regular sample {index} union roles differ")

        private = exact.mapping(public.get("private"), "private record")
        child = crop_analysis.finite_rect(
            private.get("recursiveChildF64"), "recursive child"
        )
        geometry = exact.mapping(base_result.get("geometry"), "geometry")
        canvas_height = crop_analysis.finite(
            geometry.get("windowHeight"), "canvas height"
        )
        transformed = union_validator.transform_child(
            exact.sequence(public.get("carrierPosition"), "carrier position"),
            child,
            canvas_height,
        )
        before = crop_analysis.finite_rect(
            selected["targetBeforeF64"], "selected target before"
        )
        union_input = crop_analysis.finite_rect(
            selected["inputF64"], "selected union input"
        )
        after = crop_analysis.finite_rect(
            selected["targetAfterF64"], "selected target after"
        )
        observed = crop_analysis.finite_rect(
            private.get("aggregateF64"), "observed aggregate"
        )
        if (
            not crop_analysis.same_f64_rect(before, transformed)
            or not crop_analysis.same_f64_rect(
                union_validator.replay_union(before, union_input), after
            )
            or not crop_analysis.same_f64_rect(after, observed)
        ):
            raise ValueError(f"{label} regular sample {index} union replay differs")

        viewport_f64 = crop_analysis.finite_rect(private.get("viewportF64"), "viewport")
        if any(not value.is_integer() for value in viewport_f64):
            raise ValueError(f"{label} regular sample {index} viewport is fractional")
        viewport = tuple(int(value) for value in viewport_f64)
        records.append(
            {
                "label": label,
                "sampleIndex": index,
                "firstUnionRecordIndex": first["recordIndex"],
                "selectedLastUnionRecordIndex": selected["recordIndex"],
                "candidateIntersectionF64": list(before),
                "viewportI32": list(viewport),
                "observedNestedInputI32": list(selected["nestedInputI32"]),
                "observedAggregateF64": list(observed),
            }
        )
        previous_end = end

    trailing = len(unions) - previous_end
    if (
        extension.get("finalTrailingUnionRecordCount") != trailing
        or extension.get("finalLinkedUnionRecordCount") != 64
    ):
        raise ValueError(f"{label} regular union trailing accounting differs")
    return records, {
        "unionRecordCount": len(unions),
        "rejectedUnionCallCount": rejected_calls,
        "destinationMatchedUnionCount": 64,
        "structurallyRetainedTrailingUnionCount": trailing,
    }


def validate_regular_store_structure(
    trace: Mapping[str, Any],
    base_result: Mapping[str, Any],
    timeline: Mapping[str, Any],
    crop_records: Sequence[Any],
    label: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Open the regular producer while retaining its two-stage crop chain."""

    extension = exact.mapping(
        trace.get("cropPolicyHoldoutExtension"), "crop policy extension"
    )
    if (
        extension.get("cropPolicyHoldoutExtensionSchemaVersion")
        != store_validator.EXTENSION_SCHEMA_VERSION
        or extension.get("configuration")
        != store_validator.EXPECTED_EXTENSION_CONFIGURATION
        or extension.get("status") != "finalized"
        or extension.get("statusBeforeFinalization") != "crop-policy-store-active"
    ):
        raise ValueError(f"{label} regular store extension identity differs")

    prepare_start = holdout.integer(
        exact.mapping(trace.get("prepareLayer"), "prepare layer").get("symbolStart"),
        "prepare start",
    )
    instruction_digest = hashlib.sha256(
        bytes.fromhex(store_validator.STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX)
    ).hexdigest()
    if (
        extension.get("prepareLayerSymbolStart") != prepare_start
        or holdout.integer(extension.get("storeBreakpointID"), "store breakpoint") <= 0
        or extension.get("storeInstructionSHA256") != instruction_digest
    ):
        raise ValueError(f"{label} regular store instruction identity differs")

    raw_stores = exact.sequence(extension.get("storeRecords"), "store records")
    if (
        not EXPECTED_RECORD_COUNT
        <= len(raw_stores)
        <= store_validator.MAXIMUM_QUALIFIED_STORE_RECORD_COUNT
    ):
        raise ValueError(f"{label} regular qualified store bounds differ")
    stores = [
        store_validator.validate_store_record(raw, index, prepare_start)
        for index, raw in enumerate(raw_stores)
    ]
    hit_indices = [record["storeHitIndex"] for record in stores]
    if hit_indices != sorted(hit_indices) or len(set(hit_indices)) != len(hit_indices):
        raise ValueError(f"{label} regular store hit order differs")

    rejected = holdout.integer(
        extension.get("finalRejectedStoreCount"), "rejected stores"
    )
    grouped_rejections = 0
    for raw_group in exact.sequence(extension.get("rejectionGroups"), "rejections"):
        group = exact.mapping(raw_group, "store rejection group")
        if group.get("reason") != "caller-chain-excluded":
            raise ValueError(f"{label} regular store rejection reason differs")
        holdout.integer(group.get("prepareRecursionDepth"), "rejection depth")
        grouped_rejections += holdout.integer(
            group.get("hitCount"), "store rejection count"
        )
    if (
        rejected != grouped_rejections
        or extension.get("finalQualifiedStoreRecordCount") != len(stores)
        or extension.get("finalStoreHitCount") != len(stores) + rejected
    ):
        raise ValueError(f"{label} regular store accounting differs")

    links = exact.sequence(extension.get("markerLinks"), "store marker links")
    markers = exact.sequence(trace.get("qualifiedRecords"), "qualified markers")
    union_extension = exact.mapping(
        trace.get("cropUnionOperandExtension"), "union extension"
    )
    raw_unions = exact.sequence(union_extension.get("unionRecords"), "union records")
    union_links = exact.sequence(
        union_extension.get("markerLinks"), "union marker links"
    )
    public_records = exact.sequence(base_result.get("records"), "public records")
    timeline_records = exact.sequence(
        exact.mapping(
            timeline.get("dynamicBackgroundUniforms"), "dynamic uniforms"
        ).get("records"),
        "timeline records",
    )
    if (
        not len(links)
        == len(markers)
        == len(union_links)
        == len(public_records)
        == len(timeline_records)
        == len(crop_records)
        == EXPECTED_RECORD_COUNT
    ):
        raise ValueError(f"{label} regular store marker inventory differs")
    if extension.get("finalMarkerLinkCount") != EXPECTED_RECORD_COUNT:
        raise ValueError(f"{label} regular store marker accounting differs")

    joined: list[dict[str, Any]] = []
    previous_end = 0
    producer_working_stage_counts = {
        "preViewport": 0,
        "postViewport": 0,
        "coincident": 0,
    }
    for index, (raw_link, raw_marker, raw_union_link, raw_crop) in enumerate(
        zip(links, markers, union_links, crop_records, strict=True), start=1
    ):
        link = exact.mapping(raw_link, "store marker link")
        marker = exact.mapping(raw_marker, "qualified marker")
        union_link = exact.mapping(raw_union_link, "union marker link")
        crop = exact.mapping(raw_crop, "crop record")
        start = holdout.integer(link.get("startStoreRecordIndex"), "store start")
        end = holdout.integer(link.get("endStoreRecordIndexExclusive"), "store end")
        union_indices = list(
            exact.sequence(
                union_link.get("matchingUnionRecordIndices"), "matching unions"
            )
        )
        if len(union_indices) != 2:
            raise ValueError(f"{label} regular sample {index} union topology differs")
        selected_union_index = holdout.integer(
            union_indices[-1], "selected union index"
        )
        selected_union = exact.mapping(
            raw_unions[selected_union_index], "selected union"
        )
        selected_layer_shapes = holdout.integer(
            exact.mapping(
                selected_union.get("frameIdentity"), "selected union identity"
            ).get("layerShapesBase"),
            "selected LayerShapes base",
        )
        matching = list(
            exact.sequence(link.get("matchingStoreRecordIndices"), "matching stores")
        )
        recomputed = [
            store["recordIndex"]
            for store in stores[start:end]
            if store["layerShapesBase"] == selected_layer_shapes
        ]
        embedded = exact.mapping(
            marker.get("cropPolicyStoreWindow"), "embedded store window"
        )
        if (
            start != previous_end
            or not start < end <= len(stores)
            or link.get("selectedUnionRecordIndex") != selected_union_index
            or link.get("selectedLayerShapesBase") != selected_layer_shapes
            or matching != recomputed
            or len(matching) != 1
            or embedded.get("startRecordIndex") != start
            or embedded.get("endRecordIndexExclusive") != end
            or embedded.get("selectedUnionRecordIndex") != selected_union_index
            or embedded.get("selectedLayerShapesBase") != selected_layer_shapes
            or embedded.get("matchingStoreRecordIndices") != matching
        ):
            raise ValueError(f"{label} regular sample {index} store link differs")

        mirror_index = holdout.integer(matching[0], "mirror store index")
        producer_index = mirror_index - holdout.TRUE_PRODUCER_STORE_INDEX_DELTA
        sdf_index = mirror_index + SDF_STATE_STORE_INDEX_DELTA_FROM_MIRROR
        if producer_index < start or not producer_index < sdf_index < mirror_index:
            raise ValueError(f"{label} regular sample {index} producer leaves window")
        producer = stores[producer_index]
        sdf_store = stores[sdf_index]
        mirror = stores[mirror_index]
        if (
            producer["recordIndex"] + holdout.TRUE_PRODUCER_STORE_INDEX_DELTA
            != mirror["recordIndex"]
            or producer["roleBase"] + holdout.TRUE_PRODUCER_ROLE_DELTA
            != mirror["roleBase"]
            or producer["prepareRecursionDepth"]
            != mirror["prepareRecursionDepth"] + holdout.TRUE_PRODUCER_DEPTH_DELTA
            or sdf_store["recordIndex"] - mirror["recordIndex"]
            != SDF_STATE_STORE_INDEX_DELTA_FROM_MIRROR
            or sdf_store["roleBase"] - mirror["roleBase"]
            != SDF_STATE_ROLE_DELTA_FROM_MIRROR
            or sdf_store["prepareRecursionDepth"] - mirror["prepareRecursionDepth"]
            != SDF_STATE_DEPTH_DELTA_FROM_MIRROR
        ):
            raise ValueError(f"{label} regular sample {index} producer chain differs")

        observed_crop_values = exact.sequence(
            crop.get("observedNestedInputI32"), "observed crop"
        )
        if len(observed_crop_values) != 4:
            raise ValueError(f"{label} regular sample {index} crop size differs")
        observed_crop = tuple(
            holdout.integer(value, "observed crop") for value in observed_crop_values
        )
        viewport_values = exact.sequence(crop.get("viewportI32"), "viewport")
        if len(viewport_values) != 4:
            raise ValueError(f"{label} regular sample {index} viewport size differs")
        viewport = tuple(
            holdout.integer(value, "viewport") for value in viewport_values
        )
        producer_float = holdout.finite_rect(
            producer["floatingInputF64"], "producer float"
        )
        producer_enclosure = crop_analysis.integer_crop(producer_float)
        producer_crop = crop_analysis.intersect_i32(
            producer_enclosure,
            viewport,  # type: ignore[arg-type]
        )
        producer_working = tuple(producer["workingCropI32"])
        if producer_working == producer_enclosure == observed_crop:
            producer_working_stage = "coincident"
        elif producer_working == producer_enclosure:
            producer_working_stage = "preViewport"
        elif producer_working == observed_crop:
            producer_working_stage = "postViewport"
        else:
            raise ValueError(
                f"{label} regular sample {index} producer working stage differs"
            )
        producer_working_stage_counts[producer_working_stage] += 1
        producer_working_f64 = tuple(float(value) for value in producer_working)
        integer_crop_f64 = tuple(float(value) for value in observed_crop)
        if (
            tuple(sdf_store["workingCropI32"]) != observed_crop
            or not holdout.same_f64(
                holdout.finite_rect(
                    sdf_store["floatingInputF64"], "SDF store floating input"
                ),
                producer_working_f64,
            )
            or tuple(mirror["workingCropI32"]) != observed_crop
            or not holdout.same_f64(
                holdout.finite_rect(
                    mirror["floatingInputF64"], "mirror floating input"
                ),
                integer_crop_f64,
            )
            or producer_crop != observed_crop
        ):
            raise ValueError(f"{label} regular sample {index} crop chain differs")

        payload = holdout.role_payload(raw_stores[producer_index], producer["roleBase"])
        joined.append(
            {
                "label": label,
                "geometry": exact.mapping(base_result.get("geometry"), "geometry").get(
                    "name"
                ),
                "sampleIndex": index,
                "storeWindow": [start, end],
                "pointerCorrelatedMirrorStoreIndex": mirror_index,
                "structuralProducerStoreIndex": producer_index,
                "mirrorRoleBase": mirror["roleBase"],
                "producerRoleBase": producer["roleBase"],
                "mirrorPrepareRecursionDepth": mirror["prepareRecursionDepth"],
                "producerPrepareRecursionDepth": producer["prepareRecursionDepth"],
                "observedProducerF64": list(producer_float),
                "observedProducerHex": exact.f64_hex(producer_float),
                "producerEnclosureI32": list(producer_enclosure),
                "producerWorkingI32": list(producer_working),
                "producerWorkingStage": producer_working_stage,
                "viewportI32": list(viewport),
                "observedCropI32": list(observed_crop),
                "roleIntermediates": holdout.role_intermediates(payload),
            }
        )
        previous_end = end

    trailing = len(stores) - previous_end
    if (
        extension.get("finalLinkedStoreRecordCount") != EXPECTED_RECORD_COUNT
        or extension.get("finalTrailingStoreRecordCount") != trailing
    ):
        raise ValueError(f"{label} regular store trailing accounting differs")
    return joined, {
        "storeRecordCount": len(stores),
        "rejectedStoreCount": rejected,
        "trailingStoreRecordCount": trailing,
        "twoStageRegularCropChainExactCount": len(joined),
        "producerWorkingStageCounts": producer_working_stage_counts,
    }


def terminal_clear_source_bounds(
    producer_records: Sequence[Mapping[str, Any]],
) -> tuple[float, float, float, float]:
    matches = [
        record
        for record in producer_records
        if holdout.integer(record.get("sampleIndex"), "sample index")
        == EXPECTED_RECORD_COUNT
    ]
    if len(matches) != 1:
        raise ValueError("terminal clear source-bound record is not unique")
    role = exact.mapping(matches[0].get("roleIntermediates"), "terminal role")
    transform = exact.sequence(role.get("transformF64"), "terminal transform")
    if len(transform) != 16:
        raise ValueError("terminal clear transform component count differs")
    nominal = exact.rect(role.get("nominalShapeF64"), "terminal nominal shape")
    return (
        exact.finite(transform[12], "terminal source x"),
        exact.finite(transform[13], "terminal source y"),
        nominal[2],
        nominal[3],
    )


def source_bounds(
    material: str, producer_records: Sequence[Mapping[str, Any]]
) -> tuple[float, float, float, float]:
    if material == "clear":
        return terminal_clear_source_bounds(producer_records)
    for record in producer_records:
        role = exact.mapping(record.get("roleIntermediates"), "regular role")
        child = exact.rect(role.get("recursiveChildF64"), "regular recursive child")
        if exact.f64_hex(child) != exact.f64_hex(REGULAR_RECURSIVE_CHILD):
            raise ValueError("regular recursive child differs")
    return REGULAR_SOURCE_BOUNDS


def filter_radius(timeline_record: Mapping[str, Any], material: str) -> float:
    values = exact.mapping(
        exact.mapping(timeline_record.get("filter"), "background filter").get(
            "inputValues"
        ),
        "background filter inputs",
    )
    blur = exact.finite(values.get("inputBlurRadius"), "blur radius")
    bleed = exact.finite(values.get("inputBleedBlurRadius"), "bleed blur radius")
    if material == "clear":
        return max(2.0 * blur, bleed)
    return max(2.0 * blur, 0.5 * bleed)


def foreground_filter_is_live(timeline_record: Mapping[str, Any]) -> bool:
    foreground = exact.mapping(
        timeline_record.get("foregroundFilter"), "foreground filter"
    )
    return foreground.get("filterPresent") is not False


def endpoint_y_offset(
    material: str,
    direction: str,
    producer_depth: int,
    timeline_record: Mapping[str, Any],
    mirror_nominal: tuple[float, float, float, float],
) -> tuple[float, bool]:
    if material != "regular":
        return 0.0, False
    selected_depth = (
        REGULAR_MATERIALIZE_ENDPOINT_DEPTH
        if direction == "materialize"
        else REGULAR_DEMATERIALIZE_ENDPOINT_DEPTH
    )
    applied = (
        foreground_filter_is_live(timeline_record) and producer_depth == selected_depth
    )
    if not applied:
        return 0.0, False
    return mirror_nominal[2] + REGULAR_ENDPOINT_SOURCE_ORIGIN, True


def sdf_entry(
    transformed: tuple[float, float, float, float],
    parameters: tuple[float, float, float, float],
    extra_y_offset: float,
) -> tuple[float, float, float, float]:
    radius, offset_x, offset_y, _padding = parameters
    return (
        transformed[0] - radius + offset_x,
        transformed[1] - radius + offset_y + extra_y_offset,
        transformed[2] + 2.0 * radius,
        transformed[3] + 2.0 * radius,
    )


def structurally_selected_sdf_state(
    raw_stores: Sequence[Any],
    stores: Sequence[Mapping[str, Any]],
    producer_record: Mapping[str, Any],
    material: str,
) -> tuple[
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    dict[str, Any],
]:
    mirror_index = holdout.integer(
        producer_record.get("pointerCorrelatedMirrorStoreIndex"),
        "mirror store index",
    )
    window = exact.sequence(producer_record.get("storeWindow"), "store window")
    if len(window) != 2:
        raise ValueError("store window component count differs")
    start = holdout.integer(window[0], "store window start")
    end = holdout.integer(window[1], "store window end")
    sdf_index = mirror_index + SDF_STATE_STORE_INDEX_DELTA_FROM_MIRROR
    if not start <= sdf_index < end or not 0 <= sdf_index < len(stores):
        raise ValueError("SDF state leaves the authenticated store window")

    mirror = stores[mirror_index]
    sdf_store = stores[sdf_index]
    if (
        mirror.get("roleBase") != producer_record.get("mirrorRoleBase")
        or mirror.get("prepareRecursionDepth")
        != producer_record.get("mirrorPrepareRecursionDepth")
        or sdf_store.get("recordIndex") - mirror.get("recordIndex")
        != SDF_STATE_STORE_INDEX_DELTA_FROM_MIRROR
        or sdf_store.get("roleBase") - mirror.get("roleBase")
        != SDF_STATE_ROLE_DELTA_FROM_MIRROR
        or sdf_store.get("prepareRecursionDepth") - mirror.get("prepareRecursionDepth")
        != SDF_STATE_DEPTH_DELTA_FROM_MIRROR
    ):
        raise ValueError("SDF state structural relation differs")

    sdf_payload = holdout.role_payload(raw_stores[sdf_index], sdf_store["roleBase"])
    parameter_bytes = sdf_payload[
        SDF_PARAMETERS_OFFSET : SDF_PARAMETERS_OFFSET + SDF_PARAMETERS_BYTE_COUNT
    ]
    expected_hex = EXPECTED_SDF_PARAMETERS_HEX[material]
    if parameter_bytes.hex() != expected_hex:
        raise ValueError("SDF float32 parameters differ")
    parameters = struct.unpack("<4f", parameter_bytes)

    mirror_payload = holdout.role_payload(raw_stores[mirror_index], mirror["roleBase"])
    mirror_nominal = struct.unpack_from(
        "<4d", mirror_payload, holdout.ROLE_NOMINAL_SHAPE_OFFSET
    )
    return (
        parameters,
        mirror_nominal,
        {
            "storeIndex": sdf_index,
            "roleBase": sdf_store["roleBase"],
            "prepareRecursionDepth": sdf_store["prepareRecursionDepth"],
            "parametersHex": parameter_bytes.hex(),
            "parametersF32": list(parameters),
        },
    )


def validate(
    trace_path: Path,
    timeline_path: Path,
    expected_geometry: str,
    expected_material: str,
    expected_appearance: str,
    expected_direction: str,
) -> dict[str, Any]:
    if expected_material not in VALID_MATERIALS:
        raise ValueError("expected material differs")
    if expected_appearance not in VALID_APPEARANCES:
        raise ValueError("expected appearance differs")
    if expected_direction not in VALID_DIRECTIONS:
        raise ValueError("expected direction differs")

    base_result, trace, timeline = validate_base(
        trace_path,
        timeline_path,
        expected_geometry,
        expected_material,
        expected_appearance,
        expected_direction,
    )
    if expected_material == "clear":
        crop_records, union_accounting = crop_analysis.validate_extension(
            trace, base_result, timeline, expected_geometry
        )
    else:
        crop_records, union_accounting = validate_regular_union_structure(
            trace, base_result, timeline, expected_geometry
        )
    if expected_material == "clear":
        producer_records, store_accounting = holdout.validate_store_extension(
            trace, base_result, timeline, crop_records, expected_geometry
        )
    else:
        producer_records, store_accounting = validate_regular_store_structure(
            trace, base_result, timeline, crop_records, expected_geometry
        )
    if len(producer_records) != EXPECTED_RECORD_COUNT:
        raise ValueError("profile retry producer record count differs")
    raw_stores, stores = validated_store_inventory(trace)
    frozen_source_bounds = source_bounds(expected_material, producer_records)

    timeline_records = exact.sequence(
        exact.mapping(
            timeline.get("dynamicBackgroundUniforms"), "dynamic uniforms"
        ).get("records"),
        "timeline records",
    )
    if len(timeline_records) != EXPECTED_RECORD_COUNT:
        raise ValueError("profile retry timeline record count differs")

    metric = holdout.ExactMetric()
    records: list[dict[str, Any]] = []
    endpoint_offset_count = 0
    live_foreground_count = 0
    sdf_state_records: list[dict[str, Any]] = []
    for producer_record, raw_timeline in zip(
        producer_records, timeline_records, strict=True
    ):
        timeline_record = exact.mapping(raw_timeline, "timeline record")
        role = exact.mapping(
            producer_record.get("roleIntermediates"), "producer role intermediates"
        )
        transformed = exact.rect(
            role.get("transformedDynamicBoundsF64"),
            "transformed dynamic bounds",
        )
        carrier_values = exact.sequence(
            role.get("carrierTranslationF64"), "carrier translation"
        )
        if len(carrier_values) != 2:
            raise ValueError("carrier translation component count differs")
        carrier = (
            exact.finite(carrier_values[0], "carrier x"),
            exact.finite(carrier_values[1], "carrier y"),
        )
        parameters, mirror_nominal, sdf_state = structurally_selected_sdf_state(
            raw_stores,
            stores,
            producer_record,
            expected_material,
        )
        live_foreground_count += int(foreground_filter_is_live(timeline_record))
        producer_depth = holdout.integer(
            producer_record.get("producerPrepareRecursionDepth"),
            "producer recursion depth",
        )
        y_offset, offset_applied = endpoint_y_offset(
            expected_material,
            expected_direction,
            producer_depth,
            timeline_record,
            mirror_nominal,
        )
        endpoint_offset_count += int(offset_applied)
        entry = sdf_entry(transformed, parameters, y_offset)
        radius = filter_radius(timeline_record, expected_material)
        candidate = exact.replay(
            entry,
            carrier,
            frozen_source_bounds,
            exact.finite(role.get("shadowOffsetF64"), "shadow offset"),
            radius,
        )
        observed = exact.rect(
            producer_record.get("observedProducerF64"), "observed producer"
        )
        is_exact = metric.add(observed, candidate)
        sample_index = holdout.integer(
            producer_record.get("sampleIndex"), "sample index"
        )
        sdf_state_records.append({"sampleIndex": sample_index, **sdf_state})
        records.append(
            {
                "sampleIndex": sample_index,
                "producerPrepareRecursionDepth": producer_depth,
                "foregroundFilterLive": foreground_filter_is_live(timeline_record),
                "mirrorNominalF64": list(mirror_nominal),
                "endpointYOffsetApplied": offset_applied,
                "endpointYOffsetF64": y_offset,
                "endpointYOffsetHex": exact.f64_hex((y_offset,)),
                "sdfEntryF64": list(entry),
                "sdfEntryHex": exact.f64_hex(entry),
                "filterRadiusF64": radius,
                "filterRadiusHex": exact.f64_hex((radius,)),
                "observedProducerF64": list(observed),
                "observedProducerHex": exact.f64_hex(observed),
                "replayF64": list(candidate),
                "replayHex": exact.f64_hex(candidate),
                "exact": is_exact,
            }
        )

    expected_endpoint_count = 1 if expected_material == "regular" else 0
    if endpoint_offset_count != expected_endpoint_count:
        raise ValueError("endpoint-adjacent SDF y-offset branch count differs")
    metric_result = metric.result()
    if (
        metric_result["rectangleCount"] != EXPECTED_RECORD_COUNT
        or metric_result["exactRectangleCount"] != EXPECTED_RECORD_COUNT
        or metric_result["exactComponentCount"] != EXPECTED_RECORD_COUNT * 4
    ):
        raise ValueError("exact FilterOp profile-transfer retry replay differs")

    return {
        "prepareLayerFilterMapBoundsProfileTransferRetryValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            "prospectively frozen output-blind exact binary64 profile-transfer "
            "retry; SDF state and floating producer are selected only by store "
            "order, role-base delta, recursion depth, and marker interval"
        ),
        "conclusion": "success",
        "inputs": {
            "traceSHA256": crop_validator.sha256_file(trace_path),
            "timelineSHA256": crop_validator.sha256_file(timeline_path),
        },
        "profile": {
            "material": expected_material,
            "appearance": expected_appearance,
            "direction": expected_direction,
            "geometry": expected_geometry,
            "backingScaleFactor": 1,
        },
        "metadataAdapter": {
            "actualProfileAuthenticatedBeforeNormalization": True,
            "onlyMaterialAppearanceDirectionNormalized": True,
            "dematerializeObservedTopologyAuthenticated": (
                expected_direction == "dematerialize"
            ),
            "traceBytesChanged": False,
            "timelineBytesChanged": False,
            "cropOrProducerValuesInspectedForSelection": False,
        },
        "sourceBounds": {
            "branch": expected_material,
            "rule": (
                "terminal producer transform x/y plus nominal width/height"
                if expected_material == "clear"
                else "frozen regular FilterOp source DOD, independently observed "
                "as the centered 1360-square recursive child"
            ),
            "cropOrProducerValuesUsed": False,
            "f64": list(frozen_source_bounds),
            "hex": exact.f64_hex(frozen_source_bounds),
        },
        "sdfState": {
            "storeIndexDeltaFromMirror": SDF_STATE_STORE_INDEX_DELTA_FROM_MIRROR,
            "roleBaseDeltaFromMirror": SDF_STATE_ROLE_DELTA_FROM_MIRROR,
            "prepareDepthDeltaFromMirror": SDF_STATE_DEPTH_DELTA_FROM_MIRROR,
            "parametersOffset": SDF_PARAMETERS_OFFSET,
            "expectedParametersHex": EXPECTED_SDF_PARAMETERS_HEX[expected_material],
            "recordCount": len(sdf_state_records),
            "cropOrProducerValuesUsedForSelection": False,
            "records": sdf_state_records,
        },
        "filterArithmetic": {
            "radiusRule": (
                "max(2 * inputBlurRadius, inputBleedBlurRadius)"
                if expected_material == "clear"
                else "max(2 * inputBlurRadius, 0.5 * inputBleedBlurRadius)"
            ),
            "binary64FMARequired": True,
            "toleranceUsed": False,
        },
        "endpointYOffset": {
            "rule": (
                "regular live-foreground producer depth 6 while materializing or "
                "depth 7 while dematerializing uses mirror nominalShapeF64[2] + 280"
            ),
            "foregroundFilterLiveRecordCount": live_foreground_count,
            "appliedRecordCount": endpoint_offset_count,
            "cropOrProducerValuesUsedForSelection": False,
        },
        "floatingReplay": {
            **metric_result,
            "allRectanglesExact": True,
            "allComponentsExact": True,
            "records": records,
        },
        "structuralSelection": {
            "producerStoreIndexDelta": holdout.TRUE_PRODUCER_STORE_INDEX_DELTA,
            "producerRoleDelta": holdout.TRUE_PRODUCER_ROLE_DELTA,
            "producerDepthDelta": holdout.TRUE_PRODUCER_DEPTH_DELTA,
            "cropOrProducerValuesUsedForSelection": False,
            **union_accounting,
            **store_accounting,
        },
        "sealedConclusion": {
            "singleProfileExactCropReplayPassed": True,
            "allSDFStatesStructurallyAuthenticated": True,
            "allFloatingProducerRectanglesBitExact": True,
            "allDownstreamIntegerCropsExact": True,
            "completeProfileMatrixPassed": False,
            "filterOpCropProfileTransferPassed": False,
            "opticalMaterialAppearanceDirectionTransferPassed": False,
            "physicalRetina2xAndColorTransferPassed": False,
            "independentWalleZeroByteFrameParityPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--expected-geometry", required=True)
    parser.add_argument("--expected-material", required=True, choices=VALID_MATERIALS)
    parser.add_argument(
        "--expected-appearance", required=True, choices=VALID_APPEARANCES
    )
    parser.add_argument("--expected-direction", required=True, choices=VALID_DIRECTIONS)
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
