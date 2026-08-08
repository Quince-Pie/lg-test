#!/usr/bin/env python3
"""Validate the prospective small-clear Tghn controlled replay."""

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
import math
from pathlib import Path
import struct
from typing import Any, Never


type JsonObject = dict[str, Any]

REPOSITORY = Path(__file__).resolve().parents[1]
PIPELINE = "com.apple.coreanimation.PBGRABsovXm_TghnA2Xhf_Isrc_Isrc"
CANDIDATE_SAMPLES = tuple(range(2, 32))
EXPECTED_RECORD_SAMPLES = tuple(range(2, 33))
EXPECTED_INDEX = bytes.fromhex("000001000200020003000000")
EXPECTED_LAYOUT = (
    ("pipeline", None, None),
    ("scissorRect", None, None),
    ("buffer", "fragment", 1),
    ("texture", "fragment", 3),
    ("sampler", "fragment", 0),
    ("texture", "fragment", 4),
    ("sampler", "fragment", 1),
    ("buffer", "fragment", 2),
    ("buffer", "fragment", 6),
    ("buffer", "vertex", 3),
    ("buffer", "vertex", 2),
    ("buffer", "vertex", 1),
    ("drawIndexedPrimitives", None, None),
)
VERTEX_COUNT = 4
VERTEX_STRIDE = 48
ACTIVE_VERTEX_BYTES = VERTEX_COUNT * VERTEX_STRIDE
FRAGMENT_BYTES = 210
TAIL_OFFSET = 40
TAIL_BYTES = 8
FINITE_TAIL = bytes.fromhex("003c003800bc0040")
INTERVENTIONS = (
    "ordinary-ties-to-even-high-coordinate",
    "zero-unclassified-tail",
    "finite-unclassified-tail",
)


def fail(message: str) -> Never:
    raise ValueError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    require(isinstance(value, dict), f"{label} is not an object")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    require(isinstance(value, list), f"{label} is not an array")
    return value


def load_json(path: Path, label: str) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{label} is not an object")
    return value


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def f32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", f32(value)))[0]


def f32_from_bits(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def binary32_halfway(value: float) -> bool:
    """Return whether a finite binary64 value is midway between floats."""
    rounded = f32(value)
    if value == rounded:
        return False
    bits = f32_bits(rounded)
    adjacent = f32_from_bits(bits + (-1 if value < rounded else 1))
    return value == (float(rounded) + float(adjacent)) / 2.0


def pipeline_label(record: Mapping[str, Any]) -> str:
    pipeline = record.get("pipeline")
    if not isinstance(pipeline, dict):
        return ""
    label = pipeline.get("label")
    return label if isinstance(label, str) else ""


def payload(snapshot: Mapping[str, Any], label: str) -> bytes:
    description = mapping(snapshot.get("payload"), f"{label} payload")
    encoded = description.get("hex")
    length = description.get("lengthBytes")
    require(isinstance(encoded, str), f"{label} payload is not hexadecimal")
    try:
        result = bytes.fromhex(encoded)
    except ValueError as error:
        raise ValueError(f"{label} payload is not hexadecimal") from error
    require(length == len(result), f"{label} payload length differs")
    return result


def one_snapshot(
    snapshots: Sequence[Any],
    *,
    sequence_number: int,
    stage: str,
    index: int,
    label: str,
) -> Mapping[str, Any]:
    matches = [
        value
        for value in snapshots
        if isinstance(value, dict)
        and value.get("sequence") == sequence_number
        and value.get("stage") == stage
        and value.get("index") == index
        and pipeline_label(value) == PIPELINE
    ]
    require(len(matches) == 1, f"{label} snapshot count differs")
    return matches[0]


def exact_replay(record: Mapping[str, Any]) -> Mapping[str, Any]:
    sample = record.get("sampleIndex")
    render = mapping(record.get("render"), f"sample {sample} render")
    replay = mapping(render.get("exactPassReplay"), f"sample {sample} replay")
    require(replay.get("executed") is True, f"sample {sample} replay failed")
    require(replay.get("exactByteMatch") is True, f"sample {sample} replay differs")
    require(replay.get("mismatchedByteCount") == 0, "full replay byte count differs")
    require(replay.get("mismatchedPixelCount") == 0, "full replay pixel count differs")
    require(replay.get("maximumChannelDelta") == 0, "full replay delta differs")
    return replay


def branch_inputs(record: Mapping[str, Any]) -> JsonObject | None:
    sample = record.get("sampleIndex")
    render = mapping(record.get("render"), f"sample {sample} render")
    probe = mapping(render.get("metalUniformProbe"), f"sample {sample} probe")
    snapshot_root = mapping(
        render.get("metalBufferSnapshots"), f"sample {sample} snapshots"
    )
    records = [
        mapping(value, "Metal record")
        for value in sequence(probe.get("records"), "Metal records")
    ]
    branch = [value for value in records if pipeline_label(value) == PIPELINE]
    if not branch:
        return None
    observed_layout = tuple(
        (value.get("kind"), value.get("stage"), value.get("index"))
        for value in branch
    )
    require(observed_layout == EXPECTED_LAYOUT, f"sample {sample} topology differs")
    draw = branch[-1]
    require(
        draw.get("primitiveType") == 3
        and draw.get("indexCount") == 6
        and draw.get("indexType") == 0,
        f"sample {sample} indexed draw differs",
    )
    bindings = {
        (value.get("stage"), value.get("index")): value
        for value in branch
        if value.get("kind") == "buffer"
    }
    snapshots = sequence(snapshot_root.get("snapshots"), "buffer snapshots")
    fragment_binding = bindings[("fragment", 1)]
    vertex_binding = bindings[("vertex", 1)]
    fragment = payload(
        one_snapshot(
            snapshots,
            sequence_number=fragment_binding["sequence"],
            stage="fragment",
            index=1,
            label="fragment[1]",
        ),
        "fragment[1]",
    )
    vertex = payload(
        one_snapshot(
            snapshots,
            sequence_number=vertex_binding["sequence"],
            stage="vertex",
            index=1,
            label="vertex[1]",
        ),
        "vertex[1]",
    )
    index = payload(
        one_snapshot(
            snapshots,
            sequence_number=draw["sequence"],
            stage="index",
            index=-1,
            label="index",
        ),
        "index",
    )
    require(len(fragment) >= FRAGMENT_BYTES, "fragment snapshot is truncated")
    require(len(vertex) >= ACTIVE_VERTEX_BYTES, "vertex snapshot is truncated")
    require(len(index) >= len(EXPECTED_INDEX), "index snapshot is truncated")
    require(index[: len(EXPECTED_INDEX)] == EXPECTED_INDEX, "indices differ")
    return {
        "fragment": fragment[:FRAGMENT_BYTES],
        "vertex": vertex[:ACTIVE_VERTEX_BYTES],
        "index": index[: len(EXPECTED_INDEX)],
    }


def decision_from_inputs(inputs: Mapping[str, Any]) -> JsonObject:
    fragment = inputs["fragment"]
    vertex = inputs["vertex"]
    require(isinstance(fragment, bytes), "fragment input type differs")
    require(isinstance(vertex, bytes), "vertex input type differs")
    values = struct.unpack("<48f", vertex)
    fragment_scale = struct.unpack_from("<f", fragment)[0]
    backdrop_scale = f32(fragment_scale * 64.0)
    require(math.isfinite(backdrop_scale) and backdrop_scale > 0, "scale differs")
    reciprocal = f32(1.0 / backdrop_scale)
    base_x = values[0]
    base_y = f32(values[1] + 8.0)
    origin_x = float(base_x) - float(values[6])
    origin_y = float(values[1]) - float(values[7])
    require(
        math.isfinite(origin_x)
        and math.isfinite(origin_y)
        and origin_x == round(origin_x)
        and origin_y == round(origin_y),
        "reconstructed origin differs",
    )
    high_backdrop_x = values[16]
    high_backdrop_y = values[29]
    require(
        math.isfinite(high_backdrop_x) and math.isfinite(high_backdrop_y),
        "reconstructed extent is non-finite",
    )
    extent_x = round(high_backdrop_x)
    extent_y = round(high_backdrop_y)
    require(
        extent_x > 0
        and extent_y > 0
        and extent_x % 4 == 0
        and extent_y % 4 == 0,
        "reconstructed extent differs",
    )
    delta_x = f32(float(extent_x) * reciprocal)
    delta_y = f32(float(extent_y) * reciprocal)
    raw_high = (
        float(base_x) + float(delta_x) - origin_x,
        float(base_y) + float(delta_y) - origin_y,
    )
    captured = (values[18], values[31])
    duplicate = (values[30], values[43])
    axes: list[JsonObject] = []
    for name, raw, observed, repeated, offsets in zip(
        ("x", "y"),
        raw_high,
        captured,
        duplicate,
        ((VERTEX_STRIDE + 24, 2 * VERTEX_STRIDE + 24),
         (2 * VERTEX_STRIDE + 28, 3 * VERTEX_STRIDE + 28)),
        strict=True,
    ):
        rounded = f32(raw)
        require(f32_bits(observed) == f32_bits(repeated), "duplicate high differs")
        axes.append(
            {
                "name": name,
                "raw": raw,
                "rounded": rounded,
                "captured": observed,
                "duplicate": repeated,
                "offsets": offsets,
                "halfway": binary32_halfway(raw),
                "differs": f32_bits(rounded) != f32_bits(observed),
            }
        )
    differing = [axis for axis in axes if axis["halfway"] and axis["differs"]]
    return {
        "backdropScale": backdrop_scale,
        "reciprocalScale": reciprocal,
        "origin": [int(origin_x), int(origin_y)],
        "extent": [extent_x, extent_y],
        "axes": axes,
        "differing": differing,
    }


def mutated_vertex_streams(
    original: bytes, decision: Mapping[str, Any]
) -> dict[str, bytes]:
    require(len(original) == ACTIVE_VERTEX_BYTES, "active vertex size differs")
    ties = bytearray(original)
    for axis in decision["differing"]:
        encoded = struct.pack("<f", axis["rounded"])
        for offset in axis["offsets"]:
            ties[offset : offset + 4] = encoded
    zero_tail = bytearray(original)
    finite_tail = bytearray(original)
    for vertex in range(VERTEX_COUNT):
        start = vertex * VERTEX_STRIDE + TAIL_OFFSET
        zero_tail[start : start + TAIL_BYTES] = bytes(TAIL_BYTES)
        finite_tail[start : start + TAIL_BYTES] = FINITE_TAIL
    return {
        INTERVENTIONS[0]: bytes(ties),
        INTERVENTIONS[1]: bytes(zero_tail),
        INTERVENTIONS[2]: bytes(finite_tail),
    }


def trace_for(record: Mapping[str, Any]) -> Mapping[str, Any]:
    replay = exact_replay(record)
    trace = replay.get("smallClearBackgroundIntervention")
    require(isinstance(trace, dict), "Tghn intervention trace is absent")
    require(trace.get("schemaVersion") == 1, "Tghn trace schema differs")
    return trace


def validate_trace_axis(
    trace_axis: Mapping[str, Any], expected: Mapping[str, Any]
) -> None:
    require(trace_axis.get("axis") == expected["name"], "axis name differs")
    require(trace_axis.get("rawBinary64") == expected["raw"], "axis raw differs")
    require(
        trace_axis.get("rawBinary64Bits")
        == f"{struct.unpack('<Q', struct.pack('<d', expected['raw']))[0]:016x}",
        "axis binary64 bits differ",
    )
    rounded = mapping(trace_axis.get("ordinaryTiesToEven"), "rounded axis")
    captured = mapping(trace_axis.get("captured"), "captured axis")
    duplicate = mapping(trace_axis.get("duplicate"), "duplicate axis")
    require(
        rounded.get("littleEndianBits") == f"{f32_bits(expected['rounded']):08x}",
        "rounded axis bits differ",
    )
    require(
        captured.get("littleEndianBits") == f"{f32_bits(expected['captured']):08x}",
        "captured axis bits differ",
    )
    require(
        duplicate.get("littleEndianBits") == f"{f32_bits(expected['duplicate']):08x}",
        "duplicate axis bits differ",
    )
    require(trace_axis.get("exactHalfway") is expected["halfway"], "halfway differs")
    require(
        trace_axis.get("ordinaryTiesToEvenDiffers") is expected["differs"],
        "axis difference classification differs",
    )


def raw_payload(
    capture_directory: Path,
    snapshot: Mapping[str, Any],
    label: str,
) -> bytes:
    width = snapshot.get("width")
    height = snapshot.get("height")
    require(
        isinstance(width, int) and width > 0,
        f"{label} width differs",
    )
    require(
        isinstance(height, int) and height > 0,
        f"{label} height differs",
    )
    require(snapshot.get("pixelFormat") == 80, f"{label} format differs")
    expected_bytes = width * height * 4
    require(snapshot.get("rawBytes") == expected_bytes, f"{label} bytes differ")
    relative = snapshot.get("rawFile")
    require(isinstance(relative, str), f"{label} raw path is absent")
    path = capture_directory / relative
    require(path.is_file(), f"{label} raw file is absent")
    result = path.read_bytes()
    require(len(result) == expected_bytes, f"{label} disk bytes differ")
    return result


def validate_exact_comparison(
    comparison: Mapping[str, Any], byte_count: int, label: str
) -> None:
    expected = {
        "compared": True,
        "exactByteMatch": True,
        "byteCount": byte_count,
        "mismatchedByteCount": 0,
        "mismatchedPixelCount": 0,
        "matchingPixelFraction": 1.0,
        "meanAbsoluteChannelDelta": 0.0,
        "rootMeanSquareChannelDelta": 0.0,
        "maximumChannelDelta": 0,
        "firstMismatchedByte": -1,
    }
    for field, value in expected.items():
        require(comparison.get(field) == value, f"{label} {field} differs")


def validate_selected(
    capture_directory: Path,
    record: Mapping[str, Any],
    inputs: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> JsonObject:
    sample = record.get("sampleIndex")
    trace = trace_for(record)
    expected_scalars = {
        "executed": True,
        "eligible": True,
        "selected": True,
        "selectionPolicy": (
            "first exact-halfway Tghn state whose captured high coordinate "
            "differs from ordinary ties-to-even"
        ),
        "classification": (
            "captured Apple small-clear Tghn coordinate/tail "
            "pixel-influence intervention"
        ),
        "liveAppleFrameMutated": False,
        "capturedApplePipelinesUnmodified": True,
        "pipelineLabel": PIPELINE,
        "indexCount": 6,
        "vertexCount": VERTEX_COUNT,
        "vertexStride": VERTEX_STRIDE,
        "fragmentMeaningfulByteCount": FRAGMENT_BYTES,
        "reconstructedOrigin": decision["origin"],
        "reconstructedExtent": decision["extent"],
        "differingHalfwayAxisCount": len(decision["differing"]),
        "interventionCount": len(INTERVENTIONS),
        "allInterventionsExact": True,
    }
    for field, value in expected_scalars.items():
        require(trace.get(field) == value, f"sample {sample}: {field} differs")
    require(
        trace.get("originalActiveVertexSHA256") == sha256_bytes(inputs["vertex"]),
        "original vertex digest differs",
    )
    require(
        trace.get("fragmentPrefixSHA256") == sha256_bytes(inputs["fragment"]),
        "fragment digest differs",
    )
    require(
        trace.get("indexSHA256") == sha256_bytes(inputs["index"]),
        "index digest differs",
    )
    trace_axes = sequence(trace.get("axisDecisions"), "axis decisions")
    require(len(trace_axes) == 2, "axis decision count differs")
    for observed, expected in zip(trace_axes, decision["axes"], strict=True):
        validate_trace_axis(mapping(observed, "axis decision"), expected)

    reference = mapping(trace.get("reference"), "prefix reference")
    require(reference.get("executed") is True, "prefix reference failed")
    reference_snapshot = mapping(reference.get("output"), "reference output")
    reference_bytes = raw_payload(
        capture_directory, reference_snapshot, "prefix reference"
    )
    expected_streams = mutated_vertex_streams(inputs["vertex"], decision)
    require(
        all(value != inputs["vertex"] for value in expected_streams.values()),
        "an intervention did not change its active vertex stream",
    )
    raw_interventions = sequence(trace.get("interventions"), "interventions")
    require(len(raw_interventions) == len(INTERVENTIONS), "count differs")
    interventions = {
        value.get("name"): mapping(value, "intervention")
        for value in raw_interventions
        if isinstance(value, dict)
    }
    require(set(interventions) == set(INTERVENTIONS), "names differ")
    for name in INTERVENTIONS:
        intervention = interventions[name]
        require(
            intervention.get("mutatedActiveVertexSHA256")
            == sha256_bytes(expected_streams[name]),
            f"{name}: mutated vertex digest differs",
        )
        replay = mapping(intervention.get("replay"), f"{name} replay")
        require(replay.get("executed") is True, f"{name}: replay failed")
        snapshot = mapping(replay.get("output"), f"{name} output")
        candidate = raw_payload(capture_directory, snapshot, f"{name} output")
        require(candidate == reference_bytes, f"{name}: raw output differs")
        validate_exact_comparison(
            mapping(intervention.get("comparison"), f"{name} comparison"),
            len(reference_bytes),
            name,
        )
    return {
        "sampleIndex": sample,
        "differingHalfwayAxes": [axis["name"] for axis in decision["differing"]],
        "referenceBytes": len(reference_bytes),
        "referenceSHA256": sha256_bytes(reference_bytes),
        "comparedBytes": len(INTERVENTIONS) * len(reference_bytes),
        "unequalBytes": 0,
        "unequalPixels": 0,
        "maximumChannelDelta": 0,
    }


def validate_sources(preregistration: Mapping[str, Any]) -> None:
    sources = mapping(preregistration.get("sourceSHA256"), "source hash map")
    for relative, expected in sources.items():
        require(
            isinstance(relative, str) and isinstance(expected, str),
            "source hash entry is malformed",
        )
        path = REPOSITORY / relative
        require(path.is_file(), f"pinned source is absent: {relative}")
        require(sha256_file(path) == expected, f"pinned source differs: {relative}")


def validate(
    capture_directory: Path,
    preregistration_path: Path,
    preflight_path: Path,
) -> JsonObject:
    preregistration = load_json(preregistration_path, "preregistration")
    require(
        preregistration.get("smallClearBackgroundPreregistrationSchemaVersion") == 1,
        "preregistration schema differs",
    )
    validate_sources(preregistration)
    preflight = load_json(preflight_path, "Retina preflight")
    require(preflight.get("passed") is True, "Retina preflight failed")
    require(preflight.get("backingScaleFactor") == 2, "Retina scale differs")
    require(preflight.get("physicalPixels") == [3456, 2234], "Retina pixels differ")

    timeline_path = capture_directory / "transition-timeline.json"
    timeline = load_json(timeline_path, "transition timeline")
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
        require(timeline.get(field) == value, f"timeline {field} differs")
    geometry = mapping(timeline.get("geometry"), "timeline geometry")
    require(
        geometry.get("name") == "circle-combined-holdout-01"
        and geometry.get("shape") == "circle"
        and geometry.get("width") == 53
        and geometry.get("height") == 53
        and geometry.get("centerX") == 11.25
        and geometry.get("centerY") == 211.75,
        "timeline geometry differs",
    )
    uniforms = mapping(
        timeline.get("dynamicBackgroundUniforms"), "dynamic uniforms"
    )
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
    for field, value in expected_uniforms.items():
        require(uniforms.get(field) == value, f"dynamic {field} differs")
    raw_records = sequence(uniforms.get("records"), "dynamic records")
    records = {
        value.get("sampleIndex"): mapping(value, "dynamic record")
        for value in raw_records
        if isinstance(value, dict)
    }
    require(set(records) == set(EXPECTED_RECORD_SAMPLES), "sample set differs")

    inputs: dict[int, JsonObject] = {}
    decisions: dict[int, JsonObject] = {}
    eligible: list[int] = []
    for sample in CANDIDATE_SAMPLES:
        exact_replay(records[sample])
        branch = branch_inputs(records[sample])
        require(branch is not None, f"sample {sample}: Tghn branch is absent")
        inputs[sample] = branch
        decisions[sample] = decision_from_inputs(branch)
        if decisions[sample]["differing"]:
            eligible.append(sample)
    require(eligible, "no exact-halfway differing Tghn state exists")
    selected = eligible[0]
    selected_capture = f"transition-background-uniform-{selected:02d}"
    for sample in CANDIDATE_SAMPLES:
        trace = trace_for(records[sample])
        is_eligible = bool(decisions[sample]["differing"])
        require(trace.get("eligible") is is_eligible, f"sample {sample}: eligibility differs")
        if sample == selected:
            require(trace.get("selected") is True, "first eligible state was not selected")
            require(trace.get("executed") is True, "selected intervention did not execute")
        elif is_eligible:
            require(sample > selected, "an earlier eligible state was skipped")
            require(trace.get("selected") is False, "later eligible state was selected")
            require(trace.get("executed") is False, "later eligible state executed")
            require(
                trace.get("selectedCapture") == selected_capture,
                "selected capture identity differs",
            )
            require(
                trace.get("reason") == "earlier eligible Tghn state selected",
                "later eligible reason differs",
            )
        else:
            require(trace.get("selected") is False, "ineligible state was selected")
            require(trace.get("executed") is False, "ineligible state executed")
            require(
                trace.get("reason") == "no differing exact-halfway decision in state",
                "ineligible reason differs",
            )
    exact_replay(records[32])
    require(
        exact_replay(records[32]).get("smallClearBackgroundIntervention") is None,
        "endpoint unexpectedly executed the intervention",
    )
    intervention = validate_selected(
        capture_directory,
        records[selected],
        inputs[selected],
        decisions[selected],
    )
    return {
        "smallClearBackgroundValidationSchemaVersion": 1,
        "passed": True,
        "authority": (
            "current-build Tghn observational pixel influence for the "
            "ordinary-ties-to-even midpoint alternative and bytes 40 through 47"
        ),
        "formalLiquidGlassParity": False,
        "captureDirectory": capture_directory.name,
        "timelineSHA256": sha256_file(timeline_path),
        "preregistrationSHA256": sha256_file(preregistration_path),
        "candidateSampleIndices": list(CANDIDATE_SAMPLES),
        "eligibleSampleIndices": eligible,
        "selectedSampleIndex": selected,
        "intervention": intervention,
    }


def main() -> int:
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
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
