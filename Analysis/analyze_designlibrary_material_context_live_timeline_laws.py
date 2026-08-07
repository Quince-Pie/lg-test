#!/usr/bin/env python3
"""Prove observed-domain Material.Context laws from frozen native transfers."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Mapping, Sequence, Tuple

import capture_designlibrary_parameters_mixer_basis_local_macos_26_6_1 as basis


SCHEMA_VERSION = 1
ZERO_FLAGS_RESULT_NAME = "designlibrary_material_context_live_timeline_transfer_local_macos_26_6_1_result.json"
FLAGS_RESULT_NAME = "designlibrary_material_context_flags_live_timeline_transfer_local_macos_26_6_1_result.json"
EXPECTED_ZERO_FLAGS_RESULT_SHA256 = (
    "6237b29fa78c1626df9ed95aed6d3d8ad6c026b290c66def1e3af8380b54f570"
)
EXPECTED_FLAGS_RESULT_SHA256 = (
    "7df7230548463675d00a7bc78dac0003cd08a9beb19e9b53268b3a6073c15ac7"
)


class AnalysisError(RuntimeError):
    """Raised when frozen context evidence violates the exact law."""


@dataclass(frozen=True)
class Law:
    name: str
    expression: str
    evaluate: Callable[[float], float]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_json(path: Path, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AnalysisError(label + " is unreadable") from error
    if not isinstance(value, dict):
        raise AnalysisError(label + " is not an object")
    return value


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def binary64_bits(value: float) -> str:
    return "0x{0:016x}".format(struct.unpack("<Q", struct.pack("<d", value))[0])


def field_by_name(name: str):
    matches = [field for field in basis.SCALAR_FIELDS if field.name == name]
    if len(matches) != 1:
        raise AnalysisError("unknown scalar field " + name)
    return matches[0]


def flags_shadow_opacity(dimension: float) -> float:
    shape_fraction = (dimension - 48.0) / 112.0
    small_product = f32(0.5 * (1.0 - shape_fraction))
    large_product = f32(0.25 * shape_fraction)
    return f32(small_product + large_product)


def flags_blur_radius(dimension: float) -> float:
    shape_fraction = (dimension - 48.0) / 112.0
    small_radius = 8.0 / 3.0
    return small_radius + (8.0 - small_radius) * shape_fraction


def flags_edge_opacity(dimension: float) -> float:
    effect_fraction = (dimension - 64.0) / 96.0
    return f32(effect_fraction * 0.5)


def flags_sdr_shadow_opacity_shift(dimension: float) -> float:
    shape_fraction = f32((dimension - 48.0) / 112.0)
    small_shift = f32(0.08)
    shift_delta = f32(0.24 - 0.08)
    return f32(small_shift + f32(shift_delta * shape_fraction))


ZERO_FLAGS_LAWS = (
    Law("shadow.height", "x * 0.4", lambda x: x * 0.4),
    Law("blur.radius", "4 + (x - 48) / 28", lambda x: 4.0 + (x - 48.0) / 28.0),
    Law("edgeBleed.amount", "x * 0.35", lambda x: x * 0.35),
    Law("edgeBleed.height", "x * 0.35", lambda x: x * 0.35),
)

FLAGS_LAWS = (
    Law("shadow.height", "x * 0.4", lambda x: x * 0.4),
    Law(
        "shadow.opacity",
        "f32(f32(0.5 * (1 - u)) + f32(0.25 * u)), u=(x-48)/112",
        flags_shadow_opacity,
    ),
    Law(
        "shadow.vibrancyContribution",
        "(x - 64) / 96",
        lambda x: (x - 64.0) / 96.0,
    ),
    Law(
        "blur.radius",
        "b + (8 - b) * u, b=8/3, u=(x-48)/112",
        flags_blur_radius,
    ),
    Law("blur.distances.0", "-x / 2", lambda x: -x / 2.0),
    Law("refraction.outerHeight", "x / 8", lambda x: x / 8.0),
    Law("refraction.outerAmount", "x * 0.2", lambda x: x * 0.2),
    Law("edgeBleed.amount", "x * 0.35", lambda x: x * 0.35),
    Law("edgeBleed.height", "x * 0.35", lambda x: x * 0.35),
    Law("edgeBleed.blurRadius", "x * 0.7", lambda x: x * 0.7),
    Law(
        "edgeBleed.opacity",
        "f32(((x - 64) / 96) * 0.5)",
        flags_edge_opacity,
    ),
    Law(
        "sdrAdjustment.shadowOpacityShift",
        "f32(f32(0.08) + f32(f32(0.24 - 0.08) * f32((x-48)/112)))",
        flags_sdr_shadow_opacity_shift,
    ),
)


def validate_result(
    value: Mapping[str, object],
    schema_key: str,
    transfer_claim: str,
    expected_case_count: int,
) -> Tuple[Sequence[Mapping[str, object]], Mapping[str, object]]:
    if value.get(schema_key) != 1:
        raise AnalysisError("context transfer schema differs")
    claims = value.get("claims")
    invariants = value.get("measuredInvariants")
    cases = value.get("cases")
    unique = value.get("uniqueNormalizedParameters")
    if (
        not isinstance(claims, dict)
        or claims.get(transfer_claim) is not True
        or not isinstance(invariants, dict)
        or invariants.get("caseCount") != expected_case_count
        or invariants.get("freshProcessSemanticStabilityEstablished") is not True
        or not isinstance(cases, list)
        or len(cases) != expected_case_count
        or not isinstance(unique, dict)
    ):
        raise AnalysisError("context transfer authority differs")
    return cases, unique


def normalized_payload(
    case: Mapping[str, object], unique: Mapping[str, object]
) -> bytes:
    digest = case.get("normalizedParametersSHA256")
    record = unique.get(digest)
    if not isinstance(digest, str) or not isinstance(record, dict):
        raise AnalysisError("normalized Parameters record is absent")
    try:
        payload = bytes.fromhex(str(record["normalizedHex"]))
    except (KeyError, ValueError) as error:
        raise AnalysisError("normalized Parameters hex differs") from error
    if len(payload) != basis.PARAMETERS_BYTE_COUNT or digest_bytes(payload) != digest:
        raise AnalysisError("normalized Parameters identity differs")
    if basis.normalize_parameters(payload) != payload:
        raise AnalysisError("Parameters payload is not normalized")
    return payload


def observed_varying_scalar_names(payloads: Sequence[bytes]) -> Tuple[str, ...]:
    names = []
    for field in basis.SCALAR_FIELDS:
        size = struct.calcsize("<" + field.format)
        values = {payload[field.offset : field.offset + size] for payload in payloads}
        if len(values) > 1:
            names.append(field.name)
    for field in basis.COLOR_FIELDS:
        values = {payload[field.offset : field.offset + 17] for payload in payloads}
        if len(values) > 1:
            raise AnalysisError("unexpected varying color field " + field.name)
    for name, (offset, _present, _nil) in basis.CONTAINER_PRESENCE.items():
        if len({payload[offset] for payload in payloads}) > 1:
            raise AnalysisError("unexpected varying presence field " + name)
    return tuple(names)


def analyze_profile(
    name: str,
    cases: Sequence[Mapping[str, object]],
    unique: Mapping[str, object],
    laws: Sequence[Law],
    prediction_key: str,
) -> Mapping[str, object]:
    payloads = [normalized_payload(case, unique) for case in cases]
    law_names = tuple(law.name for law in laws)
    varying_names = observed_varying_scalar_names(payloads)
    if varying_names != law_names:
        raise AnalysisError(name + " varying field set differs")

    template = bytearray(payloads[0])
    variable_offsets = set()
    law_records: List[Mapping[str, object]] = []
    for law in laws:
        field = field_by_name(law.name)
        size = struct.calcsize("<" + field.format)
        variable_offsets.update(range(field.offset, field.offset + size))
        raw_matches = 0
        observations = []
        for case, payload in zip(cases, payloads):
            dimension = float(case["shapeDimension"])
            predicted = struct.pack("<" + field.format, law.evaluate(dimension))
            observed = payload[field.offset : field.offset + size]
            if predicted == observed:
                raw_matches += 1
            observations.append(
                {
                    "caseIndex": case["index"],
                    "dimensionBits": case["shapeDimensionBits"],
                    "observedRawLittleEndianHex": observed.hex(),
                    "predictedRawLittleEndianHex": predicted.hex(),
                    "matchedBitwise": predicted == observed,
                }
            )
        if raw_matches != len(cases):
            raise AnalysisError(name + " law differs for " + law.name)
        law_records.append(
            {
                "field": law.name,
                "offset": field.offset,
                "storage": "binary32" if field.format == "f" else "binary64",
                "expressionWithOperationOrder": law.expression,
                "bitwiseMatchCount": raw_matches,
                "observations": observations,
            }
        )

    reconstruction_matches = 0
    dimension_matches = 0
    transfer_matches = 0
    transfer_count = 0
    reconstruction_records = []
    for case, payload in zip(cases, payloads):
        fraction = float(case["fraction"])
        dimension = float(case["shapeDimension"])
        predicted_dimension = 143.0 - 16.0 * fraction
        dimension_matched = binary64_bits(predicted_dimension) == str(
            case["shapeDimensionBits"]
        )
        dimension_matches += int(dimension_matched)
        reconstructed = bytearray(template)
        for law in laws:
            field = field_by_name(law.name)
            struct.pack_into(
                "<" + field.format,
                reconstructed,
                field.offset,
                law.evaluate(dimension),
            )
        reconstructed_matched = bytes(reconstructed) == payload
        reconstruction_matches += int(reconstructed_matched)
        predictions = case.get(prediction_key)
        if not isinstance(predictions, list):
            raise AnalysisError(name + " transfer predictions are absent")
        transfer_count += len(predictions)
        transfer_matches += sum(
            prediction.get("matchedBitwise") is True
            for prediction in predictions
            if isinstance(prediction, dict)
        )
        reconstruction_records.append(
            {
                "caseIndex": case["index"],
                "fractionBits": case["fractionBits"],
                "dimensionBits": case["shapeDimensionBits"],
                "predictedDimensionBits": binary64_bits(predicted_dimension),
                "dimensionLawMatchedBitwise": dimension_matched,
                "observedNormalizedParametersSHA256": digest_bytes(payload),
                "reconstructedNormalizedParametersSHA256": digest_bytes(
                    bytes(reconstructed)
                ),
                "fullNormalizedParametersMatchedBitwise": reconstructed_matched,
            }
        )
    if dimension_matches != len(cases):
        raise AnalysisError(name + " dimension production law differs")
    if reconstruction_matches != len(cases):
        raise AnalysisError(name + " full Parameters reconstruction differs")
    if transfer_matches != transfer_count:
        raise AnalysisError(name + " retained live transfer differs")

    constant_projection = bytearray(template)
    for offset in variable_offsets:
        constant_projection[offset] = 0
    for payload in payloads:
        projected = bytearray(payload)
        for offset in variable_offsets:
            projected[offset] = 0
        if projected != constant_projection:
            raise AnalysisError(name + " constant Parameters projection differs")

    return {
        "name": name,
        "caseCount": len(cases),
        "uniqueDimensionWordCount": len(
            {str(case["shapeDimensionBits"]) for case in cases}
        ),
        "dimensionLaw": {
            "expressionWithOperationOrder": "x = 143 - 16 * k",
            "bitwiseMatchCount": dimension_matches,
        },
        "varyingScalarFields": law_records,
        "varyingSemanticByteOffsets": sorted(variable_offsets),
        "constantNormalizedProjectionSHA256": digest_bytes(bytes(constant_projection)),
        "fullNormalizedParametersReconstructionMatchCount": (reconstruction_matches),
        "retainedLiveTransferMatchCount": transfer_matches,
        "retainedLiveTransferPredictionCount": transfer_count,
        "reconstructions": reconstruction_records,
    }


def analyze(output_path: Path) -> Mapping[str, object]:
    analysis_directory = Path(__file__).resolve().parent
    source_path = Path(__file__).resolve()
    zero_path = analysis_directory / ZERO_FLAGS_RESULT_NAME
    flags_path = analysis_directory / FLAGS_RESULT_NAME
    if sha256(zero_path) != EXPECTED_ZERO_FLAGS_RESULT_SHA256:
        raise AnalysisError("zero-flags transfer result identity differs")
    if sha256(flags_path) != EXPECTED_FLAGS_RESULT_SHA256:
        raise AnalysisError("flags-produced transfer result identity differs")
    zero = load_json(zero_path, "zero-flags context transfer")
    flags = load_json(flags_path, "flags-produced context transfer")
    zero_cases, zero_unique = validate_result(
        zero,
        "designLibraryMaterialContextLiveTimelineTransferCaptureSchemaVersion",
        "exactZeroFlagsContextToOpenedLiveProviderFieldsTransferEstablished",
        31,
    )
    flags_cases, flags_unique = validate_result(
        flags,
        "designLibraryMaterialContextFlagsLiveTimelineTransferCaptureSchemaVersion",
        "exactFlagsProducedContextToOpenedLivePublicFieldsTransferEstablished",
        32,
    )
    profiles = [
        analyze_profile(
            "zeroFlagsRegularLight",
            zero_cases,
            zero_unique,
            ZERO_FLAGS_LAWS,
            "providerPredictions",
        ),
        analyze_profile(
            "flagsProducedRegularLight",
            flags_cases,
            flags_unique,
            FLAGS_LAWS,
            "publicPredictions",
        ),
    ]
    result = {
        "designLibraryMaterialContextLiveTimelineLawAnalysisSchemaVersion": (
            SCHEMA_VERSION
        ),
        "classification": (
            "deterministic retrospective whole-Parameters reconstruction of two "
            "independently prospectively captured Material.Context live domains; "
            "no GUI, render, image, crop, pixel, or captured-value runtime selection"
        ),
        "inputs": {
            "zeroFlagsTransfer": {
                "path": "Analysis/" + zero_path.name,
                "sha256": sha256(zero_path),
            },
            "flagsProducedTransfer": {
                "path": "Analysis/" + flags_path.name,
                "sha256": sha256(flags_path),
            },
            "analysisSource": {
                "path": "Analysis/" + source_path.name,
                "sha256": sha256(source_path),
            },
        },
        "profiles": profiles,
        "measuredInvariants": {
            "profileCount": 2,
            "capturedCaseCount": 63,
            "fullNormalizedParametersReconstructionMatchCount": sum(
                int(profile["fullNormalizedParametersReconstructionMatchCount"])
                for profile in profiles
            ),
            "retainedLiveTransferPredictionCount": sum(
                int(profile["retainedLiveTransferPredictionCount"])
                for profile in profiles
            ),
            "retainedLiveTransferMatchCount": sum(
                int(profile["retainedLiveTransferMatchCount"]) for profile in profiles
            ),
            "capturedValuesUsedForRuntimeSelection": False,
        },
        "claims": {
            "exactObservedTimelineContextValueLawEstablished": True,
            "allCapturedNormalizedParametersReconstructedBitwise": True,
            "allOpenedLiveFieldsReplayedBitwise": True,
            "completeLiveParametersTransferEstablished": False,
            "generalContextToParametersValueLawEstablished": False,
            "liveContextCallbackProductionEstablished": False,
            "generalIntegerCropAllocationPolicyEstablished": False,
            "retinaCompositorColorLawEstablished": False,
            "independentWalleZeroByteFrameParityEstablished": False,
            "liquidGlassParityEstablished": False,
            "productionShaderChangeAuthorized": False,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    try:
        analyze(arguments.output.resolve())
    except AnalysisError as error:
        print("ANALYSIS_ERROR: " + str(error))
        return 1
    print(str(arguments.output.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
