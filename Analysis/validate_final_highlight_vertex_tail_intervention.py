#!/usr/bin/env python3
"""Validate the frozen current-build Irsd vertex-tail intervention."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Never


REPOSITORY = Path(__file__).resolve().parents[1]
CANDIDATE_SAMPLES = tuple(range(24, 32))
EXPECTED_PIPELINE = "com.apple.coreanimation.PBGRAXm_TkfhBvcmA2Xhfc_Irsd"
EXPECTED_PATTERNS = {
    "zero-half4": "0000000000000000",
    "finite-asymmetric-half4": "003c003800bc0040",
}
EXPECTED_RENDER_BYTES = 1024 * 1024 * 4


def fail(message: str) -> Never:
    raise ValueError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"{path} is not a JSON object")
    return value


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def validate_sources(preregistration: dict[str, Any]) -> None:
    sources = preregistration.get("sourceSHA256")
    require(isinstance(sources, dict), "source hash map is absent")
    for relative, expected in sources.items():
        require(
            isinstance(relative, str) and isinstance(expected, str),
            "source hash entry is malformed",
        )
        path = REPOSITORY / relative
        require(path.is_file(), f"pinned source is absent: {relative}")
        require(
            sha256_file(path) == expected,
            f"pinned source differs: {relative}",
        )


def raw_payload(
    capture_directory: Path,
    snapshot: dict[str, Any],
    label: str,
) -> bytes:
    require(snapshot.get("width") == 1024, f"{label} width differs")
    require(snapshot.get("height") == 1024, f"{label} height differs")
    require(snapshot.get("pixelFormat") == 80, f"{label} format differs")
    require(
        snapshot.get("rawBytes") == EXPECTED_RENDER_BYTES,
        f"{label} raw byte count differs",
    )
    relative = snapshot.get("rawFile")
    require(isinstance(relative, str), f"{label} raw file is absent")
    path = capture_directory / relative
    require(path.is_file(), f"{label} raw file is absent on disk")
    payload = path.read_bytes()
    require(
        len(payload) == EXPECTED_RENDER_BYTES,
        f"{label} disk byte count differs",
    )
    return payload


def validate_intervention(
    capture_directory: Path,
    record: dict[str, Any],
) -> dict[str, Any]:
    sample = record.get("sampleIndex")
    require(sample in CANDIDATE_SAMPLES, "unexpected candidate sample")
    render = record.get("render")
    require(isinstance(render, dict), f"sample {sample}: render is absent")
    exact = render.get("exactPassReplay")
    require(
        isinstance(exact, dict) and exact.get("executed") is True,
        f"sample {sample}: exact replay did not execute",
    )
    reference_snapshot = exact.get("replayOutput")
    require(
        isinstance(reference_snapshot, dict),
        f"sample {sample}: exact replay output is absent",
    )
    reference = raw_payload(
        capture_directory,
        reference_snapshot,
        f"sample {sample} reference",
    )

    trace = exact.get("finalHighlightVertexTailIntervention")
    require(
        isinstance(trace, dict) and trace.get("executed") is True,
        f"sample {sample}: tail intervention did not execute",
    )
    expected_scalars = {
        "schemaVersion": 1,
        "eligible": True,
        "selected": True,
        "selectionPolicy": ("first topology-eligible candidate in sample order"),
        "classification": ("captured Apple Irsd pixel-influence intervention"),
        "liveAppleFrameMutated": False,
        "capturedApplePipelinesUnmodified": True,
        "pipelineLabel": EXPECTED_PIPELINE,
        "indexCount": 24,
        "vertexCount": 16,
        "stride": 48,
        "attributeIndex": 3,
        "attributeOffset": 32,
        "attributeFormat": "half4",
        "interventionCount": 2,
        "allInterventionsExact": True,
    }
    for field, expected in expected_scalars.items():
        require(
            trace.get(field) == expected,
            f"sample {sample}: {field} differs",
        )
    original_sha = trace.get("originalAttributeStreamSHA256")
    require(
        isinstance(original_sha, str) and len(original_sha) == 64,
        f"sample {sample}: original attribute digest is malformed",
    )

    interventions = trace.get("interventions")
    require(
        isinstance(interventions, list) and len(interventions) == 2,
        f"sample {sample}: intervention cardinality differs",
    )
    by_name = {
        intervention.get("name"): intervention
        for intervention in interventions
        if isinstance(intervention, dict)
    }
    require(
        set(by_name) == set(EXPECTED_PATTERNS),
        f"sample {sample}: intervention names differ",
    )
    candidate_digests: dict[str, str] = {}
    for name, pattern_hex in EXPECTED_PATTERNS.items():
        intervention = by_name[name]
        require(
            intervention.get("half4LittleEndianHex") == pattern_hex,
            f"sample {sample} {name}: half4 pattern differs",
        )
        expected_stream = bytes.fromhex(pattern_hex) * 16
        expected_stream_sha = sha256_bytes(expected_stream)
        require(
            intervention.get("mutatedAttributeStreamSHA256") == expected_stream_sha,
            f"sample {sample} {name}: mutated stream differs",
        )
        require(
            expected_stream_sha != original_sha,
            f"sample {sample} {name}: intervention did not change input",
        )
        replay = intervention.get("replay")
        require(
            isinstance(replay, dict) and replay.get("executed") is True,
            f"sample {sample} {name}: replay did not execute",
        )
        snapshot = replay.get("output")
        require(
            isinstance(snapshot, dict),
            f"sample {sample} {name}: replay output is absent",
        )
        candidate = raw_payload(
            capture_directory,
            snapshot,
            f"sample {sample} {name}",
        )
        require(
            candidate == reference,
            f"sample {sample} {name}: replay bytes differ",
        )
        comparison = intervention.get("comparison")
        require(
            isinstance(comparison, dict),
            f"sample {sample} {name}: comparison is absent",
        )
        expected_comparison = {
            "compared": True,
            "exactByteMatch": True,
            "byteCount": EXPECTED_RENDER_BYTES,
            "mismatchedByteCount": 0,
            "mismatchedPixelCount": 0,
            "maximumChannelDelta": 0,
            "firstMismatchedByte": -1,
        }
        for field, expected in expected_comparison.items():
            require(
                comparison.get(field) == expected,
                f"sample {sample} {name}: {field} differs",
            )
        candidate_digests[name] = sha256_bytes(candidate)

    require(
        len(set(candidate_digests.values())) == 1,
        f"sample {sample}: candidate output digests differ",
    )
    return {
        "sampleIndex": sample,
        "originalAttributeStreamSHA256": original_sha,
        "referenceOutputSHA256": sha256_bytes(reference),
        "interventionOutputSHA256": candidate_digests,
        "comparedBytesPerIntervention": EXPECTED_RENDER_BYTES,
    }


def candidate_trace(record: dict[str, Any]) -> dict[str, Any]:
    sample = record.get("sampleIndex")
    require(sample in CANDIDATE_SAMPLES, "unexpected candidate sample")
    render = record.get("render")
    require(isinstance(render, dict), f"sample {sample}: render is absent")
    exact = render.get("exactPassReplay")
    require(
        isinstance(exact, dict) and exact.get("executed") is True,
        f"sample {sample}: exact replay did not execute",
    )
    trace = exact.get("finalHighlightVertexTailIntervention")
    require(
        isinstance(trace, dict) and trace.get("schemaVersion") == 1,
        f"sample {sample}: tail candidate trace is absent",
    )
    return trace


def validate_selection(records: dict[int, dict[str, Any]]) -> int:
    traces = {sample: candidate_trace(records[sample]) for sample in CANDIDATE_SAMPLES}
    eligible_samples = [
        sample for sample, trace in traces.items() if trace.get("eligible") is True
    ]
    require(eligible_samples, "no topology-eligible Irsd candidate exists")
    selected_sample = eligible_samples[0]
    selected_capture = f"transition-background-uniform-{selected_sample:02d}"
    selected_samples = [
        sample for sample, trace in traces.items() if trace.get("selected") is True
    ]
    executed_samples = [
        sample for sample, trace in traces.items() if trace.get("executed") is True
    ]
    require(
        selected_samples == [selected_sample],
        "selected sample is not the first eligible candidate",
    )
    require(
        executed_samples == [selected_sample],
        "executed sample is not the first eligible candidate",
    )

    for sample, trace in traces.items():
        if sample == selected_sample:
            continue
        require(
            trace.get("selected") is False and trace.get("executed") is False,
            f"sample {sample}: unselected candidate state differs",
        )
        if trace.get("eligible") is False:
            require(
                trace.get("reason") == "current Irsd border draw is unavailable",
                f"sample {sample}: ineligible reason differs",
            )
            continue
        require(
            sample > selected_sample,
            f"sample {sample}: an earlier eligible candidate was skipped",
        )
        expected = {
            "selectionPolicy": ("first topology-eligible candidate in sample order"),
            "selectedCapture": selected_capture,
            "pipelineLabel": EXPECTED_PIPELINE,
            "indexCount": 24,
            "reason": ("earlier topology-eligible Irsd candidate selected"),
        }
        for field, value in expected.items():
            require(
                trace.get(field) == value,
                f"sample {sample}: {field} differs",
            )
    return selected_sample


def validate(
    capture_directory: Path,
    preregistration_path: Path,
    preflight_path: Path,
) -> dict[str, Any]:
    preregistration = load_json(preregistration_path)
    require(
        preregistration.get(
            "finalHighlightVertexTailInterventionPreregistrationSchemaVersion"
        )
        == 2,
        "preregistration schema differs",
    )
    validate_sources(preregistration)
    preflight = load_json(preflight_path)
    require(preflight.get("passed") is True, "Retina preflight did not pass")
    require(
        preflight.get("backingScaleFactor") == 2,
        "Retina backing scale differs",
    )

    runtime_path = capture_directory / "transition-timeline.json"
    runtime = load_json(runtime_path)
    expected_runtime = {
        "material": "regular",
        "appearance": "dark",
        "direction": "dematerialize",
        "sampleCount": 33,
        "windowBackingScaleFactor": 2,
        "failedSamples": 0,
        "expectedWindowPixels": [2048, 2048],
    }
    for field, expected in expected_runtime.items():
        require(runtime.get(field) == expected, f"runtime {field} differs")
    geometry = runtime.get("geometry")
    require(
        isinstance(geometry, dict)
        and geometry.get("name") == "circle-480-center"
        and geometry.get("width") == 480
        and geometry.get("height") == 480,
        "runtime geometry differs",
    )
    uniforms = runtime.get("dynamicBackgroundUniforms")
    require(isinstance(uniforms, dict), "dynamic records are absent")
    expected_uniforms = {
        "schemaVersion": 9,
        "requested": True,
        "executed": True,
        "evidenceMode": "controlled-replay-v1",
        "sampleIndices": list(CANDIDATE_SAMPLES),
        "sampleCount": len(CANDIDATE_SAMPLES),
        "executedSampleCount": len(CANDIDATE_SAMPLES),
        "presentationLayerReplayed": True,
        "presentationLayerAssignedToCARenderer": False,
        "freshStaticCarrier": True,
        "detachedLayerTreeCopies": False,
    }
    for field, expected in expected_uniforms.items():
        require(
            uniforms.get(field) == expected,
            f"dynamic uniforms {field} differs",
        )
    records = uniforms.get("records")
    require(
        isinstance(records, list)
        and len(records) == len(CANDIDATE_SAMPLES)
        and all(isinstance(record, dict) for record in records),
        "dynamic record list differs",
    )
    target_records = {record.get("sampleIndex"): record for record in records}
    require(
        set(target_records) == set(CANDIDATE_SAMPLES),
        "candidate sample set differs",
    )
    selected_sample = validate_selection(target_records)
    result = validate_intervention(
        capture_directory,
        target_records[selected_sample],
    )
    return {
        "schemaVersion": 2,
        "passed": True,
        "authority": (
            "current-build observational irrelevance of generated vertex "
            "bytes 32 through 39 for the Irsd border draw"
        ),
        "formalLiquidGlassParity": False,
        "captureDirectory": capture_directory.name,
        "runtimeSHA256": sha256_file(runtime_path),
        "preregistrationSHA256": sha256_file(preregistration_path),
        "candidateSampleIndices": list(CANDIDATE_SAMPLES),
        "candidateSampleCount": len(CANDIDATE_SAMPLES),
        "selectedSampleIndex": selected_sample,
        "sampleCount": 1,
        "interventionCount": len(EXPECTED_PATTERNS),
        "comparedBytes": len(EXPECTED_PATTERNS) * EXPECTED_RENDER_BYTES,
        "unequalBytes": 0,
        "samples": [result],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
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
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
