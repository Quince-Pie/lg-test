#!/usr/bin/env python3
"""Validate one structurally selected regular-material FilterOp trace.

The historical clear-material antecedent includes a clear-only public crop
formula.  This diagnostic replaces only that antecedent with the already
observed pointer/store relation, then delegates every instruction, code, and
FilterOp entry/return check to the frozen validator.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import analyze_prepare_layer_crop_policy_holdout_callback_retry as holdout
import validate_prepare_layer_crop_policy_holdout as store_validator
import validate_prepare_layer_crop_producer_callee as producer_validator
import validate_prepare_layer_crop_transfer as crop_validator
import validate_prepare_layer_crop_union_operand as union_validator
import validate_prepare_layer_filter_map_bounds as frozen
import validate_prepare_layer_mask_instruction_trace as frozen_mask


EXPECTED_GEOMETRY = "circle-800-center"
EXPECTED_MATERIAL = "regular"
EXPECTED_APPEARANCE = "light"
EXPECTED_DIRECTION = "materialize"


def validate_base(
    trace_path: Path, timeline_path: Path
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    original_timeline_validator = crop_validator.validate_timeline

    def validate_profile_timeline(
        timeline: Mapping[str, Any], expected_geometry: str
    ) -> tuple[Mapping[str, Any], list[Any]]:
        if (
            timeline.get("material") != EXPECTED_MATERIAL
            or timeline.get("appearance") != EXPECTED_APPEARANCE
            or timeline.get("direction") != EXPECTED_DIRECTION
        ):
            raise ValueError("regular diagnostic profile metadata differs")
        normalized = dict(timeline)
        normalized["material"] = "clear"
        normalized["appearance"] = "light"
        normalized["direction"] = "materialize"
        return original_timeline_validator(normalized, expected_geometry)

    crop_validator.validate_timeline = validate_profile_timeline
    try:
        crop_validator.validate(trace_path, timeline_path, EXPECTED_GEOMETRY)
    finally:
        crop_validator.validate_timeline = original_timeline_validator
    trace = holdout.mapping(crop_validator.load_json(trace_path, "trace"), "trace")
    timeline = holdout.mapping(
        crop_validator.load_json(timeline_path, "timeline"), "timeline"
    )
    return trace, timeline


def structural_producer_records(
    trace: Mapping[str, Any], prepare_start: int
) -> list[dict[str, Any]]:
    store_extension = holdout.mapping(
        trace.get("cropPolicyHoldoutExtension"), "store extension"
    )
    raw_stores = holdout.sequence(store_extension.get("storeRecords"), "store records")
    stores = [
        store_validator.validate_store_record(raw, index, prepare_start)
        for index, raw in enumerate(raw_stores)
    ]
    store_links = holdout.sequence(
        store_extension.get("markerLinks"), "store marker links"
    )

    union_extension = holdout.mapping(
        trace.get("cropUnionOperandExtension"), "union extension"
    )
    raw_unions = holdout.sequence(union_extension.get("unionRecords"), "union records")
    unions = [
        union_validator.validate_union_record(raw, index, prepare_start)
        for index, raw in enumerate(raw_unions)
    ]
    union_links = holdout.sequence(
        union_extension.get("markerLinks"), "union marker links"
    )
    if len(store_links) != 32 or len(union_links) != 32:
        raise ValueError("regular diagnostic marker-link inventory differs")

    records = []
    for sample_index, (raw_store_link, raw_union_link) in enumerate(
        zip(store_links, union_links, strict=True), start=1
    ):
        store_link = holdout.mapping(raw_store_link, "store marker link")
        union_link = holdout.mapping(raw_union_link, "union marker link")
        union_indices = [
            holdout.integer(value, "matching union index")
            for value in holdout.sequence(
                union_link.get("matchingUnionRecordIndices"), "matching unions"
            )
        ]
        if len(union_indices) != 2:
            raise ValueError(
                f"regular diagnostic sample {sample_index} union topology differs"
            )
        selected_union_index = union_indices[-1]
        selected_union = unions[selected_union_index]
        start = holdout.integer(
            store_link.get("startStoreRecordIndex"), "store window start"
        )
        end = holdout.integer(
            store_link.get("endStoreRecordIndexExclusive"), "store window end"
        )
        mirror_indices = [
            int(store["recordIndex"])
            for store in stores[start:end]
            if store["layerShapesBase"] == selected_union["layerShapesBase"]
        ]
        if len(mirror_indices) != 1:
            raise ValueError(
                f"regular diagnostic sample {sample_index} mirror differs"
            )
        mirror = stores[mirror_indices[0]]
        producer_index = int(mirror["recordIndex"]) - holdout.TRUE_PRODUCER_STORE_INDEX_DELTA
        if producer_index < start:
            raise ValueError(
                f"regular diagnostic sample {sample_index} producer leaves window"
            )
        producer = stores[producer_index]
        if (
            producer["recordIndex"] + holdout.TRUE_PRODUCER_STORE_INDEX_DELTA
            != mirror["recordIndex"]
            or producer["roleBase"] + holdout.TRUE_PRODUCER_ROLE_DELTA
            != mirror["roleBase"]
            or producer["prepareRecursionDepth"]
            != mirror["prepareRecursionDepth"] + holdout.TRUE_PRODUCER_DEPTH_DELTA
            or store_link.get("selectedUnionRecordIndex") != selected_union_index
            or store_link.get("selectedLayerShapesBase")
            != selected_union["layerShapesBase"]
        ):
            raise ValueError(
                f"regular diagnostic sample {sample_index} producer relation differs"
            )
        records.append(
            {
                "sampleIndex": sample_index,
                "producerRoleBase": producer["roleBase"],
                "observedProducerHex": producer["floatingInputHex"],
            }
        )
    return records


def validate(
    trace_path: Path, timeline_path: Path, inventory_path: Path
) -> dict[str, Any]:
    trace, timeline = validate_base(trace_path, timeline_path)
    prepare_start = holdout.integer(
        holdout.mapping(trace.get("prepareLayer"), "prepare layer").get("symbolStart"),
        "prepare layer start",
    )
    opened_records = structural_producer_records(trace, prepare_start)
    inventory, ordinal, inventory_sha = producer_validator.validate_inventory_transport(
        trace, inventory_path
    )

    original_filter_geometry = frozen.EXPECTED_GEOMETRY
    original_mask_geometry = frozen_mask.EXPECTED_GEOMETRY
    original_antecedent = producer_validator.validate_antecedent

    def validate_regular_antecedent(
        actual_trace_path: Path,
        actual_timeline_path: Path,
        actual_inventory_path: Path,
        expected_geometry: str,
    ) -> tuple[
        Mapping[str, Any],
        Mapping[str, Any],
        list[dict[str, Any]],
        Mapping[str, Any],
        int,
        str,
    ]:
        if (
            actual_trace_path != trace_path
            or actual_timeline_path != timeline_path
            or actual_inventory_path != inventory_path
            or expected_geometry != EXPECTED_GEOMETRY
        ):
            raise ValueError("regular diagnostic antecedent inputs differ")
        return trace, timeline, opened_records, inventory, ordinal, inventory_sha

    frozen.EXPECTED_GEOMETRY = EXPECTED_GEOMETRY
    frozen_mask.EXPECTED_GEOMETRY = EXPECTED_GEOMETRY
    producer_validator.validate_antecedent = validate_regular_antecedent
    try:
        result = frozen.validate(
            trace_path, timeline_path, inventory_path, EXPECTED_GEOMETRY
        )
    finally:
        frozen.EXPECTED_GEOMETRY = original_filter_geometry
        frozen_mask.EXPECTED_GEOMETRY = original_mask_geometry
        producer_validator.validate_antecedent = original_antecedent

    result["prepareLayerFilterMapBoundsRegularDiagnosticValidationSchemaVersion"] = 1
    result["classification"] = (
        "prospective output-blind regular-material FilterOp instruction diagnostic; "
        "the clear-only public crop antecedent is replaced by the frozen structural "
        "mirror-minus-two store relation, while the complete FilterOp validator is "
        "otherwise unchanged"
    )
    result["profile"] = {
        "material": EXPECTED_MATERIAL,
        "appearance": EXPECTED_APPEARANCE,
        "direction": EXPECTED_DIRECTION,
        "geometry": EXPECTED_GEOMETRY,
        "backingScaleFactor": 1,
    }
    result["antecedentAdapter"] = {
        "producerStoreIndexDelta": holdout.TRUE_PRODUCER_STORE_INDEX_DELTA,
        "producerRoleDelta": holdout.TRUE_PRODUCER_ROLE_DELTA,
        "producerDepthDelta": holdout.TRUE_PRODUCER_DEPTH_DELTA,
        "structuralProducerRecordCount": len(opened_records),
        "cropOrOutputValuesUsedForSelection": False,
        "filterInstructionValidatorChanged": False,
        "traceBytesChanged": False,
        "timelineBytesChanged": False,
    }
    result["sealedConclusion"]["regularMaterialDiagnosticPassed"] = True
    result["sealedConclusion"]["completeProfileMatrixPassed"] = False
    result["sealedConclusion"]["liquidGlassParityEstablished"] = False
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(
        arguments.trace,
        arguments.timeline,
        arguments.inventory,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
