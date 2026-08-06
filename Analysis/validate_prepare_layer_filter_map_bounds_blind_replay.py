#!/usr/bin/env python3
"""Validate the frozen exact FilterOp decoder on one unseen geometry."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_prepare_layer_crop_policy_holdout_callback_retry as holdout
import analyze_prepare_layer_crop_union_operand_matrix as crop_analysis
import analyze_prepare_layer_filter_map_bounds_exact_replay as exact
import validate_prepare_layer_crop_transfer as crop_validator


VALIDATION_SCHEMA_VERSION = 1
EXPECTED_RECORD_COUNT = 32


def terminal_source_bounds(
    records: Sequence[Mapping[str, Any]],
) -> tuple[float, float, float, float]:
    matches = [record for record in records if int(record.get("sampleIndex")) == 32]
    if len(matches) != 1:
        raise ValueError("terminal source-bound record is not unique")
    role = exact.mapping(matches[0].get("roleIntermediates"), "terminal role")
    transform = exact.sequence(role.get("transformF64"), "terminal transform")
    if len(transform) != 16:
        raise ValueError("terminal transform component count differs")
    nominal = exact.rect(role.get("nominalShapeF64"), "terminal nominal shape")
    return (
        exact.finite(transform[12], "terminal transform x"),
        exact.finite(transform[13], "terminal transform y"),
        nominal[2],
        nominal[3],
    )


def validate(
    trace_path: Path, timeline_path: Path, expected_geometry: str
) -> dict[str, Any]:
    base_result = crop_validator.validate(trace_path, timeline_path, expected_geometry)
    trace = exact.mapping(crop_validator.load_json(trace_path, "trace"), "trace")
    timeline = exact.mapping(
        crop_validator.load_json(timeline_path, "timeline"), "timeline"
    )
    crop_records, union_accounting = crop_analysis.validate_extension(
        trace, base_result, timeline, expected_geometry
    )
    producer_records, store_accounting = holdout.validate_store_extension(
        trace, base_result, timeline, crop_records, expected_geometry
    )
    if len(producer_records) != EXPECTED_RECORD_COUNT:
        raise ValueError("blind replay record count differs")
    source_bounds = terminal_source_bounds(producer_records)

    timeline_records = exact.sequence(
        exact.mapping(
            timeline.get("dynamicBackgroundUniforms"), "dynamic uniforms"
        ).get("records"),
        "timeline records",
    )
    if len(timeline_records) != EXPECTED_RECORD_COUNT:
        raise ValueError("blind replay timeline count differs")

    metric = holdout.ExactMetric()
    records: list[dict[str, Any]] = []
    for record, raw_timeline in zip(producer_records, timeline_records, strict=True):
        role = exact.mapping(record.get("roleIntermediates"), "role intermediates")
        transformed = exact.rect(
            role.get("transformedDynamicBoundsF64"),
            "transformed dynamic bounds",
        )
        entry = (
            transformed[0] - 9.0,
            transformed[1] - 9.0,
            transformed[2] + 18.0,
            transformed[3] + 18.0,
        )
        carrier_values = exact.sequence(
            role.get("carrierTranslationF64"), "carrier translation"
        )
        carrier = (
            exact.finite(carrier_values[0], "carrier x"),
            exact.finite(carrier_values[1], "carrier y"),
        )
        timeline_record = exact.mapping(raw_timeline, "timeline record")
        candidate = exact.replay(
            entry,
            carrier,
            source_bounds,
            exact.finite(role.get("shadowOffsetF64"), "shadow offset"),
            exact.filter_radius(timeline_record),
        )
        observed = exact.rect(record.get("observedProducerF64"), "observed producer")
        is_exact = metric.add(observed, candidate)
        records.append(
            {
                "sampleIndex": int(record.get("sampleIndex")),
                "entryF64": list(entry),
                "entryHex": exact.f64_hex(entry),
                "observedProducerF64": list(observed),
                "observedProducerHex": exact.f64_hex(observed),
                "replayF64": list(candidate),
                "replayHex": exact.f64_hex(candidate),
                "exact": is_exact,
            }
        )

    metric_result = metric.result()
    exact_pass = (
        metric_result["rectangleCount"] == EXPECTED_RECORD_COUNT
        and metric_result["exactRectangleCount"] == EXPECTED_RECORD_COUNT
        and metric_result["exactComponentCount"] == EXPECTED_RECORD_COUNT * 4
    )
    if not exact_pass:
        raise ValueError("blind FilterOp replay differs")
    return {
        "prepareLayerFilterMapBoundsBlindReplayValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            "prospectively frozen output-blind exact binary64 replay using "
            "only structurally selected producer records, public filter "
            "inputs, and the terminal-role source-bound rule"
        ),
        "conclusion": "success",
        "expectedGeometry": expected_geometry,
        "sourceBounds": {
            "rule": (
                "terminal sample 32 transformF64[12:14] plus terminal "
                "nominalShapeF64[2:4]"
            ),
            "sampleIndex": 32,
            "cropOrProducerValuesUsed": False,
            "f64": list(source_bounds),
            "hex": exact.f64_hex(source_bounds),
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
            "terminalSourceBoundsDerivedWithoutCropValues": True,
            "exactFilterOperationOrderReplayed": True,
            "allFloatingProducerRectanglesBitExact": True,
            "allDownstreamIntegerCropsExact": True,
            "unseenGeometryCropReplayPassed": True,
            "materialAppearanceDirectionTransferPassed": False,
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
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.trace, arguments.timeline, arguments.expected_geometry)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
