#!/usr/bin/env python3
"""Validate the nonvacuous controlled-target Tmua source replay."""

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
from typing import Any, Never


type JsonObject = dict[str, Any]

REPOSITORY = Path(__file__).resolve().parents[1]
SAMPLES = tuple(range(3, 10))
STAGES = ("Tghn", "Irsd")
TARGET_BYTES = 4_194_304
TMUA_SOURCE_SHA256 = "7db629a886e5cd6982b3e23b2170681194cf9956d97de086754e68598b705c3e"
TGHN_PIPELINE = "com.apple.coreanimation.PBGRABsovXm_TghnA2Xhf_Isrc_Isrc"
FINAL_PIPELINE = "com.apple.coreanimation.PBGRAXm_A2Xghfc"


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


def validate_sources(preregistration: Mapping[str, Any]) -> None:
    sources = mapping(preregistration.get("sourceSHA256"), "pinned sources")
    for relative, expected in sources.items():
        require(
            isinstance(relative, str) and isinstance(expected, str),
            "source hash entry is malformed",
        )
        path = REPOSITORY / relative
        require(path.is_file(), f"pinned source is absent: {relative}")
        require(sha256_file(path) == expected, f"pinned source differs: {relative}")


def raw_payload(
    directory: Path,
    snapshot: Mapping[str, Any],
    label: str,
) -> bytes:
    width = snapshot.get("width")
    height = snapshot.get("height")
    pixel_format = snapshot.get("pixelFormat")
    pixel_bytes = {80: 4, 81: 4, 115: 8}.get(pixel_format)
    require(isinstance(width, int) and width > 0, f"{label} width differs")
    require(isinstance(height, int) and height > 0, f"{label} height differs")
    require(pixel_bytes is not None, f"{label} pixel format differs")
    expected_bytes = width * height * pixel_bytes
    require(snapshot.get("rawCapture") is True, f"{label} was not captured")
    require(snapshot.get("rawBytes") == expected_bytes, f"{label} rawBytes differs")
    filename = snapshot.get("rawFile")
    require(isinstance(filename, str), f"{label} filename differs")
    require(Path(filename).name == filename, f"{label} filename escapes root")
    path = directory / filename
    require(path.is_file(), f"{label} raw file is absent")
    payload = path.read_bytes()
    require(len(payload) == expected_bytes, f"{label} disk bytes differ")
    return payload


def pattern_payload(width: int, height: int, salt: int) -> bytes:
    result = bytearray(width * height * 4)
    for y in range(height):
        for x in range(width):
            offset = (y * width + x) * 4
            word = ((x * 0x45D9F3B) ^ (y * 0x119DE1F) ^ salt) & 0xFFFFFFFF
            result[offset] = word & 0xFF
            result[offset + 1] = (word >> 8) & 0xFF
            result[offset + 2] = (word >> 16) & 0xFF
            result[offset + 3] = 0xFF
    return bytes(result)


def comparison_metrics(left: bytes, right: bytes) -> JsonObject:
    require(len(left) == len(right), "comparison lengths differ")
    require(len(left) % 4 == 0, "comparison is not BGRA8")
    mismatched_bytes = 0
    mismatched_pixels = 0
    maximum_delta = 0
    first = -1
    absolute_delta = 0
    squared_delta = 0
    for index, (lhs, rhs) in enumerate(zip(left, right, strict=True)):
        delta = abs(lhs - rhs)
        if delta:
            mismatched_bytes += 1
            if first < 0:
                first = index
        maximum_delta = max(maximum_delta, delta)
        absolute_delta += delta
        squared_delta += delta * delta
    for offset in range(0, len(left), 4):
        mismatched_pixels += left[offset : offset + 4] != right[offset : offset + 4]
    return {
        "byteCount": len(left),
        "mismatchedByteCount": mismatched_bytes,
        "mismatchedPixelCount": mismatched_pixels,
        "maximumChannelDelta": maximum_delta,
        "firstMismatchedByte": first,
        "absoluteChannelDelta": absolute_delta,
        "squaredChannelDelta": squared_delta,
    }


def validate_reported_comparison(
    reported: Mapping[str, Any],
    measured: Mapping[str, Any],
    label: str,
) -> None:
    for field in (
        "byteCount",
        "mismatchedByteCount",
        "mismatchedPixelCount",
        "maximumChannelDelta",
        "firstMismatchedByte",
    ):
        require(reported.get(field) == measured[field], f"{label} {field} differs")
    exact = measured["mismatchedByteCount"] == 0
    require(reported.get("compared") is True, f"{label} was not compared")
    require(reported.get("exactByteMatch") is exact, f"{label} exact flag differs")


def snapshot_from_replay(
    replay: Mapping[str, Any],
    label: str,
) -> Mapping[str, Any]:
    require(replay.get("executed") is True, f"{label} replay failed")
    snapshot = mapping(replay.get("output"), f"{label} output")
    require(snapshot.get("width") == 1024, f"{label} width differs")
    require(snapshot.get("height") == 1024, f"{label} height differs")
    require(snapshot.get("pixelFormat") == 80, f"{label} pixel format differs")
    return snapshot


def validate_trace(
    directory: Path,
    trace: Mapping[str, Any],
    sample: int,
) -> JsonObject:
    label = f"sample {sample}"
    require(trace.get("schemaVersion") == 1, f"{label} schema differs")
    require(trace.get("executed") is True, f"{label} intervention failed")
    require(trace.get("eligible") is True, f"{label} intervention ineligible")
    require(
        trace.get("classification")
        == "nonvacuous controlled-target Tmua source influence replay",
        f"{label} classification differs",
    )
    require(trace.get("liveAppleFrameMutated") is False, f"{label} live frame mutated")
    require(
        trace.get("capturedApplePipelinesUnmodified") is True,
        f"{label} Apple pipeline changed",
    )
    require(trace.get("tghnPipelineLabel") == TGHN_PIPELINE, f"{label} Tghn differs")
    require(trace.get("finalPipelineLabel") == FINAL_PIPELINE, f"{label} Irsd differs")
    tghn_pipeline_index = trace.get("tghnPipelineCommandIndex")
    tghn_draw_index = trace.get("tghnDrawIndex")
    final_pipeline_index = trace.get("finalPipelineCommandIndex")
    final_draw_index = trace.get("finalDrawIndex")
    require(
        all(
            isinstance(value, int)
            for value in (
                tghn_pipeline_index,
                tghn_draw_index,
                final_pipeline_index,
                final_draw_index,
            )
        ),
        f"{label} command positions differ",
    )
    require(
        tghn_pipeline_index < tghn_draw_index < final_pipeline_index < final_draw_index,
        f"{label} command order differs",
    )

    source_snapshot = mapping(trace.get("sourceTexture"), f"{label} source")
    zero_snapshot = mapping(trace.get("zeroTexture"), f"{label} zero")
    for snapshot_name, snapshot in (
        ("source", source_snapshot),
        ("zero", zero_snapshot),
    ):
        require(snapshot.get("width") == 128, f"{label} {snapshot_name} width differs")
        require(
            snapshot.get("height") == 128, f"{label} {snapshot_name} height differs"
        )
        require(
            snapshot.get("pixelFormat") == 115,
            f"{label} {snapshot_name} pixel format differs",
        )
    source = raw_payload(directory, source_snapshot, f"{label} source")
    zero = raw_payload(directory, zero_snapshot, f"{label} zero")
    require(sha256_bytes(source) == TMUA_SOURCE_SHA256, f"{label} source differs")
    require(any(source), f"{label} source is vacuous")
    require(not any(zero), f"{label} zero replacement is nonzero")
    require(len(source) == len(zero) == 131_072, f"{label} source bytes differ")

    controlled_specs = (
        ("destinationSeed", 0x13579BDF, (1024, 1024)),
        ("controlledTghnBackdrop", 0x2468ACE0, (64, 64)),
        ("controlledFinalInput", 0x0F1E2D3C, (576, 448)),
    )
    controlled_hashes: dict[str, str] = {}
    for field, salt, expected_dimensions in controlled_specs:
        snapshot = mapping(trace.get(field), f"{label} {field}")
        width = snapshot.get("width")
        height = snapshot.get("height")
        require(
            (width, height) == expected_dimensions,
            f"{label} {field} dimensions differ",
        )
        require(
            snapshot.get("pixelFormat") == 80,
            f"{label} {field} pixel format differs",
        )
        payload = raw_payload(directory, snapshot, f"{label} {field}")
        require(
            payload == pattern_payload(width, height, salt),
            f"{label} {field} pattern differs",
        )
        controlled_hashes[field] = sha256_bytes(payload)

    stage_results: dict[str, JsonObject] = {}
    for stage_name in STAGES:
        stage = mapping(trace.get(stage_name), f"{label} {stage_name}")
        before = raw_payload(
            directory,
            snapshot_from_replay(
                mapping(stage.get("before"), f"{label} {stage_name} before"),
                f"{label} {stage_name} before",
            ),
            f"{label} {stage_name} before",
        )
        reference = raw_payload(
            directory,
            snapshot_from_replay(
                mapping(stage.get("reference"), f"{label} {stage_name} reference"),
                f"{label} {stage_name} reference",
            ),
            f"{label} {stage_name} reference",
        )
        candidate = raw_payload(
            directory,
            snapshot_from_replay(
                mapping(stage.get("zeroSource"), f"{label} {stage_name} zero"),
                f"{label} {stage_name} zero",
            ),
            f"{label} {stage_name} zero",
        )
        require(
            len(before) == len(reference) == len(candidate) == TARGET_BYTES,
            f"{label} {stage_name} target bytes differ",
        )
        activity = comparison_metrics(before, reference)
        source_comparison = comparison_metrics(reference, candidate)
        require(
            activity["mismatchedByteCount"] > 0,
            f"{label} {stage_name} positive control is vacuous",
        )
        require(
            source_comparison["mismatchedByteCount"] == 0,
            f"{label} {stage_name} source replacement differs",
        )
        validate_reported_comparison(
            mapping(stage.get("activityComparison"), f"{label} activity"),
            activity,
            f"{label} {stage_name} activity",
        )
        validate_reported_comparison(
            mapping(stage.get("sourceComparison"), f"{label} source comparison"),
            source_comparison,
            f"{label} {stage_name} source comparison",
        )
        stage_results[stage_name] = {
            "activityMismatchedByteCount": activity["mismatchedByteCount"],
            "activityMismatchedPixelCount": activity["mismatchedPixelCount"],
            "activityMaximumChannelDelta": activity["maximumChannelDelta"],
            "referenceSHA256": sha256_bytes(reference),
            "zeroSourceSHA256": sha256_bytes(candidate),
            "sourceUnequalByteCount": 0,
        }
    require(
        trace.get("positiveControlsPassed") is True, f"{label} control flag differs"
    )
    require(trace.get("sourceComparisonsExact") is True, f"{label} source flag differs")
    return {
        "sampleIndex": sample,
        "sourceSHA256": sha256_bytes(source),
        "controlledTextureSHA256": controlled_hashes,
        "stages": stage_results,
    }


def validate(
    capture_directory: Path,
    preregistration_path: Path,
    preflight_path: Path,
) -> JsonObject:
    preregistration = load_json(preregistration_path, "preregistration")
    require(
        preregistration.get("smallClearTmuaNonvacuousPreregistrationSchemaVersion")
        == 1,
        "preregistration schema differs",
    )
    validate_sources(preregistration)
    preflight = load_json(preflight_path, "Retina preflight")
    require(preflight.get("passed") is True, "Retina preflight failed")
    require(preflight.get("backingScaleFactor") == 2, "Retina scale differs")
    require(preflight.get("physicalPixels") == [3456, 2234], "Retina pixels differ")

    timeline_path = capture_directory / "transition-timeline.json"
    timeline = load_json(timeline_path, "timeline")
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
    geometry = mapping(timeline.get("geometry"), "geometry")
    require(
        geometry.get("name") == "circle-combined-holdout-01"
        and geometry.get("shape") == "circle"
        and geometry.get("width") == 53
        and geometry.get("height") == 53
        and geometry.get("centerX") == 11.25
        and geometry.get("centerY") == 211.75,
        "timeline geometry differs",
    )
    uniforms = mapping(timeline.get("dynamicBackgroundUniforms"), "uniforms")
    require(uniforms.get("requested") is True, "uniform capture not requested")
    require(uniforms.get("executed") is True, "uniform capture failed")
    records: dict[int, Mapping[str, Any]] = {}
    for value in sequence(uniforms.get("records"), "uniform records"):
        record = mapping(value, "uniform record")
        sample = record.get("sampleIndex")
        require(isinstance(sample, int), "sample index differs")
        records[sample] = record
    require(set(SAMPLES).issubset(records), "candidate sample set differs")

    states: list[JsonObject] = []
    for sample in SAMPLES:
        render = mapping(records[sample].get("render"), f"sample {sample} render")
        replay = mapping(render.get("exactPassReplay"), f"sample {sample} replay")
        require(replay.get("executed") is True, f"sample {sample} replay failed")
        trace = mapping(
            replay.get("smallClearTmuaNonvacuousIntervention"),
            f"sample {sample} intervention",
        )
        states.append(validate_trace(capture_directory, trace, sample))

    return {
        "smallClearTmuaNonvacuousResultSchemaVersion": 1,
        "status": "exact-nonvacuous-small-clear-Tmua-source-irrelevance",
        "classification": (
            "prospective physical-Retina Apple-pipeline replay with populated "
            "destination, controlled texture-3 inputs, and per-consumer positive controls"
        ),
        "captureDirectory": capture_directory.name,
        "timelineSHA256": sha256_file(timeline_path),
        "stateCount": len(states),
        "AppleConsumerPositiveControlCount": len(states) * len(STAGES),
        "sourceComparisonCount": len(states) * len(STAGES),
        "sourceComparedByteCount": len(states) * len(STAGES) * TARGET_BYTES,
        "sourceUnequalByteCount": 0,
        "states": states,
        "TmuaSourceAffectsTghnPixels": False,
        "TmuaSourceAffectsCurrentIrsdPixels": False,
        "TmuaProducerOutputRequiredForWalle": False,
        "remainingAppleConstructionQuestions": [
            "bit-exact transfer of the recovered compositor arithmetic to the current small-clear Iscd/Irsd pair"
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
