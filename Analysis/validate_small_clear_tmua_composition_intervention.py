#!/usr/bin/env python3
"""Validate the prospective small-clear Tmua source-influence replay."""

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
from typing import Any, Never


type JsonObject = dict[str, Any]

REPOSITORY = Path(__file__).resolve().parents[1]
TGHN_PIPELINE = "com.apple.coreanimation.PBGRABsovXm_TghnA2Xhf_Isrc_Isrc"
FINAL_PIPELINE = "com.apple.coreanimation.PBGRAXm_A2Xghfc"
SAMPLES = tuple(range(2, 32))
INTERVENTIONS = (
    "zero-for-Tghn-only",
    "zero-for-Irsd-only",
    "zero-for-Tghn-and-Irsd",
)
CASES: dict[str, JsonObject] = {
    "clear-light-materialize-01": {
        "appearance": "light",
        "direction": "materialize",
        "geometry": "circle-combined-holdout-01",
        "diameter": 53,
        "center": [11.25, 211.75],
    },
    "clear-dark-dematerialize-06": {
        "appearance": "dark",
        "direction": "dematerialize",
        "geometry": "circle-combined-holdout-06",
        "diameter": 51,
        "center": [1002.75, 475.5],
    },
}


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
        require(
            sha256_file(path) == expected,
            f"pinned source differs: {relative}",
        )


def raw_payload(
    directory: Path,
    snapshot: Mapping[str, Any],
    label: str,
) -> bytes:
    width = snapshot.get("width")
    height = snapshot.get("height")
    pixel_format = snapshot.get("pixelFormat")
    bytes_per_pixel = {80: 4, 81: 4, 115: 8}.get(pixel_format)
    require(
        isinstance(width, int) and width > 0,
        f"{label} width differs",
    )
    require(
        isinstance(height, int) and height > 0,
        f"{label} height differs",
    )
    require(bytes_per_pixel is not None, f"{label} pixel format differs")
    expected_bytes = width * height * bytes_per_pixel
    require(snapshot.get("rawCapture") is True, f"{label} was not captured")
    require(snapshot.get("rawBytes") == expected_bytes, f"{label} rawBytes differs")
    filename = snapshot.get("rawFile")
    require(isinstance(filename, str), f"{label} raw filename differs")
    require(Path(filename).name == filename, f"{label} raw filename escapes root")
    path = directory / filename
    require(path.is_file(), f"{label} raw file is absent")
    payload = path.read_bytes()
    require(len(payload) == expected_bytes, f"{label} disk bytes differ")
    return payload


def validate_exact_comparison(
    comparison: Mapping[str, Any],
    expected_bytes: int,
    label: str,
) -> None:
    expected = {
        "compared": True,
        "exactByteMatch": True,
        "byteCount": expected_bytes,
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


def records_by_sample(timeline: Mapping[str, Any], label: str) -> dict[int, JsonObject]:
    uniforms = mapping(timeline.get("dynamicBackgroundUniforms"), f"{label} uniforms")
    require(uniforms.get("requested") is True, f"{label} uniforms not requested")
    require(uniforms.get("executed") is True, f"{label} uniforms did not execute")
    require(
        uniforms.get("evidenceMode") == "controlled-replay-v1",
        f"{label} evidence mode differs",
    )
    result: dict[int, JsonObject] = {}
    for value in sequence(uniforms.get("records"), f"{label} records"):
        record = mapping(value, f"{label} record")
        sample = record.get("sampleIndex")
        require(isinstance(sample, int), f"{label} sample index differs")
        require(sample not in result, f"{label} sample is duplicated")
        result[sample] = dict(record)
    require(set(SAMPLES).issubset(result), f"{label} candidate sample set differs")
    return result


def exact_pass(record: Mapping[str, Any], label: str) -> Mapping[str, Any]:
    render = mapping(record.get("render"), f"{label} render")
    replay = mapping(render.get("exactPassReplay"), f"{label} exact replay")
    require(replay.get("executed") is True, f"{label} exact replay failed")
    require(replay.get("exactByteMatch") is True, f"{label} exact replay differs")
    require(replay.get("mismatchedByteCount") == 0, f"{label} replay bytes differ")
    require(replay.get("mismatchedPixelCount") == 0, f"{label} replay pixels differ")
    require(replay.get("maximumChannelDelta") == 0, f"{label} replay delta differs")
    return replay


def missing_branch(record: Mapping[str, Any], label: str) -> bool:
    render = mapping(record.get("render"), f"{label} render")
    replay = mapping(render.get("exactPassReplay"), f"{label} exact replay")
    if replay.get("executed") is not False:
        return False
    require(
        replay.get("reason")
        == "captured adjacent small-clear Tghn/Irsd pass unavailable",
        f"{label} missing-branch reason differs",
    )
    require(
        replay.get("smallClearTmuaCompositionIntervention") is None,
        f"{label} missing branch contains an intervention",
    )
    return True


def validate_trace(
    directory: Path,
    replay: Mapping[str, Any],
    label: str,
) -> JsonObject:
    trace = mapping(
        replay.get("smallClearTmuaCompositionIntervention"),
        f"{label} intervention",
    )
    require(trace.get("schemaVersion") == 1, f"{label} trace schema differs")
    require(trace.get("executed") is True, f"{label} intervention failed")
    require(trace.get("eligible") is True, f"{label} intervention ineligible")
    require(
        trace.get("classification")
        == "captured Apple small-clear Tmua source influence intervention",
        f"{label} classification differs",
    )
    require(trace.get("liveAppleFrameMutated") is False, f"{label} live frame mutated")
    require(
        trace.get("capturedApplePipelinesUnmodified") is True,
        f"{label} Apple pipeline changed",
    )
    require(trace.get("tghnPipelineLabel") == TGHN_PIPELINE, f"{label} Tghn differs")
    require(trace.get("finalPipelineLabel") == FINAL_PIPELINE, f"{label} Irsd differs")
    tghn_pipeline = trace.get("tghnPipelineCommandIndex")
    tghn_draw = trace.get("tghnDrawIndex")
    final_pipeline = trace.get("finalPipelineCommandIndex")
    final_draw = trace.get("finalDrawIndex")
    require(
        all(isinstance(value, int) for value in (
            tghn_pipeline,
            tghn_draw,
            final_pipeline,
            final_draw,
        )),
        f"{label} command indices differ",
    )
    require(
        tghn_pipeline < tghn_draw < final_pipeline < final_draw,
        f"{label} command order differs",
    )
    require(final_pipeline == tghn_draw + 1, f"{label} draws are not adjacent")
    require(trace.get("drawsAreAdjacent") is True, f"{label} adjacency flag differs")

    descriptor = mapping(trace.get("sourceTextureDescriptor"), f"{label} descriptor")
    require(
        descriptor.get("width") in {64, 128}
        and descriptor.get("height") == 128
        and descriptor.get("pixelFormat") == 115
        and descriptor.get("mipmapLevelCount") == 1
        and descriptor.get("sampleCount") == 1
        and descriptor.get("textureType") == 2,
        f"{label} source texture descriptor differs",
    )
    source_snapshot = mapping(trace.get("sourceTexture"), f"{label} source snapshot")
    zero_snapshot = mapping(trace.get("zeroTexture"), f"{label} zero snapshot")
    source = raw_payload(directory, source_snapshot, f"{label} source")
    zero = raw_payload(directory, zero_snapshot, f"{label} zero")
    require(len(source) == len(zero), f"{label} source dimensions differ")
    require(not any(zero), f"{label} replacement texture is not zero")

    reference_snapshot = mapping(replay.get("replayOutput"), f"{label} reference")
    reference = raw_payload(directory, reference_snapshot, f"{label} reference")
    require(len(reference) == 4_194_304, f"{label} target byte count differs")
    records = sequence(trace.get("interventions"), f"{label} interventions")
    require(len(records) == len(INTERVENTIONS), f"{label} intervention count differs")
    require(trace.get("interventionCount") == len(records), f"{label} count field differs")
    observed_names: list[str] = []
    candidate_hashes: dict[str, str] = {}
    for untyped in records:
        intervention = mapping(untyped, f"{label} intervention record")
        name = intervention.get("name")
        require(isinstance(name, str), f"{label} intervention name differs")
        observed_names.append(name)
        candidate_replay = mapping(intervention.get("replay"), f"{label} {name} replay")
        require(candidate_replay.get("executed") is True, f"{label} {name} failed")
        candidate_snapshot = mapping(
            candidate_replay.get("output"), f"{label} {name} output"
        )
        candidate = raw_payload(directory, candidate_snapshot, f"{label} {name}")
        require(candidate == reference, f"{label} {name} raw bytes differ")
        comparison = mapping(
            intervention.get("comparison"), f"{label} {name} comparison"
        )
        validate_exact_comparison(comparison, len(reference), f"{label} {name}")
        candidate_hashes[name] = sha256_bytes(candidate)
    require(tuple(observed_names) == INTERVENTIONS, f"{label} intervention order differs")
    require(trace.get("allInterventionsExact") is True, f"{label} exact flag differs")
    return {
        "sourceSHA256": sha256_bytes(source),
        "zeroSHA256": sha256_bytes(zero),
        "sourceContainsNonzeroBytes": any(source),
        "sourceByteCount": len(source),
        "referenceSHA256": sha256_bytes(reference),
        "candidateSHA256": candidate_hashes,
    }


def validate(
    capture_root: Path,
    preregistration_path: Path,
    preflight_path: Path,
) -> JsonObject:
    preregistration = load_json(preregistration_path, "preregistration")
    require(
        preregistration.get("smallClearTmuaCompositionPreregistrationSchemaVersion")
        == 1,
        "preregistration schema differs",
    )
    validate_sources(preregistration)
    preflight = load_json(preflight_path, "Retina preflight")
    require(preflight.get("passed") is True, "Retina preflight failed")
    require(preflight.get("backingScaleFactor") == 2, "Retina scale differs")
    require(preflight.get("physicalPixels") == [3456, 2234], "Retina pixels differ")

    case_results: list[JsonObject] = []
    total_states = 0
    total_comparisons = 0
    total_compared_bytes = 0
    nonzero_source_states = 0
    for case_id, expected in CASES.items():
        directory = capture_root / case_id
        timeline_path = directory / "transition-timeline.json"
        require(timeline_path.is_file(), f"{case_id} timeline is absent")
        timeline = load_json(timeline_path, f"{case_id} timeline")
        for field, value in (
            ("material", "clear"),
            ("appearance", expected["appearance"]),
            ("direction", expected["direction"]),
            ("sampleCount", 33),
            ("windowBackingScaleFactor", 2),
            ("expectedWindowPixels", [2048, 2048]),
            ("failedSamples", 0),
        ):
            require(timeline.get(field) == value, f"{case_id} {field} differs")
        geometry = mapping(timeline.get("geometry"), f"{case_id} geometry")
        require(
            geometry.get("name") == expected["geometry"]
            and geometry.get("shape") == "circle"
            and geometry.get("width") == expected["diameter"]
            and geometry.get("height") == expected["diameter"]
            and geometry.get("centerX") == expected["center"][0]
            and geometry.get("centerY") == expected["center"][1],
            f"{case_id} geometry differs",
        )
        records = records_by_sample(timeline, case_id)
        executed: list[JsonObject] = []
        absent: list[int] = []
        for sample in SAMPLES:
            label = f"{case_id} sample {sample}"
            if missing_branch(records[sample], label):
                absent.append(sample)
                continue
            replay = exact_pass(records[sample], label)
            metrics = validate_trace(directory, replay, label)
            metrics["sampleIndex"] = sample
            executed.append(metrics)
            total_states += 1
            total_comparisons += len(INTERVENTIONS)
            total_compared_bytes += len(INTERVENTIONS) * 4_194_304
            nonzero_source_states += bool(metrics["sourceContainsNonzeroBytes"])
        require(executed, f"{case_id} has no eligible Tghn/Irsd state")
        case_results.append(
            {
                "caseId": case_id,
                "timelineSHA256": sha256_file(timeline_path),
                "eligibleStateCount": len(executed),
                "absentBranchSamples": absent,
                "states": executed,
            }
        )

    require(total_states > 0, "no Tmua intervention state executed")
    return {
        "smallClearTmuaCompositionResultSchemaVersion": 1,
        "status": "exact-current-build-small-clear-Tmua-source-irrelevance",
        "classification": (
            "prospective physical-Retina zero-tolerance replay of the captured "
            "Tmua source independently at Tghn and current Irsd"
        ),
        "captureRoot": capture_root.name,
        "caseCount": len(case_results),
        "eligibleStateCount": total_states,
        "interventionComparisonCount": total_comparisons,
        "comparedTargetByteCount": total_compared_bytes,
        "unequalTargetByteCount": 0,
        "nonzeroSourceStateCount": nonzero_source_states,
        "cases": case_results,
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
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--preflight", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(
        arguments.capture_root,
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
