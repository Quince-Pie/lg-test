#!/usr/bin/env python3
"""Validate the corrected populated-target Tmua and Tghn residual replay."""

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
from typing import Any, Never

import validate_small_clear_background_intervention as background_subject


type JsonObject = dict[str, Any]

REPOSITORY = Path(__file__).resolve().parents[1]
SAMPLES = tuple(range(2, 32))
TARGET_BYTES = 4_194_304
TMUA_NONZERO_SHA256 = "7db629a886e5cd6982b3e23b2170681194cf9956d97de086754e68598b705c3e"
TMUA_ZERO_SHA256 = {
    65_536: "de2f256064a0af797747c2b97505dc0b9f3df0de4f489eac731c23ae9ca9cc31",
    131_072: "fa43239bcee7b97ca62f007cc68487560a39e19f74f3dde7486db3f98df8e471",
}
TGHN_PIPELINE = "com.apple.coreanimation.PBGRABsovXm_TghnA2Xhf_Isrc_Isrc"
FINAL_PIPELINE = "com.apple.coreanimation.PBGRAXm_A2Xghfc"
ABSENT_REASON = "captured nonvacuous small-clear Tghn/Irsd pass unavailable"


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
    *,
    expected_format: int,
    expected_dimensions: tuple[int, int] | None = None,
) -> bytes:
    width = snapshot.get("width")
    height = snapshot.get("height")
    pixel_format = snapshot.get("pixelFormat")
    pixel_bytes = {80: 4, 115: 8}.get(pixel_format)
    require(isinstance(width, int) and width > 0, f"{label} width differs")
    require(isinstance(height, int) and height > 0, f"{label} height differs")
    if expected_dimensions is not None:
        require((width, height) == expected_dimensions, f"{label} dimensions differ")
    require(pixel_format == expected_format, f"{label} pixel format differs")
    require(pixel_bytes is not None, f"{label} pixel byte size differs")
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


def replay_payload(
    directory: Path,
    replay: Mapping[str, Any],
    label: str,
) -> bytes:
    require(replay.get("executed") is True, f"{label} replay failed")
    snapshot = mapping(replay.get("output"), f"{label} output")
    return raw_payload(
        directory,
        snapshot,
        label,
        expected_format=80,
        expected_dimensions=(1024, 1024),
    )


def validate_controlled_pattern(
    directory: Path,
    snapshot: Mapping[str, Any],
    label: str,
    dimensions: tuple[int, int],
    salt: int,
) -> str:
    payload = raw_payload(
        directory,
        snapshot,
        label,
        expected_format=80,
        expected_dimensions=dimensions,
    )
    require(
        payload == pattern_payload(*dimensions, salt),
        f"{label} controlled pattern differs",
    )
    return sha256_bytes(payload)


def validate_tmua_trace(
    directory: Path,
    trace: Mapping[str, Any],
    sample: int,
) -> JsonObject:
    label = f"sample {sample}"
    require(trace.get("schemaVersion") == 2, f"{label} schema differs")
    require(trace.get("executed") is True, f"{label} intervention failed")
    require(trace.get("eligible") is True, f"{label} intervention ineligible")
    require(
        trace.get("classification")
        == (
            "nonvacuous controlled-target Tmua/Tghn influence "
            "and explicit-Irsd-source replay"
        ),
        f"{label} classification differs",
    )
    require(trace.get("liveAppleFrameMutated") is False, f"{label} live frame mutated")
    require(
        trace.get("capturedApplePipelinesUnmodified") is True,
        f"{label} Apple pipeline changed",
    )
    require(trace.get("tghnPipelineLabel") == TGHN_PIPELINE, f"{label} Tghn differs")
    require(trace.get("finalPipelineLabel") == FINAL_PIPELINE, f"{label} Irsd differs")
    positions = tuple(
        trace.get(field)
        for field in (
            "tghnPipelineCommandIndex",
            "tghnDrawIndex",
            "finalPipelineCommandIndex",
            "finalDrawIndex",
        )
    )
    require(all(type(value) is int for value in positions), f"{label} positions differ")
    require(
        positions[0] < positions[1] < positions[2] < positions[3],
        f"{label} command order differs",
    )

    source_snapshot = mapping(trace.get("sourceTexture"), f"{label} source")
    zero_snapshot = mapping(trace.get("zeroTexture"), f"{label} zero")
    source_width = source_snapshot.get("width")
    require(source_width in (64, 128), f"{label} source width differs")
    source_dimensions = (source_width, 128)
    source = raw_payload(
        directory,
        source_snapshot,
        f"{label} source",
        expected_format=115,
        expected_dimensions=source_dimensions,
    )
    zero = raw_payload(
        directory,
        zero_snapshot,
        f"{label} zero",
        expected_format=115,
        expected_dimensions=source_dimensions,
    )
    require(not any(zero), f"{label} zero replacement is nonzero")
    source_hash = sha256_bytes(source)
    if any(source):
        require(source_hash == TMUA_NONZERO_SHA256, f"{label} nonzero source differs")
        source_kind = "nonzero"
    else:
        require(
            source_hash == TMUA_ZERO_SHA256[len(source)],
            f"{label} zero source hash differs",
        )
        source_kind = "zero"

    final_source = raw_payload(
        directory,
        mapping(trace.get("explicitFinalSource"), f"{label} final source"),
        f"{label} final source",
        expected_format=80,
        expected_dimensions=(1, 1),
    )
    require(
        trace.get("finalSourceDistinctFromTmua") is True,
        f"{label} final source identity differs",
    )
    controlled_hashes = {
        "destinationSeed": validate_controlled_pattern(
            directory,
            mapping(trace.get("destinationSeed"), f"{label} destination"),
            f"{label} destination",
            (1024, 1024),
            0x13579BDF,
        ),
        "controlledTghnBackdrop": validate_controlled_pattern(
            directory,
            mapping(trace.get("controlledTghnBackdrop"), f"{label} backdrop"),
            f"{label} backdrop",
            (64, 64),
            0x2468ACE0,
        ),
        "controlledFinalInput": validate_controlled_pattern(
            directory,
            mapping(trace.get("controlledFinalInput"), f"{label} final input"),
            f"{label} final input",
            (576, 448),
            0x0F1E2D3C,
        ),
    }

    tghn = mapping(trace.get("Tghn"), f"{label} Tghn")
    tghn_before = replay_payload(
        directory,
        mapping(tghn.get("before"), f"{label} Tghn before"),
        f"{label} Tghn before",
    )
    tghn_reference = replay_payload(
        directory,
        mapping(tghn.get("reference"), f"{label} Tghn reference"),
        f"{label} Tghn reference",
    )
    tghn_zero = replay_payload(
        directory,
        mapping(tghn.get("zeroSource"), f"{label} Tghn zero"),
        f"{label} Tghn zero",
    )
    activity = comparison_metrics(tghn_before, tghn_reference)
    source_comparison = comparison_metrics(tghn_reference, tghn_zero)
    require(activity["mismatchedByteCount"] > 0, f"{label} Tghn control is vacuous")
    require(
        source_comparison["mismatchedByteCount"] == 0,
        f"{label} Tmua replacement changes Tghn",
    )
    validate_reported_comparison(
        mapping(tghn.get("activityComparison"), f"{label} Tghn activity"),
        activity,
        f"{label} Tghn activity",
    )
    validate_reported_comparison(
        mapping(tghn.get("sourceComparison"), f"{label} Tghn source"),
        source_comparison,
        f"{label} Tghn source",
    )
    require(
        trace.get("tghnPositiveControlPassed") is True,
        f"{label} Tghn control flag differs",
    )
    require(
        trace.get("sourceComparisonsExact") is True,
        f"{label} source flag differs",
    )

    irsd = mapping(trace.get("Irsd"), f"{label} Irsd")
    irsd_before = replay_payload(
        directory,
        mapping(irsd.get("before"), f"{label} Irsd before"),
        f"{label} Irsd before",
    )
    irsd_reference = replay_payload(
        directory,
        mapping(irsd.get("reference"), f"{label} Irsd reference"),
        f"{label} Irsd reference",
    )
    irsd_activity = comparison_metrics(irsd_before, irsd_reference)
    validate_reported_comparison(
        mapping(irsd.get("activityComparison"), f"{label} Irsd activity"),
        irsd_activity,
        f"{label} Irsd activity",
    )
    require(
        trace.get("IrsdActivityObserved") is (irsd_activity["mismatchedByteCount"] > 0),
        f"{label} Irsd activity flag differs",
    )
    return {
        "sampleIndex": sample,
        "TmuaSourceKind": source_kind,
        "TmuaSourceSHA256": source_hash,
        "explicitFinalSourceSHA256": sha256_bytes(final_source),
        "controlledTextureSHA256": controlled_hashes,
        "TghnActivityMismatchedByteCount": activity["mismatchedByteCount"],
        "TghnActivityMismatchedPixelCount": activity["mismatchedPixelCount"],
        "TghnReferenceSHA256": sha256_bytes(tghn_reference),
        "TghnZeroSourceSHA256": sha256_bytes(tghn_zero),
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
    label = f"sample {sample} Tghn residual"
    require(trace.get("schemaVersion") == 2, f"{label} schema differs")
    require(trace.get("executed") is True, f"{label} intervention failed")
    require(trace.get("eligible") is True, f"{label} intervention ineligible")
    require(trace.get("selected") is True, f"{label} was not selected")
    require(
        trace.get("classification")
        == (
            "captured Apple small-clear Tghn coordinate/tail "
            "nonvacuous pixel-influence intervention"
        ),
        f"{label} classification differs",
    )
    require(trace.get("nonvacuousControlledTarget") is True, f"{label} mode differs")
    require(trace.get("positiveControlPassed") is True, f"{label} control flag differs")
    require(
        trace.get("allInterventionsExact") is True, f"{label} candidate flag differs"
    )
    require(
        trace.get("originalActiveVertexSHA256") == sha256_bytes(inputs["vertex"]),
        f"{label} original vertex differs",
    )
    require(
        trace.get("fragmentPrefixSHA256") == sha256_bytes(inputs["fragment"]),
        f"{label} fragment differs",
    )
    require(
        trace.get("indexSHA256") == sha256_bytes(inputs["index"]),
        f"{label} index differs",
    )
    trace_axes = sequence(trace.get("axisDecisions"), f"{label} axes")
    require(len(trace_axes) == 2, f"{label} axis count differs")
    for observed, expected in zip(trace_axes, decision["axes"], strict=True):
        background_subject.validate_trace_axis(
            mapping(observed, f"{label} axis"),
            expected,
        )

    destination_hash = validate_controlled_pattern(
        directory,
        mapping(trace.get("destinationSeed"), f"{label} destination"),
        f"{label} destination",
        (1024, 1024),
        0x13579BDF,
    )
    backdrop_hash = validate_controlled_pattern(
        directory,
        mapping(trace.get("controlledTghnBackdrop"), f"{label} backdrop"),
        f"{label} backdrop",
        (64, 64),
        0x2468ACE0,
    )
    before = replay_payload(
        directory,
        mapping(trace.get("before"), f"{label} before"),
        f"{label} before",
    )
    reference = replay_payload(
        directory,
        mapping(trace.get("reference"), f"{label} reference"),
        f"{label} reference",
    )
    activity = comparison_metrics(before, reference)
    require(activity["mismatchedByteCount"] > 0, f"{label} control is vacuous")
    validate_reported_comparison(
        mapping(trace.get("activityComparison"), f"{label} activity"),
        activity,
        f"{label} activity",
    )

    expected_streams = background_subject.mutated_vertex_streams(
        inputs["vertex"],
        decision,
    )
    interventions = {
        mapping(value, f"{label} intervention").get("name"): mapping(
            value,
            f"{label} intervention",
        )
        for value in sequence(trace.get("interventions"), f"{label} interventions")
    }
    require(
        set(interventions) == set(background_subject.INTERVENTIONS),
        f"{label} intervention names differ",
    )
    intervention_results: list[JsonObject] = []
    for name in background_subject.INTERVENTIONS:
        intervention = interventions[name]
        require(
            intervention.get("mutatedActiveVertexSHA256")
            == sha256_bytes(expected_streams[name]),
            f"{label} {name} vertex differs",
        )
        candidate = replay_payload(
            directory,
            mapping(intervention.get("replay"), f"{label} {name} replay"),
            f"{label} {name}",
        )
        comparison = comparison_metrics(reference, candidate)
        require(
            comparison["mismatchedByteCount"] == 0,
            f"{label} {name} changes output",
        )
        validate_reported_comparison(
            mapping(intervention.get("comparison"), f"{label} {name} comparison"),
            comparison,
            f"{label} {name}",
        )
        intervention_results.append(
            {
                "name": name,
                "mutatedActiveVertexSHA256": sha256_bytes(expected_streams[name]),
                "candidateSHA256": sha256_bytes(candidate),
                "unequalByteCount": 0,
            }
        )
    return {
        "sampleIndex": sample,
        "positiveControlMismatchedByteCount": activity["mismatchedByteCount"],
        "positiveControlMismatchedPixelCount": activity["mismatchedPixelCount"],
        "referenceSHA256": sha256_bytes(reference),
        "destinationSeedSHA256": destination_hash,
        "controlledBackdropSHA256": backdrop_hash,
        "interventions": intervention_results,
        "comparedByteCount": len(intervention_results) * TARGET_BYTES,
        "unequalByteCount": 0,
    }


def validate_background_selection_trace(
    trace: Mapping[str, Any],
    *,
    sample: int,
    should_select: bool,
    has_differing_axis: bool,
) -> None:
    if should_select:
        require(trace.get("selected") is True, f"sample {sample} selection differs")
        return
    require(trace.get("executed") is False, f"sample {sample} residual executed")
    require(trace.get("selected") is False, f"sample {sample} residual selected")
    if has_differing_axis:
        require(trace.get("eligible") is True, f"sample {sample} eligibility differs")
        require(
            trace.get("reason") == "earlier eligible Tghn state selected",
            f"sample {sample} post-selection reason differs",
        )
    else:
        require(trace.get("eligible") is False, f"sample {sample} eligibility differs")
        require(
            trace.get("reason") == "no differing exact-halfway decision in state",
            f"sample {sample} pre-selection reason differs",
        )


def validate(
    capture_directory: Path,
    preregistration_path: Path,
    preflight_path: Path,
) -> JsonObject:
    preregistration = load_json(preregistration_path, "preregistration")
    require(
        preregistration.get("smallClearTmuaNonvacuousV2PreregistrationSchemaVersion")
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
        require(type(sample) is int, "sample index differs")
        records[sample] = record
    require(set(SAMPLES).issubset(records), "candidate sample set differs")

    branch_data: dict[int, tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
    absent_samples: list[int] = []
    for sample in SAMPLES:
        record = records[sample]
        inputs = background_subject.branch_inputs(record)
        render = mapping(record.get("render"), f"sample {sample} render")
        replay = mapping(render.get("exactPassReplay"), f"sample {sample} replay")
        if inputs is None:
            require(replay.get("executed") is False, f"sample {sample} replay executed")
            require(
                replay.get("reason") == ABSENT_REASON, f"sample {sample} reason differs"
            )
            absent_samples.append(sample)
            continue
        require(replay.get("executed") is True, f"sample {sample} replay failed")
        decision = background_subject.decision_from_inputs(inputs)
        branch_data[sample] = (inputs, decision)

    require(len(branch_data) >= 20, "too few Tghn-bearing states")
    selected_candidates = [
        sample for sample, (_, decision) in branch_data.items() if decision["differing"]
    ]
    require(selected_candidates, "no Tghn residual candidate exists")
    selected_sample = selected_candidates[0]

    tmua_states: list[JsonObject] = []
    selected_background: JsonObject | None = None
    for sample, (inputs, decision) in branch_data.items():
        record = records[sample]
        render = mapping(record.get("render"), f"sample {sample} render")
        replay = mapping(render.get("exactPassReplay"), f"sample {sample} replay")
        tmua_trace = mapping(
            replay.get("smallClearTmuaNonvacuousIntervention"),
            f"sample {sample} Tmua intervention",
        )
        tmua_states.append(validate_tmua_trace(capture_directory, tmua_trace, sample))
        background_trace = mapping(
            replay.get("smallClearBackgroundNonvacuousIntervention"),
            f"sample {sample} Tghn residual",
        )
        validate_background_selection_trace(
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
    require(selected_background is not None, "selected Tghn residual is absent")
    nonzero_count = sum(state["TmuaSourceKind"] == "nonzero" for state in tmua_states)
    zero_count = len(tmua_states) - nonzero_count
    require(nonzero_count > 0, "no nonzero Tmua source state was tested")
    require(zero_count > 0, "no zero Tmua source state was tested")
    irsd_activity_count = sum(
        state["IrsdActivityMismatchedByteCount"] > 0 for state in tmua_states
    )

    return {
        "smallClearTmuaNonvacuousV2ResultSchemaVersion": 1,
        "status": "exact-nonvacuous-small-clear-Tmua-and-Tghn-residual-closure",
        "classification": (
            "prospective physical-Retina populated-target replay over every "
            "branch-bearing grid state"
        ),
        "captureDirectory": capture_directory.name,
        "timelineSHA256": sha256_file(timeline_path),
        "candidateSampleCount": len(SAMPLES),
        "branchBearingStateCount": len(tmua_states),
        "absentBranchSamples": absent_samples,
        "nonzeroTmuaSourceStateCount": nonzero_count,
        "zeroTmuaSourceStateCount": zero_count,
        "TghnPositiveControlCount": len(tmua_states),
        "TmuaSourceComparisonCount": len(tmua_states),
        "TmuaSourceComparedByteCount": len(tmua_states) * TARGET_BYTES,
        "TmuaSourceUnequalByteCount": 0,
        "IrsdActivityStateCount": irsd_activity_count,
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
