#!/usr/bin/env python3
"""Validate the finite-source-positive-control Tmua/Tghn replay."""

import argparse
from collections.abc import Mapping
import json
from pathlib import Path
import struct
from typing import Any

import validate_small_clear_background_intervention as background_subject
import validate_small_clear_tmua_nonvacuous_v2 as v2


type JsonObject = dict[str, Any]

SAMPLES = v2.SAMPLES
TARGET_BYTES = v2.TARGET_BYTES


def finite_source_payload(width: int, height: int) -> bytes:
    result = bytearray(width * height * 8)
    for y in range(height):
        for x in range(width):
            offset = (y * width + x) * 8
            words = (
                0x3400 if x % 2 == 0 else 0x3C00,
                0x3C00 if y % 2 == 0 else 0x3800,
                0x3000 if (x ^ y) % 2 == 0 else 0x3A00,
                0x3C00,
            )
            struct.pack_into("<4H", result, offset, *words)
    return bytes(result)


def validate_finite_source(
    directory: Path,
    snapshot: Mapping[str, Any],
    label: str,
    dimensions: tuple[int, int],
) -> str:
    payload = v2.raw_payload(
        directory,
        snapshot,
        label,
        expected_format=115,
        expected_dimensions=dimensions,
    )
    v2.require(
        payload == finite_source_payload(*dimensions),
        f"{label} finite pattern differs",
    )
    return v2.sha256_bytes(payload)


def validate_tmua_trace(
    directory: Path,
    trace: Mapping[str, Any],
    sample: int,
) -> JsonObject:
    label = f"sample {sample}"
    v2.require(trace.get("schemaVersion") == 3, f"{label} schema differs")
    v2.require(trace.get("executed") is True, f"{label} intervention failed")
    v2.require(trace.get("eligible") is True, f"{label} intervention ineligible")
    v2.require(
        trace.get("classification")
        == (
            "finite-source-positive-control Tmua/Tghn influence "
            "and explicit-Irsd-source replay"
        ),
        f"{label} classification differs",
    )
    v2.require(
        trace.get("liveAppleFrameMutated") is False, f"{label} live frame mutated"
    )
    v2.require(
        trace.get("capturedApplePipelinesUnmodified") is True,
        f"{label} Apple pipeline changed",
    )
    v2.require(
        trace.get("tghnPipelineLabel") == v2.TGHN_PIPELINE, f"{label} Tghn differs"
    )
    v2.require(
        trace.get("finalPipelineLabel") == v2.FINAL_PIPELINE, f"{label} Irsd differs"
    )
    positions = tuple(
        trace.get(field)
        for field in (
            "tghnPipelineCommandIndex",
            "tghnDrawIndex",
            "finalPipelineCommandIndex",
            "finalDrawIndex",
        )
    )
    v2.require(
        all(type(value) is int for value in positions), f"{label} positions differ"
    )
    v2.require(
        positions[0] < positions[1] < positions[2] < positions[3],
        f"{label} command order differs",
    )

    source_snapshot = v2.mapping(trace.get("sourceTexture"), f"{label} source")
    source_width = source_snapshot.get("width")
    v2.require(source_width in (64, 128), f"{label} source width differs")
    source_dimensions = (source_width, 128)
    source = v2.raw_payload(
        directory,
        source_snapshot,
        f"{label} source",
        expected_format=115,
        expected_dimensions=source_dimensions,
    )
    zero = v2.raw_payload(
        directory,
        v2.mapping(trace.get("zeroTexture"), f"{label} zero"),
        f"{label} zero",
        expected_format=115,
        expected_dimensions=source_dimensions,
    )
    v2.require(not any(zero), f"{label} zero replacement is nonzero")
    source_hash = v2.sha256_bytes(source)
    if any(source):
        v2.require(source_hash == v2.TMUA_NONZERO_SHA256, f"{label} source differs")
        source_kind = "nonzero"
    else:
        v2.require(
            source_hash == v2.TMUA_ZERO_SHA256[len(source)],
            f"{label} zero source hash differs",
        )
        source_kind = "zero"
    finite_hash = validate_finite_source(
        directory,
        v2.mapping(trace.get("finiteControlSource"), f"{label} finite source"),
        f"{label} finite source",
        source_dimensions,
    )

    final_source = v2.raw_payload(
        directory,
        v2.mapping(trace.get("explicitFinalSource"), f"{label} final source"),
        f"{label} final source",
        expected_format=80,
        expected_dimensions=(1, 1),
    )
    v2.require(
        trace.get("finalSourceDistinctFromTmua") is True,
        f"{label} final source identity differs",
    )
    controlled_hashes = {
        "destinationSeed": v2.validate_controlled_pattern(
            directory,
            v2.mapping(trace.get("destinationSeed"), f"{label} destination"),
            f"{label} destination",
            (1024, 1024),
            0x13579BDF,
        ),
        "controlledTghnBackdrop": v2.validate_controlled_pattern(
            directory,
            v2.mapping(trace.get("controlledTghnBackdrop"), f"{label} backdrop"),
            f"{label} backdrop",
            (64, 64),
            0x2468ACE0,
        ),
        "controlledFinalInput": v2.validate_controlled_pattern(
            directory,
            v2.mapping(trace.get("controlledFinalInput"), f"{label} final input"),
            f"{label} final input",
            (576, 448),
            0x0F1E2D3C,
        ),
    }

    tghn = v2.mapping(trace.get("Tghn"), f"{label} Tghn")
    before = v2.replay_payload(
        directory,
        v2.mapping(tghn.get("before"), f"{label} Tghn before"),
        f"{label} Tghn before",
    )
    reference = v2.replay_payload(
        directory,
        v2.mapping(tghn.get("reference"), f"{label} Tghn reference"),
        f"{label} Tghn reference",
    )
    zero_output = v2.replay_payload(
        directory,
        v2.mapping(tghn.get("zeroSource"), f"{label} Tghn zero"),
        f"{label} Tghn zero",
    )
    finite_output = v2.replay_payload(
        directory,
        v2.mapping(tghn.get("finiteControlSource"), f"{label} Tghn finite"),
        f"{label} Tghn finite",
    )
    captured_activity = v2.comparison_metrics(before, reference)
    source_comparison = v2.comparison_metrics(reference, zero_output)
    path_sensitivity = v2.comparison_metrics(zero_output, finite_output)
    v2.require(
        source_comparison["mismatchedByteCount"] == 0,
        f"{label} captured Tmua differs from zero",
    )
    v2.validate_reported_comparison(
        v2.mapping(tghn.get("activityComparison"), f"{label} captured activity"),
        captured_activity,
        f"{label} captured activity",
    )
    v2.validate_reported_comparison(
        v2.mapping(tghn.get("sourceComparison"), f"{label} source comparison"),
        source_comparison,
        f"{label} source comparison",
    )
    v2.validate_reported_comparison(
        v2.mapping(tghn.get("pathSensitivityComparison"), f"{label} path control"),
        path_sensitivity,
        f"{label} path control",
    )
    v2.require(
        trace.get("tghnPositiveControlPassed")
        is (path_sensitivity["mismatchedByteCount"] > 0),
        f"{label} Tghn control flag differs",
    )
    v2.require(
        trace.get("sourceComparisonsExact") is True,
        f"{label} source flag differs",
    )

    irsd = v2.mapping(trace.get("Irsd"), f"{label} Irsd")
    irsd_before = v2.replay_payload(
        directory,
        v2.mapping(irsd.get("before"), f"{label} Irsd before"),
        f"{label} Irsd before",
    )
    irsd_reference = v2.replay_payload(
        directory,
        v2.mapping(irsd.get("reference"), f"{label} Irsd reference"),
        f"{label} Irsd reference",
    )
    irsd_activity = v2.comparison_metrics(irsd_before, irsd_reference)
    v2.validate_reported_comparison(
        v2.mapping(irsd.get("activityComparison"), f"{label} Irsd activity"),
        irsd_activity,
        f"{label} Irsd activity",
    )
    v2.require(
        trace.get("IrsdActivityObserved") is (irsd_activity["mismatchedByteCount"] > 0),
        f"{label} Irsd activity flag differs",
    )
    return {
        "sampleIndex": sample,
        "TmuaSourceKind": source_kind,
        "TmuaSourceSHA256": source_hash,
        "finiteControlSourceSHA256": finite_hash,
        "explicitFinalSourceSHA256": v2.sha256_bytes(final_source),
        "controlledTextureSHA256": controlled_hashes,
        "capturedSourceActivityMismatchedByteCount": captured_activity[
            "mismatchedByteCount"
        ],
        "finiteSourceControlMismatchedByteCount": path_sensitivity[
            "mismatchedByteCount"
        ],
        "finiteSourceControlMismatchedPixelCount": path_sensitivity[
            "mismatchedPixelCount"
        ],
        "TghnReferenceSHA256": v2.sha256_bytes(reference),
        "TghnZeroSourceSHA256": v2.sha256_bytes(zero_output),
        "TmuaSourceUnequalByteCount": 0,
        "IrsdActivityMismatchedByteCount": irsd_activity["mismatchedByteCount"],
        "IrsdActivityMismatchedPixelCount": irsd_activity["mismatchedPixelCount"],
    }


def validate_background_trace(
    directory: Path,
    trace: Mapping[str, Any],
    inputs: Mapping[str, Any],
    decision: Mapping[str, Any],
    sample: int,
) -> JsonObject:
    result = v2.validate_background_trace(directory, trace, inputs, decision, sample)
    source_snapshot = v2.mapping(
        trace.get("controlledTghnSource"),
        f"sample {sample} Tghn residual source",
    )
    width = source_snapshot.get("width")
    v2.require(width in (64, 128), "Tghn residual source width differs")
    result["controlledSourceSHA256"] = validate_finite_source(
        directory,
        source_snapshot,
        f"sample {sample} Tghn residual source",
        (width, 128),
    )
    return result


def validate(
    capture_directory: Path,
    preregistration_path: Path,
    preflight_path: Path,
) -> JsonObject:
    preregistration = v2.load_json(preregistration_path, "preregistration")
    v2.require(
        preregistration.get("smallClearTmuaNonvacuousV3PreregistrationSchemaVersion")
        == 1,
        "preregistration schema differs",
    )
    v2.validate_sources(preregistration)
    preflight = v2.load_json(preflight_path, "Retina preflight")
    v2.require(preflight.get("passed") is True, "Retina preflight failed")
    v2.require(preflight.get("backingScaleFactor") == 2, "Retina scale differs")
    v2.require(preflight.get("physicalPixels") == [3456, 2234], "Retina pixels differ")

    timeline_path = capture_directory / "transition-timeline.json"
    timeline = v2.load_json(timeline_path, "timeline")
    expected_timeline = {
        "material": "clear",
        "appearance": "light",
        "direction": "materialize",
        "sampleCount": 33,
        "windowBackingScaleFactor": 2,
        "expectedWindowPixels": [2048, 2048],
        "failedSamples": 0,
    }
    for field, value in expected_timeline.items():
        v2.require(timeline.get(field) == value, f"timeline {field} differs")
    geometry = v2.mapping(timeline.get("geometry"), "geometry")
    v2.require(
        geometry.get("name") == "circle-combined-holdout-01"
        and geometry.get("shape") == "circle"
        and geometry.get("width") == 53
        and geometry.get("height") == 53
        and geometry.get("centerX") == 11.25
        and geometry.get("centerY") == 211.75,
        "timeline geometry differs",
    )
    uniforms = v2.mapping(timeline.get("dynamicBackgroundUniforms"), "uniforms")
    v2.require(uniforms.get("requested") is True, "uniform capture not requested")
    v2.require(uniforms.get("executed") is True, "uniform capture failed")
    records: dict[int, Mapping[str, Any]] = {}
    for value in v2.sequence(uniforms.get("records"), "uniform records"):
        record = v2.mapping(value, "uniform record")
        sample = record.get("sampleIndex")
        v2.require(type(sample) is int, "sample index differs")
        records[sample] = record
    v2.require(set(SAMPLES).issubset(records), "candidate sample set differs")

    branch_data: dict[int, tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
    absent_samples: list[int] = []
    for sample in SAMPLES:
        record = records[sample]
        inputs = background_subject.branch_inputs(record)
        render = v2.mapping(record.get("render"), f"sample {sample} render")
        replay = v2.mapping(render.get("exactPassReplay"), f"sample {sample} replay")
        if inputs is None:
            v2.require(
                replay.get("executed") is False, f"sample {sample} replay executed"
            )
            v2.require(
                replay.get("reason") == v2.ABSENT_REASON,
                f"sample {sample} reason differs",
            )
            absent_samples.append(sample)
            continue
        v2.require(replay.get("executed") is True, f"sample {sample} replay failed")
        branch_data[sample] = (
            inputs,
            background_subject.decision_from_inputs(inputs),
        )
    v2.require(len(branch_data) >= 20, "too few Tghn-bearing states")
    selected_candidates = [
        sample for sample, (_, decision) in branch_data.items() if decision["differing"]
    ]
    v2.require(selected_candidates, "no Tghn residual candidate exists")
    selected_sample = selected_candidates[0]

    tmua_states: list[JsonObject] = []
    selected_background: JsonObject | None = None
    for sample, (inputs, decision) in branch_data.items():
        record = records[sample]
        render = v2.mapping(record.get("render"), f"sample {sample} render")
        replay = v2.mapping(render.get("exactPassReplay"), f"sample {sample} replay")
        tmua_states.append(
            validate_tmua_trace(
                capture_directory,
                v2.mapping(
                    replay.get("smallClearTmuaNonvacuousIntervention"),
                    f"sample {sample} Tmua intervention",
                ),
                sample,
            )
        )
        background_trace = v2.mapping(
            replay.get("smallClearBackgroundNonvacuousIntervention"),
            f"sample {sample} Tghn residual",
        )
        v2.validate_background_selection_trace(
            background_trace,
            sample=sample,
            should_select=sample == selected_sample,
            has_differing_axis=bool(decision["differing"]),
        )
        if sample == selected_sample:
            selected_background = validate_background_trace(
                capture_directory,
                background_trace,
                inputs,
                decision,
                sample,
            )
    v2.require(selected_background is not None, "selected Tghn residual is absent")
    nonzero_count = sum(state["TmuaSourceKind"] == "nonzero" for state in tmua_states)
    zero_count = len(tmua_states) - nonzero_count
    v2.require(nonzero_count > 0, "no nonzero Tmua source state was tested")
    v2.require(zero_count > 0, "no zero Tmua source state was tested")
    finite_control_count = sum(
        state["finiteSourceControlMismatchedByteCount"] > 0 for state in tmua_states
    )
    v2.require(finite_control_count > 0, "finite Tmua control never affected Tghn")
    v2.require(
        any(
            state["TmuaSourceKind"] == "nonzero"
            and state["finiteSourceControlMismatchedByteCount"] > 0
            for state in tmua_states
        ),
        "finite Tmua control did not affect a nonzero-source state",
    )

    return {
        "smallClearTmuaNonvacuousV3ResultSchemaVersion": 1,
        "status": "exact-finite-control-small-clear-Tmua-and-Tghn-residual-closure",
        "classification": (
            "prospective finite-source path-sensitivity control plus unchanged "
            "captured-versus-zero replication"
        ),
        "captureDirectory": capture_directory.name,
        "timelineSHA256": v2.sha256_file(timeline_path),
        "candidateSampleCount": len(SAMPLES),
        "branchBearingStateCount": len(tmua_states),
        "absentBranchSamples": absent_samples,
        "nonzeroTmuaSourceStateCount": nonzero_count,
        "zeroTmuaSourceStateCount": zero_count,
        "finiteSourcePositiveControlCount": finite_control_count,
        "TmuaSourceComparisonCount": len(tmua_states),
        "TmuaSourceComparedByteCount": len(tmua_states) * TARGET_BYTES,
        "TmuaSourceUnequalByteCount": 0,
        "currentIrsdBindsTmuaSource": False,
        "TmuaProducerOutputRequiredForWalle": False,
        "TmuaStates": tmua_states,
        "TghnResidual": selected_background,
        "TghnResidualUnequalByteCount": 0,
        "remainingAppleConstructionQuestions": [
            "bit-exact transfer of recovered compositor arithmetic to the current small-clear Iscd/Irsd pair"
        ],
        "appleUnknownsBlockingGatedWalleIntegration": 0,
        "remainingProductProofs": [
            "Walle-shaped physical Retina color/compositor transfer",
            "fresh production-Walle frame with zero unequal bytes",
        ],
        "productionParityAuthorized": False,
        "productionShaderChanged": False,
        "productionFlakeChanged": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_directory", type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--preflight", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(
        arguments.capture_directory,
        arguments.preregistration,
        arguments.preflight,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
