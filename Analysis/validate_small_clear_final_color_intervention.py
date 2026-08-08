#!/usr/bin/env python3
"""Validate the frozen small-clear final half4 pixel-influence intervention."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
from typing import Any, Never


type JsonObject = dict[str, Any]

REPOSITORY = Path(__file__).resolve().parents[1]
CANDIDATE_SAMPLES = tuple(range(2, 32))
EXPECTED_RECORD_SAMPLES = tuple(range(2, 33))
EXPECTED_PIPELINE = "com.apple.coreanimation.PBGRAXm_TkfhA2Xhfc_Iscd"
FINITE_CYCLE = (
    "003c003800bc0040",
    "00b80040003400bc",
    "004200c0003a0030",
    "00bc003400400038",
)
EXPECTED_INTERVENTIONS = (
    "finite-constant-half4",
    "finite-varying-half4",
)
EXPECTED_RENDER_WIDTH = 128
EXPECTED_RENDER_HEIGHT = 128
EXPECTED_RENDER_BYTES = EXPECTED_RENDER_WIDTH * EXPECTED_RENDER_HEIGHT * 4
VERTEX_COUNTS = {6: 4, 24: 16}
VERTEX_STRIDE = 48
ATTRIBUTE_OFFSET = 32
ATTRIBUTE_BYTES = 8


def fail(message: str) -> Never:
    raise ValueError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def load_json(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path} is not a JSON object")
    return value


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def expected_attribute_stream(name: str, vertex_count: int) -> bytes:
    require(name in EXPECTED_INTERVENTIONS, f"unknown intervention: {name}")
    patterns = (
        (FINITE_CYCLE[0],) * vertex_count
        if name == "finite-constant-half4"
        else tuple(
            FINITE_CYCLE[index % len(FINITE_CYCLE)] for index in range(vertex_count)
        )
    )
    return b"".join(bytes.fromhex(pattern) for pattern in patterns)


def validate_sources(preregistration: JsonObject) -> None:
    sources = preregistration.get("sourceSHA256")
    require(isinstance(sources, dict), "source hash map is absent")
    for relative, expected in sources.items():
        require(
            isinstance(relative, str) and isinstance(expected, str),
            "source hash entry is malformed",
        )
        path = REPOSITORY / relative
        require(path.is_file(), f"pinned source is absent: {relative}")
        require(sha256_file(path) == expected, f"pinned source differs: {relative}")


def raw_payload(
    capture_directory: Path,
    snapshot: JsonObject,
    label: str,
) -> bytes:
    require(
        snapshot.get("width") == EXPECTED_RENDER_WIDTH,
        f"{label} width differs",
    )
    require(
        snapshot.get("height") == EXPECTED_RENDER_HEIGHT,
        f"{label} height differs",
    )
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
    require(len(payload) == EXPECTED_RENDER_BYTES, f"{label} disk bytes differ")
    return payload


def exact_replay(record: JsonObject) -> JsonObject:
    sample = record.get("sampleIndex")
    render = record.get("render")
    require(isinstance(render, dict), f"sample {sample}: render is absent")
    replay = render.get("exactPassReplay")
    require(
        isinstance(replay, dict) and replay.get("executed") is True,
        f"sample {sample}: exact replay did not execute",
    )
    return replay


def candidate_trace(record: JsonObject) -> JsonObject:
    sample = record.get("sampleIndex")
    require(sample in CANDIDATE_SAMPLES, "unexpected candidate sample")
    trace = exact_replay(record).get("finalHighlightVertexTailIntervention")
    require(
        isinstance(trace, dict) and trace.get("schemaVersion") == 1,
        f"sample {sample}: color candidate trace is absent",
    )
    return trace


def validate_selection(records: Mapping[int, JsonObject]) -> int:
    traces = {sample: candidate_trace(records[sample]) for sample in CANDIDATE_SAMPLES}
    eligible = [
        sample for sample, trace in traces.items() if trace.get("eligible") is True
    ]
    require(eligible, "no exact-pipeline small-clear candidate exists")
    selected = eligible[0]
    selected_capture = f"transition-background-uniform-{selected:02d}"
    require(
        [sample for sample, trace in traces.items() if trace.get("selected") is True]
        == [selected],
        "selected sample is not the first eligible candidate",
    )
    require(
        [sample for sample, trace in traces.items() if trace.get("executed") is True]
        == [selected],
        "executed sample is not the first eligible candidate",
    )
    for sample, trace in traces.items():
        if sample == selected:
            continue
        require(
            trace.get("selected") is False and trace.get("executed") is False,
            f"sample {sample}: unselected candidate state differs",
        )
        if trace.get("eligible") is False:
            require(
                trace.get("reason") == "small-clear Tkfh draw is unavailable",
                f"sample {sample}: ineligible reason differs",
            )
            continue
        require(sample > selected, f"sample {sample}: earlier candidate was skipped")
        expected = {
            "selectionPolicy": "first exact-pipeline candidate in sample order",
            "selectedCapture": selected_capture,
            "pipelineLabel": EXPECTED_PIPELINE,
            "reason": "earlier exact-pipeline small-clear Tkfh candidate selected",
        }
        for field, value in expected.items():
            require(trace.get(field) == value, f"sample {sample}: {field} differs")
        require(
            trace.get("indexCount") in VERTEX_COUNTS,
            f"sample {sample}: indexCount differs",
        )
    return selected


def pipeline_label(record: JsonObject) -> str:
    pipeline = record.get("pipeline")
    if not isinstance(pipeline, dict):
        return ""
    label = pipeline.get("label")
    return label if isinstance(label, str) else ""


def payload(record: JsonObject, label: str) -> bytes:
    description = record.get("payload")
    require(isinstance(description, dict), f"{label} payload is absent")
    encoded = description.get("hex")
    length = description.get("lengthBytes")
    require(isinstance(encoded, str), f"{label} payload is not hexadecimal")
    try:
        result = bytes.fromhex(encoded)
    except ValueError as error:
        raise ValueError(f"{label} payload is not hexadecimal") from error
    require(length == len(result), f"{label} payload length differs")
    return result


def validate_selected_pipeline(record: JsonObject) -> tuple[str, int, int]:
    sample = record.get("sampleIndex")
    render = record.get("render")
    require(isinstance(render, dict), f"sample {sample}: render is absent")
    probe = render.get("metalUniformProbe")
    snapshots = render.get("metalBufferSnapshots")
    require(isinstance(probe, dict), f"sample {sample}: Metal probe is absent")
    require(isinstance(snapshots, dict), f"sample {sample}: snapshots are absent")
    metal_records = probe.get("records")
    snapshot_records = snapshots.get("snapshots")
    require(isinstance(metal_records, list), "Metal record list differs")
    require(isinstance(snapshot_records, list), "Metal snapshot list differs")
    typed_records = [value for value in metal_records if isinstance(value, dict)]
    branch = [
        value for value in typed_records if pipeline_label(value) == EXPECTED_PIPELINE
    ]
    draws = [
        value
        for value in branch
        if value.get("kind") == "drawIndexedPrimitives"
        and value.get("indexCount") in VERTEX_COUNTS
        and value.get("indexType") == 0
    ]
    bindings = [
        value
        for value in branch
        if value.get("kind") in {"buffer", "bufferOffset"}
        and value.get("stage") == "vertex"
        and value.get("index") == 1
    ]
    require(len(draws) == 1, "selected small-clear indexed draw differs")
    require(len(bindings) == 1, "selected small-clear vertex binding differs")
    pipeline = draws[0].get("pipeline")
    require(isinstance(pipeline, dict), "selected pipeline record is absent")
    descriptor = pipeline.get("creationDescriptor")
    require(isinstance(descriptor, dict), "selected pipeline descriptor is absent")
    require(
        descriptor.get("vertexFunction") == "VfxU10Xh"
        and descriptor.get("fragmentFunction") == "TkfhA2Xhfc_Iscd",
        "selected shader identity differs",
    )
    attributes = descriptor.get("vertexAttributes")
    stage_inputs = descriptor.get("vertexFunctionStageInputAttributes")
    layouts = descriptor.get("vertexLayouts")
    require(isinstance(attributes, list) and len(attributes) == 4, "attributes differ")
    require(
        attributes[3] == {"bufferIndex": 1, "format": 27, "index": 3, "offset": 32},
        "half4 attribute descriptor differs",
    )
    require(isinstance(stage_inputs, list) and len(stage_inputs) == 4, "inputs differ")
    require(
        stage_inputs[3].get("active") is True
        and stage_inputs[3].get("attributeIndex") == 3
        and stage_inputs[3].get("attributeType") == 19
        and stage_inputs[3].get("name") == "color",
        "half4 attribute is not declared active",
    )
    require(
        layouts == [{"index": 1, "stepFunction": 1, "stepRate": 1, "stride": 48}],
        "selected vertex layout differs",
    )
    sequence = bindings[0].get("sequence")
    matches = [
        value
        for value in snapshot_records
        if isinstance(value, dict)
        and value.get("sequence") == sequence
        and value.get("stage") == "vertex"
        and value.get("index") == 1
        and pipeline_label(value) == EXPECTED_PIPELINE
    ]
    require(len(matches) == 1, "selected vertex snapshot differs")
    raw = payload(matches[0], "selected vertex")
    index_count = draws[0]["indexCount"]
    vertex_count = VERTEX_COUNTS[index_count]
    require(
        len(raw) >= vertex_count * VERTEX_STRIDE,
        "vertex snapshot is truncated",
    )
    stream = b"".join(
        raw[
            index * VERTEX_STRIDE + ATTRIBUTE_OFFSET : index * VERTEX_STRIDE
            + ATTRIBUTE_OFFSET
            + ATTRIBUTE_BYTES
        ]
        for index in range(vertex_count)
    )
    return sha256_bytes(stream), index_count, vertex_count


def validate_intervention(
    capture_directory: Path,
    record: JsonObject,
) -> JsonObject:
    sample = record.get("sampleIndex")
    replay = exact_replay(record)
    reference_snapshot = replay.get("replayOutput")
    require(isinstance(reference_snapshot, dict), "exact replay output is absent")
    reference = raw_payload(
        capture_directory,
        reference_snapshot,
        f"sample {sample} reference",
    )
    trace = candidate_trace(record)
    original_sha, index_count, vertex_count = validate_selected_pipeline(record)
    expected_scalars = {
        "schemaVersion": 1,
        "executed": True,
        "eligible": True,
        "selected": True,
        "selectionPolicy": "first exact-pipeline candidate in sample order",
        "classification": (
            "captured Apple small-clear Tkfh active-color pixel-influence intervention"
        ),
        "liveAppleFrameMutated": False,
        "capturedApplePipelinesUnmodified": True,
        "pipelineLabel": EXPECTED_PIPELINE,
        "indexCount": index_count,
        "vertexCount": vertex_count,
        "stride": VERTEX_STRIDE,
        "attributeIndex": 3,
        "attributeOffset": ATTRIBUTE_OFFSET,
        "attributeFormat": "half4",
        "interventionCount": 2,
        "allInterventionsExact": True,
    }
    for field, expected in expected_scalars.items():
        require(trace.get(field) == expected, f"sample {sample}: {field} differs")
    require(
        isinstance(trace.get("originalAttributeStreamSHA256"), str)
        and len(trace["originalAttributeStreamSHA256"]) == 64,
        "original attribute digest is malformed",
    )
    require(
        trace["originalAttributeStreamSHA256"] == original_sha,
        "trace and independently retained attribute stream differ",
    )
    interventions = trace.get("interventions")
    require(
        isinstance(interventions, list) and len(interventions) == 2, "count differs"
    )
    by_name = {
        value.get("name"): value for value in interventions if isinstance(value, dict)
    }
    require(set(by_name) == set(EXPECTED_INTERVENTIONS), "intervention names differ")
    output_sha256: str | None = None
    for name in EXPECTED_INTERVENTIONS:
        intervention = by_name[name]
        require(
            intervention.get("half4LittleEndianHex") == FINITE_CYCLE[0],
            f"{name}: half4 pattern differs",
        )
        expected_stream = expected_attribute_stream(name, vertex_count)
        require(
            intervention.get("attributeStreamLittleEndianHex") == expected_stream.hex(),
            f"{name}: explicit mutated stream differs",
        )
        expected_stream_sha = sha256_bytes(expected_stream)
        require(
            intervention.get("mutatedAttributeStreamSHA256") == expected_stream_sha,
            f"{name}: mutated stream differs",
        )
        require(expected_stream_sha != original_sha, f"{name}: input did not change")
        candidate_replay = intervention.get("replay")
        require(
            isinstance(candidate_replay, dict)
            and candidate_replay.get("executed") is True,
            f"{name}: replay did not execute",
        )
        snapshot = candidate_replay.get("output")
        require(isinstance(snapshot, dict), f"{name}: replay output is absent")
        candidate = raw_payload(capture_directory, snapshot, f"sample {sample} {name}")
        require(candidate == reference, f"{name}: replay bytes differ")
        comparison = intervention.get("comparison")
        require(isinstance(comparison, dict), f"{name}: comparison is absent")
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
            require(comparison.get(field) == expected, f"{name}: {field} differs")
        candidate_sha256 = sha256_bytes(candidate)
        if output_sha256 is None:
            output_sha256 = candidate_sha256
        require(output_sha256 == candidate_sha256, "candidate output digests differ")
    require(output_sha256 is not None, "candidate output digest is absent")
    return {
        "sampleIndex": sample,
        "originalAttributeStreamSHA256": original_sha,
        "outputSHA256": output_sha256,
        "comparedBytes": 2 * EXPECTED_RENDER_BYTES,
        "unequalBytes": 0,
        "unequalPixels": 0,
        "maximumChannelDelta": 0,
    }


def validate(
    capture_directory: Path,
    preregistration_path: Path,
    amendment_path: Path,
    quad_fallback_amendment_path: Path,
    pass_selection_amendment_path: Path,
    clear_load_amendment_path: Path,
    compile_correction_path: Path,
    preflight_path: Path,
) -> JsonObject:
    preregistration = load_json(preregistration_path)
    require(
        preregistration.get("smallClearFinalColorPreregistrationSchemaVersion") == 1,
        "preregistration schema differs",
    )
    amendment = load_json(amendment_path)
    require(
        amendment.get("smallClearFinalColorTransportAmendmentSchemaVersion") == 1,
        "transport amendment schema differs",
    )
    require(
        amendment.get("basePreregistrationSHA256") == sha256_file(preregistration_path),
        "base preregistration SHA-256 differs",
    )
    quad_fallback = load_json(quad_fallback_amendment_path)
    require(
        quad_fallback.get("smallClearFinalColorQuadFallbackAmendmentSchemaVersion")
        == 1,
        "quad fallback amendment schema differs",
    )
    require(
        quad_fallback.get("basePreregistrationSHA256")
        == sha256_file(preregistration_path),
        "quad fallback base preregistration SHA-256 differs",
    )
    require(
        quad_fallback.get("transportAmendmentSHA256") == sha256_file(amendment_path),
        "transport amendment SHA-256 differs",
    )
    pass_selection = load_json(pass_selection_amendment_path)
    require(
        pass_selection.get("smallClearFinalColorPassSelectionAmendmentSchemaVersion")
        == 1,
        "pass selection amendment schema differs",
    )
    require(
        pass_selection.get("basePreregistrationSHA256")
        == sha256_file(preregistration_path),
        "pass selection base preregistration SHA-256 differs",
    )
    require(
        pass_selection.get("transportAmendmentSHA256") == sha256_file(amendment_path),
        "pass selection transport amendment SHA-256 differs",
    )
    require(
        pass_selection.get("quadFallbackAmendmentSHA256")
        == sha256_file(quad_fallback_amendment_path),
        "quad fallback amendment SHA-256 differs",
    )
    clear_load = load_json(clear_load_amendment_path)
    require(
        clear_load.get("smallClearFinalColorClearLoadAmendmentSchemaVersion") == 1,
        "clear-load amendment schema differs",
    )
    require(
        clear_load.get("basePreregistrationSHA256")
        == sha256_file(preregistration_path),
        "clear-load base preregistration SHA-256 differs",
    )
    require(
        clear_load.get("transportAmendmentSHA256") == sha256_file(amendment_path),
        "clear-load transport amendment SHA-256 differs",
    )
    require(
        clear_load.get("quadFallbackAmendmentSHA256")
        == sha256_file(quad_fallback_amendment_path),
        "clear-load quad fallback amendment SHA-256 differs",
    )
    require(
        clear_load.get("passSelectionAmendmentSHA256")
        == sha256_file(pass_selection_amendment_path),
        "pass selection amendment SHA-256 differs",
    )
    compile_correction = load_json(compile_correction_path)
    require(
        compile_correction.get("smallClearFinalColorCompileCorrectionSchemaVersion")
        == 1,
        "compile correction schema differs",
    )
    require(
        compile_correction.get("clearLoadAmendmentSHA256")
        == sha256_file(clear_load_amendment_path),
        "clear-load amendment SHA-256 differs",
    )
    validate_sources(compile_correction)
    preflight = load_json(preflight_path)
    require(preflight.get("passed") is True, "Retina preflight did not pass")
    require(preflight.get("backingScaleFactor") == 2, "Retina scale differs")
    require(
        preflight.get("physicalPixels") == [3456, 2234],
        "Retina physical extent differs",
    )

    timeline_path = capture_directory / "transition-timeline.json"
    timeline = load_json(timeline_path)
    expected_timeline = {
        "material": "clear",
        "appearance": "light",
        "direction": "materialize",
        "sampleCount": 33,
        "windowBackingScaleFactor": 2,
        "failedSamples": 0,
        "expectedWindowPixels": [2048, 2048],
    }
    for field, expected in expected_timeline.items():
        require(timeline.get(field) == expected, f"timeline {field} differs")
    geometry = timeline.get("geometry")
    require(
        isinstance(geometry, dict)
        and geometry.get("name") == "circle-047-center"
        and geometry.get("shape") == "circle"
        and geometry.get("width") == 47
        and geometry.get("height") == 47
        and geometry.get("centerX") == 512
        and geometry.get("centerY") == 512,
        "timeline geometry differs",
    )
    uniforms = timeline.get("dynamicBackgroundUniforms")
    require(isinstance(uniforms, dict), "dynamic records are absent")
    expected_uniforms = {
        "schemaVersion": 9,
        "requested": True,
        "executed": True,
        "evidenceMode": "controlled-replay-v1",
        "sampleIndices": list(EXPECTED_RECORD_SAMPLES),
        "sampleCount": len(EXPECTED_RECORD_SAMPLES),
        "executedSampleCount": len(EXPECTED_RECORD_SAMPLES),
        "presentationLayerReplayed": True,
        "presentationLayerAssignedToCARenderer": False,
        "freshStaticCarrier": True,
        "detachedLayerTreeCopies": False,
    }
    for field, expected in expected_uniforms.items():
        require(uniforms.get(field) == expected, f"dynamic {field} differs")
    raw_records = uniforms.get("records")
    require(
        isinstance(raw_records, list)
        and len(raw_records) == len(EXPECTED_RECORD_SAMPLES)
        and all(isinstance(value, dict) for value in raw_records),
        "dynamic record list differs",
    )
    records = {value.get("sampleIndex"): value for value in raw_records}
    require(set(records) == set(EXPECTED_RECORD_SAMPLES), "record sample set differs")
    endpoint_trace = exact_replay(records[32]).get(
        "finalHighlightVertexTailIntervention"
    )
    require(endpoint_trace is None, "endpoint unexpectedly executed intervention")
    selected = validate_selection(records)
    intervention = validate_intervention(capture_directory, records[selected])
    return {
        "smallClearFinalColorValidationSchemaVersion": 1,
        "passed": True,
        "authority": (
            "current-build observational irrelevance of active half4 bytes 32 "
            "through 39 for the exact small-clear Tkfh pipeline"
        ),
        "formalLiquidGlassParity": False,
        "captureDirectory": capture_directory.name,
        "timelineSHA256": sha256_file(timeline_path),
        "preregistrationSHA256": sha256_file(preregistration_path),
        "transportAmendmentSHA256": sha256_file(amendment_path),
        "quadFallbackAmendmentSHA256": sha256_file(quad_fallback_amendment_path),
        "passSelectionAmendmentSHA256": sha256_file(pass_selection_amendment_path),
        "clearLoadAmendmentSHA256": sha256_file(clear_load_amendment_path),
        "compileCorrectionSHA256": sha256_file(compile_correction_path),
        "candidateSampleIndices": list(CANDIDATE_SAMPLES),
        "selectedSampleIndex": selected,
        "intervention": intervention,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture_directory", type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--transport-amendment", required=True, type=Path)
    parser.add_argument("--quad-fallback-amendment", required=True, type=Path)
    parser.add_argument("--pass-selection-amendment", required=True, type=Path)
    parser.add_argument("--clear-load-amendment", required=True, type=Path)
    parser.add_argument("--compile-correction", required=True, type=Path)
    parser.add_argument("--preflight", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(
        arguments.capture_directory,
        arguments.preregistration,
        arguments.transport_amendment,
        arguments.quad_fallback_amendment,
        arguments.pass_selection_amendment,
        arguments.clear_load_amendment,
        arguments.compile_correction,
        arguments.preflight,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
