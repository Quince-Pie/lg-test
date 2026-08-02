#!/usr/bin/env python3
"""Audit a fixed-state allocation run even when its frozen gate failed."""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_dynamic_allocation_holdout as allocation
import validate_dynamic_allocation_fixed_state as fixed
import validate_dynamic_allocation_holdout as holdout


CLASSIFICATION = (
    "post-opening-audit-of-failed-preregistered-fixed-state-calibration; "
    "not-an-accepted-calibration-or-unseen-transfer"
)
EXPECTED_RUN_ID = 30_752_897_393
SNAPSHOT_STORAGE_HASH_FIELDS = frozenset(
    {
        "mvpPayloadSHA256",
        "vertexPayloadSHA256",
    }
)
DRAW_CONSUMED_HASH_FIELDS = (
    "vertexDrawConsumedPayloadSHA256",
    "mvpDrawConsumedPayloadSHA256",
    "indexDrawConsumedPayloadSHA256",
)
INVARIANT_POLICY_FIELDS = (
    "cropOrigin",
    "textureCoordinateClamp",
    "producerExtent",
    "destinationExtent",
    "copyOffset",
    "effectiveOrigin",
)
EDGE_NAMES = allocation.EDGE_NAMES


def metric(component_count: int, mismatch_count: int) -> dict[str, Any]:
    if component_count < 0 or not 0 <= mismatch_count <= component_count:
        raise ValueError("invalid exactness metric")
    return {
        "componentCount": component_count,
        "mismatchedComponents": mismatch_count,
        "exact": mismatch_count == 0,
    }


def semantic_policy(value: Mapping[str, Any]) -> dict[str, Any]:
    """Drop hashes of snapshot storage bytes that the draw does not consume."""
    result = copy.deepcopy(dict(value))
    mesh = dict(holdout.mapping(result.get("producerMesh"), "producer mesh"))
    for name in SNAPSHOT_STORAGE_HASH_FIELDS:
        mesh.pop(name, None)
    result["producerMesh"] = mesh
    return result


def primary_edges(value: Mapping[str, Any]) -> list[float]:
    mesh = holdout.mapping(value.get("producerMesh"), "producer mesh")
    return allocation.primary_position_bounds(mesh.get("primaryVertices"))


def edge_delta(
    reference: Mapping[str, Any], observed: Mapping[str, Any]
) -> list[float]:
    return [
        actual - expected
        for actual, expected in zip(
            primary_edges(observed),
            primary_edges(reference),
            strict=True,
        )
    ]


def draw_consumed_hashes(value: Mapping[str, Any]) -> dict[str, str]:
    mesh = holdout.mapping(value.get("producerMesh"), "producer mesh")
    hashes: dict[str, str] = {}
    for name in DRAW_CONSUMED_HASH_FIELDS:
        digest = mesh.get(name)
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError(f"draw-consumed hash is missing: {name}")
        hashes[name] = digest
    return hashes


def _validate_fixed_header(
    fixed_evidence: Mapping[str, Any], expected_record_count: int
) -> Sequence[Any]:
    if (
        fixed_evidence.get("schemaVersion") != 1
        or fixed_evidence.get("requested") is not True
        or fixed_evidence.get("executed") is not True
        or fixed_evidence.get("sourceSampleIndices")
        != list(fixed.EXPECTED_SOURCE_SAMPLE_INDICES)
        or fixed_evidence.get("translationCount") != len(fixed.EXPECTED_TRANSLATIONS)
        or fixed_evidence.get("expectedRecordCount") != expected_record_count
        or fixed_evidence.get("executedRecordCount") != expected_record_count
        or fixed_evidence.get("translatedBoundsAndPositionPaths")
        != [list(path) for path in fixed.EXPECTED_BOUNDS_AND_POSITION_PATHS]
        or fixed_evidence.get("translatedPositionOnlyPaths")
        != [list(path) for path in fixed.EXPECTED_POSITION_ONLY_PATHS]
        or not holdout.no_raw_stage_dumps(fixed_evidence)
    ):
        raise ValueError("fixed-state intervention header differs")
    records = fixed.sequence(fixed_evidence.get("records"), "fixed-state records")
    if len(records) != expected_record_count:
        raise ValueError("fixed-state record count differs")
    return records


def analyze(
    timeline_path: Path,
    *,
    preregistration_path: Path,
    run_id: int,
) -> dict[str, Any]:
    if run_id != EXPECTED_RUN_ID:
        raise ValueError(f"this immutable audit is frozen for run {EXPECTED_RUN_ID}")
    preregistration = holdout.mapping(
        json.loads(preregistration_path.read_text(encoding="utf-8")),
        "fixed-state preregistration",
    )
    if preregistration.get("schemaVersion") != 1:
        raise ValueError("fixed-state preregistration schema differs")

    base = holdout.validate(
        timeline_path,
        expected_geometry=fixed.EXPECTED_GEOMETRY,
        expected_sample_indices=fixed.EXPECTED_SAMPLE_INDICES,
        classification=CLASSIFICATION,
        allowed_geometries=frozenset({fixed.EXPECTED_GEOMETRY}),
        require_primary_source_q_exact=False,
    )
    report = holdout.mapping(
        json.loads(timeline_path.read_text(encoding="utf-8")),
        "transition report",
    )
    uniforms = holdout.mapping(
        report.get("dynamicBackgroundUniforms"),
        "dynamic background uniforms",
    )
    fixed_evidence = holdout.mapping(
        uniforms.get("fixedStateInterventions"),
        "fixed-state interventions",
    )
    expected_record_count = len(fixed.EXPECTED_SOURCE_SAMPLE_INDICES) * len(
        fixed.EXPECTED_TRANSLATIONS
    )
    untyped_records = _validate_fixed_header(fixed_evidence, expected_record_count)

    normal_records = {
        int(
            holdout.mapping(value, "normal dynamic record")["sampleIndex"]
        ): holdout.mapping(value, "normal dynamic record")
        for value in fixed.sequence(uniforms.get("records"), "normal records")
    }
    normal_states = {
        int(
            holdout.mapping(value, "normal validated state")["sampleIndex"]
        ): holdout.mapping(value, "normal validated state")
        for value in fixed.sequence(base.get("states"), "normal validated states")
    }
    expected_order = [
        (sample_index, translation_index, name, delta)
        for sample_index in fixed.EXPECTED_SOURCE_SAMPLE_INDICES
        for translation_index, (name, delta) in enumerate(fixed.EXPECTED_TRANSLATIONS)
    ]

    source_layer_hashes: dict[int, str] = {}
    source_filter_hashes: dict[int, str] = {}
    extracted_records: list[dict[str, Any]] = []
    extraction_failures: list[dict[str, Any]] = []
    edge_change_records: list[dict[str, Any]] = []
    invariant_residuals: list[dict[str, Any]] = []
    q_components = 0
    q_mismatches = 0
    invariant_components = 0
    invariant_mismatches = 0
    topology_mismatches = 0
    zero_semantic_matches = 0
    zero_draw_hash_matches = 0
    edge_components = 0
    edge_mismatches = 0
    edge_delta_counts: Counter[tuple[str, float]] = Counter()
    changed_record_groups: Counter[str] = Counter()

    for untyped_record, expected in zip(untyped_records, expected_order, strict=True):
        sample_index, translation_index, translation_name, delta = expected
        record = holdout.mapping(untyped_record, "fixed-state record")
        translation = tuple(
            int(value)
            for value in fixed.sequence(record.get("translation"), "translation")
        )
        if (
            record.get("sampleIndex") != sample_index
            or record.get("translationIndex") != translation_index
            or record.get("translationName") != translation_name
            or translation != delta
            or record.get("executed") is not True
            or record.get("originalProducerInput") is not True
            or record.get("filterInputValuesUnchanged") is not True
            or record.get("missingCriticalCarrierPaths") != []
        ):
            raise ValueError(
                f"fixed-state record differs at {sample_index}/{translation_name}"
            )
        normal_record = normal_records[sample_index]
        remaining = holdout.numeric(record.get("remaining"), "remaining")
        if remaining != holdout.numeric(
            normal_record.get("remaining"), "normal remaining"
        ):
            raise ValueError("fixed and normal remaining values differ")

        source_layer_hash = record.get("sourceLayerStatesSHA256")
        source_filter_hash = record.get("sourceFilterInputValuesSHA256")
        replayed_filter_hash = record.get("replayedFilterInputValuesSHA256")
        if (
            not isinstance(source_layer_hash, str)
            or len(source_layer_hash) != 64
            or not isinstance(source_filter_hash, str)
            or len(source_filter_hash) != 64
            or source_filter_hash != replayed_filter_hash
        ):
            raise ValueError("fixed-state source identity differs")
        if (
            source_layer_hashes.setdefault(sample_index, source_layer_hash)
            != source_layer_hash
            or source_filter_hashes.setdefault(sample_index, source_filter_hash)
            != source_filter_hash
        ):
            raise ValueError("fixed-state source changed within one sample")

        expected_states = fixed.translated_layer_states(
            fixed.sequence(
                normal_record.get("capturedLayerStates"),
                "normal captured layer states",
            ),
            delta,
        )
        translated_states = list(
            fixed.sequence(record.get("translatedLayerStates"), "translated states")
        )
        reported_captured_states = list(
            fixed.sequence(record.get("capturedLayerStates"), "reported states")
        )
        if (
            translated_states != expected_states
            or reported_captured_states != expected_states
        ):
            raise ValueError("reported fixed-state replay changed undeclared state")

        scale, layer_state_count = holdout.captured_scale(record)
        if scale != 1.0 - remaining / 2.0:
            raise ValueError("fixed-state backdrop scale differs")
        try:
            observed = holdout.observed_policy(
                record,
                scale=scale,
                require_primary_source_q_exact=False,
            )
        except ValueError as error:
            render = holdout.mapping(record.get("render"), "fixed-state render")
            probe = holdout.mapping(
                render.get("metalUniformProbe"), "fixed-state Metal probe"
            )
            probe_records = fixed.sequence(probe.get("records"), "Metal records")
            extraction_failures.append(
                {
                    "sampleIndex": sample_index,
                    "translationIndex": translation_index,
                    "translationName": translation_name,
                    "translation": list(delta),
                    "error": str(error),
                    "metalRecordCount": len(probe_records),
                    "glassFragmentUniformBindingCount": render.get(
                        "glassFragmentUniformBindingCount"
                    ),
                }
            )
            continue

        mesh = holdout.mapping(observed.get("producerMesh"), "producer mesh")
        record_q_components = int(mesh["sourceScaleComponentCount"])
        record_q_mismatches = int(mesh["sourceScaleMismatchedComponents"])
        q_components += record_q_components
        q_mismatches += record_q_mismatches
        reference = holdout.mapping(
            normal_states[sample_index].get("observed"), "normal policy"
        )

        for field in INVARIANT_POLICY_FIELDS:
            expected_values = list(
                fixed.sequence(reference.get(field), f"normal {field}")
            )
            observed_values = list(
                fixed.sequence(observed.get(field), f"fixed {field}")
            )
            if len(expected_values) != len(observed_values):
                raise ValueError(f"fixed policy field length differs: {field}")
            invariant_components += len(expected_values)
            for component, (expected_value, observed_value) in enumerate(
                zip(expected_values, observed_values, strict=True)
            ):
                if expected_value == observed_value:
                    continue
                invariant_mismatches += 1
                invariant_residuals.append(
                    {
                        "sampleIndex": sample_index,
                        "translationName": translation_name,
                        "field": field,
                        "component": component,
                        "expected": expected_value,
                        "observed": observed_value,
                    }
                )
        reference_mesh = holdout.mapping(
            reference.get("producerMesh"), "normal producer mesh"
        )
        topology_mismatches += int(mesh["vertexCount"]) != int(
            reference_mesh["vertexCount"]
        )

        delta_edges = edge_delta(reference, observed)
        edge_components += len(delta_edges)
        changed_edges = []
        for edge_name, difference in zip(EDGE_NAMES, delta_edges, strict=True):
            if difference == 0:
                continue
            edge_mismatches += 1
            edge_delta_counts[(edge_name, difference)] += 1
            changed_edges.append(
                {
                    "edge": edge_name,
                    "difference": difference,
                }
            )
        if changed_edges:
            if translation_name.startswith("x-"):
                group = "x-only"
            elif translation_name.startswith("y-"):
                group = "y-only"
            else:
                group = "combined-target"
            changed_record_groups[group] += 1
            edge_change_records.append(
                {
                    "sampleIndex": sample_index,
                    "remaining": remaining,
                    "translationName": translation_name,
                    "translation": list(delta),
                    "changes": changed_edges,
                }
            )

        if translation_name == "base":
            zero_semantic_matches += semantic_policy(observed) == semantic_policy(
                reference
            )
            zero_draw_hash_matches += draw_consumed_hashes(
                observed
            ) == draw_consumed_hashes(reference)

        extracted_records.append(
            {
                "sampleIndex": sample_index,
                "remaining": remaining,
                "runtimeScale": scale,
                "translationIndex": translation_index,
                "translationName": translation_name,
                "translation": list(delta),
                "capturedLayerStateCount": layer_state_count,
                "producerVertexCount": int(mesh["vertexCount"]),
                "primaryEdges": primary_edges(observed),
                "primaryEdgeDeltaFromNormal": delta_edges,
                "primarySourceQ": metric(record_q_components, record_q_mismatches),
                "drawConsumedPayloadSHA256": draw_consumed_hashes(observed),
            }
        )

    normal_q_components = 0
    normal_q_mismatches = 0
    normal_q_residual_samples: list[dict[str, Any]] = []
    for untyped_state in fixed.sequence(base.get("states"), "normal states"):
        state = holdout.mapping(untyped_state, "normal state")
        mesh = holdout.mapping(
            holdout.mapping(state.get("observed"), "normal policy").get("producerMesh"),
            "normal mesh",
        )
        components = int(mesh["sourceScaleComponentCount"])
        mismatches = int(mesh["sourceScaleMismatchedComponents"])
        normal_q_components += components
        normal_q_mismatches += mismatches
        if mismatches:
            normal_q_residual_samples.append(
                {
                    "sampleIndex": int(state["sampleIndex"]),
                    "remaining": state["remaining"],
                    "mismatchedComponents": mismatches,
                }
            )

    zero_count = len(fixed.EXPECTED_SOURCE_SAMPLE_INDICES)
    live_readback_keys = {
        "liveLayerStatesBeforeRender",
        "liveLayerStatesAfterRender",
    }
    independent_live_readback_available = all(
        live_readback_keys <= set(holdout.mapping(record, "record"))
        for record in untyped_records
    )
    intervention_q_exact = q_mismatches == 0
    fixed_gate_passed = (
        not extraction_failures
        and intervention_q_exact
        and zero_semantic_matches == zero_count
        and zero_draw_hash_matches == zero_count
        and invariant_mismatches == 0
        and topology_mismatches == 0
        and independent_live_readback_available
    )

    return {
        "dynamicAllocationFixedStateFailedRunAnalysisSchemaVersion": 1,
        "classification": CLASSIFICATION,
        "runID": run_id,
        "timelineArtifact": timeline_path.parent.name + "/" + timeline_path.name,
        "timelineSHA256": holdout.sha256_file(timeline_path),
        "preregistrationArtifact": preregistration_path.name,
        "preregistrationSHA256": holdout.sha256_file(preregistration_path),
        "geometry": report.get("geometry"),
        "frozenValidatorSHA256": holdout.mapping(
            preregistration.get("frozenImplementation"), "frozen implementation"
        ).get("fixedStateValidatorSHA256"),
        "aggregate": {
            "expectedInterventionCount": expected_record_count,
            "extractableInterventionCount": len(extracted_records),
            "producerExtractionFailureCount": len(extraction_failures),
            "primaryProducerSourceQ": metric(q_components, q_mismatches),
            "normalTimelinePrimaryProducerSourceQ": metric(
                normal_q_components, normal_q_mismatches
            ),
            "normalTimelineQResidualSamples": normal_q_residual_samples,
            "zeroTranslationSemanticPolicy": metric(
                zero_count, zero_count - zero_semantic_matches
            ),
            "zeroTranslationDrawConsumedPayloadTriples": metric(
                zero_count, zero_count - zero_draw_hash_matches
            ),
            "invariantAllocationPolicy": metric(
                invariant_components, invariant_mismatches
            ),
            "producerTopology": metric(len(extracted_records), topology_mismatches),
            "primaryEdgeResponseAgainstNormal": metric(
                edge_components, edge_mismatches
            ),
            "changedPrimaryEdgeRecordCount": len(edge_change_records),
            "changedPrimaryEdgeRecordsByInterventionGroup": {
                name: changed_record_groups[name]
                for name in sorted(changed_record_groups)
            },
            "primaryEdgeDeltaCounts": [
                {
                    "edge": edge,
                    "difference": difference,
                    "count": count,
                }
                for (edge, difference), count in sorted(edge_delta_counts.items())
            ],
            "sourceFilterHashStableWithinEachState": True,
            "sourceLayerHashStableWithinEachState": True,
            "reportedRequestedLayerFieldsOnly": True,
            "independentLiveLayerReadbackAvailable": (
                independent_live_readback_available
            ),
            "rawStageDumpsAbsent": True,
        },
        "extractionFailures": extraction_failures,
        "invariantPolicyResiduals": invariant_residuals,
        "primaryEdgeChangeRecords": edge_change_records,
        "records": extracted_records,
        "gate": {
            "frozenWorkflowPassed": False,
            "correctedPostOpeningFixedStateGatePassed": fixed_gate_passed,
            "failureReasons": [
                "the frozen validator rejected a two-component one-ULP q "
                "residual in unrelated normal sample 14",
                "one intervention render contains no producer copy-base pass",
                "the capture has no independent live-layer readback at the "
                "render boundary",
            ],
            "allowTolerance": False,
            "maximumMismatchedComponents": 0,
        },
        "conclusion": {
            "targetSubtreeCoordinatesCausallyAffectPrimaryMeshIntegerization": (
                bool(edge_change_records)
                and invariant_mismatches == 0
                and topology_mismatches == 0
            ),
            "exactThresholdRecovered": False,
            "independentProducerMeshPolicyRecovered": False,
            "requiresLiveReadbackIntervention": True,
            "requiresUnseenHoldout": True,
            "acceptedCalibration": False,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = analyze(
        arguments.timeline,
        preregistration_path=arguments.preregistration,
        run_id=arguments.run_id,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
        print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
