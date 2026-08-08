#!/usr/bin/env python3
"""Validate the frozen Tghn capture after the sample-2 transport correction."""

import argparse
from collections.abc import Mapping
import json
from pathlib import Path
from typing import Any

import validate_small_clear_background_intervention as base


type JsonObject = dict[str, Any]


def validate_missing_branch_replay(
    record: Mapping[str, Any], sample: int
) -> None:
    render = base.mapping(record.get("render"), f"sample {sample} render")
    replay = base.mapping(
        render.get("exactPassReplay"), f"sample {sample} exact replay"
    )
    base.require(replay.get("executed") is False, "missing-branch replay executed")
    base.require(
        replay.get("reason") == "captured small-clear Tghn render pass unavailable",
        "missing-branch replay reason differs",
    )
    base.require(
        isinstance(replay.get("capturedPassCount"), int)
        and replay["capturedPassCount"] >= 0,
        "missing-branch pass count differs",
    )
    base.require(
        replay.get("smallClearBackgroundIntervention") is None,
        "missing branch unexpectedly contains an intervention trace",
    )


def validate_amendment_sources(amendment: Mapping[str, Any]) -> None:
    sources = base.mapping(amendment.get("sourceSHA256"), "amendment sources")
    for relative, expected in sources.items():
        base.require(
            isinstance(relative, str) and isinstance(expected, str),
            "amendment source hash entry is malformed",
        )
        path = base.REPOSITORY / relative
        base.require(path.is_file(), f"amendment source is absent: {relative}")
        base.require(
            base.sha256_file(path) == expected,
            f"amendment source differs: {relative}",
        )


def validate(
    capture_directory: Path,
    preregistration_path: Path,
    amendment_path: Path,
    preflight_path: Path,
) -> JsonObject:
    preregistration = base.load_json(preregistration_path, "preregistration")
    base.require(
        preregistration.get("smallClearBackgroundPreregistrationSchemaVersion")
        == 1,
        "preregistration schema differs",
    )
    base.validate_sources(preregistration)
    amendment = base.load_json(amendment_path, "transport correction")
    base.require(
        amendment.get("smallClearBackgroundTransportCorrectionSchemaVersion") == 1,
        "transport correction schema differs",
    )
    base.require(
        amendment.get("basePreregistrationSHA256")
        == base.sha256_file(preregistration_path),
        "base preregistration SHA-256 differs",
    )
    base.require(
        amendment.get("baseValidatorSHA256")
        == base.sha256_file(
            base.REPOSITORY
            / "Analysis/validate_small_clear_background_intervention.py"
        ),
        "base validator SHA-256 differs",
    )
    validate_amendment_sources(amendment)

    preflight = base.load_json(preflight_path, "Retina preflight")
    base.require(preflight.get("passed") is True, "Retina preflight failed")
    base.require(preflight.get("backingScaleFactor") == 2, "Retina scale differs")
    base.require(
        preflight.get("physicalPixels") == [3456, 2234], "Retina pixels differ"
    )
    base.require(
        base.sha256_file(preflight_path) == amendment.get("capturePreflightSHA256"),
        "capture preflight SHA-256 differs",
    )

    timeline_path = capture_directory / "transition-timeline.json"
    base.require(timeline_path.is_file(), "transition timeline is absent")
    base.require(
        base.sha256_file(timeline_path) == amendment.get("captureTimelineSHA256"),
        "capture timeline SHA-256 differs",
    )
    timeline = base.load_json(timeline_path, "transition timeline")
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
        base.require(timeline.get(field) == value, f"timeline {field} differs")
    geometry = base.mapping(timeline.get("geometry"), "timeline geometry")
    base.require(
        geometry.get("name") == "circle-combined-holdout-01"
        and geometry.get("shape") == "circle"
        and geometry.get("width") == 53
        and geometry.get("height") == 53
        and geometry.get("centerX") == 11.25
        and geometry.get("centerY") == 211.75,
        "timeline geometry differs",
    )
    uniforms = base.mapping(
        timeline.get("dynamicBackgroundUniforms"), "dynamic uniforms"
    )
    expected_uniforms = {
        "schemaVersion": 9,
        "requested": True,
        "executed": True,
        "evidenceMode": "controlled-replay-v1",
        "sampleIndices": list(base.EXPECTED_RECORD_SAMPLES),
        "sampleCount": len(base.EXPECTED_RECORD_SAMPLES),
        "executedSampleCount": len(base.EXPECTED_RECORD_SAMPLES),
        "presentationLayerReplayed": True,
        "presentationLayerAssignedToCARenderer": False,
        "freshStaticCarrier": True,
        "detachedLayerTreeCopies": False,
    }
    for field, value in expected_uniforms.items():
        base.require(uniforms.get(field) == value, f"dynamic {field} differs")
    raw_records = base.sequence(uniforms.get("records"), "dynamic records")
    records = {
        value.get("sampleIndex"): base.mapping(value, "dynamic record")
        for value in raw_records
        if isinstance(value, dict)
    }
    base.require(
        set(records) == set(base.EXPECTED_RECORD_SAMPLES), "sample set differs"
    )

    inputs: dict[int, JsonObject] = {}
    decisions: dict[int, JsonObject] = {}
    missing_branch: list[int] = []
    eligible: list[int] = []
    for sample in base.CANDIDATE_SAMPLES:
        branch = base.branch_inputs(records[sample])
        if branch is None:
            validate_missing_branch_replay(records[sample], sample)
            missing_branch.append(sample)
            continue
        base.exact_replay(records[sample])
        inputs[sample] = branch
        decisions[sample] = base.decision_from_inputs(branch)
        if decisions[sample]["differing"]:
            eligible.append(sample)
    base.require(
        missing_branch == amendment.get("ineligibleNoTghnSamples"),
        "no-Tghn sample set differs",
    )
    base.require(eligible, "no exact-halfway differing Tghn state exists")
    selected = eligible[0]
    selected_capture = f"transition-background-uniform-{selected:02d}"
    for sample in base.CANDIDATE_SAMPLES:
        if sample in missing_branch:
            continue
        trace = base.trace_for(records[sample])
        is_eligible = bool(decisions[sample]["differing"])
        base.require(
            trace.get("eligible") is is_eligible,
            f"sample {sample}: eligibility differs",
        )
        if sample == selected:
            base.require(
                trace.get("selected") is True,
                "first eligible state was not selected",
            )
            base.require(
                trace.get("executed") is True,
                "selected intervention did not execute",
            )
        elif is_eligible:
            base.require(sample > selected, "an earlier eligible state was skipped")
            base.require(
                trace.get("selected") is False,
                "later eligible state was selected",
            )
            base.require(
                trace.get("executed") is False,
                "later eligible state executed",
            )
            base.require(
                trace.get("selectedCapture") == selected_capture,
                "selected capture identity differs",
            )
            base.require(
                trace.get("reason") == "earlier eligible Tghn state selected",
                "later eligible reason differs",
            )
        else:
            base.require(
                trace.get("selected") is False,
                "ineligible state was selected",
            )
            base.require(
                trace.get("executed") is False,
                "ineligible state executed",
            )
            base.require(
                trace.get("reason")
                == "no differing exact-halfway decision in state",
                "ineligible reason differs",
            )
    endpoint = base.exact_replay(records[32])
    base.require(
        endpoint.get("smallClearBackgroundIntervention") is None,
        "endpoint unexpectedly executed the intervention",
    )
    intervention = base.validate_selected(
        capture_directory,
        records[selected],
        inputs[selected],
        decisions[selected],
    )
    base.require(
        intervention["referenceSHA256"]
        == amendment.get("selectedReferenceSHA256"),
        "selected reference SHA-256 differs",
    )
    return {
        "smallClearBackgroundValidationSchemaVersion": 2,
        "passed": True,
        "authority": (
            "current-build Tghn observational pixel irrelevance of the "
            "ordinary-ties-to-even midpoint alternative and bytes 40 through 47"
        ),
        "formalLiquidGlassParity": False,
        "captureDirectory": capture_directory.name,
        "timelineSHA256": base.sha256_file(timeline_path),
        "preregistrationSHA256": base.sha256_file(preregistration_path),
        "transportCorrectionSHA256": base.sha256_file(amendment_path),
        "candidateSampleIndices": list(base.CANDIDATE_SAMPLES),
        "ineligibleNoTghnSampleIndices": missing_branch,
        "eligibleSampleIndices": eligible,
        "selectedSampleIndex": selected,
        "intervention": intervention,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture_directory", type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--transport-correction", required=True, type=Path)
    parser.add_argument("--preflight", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(
        arguments.capture_directory,
        arguments.preregistration,
        arguments.transport_correction,
        arguments.preflight,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
